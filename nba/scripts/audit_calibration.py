#!/usr/bin/env python3
"""Calibration of prop model v2 and the consensus engine against the market, 2025-26 test season (models fit on 2024-25).
Rows: ESPN pre-tip main lines (model vs no-vig price) and Kalshi ladder rungs (model, leave-one-out consensus, price).
Writes a CSV for the calibration-check skill (.claude/skills/calibration-check/scripts/calibration_report.py). ~1 min.
  python3 nba/scripts/audit_calibration.py --out rows.csv"""
import os, sys, json, csv
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nba_common as C
import build_prop_model_v2 as V2, build_prop_model_v3 as A, build_prop_model_v3_full as F, consensus as CE
from build_prop_model import MARKETS, apply_cal
from collections import defaultdict
out = sys.argv[sys.argv.index('--out') + 1]
I = F.inputs(); recs = F.walk_v2(I); by = A.by_rec(recs); espn, kal = A.load_markets(by)
v2 = json.load(open(V2.OUT_JSON)); V, stk, cal = v2['variance']['v2'], v2['stacker'], v2['calibration']['v2']
extra = lambda r, m: (V2.minrate(r, m) * r['sdm']) ** 2
model = lambda r, m, L: apply_cal(cal[m], V2.p_over(m, V2.mu2(r, stk)[m], L, V, extra(r, m)))
key = lambda r: (r['gid'], r['aid'])
rows = []
for m in MARKETS:
    for x in espn.get(('2026', m, 'close'), []):
        rows.append(dict(src='espn', stat=m, y=int(x['over']), model=model(x['r'], m, x['L']), cons='', price=x['pk'], line=x['L'], gid=x['gid']))
ladders = {m: defaultdict(list) for m in ('pts', 'reb', 'ast', '3pm')}
for m in ladders:
    for x in kal.get(m, []): ladders[m][key(x['r'])].append(x)
    for lad in ladders[m].values():
        if len(lad) < 4: continue
        r0 = lad[0]['r']; ex = extra(r0, m)
        for i, x in enumerate(lad):
            mu = CE.implied_mean(m, [(z['L'], z['k'], 1.0) for j, z in enumerate(lad) if j != i], V, ex)
            rows.append(dict(src='kalshi', stat=m, y=int(x['yes']), model=model(r0, m, x['L']), cons=CE.p_over(m, mu, x['L'], V, ex), price=x['k'], line=x['L'], gid=x['gid']))
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), 'rows ->', out)
