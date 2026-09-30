#!/usr/bin/env python3
"""
NBA minutes model: the "volume" half of every player prop (docs/PLAN.md §4B).

Predicts a player's minutes before tip, walk-forward, from:
  base       recency-weighted minutes (EWMA)
  vacated    minutes of rotation teammates who are OUT, split same position
             group (G / F / C) vs other, scaled by the player's own share
  blowout    |expected margin|: starters sit late in lopsided games. Uses the game
             model's own pre-game margin (walk-forward), not the betting line, so the
             tune seasons (no archived lines) learn it too
  rest       back-to-back
then (optionally) rescales the team's expected players to 240 minutes.

delta = actual - base is fit by OLS on the tune seasons using who actually sat;
the test seasons use the official injury report as of 30 min before tip.
Scored only on players who played (books void a prop when the player sits).

  python3 nba/scripts/build_minutes_model.py
Writes nba/data/minutes_model.json and nba/docs/minutes-model.md
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_game_model as GM

WARM, TUNE, TEST = [2022], [2023, 2024], [2025, 2026]
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'minutes_model.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-model.md')
ROT_MIN, ROT_DAYS = 10.0, 21
FEATURES = ['vac_same', 'vac_other', 'vac_same_x_share', 'vac_other_x_share', 'blowout_starter', 'blowout_bench', 'b2b', 'b2b_x_share', 'const']


def group(pos):
    p = (pos or '').upper()
    if p in ('PG', 'SG', 'G'):
        return 'G'
    if p == 'C':
        return 'C'
    return 'F'


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def ols(X, y, ridge=1.0):
    k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (ridge if i == j else 0) for j in range(k)] for i in range(k)]
    b = [sum(x[i] * yy for x, yy in zip(X, y)) for i in range(k)]
    return solve(A, b)


class State:
    def __init__(self, alpha):
        self.alpha = alpha
        self.pl = {}          # aid -> {m, n, team, last, pos, starts}
        self.team_last = {}

    def rotation(self, team, when):
        lim = when - dt.timedelta(days=ROT_DAYS)
        return {a: p for a, p in self.pl.items() if p['team'] == team and p['m'] >= ROT_MIN and p['last'] >= lim}

    def update(self, g, rows):
        for r in rows:
            if not r['played']:
                continue
            p = self.pl.get(r['athlete_id'])
            if p is None:
                self.pl[r['athlete_id']] = {'m': r['minutes'], 'n': 1, 'team': r['team'], 'last': g['tip'],
                                            'pos': group(r['pos']), 'st': 1.0 if r['starter'] else 0.0}
            else:
                a = max(self.alpha, 1 / (p['n'] + 1))
                p['m'] += a * (r['minutes'] - p['m'])
                p['st'] += a * ((1.0 if r['starter'] else 0.0) - p['st'])
                p['n'] += 1
                p['team'], p['last'] = r['team'], g['tip']
        self.team_last[g['home']] = self.team_last[g['away']] = g['tip']


def features(st, g, team, aid, out, spread):
    p = st.pl[aid]
    rot = st.rotation(team, g['tip'])
    vs = sum(q['m'] * out.get(a, 0) for a, q in rot.items() if a != aid and q['pos'] == p['pos'])
    vo = sum(q['m'] * out.get(a, 0) for a, q in rot.items() if a != aid and q['pos'] != p['pos'])
    share = p['m'] / 48.0
    last = st.team_last.get(team)
    b2b = 1.0 if last and (g['tip'] - last) < dt.timedelta(hours=30) else 0.0
    blow = max(0.0, abs(spread) - 6.0) if spread is not None else 0.0
    starter = p['st'] >= 0.5
    return [vs, vo, vs * share, vo * share, blow if starter else 0.0, 0.0 if starter else blow, b2b, b2b * share, 1.0]


def expected_margins(box):
    """game_id -> game model's pre-game home margin (no injury info), walk-forward over every season."""
    P = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params']) if os.path.exists(GM.OUT_JSON) else GM.DEFAULT
    _, recs = GM.run(P, WARM + TUNE + TEST, box, record_from=WARM[0])
    return {r['g']['game_id']: r['none'][0] for r in recs}


def walk(seasons, box, lines, inj, alpha, record_from, mode):
    """mode: 'oracle' (who actually sat) or 'report' (injury report 30 min pre-tip)."""
    st = State(alpha)
    rows_out = []
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= record_from:
            played = {r['athlete_id'] for r in rows if r['played']}
            sp = lines.get(g['game_id'])  # expected home margin; sign is irrelevant, |margin| is used
            day = g['tip_et'].strftime('%Y-%m-%d')
            cut = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
            for team in (g['home'], g['away']):
                rot = st.rotation(team, g['tip'])
                if mode == 'oracle':
                    out = {a: 1.0 for a in rot if a not in played}
                else:
                    out = {a: (1.0 if s in ('Out', 'Doubtful') else 0.0) for a, s in inj.status(day, team, cut).items()}
                for r in rows:
                    if r['team'] != team or not r['played'] or r['athlete_id'] not in st.pl:
                        continue
                    if st.pl[r['athlete_id']]['team'] != team:
                        continue  # just traded: no base with this team yet
                    x = features(st, g, team, r['athlete_id'], out, sp)
                    rows_out.append({'g': g['game_id'], 'season': g['season'], 'team': team, 'aid': r['athlete_id'],
                                     'base': st.pl[r['athlete_id']]['m'], 'x': x, 'y': r['minutes']})
        st.update(g, rows)
    return rows_out


def evaluate(recs, beta, rescale):
    pred = {}
    for r in recs:
        pred[id(r)] = max(0.0, min(48.0, r['base'] + sum(b * x for b, x in zip(beta, r['x']))))
    if rescale:
        by = defaultdict(list)
        for r in recs:
            by[(r['g'], r['team'])].append(r)
        for grp in by.values():
            tot = sum(pred[id(r)] for r in grp)
            if tot > 0 and len(grp) >= 7:
                f = 240.0 / tot
                for r in grp:
                    pred[id(r)] = min(48.0, pred[id(r)] * f)
    err = [pred[id(r)] - r['y'] for r in recs]
    return statistics.mean(abs(e) for e in err), statistics.mean(err)


def main():
    box = C.player_games(WARM + TUNE + TEST)
    lines = expected_margins(box)
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    best = None
    for alpha in (0.10, 0.15, 0.20, 0.25, 0.30):
        tr = walk(WARM + TUNE, box, lines, None, alpha, TUNE[0], 'oracle')
        beta = ols([r['x'] for r in tr], [r['y'] - r['base'] for r in tr])
        m = evaluate(tr, beta, False)[0]
        print(f'alpha {alpha}: tune MAE {m:.3f}', flush=True)
        if best is None or m < best[0]:
            best = (m, alpha, beta)
    _, alpha, beta = best
    te_rep = walk(WARM + TUNE + TEST, box, lines, inj, alpha, TEST[0], 'report')
    te_orc = walk(WARM + TUNE + TEST, box, lines, inj, alpha, TEST[0], 'oracle')
    zero = [0.0] * len(FEATURES)
    res = {
        'alpha': alpha, 'beta': dict(zip(FEATURES, [round(b, 4) for b in beta])), 'n_test': len(te_rep),
        'mae': {
            'ewma_only': evaluate(te_rep, zero, False),
            'ewma_rescaled_240': evaluate(te_rep, zero, True),
            'model_report': evaluate(te_rep, beta, False),
            'model_report_rescaled': evaluate(te_rep, beta, True),
            'model_hindsight': evaluate(te_orc, beta, False),
        },
    }
    # where it matters most: games with a same-position rotation teammate out
    hit = [r for r in te_rep if r['x'][0] >= 15]
    res['mae_teammate_out'] = {'n': len(hit), 'ewma_only': evaluate(hit, zero, False), 'model': evaluate(hit, beta, False)}
    for k, v in res['mae'].items():
        print(f'{k:24s} MAE {v[0]:.3f}  bias {v[1]:+.3f}')
    print('teammate out (>=15 same-pos min vacated):', res['mae_teammate_out'])
    print('beta', res['beta'])
    res['generated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)


def write_md(res):
    b, m = res['beta'], res['mae']
    t = res['mae_teammate_out']
    L = ['# NBA minutes model: backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_minutes_model.py`. Walk-forward, out of sample.", '',
         'Fit on 2022-23 and 2023-24 (who actually sat). Tested on 2024-25 and 2025-26 using the official injury',
         f"report 30 min before tip. Scored on players who played: {res['n_test']:,} player-games.", '',
         '| Method | MAE (min) | Bias |', '|---|---|---|']
    names = {'ewma_only': 'Recent minutes only (EWMA)', 'ewma_rescaled_240': 'Recent minutes, team scaled to 240',
             'model_report': 'Model, injury report', 'model_report_rescaled': 'Model, injury report, scaled to 240',
             'model_hindsight': 'Model, hindsight (who actually sat)'}
    for k, v in m.items():
        L.append(f'| {names[k]} | {v[0]:.2f} | {v[1]:+.2f} |')
    L += ['', f"When a same-position rotation teammate (15+ min) is out ({t['n']:,} player-games): recent-minutes MAE "
          f"{t['ewma_only'][0]:.2f} vs model {t['model'][0]:.2f}.", '',
          '## What the fitted weights say', '',
          f"- Each minute vacated by a same-position teammate: +{b['vac_same']:.3f} min, plus {b['vac_same_x_share']:.3f} x (player's share of 48).",
          f"- Each minute vacated by another position: +{b['vac_other']:.3f} min, plus {b['vac_other_x_share']:.3f} x share.",
          f"- Blowout (per point of spread beyond 6): starters {b['blowout_starter']:+.3f} min, bench {b['blowout_bench']:+.3f} min.",
          f"- Back-to-back: {b['b2b']:+.3f} min, plus {b['b2b_x_share']:+.3f} x share.",
          f"- EWMA smoothing alpha {res['alpha']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
