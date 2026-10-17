"""Per-book player-prop lines from the local SmartStake tape, for the pages' ?ss view.

  python3 scripts/smartstake_props.py            # nfl and nba

Reads  data/smartstake/<league>/*.jsonl.gz
Writes data/smartstake/props_<league>.json:
  {"asof": epoch, "league": "nba", "props": [{"n": player, "s": stat, "away": "BOS", "home": "DET", "start": epoch,
    "books": [[book, line, over, under, line0, over0, under0, t]]}]}
line0/over0/under0 are the first line and prices the tape saw for that book; t is when the book last quoted it.

LOCAL ONLY (gitignored). SmartStake's terms forbid publishing the data or showing it in the UI without written
permission, so the pages read this file only on localhost with ?ss. Only two-sided over/under quotes on a book's main
(non-alternate) line are kept; pick'em single-price quotes and alternates are left out rather than guessed.
"""
import glob
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

from smartstake_to_book_tape import abbr

ROOT = Path(__file__).resolve().parent.parent
SS = ROOT / "data" / "smartstake"

NAMES = {
    "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "caesars": "Caesars", "fanatics": "Fanatics",
    "parlayplay": "ParlayPlay", "betrivers": "BetRivers", "bet365": "bet365", "circa": "Circa", "bookmaker": "Bookmaker",
    "prophetx": "ProphetX", "novig": "Novig",
}   # Kalshi and Polymarket are ladders of strikes, not one main line, so they stay on their own Props chips
STAT = {
    "nba": {
        "points": "pts", "rebounds": "reb", "assists": "ast", "made_threes": "3pm", "points_rebounds_assists": "pra",
        "points_rebounds": "pr", "points_assists": "pa", "rebounds_assists": "ra", "steals": "stl", "blocks": "blk",
        "steals_blocks": "sb", "turnovers": "tov",
    },
    "nfl": {
        "passing_yards": "Pass yds", "passing_touchdowns": "Pass TD", "passing_attempts": "Pass att",
        "passing_completions": "Completions", "rushing_yards": "Rush yds", "rushing_attempts": "Rush att",
        "receiving_yards": "Rec yds", "receptions": "Receptions", "rushing_receiving_yards": "Rush+Rec yds",
        "passing_rushing_yards": "Pass+Rush yds", "longest_reception": "Long rec",
    },
}
PREFIX = {"nba": "basketball_player_", "nfl": "football_player_"}


def main_line(qs):
    """The line whose over and under prices are closest, with both sides present."""
    by = {}
    for q in qs:
        by.setdefault(q["line"], {})[q["side"]] = q
    best = None
    for line, s in by.items():
        if "over" in s and "under" in s and abs(s["over"]["odds"]) <= 200 and abs(s["under"]["odds"]) <= 200:
            gap = abs(s["over"]["odds"] - s["under"]["odds"])
            if best is None or gap < best[0]:
                best = (gap, line, s)
    return best


def convert(league):
    pre, stats = PREFIX[league], STAT[league]
    first, last, meta = {}, {}, {}
    for f in sorted(glob.glob(str(SS / league / "*.jsonl.gz"))):
        for line in gzip.open(f, "rt", encoding="utf-8"):
            p = json.loads(line)
            groups = {}
            for q in p["quotes"]:
                if not q.get("player_id") or q.get("alternate") or q.get("live") or q.get("line") is None:
                    continue
                if q["book"] not in NAMES or not q["market_key"].startswith(pre):
                    continue
                st = stats.get(q["market_key"][len(pre):])
                if st and q.get("participant") and q["side"] in ("over", "under"):
                    groups.setdefault((q["event_id"], q["participant"], st, q["book"]), []).append(q)
            for key, qs in groups.items():
                m = main_line(qs)
                if not m:
                    continue
                _, ln, s = m
                row = [NAMES[key[3]], ln, s["over"]["odds"], s["under"]["odds"]]
                t = max(s["over"]["updated_at"], s["under"]["updated_at"]) // 1000
                first.setdefault(key, row + [t])
                last[key] = row + [t]
                q0 = s["over"]
                meta[key[:3]] = (q0["away"], q0["home"], q0["starts_at"])
    props = {}
    for key, cur in last.items():
        ev, name, st, _ = key
        a, h, starts = meta[key[:3]]
        aa, ha = abbr(league, a), abbr(league, h)
        if not aa or not ha:
            continue
        start = int(datetime.fromisoformat(starts.replace("Z", "+00:00")).timestamp())
        p = props.setdefault((ev, name, st), {"n": name, "s": st, "away": aa, "home": ha, "start": start, "books": []})
        f = first[key]
        p["books"].append(cur[:4] + [f[1], f[2], f[3], cur[4]])
    out = sorted(props.values(), key=lambda p: (p["start"], p["n"], p["s"]))
    for p in out:
        p["books"].sort(key=lambda b: b[0])
    path = SS / f"props_{league}.json"
    path.write_text(json.dumps({"asof": max((b[7] for p in out for b in p["books"]), default=0), "league": league, "props": out}, separators=(",", ":")))
    print(f"{league}: {len(out)} props, {sum(len(p['books']) for p in out)} book lines -> {path}", flush=True)


if __name__ == "__main__":
    for lg in (sys.argv[1:] or ["nfl", "nba"]):
        convert(lg)
