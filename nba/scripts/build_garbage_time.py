#!/usr/bin/env python3
"""
Garbage-time model from play-by-play stints. Question: does a nonlinear, probability-of-garbage-time form of blowout
risk describe late-game minutes better than the minutes model's linear 'max(0, |spread| - 6)' term?

Garbage time starts (first time) in Q4 when the lead >= G(t), G shrinking from 25 points at 9:00 left to 8 at 1:00
(the NBA-in-R style definition, minus its starters-on-floor condition). Pregame strength gap = difference in
PRIOR-season average margin (from the same stints) + 2.5 home edge: a stand-in for the spread, because ESPN lines are
unreachable from this sandbox.

  python3 nba/scripts/build_garbage_time.py
"""
import os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(os.path.join(HERE, '..', 'raw', 'stints_2023_2025.csv'), dtype={'home5': str, 'away5': str})


def thresh(left):
    """Lead needed for garbage time with `left` seconds remaining in Q4; None before 9:00."""
    if left > 540:
        return None
    return 25 - (540 - max(left, 60)) * (17 / 480)


rows = []
for (season, gid), g in d.groupby(['season', 'game_id']):
    g = g.sort_values('start_s')
    mh = ma = 0
    gt_start = None
    for r in g.itertuples():
        mh += r.home_pts
        ma += r.away_pts
        if r.period == 4 and gt_start is None:
            t = thresh(2880 - r.end_s)
            if t is not None and abs(mh - ma) >= t:
                gt_start = r.end_s
    rows.append(dict(season=season, game_id=gid, home=g.home_team.iloc[0], away=g.away_team.iloc[0],
                     margin=mh - ma, gt_start=gt_start, reg_end=2880))
G = pd.DataFrame(rows)
G['is_gt'] = G.gt_start.notna()
G['gt_min'] = np.where(G.is_gt, (G.reg_end - G.gt_start.fillna(0)) / 60, 0.0)
tm = pd.concat([G.assign(t=G.home, m=G.margin), G.assign(t=G.away, m=-G.margin)])
prior = tm.groupby(['season', 't']).m.mean().reset_index()
prior['season'] += 1
P = prior.set_index(['season', 't']).m
G['gap'] = [P.get((s, h), np.nan) - P.get((s, a), np.nan) + 2.5 for s, h, a in zip(G.season, G.home, G.away)]
G = G.dropna(subset=['gap']).copy()
G['absgap'] = G.gap.abs()
G['bucket'] = pd.cut(G.absgap, [0, 2, 4, 6, 8, 10, 30])
print(f'{len(G)} games with a prior-season gap (seasons {sorted(G.season.unique())})')
print(G.groupby('bucket', observed=True).agg(games=('is_gt', 'size'), p_garbage=('is_gt', 'mean'), garbage_min=('gt_min', 'mean')).round(3))
x, y = G.absgap.values, G.gt_min.values
for name, X in (('linear max(0,|gap|-6)', np.column_stack([np.ones(len(x)), np.maximum(0, x - 6)])),
                ('quadratic |gap|', np.column_stack([np.ones(len(x)), x, x ** 2]))):
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    print(f'{name:24s} R2 on garbage minutes: {1 - ((y - X @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum():.4f}')
G.to_csv(os.path.join(HERE, '..', 'raw', 'garbage_time_games.csv'), index=False)
