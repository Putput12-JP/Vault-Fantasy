#!/usr/bin/env python3
"""Merge a known-good data/game_line_history.json back into the current one.

Why this exists: on 2026-10-19 20:01Z the game-history cron committed git
conflict markers into the file. snapshot-game-history.mjs read it as null and
started over, so 283 games (open lines, line samples, Pinnacle lead records)
collapsed to the 15 still on the board, and the Pinnacle spread/totals lead
scoreboard lost all of its graded games.

Usage:
    git show <good-commit>:data/game_line_history.json > /tmp/good.json
    python3 scripts/restore_game_line_history.py /tmp/good.json

Rules, per game key:
  * key only in the good file  -> keep it as it was
  * key only in the current    -> keep it as it is
  * key in both                -> open / firstSeen / earliest lead.first come
                                  from the older record, cur / lastSeen / latest
                                  lead.close come from whichever is newer, and
                                  samples are the union by timestamp (open kept,
                                  capped at 120 like the snapshot script)
Idempotent: running it twice changes nothing. No number is invented; every value
is copied from one of the two files.
"""
import json, os, sys

MAX_SAMPLES = 120
HERE = os.path.dirname(os.path.abspath(__file__))
CUR = os.path.join(HERE, "..", "data", "game_line_history.json")


def merge_lead(a, b):
    out = {}
    for mk in sorted(set(a or {}) | set(b or {})):
        out[mk] = {}
        am, bm = (a or {}).get(mk) or {}, (b or {}).get(mk) or {}
        for book in sorted(set(am) | set(bm)):
            x, y = am.get(book) or {}, bm.get(book) or {}
            r = {}
            fs = [v for v in (x.get("first"), y.get("first")) if v]
            cs = [v for v in (x.get("close"), y.get("close")) if v]
            if fs: r["first"] = min(fs, key=lambda v: v["ts"])
            if cs: r["close"] = max(cs, key=lambda v: v["ts"])
            out[mk][book] = r
    return out


def merge_rec(old, new):
    out = dict(new)
    out["open"] = old.get("open") or new.get("open")
    out["firstSeen"] = min(filter(None, (old.get("firstSeen"), new.get("firstSeen"))), default=None)
    out["lastSeen"] = max(filter(None, (old.get("lastSeen"), new.get("lastSeen"))), default=None)
    if (old.get("cur") or {}).get("ts", "") > (new.get("cur") or {}).get("ts", ""):
        out["cur"] = old["cur"]
    by = {}
    for s in (old.get("samples") or []) + (new.get("samples") or []):
        by.setdefault(s.get("ts"), s)
    samples = sorted(by.values(), key=lambda s: s.get("ts") or "")
    if out["open"] and (not samples or samples[0].get("ts") != out["open"].get("ts")):
        samples = [out["open"]] + [s for s in samples if s.get("ts") != out["open"].get("ts")]
    if len(samples) > MAX_SAMPLES:
        del samples[1:len(samples) - MAX_SAMPLES + 1]
    out["samples"] = samples
    if old.get("lead") or new.get("lead"):
        out["lead"] = merge_lead(old.get("lead"), new.get("lead"))
    return out


def main():
    good = json.load(open(sys.argv[1]))
    cur = json.load(open(CUR))
    G, C = good.get("games") or {}, cur.get("games") or {}
    games = {}
    for k in sorted(set(G) | set(C)):
        games[k] = merge_rec(G[k], C[k]) if k in G and k in C else (C.get(k) or G[k])
    cur["games"] = games
    cur["keys"] = len(games)
    with open(CUR, "w") as f:
        json.dump(cur, f, separators=(",", ":"))
    led = sum(1 for r in games.values() if r.get("lead"))
    print(f"restored: {len(G)} good + {len(C)} current -> {len(games)} games, {led} with lead records")


if __name__ == "__main__":
    main()
