#!/usr/bin/env python3
"""Backtest: does a price that beats the later no-vig fair actually pay?  (ESPN BET props, 2024-25, ~15k lines)

The live Props page calls a side +EV when a venue's price beats the no-vig fair price at the SAME line. The
only large archive that can test that mechanism is ESPN BET's open + close prop prices (data/espn_prop_lines_*.json),
settled from nflverse box scores. Treat the OPEN price as "the price on offer" and the CLOSE no-vig price as
"fair": a stale / lagging venue is exactly an open price the close later proves was off.

  EV      = closeFair(side) / impliedOpenPrice(side) - 1        (same line only; a line move is a different bet)
  tests   1. calibration  : does closeFair predict wins?  (bucketed, plus ROI of just betting everything = -vig)
          2. realized vs expected: by EV bucket, realized ROI vs the EV the close fair promised.
                         realized ~= expected  -> the fair price is the true price and gaps are real money.
                         realized << expected  -> the "edge" is noise / vig / bad data (phantom).
          3. consistency  : 2024 and 2025 reported separately.
Honest limits: one book (ESPN BET), main lines only, open->close not venue->venue, pushes dropped.

  python3 scripts/backtest_prop_stale_price.py            # all
  python3 scripts/backtest_prop_stale_price.py --min-ev 0.03
"""
import argparse, csv, io, json, math, os, sys, urllib.request, collections
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "..", "data"); sys.path.insert(0, HERE)
import build_prop_market_prior as P

COL = {"pass_yd": ("pyds",), "pass_att": ("att",), "pass_cmp": ("cmp",), "pass_td": ("ptds",),
       "rush_yd": ("ryds",), "rush_att": ("car",), "rec": ("rec",), "rec_yd": ("recyds",)}
prob = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)
dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
def devig(o, u):
    po, pu = prob(o), prob(u); return po / (po + pu)

def text(url): return urllib.request.urlopen(urllib.request.Request(url, headers=P.UA), timeout=120).read().decode("utf-8", "replace")
ap = argparse.ArgumentParser(); ap.add_argument("--min-ev", type=float, default=0.03); A = ap.parse_args()
games = {g["game_id"]: g for g in csv.DictReader(io.StringIO(text(P.GAMES_URL)))}
e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(text(P.PLAYERS_URL))) if r.get("espn_id")}
W = P.load_weeks([2024, 2025])

bets, skipped = [], collections.Counter()
for season in (2024, 2025):
    for gid, ath, mkt, lo, oo, uo, lc, oc, uc in P.load_lines(season, [], False):
        if mkt not in COL: skipped["market"] += 1; continue
        if None in (lo, oo, uo, lc, oc, uc): skipped["unpriced"] += 1; continue
        name, g = e2n.get(ath), games.get(gid)
        if not name or not g: skipped["id"] += 1; continue
        _, cur = W.get((P.nkey(name), season), (None, []))
        row = next((w for w in cur if P.B.num(w.get("wk")) == int(g["week"])), None)
        if row is None: skipped["did not play"] += 1; continue
        act = sum(P.B.num(row.get(k)) or 0 for k in COL[mkt])
        fo = devig(oc, uc)                                    # close no-vig P(over)
        for side, price, fair in (("over", oo, fo), ("under", uo, 1 - fo)):
            same = lo == lc
            bets.append(dict(season=season, mkt=mkt, side=side, same=same, line_o=lo, line_c=lc, price=price, fair=fair,
                             open_fair=devig(oo, uo) if side == "over" else 1 - devig(oo, uo),
                             win=(act > lo) if side == "over" else (act < lo), push=act == lo, closefair_line=lc))
print("lines:", len(bets) // 2, " skipped:", dict(skipped))

def stats(xs):
    xs = [x for x in xs if not x["push"]]
    if not xs: return None
    u = [(dec(x["price"]) - 1) if x["win"] else -1 for x in xs]
    n = len(u); roi = sum(u) / n; sd = (sum((v - roi) ** 2 for v in u) / max(1, n - 1)) ** .5
    exp = sum(x["fair"] * dec(x["price"]) - 1 for x in xs) / n    # EV the close fair promised
    hit = sum(x["win"] for x in xs) / n
    return dict(n=n, hit=hit, exp_hit=sum(x["fair"] for x in xs) / n, roi=roi, se=sd / math.sqrt(n), exp=exp)
def show(lab, xs):
    s = stats(xs)
    if not s: print(f"{lab:30} n=0"); return
    z = (s["roi"] - s["exp"]) / s["se"] if s["se"] else 0
    print(f"{lab:30} n={s['n']:5} hit={s['hit']:5.1%} (fair {s['exp_hit']:5.1%})  ROI={s['roi']:+6.1%} ±{1.96*s['se']:.1%}  expected={s['exp']:+6.1%}  realized-vs-expected z={z:+.1f}")

same = [b for b in bets if b["same"]]
print("\n== 1. calibration of the CLOSE no-vig fair (every priced side at the close line; ROI = what the vig costs)")
close_all = [dict(b, price=b["price"]) for b in bets]
# the close side price isn't kept per side here, so calibrate on fair vs outcome at the OPEN line when unchanged
show("all same-line sides (open px)", same)
for lo_, hi_ in ((0, .35), (.35, .45), (.45, .5), (.5, .55), (.55, .65), (.65, 1)):
    xs = [b for b in same if lo_ <= b["fair"] < hi_]
    s = stats(xs)
    if s: print(f"  fair {lo_:.2f}-{hi_:.2f}   n={s['n']:5}  predicted {s['exp_hit']:5.1%}  actual {s['hit']:5.1%}")

print(f"\n== 2. realized vs expected by EV of the OPEN price against the CLOSE fair (same line only, {len(same)//2} lines)")
B_ = [(-1, -.06), (-.06, -.03), (-.03, 0), (0, .03), (.03, .06), (.06, .10), (.10, 9)]
for lo_, hi_ in B_:
    show(f"EV {lo_:+.0%}..{hi_:+.0%}" if hi_ < 9 else f"EV {lo_:+.0%}+", [b for b in same if lo_ <= b["fair"] * dec(b["price"]) - 1 < hi_])
pl = [b for b in same if b["fair"] * dec(b["price"]) - 1 >= A.min_ev]
print(f"\n== 3. plays at EV >= {A.min_ev:.0%}: by season / market / side")
show("ALL", pl)
for s_ in (2024, 2025): show(f"season {s_}", [b for b in pl if b["season"] == s_])
for sd in ("over", "under"): show(sd, [b for b in pl if b["side"] == sd])
for m in sorted({b["mkt"] for b in pl}): show(m, [b for b in pl if b["mkt"] == m])

print("\n== 4. the same test when the line MOVED (different bet: open side priced at the open line, fair is the close line's)")
mv = [b for b in bets if not b["same"]]
print(f"  {len(mv)//2} lines moved ({len(mv)/len(bets):.0%}); not comparable, reported only so the 'same line' filter is visible")
