#!/usr/bin/env python3
"""Part A of docs/minutes-autopsy-and-implied.md (rule committed before this ran). Needs lightgbm; reads /tmp/rotation_pool.json.
  python3 nba/scripts/test_minutes_autopsy.py"""
import json, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test_minutes_bakeoff as B

CAUSES = ['blowout', 'early exit', 'rotation change', 'teammate out', 'rest / schedule', 'unexplained']

def cause(r, rank):
    gp, a, fm = r['GP'], r['min'], abs(r['fm'])
    if fm >= 20: return 'blowout'
    if a < 0.4 * gp: return 'early exit'
    if (rank <= 8 and a <= gp - 8) or (rank > 8 and a >= gp + 8): return 'rotation change'
    if r['nout'] >= 1: return 'teammate out'
    if r['b2b'] == 1: return 'rest / schedule'
    return 'unexplained'

def main():
    te, groups, recs, model, _ = B.compute()
    played, miss, err = Counter(), Counter(), defaultdict(list)
    for rs in groups.values():
        order = sorted(rs, key=lambda r: -r['m'])
        rk = {id(r): i + 1 for i, r in enumerate(order)}
        for r in rs:
            if not (r['played'] and r['min'] > 0) or 'GP' not in r: continue
            c = cause(r, rk[id(r)]); played[c] += 1
            if abs(r['GP'] - r['min']) >= 8: miss[c] += 1; err[c].append(r['GP'] - r['min'])
    P, M = sum(played.values()), sum(miss.values())
    out = {'played': P, 'miss8': M, 'rows': {}}
    for c in CAUSES:
        sh_m, sh_p = miss[c] / M, played[c] / P
        out['rows'][c] = {'miss8': miss[c], 'share_miss8': sh_m, 'share_all': sh_p, 'lift': sh_m / sh_p if sh_p else None,
                          'mean_err': sum(err[c]) / len(err[c]) if err[c] else None, 'qualifies': sh_m >= .25 and sh_p > 0 and sh_m / sh_p >= 1.5}
    # context only (added after the registered result was seen): direction of every miss8, by cause
    d = defaultdict(lambda: [0, 0])
    for rs in groups.values():
        order = sorted(rs, key=lambda r: -r['m']); rk = {id(r): i + 1 for i, r in enumerate(order)}
        for r in rs:
            if not (r['played'] and r['min'] > 0) or 'GP' not in r or abs(r['GP'] - r['min']) < 8: continue
            d[cause(r, rk[id(r)])][0 if r['GP'] > r['min'] else 1] += 1
            d['top8' if rk[id(r)] <= 8 else 'outside top8'][0 if r['GP'] > r['min'] else 1] += 1
    out['direction_over_under'] = {k: {'gp_too_high': v[0], 'gp_too_low': v[1]} for k, v in d.items()}
    json.dump(out, open(os.path.join(HERE, '..', 'data', 'minutes_autopsy.json'), 'w'), indent=1)
    print(P, M); print(out['direction_over_under'])
    for c in CAUSES: print(c, out['rows'][c])
main()
