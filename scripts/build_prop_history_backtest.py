#!/usr/bin/env python3
"""Historical prop test for the Props > Record drill-down: ESPN BET 2024-25, open price vs the later no-vig close.

Question: when ESPN BET's OPENING price on a side was better than the no-vig fair price at the CLOSE (same line), did
that side win, and did it beat the close? This is a one-book, early-vs-late test. It is NOT the live strategy (exchange or
US-book price vs Pinnacle's fair price); it just gives thousands of settled plays to learn from while the live ledger fills.

  entry   a side whose opening price implies EV >= MIN_EV against the close's power-devigged fair price, same line
          (open line != close line rows are skipped: the prices are not comparable)
  settle  flat 1 unit at the opening price from nflverse box scores (data/nflverse_stats_<season>.json); pushes dropped
  CLV     fair close / opening implied probability - 1

Inputs : data/espn_prop_lines_<season>.json (crawl cache from build_prop_market_prior.py), nflverse games + players csv
Output : data/prop_history_backtest.json  (compact rows; read by sharp-money/index.html's drill-down)
Usage  : python3 scripts/build_prop_history_backtest.py [--min-ev=0.03]
"""
import csv, io, json, os, re, sys, unicodedata, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
SEASONS = (2024, 2025)
MIN_EV = 0.03
for a in sys.argv[1:]:
    if a.startswith("--min-ev="): MIN_EV = float(a.split("=", 1)[1])

COL = {"pass_yd": ("pyds",), "pass_att": ("att",), "pass_cmp": ("cmp",), "pass_td": ("ptds",),
       "rush_yd": ("ryds",), "rush_att": ("car",), "rec": ("rec",), "rec_yd": ("recyds",)}
LABEL = {"pass_yd": "Passing yards", "pass_att": "Pass attempts", "pass_cmp": "Completions", "pass_td": "Passing TDs",
         "rush_yd": "Rushing yards", "rush_att": "Rush attempts", "rec": "Receptions", "rec_yd": "Receiving yards"}


def text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def nkey(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z]", "", "".join(ch for ch in s if unicodedata.category(ch) != "Mn"))


def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def imp(a): return 1 / dec(a)


def devig_power(o, u):
    po, pu = imp(o), imp(u)
    if po + pu <= 1: return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1: lo = k
        else: hi = k
    return po ** ((lo + hi) / 2)


def main():
    games = {g["game_id"]: g for g in csv.DictReader(io.StringIO(text(GAMES_URL)))}
    e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(text(PLAYERS_URL))) if r.get("espn_id")}
    stats = {}
    for yr in SEASONS:
        blob = json.load(open(os.path.join(DATA, f"nflverse_stats_{yr}.json")))
        for p in (blob.values() if isinstance(blob, dict) else blob):
            stats[(nkey(p.get("name")), yr)] = {int(w["wk"]): w for w in (p.get("weeks") or []) if w.get("wk") is not None}
    plays, skipped = [], {}
    def skip(why): skipped[why] = skipped.get(why, 0) + 1
    for yr in SEASONS:
        rows = json.load(open(os.path.join(DATA, f"espn_prop_lines_{yr}.json")))["rows"]
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in rows:
            if mkt not in COL: skip("market"); continue
            if None in (lo, oo, uo, lc, oc, uc): skip("incomplete"); continue
            if lo != lc: skip("line moved"); continue
            g = games.get(gid); name = e2n.get(ath)
            if not g or not name: skip("no game/id"); continue
            wk = int(g["week"]); w = (stats.get((nkey(name), int(g["season"]))) or {}).get(wk)
            if not w: skip("no box score"); continue
            act = sum(float(w.get(c) or 0) for c in COL[mkt])
            if abs(act - lo) < 1e-9: skip("push"); continue
            fo = devig_power(oc, uc)
            for side, price, fair in (("over", oo, fo), ("under", uo, 1 - fo)):
                p_entry = imp(price); ev = fair / p_entry - 1
                if ev < MIN_EV: continue
                won = (act > lo) if side == "over" else (act < lo)
                units = round(dec(price) - 1, 4) if won else -1.0
                plays.append([int(g["season"]), wk, int(ath), mkt, 1 if side == "over" else 0,
                              round(ev, 4), round(p_entry, 4), round(fair / p_entry - 1, 4), 1 if won else 0, units])
    n = len(plays); w = sum(p[8] for p in plays); u = sum(p[9] for p in plays)
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "ESPN BET open vs no-vig close, 2024-25",
           "minEv": MIN_EV, "cols": ["season", "week", "athlete", "market", "over", "ev", "p", "clv", "won", "units"],
           "labels": LABEL, "n": n, "plays": plays}
    json.dump(out, open(os.path.join(DATA, "prop_history_backtest.json"), "w"), separators=(",", ":"))
    print(f"[prop-history] {n} plays, won {w} ({w / n:.1%}), units {u:+.1f}, roi {u / n:+.1%}; skipped {skipped}")


if __name__ == "__main__":
    main()
