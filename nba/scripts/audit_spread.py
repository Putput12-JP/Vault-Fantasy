#!/usr/bin/env python3
"""Sensitivity of the Kalshi consensus GO cells to execution cost. The backtest fills at the 30-minute VWAP; a real taker
pays half the bid-ask spread on top (YES at the ask, NO at 1 - bid). Historical Kalshi data here is trades only (no book), so
the spread cannot be measured back then; this finds how large a half-spread the edge can absorb. Adds h to the fee used for
both the 3% edge test and the bet cost. Writes only to --out. ~4 min.
  python3 nba/scripts/audit_spread.py --out /path/to/dir"""
import os, sys, io, json, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_prop_model_v3_full as F, build_consensus as BC
out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else '.'
os.makedirs(out, exist_ok=True)
_walk, _fee = F.walk_v2, BC.kalshi_fee
_cache = {}
F.walk_v2 = lambda I: _cache.setdefault('w', _walk(I))
res = {}
for h in (0.0, 0.01, 0.02, 0.03):
    BC.kalshi_fee = lambda p, h=h: _fee(p) + h
    BC.OUT_JSON = os.path.join(out, f'spread_{h}.json'); BC.OUT_MD = os.path.join(out, f'spread_{h}.md')
    with contextlib.redirect_stdout(io.StringIO()): BC.main()
    res[h] = json.load(open(BC.OUT_JSON)); print('h', h, 'done', flush=True)
print('\nconsensus + model, Kalshi ladder leave-one-out, second half, 3%+ edge after fees AND an extra half-spread h')
for h, d in res.items():
    for m in ('pts', '3pm', 'reb', 'ast'):
        for sd in ('NO', 'YES'):
            b = ((d['tests']['kalshi_ladder'].get(m, {}).get('bets') or {}).get('consensus + model') or {}).get(sd)
            if b and b.get('n') and b['n'] >= 20: print(f"h={h:.2f} {m:4s} {sd:3s} n={b['n']:5d} games={b['games']:4d} roi={b['roi']:+.3f} z={b['z']}")
