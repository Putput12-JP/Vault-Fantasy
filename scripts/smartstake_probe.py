"""One-shot look at what this SmartStake key can see: status, sports, leagues, books,
and the markets for NFL and NBA. Prints a summary only; writes nothing.

  SMARTSTAKE_API_KEY=... python3 scripts/smartstake_probe.py
"""
import json

from smartstake_client import get


def show(title, path, params=None):
    print(f"\n== {title} ({path})")
    try:
        print(json.dumps(get(path, params).get("data"), indent=1)[:3000])
    except Exception as e:  # keep probing the rest
        print("  failed:", e)


show("status", "/v1/status")
show("sports", "/v1/sports")
show("leagues", "/v1/leagues")
show("books", "/v1/books")
for lg in ("nfl", "nba", "ncaaf", "cfb"):
    show(f"markets {lg}", "/v1/markets", {"league": lg})
