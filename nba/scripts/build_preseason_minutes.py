#!/usr/bin/env python3
"""
data/preseason_minutes.json for the Minutes Lab (docs/minutes-lab-preseason.md).

Per player: preseason games, first-half mpg, box mpg, starts, preseason team (abbreviation as depth_charts.json uses).
Plus the fitted early-season minutes model and the decay, so build_player_projections.py has one input.
Preseason is over, so this is built once per season from raw/preseason (needs fetch_preseason.py and
build_preseason_table.py); it does not change during the regular season.

  nba/.venv/bin/python nba/scripts/build_preseason_minutes.py [SEASON]     # default 2027 = the 2026-27 preseason
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_preseason_signals as B

DECAY = os.path.join(B.DATA, 'preseason_decay.json')
ROOKIE = os.path.join(B.DATA, 'rookie_minutes.json')        # build_rookie_minutes.py: fit, bucket means, schedule (docs/rookie-minutes-test.md)


def main():
    live = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    d, pre, bad = B.build_table()
    dec = json.load(open(DECAY))
    rk = json.load(open(ROOKIE))
    assert rk['pass'], 'the rookie model did not pass its pre-registered rule: do not ship it'
    tr = d[(d.L_min >= 400) & (d.box_min >= 40) & (d.E_gp >= 10)]
    b = B.ols(tr[['L_mpg', 'mpg_1h']].values, tr.E_mpg.values)
    bL = B.ols(tr[['L_mpg']].values, tr.E_mpg.values)
    # hoopR team ids -> the abbreviations depth_charts.json and the Lab use
    ab = pd.read_csv(os.path.join(B.RAW, 'hoopr', f'player_box_{live - 1}.csv'), low_memory=False,
                     usecols=['team_id', 'team_abbreviation']).drop_duplicates('team_id')
    abbr = {str(int(r.team_id)): r.team_abbreviation for r in ab.itertuples()}
    ps = pre[pre.season == live]
    P, _, _ = B.load_pre()
    P = P[(P.season == live) & (P.box_min > 0)]
    team = P.groupby('pid').team.agg(lambda s: s.mode().iloc[0])
    players = {}
    for r in ps.itertuples():
        players[r.pid] = {'name': r.name, 'team': abbr.get(str(team.get(r.pid)), None), 'n': int(r.n),
                          'h1_mpg': round(float(r.mpg_1h), 2), 'mpg': round(float(r.mpg_total), 2),
                          'h1_min': round(float(r.h1_min), 1), 'box_min': round(float(r.box_min), 1), 'starts': int(r.starts)}
    out = {'season': live, 'generated': pd.Timestamp.now().isoformat()[:16],
           'model': {'start_pre': [float(x) for x in b], 'start_last': [float(x) for x in bL],
                     'fit_rows': int(len(tr)), 'feats': ['last_mpg', 'h1_mpg']},
           'decay': {'K': dec['K_pre'], 'taper_from': 5, 'retire_at': dec['retire']['N_ret_games_played'],
                     'absence_games': 5},
           'rookie': {'model': rk['fit_R1'], 'feats': ['bucket_mean', 'h1_mpg'], 'bucket_means': rk['bucket_means'],
                      'decay': {'K': rk['K_rookie'], 'taper_from': rk['taper_from'], 'retire_at': rk['N_ret_materiality_0.10'],
                                'absence_games': 5}, 'fit_rows': rk['n']},
           'eligibility': {'min_last_minutes': 400, 'min_preseason_minutes': 40},
           'games_excluded_team_games': int(len(bad)), 'players': players}
    with open(os.path.join(B.DATA, 'preseason_minutes.json'), 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    print(live, len(players), 'players; model', out['model'], 'decay', out['decay'])


if __name__ == '__main__':
    main()
