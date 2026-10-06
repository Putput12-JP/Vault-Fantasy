#!/usr/bin/env python3
# Ranks the week's props by Vault P(side) minus the real books' no-vig P(side), the
# "gap" tier's number (see docs/strict-tier-backtest.md). Runs the Best Bets builder on a
# scratch copy of the feed so nothing in data/ is changed. Research list, not a bet list.
#   python3 scripts/rank_week_gaps.py [--week 5] [--top 15]
import argparse, json, os, subprocess, sys, tempfile, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument("--week", type=int); ap.add_argument("--top", type=int, default=15)
ap.add_argument("--no-pull", action="store_true"); a = ap.parse_args()
sh = lambda *c: subprocess.run(c, cwd=ROOT, capture_output=True, text=True)
if not a.no_pull: sh("git", "pull", "--rebase", "--autostash", "-q", "origin", "main")
feed = json.load(open(os.path.join(ROOT, "data/lineup-feed.json")))
games = feed.get("vegas_games") or []
wk = a.week or max((g.get("week") or 0) for g in games) or feed.get("week")
feed["week"] = wk
tmp = tempfile.mkdtemp()
fp, sp = os.path.join(tmp, "feed.json"), os.path.join(tmp, "strict.json")
json.dump(feed, open(fp, "w"))
r = sh("node", "scripts/build_best_bets.mjs", f"--feed={fp}", f"--card={tmp}/card.json", f"--shadow={tmp}/shadow.json",
       f"--strict={sp}", "--strictmodel=0", "--strictmkt=0", "--gapmin=0")
sh("git", "checkout", "data/best_bets_held.json", "data/signal_log.json")   # builder side files, not part of this report
if not os.path.exists(sp): print("no scored lines for week", wk); print(r.stdout[-600:]); sys.exit(0)
P = {(p["pid"], p["market"]): p for p in json.load(open(sp))["picks"] if p["tier"] == "strict"}
rows = []
for p in P.values():
    p["gap"] = p["prob"] - p["mkt"]; rows.append(p)
rows.sort(key=lambda p: -p["gap"])
tested = {"rush_yd", "rush_att", "rec_yd"}
posted = sorted({tuple(sorted((p["team"], p["opp"]))) for p in rows})
print(f"WEEK {wk}: {len(rows)} scored lines across {len(posted)} games with props ({len(games and [g for g in games if g.get('week') == wk])} games on the slate)")
print(f"Tested tier (rush yds / rush att / rec yds, gap >= 15 pts): {sum(1 for p in rows if p['market'] in tested and p['gap'] >= .15)} plays\n")
def line(p):
    return (f"{p['name']:22s} {p['pos']:3s} {p['team']}@{p['opp']} {p['market']:8s} {p['side']:5s} {p['line']:>6} {p['book'][:11]:11s} {p['price']:>5} "
            f"vault {p['prob']*100:3.0f}% mkt {p['mkt']*100:3.0f}% gap {p['gap']*100:+3.0f} books {p['nBooks']}")
print("TESTED MARKETS, biggest gaps (the only place the model beat the price):")
for p in [x for x in rows if x["market"] in tested][:a.top]: print(" ", line(p))
print("\nOTHER MARKETS, biggest gaps (context; no measured edge):")
for p in [x for x in rows if x["market"] not in tested][:a.top]: print(" ", line(p))
print("\nNotes: gap = Vault P(side) minus real-book no-vig P(side). 1-book markets are weak. Check injuries/role before acting.")
