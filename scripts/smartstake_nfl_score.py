#!/usr/bin/env python3
"""Score the SmartStake NFL player-prop closes against what happened. LOCAL ONLY.

  python3 scripts/smartstake_nfl_score.py [--min-books 3] [--write]

For every NFL player prop on the local tape (data/smartstake/nfl/*.jsonl.gz), this takes each book's LAST read before
kickoff, at one shared line (the line the most books priced two-way), and asks: what chance did you give the over?
That chance is scored against the nflverse box score with log loss and Brier, the same scoring as
scripts/compare_prop_closes.py (whose `single` and `pair` it reuses, bootstrap CI and the n-of-150 rule included).

It answers three questions, each reported with its sample size:
  1. Is the multi-book SmartStake consensus a closer yardstick than one book (FanDuel, DraftKings)?
  2. Do the sharper-leaning books (Circa, Bookmaker, Novig, ProphetX) close nearer the truth than the soft ones?
  3. Pick'em apps (PrizePicks, Underdog, ParlayPlay): when their line sits where >= 3 sportsbooks also posted that exact
     line, which side does the consensus lean to, and how often did the lean hit? Context only, no payout claim.
Plus the max_bet each exchange quoted at its close, kept as a feature for later (no gate).

Nothing is published: output goes under data/smartstake/ (gitignored). SmartStake's terms allow internal research and
backtests only. Games that have not settled yet are counted as waiting, never guessed.
"""
import argparse
import glob
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from prop_close_lib import devig, log_loss, brier, nkey  # noqa: E402
from compare_prop_closes import single, pair, MIN_N  # noqa: E402
from smartstake_to_book_tape import abbr  # noqa: E402

# SmartStake market -> settle_bets market (the nflverse column map lives in settle_bets.COL)
MARKET = {
    "receptions": "rec", "receiving_yards": "rec_yd", "rushing_yards": "rush_yd", "rushing_attempts": "rush_att",
    "rushing_receiving_yards": "rush_rec_yd", "passing_yards": "pass_yd", "passing_attempts": "pass_att",
    "passing_completions": "pass_cmp", "passing_touchdowns": "pass_td", "passing_rushing_yards": "pass_rush_yd",
}
PREFIX = "football_player_"
SHARP = {"circa", "bookmaker", "novig", "prophetx"}
LADDER = {"kalshi", "polymarket", "polymarket_us"}          # strikes, not a main line
PICKEM = {"prizepicks", "underdog_dfs", "parlayplay"}
SS = os.path.join(ROOT, "data", "smartstake")
MAX_ODDS = 500                                              # a main line sits near even; wider is a skewed ladder rung


def scan(league="nfl"):
    """reads[(event, player, market)] = {"ko": ms, "name": str, "home": str, "books": {book: {line: reading}}, "pe": {app: line}}"""
    reads = {}
    for f in sorted(glob.glob(os.path.join(SS, league, "*.jsonl.gz"))):
        for raw in gzip.open(f, "rt", encoding="utf-8"):
            p = json.loads(raw)
            for q in p["quotes"]:
                if not q.get("player_id") or q.get("live") or q.get("line") is None or not q["market_key"].startswith(PREFIX):
                    continue
                mk = MARKET.get(q["market_key"][len(PREFIX):])
                if not mk or not q.get("participant") or q["side"] not in ("over", "under"):
                    continue
                ko = int(datetime.fromisoformat(q["starts_at"].replace("Z", "+00:00")).timestamp() * 1000)
                if q["updated_at"] >= ko or p["t"] >= ko:    # a read at or after kickoff is live, not a close
                    continue
                key = (q["event_id"], nkey(q["participant"]), mk)
                e = reads.setdefault(key, {"ko": ko, "name": q["participant"], "home": q["home"], "away": q["away"], "books": {}, "pe": {}})
                if q["book"] in PICKEM:
                    e["pe"][q["book"]] = q["line"]
                    continue
                cell = e["books"].setdefault(q["book"], {}).setdefault(q["line"], {})
                if q["updated_at"] >= cell.get("t", 0) or q["side"] not in cell:
                    cell[q["side"]] = q["odds"]
                    cell["t"] = max(cell.get("t", 0), q["updated_at"])
                    cell["mb"] = q.get("max_bet") if q.get("max_bet") is not None else cell.get("mb")
    return reads


def shared_line(e, min_books):
    """The line the most non-ladder books priced two-way within +/-MAX_ODDS; ties go to the line nearest an even price."""
    by = defaultdict(list)
    for b, lines in e["books"].items():
        if b in LADDER:
            continue
        for ln, c in lines.items():
            if "over" in c and "under" in c and abs(c["over"]) <= MAX_ODDS and abs(c["under"]) <= MAX_ODDS:
                by[ln].append((b, devig(c["over"], c["under"]), c.get("mb")))
    best = None
    for ln, bs in by.items():
        bs = [x for x in bs if x[1] is not None]
        if len(bs) < min_books:
            continue
        gap = abs(sum(x[1] for x in bs) / len(bs) - 0.5)
        if best is None or (len(bs), -gap) > (len(best[1]), -best[2]):
            best = (ln, bs, gap)
    return (best[0], best[1]) if best else (None, [])


def kickoff_week(ko_ms, home_abbr, kickoffs):
    for (season, week, team), iso in kickoffs.items():
        if team == home_abbr:
            t = datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
            if abs(t - ko_ms) < 2 * 3600 * 1000:
                return season, week
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-books", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest-week", type=int, help="grade against this week's box score instead (code-path test only, results invalid)")
    a = ap.parse_args()
    import settle_bets
    reads = scan()
    kickoffs = settle_bets.load_kickoffs()
    actuals = settle_bets.load_actuals(2026)
    byname = {nkey(n): n for n in actuals}

    rs, pe_rows, waiting, nomatch, mb = [], [], 0, 0, defaultdict(list)
    for (ev, pk, mk), e in reads.items():
        line, bs = shared_line(e, a.min_books)
        hm = abbr("nfl", e["home"])
        season, week = kickoff_week(e["ko"], hm, kickoffs)
        wk = a.selftest_week or week
        nm = byname.get(pk)
        actual = settle_bets.actual_for(actuals, nm, wk, mk) if (nm and wk) else None
        if not nm or not wk:
            nomatch += 1
        for b, _, m in bs:
            if m:
                mb[b].append(m)
        if actual is None:
            waiting += 1
            continue
        if line is not None:
            if abs(actual - line) > 1e-9:
                p = {SS_NAME.get(b, b): v for b, v, _ in bs}
                sharp = [v for b, v, _ in bs if b in SHARP]
                soft = [v for b, v, _ in bs if b not in SHARP]
                p["SS consensus"] = sum(v for _, v, _ in bs) / len(bs)
                if len(sharp) >= 2:
                    p["SS sharp"] = sum(sharp) / len(sharp)
                if len(soft) >= 2:
                    p["SS soft"] = sum(soft) / len(soft)
                rs.append({"key": f"{ev}|{pk}|{mk}", "market": mk, "won_over": actual > line, "p": p})
        for app, pl in e["pe"].items():                           # pick'em: consensus at the app's exact line
            cell = [(b, devig(c["over"], c["under"])) for b, lines in e["books"].items() if b not in LADDER
                    for ln, c in lines.items() if ln == pl and "over" in c and "under" in c and abs(c["over"]) <= MAX_ODDS and abs(c["under"]) <= MAX_ODDS]
            cell = [(b, v) for b, v in cell if v is not None]
            if len(cell) >= a.min_books and abs(actual - pl) > 1e-9:
                pe_rows.append({"app": app, "market": mk, "p": sum(v for _, v in cell) / len(cell), "won_over": actual > pl, "books": len(cell)})

    names = ["SS consensus", "SS sharp", "SS soft", "FanDuel", "DraftKings", "Circa", "Bookmaker", "Novig", "ProphetX", "Caesars", "Fanatics", "BetMGM", "BetRivers", "bet365"]
    res = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "selftest": bool(a.selftest_week),
        "props_on_tape": len(reads), "graded": len(rs), "waiting_for_box_score": waiting, "no_player_or_week_match": nomatch,
        "min_n": MIN_N, "by_book": {b: single(rs, b) for b in names},
        "pairs": [pair(rs, x, y) for x, y in [("SS consensus", "FanDuel"), ("SS consensus", "DraftKings"), ("SS sharp", "SS soft")]],
        "pickem": {},
        "max_bet_median": {b: sorted(v)[len(v) // 2] for b, v in mb.items() if v},
    }
    for app in sorted(PICKEM):
        xs = [x for x in pe_rows if x["app"] == app]
        lean = [x for x in xs if abs(x["p"] - 0.5) >= 0.04]
        hit = [(x["won_over"] if x["p"] > 0.5 else not x["won_over"]) for x in lean]
        res["pickem"][app] = {"lines_with_consensus": len(xs), "lean_4pt": len(lean), "lean_hit_rate": round(sum(hit) / len(hit), 4) if hit else None,
                              "mean_lean_chance": round(sum(max(x["p"], 1 - x["p"]) for x in lean) / len(lean), 4) if lean else None,
                              "verdict": f"tracking ({len(lean)} of {MIN_N})" if len(lean) < MIN_N else "enough to read"}
    print(json.dumps(res, indent=1))
    if a.selftest_week:
        print("SELFTEST: graded against week %d on purpose to exercise the code. These numbers are not results." % a.selftest_week)
    elif a.write:
        with open(os.path.join(SS, "score_nfl.json"), "w") as f:
            json.dump(res, f, indent=1)


SS_NAME = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM", "caesars": "Caesars", "fanatics": "Fanatics",
           "betrivers": "BetRivers", "bet365": "bet365", "circa": "Circa", "bookmaker": "Bookmaker", "prophetx": "ProphetX", "novig": "Novig"}

if __name__ == "__main__":
    main()
