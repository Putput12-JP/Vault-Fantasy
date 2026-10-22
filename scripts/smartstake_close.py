"""Closing lines from the local SmartStake tape: the last pass before starts_at, per book and market.

  python3 scripts/smartstake_close.py            # nfl and nba
  python3 scripts/smartstake_close.py --league nba [--include-open]

Reads  data/smartstake/<league>/*.jsonl.gz   (one line per pass: {"t": epoch_ms, "quotes": [...]})
Writes data/smartstake/close_<league>.json:
  {"asof": epoch, "league": "nba", "passes": N, "closes": [{"event_id", "starts_at", "home", "away", "market",
    "participant", "player_id", "line", "book", "alt", "side_a", "odds_a", "odds_b", "p_a", "t", "min_before", "updated_at"}]}

A close is a two-sided pair (over/under, hometeam/awayteam, yes/no, odd/even) at one line on one book, taken from the
last pass with t < starts_at, and de-vigged with prop_close_lib.devig. p_a is the no-vig probability of side_a (over,
hometeam, yes or odd). Handicaps are keyed on the home line, so the away side at -L pairs with the home side at L.
Alternate rungs are kept (alt=true); the main line is the one with alt=false. A one-sided quote is never given a fair
price, it is counted and left out. min_before is how long before the start the pass ran, so a thin tape shows up as a
large number instead of passing as a close.

LOCAL ONLY (gitignored). SmartStake's terms forbid publishing the data, so this file is never committed, never goes into
track.json or any published file, and no page reads it without written permission. Forward-only: it sits beside the
ledger's price_close and never replaces it.
"""
import argparse
import glob
import gzip
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prop_close_lib import devig  # noqa: E402

SS = Path(__file__).resolve().parent.parent / "data" / "smartstake"
SIDE_A = {"over": "over", "under": "over", "hometeam": "hometeam", "awayteam": "hometeam", "yes": "yes", "no": "yes",
          "odd": "odd", "even": "odd"}
IS_A = {"over", "hometeam", "yes", "odd"}


def start_ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000) if s else None


def pair_key(q):
    side = q.get("side")
    if side not in SIDE_A or q.get("live") or q.get("odds") is None or not q.get("starts_at"):
        return None
    line = q.get("line")
    if side == "awayteam" and line is not None:
        line = -line   # key handicaps on the home line
    return (q["event_id"], q["market_key"], (q.get("player_id") or q.get("participant")) if side not in ("hometeam", "awayteam") else None,
            line, q["book"])


def build(league, include_open):
    now = int(time.time() * 1000)
    best = {}   # pair key -> (t, {side: quote})
    partial = {}   # pair keys seen one-sided
    passes = 0
    for path in sorted(glob.glob(str(SS / league / "*.jsonl.gz"))):
        for ln in gzip.open(path, "rt", encoding="utf-8"):
            rec = json.loads(ln)
            t = rec["t"]
            passes += 1
            cur = {}
            for q in rec["quotes"]:
                k = pair_key(q)
                if not k:
                    continue
                st = start_ms(q["starts_at"])
                if st is None or t >= st or (st > now and not include_open):
                    continue   # only passes strictly before the start count; unstarted games wait for their close
                cur.setdefault(k, {})[q["side"]] = q
            for k, sides in cur.items():
                if len({SIDE_A[s] for s in sides}) == 1 and any(s in IS_A for s in sides) and any(s not in IS_A for s in sides):
                    best[k] = (t, sides)   # a close needs both sides in the same pass; a later one-sided pass never replaces it
                else:
                    partial[k] = partial.get(k, 0) + 1
    closes, one_sided, still_open = [], Counter(), 0
    for k in partial:
        if k not in best:
            one_sided[k[1]] += 1
    for k, (t, sides) in best.items():
        a = next(s for s in sides if s in IS_A)
        b = next(s for s in sides if s not in IS_A)
        qa, qb = sides[a], sides[b]
        if start_ms(qa["starts_at"]) > now:
            still_open += 1
        p = devig(qa["odds"], qb["odds"])
        if p is None:
            one_sided[k[1]] += 1
            continue
        closes.append({
            "event_id": k[0], "starts_at": qa["starts_at"], "home": qa["home"], "away": qa["away"], "market": k[1],
            "participant": qa.get("participant") if k[2] is not None else None, "player_id": qa.get("player_id"),
            "line": k[3], "book": k[4], "alt": bool(qa.get("alternate")), "side_a": SIDE_A[a], "odds_a": qa["odds"],
            "odds_b": qb["odds"], "p_a": round(p, 5), "t": t, "min_before": round((start_ms(qa["starts_at"]) - t) / 60000, 1),
            "updated_at": min(qa.get("updated_at") or t, qb.get("updated_at") or t),
        })
    return passes, closes, one_sided, still_open


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", action="append")
    ap.add_argument("--dir", help="tape folder (default: data/smartstake beside this script's checkout)")
    ap.add_argument("--include-open", action="store_true", help="also keep the latest pass for games not yet started")
    a = ap.parse_args()
    global SS
    if a.dir:
        SS = Path(a.dir)
    for lg in a.league or ["nfl", "nba"]:
        passes, closes, one_sided, still_open = build(lg, a.include_open)
        out = SS / f"close_{lg}.json"
        out.write_text(json.dumps({"asof": int(time.time() * 1000), "league": lg, "passes": passes, "closes": closes},
                                  separators=(",", ":")))
        games = {c["event_id"] for c in closes}
        mins = [c["min_before"] for c in closes]
        print(f"{lg}: {passes} passes read, {len(closes)} closes over {len(games)} games "
              f"({len({c['book'] for c in closes})} books, {len({c['market'] for c in closes})} markets), "
              f"{sum(one_sided.values())} one-sided skipped, {still_open} for games not started yet")
        if mins:
            print(f"   min before start: median {pct(mins, .5)}, p90 {pct(mins, .9)}, max {max(mins)}")
        print(f"   by book: {dict(Counter(c['book'] for c in closes).most_common())}")
        print(f"   -> {out}")


if __name__ == "__main__":
    main()
