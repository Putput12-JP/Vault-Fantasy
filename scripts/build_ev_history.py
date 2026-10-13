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
import json
import os
import re
import subprocess
import sys


_NUM = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def _js_num(n):
    """String(n) for a finite float, as JavaScript prints it (1e+21, 1e-7, -0 -> 0)."""
    if n == 0:
        return "0"
    sign = "-" if n < 0 else ""
    mant, _, exp = repr(abs(n)).partition("e")
    whole, _, frac = mant.partition(".")
    if frac == "0":
        frac = ""
    digits = (whole + frac).lstrip("0")
    # decimal point position relative to the start of digits
    pt = len(whole) + int(exp or 0) - (len(whole + frac) - len((whole + frac).lstrip("0")))
    digits = digits.rstrip("0") or "0"
    k = len(digits)
    if k <= pt <= 21:
        out = digits + "0" * (pt - k)
    elif 0 < pt <= 21:
        out = digits[:pt] + "." + digits[pt:]
    elif -6 < pt <= 0:
        out = "0." + "0" * -pt + digits
    else:
        e = pt - 1
        out = digits[0] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + out


def line_key(x):
    """Canonical line text: 3, 3.0 and "3.0" all give "3". Mirrors evLn() in sharp-money/index.html."""
    if x is None or x == "":
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    n = None
    if isinstance(x, (int, float)):
        try:
            n = float(x)
        except OverflowError:
            n = float("inf")
    elif isinstance(x, str) and x.strip() != "" and _NUM.fullmatch(x.strip()):
        n = float(x.strip())
    if n is None:
        return str(x)
    if n != n:
        return "NaN"
    if n in (float("inf"), float("-inf")):
        return "Infinity" if n > 0 else "-Infinity"
    return _js_num(n)


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
    """Missing file: start fresh. Broken JSON or wrong shape: ::error:: and exit, file untouched."""
    if not (path and os.path.exists(path)):
        return {}
    try:
        with open(path) as f:
            h = json.load(f)
    except (ValueError, OSError) as e:
        print("::error::ev history %s is unreadable (%s); left untouched" % (path, e))
        sys.exit(1)
    if not isinstance(h, dict) or not isinstance(h.get("entries"), list):
        print("::error::ev history %s has the wrong shape (expected an object with an entries list); left untouched" % path)
        sys.exit(1)
    entries = {}
    skipped = 0
    for e in h["entries"]:
        if not isinstance(e, dict):
            skipped += 1
            continue
        if "key" not in e:
            if not all(k in e for k in ("game", "m", "side", "line")):
                skipped += 1
                continue
            e["key"] = key_of(e)
        elif all(k in e for k in ("game", "m", "side")):
            e["key"] = key_of(e)
        entries.setdefault(e["key"], e)
    if skipped:
        print("::warning::ev history %s: skipped %d unrepairable entries" % (path, skipped))
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
