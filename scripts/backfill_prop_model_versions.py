#!/usr/bin/env python3
# ============================================================================
# VAULT · PROP-MODEL VERSION HISTORY  →  data/prop_model_versions.json
#
# Settlement used to re-grade every past prop with TODAY's prop_model.json.
# Since the in-season corrections (real-line recal, projection-bias and
# in-season overlays) are fitted on settled results, that meant Weeks 1-3 were
# graded by a model that had already seen their outcomes: 432 of 2,007 Week 1-3
# grades changed (docs/retro/week-4-deep-dive.md, finding 1).
#
# The fix keeps every published model with the time it went live, so
# settle_bets.py can grade each prop with the version Vault was showing when
# the line was first graded. build_prop_projections.py appends a version on
# each refit; this script rebuilds the whole history from git, which is the
# source of truth for when each version shipped (commit time). Re-run it any
# time the history looks wrong: it is deterministic and idempotent.
#
# Needs full git history, so it runs locally (CI checkouts are shallow).
#
# Usage:
#   python3 scripts/backfill_prop_model_versions.py                 # since 2026-08-28
#   python3 scripts/backfill_prop_model_versions.py --since 2026-08-01
#   python3 scripts/backfill_prop_model_versions.py --dry
# ============================================================================
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "prop_model_versions.json")
SRC = "data/prop_model.json"

NOTE = ("Every published data/prop_model.json with the time it went live (UTC). "
        "settle_bets.py grades each prop with the version live when its line was first "
        "graded, so the record never re-grades history with a refit that saw the results. "
        "Appended by build_prop_projections.py; rebuilt from git by "
        "scripts/backfill_prop_model_versions.py.")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def iso_utc(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-08-28", help="oldest commit date to keep (YYYY-MM-DD)")
    ap.add_argument("--ref", default="HEAD", help="git ref whose history to read")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    # Oldest first. %ct = committer time: when the version landed on main.
    log = git("log", "--reverse", "--format=%H %ct", args.ref, "--", SRC).split("\n")
    since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    rows = [l.split() for l in log if l.strip()]
    # Keep the last version BEFORE --since too: it was the one live at the cutoff.
    keep, prev = [], None
    for sha, ct in rows:
        if int(ct) < since:
            prev = (sha, ct)
            continue
        keep.append((sha, ct))
    if prev:
        keep.insert(0, prev)

    versions, last = [], None
    for sha, ct in keep:
        try:
            blob = json.loads(git("show", f"{sha}:{SRC}"))
        except (subprocess.CalledProcessError, ValueError):
            print(f"[versions] {sha[:8]}: unreadable, skipped", file=sys.stderr)
            continue
        markets = blob.get("markets", blob)
        if markets == last:
            continue                       # a commit that didn't change the model
        versions.append({"from": iso_utc(ct), "sha": sha[:8], "markets": markets})
        last = markets

    out = {"note": NOTE, "versions": versions}
    for v in versions:
        print(f"[versions] {v['from']}  {v['sha']}  {len(v['markets'])} markets")
    if args.dry:
        print("[versions] --dry: not written")
        return
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"[versions] wrote {len(versions)} versions to {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
