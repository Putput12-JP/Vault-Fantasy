#!/usr/bin/env python3
"""Is the proven-sharps grading stale, and should the card build start the record job?

The record job (.github/workflows/pm-record.yml) grades every frozen card by Polymarket resolution and rebuilds
pm_record/cards_record.json. GitHub's scheduler skips scheduled runs, so on 2026-11-24 it ran four times in 24 hours and plays that
started hours earlier stayed "Awaiting result". The card build (pm-cards.yml) runs every 10 minutes, so it calls this script and, when
the answer is "stale and allowed", starts the record job with `gh workflow run`.

Stale means ALL of:
  1. the newest `generated` in pm_record/cards_record.json is more than 45 minutes old (or is missing: the age is unknown),
  2. at least one shown frozen play (key `card|group|all|sf`, NBA, NFL or CBB, the plays the Frozen plays box lists) started more than 2.5 hours
     ago and no more than 24 hours ago (older open rows are not a grading-lag case and would keep this true forever), is not flagged
     postponed, and has no graded result row (a `result` row with the same key in pm_record/cards/<sport>/<month>.jsonl; the same key rule as
     the Record page, sharp-money/sharps-v2/sv2-record.js rec.frozenList: any result row for the key settles it).
Stale still does not dispatch when:
  3. a pm-record run is queued or in progress (it is about to refresh the file), or
  4. 3 or more workflow_dispatch runs of pm-record.yml were created in the last 6 hours (a loop guard: an overdue play that Polymarket has not
     resolved yet must not start a run every 10 minutes), or
  5. the run list could not be read (the guard cannot be checked, so nothing is started).

Output: one JSON object on stdout with the decision and every number behind it, one log line on stderr. Exit code: 10 = stale and allowed to
dispatch, 0 = nothing to do (fresh, no overdue play, queued run or loop guard), 3 = could not decide (a warning in the workflow, never a failure
of the build). Sharp money is context only: this reads no signal, only timestamps and result keys.
"""
import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys

STALE_AFTER = 45 * 60            # cards_record.json `generated` older than this is stale
OVERDUE_AFTER = int(2.5 * 3600)  # a shown play whose game started more than this long ago should have a result
OVERDUE_WINDOW = 24 * 3600       # ... and no more than this long ago
GUARD_WINDOW = 6 * 3600          # loop guard: dispatches counted over this window
GUARD_MAX = 3                    # ... a 4th is refused
SHOWN_SPORTS = ("nba", "nfl", "cbb")   # CFB shows no size, so it has no shown play
ACTIVE = ("queued", "in_progress", "waiting", "requested", "pending")   # every run status except completed
EXIT_DISPATCH, EXIT_NONE, EXIT_UNKNOWN = 10, 0, 3


def is_shown_key(key):
    return isinstance(key, str) and key.endswith("|all|sf")   # the Record page rule: sv2-record.js SHOWN_KEY /\|all\|sf$/


def shown_candidates(live_locked, record_open):
    """Shown plays still without a result as far as the two published lists know (live.json `locked`, cards_record.json `open`), deduped by key.
    Each is {key, sport, gst, postponed}. A row without a numeric gst can never be called overdue, so it is dropped."""
    out, seen = [], set()
    for src in (live_locked, record_open):
        for r in src or []:
            if not isinstance(r, dict) or not is_shown_key(r.get("key")) or r["key"] in seen:
                continue
            if r.get("play") not in (None, "sf") or str(r.get("sport", "")).lower() not in SHOWN_SPORTS:
                continue
            g = r.get("gst")
            if isinstance(g, bool) or not isinstance(g, (int, float)):
                continue
            seen.add(r["key"])
            out.append({"key": r["key"], "sport": str(r["sport"]).lower(), "gst": g, "postponed": r.get("postponed") is True})
    return out


def parse_time(s):
    """GitHub's ISO time ('2026-11-24T16:39:12Z') as unix seconds, None when unreadable."""
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def assess(now, generated, candidates, result_keys):
    """Steps 1 and 2: the numbers and whether the grading looks stale. No GitHub call."""
    age = None if isinstance(generated, bool) or not isinstance(generated, (int, float)) else now - generated
    open_ = [c for c in candidates if not c["postponed"] and c["key"] not in result_keys]
    overdue = [c for c in open_ if OVERDUE_AFTER < now - c["gst"] <= OVERDUE_WINDOW]
    o = {"now": int(now), "generated": generated if age is not None else None,
         "generated_age_min": round(age / 60, 1) if age is not None else None,
         "frozen_shown_open": len(candidates), "overdue_ungraded": len(overdue), "not_yet_overdue": len(open_) - len(overdue),
         "oldest_overdue_hours": round(max(now - c["gst"] for c in overdue) / 3600, 1) if overdue else None,
         "dispatches_6h": None, "active_runs": None, "stale": False, "dispatch": False, "reason": ""}
    if not candidates:
        o["reason"] = "no frozen shown plays waiting for a result"
    elif not overdue:
        o["reason"] = "no shown play started more than 2.5 hours ago without a result"
    elif age is not None and age <= STALE_AFTER:
        o["reason"] = "fresh: cards_record.json was generated %.1f minutes ago (limit 45)" % (age / 60)
    else:
        o["stale"] = True
        o["reason"] = "stale: %d overdue shown play%s, record %s" % (
            len(overdue), "" if len(overdue) == 1 else "s", "has no generated time" if age is None else "%.1f minutes old" % (age / 60))
    return o


def guard(o, now, runs):
    """Steps 3 to 5 on a stale assessment. `runs` is None when the run list could not be read, else [{createdAt, status, event}]."""
    o = dict(o)
    if runs is None:
        o["reason"] = "stale, but the pm-record run list could not be read, so nothing was started"
        return o
    active = [r for r in runs if str(r.get("status", "")).lower() in ACTIVE]
    disp = [r for r in runs if r.get("event") == "workflow_dispatch" and (parse_time(r.get("createdAt")) or 0) > now - GUARD_WINDOW]
    o["active_runs"], o["dispatches_6h"] = len(active), len(disp)
    if active:
        o["reason"] = "stale, but a pm-record run is already %s" % str(active[0].get("status")).replace("_", " ")
    elif len(disp) >= GUARD_MAX:
        o["reason"] = "stale, but %d dispatches in the last 6 hours already (limit %d)" % (len(disp), GUARD_MAX)
    else:
        o["dispatch"] = True
    return o


def decide(now, generated, candidates, result_keys, runs):
    """The whole decision as a pure function (runs: see guard)."""
    o = assess(now, generated, candidates, result_keys)
    return guard(o, now, runs) if o["stale"] else o


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def result_keys_from(data_dir, sports=SHOWN_SPORTS):
    """Keys with a `result` row anywhere in pm_record/cards/<sport>/*.jsonl."""
    keys = set()
    for sp in sports:
        for path in glob.glob(os.path.join(data_dir, "pm_record", "cards", sp, "*.jsonl")):
            try:
                with open(path) as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(r, dict) and r.get("kind") == "result" and isinstance(r.get("key"), str):
                            keys.add(r["key"])
            except OSError:
                continue
    return keys


def gh_runs(workflow, gh="gh"):
    """The recent runs of one workflow as [{createdAt, status, event}], None when a gh call fails or prints something unreadable.
    Two calls: the dispatch history (event filter, 20 newest) and the live runs (any event, 20 newest)."""
    def call(extra):
        try:
            p = subprocess.run([gh, "run", "list", "--workflow", workflow, *extra, "--limit", "20", "--json", "createdAt,status,event"],
                               capture_output=True, text=True, timeout=60)
            if p.returncode != 0:
                return None
            j = json.loads(p.stdout or "[]")
            return j if isinstance(j, list) else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
    d, a = call(["--event", "workflow_dispatch"]), call([])
    if d is None or a is None:
        return None
    seen, out = set(), []
    for r in d + a:      # one run can be in both lists: count it once
        k = (r.get("createdAt"), r.get("event"), r.get("status"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def log_line(o):
    return ("grading freshness: %s | record age %s min | overdue %s of %s open shown plays | dispatches in 6h %s | active runs %s | %s"
            % ("STALE" if o["stale"] else "ok", o["generated_age_min"], o["overdue_ungraded"], o["frozen_shown_open"],
               o["dispatches_6h"], o["active_runs"], "DISPATCH pm-record.yml" if o["dispatch"] else "no dispatch (" + o["reason"] + ")"))


def main(argv=None, runs_fn=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", required=True, help="live/live.json from this build (its `locked` list)")
    ap.add_argument("--data-dir", required=True, help="checkout of pm-holders-data (pm_record/ inside)")
    ap.add_argument("--workflow", default="pm-record.yml")
    ap.add_argument("--gh", default="gh")
    ap.add_argument("--now", type=float, default=None, help="unix seconds, for tests")
    a = ap.parse_args(argv)
    now = a.now if a.now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    try:
        live = read_json(a.live) or {}
        rec = read_json(os.path.join(a.data_dir, "pm_record", "cards_record.json")) or {}
        o = assess(now, rec.get("generated"), shown_candidates(live.get("locked"), rec.get("open")), result_keys_from(a.data_dir))
        if o["stale"]:      # GitHub is asked only when everything else says stale
            o = guard(o, now, (runs_fn or (lambda: gh_runs(a.workflow, a.gh)))())
    except Exception as e:   # never break the card build
        print(json.dumps({"stale": None, "dispatch": False, "reason": "could not decide: %s" % e}))
        print("grading freshness: could not decide (%s)" % e, file=sys.stderr)
        return EXIT_UNKNOWN
    print(json.dumps(o, sort_keys=True))
    print(log_line(o), file=sys.stderr)
    if o["stale"] and o["active_runs"] is None:
        return EXIT_UNKNOWN
    return EXIT_DISPATCH if o["dispatch"] else EXIT_NONE


if __name__ == "__main__":
    sys.exit(main())
