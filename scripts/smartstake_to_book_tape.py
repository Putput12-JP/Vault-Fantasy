"""Turn the local SmartStake tape into book-tape rows for the line-movement chart.

  python3 scripts/smartstake_to_book_tape.py            # nfl and nba, books Circa and Bookmaker

Reads  data/smartstake/<league>/*.jsonl.gz   (written by smartstake_record.py)
Writes data/smartstake/book_tape/<league>/YYYY-MM.jsonl   in the same row format as data/book_tape/:
  {"t","src":"ss","gk","away","home","start","book","ml":[away,home],"sp":[home line,home price,away price],"tot":[line,over,under]}
one row per book per game, appended only when that book's line or price changes.

LOCAL ONLY. SmartStake's terms forbid publishing their data or showing it in the UI without written permission,
so this output is gitignored and the chart only reads it on localhost behind a flag (?ss). Games are matched to the
public tape by team and start time so each row carries the same game key the chart already uses.
"""
import glob
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SS = ROOT / "data" / "smartstake"
BOOKS = {"circa": "Circa", "bookmaker": "Bookmaker"}   # the ones the public tape does not have
SPORT = {"nfl": "football", "nba": "basketball"}

NICK = {
    "nfl": {
        "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF", "panthers": "CAR", "bears": "CHI",
        "bengals": "CIN", "browns": "CLE", "cowboys": "DAL", "broncos": "DEN", "lions": "DET", "packers": "GB",
        "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC", "raiders": "LV", "chargers": "LAC",
        "rams": "LAR", "dolphins": "MIA", "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG",
        "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "49ers": "SF", "seahawks": "SEA", "buccaneers": "TB",
        "titans": "TEN", "commanders": "WAS",
    },
    "nba": {
        "hawks": "ATL", "celtics": "BOS", "nets": "BKN", "hornets": "CHA", "bulls": "CHI", "cavaliers": "CLE",
        "mavericks": "DAL", "nuggets": "DEN", "pistons": "DET", "warriors": "GS", "rockets": "HOU", "pacers": "IND",
        "clippers": "LAC", "lakers": "LAL", "grizzlies": "MEM", "heat": "MIA", "bucks": "MIL", "timberwolves": "MIN",
        "pelicans": "NO", "knicks": "NY", "thunder": "OKC", "magic": "ORL", "76ers": "PHI", "suns": "PHX",
        "blazers": "POR", "kings": "SAC", "spurs": "SA", "raptors": "TOR", "jazz": "UTA", "wizards": "WAS",
    },
}
ALIAS = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX", "LVR": "LV", "OAK": "LV", "GSW": "GS", "NYK": "NY", "NOP": "NO",
         "SAS": "SA", "PHO": "PHX", "BRK": "BKN"}


def abbr(league, name):
    return NICK[league].get(str(name or "").lower().split()[-1])


def public_games(league):
    """(away, home) -> list of (start, gk) from the public book tape, so rows join to the chart's game."""
    out = {}
    for f in glob.glob(str(ROOT / "data" / "book_tape" / league / "*.jsonl")):
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            a, h = ALIAS.get(r.get("away"), r.get("away")), ALIAS.get(r.get("home"), r.get("home"))
            out.setdefault((a, h), {})[(r.get("start"), r.get("gk"))] = 1
    return {k: list(v) for k, v in out.items()}


def main_pair(quotes, kind):
    """Pick the main line (the one whose two prices are closest) among non-alternate quotes."""
    by = {}
    for q in quotes:
        key = abs(q["line"]) if kind == "sp" else q["line"]
        by.setdefault(key, []).append(q)
    best = None
    for key, qs in by.items():
        sides = {}
        for q in qs:
            sides[q["side"]] = q
        need = ("hometeam", "awayteam") if kind == "sp" else ("over", "under")
        if not all(s in sides for s in need):
            continue
        gap = abs(sides[need[0]]["odds"] - sides[need[1]]["odds"])
        if best is None or gap < best[0]:
            best = (gap, sides)
    return best[1] if best else None


def build_row(league, quotes):
    pre = SPORT[league] + "_"
    by = {"ml": [], "sp": [], "tot": []}
    for q in quotes:
        if q.get("player_id") or q.get("alternate") or q.get("live"):
            continue
        k = q["market_key"]
        if k == pre + "moneyline":
            by["ml"].append(q)
        elif k == pre + "points_handicap" and q.get("line") is not None:
            by["sp"].append(q)
        elif k == pre + "points" and q.get("line") is not None:
            by["tot"].append(q)
    row = {}
    ml = {q["side"]: q["odds"] for q in by["ml"]}
    row["ml"] = [ml["awayteam"], ml["hometeam"]] if "awayteam" in ml and "hometeam" in ml else None
    s = main_pair(by["sp"], "sp")
    row["sp"] = [s["hometeam"]["line"], s["hometeam"]["odds"], s["awayteam"]["odds"]] if s else None
    t = main_pair(by["tot"], "tot")
    row["tot"] = [t["over"]["line"], t["over"]["odds"], t["under"]["odds"]] if t else None
    if not any(row.values()):
        return None
    row["_t"] = max(q["updated_at"] for q in quotes) // 1000
    return row


def convert(league):
    pub = public_games(league)
    last, rows = {}, []
    for f in sorted(glob.glob(str(SS / league / "*.jsonl.gz"))):
        for line in gzip.open(f, "rt", encoding="utf-8"):
            p = json.loads(line)
            groups = {}
            for q in p["quotes"]:
                b = BOOKS.get(q["book"])
                if b:
                    groups.setdefault((q["event_id"], b), []).append(q)
            for (ev, book), qs in groups.items():
                q0 = qs[0]
                away, home = abbr(league, q0["away"]), abbr(league, q0["home"])
                start = int(datetime.fromisoformat(q0["starts_at"].replace("Z", "+00:00")).timestamp())
                cand = [c for c in pub.get((away, home), []) if c[0] is not None and abs(c[0] - start) < 6 * 3600]
                if not away or not home or not cand:
                    continue   # no public-tape game to attach to, so the chart could not show it anyway
                r = build_row(league, qs)
                if not r:
                    continue
                sig = json.dumps([r["ml"], r["sp"], r["tot"]])
                if last.get((ev, book)) == sig:
                    continue
                last[(ev, book)] = sig
                out = {"t": r.pop("_t"), "src": "ss", "away": away, "home": home, "start": cand[0][0], "book": book, **r}
                if cand[0][1]:
                    out["gk"] = cand[0][1]
                rows.append(out)
    by_month = {}
    for r in sorted(rows, key=lambda x: x["t"]):
        by_month.setdefault(datetime.fromtimestamp(r["t"], timezone.utc).strftime("%Y-%m"), []).append(r)
    for m, rs in by_month.items():
        out = SS / "book_tape" / league / f"{m}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rs))
    print(f"{league}: {len(rows)} rows -> {SS / 'book_tape' / league}", flush=True)


if __name__ == "__main__":
    for lg in (sys.argv[1:] or ["nfl", "nba"]):
        convert(lg)
