#!/usr/bin/env python3
"""Backtest: can a prop's fair price at one line be converted to another line?  (ESPN BET 2024-25 moved lines)

Pick'em apps and some books hang a different number than Pinnacle. To price them we need P(over L') from a fair
price at L_c. Model: logit P(over L') = logit(fair_c) + (L_c - L')/s, with s = c_m * L_c^b per market.
  * fit (c, b) per market on 2024 moved lines, score OUT OF SAMPLE on 2025
  * the lines that moved are open -> close: the OPEN line L_o is the target, the CLOSE fair is the source
  * baselines at the open line: the open no-vig price itself (what a venue at that line believed), and the
    unshifted close fair (ignores the move).  A converter that beats both is adding real information.
Metrics: log-loss, calibration by bucket, and how error grows with the size of the shift.
"""
import csv, io, json, math, os, sys, collections, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_prop_market_prior as P
COL = {"pass_yd": ("pyds",), "pass_att": ("att",), "pass_cmp": ("cmp",), "pass_td": ("ptds",), "rush_yd": ("ryds",), "rush_att": ("car",), "rec": ("rec",), "rec_yd": ("recyds",)}
prob = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)
def devig(o, u): po, pu = prob(o), prob(u); return po / (po + pu)
lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))
sg = lambda x: 1 / (1 + math.exp(-max(-40, min(40, x))))
ll = lambda p, y: -math.log(min(max(p, 1e-4), 1 - 1e-4)) if y else -math.log(1 - min(max(p, 1e-4), 1 - 1e-4))
text = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=P.UA), timeout=120).read().decode("utf-8", "replace")
games = {g["game_id"]: g for g in csv.DictReader(io.StringIO(text(P.GAMES_URL)))}
e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(text(P.PLAYERS_URL))) if r.get("espn_id")}
W = P.load_weeks([2024, 2025])
rows = []
for season in (2024, 2025):
    for gid, ath, mkt, lo, oo, uo, lc, oc, uc in P.load_lines(season, [], False):
        if mkt not in COL or None in (lo, oo, uo, lc, oc, uc) or lo == lc: continue
        name, g = e2n.get(ath), games.get(gid)
        if not name or not g: continue
        row = next((w for w in W.get((P.nkey(name), season), (None, []))[1] if P.B.num(w.get("wk")) == int(g["week"])), None)
        if row is None: continue
        act = sum(P.B.num(row.get(k)) or 0 for k in COL[mkt])
        if act == lo: continue
        rows.append(dict(season=season, mkt=mkt, lo=lo, lc=lc, fc=devig(oc, uc), fo=devig(oo, uo), y=act > lo))
print("moved lines with a result:", len(rows), collections.Counter(r["season"] for r in rows))

def pred(r, c, b): s = c * r["lc"] ** b; return sg(lg(r["fc"]) + (r["lc"] - r["lo"]) / s)
fit = {}
for m in COL:
    tr = [r for r in rows if r["mkt"] == m and r["season"] == 2024]
    if len(tr) < 40: continue
    best = None
    for b in (0, .25, .5, .75, 1.0):
        for c in [x / 20 for x in range(1, 120)]:
            L = sum(ll(pred(r, c, b), r["y"]) for r in tr) / len(tr)
            if best is None or L < best[0]: best = (L, c, b)
    fit[m] = (best[1], best[2])
print("fitted (c, b) on 2024:", {m: (round(c, 3), b) for m, (c, b) in fit.items()})

def report(lab, xs):
    if not xs: return
    n = len(xs); mod = sum(ll(pred(r, *fit[r["mkt"]]), r["y"]) for r in xs) / n
    opn = sum(ll(r["fo"], r["y"]) for r in xs) / n; unsh = sum(ll(r["fc"], r["y"]) for r in xs) / n
    print(f"{lab:26} n={n:5}  logloss  shifted-close {mod:.4f}   open-price {opn:.4f}   unshifted-close {unsh:.4f}   (lower = better)")
test = [r for r in rows if r["season"] == 2025 and r["mkt"] in fit]
print("\nOUT OF SAMPLE (2025):")
report("ALL", test)
for m in fit: report(m, [r for r in test if r["mkt"] == m])
print("\nby size of the move (|L_o - L_c| / L_c), 2025:")
for lo_, hi_ in ((0, .03), (.03, .06), (.06, .10), (.10, .20), (.20, 9)):
    report(f"shift {lo_:.0%}-{hi_:.0%}" if hi_ < 9 else f"shift {lo_:.0%}+", [r for r in test if lo_ <= abs(r["lo"] - r["lc"]) / r["lc"] < hi_])
print("\ncalibration of the shifted prediction (2025):")
for a, b in ((0, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7), (.7, 1)):
    xs = [(pred(r, *fit[r["mkt"]]), r["y"]) for r in test]; xs = [x for x in xs if a <= x[0] < b]
    if xs: print(f"  predicted {a:.1f}-{b:.1f}  n={len(xs):5}  mean pred {sum(x[0] for x in xs)/len(xs):.3f}  actual {sum(x[1] for x in xs)/len(xs):.3f}")
prod = {}
for m in fit:                                          # production constants: refit on BOTH seasons (the out-of-sample table above is the honest score)
    tr = [r for r in rows if r["mkt"] == m]; best = None
    for b in (0, .25, .5, .75, 1.0):
        for c in [x / 20 for x in range(1, 120)]:
            L = sum(ll(pred(r, c, b), r["y"]) for r in tr) / len(tr)
            if best is None or L < best[0]: best = (L, c, b)
    prod[m] = (best[1], best[2])
json.dump({m: {"c": round(c, 4), "b": b} for m, (c, b) in prod.items()}, open(os.path.join(HERE, "..", "data", "prop_line_shift.json"), "w"), indent=1)
print("\nwrote data/prop_line_shift.json (2024 fit)")
