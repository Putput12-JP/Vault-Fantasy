#!/usr/bin/env python3
"""Audit of the consensus engine's Kalshi inputs: are the GO cells an artefact of thin, averaged prices?
Re-runs build_consensus.main with (a) a minimum 30-minute volume per rung and (b) the last trade instead of the
30-minute VWAP as the price. Writes nothing under nba/data or nba/docs (scratch dir via --out). ~5 min.
  python3 nba/scripts/audit_consensus.py --out /path/to/dir"""
import os, sys, io, json, csv, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nba_common as C
import build_prop_model_v3 as A, build_prop_model_v3_full as F
import build_consensus as BC
out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else '.'
os.makedirs(out, exist_ok=True)
LOOK = {}
for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_kalshi.csv'))):
    LOOK[(r['game_id'], int(r['athlete_id']), r['market'], float(r['strike']))] = (float(r['vol30_pretip'] or 0), r['yes_last_pretip'], r['yes_vwap30_pretip'])
_load, _walk = A.load_markets, F.walk_v2
_cache = {}
F.walk_v2 = lambda I: _cache.setdefault('w', _walk(I))
def make(min_vol, use_last):
    def load(by):
        espn, kal = _load(by)
        kal2 = {}
        for m, xs in kal.items():
            keep = []
            for x in xs:
                v, last, vw = LOOK.get((x['gid'], x['r']['aid'], m, x['L']), (0, '', ''))
                if v < min_vol: continue
                if use_last:
                    if not last or not (0.05 < float(last) < 0.95): continue
                    x = dict(x, k=float(last))
                keep.append(x)
            kal2[m] = keep
        return espn, kal2
    return load
res = {}
for tag, mv, ul in (('base', 0, False), ('vol>=500', 500, False), ('vol>=2000', 2000, False), ('last trade', 0, True)):
    A.load_markets = make(mv, ul)
    BC.OUT_JSON = os.path.join(out, f'cons_{tag.replace(" ", "_")}.json'); BC.OUT_MD = os.path.join(out, f'cons_{tag.replace(" ", "_")}.md')
    with contextlib.redirect_stdout(io.StringIO()): BC.main()
    d = json.load(open(BC.OUT_JSON)); res[tag] = d
    print(tag, 'done', flush=True)
print('\ncell: consensus + model, Kalshi ladder leave-one-out, second half, 3%+ edge after fees')
for tag, d in res.items():
    for m in ('pts', '3pm', 'ast', 'reb'):
        for sd in ('NO', 'YES'):
            b = ((d['tests']['kalshi_ladder'].get(m, {}).get('bets') or {}).get('consensus + model') or {}).get(sd)
            if b and b.get('n'): print(f"{tag:11s} {m:4s} {sd:3s} n={b['n']:5d} games={b['games']:4d} roi={b['roi']:+.3f} z={b['z']}")
