#!/usr/bin/env python3
"""
Prop model v2: v1's minutes x rate projection, plus context a box-score average does not see, weighted by a
ridge "stacker" that is fit on one season and judged on the next. Compared with v1 on identical rows.

What v2 adds (all walk-forward: every input is known before tip):
  opp      opponent defense by position group: EWMA of what a team allows each group (G / F / C) per stat,
           as actual / expected, where expected = those players' own pre-game rates x their minutes.
           So it is schedule-adjusted: holding stars below their norm counts, facing a weak lineup does not.
  pace     expected possessions: both teams' recent pace (possessions per 48, from box scores) vs league
  market   the betting market's implied team total (close total and spread) vs the team's recent scoring
  shooting points and 3PM rebuilt from volume x shooting %: attempts per minute (stable) times make rates
           shrunk hard to league average (noisy), the classic fix for hot and cold shooting stretches
  season   season-to-date per-minute rate vs the EWMA (does the EWMA over-react?)
  home, back-to-back
  minutes  each player's own minutes volatility (EWMA of squared misses) enters the variance, so a player
           whose minutes swing gets wider tails at the same mean. That is what Kalshi's ladders price.

Protocol (the week 3 one, same rows for v1 and v2):
  fit      stacker weights and both variance models on 2024-25 (injury report 30 min pre-tip);
           calibration on 2024-25 ESPN open lines
  test     2025-26: projection MAE, ESPN pre-tip close lines, every Kalshi strike at its pre-tip price
           (fees in); blend weights for Kalshi fit on the first half of the ladder data, tested on the second

  python3 nba/scripts/build_prop_model_v2.py
Writes data/prop_model_v2.json and docs/prop-model-v2.md.
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as V1
from build_prop_model import (BASE, COMBO, MARKETS, COUNT_MKTS, RATE_ALPHA, PRIOR_GAMES, sv, phi, nb_sf, pav,
                              apply_cal, am_prob, am_payout, kalshi_fee, blend, blend_prob, summarize, grade_book)

SEASONS = [2022, 2023, 2024, 2025, 2026]
FIT, TEST = 2025, 2026
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'prop_model_v2.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'prop-model-v2.md')
FEAT = ['opp', 'pace', 'market', 'shooting', 'season', 'home', 'b2b', 'scale', 'const']
A_DEF, A_PACE, A_PCT, A_VOL = 0.06, 0.08, 0.02, 0.10      # EWMA speeds: defense, pace / scoring, shooting %, minutes volatility
SHRINK = {'p3': 150.0, 'p2': 100.0, 'ft': 60.0}            # attempts of league-average shooting mixed into each %
DEF_N0 = 10                                                # games before a defense factor is trusted half-way


def ewma(old, new, a):
    return new if old is None else old + a * (new - old)


class Context:
    """Everything v2 tracks on top of v1's state. Updated after each game, read before the next."""

    def __init__(self):
        self.pace, self.pts, self.last = {}, {}, {}          # team -> possessions/48 EWMA, points scored EWMA
        self.lg_pace = None
        self.dfn = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'A': None, 'E': None, 'n': 0})))  # team -> pos -> stat
        self.sh = {}                                          # aid -> attempt rates, decayed makes/attempts, n
        self.lg = {'m3': 0.0, 'a3': 0.0, 'm2': 0.0, 'a2': 0.0, 'mf': 0.0, 'af': 0.0}
        self.szn = defaultdict(lambda: {'season': None, 'S': defaultdict(float), 'M': 0.0})
        self.vol = {}                                         # aid -> EWMA squared minutes miss

    def lg_pct(self, k):
        m, a = {'p3': ('m3', 'a3'), 'p2': ('m2', 'a2'), 'ft': ('mf', 'af')}[k]
        return self.lg[m] / self.lg[a] if self.lg[a] else {'p3': 0.36, 'p2': 0.53, 'ft': 0.78}[k]

    def opp_factor(self, team, pos, s):
        d = self.dfn[team][pos][s]
        if not d['E']:
            return 1.0
        raw = d['A'] / d['E']
        return 1.0 + (raw - 1.0) * d['n'] / (d['n'] + DEF_N0)

    def struct_rates(self, aid):
        """(points per minute, 3PM per minute) from attempts x shrunk percentages, or None."""
        p = self.sh.get(aid)
        if not p or p['n'] < 3:
            return None
        pct = {k: (p['m' + k] + SHRINK[k] * self.lg_pct(k)) / (p['a' + k] + SHRINK[k]) for k in ('p3', 'p2', 'ft')}
        return (p['r2'] * 2 * pct['p2'] + p['r3'] * 3 * pct['p3'] + p['rf'] * pct['ft'], p['r3'] * pct['p3'])

    def shoot(self, aid):
        """(3PA per minute, regressed 3P%) or None: the two halves of a 3PM projection."""
        p = self.sh.get(aid)
        if not p or p['n'] < 3:
            return None
        return p['r3'], (p['mp3'] + SHRINK['p3'] * self.lg_pct('p3')) / (p['ap3'] + SHRINK['p3'])

    def update(self, g, rows, rt_before):
        by = defaultdict(list)
        for r in rows:
            if r['played'] and r['minutes'] > 0:
                by[r['team']].append(r)
        if len(by) != 2:
            return
        paces = {}
        for team, rs in by.items():
            mins = sum(r['minutes'] for r in rs)
            poss = sum(r['field_goals_attempted'] + 0.44 * r['free_throws_attempted'] - r['offensive_rebounds'] + r['turnovers'] for r in rs)
            paces[team] = poss * 240.0 / max(200.0, mins)
            self.pts[team] = ewma(self.pts.get(team), sum(r['points'] for r in rs) * 240.0 / max(200.0, mins), A_PACE)
        gp = statistics.mean(paces.values())
        for team in by:
            self.pace[team] = ewma(self.pace.get(team), gp, A_PACE)
            self.last[team] = g['tip']
        self.lg_pace = ewma(self.lg_pace, gp, 0.01)
        # defense: each team vs the players it faced, by position group, actual / expected
        for team, rs in by.items():
            opp = next(t for t in by if t != team)
            acc = defaultdict(lambda: [0.0, 0.0])
            for r in rs:
                p = rt_before.get(r['athlete_id'])
                if not p:
                    continue
                pos = MM.group(r['pos'])
                for s in BASE:
                    acc[(pos, s)][0] += sv(r, BASE[s])
                    acc[(pos, s)][1] += p['rate'][s] * r['minutes']
            for (pos, s), (a, e) in acc.items():
                if e > 0.5:
                    d = self.dfn[opp][pos][s]
                    d['A'], d['E'] = ewma(d['A'], a, A_DEF), ewma(d['E'], e, A_DEF)
                    d['n'] += 1
        # shooting volume and makes
        for rs in by.values():
            for r in rs:
                m, aid = r['minutes'], r['athlete_id']
                a3, m3 = r['three_point_field_goals_attempted'], r['three_point_field_goals_made']
                a2, m2 = r['field_goals_attempted'] - a3, r['field_goals_made'] - m3
                af, mf = r['free_throws_attempted'], r['free_throws_made']
                for k, v in (('m3', m3), ('a3', a3), ('m2', m2), ('a2', a2), ('mf', mf), ('af', af)):
                    self.lg[k] += v
                p = self.sh.get(aid)
                if p is None:
                    p = self.sh[aid] = {'r3': a3 / m, 'r2': a2 / m, 'rf': af / m, 'n': 0,
                                        'mp3': 0.0, 'ap3': 0.0, 'mp2': 0.0, 'ap2': 0.0, 'mft': 0.0, 'aft': 0.0}
                a = max(RATE_ALPHA, 1 / (p['n'] + 1 + PRIOR_GAMES))
                w = min(1.0, m / 20.0)
                p['r3'] += a * w * (a3 / m - p['r3'])
                p['r2'] += a * w * (a2 / m - p['r2'])
                p['rf'] += a * w * (af / m - p['rf'])
                for k, mk, at in (('p3', m3, a3), ('p2', m2, a2), ('ft', mf, af)):
                    p['m' + k] = p['m' + k] * (1 - A_PCT) + mk
                    p['a' + k] = p['a' + k] * (1 - A_PCT) + at
                p['n'] += 1
                z = self.szn[aid]
                if z['season'] != g['season']:
                    z['season'], z['S'], z['M'] = g['season'], defaultdict(float), 0.0
                for s in BASE:
                    z['S'][s] += sv(r, BASE[s])
                z['M'] += m


def features(ctx, g, team, opp, aid, pos, mu, pm, rate, line):
    """Stacker inputs for one player-game, one per stat. line: closing game line dict or None."""
    home = 1.0 if team == g['home'] else 0.0
    last = ctx.last.get(team)
    b2b = 1.0 if last and (g['tip'] - last) < dt.timedelta(hours=30) else 0.0
    pace = 1.0
    if ctx.lg_pace and team in ctx.pace and opp in ctx.pace:
        pace = (ctx.pace[team] + ctx.pace[opp] - ctx.lg_pace) / ctx.pace[team]
    mkt = 1.0
    if line and line.get('total_close') and line.get('spread_close') is not None and ctx.pts.get(team):
        hs = line['spread_close']                              # home spread, negative = home favoured
        implied = line['total_close'] / 2 - hs / 2 if home else line['total_close'] / 2 + hs / 2
        mkt = implied / ctx.pts[team]
    sr = ctx.struct_rates(aid)
    z = ctx.szn[aid]
    out = {}
    for s in BASE:
        m = mu[s]
        struct = 0.0
        if sr and s in ('pts', '3pm'):
            struct = pm * (sr[0] if s == 'pts' else sr[1]) - m
        szn = 0.0
        if z['season'] == g['season'] and z['M'] > 0:
            szn = pm * ((z['S'][s] + 200 * rate[s]) / (z['M'] + 200) - rate[s])
        out[s] = [m * (ctx.opp_factor(opp, pos, s) - 1), m * (pace - 1), m * (mkt - 1), struct, szn,
                  m * (home - 0.5), m * b2b, m, 1.0]
    return out


def walk(box, inj, margins, mm, casc, team_min, lines, base='v2', mv3=None, rv3=None, feed=None, moved=False, cand_rule='asof'):
    """v1's projection exactly (the 'tip' clock), plus v2 features, for every player-game from 2023 on.
    Injuries: who actually sat before 2025 (no archived reports), the report 30 min pre-tip from 2025.
    base='v3' swaps in the v3 base (docs/v3-plan.md B + C): minutes model v3 (role, returns, new team, market spread;
    data/minutes_model_v3.json) and per-stat memory component rates (data/rates_v3.json). Everything else is shared.
    feed (base v3 only, build_starters.py): {(game_id, team): {'start': {aid}, 'inactive': {aid}}} from NBA.com's
    confirmed lineups. The role term then uses who is starting tonight (minutes v3's starters-known weights) and
    the inactive list joins the injury report's Out.
    moved (docs/moved-players-test.md): a dressed player whose minutes history is from another team counts as a
    candidate (his own minutes and starter share carried over) instead of being left out of his first game.
    Every record carries 'na' (a dressed player on this team is within his first 10 games after moving) and 'mv'
    (this player is that mover)."""
    rt, ctx = {}, Context()
    R = None
    if base == 'v3':
        import build_minutes_model_v3 as M3
        import build_rates_v3 as R3
        ms = M3.State(mv3['alpha'], mv3['a_new'], mv3['new_n'])
        beta = [mv3['beta_hindsight_starters' if feed else 'beta'][f] for f in M3.FEATURES]
        R = R3.Rates(rv3['alpha'], {c: (v['decay'], v['k']) for c, v in rv3['pct'].items()}) if rv3 else None   # None: v1 rates

        def mfeat(g, team, aid, out):
            ln = lines.get(g['game_id']) or {}
            sp = ln.get('spread_close') if ln.get('spread_close') is not None else margins.get(g['game_id'])
            x = M3.features(ms, g, team, aid, out, sp)
            lu = feed.get((g['game_id'], team)) if feed else None
            if lu:
                x[M3.FEATURES.index('role')] = M3.role_term(ms.pl[aid], aid in lu['start'])
            return x
    else:
        ms = MM.State(mm['alpha'])
        beta = [mm['beta'][f] for f in MM.FEATURES]

        def mfeat(g, team, aid, out):
            return MM.features(ms, g, team, aid, out, margins.get(g['game_id']))
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    recs = []
    with_n, mover = defaultdict(int), set()           # (aid, team) -> games dressed for it; (aid, team) that moved in
    for g in C.games(SEASONS):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= 2023:
            played = {r['athlete_id'] for r in rows if r['played']}
            day = g['tip_et'].strftime('%Y-%m-%d')
            clk = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
            for team, opp in ((g['home'], g['away']), (g['away'], g['home'])):
                rot = ms.rotation(team, g['tip'])
                new_in = {r['athlete_id'] for r in rows if r['team'] == team and (r['athlete_id'], team) in mover
                          and with_n[(r['athlete_id'], team)] < 10}
                if g['season'] < 2025:
                    out = {a: 1.0 for a in rot if a not in played}
                else:
                    out = {a: 1.0 for a, s in inj.status(day, team, clk).items() if s in ('Out', 'Doubtful')}
                if feed and (g['game_id'], team) in feed:
                    out.update({a: 1.0 for a in feed[(g['game_id'], team)]['inactive']})
                if cand_rule == 'box':
                    # LEAKY (docs/leakage-audit-2026-10-06.md, addendum 3): the post-game box score says who dressed.
                    cand = [r for r in rows if r['team'] == team and r['athlete_id'] in ms.pl
                            and (moved or ms.pl[r['athlete_id']]['team'] == team) and r['athlete_id'] in rt and r['athlete_id'] not in out]
                else:
                    # As live pricing does it (pricing.py game_minutes): everyone with minutes state on this team in the
                    # last 30 days who is not Out on the pre-tip report. Players who did not dress take minutes but
                    # get a stub row, so they are never scored.
                    byid = {r['athlete_id']: r for r in rows if r['team'] == team}
                    lim = g['tip'] - dt.timedelta(days=30)
                    cand = [byid.get(a) or {'athlete_id': a, 'team': team, 'played': False, 'minutes': 0.0}
                            for a, pp in ms.pl.items()
                            if pp['team'] == team and pp['last'] >= lim and a in rt and a not in out]
                    if moved:    # a dressed player whose history is from another team is still a candidate (docs/moved-players-test.md)
                        have = {r['athlete_id'] for r in cand}
                        cand += [r for r in byid.values() if r['athlete_id'] in ms.pl and r['athlete_id'] in rt
                                 and r['athlete_id'] not in out and r['athlete_id'] not in have]
                pm = {}
                for r in cand:
                    x = mfeat(g, team, r['athlete_id'], out)
                    pm[r['athlete_id']] = max(0.0, min(48.0, ms.pl[r['athlete_id']]['m'] + sum(b * v for b, v in zip(beta, x))))
                tot = sum(pm.values())
                if tot > 0 and len(pm) >= 7:
                    f = team_min / tot
                    pm = {a: min(48.0, m * f) for a, m in pm.items()}
                present = [rt[r['athlete_id']] for r in cand]
                for r in cand:
                    aid = r['athlete_id']
                    if not r['played']:
                        continue
                    p, pos = rt[aid], ms.pl[aid]['pos']
                    rates = (R.stat_rates(aid) if R else None) or p['rate']
                    mu = {}
                    for s in BASE:
                        rate = rates[s]
                        c = casc.get(s)
                        if c and c['use']:
                            vs = sum(rt[a]['pg'][s] for a in out if a in rt and a != aid and a in rot and rot[a]['pos'] == pos)
                            vo = sum(rt[a]['pg'][s] for a in out if a in rt and a != aid and a in rot and rot[a]['pos'] != pos)
                            avg = statistics.mean(q['rate'][s] for q in present) if present else 0
                            rel = rate / avg if avg > 0 else 1.0
                            b = c['beta']
                            mu[s] = max(0.0, pm[aid] * rate + pm[aid] / 48.0 * (b[0] * vs + b[1] * vo + b[2] * vs * rel + b[3] * vo * rel))
                        else:
                            mu[s] = max(0.0, pm[aid] * rate)
                    y = {s: sv(r, BASE[s]) for s in BASE}
                    ln = lines.get(g['game_id']) or {}
                    sh = ctx.shoot(aid)
                    recs.append({'gid': g['game_id'], 'season': g['season'], 'aid': aid, 'min': r['minutes'], 'pm': pm[aid],
                                 'team': team, 'na': bool(new_in), 'mv': aid in new_in,
                                 'pos': pos, 'st': ms.pl[aid]['st'], 'spread': ln.get('spread_close'), 'y3pa': r['three_point_field_goals_attempted'],
                                 'r3': sh[0] if sh else None, 'p3': sh[1] if sh else None,
                                 'mu': mu, 'rate': dict(rates), 'sdm': math.sqrt(ctx.vol.get(aid, 36.0)),
                                 'x': features(ctx, g, team, opp, aid, pos, mu, pm[aid], rates, lines.get(g['game_id'])),
                                 'y': y})
        for r in rows:                                # who moved in (had minutes history elsewhere), before the state learns this game
            k = (r['athlete_id'], r['team'])
            if with_n[k] == 0 and r['athlete_id'] in ms.pl and ms.pl[r['athlete_id']]['team'] != r['team']:
                mover.add(k)
            with_n[k] += 1
        update_after(g, rows, rt, prior, ms, ctx)
        if R:
            R.update(rows)
    return recs, ctx


def update_after(g, rows, rt, prior, ms, ctx):
    """All state updates once a game is final. Defense is scored against the rates as they were before it."""
    rt_before = {aid: {'rate': dict(p['rate'])} for aid, p in rt.items()}
    for r in rows:
        if r['played'] and r['athlete_id'] in ms.pl and r['minutes'] > 0:
            miss = r['minutes'] - ms.pl[r['athlete_id']]['m']
            ctx.vol[r['athlete_id']] = ewma(ctx.vol.get(r['athlete_id'], 36.0), miss * miss, A_VOL)
    ctx.update(g, rows, rt_before)
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
            p = rt[aid] = {'n': 0, 'pos': pos, 'rate': {s: prior[pos][s][0] / max(1.0, prior[pos][s][1]) for s in BASE},
                           'pg': {s: sv(r, BASE[s]) for s in BASE}}
        a = max(RATE_ALPHA, 1 / (p['n'] + 1 + PRIOR_GAMES))
        w = min(1.0, m / 20.0)
        for s, cols in BASE.items():
            p['rate'][s] += a * w * (sv(r, cols) / m - p['rate'][s])
            p['pg'][s] += max(RATE_ALPHA, 1 / (p['n'] + 1)) * (sv(r, cols) - p['pg'][s])
        p['n'] += 1


# ── fitting ────────────────────────────────────────────────────────────────
def ridge(X, y, lam):
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (lam if i == j and i < k - 1 else 0) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * yy for x, yy in zip(X, y)) for i in range(k)]
    beta = MM.solve(A, b)
    res = [yy - sum(bi * xi for bi, xi in zip(beta, x)) for x, yy in zip(X, y)]
    s2 = sum(e * e for e in res) / max(1, len(X) - k)
    se = [math.sqrt(max(0.0, s2 * MM.solve(A, [1.0 if j == i else 0.0 for j in range(k)])[i])) for i in range(k)]
    return beta, se


def fit_stacker(recs):
    """Per stat: actual - v1 mean ~ features. Ridge scaled to the sample so it only bites on weak columns."""
    out = {}
    for s in BASE:
        X = [r['x'][s] for r in recs]
        y = [r['y'][s] - r['mu'][s] for r in recs]
        beta, se = ridge(X, y, lam=len(X) * 0.002)
        out[s] = {'beta': [round(b, 5) for b in beta], 't': [round(b / e, 2) if e else 0 for b, e in zip(beta, se)]}
    return out


def mu2(r, stk):
    m = {s: max(0.0, r['mu'][s] + sum(b * x for b, x in zip(stk[s]['beta'], r['x'][s]))) for s in BASE}
    for cm, parts in COMBO.items():
        m[cm] = sum(m[x] for x in parts)
    return m


def mu1(r):
    m = dict(r['mu'])
    for cm, parts in COMBO.items():
        m[cm] = sum(m[x] for x in parts)
    return m


def minrate(r, mkt):
    parts = COMBO.get(mkt, [mkt])
    return sum(r['rate'][p] for p in parts)


def fit_var(recs, mfun, with_minutes):
    """var(y | mu) = v0 + v1 mu + v2 mu^2 (+ v3 (rate x minutes sd)^2): the last term is v2's player-specific part."""
    V = {}
    for mkt in MARKETS:
        X, Y = [], []
        for r in recs:
            mu = mfun(r)[mkt]
            y = r['y'][mkt] if mkt in BASE else sum(r['y'][p] for p in COMBO[mkt])
            row = [1.0, mu, mu * mu]
            if with_minutes:
                row.append((minrate(r, mkt) * r['sdm']) ** 2)
            X.append(row)
            Y.append((y - mu) ** 2)
        V[mkt] = [round(b, 5) for b in MM.ols(X, Y, ridge=1.0)]
    return V


def p_over(mkt, mu, line, V, extra=0.0):
    v = V[mkt]
    var = max(0.25, v[0] + v[1] * mu + v[2] * mu * mu + (v[3] * extra if len(v) > 3 else 0.0))
    if mkt in COUNT_MKTS:
        return nb_sf(int(math.floor(line)), mu, var)
    return 1 - phi((line - mu) / math.sqrt(var))


def logloss(rows, k, y):
    return statistics.mean(-math.log(max(1e-6, x[k] if x[y] else 1 - x[k])) for x in rows)


def main():
    box = C.player_games(SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    team_min = json.load(open(V1.OUT_JSON))['team_min']
    lines = C.closing_lines()
    recs, ctx = walk(box, inj, margins, mm, casc, team_min, lines)
    fit = [r for r in recs if r['season'] == FIT]
    test = [r for r in recs if r['season'] == TEST]
    print(f'player-games: fit {len(fit):,}  test {len(test):,}', flush=True)

    stk = fit_stacker(fit)
    for s, v in stk.items():
        print(f'  stacker {s:4s}', ' '.join(f'{f}={b:+.3f}(t{t:+.1f})' for f, b, t in zip(FEAT, v['beta'], v['t'])), flush=True)
    V1v = fit_var(fit, mu1, False)
    V2v = fit_var(fit, lambda r: mu2(r, stk), True)
    models = {
        'v1': (mu1, V1v, False),
        'v2': (lambda r: mu2(r, stk), V2v, True),
        'v2_mean_only': (lambda r: mu2(r, stk), fit_var(fit, lambda r: mu2(r, stk), False), False),
        'v1_mean_v2_spread': (mu1, fit_var(fit, mu1, True), True),
    }

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'features': FEAT,
           'stacker': stk, 'variance': {k: v[1] for k, v in models.items()}, 'mae': {}, 'espn': {}, 'kalshi': {},
           'blend_oos': {}, 'kalshi_bias': {}, 'calibration': {}}
    # projection accuracy, test season
    for name, (mf, _, _) in models.items():
        if name in ('v1', 'v2'):
            res['mae'][name] = {m: round(statistics.mean(abs(mf(r)[m] - (r['y'][m] if m in BASE else sum(r['y'][p] for p in COMBO[m]))) for r in test), 3)
                                for m in MARKETS}
    res['rmse'], res['bias'] = {}, {}
    for name in ('v1', 'v2'):
        mf = models[name][0]
        err = {m: [mf(r)[m] - (r['y'][m] if m in BASE else sum(r['y'][p] for p in COMBO[m])) for r in test] for m in MARKETS}
        res['rmse'][name] = {m: round(math.sqrt(statistics.mean(e * e for e in v)), 3) for m, v in err.items()}
        res['bias'][name] = {m: round(statistics.mean(v), 3) for m, v in err.items()}
    print('MAE v1', res['mae']['v1'], '\nMAE v2', res['mae']['v2'], '\nRMSE v1', res['rmse']['v1'], '\nRMSE v2', res['rmse']['v2'],
          '\nbias v1', res['bias']['v1'], '\nbias v2', res['bias']['v2'], flush=True)

    by = {(r['gid'], r['aid']): r for r in recs}
    # ESPN lines: 2024-25 open (calibration + blend fit), 2025-26 pre-tip close (test)
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
                                   'tip': int(row['tip_ts']), 'gid': row['game_id'], 'vol30': float(row['vol30_pretip'] or 0)})

    for name, (mf, V, wm) in models.items():
        cal = {}
        for mkt in MARKETS:
            pts = []
            for x in espn.get(('2025', mkt, 'open'), []):
                ex = (minrate(x['r'], mkt) * x['r']['sdm']) ** 2 if wm else 0.0
                pts.append((p_over(mkt, mf(x['r'])[mkt], x['L'], V, ex), 1 if x['over'] else 0))
            cal[mkt] = pav(pts)
        res['calibration'][name] = cal

        def prob(x, mkt):
            ex = (minrate(x['r'], mkt) * x['r']['sdm']) ** 2 if wm else 0.0
            return apply_cal(cal[mkt], p_over(mkt, mf(x['r'])[mkt], x['L'], V, ex))

        for mkt in MARKETS:
            f25 = [dict(x, pm=prob(x, mkt)) for x in espn.get(('2025', mkt, 'open'), [])]
            t26 = [dict(x, pm=prob(x, mkt)) for x in espn.get(('2026', mkt, 'close'), [])]
            if t26:
                res['espn'].setdefault(mkt, {})[name] = {
                    'n': len(t26), 'logloss_model': round(logloss(t26, 'pm', 'over'), 4), 'logloss_market': round(logloss(t26, 'pk', 'over'), 4),
                    'brier_model': round(statistics.mean((x['pm'] - x['over']) ** 2 for x in t26), 4),
                    'blend_t': (blend(t26, 'pm', 'pk', 'over') or {}).get('t')}
                if f25:
                    bo = V1.blended_backtest(f25, t26, 'pm', 'pk', 'over', lambda r_, o: (1.0, am_payout(r_['over_px'] if o else r_['under_px'])))
                    res['blend_oos'].setdefault(f'espn25->26/{mkt}', {})[name] = bo
            rows = [dict(x, pm=prob(x, mkt)) for x in kal.get(mkt, [])]
            if not rows:
                continue
            res['kalshi'].setdefault(mkt, {})[name] = {
                'n': len(rows), 'logloss_model': round(logloss(rows, 'pm', 'yes'), 4), 'logloss_market': round(logloss(rows, 'k', 'yes'), 4),
                'brier_model': round(statistics.mean((x['pm'] - x['yes']) ** 2 for x in rows), 4),
                'blend_t': (blend(rows, 'pm', 'k', 'yes') or {}).get('t')}
            tips = sorted(x['tip'] for x in rows)
            cut = tips[len(tips) // 2]
            fr, tr = [x for x in rows if x['tip'] < cut], [x for x in rows if x['tip'] >= cut]

            def kprice(r_, yes):
                c = r_['k'] if yes else 1 - r_['k']
                c += kalshi_fee(c)
                return (c, 1 - c)
            res['blend_oos'].setdefault(f'kalshi/{mkt}', {})[name] = V1.blended_backtest(fr, tr, 'pm', 'k', 'yes', kprice)
            # the overs-bias baseline: does the model beat "recalibrate the price and fade YES"?
            out = {}
            for label, f_, t_ in (('blend', fr, tr), ('price_only', [dict(x, pm=0.5) for x in fr], [dict(x, pm=0.5) for x in tr])):
                coef = blend(f_, 'pm', 'k', 'yes', keep_intercept=True)
                for side in (True, False):
                    gm, daily = defaultdict(list), defaultdict(lambda: [0, 0, 0.0])
                    for x in t_:
                        e = blend_prob(coef, x['k'], x['pm']) - x['k']
                        if abs(e) < 0.03 or (e > 0) != side:
                            continue
                        c = (x['k'] if side else 1 - x['k'])
                        c += kalshi_fee(c)
                        win = x['yes'] if side else not x['yes']
                        gm[x['gid']].append(((1 - c) if win else -c) / c)
                        dd = daily[tip_day(x['tip'])]
                        dd[0 if win else 1] += 1
                        dd[2] += gm[x['gid']][-1]
                    allr = [v for vs in gm.values() for v in vs]
                    means = [statistics.mean(v) for v in gm.values()]
                    z = (statistics.mean(means) / (statistics.stdev(means) / math.sqrt(len(means)))) if len(means) > 2 and statistics.stdev(means) > 0 else 0
                    out[f"{label}/{'YES' if side else 'NO'}"] = {'n': len(allr), 'games': len(gm), 'roi': round(statistics.mean(allr), 4) if allr else None, 'z': round(z, 2),
                                                                 # each game day's bets [ET day, wins, losses, units]: What Works draws the season from it
                                                                 'daily': [[d, w_, l_, round(u_, 3)] for d, (w_, l_, u_) in sorted(daily.items())] if label == 'blend' else None}
            res['kalshi_bias'].setdefault(mkt, {})[name] = out

    # the page needs the v2 blend coefficients: fit on ALL of 2025-26 Kalshi / the 2024-25 ESPN open lines
    res['blend_live'] = {'kalshi': {}, 'book': {}}
    mf, V, wm = models['v2']
    cal = res['calibration']['v2']
    for mkt in MARKETS:
        def pr_(x):
            ex = (minrate(x['r'], mkt) * x['r']['sdm']) ** 2
            return apply_cal(cal[mkt], p_over(mkt, mf(x['r'])[mkt], x['L'], V, ex))
        k = [dict(x, pm=pr_(x)) for x in kal.get(mkt, [])]
        if k:
            res['blend_live']['kalshi'][mkt] = blend(k, 'pm', 'k', 'yes', keep_intercept=True)
        b = [dict(x, pm=pr_(x)) for x in espn.get(('2025', mkt, 'open'), [])] + [dict(x, pm=pr_(x)) for x in espn.get(('2026', mkt, 'close'), [])]
        if b:
            res['blend_live']['book'][mkt] = blend(b, 'pm', 'pk', 'over', keep_intercept=True)
    res['verdict'] = verdicts(res)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


def verdicts(res, names=('v1', 'v2')):
    """Same gate as week 3, per model: GO = 50+ games and z >= 2 on the Kalshi blend, and the blend beats the
    price-only baseline on the same side; WATCH = positive but not yet 2 SE."""
    out = {}
    for name in names:
        out[name] = {}
        for mkt in MARKETS:
            kb = (res['kalshi_bias'].get(mkt) or {}).get(name)
            best = 'NO-GO'
            if kb:
                for side in ('YES', 'NO'):
                    b, p = kb.get(f'blend/{side}') or {}, kb.get(f'price_only/{side}') or {}
                    if b.get('roi') is None or b['roi'] <= 0:
                        continue
                    beats = p.get('roi') is None or b['roi'] > p['roi']
                    if b.get('games', 0) >= 50 and b.get('z', 0) >= 2 and beats:
                        best = f'GO ({side})'
                    elif best == 'NO-GO' and beats:
                        best = f'WATCH ({side})'
            out[name][mkt] = best
    return out


def tip_day(t):
    """ET date of a tip (datetime or epoch seconds)."""
    t = t if isinstance(t, dt.datetime) else dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return C.et(t).date().isoformat() if hasattr(C, 'et') else t.date().isoformat()


def write_md(res):
    L = ['# Prop model v2: backtest against v1', '',
         f"Generated {res['generated']} by `nba/scripts/build_prop_model_v2.py`. Fit on 2024-25, tested on 2025-26,",
         'identical player-games and prices for both models. Lower log loss is better; the market row is the bar to beat.', '',
         '## Projection accuracy, 2025-26', '',
         'MAE rewards the median, RMSE the mean; bias = average (projection - actual).', '',
         '| Stat | MAE v1 | MAE v2 | RMSE v1 | RMSE v2 | Bias v1 | Bias v2 |', '|---|---|---|---|---|---|---|']
    for m in MARKETS:
        L.append(f"| {m} | {res['mae']['v1'][m]:.3f} | {res['mae']['v2'][m]:.3f} | {res['rmse']['v1'][m]:.3f} | {res['rmse']['v2'][m]:.3f} | "
                 f"{res['bias']['v1'][m]:+.3f} | {res['bias']['v2'][m]:+.3f} |")
    L += ['', '## Kalshi ladder, 2025-26: every strike at its pre-tip price', '',
          '| Stat | Rows | Log loss market | v1 | v2 | v2 spread only | Blend t v1 | Blend t v2 |', '|---|---|---|---|---|---|---|---|']
    for m, d in res['kalshi'].items():
        L.append(f"| {m} | {d['v1']['n']:,} | {d['v1']['logloss_market']:.4f} | {d['v1']['logloss_model']:.4f} | {d['v2']['logloss_model']:.4f} | "
                 f"{d['v1_mean_v2_spread']['logloss_model']:.4f} | {d['v1']['blend_t']} | {d['v2']['blend_t']} |")
    L += ['', '## ESPN pre-tip close lines, 2025-26', '',
          '| Stat | Rows | Log loss market | v1 | v2 | Blend t v1 | Blend t v2 |', '|---|---|---|---|---|---|---|']
    for m, d in res['espn'].items():
        L.append(f"| {m} | {d['v1']['n']:,} | {d['v1']['logloss_market']:.4f} | {d['v1']['logloss_model']:.4f} | {d['v2']['logloss_model']:.4f} | {d['v1']['blend_t']} | {d['v2']['blend_t']} |")
    L += ['', '## Betting it: blended fair price, out of sample, 3%+ edge', '',
          'Kalshi: blend fit on the first half of 2025-26, bet on the second half, fees in, ROI per dollar risked, z by game.',
          'Price only = the same recalibration with no model (the overs-bias baseline the model has to beat).', '',
          '| Stat | Side | Price only | v1 blend | v2 blend |', '|---|---|---|---|---|']
    for m, d in res['kalshi_bias'].items():
        for side in ('YES', 'NO'):
            po, a, b = d['v1'].get(f'price_only/{side}', {}), d['v1'].get(f'blend/{side}', {}), d['v2'].get(f'blend/{side}', {})
            f = lambda x: f"{x['roi']:+.1%} ({x['n']:,}, z {x['z']})" if x.get('roi') is not None else 'none'
            L.append(f'| {m} | {side} | {f(po)} | {f(a)} | {f(b)} |')
    L += ['', '| Sportsbook stat (ESPN 24-25 fit, 25-26 close test) | v1 ROI (n, z) | v2 ROI (n, z) |', '|---|---|---|']
    for k, d in res['blend_oos'].items():
        if not k.startswith('espn'):
            continue
        g = lambda x: f"{x['0.03']['roi']:+.1%} ({x['0.03']['n']:,}, z {x['0.03']['z']})" if x and x.get('0.03', {}).get('n') else 'none'
        L.append(f"| {k.split('/')[1]} | {g(d.get('v1'))} | {g(d.get('v2'))} |")
    L += ['', '## Gates (Kalshi blend vs the price-only baseline)', '', '| Stat | v1 | v2 |', '|---|---|---|']
    for m in MARKETS:
        L.append(f"| {m} | {res['verdict']['v1'][m]} | {res['verdict']['v2'][m]} |")
    L += ['', '## What the stacker learned (fit on 2024-25; t in brackets)', '',
          'Each weight multiplies a feature already in stat units, so 1.0 means "take the adjustment at face value".', '',
          '| Stat | ' + ' | '.join(FEAT) + ' |', '|---|' + '---|' * len(FEAT)]
    for s, v in res['stacker'].items():
        L.append(f'| {s} | ' + ' | '.join(f'{b:+.3f} ({t:+.1f})' for b, t in zip(v['beta'], v['t'])) + ' |')
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
