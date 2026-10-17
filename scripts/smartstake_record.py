"""Record SmartStake league snapshots to a local tape for backtests and closing-line value.

  SMARTSTAKE_API_KEY=... python3 scripts/smartstake_record.py --league nfl [--league nba] \
      [--interval 300] [--once]

Each pass writes data/smartstake/<league>/<YYYY-MM-DD>.jsonl.gz, one line per pass:
{"t": epoch_ms, "league": ..., "quotes": [...]}. The API has no history, so this tape is
the history. Local only: the terms forbid publishing the data, and data/smartstake/ is
gitignored. Run it more often close to kickoff if you want a tight closing snapshot.
"""
import argparse
import gzip
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from smartstake_client import snapshot
from smartstake_props import convert as convert_props
from smartstake_to_book_tape import convert

ROOT = Path(__file__).resolve().parent.parent / "data" / "smartstake"


# Books worth keeping: exchanges and sharp-leaning prices, the big US books, and pick'em.
# Pass --all-books to keep everything (the NFL board is about 22 MB per pass uncut).
DEFAULT_BOOKS = {
    "novig", "kalshi", "polymarket", "polymarket_us", "prophetx", "circa", "bookmaker", "bet365",
    "draftkings", "fanduel", "betmgm", "caesars", "fanatics", "betrivers",
    "prizepicks", "underdog_dfs", "parlayplay",
}
DROP_FIELDS = ("bet_url", "team_id", "sport")  # keep home/away/starts_at: a closing line needs them


def record(league, books):
    t = int(time.time() * 1000)
    quotes = []
    for q in snapshot(league):
        if books and q.get("book") not in books:
            continue
        quotes.append({k: v for k, v in q.items() if k not in DROP_FIELDS})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = ROOT / league / f"{day}.jsonl.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "at", encoding="utf-8") as f:
        f.write(json.dumps({"t": t, "league": league, "quotes": quotes}, separators=(",", ":")) + "\n")
    print(f"{datetime.now():%H:%M:%S} {league}: {len(quotes)} quotes -> {out.relative_to(ROOT.parent.parent)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", action="append", required=True)
    ap.add_argument("--interval", type=int, default=300, help="seconds between passes")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--all-books", action="store_true")
    a = ap.parse_args()
    books = None if a.all_books else DEFAULT_BOOKS
    while True:
        for lg in a.league:
            try:
                record(lg, books)
            except Exception as e:
                print(f"{lg}: pass failed: {e}", flush=True)
        for lg in a.league:
            if lg in ("nfl", "nba"):
                try:
                    convert(lg)   # refresh the local-only chart tape (Circa, Bookmaker)
                    convert_props(lg)   # and the per-book prop lines the pages read with ?ss
                except Exception as e:
                    print(f"{lg}: book-tape export failed: {e}", flush=True)
        if a.once:
            return
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
