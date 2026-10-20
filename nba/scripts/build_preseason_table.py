#!/usr/bin/env python3
"""
Stage 1 of docs/preseason-signals-test.md: rebuild every preseason game from the ESPN plays and write
raw/preseason_players.csv, raw/preseason_teams.csv and the validation report (printed).

  nba/.venv/bin/python nba/scripts/build_preseason_table.py
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preseason_lib import process_game

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw')

P, T, C = [], [], []
for f in sorted(glob.glob(os.path.join(RAW, 'preseason', '*', '*.json'))):
    g = json.load(open(f))
    p, t, c = process_game(g)
    P += p; T += t; C.append(c)
P, T, C = pd.DataFrame(P), pd.DataFrame(T), pd.DataFrame(C)
P.to_csv(os.path.join(RAW, 'preseason_players.csv'), index=False)
T.to_csv(os.path.join(RAW, 'preseason_teams.csv'), index=False)

print('games', len(C), 'by season', C.season.value_counts().sort_index().to_dict())
print('starters flagged 5 per team:', int(C.starters_ok.sum()), '/', len(C))
print('sub anomalies per game: mean %.2f, games with >3: %d' % (C.anomalies.mean(), int((C.anomalies > 3).sum())))
pl = P[(P.box_min > 0)]
err = (pl.g_min - pl.box_min).abs()
print('player-games with box minutes', len(pl))
print('median |rebuilt - box| minutes %.3f; within 2 min %.1f%%; within 0.5 min %.1f%%' % (
    err.median(), 100 * (err <= 2).mean(), 100 * (err <= 0.5).mean()))
for k, bk in (('pts', 'box_pts'), ('reb', 'box_reb'), ('ast', 'box_ast'), ('tov', 'box_tov'), ('fga', 'box_fga'),
              ('fg3a', 'box_fg3a'), ('fta', 'box_fta'), ('stl', 'box_stl'), ('blk', 'box_blk')):
    if bk not in pl:
        continue
    d = pl[pl[bk].notna()]
    print('  %-5s exact match %.1f%%  mean diff %+.3f  total pbp %d vs box %d' % (
        k, 100 * (d['g_' + k] == d[bk]).mean(), (d['g_' + k] - d[bk]).mean(), d['g_' + k].sum(), d[bk].sum()))
bad = C[(C.mae > 1.0) | (~C.starters_ok)]
print('games failing (mae > 1 min or starters != 5):', len(bad), 'of', len(C))
print(bad[['game_id', 'season', 'starters_ok', 'anomalies', 'mae', 'max_err']].head(15).to_string())
