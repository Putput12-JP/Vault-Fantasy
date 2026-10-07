#!/usr/bin/env python3
"""
Prop model v3, workstream A of docs/v3-plan.md: full outcome distributions (ladders), all eight markets.

v2's projected MEAN is kept exactly (stacker fit on 2024-25). What changes is the shape around it, which is what a
Kalshi ladder prices. v2 used one variance formula per stat, calibrated on sportsbook main lines near 50%, and came
out too wide in the tails (docs/v3-plan.md §1). v3 builds each player-game's distribution from its parts:

  minutes      the player's own minutes miss (EWMA RMS miss, `sdm`) times an empirical standardized-miss
               distribution fit on 2024-25, by role (projected minutes band) x blowout risk (|market spread|).
               Left-skewed and fat-tailed as real minutes are: early exits, foul trouble, blowout benchings.
               Q equal-weight minutes scenarios; the stat mean scales with minutes, averaging back to v2's mean.
  production   given the minutes, per stat and position group (G / F / C):
                 REB, AST    negative binomial, dispersion fit by maximum likelihood
                 3PM         attempts ~ negative binomial (volume) x makes ~ beta-binomial at his regressed 3P%
                 PTS, combos normal, variance = c1*mean + c2*mean^2
               All production parameters are fit against TRUE minutes, so minutes noise is counted once.
  calibration  isotonic on P(over), fit on 2024-25 at thresholds across each player's whole range (not only
               near-50% book lines), so the tails are calibrated too.

Test on 2025-26, identical rows, v2 vs v3: log score of the actual outcome (every player-game), calibration by
decile across the range, Kalshi ladder log loss and blended betting vs the price-only baseline, ESPN close lines.

  python3 nba/scripts/build_prop_model_v3.py
Writes data/prop_model_v3.json and docs/prop-model-v3.md.
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as V1
import build_prop_model_v2 as V2
from build_prop_model import BASE, COMBO, MARKETS, phi, nb_sf, pav, apply_cal, am_prob, am_payout, kalshi_fee, blend, blend_prob

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'prop_model_v3.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'prop-model-v3.md')
Q = 12                                           # minutes scenarios per player-game
LEVELS = [(i + 0.5) / Q for i in range(Q)]
NORMAL = ['pts', 'pra', 'pr', 'pa', 'ra']
KAPPAS = [0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7]
CONC = [3, 5, 8, 12, 20, 30, 50, 80, 130, 200, 400, 1000]
FLOOR_SD = 2.0                                  # minutes miss scale floor


def role(pm):
    return 'big' if pm >= 28 else 'mid' if pm >= 18 else 'low'


def blow(spread):
    a = abs(spread) if spread is not None else 0.0
    return 0 if a < 7 else 1 if a < 12 else 2


def quantiles(vals, levels):
    v = sorted(vals)
    n = len(v)
    out = []
    for q in levels:
        x = q * (n - 1)
        i = int(x)
        out.append(v[i] + (v[min(i + 1, n - 1)] - v[i]) * (x - i))
    return out


def yval(r, m):
    return r['y'][m] if m in BASE else sum(r['y'][p] for p in COMBO[m])


# ── minutes scenarios ──────────────────────────────────────────────────────
def fit_minutes(recs):
    """Standardized minutes miss z = (actual - projected) / player's miss scale, quantiles by role x blowout risk."""
    cells, by_role = defaultdict(list), defaultdict(list)
    for r in recs:
        z = (r['min'] - r['pm']) / max(FLOOR_SD, r['sdm'])
        cells[f"{role(r['pm'])}|{blow(r['spread'])}"].append(z)
        by_role[role(r['pm'])].append(z)
    T = {}
    for rl in ('big', 'mid', 'low'):
        for b in (0, 1, 2):
            v = cells.get(f'{rl}|{b}', [])
            T[f'{rl}|{b}'] = [round(x, 4) for x in quantiles(v if len(v) >= 300 else by_role[rl], LEVELS)]
    return T


def factors(pm, sdm, spread, T):
    """Q minutes scenarios as multipliers on the mean (they average to 1, so v2's mean is kept)."""
    zq = T[f'{role(pm)}|{blow(spread)}']
    M = [min(48.0, max(1.0, pm + max(FLOOR_SD, sdm) * z)) for z in zq]
    em = sum(M) / len(M)
    return [m / em for m in M]


# ── distributions ──────────────────────────────────────────────────────────
def nb_logpmf(y, mu, k):
    if mu <= 0:
        return 0.0 if y == 0 else -30.0
    if k <= 1e-9:
        return -mu + y * math.log(mu) - math.lgamma(y + 1)
    r = 1.0 / k
    return (math.lgamma(y + r) - math.lgamma(r) - math.lgamma(y + 1) + r * math.log(r / (r + mu)) + y * math.log(mu / (r + mu)))


def nb_pmf_list(mu, k, kmax):
    out = [0.0] * (kmax + 1)
    if mu <= 0:
        out[0] = 1.0
        return out
    if k <= 1e-9:
        p = math.exp(-mu)
        for i in range(kmax + 1):
            out[i] = p
            p *= mu / (i + 1)
        return out
    r = 1.0 / k
    q = mu / (r + mu)
    p = (r / (r + mu)) ** r
    for i in range(kmax + 1):
        out[i] = p
        p *= (i + r) / (i + 1) * q
    return out


def bb_logpmf(k, n, a, b):
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + math.lgamma(k + a) + math.lgamma(n - k + b) - math.lgamma(n + a + b)
            - math.lgamma(a) - math.lgamma(b) + math.lgamma(a + b))


class Dist:
    """One player-game's distribution for one market under v3. cdf_over(line) = P(X > line)."""

    def __init__(self, P, r, m, mu, T):
        self.m, self.mu = m, mu
        self.f = factors(r['pm'], r['sdm'], r['spread'], T)
        g = r['pos']
        if m in ('reb', 'ast'):
            k = P['nb'][m][g]
            kmax = int(mu * 3 + 20)
            pm = [0.0] * (kmax + 1)
            for f in self.f:
                for i, v in enumerate(nb_pmf_list(mu * f, k, kmax)):
                    pm[i] += v / Q
            self.pmf = pm
        elif m == '3pm':
            p3 = r['p3'] if r['p3'] else 0.35
            p3 = min(0.6, max(0.15, p3))
            lam = mu / p3
            ka, c = P['att'][g], P['conc'][g]
            amax = int(lam * 3 + 15)
            att = [0.0] * (amax + 1)
            for f in self.f:
                for i, v in enumerate(nb_pmf_list(lam * f, ka, amax)):
                    att[i] += v / Q
            a, b = p3 * c, (1 - p3) * c
            pm = [0.0] * (amax + 1)
            for n, pa in enumerate(att):
                if pa < 1e-12:
                    continue
                for k in range(n + 1):
                    pm[k] += pa * math.exp(bb_logpmf(k, n, a, b))
            self.pmf = pm
        else:
            self.pmf = None
            c1, c2 = P['normal'][m][g]
            self.sd = [math.sqrt(max(0.25, c1 * mu * f + c2 * (mu * f) ** 2)) for f in self.f]

    def over(self, line):
        if self.pmf is not None:
            k = int(math.floor(line))
            return max(0.0, 1.0 - sum(self.pmf[:k + 1]))
        return sum(1 - phi((line - self.mu * f) / sd) for f, sd in zip(self.f, self.sd)) / Q

    def logp(self, y):
        if self.pmf is not None:
            return math.log(max(1e-9, self.pmf[y] if y < len(self.pmf) else 0.0))
        p = sum(phi((y + .5 - self.mu * f) / sd) - phi((y - .5 - self.mu * f) / sd) for f, sd in zip(self.f, self.sd)) / Q
        return math.log(max(1e-9, p))


# ── v2 distribution, for the comparison ────────────────────────────────────
def v2_var(V, m, mu, extra):
    v = V[m]
    return max(0.25, v[0] + v[1] * mu + v[2] * mu * mu + (v[3] * extra if len(v) > 3 else 0.0))


def v2_logp(V, m, mu, extra, y):
    var = v2_var(V, m, mu, extra)
    if m in V1.COUNT_MKTS:
        if var <= mu * 1.0001:
            return nb_logpmf(y, mu, 0.0)
        return nb_logpmf(y, mu, (var - mu) / (mu * mu))
    sd = math.sqrt(var)
    return math.log(max(1e-9, phi((y + .5 - mu) / sd) - phi((y - .5 - mu) / sd)))


# ── fitting production given TRUE minutes ─────────────────────────────────
def fit_production(recs, stk):
    P = {'nb': {}, 'att': {}, 'conc': {}, 'normal': {}}
    by = defaultdict(list)
    for r in recs:
        if r['pm'] > 0:
            by[r['pos']].append(r)
    for g, rows in by.items():
        mus = [V2.mu2(r, stk) for r in rows]
        scale = [r['min'] / r['pm'] for r in rows]            # the mean if we had known the minutes
        for m in ('reb', 'ast'):
            best = max(KAPPAS, key=lambda k: sum(nb_logpmf(int(r['y'][m]), mu[m] * s, k) for r, mu, s in zip(rows, mus, scale)))
            P['nb'].setdefault(m, {})[g] = best
        sh = [(r, mu, s) for r, mu, s in zip(rows, mus, scale) if r['p3']]
        att = lambda r, mu, s: mu['3pm'] / min(0.6, max(0.15, r['p3'])) * s
        P['att'][g] = max(KAPPAS, key=lambda k: sum(nb_logpmf(int(r['y3pa']), att(r, mu, s), k) for r, mu, s in sh))
        P['conc'][g] = max(CONC, key=lambda c: sum(bb_logpmf(int(r['y']['3pm']), int(r['y3pa']), min(.6, max(.15, r['p3'])) * c, (1 - min(.6, max(.15, r['p3']))) * c)
                                                   for r, mu, s in sh if r['y3pa'] >= r['y']['3pm']))
        for m in NORMAL:
            X, Y = [], []
            for r, mu, s in zip(rows, mus, scale):
                mt = mu[m] * s
                X.append([mt, mt * mt])
                Y.append((yval(r, m) - mt) ** 2)
            c = MM.ols(X, Y, ridge=0.0)
            P['normal'].setdefault(m, {})[g] = [round(max(0.05, c[0]), 5), round(max(0.0, c[1]), 6)]
    return P


def thresholds(m, mu):
    """Lines across a player's range, like a ladder: 0.4x to 1.8x the mean, on the .5 grid books and Kalshi use."""
    out = set()
    for k in (0.4, 0.6, 0.8, 1.0, 1.2, 1.45, 1.8):
        t = math.floor(mu * k) + 0.5
        if t > 0:
            out.add(t)
    return sorted(out)


def decile_table(rows):
    """rows: (p, outcome). -> list of (bucket, n, mean p, hit)."""
    b = defaultdict(list)
    for p, o in rows:
        b[min(9, int(p * 10))].append((p, o))
    return [(k / 10, len(v), round(statistics.mean(p for p, _ in v), 3), round(statistics.mean(o for _, o in v), 3)) for k, v in sorted(b.items()) if len(v) >= 100]


def by_rec(recs):
    return {(r['gid'], r['aid']): r for r in recs if r['pm'] > 0}


def load_markets(by):
    """ESPN main lines (2024-25 open, 2025-26 pre-tip close) and Kalshi strikes (pre-tip price), joined to player-games."""
    espn = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if row['kind'] != 'main' or row['played'] != '1' or row['market'] not in MARKETS:
            continue
        r = by.get((int(row['game_id']), int(row['athlete_id'])))
        if not r:
            continue
        act = float(row['actual'])
        for clock, line, opx, upx in (('open', row['line_open'], row['over_px_open'], row['under_px_open']),
                                      ('close', row['line_cur'], row['over_px_cur'], row['under_px_cur'])):
            if clock == 'close' and row['cur_is_pretip'] != '1':
                continue
            po, pu = am_prob(opx), am_prob(upx)
            if not line or po is None or pu is None or not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
                continue
            L = float(line)
            if act == L:
                continue
            espn[(row['season'], row['market'], clock)].append({'r': r, 'L': L, 'pk': po / (po + pu), 'over': act > L,
                                                                'over_px': opx, 'under_px': upx, 'gid': row['game_id']})
    kal = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_kalshi.csv'))):
        if row['result'] not in ('yes', 'no') or row['played'] != '1' or row['market'] not in MARKETS:
            continue
        r = by.get((int(row['game_id']), int(row['athlete_id'])))
        px = row['yes_vwap30_pretip'] or row['yes_last_pretip']
        if not r or not px or not (0.05 < float(px) < 0.95):
            continue
        kal[row['market']].append({'r': r, 'L': float(row['strike']), 'k': float(px), 'yes': row['result'] == 'yes',
                                   'tip': int(row['tip_ts']), 'gid': row['game_id']})
    return espn, kal


def eval_markets(res, NAMES, probs, espn, kal):
    """Kalshi ladders and ESPN close lines for every model in NAMES: log loss, blend t, blended betting out of sample
    vs the price-only baseline. probs[name](player-game, market, line, cache) -> P(over)."""
    def kprice(r_, yes):
        c = r_['k'] if yes else 1 - r_['k']
        c += kalshi_fee(c)
        return (c, 1 - c)

    ll = lambda rows, k, y: statistics.mean(-math.log(max(1e-6, x[k] if x[y] else 1 - x[k])) for x in rows)
    for m in MARKETS:
        cache = {}
        rows = kal.get(m, [])
        if rows:
            res['kalshi'][m] = {'n': len(rows), 'logloss_market': round(ll(rows, 'k', 'yes'), 4)}
            tips = sorted(x['tip'] for x in rows)
            cut = tips[len(tips) // 2]
            for name in NAMES:
                rr = [dict(x, pm=probs[name](x['r'], m, x['L'], cache)) for x in rows]
                res['kalshi'][m][name] = {'logloss': round(ll(rr, 'pm', 'yes'), 4), 'blend_t': (blend(rr, 'pm', 'k', 'yes') or {}).get('t'),
                                          'deciles': decile_table([(x['pm'], x['yes']) for x in rr])}
                fr, tr = [x for x in rr if x['tip'] < cut], [x for x in rr if x['tip'] >= cut]
                res['blend_oos'].setdefault(f'kalshi/{m}', {})[name] = V1.blended_backtest(fr, tr, 'pm', 'k', 'yes', kprice)
                # diagnostic, not part of the ship rule: log loss of the BLENDED price on the second half (fit on the first)
                cf = blend(fr, 'pm', 'k', 'yes', keep_intercept=True)
                bl = [{'q': blend_prob(cf, x['k'], x['pm']), 'yes': x['yes']} for x in tr]
                res['kalshi'][m][name]['blend_oos_logloss'] = round(ll(bl, 'q', 'yes'), 5)
                res['kalshi'][m].setdefault('market_2nd_half_logloss', round(ll(tr, 'k', 'yes'), 5))
                out = {}
                for label, f_, t_ in (('blend', fr, tr), ('price_only', [dict(x, pm=0.5) for x in fr], [dict(x, pm=0.5) for x in tr])):
                    coef = blend(f_, 'pm', 'k', 'yes', keep_intercept=True)
                    for side in (True, False):
                        gm = defaultdict(list)
                        for x in t_:
                            e = blend_prob(coef, x['k'], x['pm']) - x['k']
                            if abs(e) < 0.03 or (e > 0) != side:
                                continue
                            c = (x['k'] if side else 1 - x['k'])
                            c += kalshi_fee(c)
                            win = x['yes'] if side else not x['yes']
                            gm[x['gid']].append(((1 - c) if win else -c) / c)
                        allr = [v for vs in gm.values() for v in vs]
                        means = [statistics.mean(v) for v in gm.values()]
                        z = (statistics.mean(means) / (statistics.stdev(means) / math.sqrt(len(means)))) if len(means) > 2 and statistics.stdev(means) > 0 else 0
                        out[f"{label}/{'YES' if side else 'NO'}"] = {'n': len(allr), 'games': len(gm), 'roi': round(statistics.mean(allr), 4) if allr else None, 'z': round(z, 2)}
                res['kalshi_bias'].setdefault(m, {})[name] = out
            print(f"  kalshi {m:4s} logloss market {res['kalshi'][m]['logloss_market']:.4f}  " +
                  '  '.join(f"{nm} {res['kalshi'][m][nm]['logloss']:.4f} (t {res['kalshi'][m][nm]['blend_t']})" for nm in NAMES), flush=True)
        t26 = espn.get(('2026', m, 'close'), [])
        f25 = espn.get(('2025', m, 'open'), [])
        if t26:
            res['espn'][m] = {'n': len(t26), 'logloss_market': round(ll(t26, 'pk', 'over'), 4)}
            for name in NAMES:
                tt = [dict(x, pm=probs[name](x['r'], m, x['L'], cache)) for x in t26]
                ff = [dict(x, pm=probs[name](x['r'], m, x['L'], cache)) for x in f25]
                res['espn'][m][name] = {'logloss': round(ll(tt, 'pm', 'over'), 4), 'blend_t': (blend(tt, 'pm', 'pk', 'over') or {}).get('t')}
                if ff:
                    res['blend_oos'].setdefault(f'espn25->26/{m}', {})[name] = V1.blended_backtest(
                        ff, tt, 'pm', 'pk', 'over', lambda r_, o: (1.0, am_payout(r_['over_px'] if o else r_['under_px'])))


def main():
    box = C.player_games(V2.SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    team_min = V2.team_min()
    recs, _ = V2.walk(box, inj, margins, mm, casc, team_min, C.closing_lines())
    fit = [r for r in recs if r['season'] == V2.FIT and r['pm'] > 0]
    test = [r for r in recs if r['season'] == V2.TEST and r['pm'] > 0]
    print(f'player-games: fit {len(fit):,}  test {len(test):,}', flush=True)

    stk = V2.fit_stacker(fit)                            # v2's mean, as shipped
    V = V2.fit_var(fit, lambda r: V2.mu2(r, stk), True)  # v2's spread, as shipped
    T = fit_minutes(fit)
    P = fit_production(fit, stk)
    print('minutes quantiles', {k: (v[0], v[len(v) // 2], v[-1]) for k, v in T.items()}, flush=True)
    print('production', json.dumps(P), flush=True)

    def dist(r, m, cache):
        key = (id(r), m)
        if key not in cache:
            cache[key] = Dist(P, r, m, V2.mu2(r, stk)[m], T)
        return cache[key]

    extra = lambda r, m: (V2.minrate(r, m) * r['sdm']) ** 2

    # calibration on 2024-25 across each player's range; v2 keeps its own (ESPN 2024-25 open lines) as shipped
    c3 = {}
    cal_pts = defaultdict(list)
    cache = {}
    for r in fit:
        for m in MARKETS:
            mu = V2.mu2(r, stk)[m]
            d = dist(r, m, cache)
            for t in thresholds(m, mu):
                cal_pts[m].append((d.over(t), 1 if yval(r, m) > t else 0))
    for m in MARKETS:
        c3[m] = pav(cal_pts[m], bins=30, pseudo=30)
    cache.clear()
    v2cal = json.load(open(V2.OUT_JSON))['calibration']['v2']

    def p2(r, m, line):
        return apply_cal(v2cal[m], V2.p_over(m, V2.mu2(r, stk)[m], line, V, extra(r, m)))

    raw3 = lambda r, m, line, cache: dist(r, m, cache).over(line)

    espn, kal = load_markets(by_rec(recs))

    # v3 variants differ only in the calibration step:
    #   v3          isotonic across each player's whole range, 2024-25 player-games (tails included)
    #   v3_linecal  isotonic on 2024-25 sportsbook main lines, the way v2 was calibrated (carries where books set lines)
    #   v3_raw      the distribution as built, no calibration
    cache = {}
    cals = {'v3': c3, 'v3_raw': {m: None for m in MARKETS},
            'v3_linecal': {m: pav([(raw3(x['r'], m, x['L'], cache), 1 if x['over'] else 0) for x in espn.get(('2025', m, 'open'), [])]) for m in MARKETS}}
    NAMES = ['v2', 'v3', 'v3_linecal', 'v3_raw']
    probs = {'v2': lambda r, m, L, cache: p2(r, m, L)}
    for nm in ('v3', 'v3_linecal', 'v3_raw'):
        probs[nm] = (lambda cal: lambda r, m, L, cache: apply_cal(cal[m], raw3(r, m, L, cache)))(cals[nm])

    # ── test 1: every player-game, log score and calibration across the range ──
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'Q': Q, 'levels': LEVELS, 'names': NAMES,
           'minutes': T, 'production': P, 'calibration': cals, 'logscore': {}, 'range_cal': {}, 'kalshi': {}, 'espn': {},
           'blend_oos': {}, 'kalshi_bias': {}}
    cache = {}
    for m in MARKETS:
        l2, l3, rc = [], [], defaultdict(list)
        for r in test:
            mu = V2.mu2(r, stk)[m]
            y = int(round(yval(r, m)))
            l2.append(-v2_logp(V, m, mu, extra(r, m), y))
            l3.append(-dist(r, m, cache).logp(y))
            for t in thresholds(m, mu):
                o = 1 if y > t else 0
                for nm in NAMES:
                    rc[nm].append((probs[nm](r, m, t, cache), o))
        res['logscore'][m] = {'v2': round(statistics.mean(l2), 4), 'v3': round(statistics.mean(l3), 4), 'n': len(l2)}
        res['range_cal'][m] = {nm: {'deciles': decile_table(v), 'brier': round(statistics.mean((p - o) ** 2 for p, o in v), 5)} for nm, v in rc.items()}
        print(f"  {m:4s} log score v2 {res['logscore'][m]['v2']:.4f}  v3 {res['logscore'][m]['v3']:.4f}   range Brier " +
              '  '.join(f"{nm} {res['range_cal'][m][nm]['brier']:.4f}" for nm in NAMES), flush=True)
        cache = {k: v for k, v in cache.items() if k[1] != m}

    eval_markets(res, NAMES, probs, espn, kal)

    res['verdict'] = V2.verdicts(res, NAMES)
    ship = choose(res)
    res['ship'] = ship
    print('ship:', ship, flush=True)
    # live blend weights for the shipped variant (all priced history)
    res['blend_live'] = {'kalshi': {}, 'book': {}}
    cache = {}
    for m in MARKETS:
        k = [dict(x, pm=probs[ship](x['r'], m, x['L'], cache)) for x in kal.get(m, [])]
        if k:
            res['blend_live']['kalshi'][m] = blend(k, 'pm', 'k', 'yes', keep_intercept=True)
        b = [dict(x, pm=probs[ship](x['r'], m, x['L'], cache)) for x in espn.get(('2025', m, 'open'), []) + espn.get(('2026', m, 'close'), [])]
        if b:
            res['blend_live']['book'][m] = blend(b, 'pm', 'pk', 'over', keep_intercept=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


def choose(res):
    """The ship rule, fixed before looking: a v3 variant replaces v2 only if it keeps every v2 GO signal at GO and its
    out-of-sample ROI on those sides is at least v2's; among those, lowest average Kalshi log loss. Else v2 stays."""
    gos = [(m, v.split('(')[1].rstrip(')')) for m, v in res['verdict']['v2'].items() if v.startswith('GO')]
    ok = []
    for nm in res['names'][1:]:
        keep = all(res['verdict'][nm][m].startswith('GO') and
                   (res['kalshi_bias'][m][nm][f'blend/{sd}']['roi'] or -1) >= (res['kalshi_bias'][m]['v2'][f'blend/{sd}']['roi'] or 0)
                   for m, sd in gos)
        if keep:
            ok.append((statistics.mean(res['kalshi'][m][nm]['logloss'] for m in res['kalshi']), nm))
    return min(ok)[1] if ok else 'v2'


def write_md(res):
    N = res['names']
    L = ['# Prop model v3: ladder distributions (workstream A)', '',
         f"Generated {res['generated']} by `nba/scripts/build_prop_model_v3.py`. Same projected mean as v2; new shape.",
         'Fit on 2024-25, tested on 2025-26, identical rows. Lower log score / log loss / Brier is better.', '',
         'Variants differ only in calibration: **v3** = isotonic across each player\'s whole range (all 2024-25 player-games),',
         '**v3_linecal** = isotonic on 2024-25 sportsbook main lines (how v2 was calibrated), **v3_raw** = none.', '',
         f"**Shipped: {res['ship']}** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).", '',
         '## Every player-game, 2025-26', '',
         'Log score = average surprise at the actual outcome under the full distribution (before calibration).',
         'Range Brier = P(over) at lines from 0.4x to 1.8x each player\'s mean, where ladders sit.', '',
         '| Market | Log score v2 | Log score v3 | ' + ' | '.join(f'Range Brier {n}' for n in N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m in MARKETS:
        a, b = res['logscore'][m], res['range_cal'][m]
        L.append(f"| {m} | {a['v2']:.4f} | {a['v3']:.4f} | " + ' | '.join(f"{b[n]['brier']:.4f}" for n in N) + ' |')
    L += ['', '## Calibration across the range (model says -> happened)', '']
    for m in MARKETS:
        for n in ('v2', 'v3'):
            L.append(f"- **{m}** {n}: " + ', '.join(f"{p:.2f}->{h:.2f}" for _, _, p, h in res['range_cal'][m][n]['deciles']))
    L += ['', '## Kalshi ladders, 2025-26 (log loss; blend t in brackets)', '',
          '| Stat | Rows | Market | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi'].items():
        L.append(f"| {m} | {d['n']:,} | {d['logloss_market']:.4f} | " + ' | '.join(f"{d[n]['logloss']:.4f} ({d[n]['blend_t']})" for n in N) + ' |')
    L += ['', 'Blended fair price (market + model, fit on the first half) scored on the second half; a diagnostic, not the ship rule:', '',
          '| Stat | Market alone | ' + ' | '.join(N) + ' |', '|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi'].items():
        L.append(f"| {m} | {d['market_2nd_half_logloss']:.5f} | " + ' | '.join(f"{d[n]['blend_oos_logloss']:.5f}" for n in N) + ' |')
    L += ['', 'Kalshi calibration by model decile (model -> hit):', '']
    for m, d in res['kalshi'].items():
        for n in N:
            L.append(f"- **{m}** {n}: " + ', '.join(f"{p:.2f}->{h:.2f}" for _, _, p, h in d[n]['deciles']))
    L += ['', '## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)', '',
          '| Stat | Rows | Market | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['espn'].items():
        L.append(f"| {m} | {d['n']:,} | {d['logloss_market']:.4f} | " + ' | '.join(f"{d[n]['logloss']:.4f} ({d[n]['blend_t']})" for n in N) + ' |')
    f = lambda x: f"{x['roi']:+.1%} ({x['n']:,}, z {x['z']})" if x and x.get('roi') is not None else 'none'
    L += ['', '## Betting it, out of sample, 3%+ edge', '',
          'Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.', '',
          '| Stat | Side | Price only | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi_bias'].items():
        for side in ('YES', 'NO'):
            L.append(f"| {m} | {side} | {f(d['v2'].get(f'price_only/{side}'))} | " + ' | '.join(f(d[n].get(f'blend/{side}')) for n in N) + ' |')
    g = lambda x: f"{x['0.03']['roi']:+.1%} ({x['0.03']['n']:,}, z {x['0.03']['z']})" if x and x.get('0.03', {}).get('n') else 'none'
    L += ['', '| Sportsbook stat (24-25 fit, 25-26 close) | ' + ' | '.join(N) + ' |', '|---|' + '---|' * len(N)]
    for k, d in res['blend_oos'].items():
        if k.startswith('espn'):
            L.append(f"| {k.split('/')[1]} | " + ' | '.join(g(d.get(n)) for n in N) + ' |')
    L += ['', '## Gates', '', '| Stat | ' + ' | '.join(N) + ' |', '|---|' + '---|' * len(N)]
    for m in MARKETS:
        L.append(f"| {m} | " + ' | '.join(res['verdict'][n][m] for n in N) + ' |')
    P = res['production']
    L += ['', '## Fitted shape', '',
          f"- Minutes: {res['Q']} scenarios from the standardized miss; median miss by role x blowout risk: " +
          ', '.join(f"{k} {v[len(v) // 2]:+.2f}" for k, v in res['minutes'].items()),
          f"- Rebounds / assists dispersion (G, F, C): reb {P['nb']['reb']}, ast {P['nb']['ast']}",
          f"- 3PA dispersion {P['att']}, 3P% concentration {P['conc']}",
          f"- Points / combos variance (c1, c2) by group: " + '; '.join(f"{m} {P['normal'][m]}" for m in NORMAL), '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
