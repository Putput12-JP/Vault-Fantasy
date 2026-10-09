#!/usr/bin/env python3
"""Backtest: did "best price beats the no-vig consensus" props win?  (2026 wk1+, data/prop_line_history.json)

Entry = the FIRST pregame snapshot where a side's best available price implies >= MIN_EV against the no-vig
consensus of that snapshot (same line). Close = the last pregame snapshot. Settled from nflverse box scores,
flat 1 unit at the entry price.

What this can and cannot say: history stores only the consensus quote and the best price across books, not who
quoted it, so this tests LINE SHOPPING against consensus. It cannot test Pinnacle-fair, Kalshi or Novig gaps
(no history exists for those: the live tracker is how those get measured).
"""
import json, sys, collections, datetime as dt
MIN_EV = float(sys.argv[1]) if len(sys.argv) > 1 else 0.03
COL = {"pass_yd": ("pyds",), "pass_att": ("att",), "pass_cmp": ("cmp",), "pass_td": ("ptds",), "pass_int": ("ints",),
       "rush_yd": ("ryds",), "rush_att": ("car",), "rec": ("rec",), "rec_yd": ("recyds",),
       "anytime_td": ("rtds", "rectds"), "rush_rec_yd": ("ryds", "recyds"), "pass_rush_yd": ("pyds", "ryds")}
prob = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)
def fair(o, u):
    po, pu = prob(o), prob(u); return po / (po + pu)
ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

H = json.load(open("data/prop_line_history.json"))["props"]
S = json.load(open("data/nflverse_stats_2026.json"))
rows = []
for v in H.values():
    if v["season"] != "2026" or v["market"] not in COL or not v.get("commence"): continue
    c = ts(v["commence"]); sm = sorted([s for s in v["samples"] if ts(s["ts"]) < c and s.get("over") is not None and s.get("under") is not None], key=lambda s: s["ts"])
    if len(sm) < 2: continue
    close = sm[-1]
    p = S.get(v["name"]); w = next((x for x in (p or {}).get("weeks", []) if x["wk"] == v["week"]), None)
    if not w: continue
    val = sum(float(w.get(k) or 0) for k in COL[v["market"]])
    done_sides = set()   # ONE entry per (prop, side): the first pregame snapshot that qualifies
    for s in sm[:-1]:
        f = fair(s["over"], s["under"])
        for side, best, pf in (("over", s.get("bestOver"), f), ("under", s.get("bestUnder"), 1 - f)):
            if best is None or side in done_sides: continue
            ev = pf / prob(best) - 1
            if ev < MIN_EV: continue
            win = val > s["line"] if side == "over" else val < s["line"]
            push = val == s["line"]
            u = 0 if push else (100 / abs(best) if best < 0 else best / 100) if win else -1
            if win and not push: u = (best / 100) if best > 0 else (100 / -best)
            clv = None
            if close["line"] == s["line"]:
                cf = fair(close["over"], close["under"]); cf = cf if side == "over" else 1 - cf
                clv = cf / prob(best) - 1
            done_sides.add(side)
            rows.append(dict(mkt=v["market"], wk=v["week"], side=side, ev=ev, win=win and not push, push=push, u=u, clv=clv, price=best))
def summarize(xs, lab):
    d = [x for x in xs if not x["push"]]
    if not d: print(f"{lab:28} n=0"); return
    cl = [x["clv"] for x in xs if x["clv"] is not None]
    print(f"{lab:28} n={len(d):4}  hit={sum(x['win'] for x in d)/len(d):5.1%}  ROI={sum(x['u'] for x in d)/len(d):+6.1%}  CLV={(sum(cl)/len(cl) if cl else float('nan')):+6.1%} (n={len(cl)}, {sum(c>0 for c in cl)/len(cl) if cl else 0:.0%} pos)")
print(f"MIN_EV {MIN_EV:.0%}   entries {len(rows)}")
summarize(rows, "ALL")
for lo, hi in ((0.03, 0.06), (0.06, 0.10), (0.10, 9)):
    summarize([x for x in rows if lo <= x["ev"] < hi], f"EV {lo:.0%}-{hi:.0%}" if hi < 9 else f"EV {lo:.0%}+")
for side in ("over", "under"): summarize([x for x in rows if x["side"] == side], side)
by = collections.defaultdict(list)
for x in rows: by[x["mkt"]].append(x)
for m, xs in sorted(by.items(), key=lambda kv: -len(kv[1])): summarize(xs, m)
for wk in sorted({x["wk"] for x in rows}): summarize([x for x in rows if x["wk"] == wk], f"week {wk}")
