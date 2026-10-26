#!/usr/bin/env python3
"""
Fits the rotation-aware minutes model (C3) ONCE and writes data/rotation_minutes_model.json. Rules: docs/rotation-minutes-shadow.md.
Fit: the walk's 2022-23, 2023-24 and 2024-25 (walk seasons 2023 to 2025), P(plays) on 2024-25 only, with test_rotation_minutes.py's own fitting code and features (pool-size features included).
2025-26 is NOT in the fit. Never refit without a new registration.   python3 nba/scripts/build_rotation_minutes_model.py [--cache]   (the walk takes about 6 minutes without the cache)
"""
import json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test_rotation_minutes as T

OUT = os.path.join(HERE, '..', 'data', 'rotation_minutes_model.json')


def main():
    if '--cache' not in sys.argv:
        sys.argv.append('--cache') if os.path.exists(T.CACHE) else None
    data = T.walk_data()
    pool = data['pool']
    T.add_history(pool)
    pool = [r for r in pool if 'rank' in r and r['pm'] >= 0]
    train = [r for r in pool if r['season'] in T.FIT_SEASONS]
    plays = [r for r in train if r['season'] in T.PLAYS_SEASONS]
    sets, _ = T.fit_models(train, plays, T.xs_common3, T.xs_min3, with_b=False)
    out = {'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'doc': 'nba/docs/rotation-minutes-shadow.md',
           'fit': {'walk_seasons': list(T.FIT_SEASONS), 'plays_seasons': list(T.PLAYS_SEASONS), 'rows': len(train), 'plays_rows': len(plays)},
           'T': round(T.team_total(train), 4), 'sd_margin': T.SD_MARGIN, 'rot_cut': T.ROT_CUT,
           'states': [{'name': n, 'wp': [round(x, 8) for x in s['wp']], 'wr': [round(x, 8) for x in s['wr']], 'wm': [round(x, 8) for x in s['wm']], 'g': round(s['g'], 6)}
                      for n, s in zip(T.STATES, sets)]}
    json.dump(out, open(OUT, 'w'), indent=1)
    print('wrote', OUT, '| T', out['T'], '| rows', len(train), '| plays rows', len(plays))


if __name__ == '__main__':
    main()
