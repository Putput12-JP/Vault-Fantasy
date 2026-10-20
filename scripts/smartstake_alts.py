"""Alternate-line player-prop prices per book from the local SmartStake tape, for the NBA page's Combo Check (?ss view).

  python3 scripts/smartstake_alts.py

Reads  the newest data/smartstake/nba/*.jsonl.gz, last poll only (each poll is a full snapshot, so the last one is the current state)
Writes data/smartstake/props_nba_alts.json:
  {"asof": epoch, "props": [{"n": player, "s": stat, "away": "BOS", "home": "DET", "start": epoch,
    "alts": [[book, line, over_american_or_null, under_american_or_null]]}]}
Only the book's alternate (non-main) quotes, pregame only. One-sided alternates (an over with no under) are kept as they are:
sportsbooks mostly post alt lines as milestones, so the other side is null and the page does not guess it.

LOCAL ONLY (gitignored). SmartStake's terms forbid publishing the data or showing it in the UI without written permission,
so the page reads this file only on localhost with ?ss. See docs/smartstake-permission-request.md.
"""
import glob
import gzip
import json
from datetime import datetime
from pathlib import Path

from smartstake_props import NAMES, STAT, PREFIX
from smartstake_to_book_tape import abbr

ROOT = Path(__file__).resolve().parent.parent
SS = ROOT / "data" / "smartstake"


def main():
    files = sorted(glob.glob(str(SS / "nba" / "*.jsonl.gz")))
    if not files:
        print("no SmartStake NBA tape")
        return
    last = None
    for line in gzip.open(files[-1], "rt", encoding="utf-8"):
        last = line
    poll = json.loads(last)
    pre, stats = PREFIX["nba"], STAT["nba"]
    props, n = {}, 0
    for q in poll["quotes"]:
        if not q.get("alternate") or q.get("live") or q.get("line") is None or q.get("book") not in NAMES:
            continue
        if not q.get("market_key", "").startswith(pre) or not q.get("participant") or q.get("side") not in ("over", "under"):
            continue
        st = stats.get(q["market_key"][len(pre):])
        aa, ha = abbr("nba", q["away"]), abbr("nba", q["home"])
        if not st or not aa or not ha:
            continue
        start = int(datetime.fromisoformat(q["starts_at"].replace("Z", "+00:00")).timestamp())
        p = props.setdefault((q["event_id"], q["participant"], st), {"n": q["participant"], "s": st, "away": aa, "home": ha, "start": start, "by": {}})
        row = p["by"].setdefault((NAMES[q["book"]], q["line"]), [NAMES[q["book"]], q["line"], None, None])
        row[2 if q["side"] == "over" else 3] = q["odds"]
        n += 1
    out = []
    for p in sorted(props.values(), key=lambda p: (p["start"], p["n"], p["s"])):
        out.append({"n": p["n"], "s": p["s"], "away": p["away"], "home": p["home"], "start": p["start"], "alts": sorted(p["by"].values(), key=lambda r: (r[0], r[1]))})
    path = SS / "props_nba_alts.json"
    path.write_text(json.dumps({"asof": poll.get("t"), "props": out}, separators=(",", ":")))
    print(f"{n} alternate quotes, {len(out)} props, {sum(len(p['alts']) for p in out)} book lines -> {path}")


if __name__ == "__main__":
    main()
