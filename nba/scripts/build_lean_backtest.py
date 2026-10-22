#!/usr/bin/env python3
"""
Lean backtest series (docs/lean-tracking.md, "Data and history"): the same lean measures on the 2025-26 ESPN pre-tip main lines, from
data/lean_rows_nba.json (model fit on 2024-25; written by lean_search_nba.py). DESCRIPTIVE ONLY and shown apart from the forward record:
this season was already used by the lean diagnostic and the lean search, so it is not a clean test. It has the model's projection and the line,
not the calibrated P or the sd, so gap bins here are terciles of |proj - line| inside each stat (not the forward record's sd bins).

Lean = over when proj > line. y = 1 when the stat went over. Every line is a half point, so no pushes. Market side = over when pk > .5 (pk = the
price's no-vig P(over)); ties dropped. Intervals: 95% bootstrap resampling GAMES (props from one game are correlated), 2000 draws, fixed seed.

  python3 nba/scripts/build_lean_backtest.py     ->  nba/data/lean_backtest.json
"""
import json, os, random
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')


def cluster_ci(rows, stat, B=2000, seed=7):
    """95% bootstrap interval of mean(stat(row)) resampling games."""
    by = defaultdict(list)
    for r in rows:
        by[r['gid']].append(stat(r))
    gs = list(by.values())
    if len(gs) < 5:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(B):
        s = n = 0
        for _ in gs:
            g = gs[rng.randrange(len(gs))]
            s += sum(g); n += len(g)
        means.append(s / n)
    means.sort()
    return [round(means[int(B * .025)], 4), round(means[int(B * .975)], 4)]


def block(rows):
    if not rows:
        return None
    lean = lambda r: int((r['proj'] > r['L']) == (r['y'] == 1))
    under = lambda r: int(r['y'] == 0)
    mk = [r for r in rows if r['pk'] != .5]
    mside = lambda r: int((r['pk'] > .5) == (r['y'] == 1))
    n = len(rows)
    return {'n': n, 'games': len({r['gid'] for r in rows}),
            'lean': round(sum(map(lean, rows)) / n, 4), 'lean_ci': cluster_ci(rows, lean),
            'always_under': round(sum(map(under, rows)) / n, 4), 'always_over': round(1 - sum(map(under, rows)) / n, 4),
            'market_side': round(sum(map(mside, mk)) / len(mk), 4) if mk else None,
            'lean_minus_under': round(sum(lean(r) - under(r) for r in rows) / n, 4),
            'lean_minus_under_ci': cluster_ci(rows, lambda r: lean(r) - under(r)),
            'pct_over_leans': round(sum(r['proj'] > r['L'] for r in rows) / n, 4)}


def main():
    rows = json.load(open(os.path.join(DATA, 'lean_rows_nba.json')))
    rows = [r for r in rows if r['proj'] != r['L']]
    out = {'about': 'descriptive backtest series, see nba/scripts/build_lean_backtest.py', 'overall': block(rows), 'by_stat': {}, 'by_side': {}, 'by_agreement': {}, 'by_gap_tercile': {}}
    for s in sorted({r['m'] for r in rows}):
        out['by_stat'][s] = block([r for r in rows if r['m'] == s])
    out['by_side']['over_leans'] = block([r for r in rows if r['proj'] > r['L']])
    out['by_side']['under_leans'] = block([r for r in rows if r['proj'] < r['L']])
    agree = [r for r in rows if r['pk'] != .5 and (r['proj'] > r['L']) == (r['pk'] > .5)]
    dis = [r for r in rows if r['pk'] != .5 and (r['proj'] > r['L']) != (r['pk'] > .5)]
    out['by_agreement'] = {'agrees_with_market': block(agree), 'disagrees_with_market': block(dis)}
    for t in range(3):
        sel = []
        for s in {r['m'] for r in rows}:
            rs = sorted((r for r in rows if r['m'] == s), key=lambda r: abs(r['proj'] - r['L']))
            k = len(rs)
            sel += rs[k * t // 3: k * (t + 1) // 3]
        out['by_gap_tercile'][['small', 'middle', 'large'][t]] = block(sel)
    json.dump(out, open(os.path.join(DATA, 'lean_backtest.json'), 'w'), indent=1)
    o = out['overall']
    print(f"overall n={o['n']} games={o['games']} lean {o['lean']} {o['lean_ci']}  always-under {o['always_under']}  market side {o['market_side']}  lean-under {o['lean_minus_under']} {o['lean_minus_under_ci']}")
    for k, v in list(out['by_stat'].items()) + list(out['by_side'].items()) + list(out['by_agreement'].items()) + list(out['by_gap_tercile'].items()):
        print(f"  {k:24s} n={v['n']:5d} lean {v['lean']} under {v['always_under']} mkt {v['market_side']} lean-under {v['lean_minus_under']} {v['lean_minus_under_ci']}")


if __name__ == '__main__':
    main()
