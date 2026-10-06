#!/usr/bin/env python3
"""NBA lean diagnostic (port of the NFL one): does the v2 projection LEAN the right side of the real line?
For each market, on the 2025-26 ESPN pre-tip main lines (stacker fit on 2024-25, nothing from the test season):
  bias        mean(proj - actual) vs mean(line - actual)      a biased projection leans one way too often
  slope       OLS of (actual - line) on (proj - line)         1 = model right, 0 = echoes the market, <0 = backwards
  lean hit    how often the side the model prefers wins, overall and by size of the disagreement
Also scores the model's P(side) against the book's no-vig P(side) ("edge vs price"), not just hit rate.
  python3 nba/scripts/diag_nba_lean.py
"""
import json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model_v2 as V2
import build_prop_model_v3 as A
import build_prop_model_v3_full as F
from build_prop_model import MARKETS

I = F.inputs()
recs = F.walk_v2(I)
fit = [r for r in recs if r['season'] == V2.FIT]
stk = V2.fit_stacker(fit)
espn, _ = A.load_markets(A.by_rec(recs))
print('espn keys', sorted({k for k in espn})[:8], flush=True)
TEST_KEY = str(V2.TEST)

def ols(x, y):
    mx, my = st.mean(x), st.mean(y); sxx = sum((a - mx) ** 2 for a in x)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx if sxx else 0.0

out = {}
print(f"{'market':6s} {'n':>5s} {'MAE proj':>9s} {'MAE line':>9s} {'bias proj':>10s} {'bias line':>10s} {'slope':>6s} {'lean hit':>9s} {'edge vs price':>14s}", flush=True)
for m in MARKETS:
    rows = []
    for x in espn.get((TEST_KEY, m, 'close'), []):
        r, L = x['r'], x['L']
        proj = V2.mu2(r, stk)[m]; act = A.yval(r, m)
        if abs(proj - L) < 1e-9: continue
        rows.append({'proj': proj, 'L': L, 'act': act, 'pk': x['pk'], 'over': x['over']})
    if len(rows) < 100: continue
    n = len(rows)
    side_over = [r['proj'] > r['L'] for r in rows]
    hit = [(o == r['over']) for o, r in zip(side_over, rows)]
    mq = [r['pk'] if o else 1 - r['pk'] for o, r in zip(side_over, rows)]
    sl = ols([r['proj'] - r['L'] for r in rows], [r['act'] - r['L'] for r in rows])
    o = {'n': n, 'mae_proj': st.mean(abs(r['proj'] - r['act']) for r in rows), 'mae_line': st.mean(abs(r['L'] - r['act']) for r in rows),
         'bias_proj': st.mean(r['proj'] - r['act'] for r in rows), 'bias_line': st.mean(r['L'] - r['act'] for r in rows),
         'slope': sl, 'lean_hit': st.mean(hit), 'edge_pts': (st.mean(hit) - st.mean(mq)) * 100,
         'over_leans': sum(side_over), 'over_hit': st.mean(h for h, s in zip(hit, side_over) if s) if any(side_over) else None,
         'under_hit': st.mean(h for h, s in zip(hit, side_over) if not s) if not all(side_over) else None}
    gaps = sorted(abs(r['proj'] - r['L']) / max(r['L'], 0.5) for r in rows)
    cuts = [gaps[int(n * q)] for q in (0, .2, .4, .6, .8)] + [gaps[-1] + 1]
    b = []
    for lo, hi in zip(cuts, cuts[1:]):
        idx = [i for i, r in enumerate(rows) if lo <= abs(r['proj'] - r['L']) / max(r['L'], 0.5) < hi]
        if idx: b.append({'gap_lo': round(lo, 3), 'n': len(idx), 'hit': round(st.mean(hit[i] for i in idx), 3), 'edge_pts': round((st.mean(hit[i] for i in idx) - st.mean(mq[i] for i in idx)) * 100, 1)})
    o['by_gap'] = b
    out[m] = o
    print(f"{m:6s} {n:5d} {o['mae_proj']:9.3f} {o['mae_line']:9.3f} {o['bias_proj']:+10.3f} {o['bias_line']:+10.3f} {o['slope']:+6.2f} {o['lean_hit']*100:8.1f}% {o['edge_pts']:+13.1f}", flush=True)
print()
for m, o in out.items():
    print(m, 'over leans', o['over_leans'], 'of', o['n'], '| over hit', None if o['over_hit'] is None else round(o['over_hit'] * 100, 1), 'under hit', None if o['under_hit'] is None else round(o['under_hit'] * 100, 1))
    print('   by gap (quintiles, small->big):', ' | '.join(f"{b['hit']*100:.1f}% ({b['edge_pts']:+.1f}pt, n={b['n']})" for b in o['by_gap']))
json.dump(out, open(os.path.join(C.HERE, '..', 'data', 'diag_nba_lean.json'), 'w'), indent=1)
