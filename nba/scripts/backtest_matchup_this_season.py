#!/usr/bin/env python3
"""
What the live shot-matchup term (docs/matchup-live.md) would have done to this season's settled 3PM and assist leans. DESCRIPTIVE, no verdict, small sample.
Point in time: for a game on day D the matchup data is the data/diet_defense.json committed on origin/main before 12:00 UTC on D (through the night before).
Approximation: the live term multiplies the base projection (before the other v2 terms); here it multiplies the lean's logged mu, so it is close, not exact.

  python3 nba/scripts/backtest_matchup_this_season.py [first_day] [last_day]       reads origin/nba-data leans/ and origin/main history
"""
import json, os, subprocess, sys, statistics as st
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pricing as PX

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
git = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout
MT = json.load(open(os.path.join(HERE, '..', 'data', 'matchup_terms.json')))


def dd_before(day):
    sha = git('log', 'origin/main', '--format=%H', f'--until={day}T12:00:00Z', '-1', '--', 'nba/data/diet_defense.json').strip()
    return (json.loads(git('show', f'{sha}:nba/data/diet_defense.json')), sha[:8]) if sha else (None, None)


def main():
    days = [d for d in sorted(x.split('/')[-1][:-5] for x in git('ls-tree', '--name-only', 'origin/nba-data', 'leans/').split() if x.endswith('.json')) if d >= (sys.argv[1] if len(sys.argv) > 1 else '2026-10-20') and d <= (sys.argv[2] if len(sys.argv) > 2 else '9999')]
    pr = PX.Pricer.__new__(PX.Pricer)
    pr.MT, pr.example = MT, False
    rows, miss_team = [], set()
    for d in days:
        pr.DDF, sha = dd_before(d)
        if not pr.DDF:
            continue
        lj = json.loads(git('show', f'origin/nba-data:leans/{d}.json'))
        C = lj['cols']
        for raw in lj['rows']:
            r = dict(zip(C, raw))
            if r['clock'] != 'f' or r['stat'] not in ('3pm', 'ast') or r['res'] not in ('W', 'L', 'P') or r['held']:
                continue
            mu_, _t = lj['games'].get(str(r['game'])) or (None, None)
            if not mu_:
                continue
            away, home = [x.strip() for x in mu_.split('@')]
            opp = away if r['team'] == home else home if r['team'] == away else None
            if opp not in pr.DDF['teams']:
                miss_team.add(opp)
                continue
            idx = pr.matchup_idx(r['pid'], opp, r['stat'])
            lo, hi = MT['clip']
            mult = 1.0 if idx is None else min(hi, max(lo, 1 + MT['stats'][r['stat']]['beta'] * idx))
            rows.append({'day': d, 'stat': r['stat'], 'player': r['player'], 'team': r['team'], 'opp': opp, 'game': r['game'], 'line': r['line'], 'mu': r['mu'], 'y': r['y'],
                         'idx': idx, 'mult': mult, 'mu2': r['mu'] * mult, 'side': r['side'], 'dd': sha})
    print('days', days, '| rows', len(rows), '| opponents not in the matchup file:', sorted(x for x in miss_team if x))
    for s in ('3pm', 'ast'):
        R = [r for r in rows if r['stat'] == s]
        W = [r for r in R if r['idx'] is not None]
        if not W:
            continue
        mae0, mae1 = st.mean(abs(r['y'] - r['mu']) for r in W), st.mean(abs(r['y'] - r['mu2']) for r in W)
        mv = sorted(r['mult'] for r in W)
        print(f"\n{s}: {len(R)} leans, {len(W)} with a matchup index, {len({r['game'] for r in W})} games")
        print(f"  multiplier  min {mv[0]:.3f}  p10 {mv[len(mv)//10]:.3f}  median {mv[len(mv)//2]:.3f}  p90 {mv[-len(mv)//10]:.3f}  max {mv[-1]:.3f}")
        print(f"  MAE old {mae0:.4f}  new {mae1:.4f}  (gain {mae0 - mae1:+.4f}); mean bias old {st.mean(r['mu'] - r['y'] for r in W):+.4f} new {st.mean(r['mu2'] - r['y'] for r in W):+.4f}")
        W.sort(key=lambda r: r['idx']); n = len(W); t = n // 3
        for name, part in (('softest third', W[2 * t:]), ('middle', W[t:2 * t]), ('toughest third', W[:t])):
            print(f"  {name:15s} n={len(part):4d}  mean index {st.mean(r['idx'] for r in part):+.3f}  actual minus model mu {st.mean(r['y'] - r['mu'] for r in part):+.3f}  ({100 * st.mean((r['y'] - r['mu']) / max(r['mu'], .5) for r in part):+.1f}%)")
        flips = [r for r in R if r['line'] is not None and r['y'] != r['line'] and ((r['mu'] > r['line']) != (r['mu2'] > r['line']))]
        newwin = sum(1 for r in flips if (r['mu2'] > r['line']) == (r['y'] > r['line']))
        print(f"  lean side flips because of the term: {len(flips)} of {len(R)};  the NEW side won {newwin} of {len(flips)}")
    big = sorted([r for r in rows if r['idx'] is not None], key=lambda r: -abs(r['mult'] - 1))[:8]
    print('\nlargest movers:')
    for r in big:
        print(f"  {r['day']} {r['player']:22s} {r['stat']:4s} vs {r['opp']:5s} index {r['idx']:+.3f}  mu {r['mu']:.2f} -> {r['mu2']:.2f}  line {r['line']}  actual {r['y']:.0f}")
    json.dump(rows, open(os.environ.get('BT_OUT', '/tmp/matchup_bt_rows.json'), 'w'))


if __name__ == '__main__':
    main()
