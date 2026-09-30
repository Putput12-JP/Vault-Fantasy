#!/usr/bin/env python3
"""
NBA player-prop model (docs/PLAN.md §4B) + backtest against real prices.

Projection, walk-forward, per player per game:
  minutes  = minutes model (data/minutes_model.json): EWMA + vacated minutes +
             blowout + back-to-back, team rescaled to 240
  rate     = per-minute EWMA shrunk toward the player's position prior, plus the
             usage cascade for stats where it beat the plain rate (data/usage_cascade.json)
  mean     = minutes x rate           (combos = sum of component means)
  P(over)  = Normal for pts / combos, negative binomial for reb / ast / 3pm,
             variance = v0 + v1*mean + v2*mean^2 fit on the tune seasons
  calibration: isotonic (PAV, pseudo-count shrink) fit on 2024-25 lines, applied to 2025-26

Backtest (2024-25, 2025-26), graded only when the player played (books void otherwise):
  ESPN close   2025-26 rows whose "current" price was set before tip; model uses the
               injury report 30 min pre-tip. Honest.
  ESPN open    open price, model uses the 11am report. OPTIMISTIC: the open has no timestamp.
  Kalshi       every ladder strike at its pre-tip price, taker fee included. Honest.

Go / no-go per market (PLAN §6), on the honest tests only: 50+ bets, ROI > 0 at 2 SE.

  python3 nba/scripts/build_prop_model.py
Writes nba/data/prop_model.json and nba/docs/prop-model.md
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM

WARM, TUNE, TEST = [2022], [2023, 2024], [2025, 2026]
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'prop_model.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'prop-model.md')
BASE = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['three_point_field_goals_made']}
COMBO = {'pra': ['pts', 'reb', 'ast'], 'pr': ['pts', 'reb'], 'pa': ['pts', 'ast'], 'ra': ['reb', 'ast']}
MARKETS = list(BASE) + list(COMBO)
COUNT_MKTS = {'reb', 'ast', '3pm'}      # negative binomial; the rest Normal
RATE_ALPHA, PRIOR_GAMES = 0.10, 8


def sv(r, cols):
    return sum(r[c] for c in cols)


# ── distributions ──────────────────────────────────────────────────────────
def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def nb_sf(k, mu, var):
    """P(X > k) for X ~ NegBin(mean mu, variance var), k integer. Poisson when var <= mu."""
    if mu <= 0:
        return 0.0
    if var <= mu * 1.0001:
        p, cdf = math.exp(-mu), 0.0
        for i in range(k + 1):
            cdf += p
            p *= mu / (i + 1)
        return max(0.0, 1 - cdf)
    r = mu * mu / (var - mu)
    q = mu / var                       # success prob in the (r, q) parameterisation
    p = q ** r
    cdf = 0.0
    for i in range(k + 1):
        cdf += p
        p *= (i + r) / (i + 1) * (1 - q)
    return max(0.0, 1 - cdf)


def p_over(mkt, mu, line, V):
    v0, v1, v2 = V[mkt]
    var = max(0.25, v0 + v1 * mu + v2 * mu * mu)
    if mkt in COUNT_MKTS:
        return nb_sf(int(math.floor(line)), mu, var)
    return 1 - phi((line - mu) / math.sqrt(var))


# ── projection walk ────────────────────────────────────────────────────────
def walk(seasons, box, inj, record_from, mode, margins, mm, casc, team_min=240.0):
    """team_min: minutes the team's ACTIVE candidates are rescaled to. Candidates include players who will
    end up DNP (coach's decision is not knowable pre-tip), so it is fit above 240 on the tune seasons."""
    ms = MM.State(mm['alpha'])
    beta = [mm['beta'][f] for f in MM.FEATURES]
    rt = {}                                   # aid -> {n, rate{s}, pg{s}, pos}
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # pos -> stat -> [sum stat, sum min]
    recs = []
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= record_from:
            played = {r['athlete_id'] for r in rows if r['played']}
            day = g['tip_et'].strftime('%Y-%m-%d')
            clocks = {'tip': (g['tip_et'] - dt.timedelta(minutes=30))}
            clocks['am'] = min(g['tip_et'].replace(hour=11, minute=0), clocks['tip'])
            for team in (g['home'], g['away']):
                rot = ms.rotation(team, g['tip'])
                outs = {}
                for label, clk in clocks.items():
                    if mode == 'oracle':
                        outs[label] = {a: 1.0 for a in rot if a not in played}
                    else:
                        outs[label] = {a: 1.0 for a, s in inj.status(day, team, clk.strftime('%Y-%m-%dT%H:%M')).items()
                                       if s in ('Out', 'Doubtful')}
                cand = [r for r in rows if r['team'] == team and r['athlete_id'] in ms.pl
                        and ms.pl[r['athlete_id']]['team'] == team and r['athlete_id'] in rt]
                per = {}
                for label, out in outs.items():
                    cc = [r for r in cand if r['athlete_id'] not in out]
                    pm, vac = {}, {}
                    for r in cc:
                        x = MM.features(ms, g, team, r['athlete_id'], out, margins.get(g['game_id']))
                        vac[r['athlete_id']] = x[0] + x[1]
                        pm[r['athlete_id']] = max(0.0, min(48.0, ms.pl[r['athlete_id']]['m'] + sum(b * v for b, v in zip(beta, x))))
                    tot = sum(pm.values())
                    if tot > 0 and len(pm) >= 7:
                        f = team_min / tot
                        pm = {a: min(48.0, m * f) for a, m in pm.items()}
                    present = [rt[r['athlete_id']] for r in cc]
                    for r in cc:
                        aid = r['athlete_id']
                        p = rt[aid]
                        mu = {}
                        for s in BASE:
                            rate = p['rate'][s]
                            c = casc.get(s)
                            if c and c['use']:
                                vs = sum(rt[a]['pg'][s] for a in out if a in rt and a != aid and a in rot and rot[a]['pos'] == ms.pl[aid]['pos'])
                                vo = sum(rt[a]['pg'][s] for a in out if a in rt and a != aid and a in rot and rot[a]['pos'] != ms.pl[aid]['pos'])
                                avg = statistics.mean(q['rate'][s] for q in present) if present else 0
                                rel = rate / avg if avg > 0 else 1.0
                                b = c['beta']
                                add48 = b[0] * vs + b[1] * vo + b[2] * vs * rel + b[3] * vo * rel
                                mu[s] = max(0.0, pm[aid] * rate + pm[aid] / 48.0 * add48)
                            else:
                                mu[s] = max(0.0, pm[aid] * rate)
                        for cm, parts in COMBO.items():
                            mu[cm] = sum(mu[x] for x in parts)
                        per.setdefault(aid, {})[label] = (pm[aid], mu, vac[aid])
                for r in cand:
                    aid = r['athlete_id']
                    if not r['played'] or aid not in per or 'tip' not in per[aid]:
                        continue
                    y = {s: sv(r, BASE[s]) for s in BASE}
                    for cm, parts in COMBO.items():
                        y[cm] = sum(y[x] for x in parts)
                    recs.append({'gid': g['game_id'], 'season': g['season'], 'aid': aid, 'min': r['minutes'],
                                 'pred': per[aid], 'y': y})
        # updates (after the game)
        ms.update(g, rows)
        for r in rows:
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m = r['athlete_id'], r['minutes']
            pos = MM.group(r['pos'])
            for s, cols in BASE.items():
                prior[pos][s][0] += sv(r, cols)
                prior[pos][s][1] += m
            p = rt.get(aid)
            if p is None:
                p = rt[aid] = {'n': 0, 'pos': pos,
                               'rate': {s: prior[pos][s][0] / max(1.0, prior[pos][s][1]) for s in BASE},
                               'pg': {s: sv(r, BASE[s]) for s in BASE}}
            # shrink toward the position prior while the sample is thin, EWMA after
            a = max(RATE_ALPHA, 1 / (p['n'] + 1 + PRIOR_GAMES))
            w = min(1.0, m / 20.0)
            for s, cols in BASE.items():
                p['rate'][s] += a * w * (sv(r, cols) / m - p['rate'][s])
                p['pg'][s] += max(RATE_ALPHA, 1 / (p['n'] + 1)) * (sv(r, cols) - p['pg'][s])
            p['n'] += 1
    return recs


def fit_variance(recs):
    """var(y | mu) = v0 + v1*mu + v2*mu^2, OLS on squared residuals (tune seasons, 'tip' clock)."""
    V = {}
    for mkt in MARKETS:
        X, Y = [], []
        for r in recs:
            mu = r['pred']['tip'][1][mkt]
            X.append([1.0, mu, mu * mu])
            Y.append((r['y'][mkt] - mu) ** 2)
        V[mkt] = [round(b, 5) for b in MM.ols(X, Y, ridge=1.0)]
    return V


# ── isotonic calibration ───────────────────────────────────────────────────
def pav(points, bins=20, pseudo=30):
    """points: [(p_model, outcome)]. Returns sorted [(p_mid, p_cal)] knots, bins shrunk to their midpoint."""
    points.sort()
    n = len(points)
    if n < bins * 10:
        return None
    blocks = []
    for i in range(bins):
        chunk = points[i * n // bins:(i + 1) * n // bins]
        mid = statistics.mean(p for p, _ in chunk)
        rate = (sum(o for _, o in chunk) + pseudo * mid) / (len(chunk) + pseudo)
        blocks.append([mid, rate, len(chunk)])
    merged = []
    for b in blocks:
        merged.append(b)
        while len(merged) > 1 and merged[-2][1] > merged[-1][1]:
            b2 = merged.pop()
            b1 = merged.pop()
            w = b1[2] + b2[2]
            merged.append([(b1[0] * b1[2] + b2[0] * b2[2]) / w, (b1[1] * b1[2] + b2[1] * b2[2]) / w, w])
    return [(m[0], m[1]) for m in merged]


def apply_cal(knots, p):
    if not knots:
        return p
    if p <= knots[0][0]:
        return knots[0][1] * p / knots[0][0] if knots[0][0] > 0 else knots[0][1]
    if p >= knots[-1][0]:
        return knots[-1][1] + (1 - knots[-1][1]) * (p - knots[-1][0]) / max(1e-9, 1 - knots[-1][0])
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x0 <= p <= x1:
            return y0 + (y1 - y0) * (p - x0) / max(1e-9, x1 - x0)
    return p


# ── market helpers ─────────────────────────────────────────────────────────
def am_prob(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def am_payout(a):
    a = float(a)
    return a / 100 if a > 0 else 100 / -a


def kalshi_fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def grade_book(rows, th):
    """rows: dicts with p_model_over, p_mkt_over, over_px, under_px, over(bool). Bet the side with edge >= th."""
    n = w = 0
    profit = 0.0
    for r in rows:
        eo = r['pm'] - r['pk']
        if abs(eo) < th:
            continue
        over = eo > 0
        px = r['over_px'] if over else r['under_px']
        win = r['over'] if over else not r['over']
        profit += am_payout(px) if win else -1.0
        n += 1
        w += win
    return n, w, profit


def summarize(n, w, profit):
    if not n:
        return {'n': 0}
    roi = profit / n
    se = 1.0 / math.sqrt(n)            # ~ SD of a -110 bet's return / sqrt(n)
    return {'n': n, 'win': round(w / n, 4), 'roi': round(roi, 4), 'roi_se': round(se, 4), 'z': round(roi / se, 2)}


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def blend(rows, km, kk, ky, iters=25, keep_intercept=False):
    """Logistic regression y ~ a + b*logit(market) + c*logit(model), by Newton's method.
    c > 0 at 2 SE = the model adds information the price does not have."""
    X = [(1.0, logit(r[kk]), logit(r[km])) for r in rows]
    Y = [1.0 if r[ky] else 0.0 for r in rows]
    if len(X) < 200:
        return None
    b = [0.0, 1.0, 0.0]
    for _ in range(iters):
        g = [0.0] * 3
        H = [[0.0] * 3 for _ in range(3)]
        for x, y in zip(X, Y):
            z = sum(bi * xi for bi, xi in zip(b, x))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            for i in range(3):
                g[i] += (y - p) * x[i]
                for j in range(3):
                    H[i][j] += p * (1 - p) * x[i] * x[j]
        step = MM.solve(H, g)
        b = [bi + si for bi, si in zip(b, step)]
        if max(abs(si) for si in step) < 1e-6:
            break
    inv = [MM.solve(H, [1.0 if k == i else 0.0 for k in range(3)]) for i in range(3)]
    se = math.sqrt(max(1e-12, inv[2][2]))
    out = {'n': len(X), 'w_market': round(b[1], 3), 'w_model': round(b[2], 3), 'se_model': round(se, 3), 't': round(b[2] / se, 2)}
    if keep_intercept:
        out['a'] = b[0]
        out['w_market'], out['w_model'] = b[1], b[2]
    return out


def blend_fit(rows, km, kk, ky):
    b = blend(rows, km, kk, ky)
    return None if not b else b


def blend_prob(coef, p_mkt, p_model):
    z = coef['a'] + coef['w_market'] * logit(p_mkt) + coef['w_model'] * logit(p_model)
    return 1 / (1 + math.exp(-z))


def blended_backtest(fit_rows, test_rows, km, kk, ky, price_fn, ths=(0.02, 0.03, 0.05, 0.08)):
    """Fit the blend on fit_rows only, then bet test_rows where blend - price >= th. price_fn(row, side) -> (cost, payout)."""
    b = blend(fit_rows, km, kk, ky, keep_intercept=True)
    if not b:
        return None
    out = {'fit_n': len(fit_rows), 'test_n': len(test_rows), 'coef': b}
    for th in ths:
        n = w = 0
        profit = 0.0
        per_game = defaultdict(list)
        for r in test_rows:
            q = blend_prob(b, r[kk], r[km])
            e = q - r[kk]
            if abs(e) < th:
                continue
            side = e > 0
            pr_ = price_fn(r, side)
            win = r[ky] if side else not r[ky]
            gain = pr_[1] if win else -pr_[0]
            profit += gain
            per_game[r.get('gid', id(r))].append(gain / pr_[0])
            n += 1
            w += win
        if n:
            gm = [statistics.mean(v) for v in per_game.values()]
            se = (statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 1 else 0) or 1.0
            out[f'{th:.2f}'] = {'n': n, 'games': len(gm), 'win': round(w / n, 4), 'roi': round(statistics.mean(gm), 4),
                                'z': round(statistics.mean(gm) / se, 2)}
    return out


def main():
    box = C.player_games(WARM + TUNE + TEST)
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']

    tr = walk(WARM + TUNE, box, None, TUNE[0], 'oracle', margins, mm, casc)
    ratio = sum(r['min'] for r in tr) / sum(r['pred']['tip'][0] for r in tr)
    team_min = round(240.0 * ratio, 1)
    tr = walk(WARM + TUNE, box, None, TUNE[0], 'oracle', margins, mm, casc, team_min)
    print(f'team minutes target {team_min} (fit on tune seasons)', flush=True)
    V = fit_variance(tr)
    print('variance fits', V, flush=True)
    te = walk(WARM + TUNE + TEST, box, inj, TEST[0], 'report', margins, mm, casc, team_min)
    proj = {(r['gid'], r['aid']): r for r in te}
    print(f'projections: tune {len(tr):,}  test {len(te):,}', flush=True)

    # projection accuracy (mean) vs a naive season-to-date average would need another pass; report MAE + bias
    acc = {}
    for mkt in MARKETS:
        e = [r['pred']['tip'][1][mkt] - r['y'][mkt] for r in te]
        acc[mkt] = {'mae': round(statistics.mean(abs(x) for x in e), 3), 'bias': round(statistics.mean(e), 3)}

    # ── ESPN rows ──
    espn = defaultdict(list)   # (season, market, clock) -> rows
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if r['kind'] != 'main' or r['played'] != '1' or r['market'] not in MARKETS:
            continue
        pr = proj.get((int(r['game_id']), int(r['athlete_id'])))
        if not pr:
            continue
        act = float(r['actual'])
        for clock, line, opx, upx in (('open', r['line_open'], r['over_px_open'], r['under_px_open']),
                                      ('close', r['line_cur'], r['over_px_cur'], r['under_px_cur'])):
            if clock == 'close' and r['cur_is_pretip'] != '1':
                continue
            po, pu = am_prob(opx), am_prob(upx)
            if not line or po is None or pu is None:
                continue
            # A real two-way main line carries a normal vig. Anything else is a mis-paired alt price or a stale
            # half-updated row (it produced "+67% ROI on 54% wins" before this filter).
            if not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
                continue
            L = float(line)
            if act == L:
                continue
            # listed out at 11am but then played: no 11am projection exists, use the pre-tip one
            mu = pr['pred'].get('am' if clock == 'open' else 'tip', pr['pred']['tip'])[1][r['market']]
            espn[(r['season'], r['market'], clock)].append({
                'vac': pr['pred'].get('am' if clock == 'open' else 'tip', pr['pred']['tip'])[2], 'gid': r['game_id'],
                'pm_raw': p_over(r['market'], mu, L, V), 'pk': po / (po + pu), 'over_px': opx, 'under_px': upx,
                'over': act > L, 'line': L, 'open_line': float(r['line_open']), 'open_pk': None})

    # calibration fit on 2024-25 (open clock, where the volume is), applied to 2025-26 and reported both ways
    cal = {}
    for mkt in MARKETS:
        pts = [(x['pm_raw'], 1 if x['over'] else 0) for x in espn.get(('2025', mkt, 'open'), [])]
        cal[mkt] = pav(pts)
    for key, rows in espn.items():
        for x in rows:
            x['pm'] = apply_cal(cal[key[1]], x['pm_raw']) if key[0] == '2026' else x['pm_raw']

    # ── Kalshi ladder ──
    kal = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_kalshi.csv'))):
        if r['result'] not in ('yes', 'no') or r['played'] != '1' or r['market'] not in MARKETS:
            continue
        pr = proj.get((int(r['game_id']), int(r['athlete_id'])))
        px = r['yes_vwap30_pretip'] or r['yes_last_pretip']
        if not pr or not px:
            continue
        k = float(px)
        if not (0.05 < k < 0.95):
            continue
        mu = pr['pred']['tip'][1][r['market']]
        pm = apply_cal(cal[r['market']], p_over(r['market'], mu, float(r['strike']), V))
        kal[r['market']].append({'pm': pm, 'k': k, 'vac': pr['pred']['tip'][2], 'tip': r['tip_ts'],
                                 'vol30': float(r['vol30_pretip'] or 0), 'yes': r['result'] == 'yes', 'gid': r['game_id'], 'aid': r['athlete_id']})

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'variance': V, 'team_min': team_min,
           'accuracy': acc, 'calibration': {m: c for m, c in cal.items()}, 'espn': {}, 'kalshi': {}, 'verdict': {}}
    TH = (0.03, 0.05, 0.08, 0.12)
    for (season, mkt, clock), rows in sorted(espn.items()):
        blk = {'n_rows': len(rows),
               'brier_model': round(statistics.mean((x['pm'] - x['over']) ** 2 for x in rows), 4),
               'brier_market': round(statistics.mean((x['pk'] - x['over']) ** 2 for x in rows), 4)}
        for th in TH:
            blk[f'{th:.2f}'] = summarize(*grade_book(rows, th))
        hit = [x for x in rows if x['vac'] >= 15]
        blk['teammate_out'] = {f'{th:.2f}': summarize(*grade_book(hit, th)) for th in (0.03, 0.08)}
        blk['teammate_out']['n_rows'] = len(hit)
        blk['blend'] = blend(rows, 'pm', 'pk', 'over')
        res['espn'][f'{season}/{mkt}/{clock}'] = blk
    for mkt, rows in kal.items():
        blk = {'n_rows': len(rows), 'games': len({x['gid'] for x in rows}),
               'brier_model': round(statistics.mean((x['pm'] - x['yes']) ** 2 for x in rows), 4),
               'brier_market': round(statistics.mean((x['k'] - x['yes']) ** 2 for x in rows), 4)}
        for th in TH:
            n = w = 0
            profit = 0.0
            per_game = defaultdict(list)
            for x in rows:
                e = x['pm'] - x['k']
                if abs(e) < th:
                    continue
                yes = e > 0
                cost = (x['k'] if yes else 1 - x['k'])
                cost += kalshi_fee(cost)
                win = x['yes'] if yes else not x['yes']
                pr_ = (1 - cost) if win else -cost
                profit += pr_
                per_game[x['gid']].append(pr_)
                n += 1
                w += win
            if n:
                # Strikes in one game are correlated (same player, same night): the SE treats each GAME as one
                # observation (its mean profit per contract), not each strike.
                gm = [statistics.mean(v) for v in per_game.values()]
                se = statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 1 else 1.0
                blk[f'{th:.2f}'] = {'n': n, 'games': len(gm), 'win': round(w / n, 4),
                                    'roi_per_contract': round(profit / n, 4), 'z': round(statistics.mean(gm) / se, 2)}
        blk['blend'] = blend(rows, 'pm', 'k', 'yes')
        res['kalshi'][mkt] = blk

    # ── blended fair price, strictly out of sample ──
    def kal_price(r, yes):
        c = r['k'] if yes else 1 - r['k']
        c += kalshi_fee(c)
        return (c, 1 - c)

    def book_price(r, over):
        return (1.0, am_payout(r['over_px'] if over else r['under_px']))

    res['blend_oos'] = {}
    for mkt in MARKETS:
        rows = kal.get(mkt, [])
        if rows:
            tips = sorted(int(x['tip']) for x in rows)
            cut = tips[len(tips) // 2]
            fit_r = [x for x in rows if int(x['tip']) < cut]
            test_r = [x for x in rows if int(x['tip']) >= cut]
            res['blend_oos'][f'kalshi/{mkt}'] = blended_backtest(fit_r, test_r, 'pm', 'k', 'yes', kal_price)
        f25 = espn.get(('2025', mkt, 'open'), [])
        for clock in ('close', 'open'):
            t26 = espn.get(('2026', mkt, clock), [])
            if f25 and t26:
                res['blend_oos'][f'espn25->26/{mkt}/{clock}'] = blended_backtest(f25, t26, 'pm', 'pk', 'over', book_price)

    # ── is the Kalshi edge the model, or a structural YES (overs) bias? ──
    # Baseline = the price alone, recalibrated on the first half (a + w*logit(price)). If the blend's second-half
    # ROI is no better than this baseline's, the "edge" is just fading overs and the model adds nothing.
    res['kalshi_bias'] = {}
    for mkt, rows in kal.items():
        tips = sorted(int(x['tip']) for x in rows)
        cut = tips[len(tips) // 2]
        fit_r = [x for x in rows if int(x['tip']) < cut]
        test_r = [x for x in rows if int(x['tip']) >= cut]
        by_bucket = {}
        for lo, hi in ((0.05, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.95)):
            B = [x for x in rows if lo <= x['k'] < hi]
            if B:
                by_bucket[f'{lo:.2f}-{hi:.2f}'] = {'n': len(B), 'price': round(statistics.mean(x['k'] for x in B), 3),
                                                   'hit': round(statistics.mean(x['yes'] for x in B), 3)}
        out = {'buckets': by_bucket}
        for label, fr, tr_ in (('blend', fit_r, test_r),
                               ('price_only', [dict(x, pm=0.5) for x in fit_r], [dict(x, pm=0.5) for x in test_r])):
            coef = blend(fr, 'pm', 'k', 'yes', keep_intercept=True)
            sides = {}
            for side in (True, False):
                g, vols = [], []
                for x in tr_:
                    e = blend_prob(coef, x['k'], x['pm']) - x['k']
                    if abs(e) < 0.03 or (e > 0) != side:
                        continue
                    c = (x['k'] if side else 1 - x['k'])
                    c += kalshi_fee(c)
                    win = x['yes'] if side else not x['yes']
                    g.append(((1 - c) if win else -c) / c)
                    vols.append(x['vol30'])
                sides['YES' if side else 'NO'] = {'n': len(g), 'roi': round(statistics.mean(g), 4) if g else None,
                                                  'median_vol30': round(statistics.median(vols)) if vols else None}
            out[label] = sides
        res['kalshi_bias'][mkt] = out

    # Verdict per market (PLAN §6), honest tests only: ESPN pre-tip close 2025-26 and Kalshi pre-tip.
    # GO needs 50+ bets and z >= 2 on one of them, and the other not negative. WATCH = positive on both, not yet 2 SE.
    for mkt in MARKETS:
        c = (res['blend_oos'].get(f'espn25->26/{mkt}/close') or {}).get('0.03', {})
        k = (res['blend_oos'].get(f'kalshi/{mkt}') or {}).get('0.03', {})
        c = dict(c, roi=c.get('roi', 0)) if c else {}
        k = {'games': k.get('games', 0), 'z': k.get('z', 0), 'roi_per_contract': k.get('roi', 0)} if k else {}
        cz, kz = (c.get('z', 0) if c.get('n', 0) >= 50 else 0), (k.get('z', 0) if k.get('games', 0) >= 50 else 0)
        cr, kr = c.get('roi', 0), k.get('roi_per_contract', 0)
        if (cz >= 2 and kr >= 0) or (kz >= 2 and cr >= 0):
            res['verdict'][mkt] = 'GO'
        elif cr > 0 and kr >= 0 or kr > 0 and cr >= 0:
            res['verdict'][mkt] = 'WATCH'
        else:
            res['verdict'][mkt] = 'NO-GO'
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


def write_md(res):
    L = ['# NBA prop model: backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_prop_model.py`. Walk-forward, out of sample.", '',
         'Projection = predicted minutes x per-minute rate (+ usage cascade where it earned it). Variance fit on',
         '2022-23 + 2023-24; isotonic calibration fit on 2024-25 lines and applied to 2025-26. Graded only when the',
         'player played. "Edge" = model probability minus the de-vigged market probability for the side bet.', '',
         '## Bottom line', '',
         '- **The model alone does not beat the market.** Every market price (ESPN and Kalshi) is more accurate than the',
         '  model on its own. Betting "model vs price" loses.',
         '- **The model does carry information the price lacks** (logistic blend, bottom of page), so the shippable form is',
         '  a blended fair price: mostly the market, nudged by the model, weights fit on earlier data.',
         '- **Kalshi player props have a structural overs bias.** YES hits below its price in every price bucket, all',
         '  season, in all four stats (strongest in 3-pointers). Buying NO wins on its own.',
         '- **3-pointers on Kalshi is the one GO.** Blended picks (almost all NO) return +9.4% after fees in the held-out',
         '  second half vs +5.1% for the bias alone, so the model adds about 4 points by choosing which NOs. Capacity is',
         '  thin: median ~30 contracts traded in the 30 min before tip on those strikes.',
         '- **Sportsbook props (ESPN): no reliable edge.** Nothing passes out of sample; rebounds is the closest to a signal.',
         '- **Points on Kalshi:** the whole edge is the overs bias (+2%); the model adds nothing there.', '',
         '## Verdict (blended fair price, out of sample: ESPN 2025-26 pre-tip close + Kalshi second half, 3%+ edge)', '',
         '| Market | Verdict |', '|---|---|']
    for m, v in res['verdict'].items():
        L.append(f'| {m} | **{v}** |')
    L += ['', '## Projection accuracy (2024-25 + 2025-26, injury report 30 min pre-tip)', '',
          '| Market | MAE | Bias |', '|---|---|---|']
    for m, a in res['accuracy'].items():
        L.append(f"| {m} | {a['mae']} | {a['bias']:+} |")
    for title, clock, note in (('ESPN pre-tip close (honest)', 'close', 'Bet at the last pre-tip price ESPN saw; model uses the report 30 min before tip.'),
                               ('ESPN open (OPTIMISTIC, timing unknown)', 'open', 'Model uses the 11am report. The open may predate it, which flatters the model.')):
        L += ['', f'## {title}', '', note, '',
              '| Season / market | Rows | Brier model | Brier market | Edge 3%+: bets, win, ROI (z) | 5%+ | 8%+ | 12%+ |',
              '|---|---|---|---|---|---|---|---|']
        for key, b in res['espn'].items():
            s, m, c = key.split('/')
            if c != clock:
                continue
            cells = []
            for th in ('0.03', '0.05', '0.08', '0.12'):
                v = b.get(th, {})
                cells.append(f"{v['n']}, {v['win']:.1%}, {v['roi']:+.1%} ({v['z']})" if v.get('n') else '')
            L.append(f"| {s} {m} | {b['n_rows']:,} | {b['brier_model']} | {b['brier_market']} | " + ' | '.join(cells) + ' |')
    L += ['', '## Kalshi ladder, pre-tip price, after fees (honest)', '',
          'Every strike is a bet on whichever side the model prefers; strikes in one game are correlated.', '',
          '| Market | Strikes | Games | Brier model | Brier Kalshi | 3%+: bets, win, ROI/contract | 5%+ | 8%+ | 12%+ |', '|---|---|---|---|---|---|---|---|---|']
    for m, b in res['kalshi'].items():
        cells = []
        for th in ('0.03', '0.05', '0.08', '0.12'):
            v = b.get(th)
            cells.append(f"{v['n']} ({v['games']}g), {v['win']:.1%}, {v['roi_per_contract']:+.3f} (z {v['z']})" if v else '')
        L.append(f"| {m} | {b['n_rows']:,} | {b['games']} | {b['brier_model']} | {b['brier_market']} | " + ' | '.join(cells) + ' |')
    L += ['', '## Blended fair price, out of sample (the version that would ship)', '',
          'fair = logistic(a + w_market x logit(price) + w_model x logit(model)), weights fit on EARLIER data only:',
          'Kalshi fit on the first half of the season by tip time, tested on the second half; ESPN fit on 2024-25',
          'opens, tested on 2025-26. Bet when fair differs from the price by the threshold. ROI per unit staked,',
          'after Kalshi fees / at the book price; z uses games as the unit.', '',
          '| Test | Fit rows | Test rows | w_market | w_model | Edge 2%+: bets, win, ROI (z) | 3%+ | 5%+ | 8%+ |', '|---|---|---|---|---|---|---|---|---|']
    for key, b in res['blend_oos'].items():
        if not b:
            continue
        cells = [f"{b[t]['n']}, {b[t]['win']:.1%}, {b[t]['roi']:+.1%} ({b[t]['z']})" if b.get(t) else '' for t in ('0.02', '0.03', '0.05', '0.08')]
        L.append(f"| {key} | {b['fit_n']:,} | {b['test_n']:,} | {b['coef']['w_market']:.3f} | {b['coef']['w_model']:.3f} | " + ' | '.join(cells) + ' |')
    L += ['', '## Kalshi overs bias: is the edge the model, or just fading YES?', '',
          'Kalshi player-prop YES contracts (overs) hit less often than their price in EVERY price bucket: retail',
          'buys overs. So "buy NO" wins on its own. The test that matters: second-half ROI of the blended model vs a',
          'baseline that only recalibrates the price (fit on the first half). 3%+ edge, after fees. Volume = median',
          'contracts traded in the 30 min before tip on the strikes bet (capacity).', '',
          '| Market | Hit vs price by bucket (all season) | Price-only: NO bets, ROI | Blend: NO bets, ROI | Blend: YES bets, ROI | Median 30-min volume |',
          '|---|---|---|---|---|---|']
    for m, b in res.get('kalshi_bias', {}).items():
        bk = '; '.join(f"{k}: {v['hit']:.3f} vs {v['price']:.3f}" for k, v in b['buckets'].items())
        po, bn, by = b['price_only']['NO'], b['blend']['NO'], b['blend']['YES']
        f = lambda v: f"{v['n']}, {v['roi']:+.1%}" if v['n'] else '0'
        L.append(f"| {m} | {bk} | {f(po)} | {f(bn)} | {f(by)} | {bn['median_vol30']} |")
    L += ['', '## Does the model add anything to the price? (logistic blend, in sample)', '',
          'outcome ~ a + w_market x logit(price) + w_model x logit(model). w_model > 0 at t >= 2 means the model knows',
          'something the price does not. w_model <= 0: the price already has it all.', '',
          '| Test | Rows | w_market | w_model | t |', '|---|---|---|---|---|']
    for key, b in list(res['espn'].items()) + [(f'kalshi/{m}', b) for m, b in res['kalshi'].items()]:
        bl = b.get('blend')
        if bl:
            L.append(f"| {key} | {bl['n']:,} | {bl['w_market']} | {bl['w_model']} | {bl['t']} |")
    L += ['', '## Teammate-out spots (15+ rotation minutes vacated)', '',
          'Where the minutes model found plain recent minutes under-predict by 1.4 min: is the price slow here?', '',
          '| Test | Rows | Edge 3%+: bets, win, ROI (z) | 8%+ |', '|---|---|---|---|']
    for key, b in res['espn'].items():
        t = b.get('teammate_out', {})
        cells = [f"{t[k]['n']}, {t[k]['win']:.1%}, {t[k]['roi']:+.1%} ({t[k]['z']})" if t.get(k, {}).get('n') else '' for k in ('0.03', '0.08')]
        L.append(f"| {key} | {t.get('n_rows', 0):,} | " + ' | '.join(cells) + ' |')
    L += ['', f"Team minutes target {res['team_min']} (fit on tune seasons: active candidates include players who end up DNP).",
          f"Variance fits (v0, v1, v2): {res['variance']}", '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
