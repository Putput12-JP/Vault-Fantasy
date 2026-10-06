#!/usr/bin/env python3
"""NBA edge significance (follow-up to diag_nba_lean.py). On the 2025-26 ESPN pre-tip main lines, per market:
  - ROI at the posted prices of betting the model's side, split OVER vs UNDER, with a bootstrap 95% interval
  - the same for ALWAYS-UNDER and ALWAYS-OVER (does the book's line tilt, without any model?)
  - hit rate minus the no-vig implied probability ("edge vs price") with a bootstrap 95% interval
  - the same restricted to the model's biggest-disagreement quintile
  python3 nba/scripts/diag_nba_edge.py [--rows rows.json]    (first run dumps rows; later runs reuse them)
"""
import json, os, random, statistics as st, sys
sys.path.insert(0, os.path.dirname(__file__))
ROWS = sys.argv[sys.argv.index('--rows') + 1] if '--rows' in sys.argv else os.path.join(os.path.dirname(__file__), '..', 'data', 'diag_nba_rows.json')
from build_prop_model import MARKETS, am_payout, am_prob

if not os.path.exists(ROWS):
    import nba_common as C
    import build_prop_model_v2 as V2
    import build_prop_model_v3 as A
    import build_prop_model_v3_full as F
    I = F.inputs(); recs = F.walk_v2(I)
    stk = V2.fit_stacker([r for r in recs if r['season'] == V2.FIT])
    espn, _ = A.load_markets(A.by_rec(recs))
    rows = []
    for m in MARKETS:
        for x in espn.get((str(V2.TEST), m, 'close'), []):
            r, L = x['r'], x['L']; proj = V2.mu2(r, stk)[m]
            if abs(proj - L) < 1e-9: continue
            rows.append({'m': m, 'proj': proj, 'L': L, 'pk': x['pk'], 'over': bool(x['over']), 'opx': x['over_px'], 'upx': x['under_px'], 'gid': x['gid']})
    json.dump(rows, open(ROWS, 'w'))
rows = json.load(open(ROWS))
random.seed(7)

def bet(r, side_over):
    """(win?, profit per $1, no-vig implied prob of that side)"""
    win = (side_over == r['over']); px = r['opx'] if side_over else r['upx']
    return win, (am_payout(px) if win else -1.0), (r['pk'] if side_over else 1 - r['pk'])

def summarize(bets, B=2000):
    n = len(bets)
    if n < 30: return None
    hit = st.mean(b[0] for b in bets); roi = st.mean(b[1] for b in bets); imp = st.mean(b[2] for b in bets)
    rs = []
    for _ in range(B):
        s = [bets[random.randrange(n)] for _ in range(n)]
        rs.append((st.mean(b[1] for b in s), st.mean(b[0] for b in s) - st.mean(b[2] for b in s)))
    rs_roi = sorted(a for a, _ in rs); rs_edge = sorted(b for _, b in rs)
    lo, hi = int(B * 0.025), int(B * 0.975)
    return {'n': n, 'hit': hit, 'edge': (hit - imp) * 100, 'edge_ci': (rs_edge[lo] * 100, rs_edge[hi] * 100),
            'roi': roi * 100, 'roi_ci': (rs_roi[lo] * 100, rs_roi[hi] * 100)}

def line(name, s):
    if not s: return f"  {name:22s} too few"
    sig = '  <- CI excludes 0' if s['roi_ci'][0] > 0 else ''
    return (f"  {name:22s} n={s['n']:4d} hit {s['hit']*100:4.1f}% | edge {s['edge']:+5.1f} [{s['edge_ci'][0]:+5.1f},{s['edge_ci'][1]:+5.1f}] | "
            f"ROI {s['roi']:+5.1f}% [{s['roi_ci'][0]:+5.1f},{s['roi_ci'][1]:+5.1f}]{sig}")

out = {}
for m in MARKETS:
    R = [r for r in rows if r['m'] == m and r['opx'] and r['upx']]
    if len(R) < 100: continue
    gaps = sorted(abs(r['proj'] - r['L']) / max(r['L'], 0.5) for r in R); cut = gaps[int(len(R) * 0.8)]
    model_side = lambda r: r['proj'] > r['L']
    sets = {'model side (all)': [bet(r, model_side(r)) for r in R],
            'model OVER': [bet(r, True) for r in R if model_side(r)],
            'model UNDER': [bet(r, False) for r in R if not model_side(r)],
            'model, top-gap 20%': [bet(r, model_side(r)) for r in R if abs(r['proj'] - r['L']) / max(r['L'], 0.5) >= cut],
            'model UNDER, top-gap 20%': [bet(r, False) for r in R if not model_side(r) and abs(r['proj'] - r['L']) / max(r['L'], 0.5) >= cut],
            'always UNDER (no model)': [bet(r, False) for r in R],
            'always OVER (no model)': [bet(r, True) for r in R]}
    print(f"\n{m.upper()}  ({len(R)} lines)")
    out[m] = {}
    for k, v in sets.items():
        s = summarize(v); out[m][k] = s; print(line(k, s))
json.dump(out, open(os.path.join(os.path.dirname(__file__), '..', 'data', 'diag_nba_edge.json'), 'w'), indent=1)
