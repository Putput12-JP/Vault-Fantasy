#!/usr/bin/env python3
"""Append every graded +EV alert from sharp data.json to a permanent history log.

Qualification and grading mirror evRec() in sharp-money/index.html exactly:
  - type == "behind", with m and price set
  - one alert per game|m|side|line, the earliest by ts
  - graded means result not null and not 0, and fair not null
data.json keeps only the newest 1500 alerts, so older graded alerts fall off.
This log never drops an entry: an existing key is kept as is.

Usage:
  build_ev_history.py --history H --out O --data data.json [--data more.json ...]
  build_ev_history.py --history H --out O --git-ref origin/sharp-data [--repo DIR]
    (walks every commit that touched data.json on the ref, oldest first, then the ref tip)
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys


def line_key(x):
    """Canonical line text: 3, 3.0 and "3.0" all give "3". Mirrors evLn() in sharp-money/index.html."""
    if x is None or x == "":
        return ""
    if isinstance(x, bool):
        return str(x)
    try:
        n = float(x)
    except (TypeError, ValueError):
        return str(x)
    if n != n or n in (float("inf"), float("-inf")):
        return str(x)
    return str(int(n)) if n == int(n) else repr(n)


def key_of(a):
    return "%s|%s|%s|%s" % (a.get("game"), a.get("m"), a.get("side"), line_key(a.get("line")))


def ev_rows(alerts):
    """Same selection as evRec: earliest 'behind' alert per key, then graded only."""
    first = {}
    for a in alerts:
        if a.get("type") != "behind" or not a.get("m") or a.get("price") is None:
            continue
        k = key_of(a)
        c = first.get(k)
        if c is None or a["ts"] < c["ts"]:
            first[k] = a
    out = []
    for k, a in first.items():
        r = a.get("result")
        if r is None or r == 0 or a.get("fair") is None:
            continue
        out.append({
            "key": k, "id": a.get("id"), "game": a.get("game"), "gameLbl": a.get("gameLbl"),
            "sport": a.get("sport"), "start": a.get("start"), "ts": a.get("ts"),
            "m": a.get("m"), "side": a.get("side"), "line": a.get("line"), "book": a.get("book"),
            "text": a.get("text"), "odds": a.get("price"), "fair": a.get("fair"), "ev": a.get("ev"),
            "close": a.get("close"), "clv": a.get("clv"), "result": r, "won": 1 if r > 0 else 0,
        })
    return out


def load_history(path):
    if not (path and os.path.exists(path)):
        return {}
    try:
        with open(path) as f:
            h = json.load(f)
        if not isinstance(h, dict) or not isinstance(h.get("entries"), list):
            raise ValueError("expected an object with an entries list")
        rows = h["entries"]
        if not all(isinstance(e, dict) and "key" in e for e in rows):
            raise ValueError("entries must be objects with a key")
    except (ValueError, OSError) as e:
        bad = "%s.bad-%s" % (path, datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        shutil.copy2(path, bad)
        print("::warning::ev history %s is unreadable (%s); copied to %s, starting fresh" % (path, e, bad))
        return {}
    entries = {}
    for e in rows:
        if all(k in e for k in ("game", "m", "side")):
            e["key"] = key_of(e)
        entries.setdefault(e["key"], e)
    return entries


def merge(entries, alerts):
    added = 0
    for row in ev_rows(alerts):
        if row["key"] not in entries:
            entries[row["key"]] = row
            added += 1
    return added


def write_history(entries, out):
    rows = sorted(entries.values(), key=lambda e: (e.get("start") or 0, e["key"]))
    doc = {"version": 1, "count": len(rows), "entries": rows}
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, out)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True).stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history", required=True, help="existing history file (may not exist yet)")
    p.add_argument("--out", help="where to write (default: --history)")
    p.add_argument("--data", action="append", default=[], help="data.json to feed (repeatable)")
    p.add_argument("--git-ref", help="walk every data.json commit on this ref")
    p.add_argument("--repo", default=".")
    a = p.parse_args()
    out = a.out or a.history
    entries = load_history(a.history)
    before = len(entries)
    scanned = 0
    if a.git_ref:
        shas = git(a.repo, "log", "--format=%H", a.git_ref, "--", "data.json").decode().split()
        for sha in reversed(shas):
            try:
                d = json.loads(git(a.repo, "show", "%s:data.json" % sha))
            except Exception as e:
                print("skip %s: %s" % (sha[:8], e), file=sys.stderr)
                continue
            merge(entries, d.get("alerts") or [])
            scanned += 1
    for path in a.data:
        try:
            with open(path) as f:
                d = json.load(f)
        except Exception as e:
            print("skip %s: %s" % (path, e), file=sys.stderr)
            continue
        merge(entries, d.get("alerts") or [])
        scanned += 1
    write_history(entries, out)
    print("scanned %d, history %d -> %d" % (scanned, before, len(entries)))


if __name__ == "__main__":
    main()
