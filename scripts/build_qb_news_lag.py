#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · QB NEWS TIMING  →  data/qb_news_lag.json
#
#  The one place the game-model backtests found an edge (2026-10-05): knowing the
#  real starting QB before the line does. Betting Vault's side at the OPEN with
#  the actual starter hit 55% (edge >= 1 pt, 2014-16 + 2023-25); with only last
#  week's starter it was 52.6%, about breakeven. So the question is speed: when
#  Vault notices a QB change (fetch-pickem-props.mjs → data/qb_news_log.json,
#  hourly), has the spread already moved, or does it move after?
#
#  For each logged change, on that team's next game:
#    before = market move in the 24 h before Vault noticed (already priced in)
#    after  = market move from when Vault noticed to the last pre-kickoff read
#  Both are signed toward the news (positive = the line moved the way a backup
#  QB, or a returning starter, should move it). A consistent `after` of a point
#  or more is a bettable window; `after` near 0 with a big `before` means Vault
#  is late and the market already knew. Lines: the 20-min book tape median
#  (data/book_tape/nfl, from Oct 2026) where it covers, else the hourly game
#  line history. Context only: nothing in the app reads this yet.
#
#  Usage:
#    python3 scripts/build_qb_news_lag.py
#    python3 scripts/build_qb_news_lag.py --backfill-git   # rebuild the event
#        log from git history of data/qb_status.json (needs full history)
# ════════════════════════════════════════════════════════════════════════════
import argparse, glob, json, os, statistics, subprocess
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
LOG = os.path.join(DATA, "qb_news_log.json")
OUT = os.path.join(DATA, "qb_news_lag.json")
# qb_status uses game-model codes (LA); line history / tape use Vault codes (LAR)
TEAM = {"LA": "LAR"}
BEFORE_H = 24
MIN_LEAD_H = 1        # an event noticed under 1 h before kickoff can't be bet in time


def ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def diff_events(prev, cur, t):
    out = []
    for team in sorted(set(prev) | set(cur)):
        a, b = prev.get(team), cur.get(team)
        if not a and b:
            out.append({"t": t, "team": team, "kind": "out", "reason": b.get("reason"),
                        "established": b.get("established"), "starter": b.get("starter")})
        elif a and not b:
            out.append({"t": t, "team": team, "kind": "back", "established": a.get("established"),
                        "starter": a.get("established")})
        elif a and b and a.get("starter") != b.get("starter"):
            out.append({"t": t, "team": team, "kind": "starter", "reason": b.get("reason"),
                        "established": b.get("established"), "starter": b.get("starter"), "was": a.get("starter")})
    return out


def backfill_from_git():
    shas = subprocess.check_output(["git", "-C", ROOT, "log", "--reverse", "--format=%H", "--", "data/qb_status.json"],
                                   text=True).split()
    prev, events = {}, []
    for sha in shas:
        try:
            blob = json.loads(subprocess.check_output(["git", "-C", ROOT, "show", f"{sha}:data/qb_status.json"], text=True))
        except Exception:
            continue
        cur = blob.get("teams") or {}
        if prev is not None and blob.get("generated"):
            events += diff_events(prev, cur, blob["generated"])
        prev = cur
    # the first version has no "before"; its teams were already out when logging began
    json.dump({"events": events, "note": "Backfilled from git history of data/qb_status.json; first version's teams excluded."},
              open(LOG, "w"), indent=1)
    print(f"[qb-news] backfilled {len(events)} events from {len(shas)} versions")


def load_tape():
    """(away, home) -> sorted [(t, median home spread)] from the 20-min book tape."""
    by = {}
    for fn in sorted(glob.glob(os.path.join(DATA, "book_tape", "nfl", "*.jsonl"))):
        for line in open(fn):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("book") in ("Open", None) or not r.get("sp") or r["sp"][0] is None:
                continue
            by.setdefault((r["away"], r["home"], r.get("start")), {}).setdefault(r["t"], []).append(float(r["sp"][0]))
    out = {}
    for (a, h, start), snaps in by.items():
        out.setdefault((a, h), []).append((start, sorted((datetime.fromtimestamp(t, timezone.utc), statistics.median(v))
                                                         for t, v in snaps.items())))
    return out


def load_history():
    """Games from the hourly line history. The snapshot keys a game once per feed
    week, so one game can sit under several keys, each live only between its
    firstSeen and lastSeen, with a sample only when the line moved. Merge them:
    {away, home, commence, recs: [(firstSeen, lastSeen, [(t, home spread)])]}."""
    h = json.load(open(os.path.join(DATA, "game_line_history.json")))
    games = h.get("games", h)
    by = {}
    for g in (games.values() if isinstance(games, dict) else games):
        if not isinstance(g, dict) or not g.get("commence") or not g.get("firstSeen"):
            continue
        ser = sorted((ts(x["ts"]), float(x["spread"])) for x in (g.get("samples") or [])
                     if x.get("ts") and x.get("spread") is not None)
        k = (g.get("away"), g.get("home"), g["commence"])
        by.setdefault(k, {"away": k[0], "home": k[1], "commence": ts(k[2]), "recs": []})["recs"].append(
            (ts(g["firstSeen"]), ts(g.get("lastSeen") or g["firstSeen"]), ser))
    return list(by.values())


def hist_at(g, t):
    """Spread at t from a record that was live at t (last move at or before t)."""
    best = None
    for f, l, ser in g["recs"]:
        if not (f <= t <= l):
            continue
        v = [(x, s) for x, s in ser if x <= t]
        if v and (best is None or v[-1][0] > best[0]):
            best = v[-1]
    return None if best is None else best[1]


def hist_close(g):
    v = sorted((x, s) for _, _, ser in g["recs"] for x, s in ser if x < g["commence"])
    return v[-1][1] if v else None


def at(series, t):
    """Last reading at or before t (book tape: a read every 20 min)."""
    v = None
    for x, s in series:
        if x > t: break
        v = s
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-git", action="store_true")
    args = ap.parse_args()
    if args.backfill_git:
        backfill_from_git()
    try:
        events = json.load(open(LOG)).get("events") or []
    except FileNotFoundError:
        print("[qb-news] no qb_news_log.json yet"); return
    tape, hist = load_tape(), load_history()
    rows = []
    for e in events:
        t0, team = ts(e["t"]), TEAM.get(e["team"], e["team"])
        nxt = sorted((g for g in hist if team in (g["home"], g["away"]) and g["commence"] > t0), key=lambda g: g["commence"])
        if not nxt:
            continue
        g = nxt[0]
        lead_h = (g["commence"] - t0).total_seconds() / 3600
        tser = None
        for start, ser in tape.get((g["away"], g["home"]), []):
            if start and abs(datetime.fromtimestamp(start, timezone.utc) - g["commence"]) < timedelta(hours=6) and ser:
                if ser[0][0] <= t0 - timedelta(hours=BEFORE_H):   # tape covers the whole window
                    tser = [(x, v) for x, v in ser if x < g["commence"]]
                break
        if tser:
            src, now_, before, close = "tape", at(tser, t0), at(tser, t0 - timedelta(hours=BEFORE_H)), tser[-1][1]
        else:
            src, now_, before, close = "history", hist_at(g, t0), hist_at(g, t0 - timedelta(hours=BEFORE_H)), hist_close(g)
        # a backup makes `team` worse: home spread up if team is home, down if away;
        # a returning starter is the reverse
        sign = (1 if team == g["home"] else -1) * (-1 if e["kind"] == "back" else 1)
        row = {**e, "game": f'{g["away"]}@{g["home"]}', "commence": g["commence"].isoformat(), "lead_h": round(lead_h, 1),
               "line_src": src, "spread_at_news": now_, "spread_24h_before": before, "spread_close": close,
               "moved_before": None if now_ is None or before is None else round(sign * (now_ - before), 2),
               "moved_after": None if now_ is None or close is None else round(sign * (close - now_), 2),
               "settled": g["commence"] < datetime.now(timezone.utc)}
        rows.append(row)
    grade = [r for r in rows if r["settled"] and r["moved_after"] is not None and r["lead_h"] >= MIN_LEAD_H
             and r["kind"] in ("out", "back")]
    summ = {"n": len(grade)}
    if grade:
        ma = [r["moved_after"] for r in grade]
        mb = [r["moved_before"] for r in grade if r["moved_before"] is not None]
        summ.update({"mean_moved_after": round(statistics.fmean(ma), 2), "share_after_1pt": round(sum(x >= 1 for x in ma) / len(ma), 3),
                     "mean_moved_before": round(statistics.fmean(mb), 2) if mb else None,
                     "verdict": ("market moves after Vault notices: a bettable window" if statistics.fmean(ma) >= 1 and len(ma) >= 20
                                 else "too few events to judge" if len(ma) < 20
                                 else "market already moved: Vault is not early")})
    out = {"generated": datetime.now(timezone.utc).isoformat(), "before_hours": BEFORE_H, "min_lead_hours": MIN_LEAD_H,
           "summary": summ, "events": rows}
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"[qb-news] {len(rows)} events on a next game, {len(grade)} graded: {summ}")
    for r in rows:
        print(f"  {r['t'][:16]} {r['team']:4s} {r['kind']:7s} {str(r.get('starter')):18s} {r['game']:9s} lead {r['lead_h']:6.1f}h "
              f"[{r['line_src']}] spread {r['spread_24h_before']} -> {r['spread_at_news']} -> {r['spread_close']} "
              f"| before {r['moved_before']} after {r['moved_after']}")


if __name__ == "__main__":
    main()
