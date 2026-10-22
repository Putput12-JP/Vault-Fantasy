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
import re
import subprocess
import sys


# Number(string) in JS: ASCII digits only, 0x/0b/0o integers take no sign, trimmed by JS whitespace (not str.strip()).
_NUM = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?", re.ASCII)
_RADIX = re.compile(r"0(?:[xX]([0-9a-fA-F]+)|[bB]([01]+)|[oO]([0-7]+))", re.ASCII)
_JS_WS = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def _js_number(s):
    """Number(s) for a string, or None for NaN. Empty after trimming is the caller's job (evLn never gets there)."""
    t = s.strip(_JS_WS)
    m = _RADIX.fullmatch(t)
    if m:
        for grp, base in ((m.group(1), 16), (m.group(2), 2), (m.group(3), 8)):
            if grp is not None:
                try:
                    return float(int(grp, base))
                except OverflowError:
                    return float("inf")
    if _NUM.fullmatch(t):
        return float(t)
    return None


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
    elif isinstance(x, str) and x.strip(_JS_WS) != "":
        n = _js_number(x)
        if n is not None and (n != n or n in (float("inf"), float("-inf"))):
            n = None  # JS: not finite, so evLn falls back to String(x), the raw text
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


class BrokenFile(Exception):
    pass


def load_history(path):
    """Missing file: start fresh. Broken JSON or wrong shape: BrokenFile, file untouched."""
    if not (path and os.path.exists(path)):
        return {}
    try:
        with open(path) as f:
            h = json.load(f)
    except (ValueError, OSError) as e:
        raise BrokenFile("ev history %s is unreadable (%s)" % (path, e))
    if not isinstance(h, dict) or not isinstance(h.get("entries"), list):
        raise BrokenFile("ev history %s has the wrong shape (expected an object with an entries list)" % path)
    entries = {}
    skipped = 0
    for e in h["entries"]:
        if not isinstance(e, dict):
            skipped += 1
            continue
        if "key" not in e:
            if not all(k in e for k in ("game", "m", "side")):
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


def pending_paths(history):
    """Sidecars next to the history file: ev_alert_history.pending.json and ev_alert_history.pending.<ts>.json."""
    d = os.path.dirname(os.path.abspath(history))
    stem = os.path.splitext(os.path.basename(history))[0]
    return [os.path.join(d, n) for n in sorted(os.listdir(d))
            if n.startswith(stem + ".pending") and n.endswith(".json")]


def write_pending(history, rows):
    """Park graded rows beside a broken history file. Merges into an existing healthy pending file,
    else a timestamped one when the pending file is itself broken. Returns the path written."""
    d = os.path.dirname(os.path.abspath(history))
    stem = os.path.splitext(os.path.basename(history))[0]
    path = os.path.join(d, stem + ".pending.json")
    try:
        entries = load_history(path)
    except BrokenFile:
        # Microseconds, and the Actions run id when set, so two runs in the same second do not share a name.
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = os.environ.get("GITHUB_RUN_ID")
        if run_id:
            stamp = "%s.%s" % (stamp, run_id)
        path = os.path.join(d, "%s.pending.%s.json" % (stem, stamp))
        entries = {}
    for r in rows:
        entries.setdefault(r["key"], r)
    write_history(entries, path)
    return path


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
    try:
        entries = load_history(a.history)
    except BrokenFile as e:
        entries = None
        broken = e
    # With a broken history, graded rows still get collected, into a fresh map that goes to the pending sidecar.
    before = len(entries) if entries is not None else 0
    work = entries if entries is not None else {}
    scanned = 0
    if a.git_ref:
        shas = git(a.repo, "log", "--format=%H", a.git_ref, "--", "data.json").decode().split()
        for sha in reversed(shas):
            try:
                d = json.loads(git(a.repo, "show", "%s:data.json" % sha))
            except Exception as e:
                print("skip %s: %s" % (sha[:8], e), file=sys.stderr)
                continue
            merge(work, d.get("alerts") or [])
            scanned += 1
    for path in a.data:
        try:
            with open(path) as f:
                d = json.load(f)
        except Exception as e:
            print("skip %s: %s" % (path, e), file=sys.stderr)
            continue
        merge(work, d.get("alerts") or [])
        scanned += 1
    if entries is None:
        saved = "no new graded rows to save"
        if work:
            dest = write_pending(a.history, list(work.values()))
            total = len(load_history(dest))
            saved = "%d graded rows saved to %s (%d pending total)" % (len(work), os.path.basename(dest), total)
        print("::error::%s; left untouched. %s" % (broken, saved))
        sys.exit(1)
    # Healthy run: fold in any rows parked by an earlier broken run, then drop those files.
    # A pending file that still cannot be read is kept, and the run goes red while it exists.
    pend = pending_paths(a.history)
    folded = []
    kept = []
    for pp in pend:
        try:
            for k, row in load_history(pp).items():
                entries.setdefault(k, row)
            folded.append(pp)
        except BrokenFile as e:
            kept.append(pp)
            print("::error::%s; kept for manual repair" % e)
    write_history(entries, out)
    for pp in folded:
        os.remove(pp)
    print("scanned %d, history %d -> %d (merged %d pending files)" % (scanned, before, len(entries), len(folded)))
    if kept:
        sys.exit(1)


if __name__ == "__main__":
    main()
