#!/usr/bin/env python3
"""
Does play-by-play help the minutes model? One concrete idea, pre-registered:

  Recent minutes are polluted by garbage time (starters sit, bench plays on). Strip it out: keep an EWMA of
  COMPETITIVE minutes (before garbage time starts) and of garbage minutes, and use both to predict next-game total
  minutes, against the baseline of one EWMA of total minutes.

Garbage time = Q4 lead >= a threshold shrinking from 25 (9:00 left) to 8 (1:00 left); see build_garbage_time.py.
Minutes come from the stints themselves (the PBP clock), so no box-score join. Train 2023-24 (season ids 2023, 2024),
test 2025 (the 2024-25 season). OLS on [1, EWMA_total] vs [1, EWMA_comp, EWMA_garbage, EWMA_total].
Pass rule: out-of-sample minutes RMSE improves by >= 1% for players with >= 10 prior games.

  python3 nba/scripts/build_pbp_minutes_test.py
"""
import os
from collections import defaultdict
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(os.path.join(HERE, '..', 'raw', 'stints_2023_2025.csv'), dtype={'home5': str, 'away5': str})


def thresh(left):
    return None if left > 540 else 25 - (540 - max(left, 60)) * (17 / 480)


pg = defaultdict(lambda: [0.0, 0.0])               # (season, game, player) -> [competitive s, garbage s]
order = {}                                         # (season, game) -> sort key
for (season, gid), g in d.groupby(['season', 'game_id']):
    g = g.sort_values('start_s')
    mh = ma = 0
    gt = None
    for r in g.itertuples():
        # split this stint at the moment garbage time begins, using the stint-end margin (stints are short)
        mh += r.home_pts
        ma += r.away_pts
        if r.period == 4 and gt is None:
            t = thresh(2880 - r.end_s)
            if t is not None and abs(mh - ma) >= t:
                gt = r.end_s
        for p in (r.home5 + ' ' + r.away5).split():
            comp = r.end_s - r.start_s
            gar = 0.0
            if gt is not None and r.end_s > gt:
                gar = r.end_s - max(r.start_s, gt)
                comp -= gar
            k = (season, gid, p)
            pg[k][0] += comp
            pg[k][1] += gar
    order[(season, gid)] = (season, gid)

by_player = defaultdict(list)
for (season, gid, p), (c, gsec) in pg.items():
    by_player[p].append((season, gid, c / 60, gsec / 60))
A = 0.15
rows = []
for p, games in by_player.items():
    games.sort()
    et = ec = eg = None
    n = 0
    for season, gid, c, gm in games:
        tot = c + gm
        if et is not None and n >= 10 and tot >= 1:
            rows.append((season, tot, et, ec, eg))
        if et is None:
            et, ec, eg = tot, c, gm
        else:
            et += A * (tot - et); ec += A * (c - ec); eg += A * (gm - eg)
        n += 1
R = np.array(rows)
tr, te = R[R[:, 0] <= 2024], R[R[:, 0] == 2025]


def fit(cols):
    X = np.column_stack([np.ones(len(tr))] + [tr[:, c] for c in cols])
    b = np.linalg.lstsq(X, tr[:, 1], rcond=None)[0]
    Xt = np.column_stack([np.ones(len(te))] + [te[:, c] for c in cols])
    e = te[:, 1] - Xt @ b
    return float(np.sqrt((e ** 2).mean())), b


base, bb = fit([2])
new, bn = fit([2, 3, 4])
raw = float(np.sqrt(((te[:, 1] - te[:, 2]) ** 2).mean()))
print(f'train {len(tr):,} player-games, test {len(te):,}')
print(f'raw EWMA(total) as the forecast : RMSE {raw:.3f} min')
print(f'OLS on EWMA(total)              : RMSE {base:.3f}  coefs {np.round(bb, 3)}')
print(f'OLS + competitive + garbage     : RMSE {new:.3f}  coefs {np.round(bn, 3)}')
print(f'gain {100 * (1 - new / base):+.2f}%  -> {"PASS" if 1 - new / base >= 0.01 else "FAIL"} (rule: >= 1%)')
