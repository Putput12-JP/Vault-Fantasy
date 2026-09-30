#!/usr/bin/env python3
"""
Per-stat memory, workstream C of docs/v3-plan.md (DARKO's idea): every component of production gets its own
learning rate instead of one EWMA for every stat.

Components, per minute on the floor:
  volume   2PA, 3PA, FTA, OREB, DREB, AST          EWMA, shrunk to the position average while the sample is thin
  accuracy 2P%, 3P%, FT%                            decayed makes / attempts plus k attempts at the position average
Projection given minutes m:
  PTS = m (2 * 2PA * 2P% + 3 * 3PA * 3P% + FTA * FT%)    REB = m (OREB + DREB)    AST = m * AST    3PM = m * 3PA * 3P%
v1 / v2 used one EWMA (alpha 0.10) directly on PTS, REB, AST and 3PM per minute.

Protocol: each learning rate is tuned on 2022-23 and 2023-24 by predicting the component given the TRUE minutes (so
minutes errors do not leak in); tested on 2025-26 against v1's rates the same way.

  python3 nba/scripts/build_rates_v3.py
Writes data/rates_v3.json and docs/rates-v3.md.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM

SEASONS = [2022, 2023, 2024, 2025, 2026]
TUNE, TEST = (2023, 2024), 2026
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'rates_v3.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'rates-v3.md')
PRIOR_GAMES = 8
VOL = {'fg2a': lambda r: r['field_goals_attempted'] - r['three_point_field_goals_attempted'],
       'fg3a': lambda r: r['three_point_field_goals_attempted'], 'fta': lambda r: r['free_throws_attempted'],
       'oreb': lambda r: r['offensive_rebounds'], 'dreb': lambda r: r['defensive_rebounds'], 'ast': lambda r: r['assists']}
PCT = {'p2': (lambda r: r['field_goals_made'] - r['three_point_field_goals_made'], VOL['fg2a']),
       'p3': (lambda r: r['three_point_field_goals_made'], VOL['fg3a']),
       'ft': (lambda r: r['free_throws_made'], VOL['fta'])}
ALPHAS = [0.02, 0.035, 0.05, 0.07, 0.1, 0.14, 0.2, 0.3]
DECAYS = [0.0, 0.002, 0.005, 0.01, 0.02, 0.04]
KS = [25, 50, 100, 200, 400]
V1_ALPHA = 0.10
V1_STATS = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['three_point_field_goals_made']}


class Rates:
    """Component rates with one learning rate per volume component and (decay, k) per percentage."""

    def __init__(self, alpha, pct):
        self.alpha, self.pct = alpha, pct           # {comp: a}, {pct: (decay, k)}
        self.pl = {}
        self.prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))    # pos -> comp -> [sum, sum minutes | makes, attempts]

    def prior_rate(self, pos, c):
        s, m = self.prior[pos][c]
        return s / m if m else 0.0

    def prior_pct(self, pos, c):
        mk, at = self.prior[pos][c]
        return mk / at if at else {'p2': 0.53, 'p3': 0.36, 'ft': 0.78}[c]

    def comps(self, aid):
        """{component: per-minute rate or percentage} or None."""
        p = self.pl.get(aid)
        if not p:
            return None
        out = dict(p['v'])
        for c, (d, k) in self.pct.items():
            out[c] = (p['mk'][c] + k * self.prior_pct(p['pos'], c)) / (p['at'][c] + k)
        return out

    def stat_rates(self, aid):
        """Per-minute PTS, REB, AST, 3PM rebuilt from components."""
        c = self.comps(aid)
        if not c:
            return None
        return {'pts': 2 * c['fg2a'] * c['p2'] + 3 * c['fg3a'] * c['p3'] + c['fta'] * c['ft'],
                'reb': c['oreb'] + c['dreb'], 'ast': c['ast'], '3pm': c['fg3a'] * c['p3']}

    def update(self, rows):
        for r in rows:
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m, pos = r['athlete_id'], r['minutes'], MM.group(r['pos'])
            for c, f in VOL.items():
                self.prior[pos][c][0] += f(r)
                self.prior[pos][c][1] += m
            for c, (mk, at) in PCT.items():
                self.prior[pos][c][0] += mk(r)
                self.prior[pos][c][1] += at(r)
            p = self.pl.get(aid)
            if p is None:
                p = self.pl[aid] = {'n': 0, 'pos': pos, 'v': {c: self.prior_rate(pos, c) for c in VOL},
                                    'mk': {c: 0.0 for c in PCT}, 'at': {c: 0.0 for c in PCT}}
            w = min(1.0, m / 20.0)
            for c, f in VOL.items():
                a = max(self.alpha[c], 1 / (p['n'] + 1 + PRIOR_GAMES))
                p['v'][c] += a * w * (f(r) / m - p['v'][c])
            for c, (mk, at) in PCT.items():
                d = self.pct[c][0]
                p['mk'][c] = p['mk'][c] * (1 - d) + mk(r)
                p['at'][c] = p['at'][c] * (1 - d) + at(r)
            p['n'] += 1


def tune(box):
    """One pass keeps every candidate learning rate side by side; score each on 2022-24 given true minutes."""
    st = {}                                                     # aid -> state for all grid points
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    err_v = defaultdict(lambda: [0.0] * len(ALPHAS))            # comp -> squared error per alpha
    ll_p = defaultdict(lambda: [[0.0] * len(KS) for _ in DECAYS])
    n = 0
    for g in C.games(SEASONS[:3]):
        rows = box.get(g['game_id'], [])
        for r in rows:
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m, pos = r['athlete_id'], r['minutes'], MM.group(r['pos'])
            p = st.get(aid)
            if p and g['season'] in TUNE and p['n'] >= 5:
                n += 1
                for c, f in VOL.items():
                    y = f(r)
                    for i, v in enumerate(p['v'][c]):
                        err_v[c][i] += (m * v - y) ** 2
                for c, (mk, at) in PCT.items():
                    A, M = at(r), mk(r)
                    if A <= 0:
                        continue
                    pr = prior[pos][c][0] / prior[pos][c][1] if prior[pos][c][1] else 0.4
                    for i in range(len(DECAYS)):
                        for j, k in enumerate(KS):
                            q = (p['mk'][c][i] + k * pr) / (p['at'][c][i] + k)
                            q = min(0.999, max(0.001, q))
                            ll_p[c][i][j] += M * math.log(q) + (A - M) * math.log(1 - q)
            for c, f in VOL.items():
                prior[pos][c][0] += f(r)
                prior[pos][c][1] += m
            for c, (mk, at) in PCT.items():
                prior[pos][c][0] += mk(r)
                prior[pos][c][1] += at(r)
            if p is None:
                p = st[aid] = {'n': 0, 'v': {c: [prior[pos][c][0] / prior[pos][c][1]] * len(ALPHAS) for c in VOL},
                               'mk': {c: [0.0] * len(DECAYS) for c in PCT}, 'at': {c: [0.0] * len(DECAYS) for c in PCT}}
            w = min(1.0, m / 20.0)
            for c, f in VOL.items():
                x = f(r) / m
                vs = p['v'][c]
                for i, al in enumerate(ALPHAS):
                    a = max(al, 1 / (p['n'] + 1 + PRIOR_GAMES))
                    vs[i] += a * w * (x - vs[i])
            for c, (mk, at) in PCT.items():
                M, A = mk(r), at(r)
                for i, d in enumerate(DECAYS):
                    p['mk'][c][i] = p['mk'][c][i] * (1 - d) + M
                    p['at'][c][i] = p['at'][c][i] * (1 - d) + A
            p['n'] += 1
    alpha = {c: ALPHAS[min(range(len(ALPHAS)), key=lambda i: e[i])] for c, e in err_v.items()}
    pct = {}
    for c, grid in ll_p.items():
        i, j = max(((i, j) for i in range(len(DECAYS)) for j in range(len(KS))), key=lambda ij: grid[ij[0]][ij[1]])
        pct[c] = (DECAYS[i], KS[j])
    table = {'volume': {c: {str(a): round(e / n, 4) for a, e in zip(ALPHAS, err_v[c])} for c in VOL},
             'pct': {c: {f'{d}/{k}': round(ll_p[c][i][j], 1) for i, d in enumerate(DECAYS) for j, k in enumerate(KS)} for c in PCT}}
    return alpha, pct, table


def evaluate(box, alpha, pct):
    """2025-26, given true minutes: component rates vs v1's single EWMA per stat."""
    R = Rates(alpha, pct)
    v1, prior = {}, defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    err = {k: defaultdict(list) for k in ('v1', 'v3')}
    for g in C.games(SEASONS):
        rows = box.get(g['game_id'], [])
        if g['season'] == TEST:
            for r in rows:
                if not r['played'] or r['minutes'] <= 0 or r['athlete_id'] not in v1 or v1[r['athlete_id']]['n'] < 5:
                    continue
                m, s3 = r['minutes'], R.stat_rates(r['athlete_id'])
                for s, cols in V1_STATS.items():
                    y = sum(r[c] for c in cols)
                    err['v1'][s].append(m * v1[r['athlete_id']]['rate'][s] - y)
                    err['v3'][s].append(m * s3[s] - y)
        R.update(rows)
        for r in rows:                                          # v1's rates, exactly as the prop model builds them
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m, pos = r['athlete_id'], r['minutes'], MM.group(r['pos'])
            for s, cols in V1_STATS.items():
                prior[pos][s][0] += sum(r[c] for c in cols)
                prior[pos][s][1] += m
            p = v1.get(aid)
            if p is None:
                p = v1[aid] = {'n': 0, 'rate': {s: prior[pos][s][0] / max(1.0, prior[pos][s][1]) for s in V1_STATS}}
            a = max(V1_ALPHA, 1 / (p['n'] + 1 + PRIOR_GAMES))
            w = min(1.0, m / 20.0)
            for s, cols in V1_STATS.items():
                p['rate'][s] += a * w * (sum(r[c] for c in cols) / m - p['rate'][s])
            p['n'] += 1
    return {s: {k: {'rmse': round(math.sqrt(statistics.mean(e * e for e in err[k][s])), 4), 'mae': round(statistics.mean(abs(e) for e in err[k][s]), 4),
                    'bias': round(statistics.mean(err[k][s]), 4)} for k in err} | {'n': len(err['v1'][s])} for s in V1_STATS}


def main():
    box = C.player_games(SEASONS)
    alpha, pct, table = tune(box)
    print('learning rates', alpha, '\npercentages (decay, k)', pct, flush=True)
    ev = evaluate(box, alpha, pct)
    for s, d in ev.items():
        print(f"  {s:4s} RMSE v1 {d['v1']['rmse']:.4f}  v3 {d['v3']['rmse']:.4f}   MAE v1 {d['v1']['mae']:.4f}  v3 {d['v3']['mae']:.4f}", flush=True)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'alpha': alpha,
           'pct': {c: {'decay': d, 'k': k} for c, (d, k) in pct.items()}, 'prior_games': PRIOR_GAMES, 'test': ev, 'grid': table}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    half = lambda a: round(math.log(0.5) / math.log(1 - a), 1)
    L = ['# Per-stat memory (rates v3): backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_rates_v3.py`. Each learning rate tuned on 2022-23 and 2023-24,",
         'tested on 2025-26. Both models are given the TRUE minutes, so this isolates the per-minute rates.', '',
         '| Stat | Player-games | RMSE v1 (one EWMA) | RMSE v3 (components) | MAE v1 | MAE v3 | Bias v1 | Bias v3 |', '|---|---|---|---|---|---|---|---|']
    for s, d in ev.items():
        L.append(f"| {s} | {d['n']:,} | {d['v1']['rmse']:.3f} | {d['v3']['rmse']:.3f} | {d['v1']['mae']:.3f} | {d['v3']['mae']:.3f} | {d['v1']['bias']:+.3f} | {d['v3']['bias']:+.3f} |")
    L += ['', '## Tuned memory', '', '| Component | Learning rate | Half-life (games) |', '|---|---|---|']
    for c, a in alpha.items():
        L.append(f"| {c} per minute | {a} | {half(a)} |")
    for c, (d, k) in pct.items():
        L.append(f"| {c} | decay {d}/game, plus {k} attempts at the position average | {half(d) if d else 'no decay'} |")
    L += ['', 'v1 used one learning rate, 0.10 (half-life 6.6 games), for points, rebounds, assists and 3PM per minute.', '']
    open(OUT_MD, 'w').write('\n'.join(L))
    print(open(OUT_MD).read())


if __name__ == '__main__':
    main()
