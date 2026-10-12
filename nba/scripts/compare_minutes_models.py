#!/usr/bin/env python3
"""
Minutes v2 vs v3 vs GBM on the same settled player-games, from the recorder's logged 'minutes' source (nba-data branch).
Only players who played are scored (as the backtest and ledger.minutes_record do); same-player sets for every comparison.
Reads a checkout of the nba-data branch:  git fetch origin nba-data && git worktree add DIR origin/nba-data
  python3 nba/scripts/compare_minutes_models.py DIR [--since 2026-10-11] [--season]   (--season: regular season instead of preseason)
"""
import os, sys, time, statistics as S
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import ledger as L


def rows(root, since, regular):
    pre = L.preseason_games(root)
    now, out = time.time(), []
    for k, x in L.load_src(root, 'minutes', since).items():
        m = x['meta']
        ser = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
        if not ser or now < m['tip'] + L.SETTLE_AFTER_S or ((str(m['game']) in pre) == regular):
            continue
        bx = L.box(root, m['game'])
        if bx is None:
            continue
        st = bx.get(int(m['pid']))
        if not st or not st.get('minutes'):
            continue                       # did not play: not scored
        v = ser[-1]
        out.append({'day': L.tip_day(m['tip']), 'v2': v[0], 'v3': v[2] if len(v) > 2 else None,
                    'gbm': v[4] if len(v) > 4 else None, 'act': st['minutes'], 'avg': v[1]})
    return out


def line(name, rs, f):
    q = [r for r in rs if r[f] is not None]
    if not q:
        return f'{name:5} n=0'
    e = [r[f] - r['act'] for r in q]
    return f"{name:5} n={len(q):4} MAE {S.mean(abs(x) for x in e):5.2f}  bias {S.mean(e):+5.2f}  miss8 {sum(abs(x) >= 8 for x in e):4}"


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    since = (sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else '2026-09-30')
    regular = '--season' in sys.argv
    R = rows(a[0], since, regular)
    print(f"{'regular season' if regular else 'preseason'}, {len(R)} played player-games since {since}")
    print('\nAll played (each model on the players it has):')
    for n, f in (('avg', 'avg'), ('v2', 'v2'), ('v3', 'v3'), ('gbm', 'gbm')):
        print(' ', line(n, R, f))
    both = [r for r in R if r['gbm'] is not None and r['v3'] is not None]
    print(f'\nSame players for all three (n={len(both)}):')
    for n, f in (('avg', 'avg'), ('v2', 'v2'), ('v3', 'v3'), ('gbm', 'gbm')):
        print(' ', line(n, both, f))
    print('\nBy projected-minutes band (v2), same players:')
    for lo, hi in ((0, 12), (12, 24), (24, 34), (34, 49)):
        q = [r for r in both if lo <= r['v2'] < hi]
        if q:
            print(f'  v2 {lo}-{hi}: n={len(q)}  ' + ' | '.join(line(n, q, f).split('  ', 1)[1] and f"{n} MAE {S.mean(abs(r[f]-r['act']) for r in q):.2f}" for n, f in (('v2', 'v2'), ('v3', 'v3'), ('gbm', 'gbm'))))
    d = defaultdict(list)
    for r in both:
        d[r['day']].append(r)
    print('\nBy day (MAE v2 / v3 / gbm):')
    for day, q in sorted(d.items()):
        print(f"  {day} n={len(q):3}  " + ' / '.join(f"{S.mean(abs(r[f]-r['act']) for r in q):.2f}" for f in ('v2', 'v3', 'gbm')))


if __name__ == '__main__':
    main()
