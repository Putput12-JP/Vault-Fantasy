#!/usr/bin/env python3
"""tier_record.json: the per-sport record of the play evidence tiers, published beside live.json on `pm-cards-live` (docs/side-cards.md,
"tier_record.json"). Rebuilt every run from the frozen cards and the graded rows of `pm-holders-data` (the workflow's `pmdata` checkout), point
in time: a play's tier comes from its own card at its cut (the stored v2 block on a new card, a re-derivation from stored fields on an old one,
scripts/sharps_v2/tier_history.py), never from its result.

Flat 1 unit at the stored price at the cut (a win pays 1 / price - 1, a loss -1, a push 0), variant `all`, voided plays left out. `units` is
that flat sum and `roi` is units / n as a fraction (0.081 = 8.1%), null when n is 0. This is NOT the size the page shows, and CFB (no size
shown) is a flat-1u reference only. Context only: a record, never a signal, never an input to Top Reads, SM_GATE or an agree total.

  python3 -I scripts/sharps_v2/tier_record.py --data-dir pmdata --book-tape data/book_tape --out live/tier_record.json [--data-ref SHA]
"""
import argparse, datetime as dt, json, os, sys, time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
import tier_history as TH  # noqa: E402

TIERS = ("clear", "mixed", "thin", "contested", "none")           # none = not derivable at the cut; never folded into a tier
SPORTS = ("nba", "nfl", "cfb", "cbb")
ALL_SPORTS = ("nba", "nfl", "cbb")                                  # `all`: the sports that show a size (the page headline); CFB is reference only
GROUPS = ("ml", "spread", "total")
FORWARD_FROM = int(dt.datetime(2026, 11, 16, 0, 0, tzinfo=ZoneInfo("America/Chicago")).timestamp())   # 2026-11-16 12:00 AM Central
RULE = ("Evidence tier rule v2t-1 (docs/sharps-v2-plays-spec.md), read from each play's own card at its cut. Flat 1u at the stored price at the "
        "cut, not the size the page shows. forward = cut at or after 2026-11-16 12:00 AM CT, in_sample = before it (the tier rule was written "
        "after those results). none = not derivable at the cut, never counted in a tier. A record, not a signal.")


def cell(ps):
    n = len(ps)
    units = round(sum(p["flat"] for p in ps), 2)
    return {"w": sum(p["res"] == "win" for p in ps), "l": sum(p["res"] == "loss" for p in ps), "p": sum(p["res"] == "push" for p in ps),
            "n": n, "units": units, "roi": round(units / n, 4) if n else None}


def tier_block(ps, t):
    sub = [p for p in ps if p["tier"] == t]
    return {"all": cell(sub), "forward": cell([p for p in sub if p["cut"] >= FORWARD_FROM]),
            "in_sample": cell([p for p in sub if p["cut"] < FORWARD_FROM]),
            "by_market": {g: cell([p for p in sub if p["group"] == g]) for g in GROUPS}}


def shape(ps):
    return {"tiers": {t: tier_block(ps, t) for t in TIERS}}


def build(ps, built, data_ref):
    return {"built": built, "data_ref": data_ref, "rule": RULE, "units_basis": "flat 1u at the stored price at the cut",
            "forward_from": FORWARD_FROM, "all_sports": list(ALL_SPORTS),
            "sports": {sp: shape([p for p in ps if p["sport"] == sp]) for sp in SPORTS},
            "all": shape([p for p in ps if p["sport"] in ALL_SPORTS])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", required=True, help="the pm-holders-data checkout (pm_cards/, pm_record/)")
    ap.add_argument("--book-tape", default="data/book_tape")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-ref", help="the commit hash of the data read (default: the checkout's HEAD when it is a git worktree)")
    ap.add_argument("--now", type=int)
    a = ap.parse_args(argv)
    ref = a.data_ref
    if not ref:
        import subprocess
        r = subprocess.run(["git", "-C", a.data_dir, "rev-parse", "HEAD"], capture_output=True)
        ref = r.stdout.decode().strip() or None
    rd = TH.FsReader(a.data_dir, ref)
    ps = TH.play_rows(rd, TH.graded_rows(rd), BSC.BookTape(a.book_tape))
    doc = build(ps, int(a.now or time.time()), ref)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    payload = json.dumps(doc, separators=(",", ":"))
    with open(a.out + ".tmp", "w") as f:
        f.write(payload)
    os.replace(a.out + ".tmp", a.out)
    print("tier_record.json %.1f KB, %d plays" % (len(payload) / 1000, len(ps)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
