#!/usr/bin/env python3
"""tier_record.json: the per-sport record of the play evidence tiers, published beside live.json on `pm-cards-live` (docs/side-cards.md,
"tier_record.json"). Rebuilt every run from the frozen cards and the graded rows of `pm-holders-data` (the workflow's `pmdata` checkout), point
in time: a play's tier comes from its own card at its cut (the stored v2 block on a new card, a re-derivation from stored fields on an old one,
scripts/sharps_v2/tier_history.py), never from its result.

Flat 1 unit at the stored price at the cut (a win pays 1 / price - 1, a loss -1, a push 0), variant `all`, voided plays left out. `units` is
that flat sum and `roi` is units / n as a fraction (0.081 = 8.1%), null when n is 0. This is NOT the size the page shows, and CFB (no size
shown) is a flat-1u reference only. Beside it, every tier cell carries `shadow` ({units_staked, units, roi}): the same plays at the tier-scaled
size shadow v2s-1 (plays_v2.SHADOW), each play's flat result times its size; null on the `none` bucket. Context only: a record, never a signal, never an input to Top Reads, SM_GATE or an agree total.

  python3 -I scripts/sharps_v2/tier_record.py --data-dir pmdata --book-tape data/book_tape --out live/tier_record.json [--data-ref SHA]
"""
import argparse, datetime as dt, json, os, sys, time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
import tier_history as TH  # noqa: E402
from sharps_v2 import plays_v2 as P2  # noqa: E402

TIERS = ("clear", "mixed", "thin", "contested", "none")           # none = not derivable at the cut; never folded into a tier
SPORTS = ("nba", "nfl", "cfb", "cbb")
ALL_SPORTS = ("nba", "nfl", "cbb")                                  # `all`: the sports that show a size (the page headline); CFB is reference only
GROUPS = ("ml", "spread", "total")
SINCE_NOV16 = int(dt.datetime(2026, 11, 16, 0, 0, tzinfo=ZoneInfo("America/Chicago")).timestamp())   # 2026-11-16 12:00 AM Central
FORWARD_NOTE = "forward starts at the first logged lock"
RULE = ("Evidence tier rule v2t-1 (docs/sharps-v2-plays-spec.md), read from each play's own card at its cut. Flat 1u at the stored price at the "
        "cut, not the size the page shows. in_sample = every play cut before the first row of the forward tier log (the tier rule was written "
        "after those results, so these tiers are derived after the fact). forward = only plays whose tier was logged at lock by the live builder, "
        "joined to the graded record; it starts at the first logged lock. since_nov16 is informational only: plays cut on or after the Nov 16 "
        "shadow rules, tier still derived after the fact, never forward. none = not derivable at the cut, never counted in a tier. "
        "A record, not a signal.")
SHADOW_NOTE = ("shadow = the tier-scaled size rule %s (Clear 1.5u, Mixed 1u, Thin 0.5u, Contested 0.5u, CFB 0; an ordering by evidence, not fitted to results) "
               "beside the flat 1u. Its units are each play's flat result times its shadow size, staked is the sum of the sizes, roi = units / staked (null "
               "at 0 staked). The none bucket has shadow null. The page still shows the flat 1u." % P2.SHADOW_RULE)


def shadow_cell(ps, tier):
    """The same plays at the rule v2s-1 size: `units` = each play's flat result (the unit result at its own stored price) times its shadow size,
    `units_staked` = the sum of the sizes (a push counts as staked and returns 0, as in the flat n), `roi` = units / staked, null at 0 staked.
    None for the none bucket: a play with no tier has no shadow size, so nothing is staked or won (null, never 0)."""
    if tier == "none":
        return None
    sized = [(p, P2.shadow_units(p["sport"], tier)) for p in ps]
    sized = [(p, u) for p, u in sized if u is not None]
    staked = sum(u for _, u in sized)
    units = round(sum(p["flat"] * u for p, u in sized), 2)
    return {"units_staked": round(staked, 2), "units": units, "roi": round(units / staked, 4) if staked else None}


def cell(ps, tier=None):
    n = len(ps)
    units = round(sum(p["flat"] for p in ps), 2)
    out = {"w": sum(p["res"] == "win" for p in ps), "l": sum(p["res"] == "loss" for p in ps), "p": sum(p["res"] == "push" for p in ps),
           "n": n, "units": units, "roi": round(units / n, 4) if n else None}
    if tier is not None:
        out["shadow"] = shadow_cell(ps, tier)
    return out


def tier_block(ps, t, first_cut):
    """`ps`: plays with a `forward` flag (their tier was logged at lock). in_sample = cut strictly before the first logged lock (all plays when
    there is no log); forward = logged plays only, with the tier the log holds; since_nov16 is informational."""
    sub = [p for p in ps if p["tier"] == t]
    fwd = [p for p in ps if p.get("forward") and p["tier"] == t]
    return {"all": cell(sub, t), "in_sample": cell([p for p in sub if first_cut is None or p["cut"] < first_cut], t), "forward": cell(fwd, t),
            "since_nov16": cell([p for p in sub if p["cut"] >= SINCE_NOV16], t),
            "by_market": {g: cell([p for p in sub if p["group"] == g], t) for g in GROUPS}}


def shape(ps, first_cut):
    return {"tiers": {t: tier_block(ps, t, first_cut) for t in TIERS}}


def logged_rows(reader):
    """{graded sf key: row} from pm_cards/<sport>/v2_tier/*.jsonl (the forward tier log the live builder writes at lock)."""
    out = {}
    for path in reader.ls("pm_cards"):
        if "/v2_tier/" in path and path.endswith(".jsonl"):
            for line in (reader.show(path) or "").splitlines():
                try:
                    r = json.loads(line)
                    out[r["key"]] = r
                except (ValueError, KeyError, TypeError):
                    continue
    return out


def mark_forward(ps, logged):
    """The plays whose key is in the log, with the tier the log holds (a null tier is `none`); everything else is not forward."""
    out = []
    for p in ps:
        row = logged.get(p["key"])
        out.append(dict(p, forward=True, tier=row.get("tier") or "none") if row else dict(p, forward=False))
    return out


def build(ps, built, data_ref, logged=None):
    logged = logged or {}
    ps = mark_forward(ps, logged)
    cuts = [r["cut"] for r in logged.values() if isinstance(r.get("cut"), (int, float))]
    first_cut = min(cuts) if cuts else None
    n_fwd = sum(1 for p in ps if p["forward"])
    return {"built": built, "data_ref": data_ref, "rule": RULE, "units_basis": "flat 1u at the stored price at the cut", "shadow_rule": P2.SHADOW_RULE, "shadow_note": SHADOW_NOTE,
            "first_logged_cut": first_cut, "logged_rows": len(logged), "forward_graded": n_fwd,
            "forward_note": FORWARD_NOTE if not n_fwd else "forward = plays whose tier was logged at lock by the live builder",
            "since_nov16_from": SINCE_NOV16, "all_sports": list(ALL_SPORTS),
            "sports": {sp: shape([p for p in ps if p["sport"] == sp], first_cut) for sp in SPORTS},
            "all": shape([p for p in ps if p["sport"] in ALL_SPORTS], first_cut)}


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
    doc = build(ps, int(a.now or time.time()), ref, logged_rows(rd))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    payload = json.dumps(doc, separators=(",", ":"))
    with open(a.out + ".tmp", "w") as f:
        f.write(payload)
    os.replace(a.out + ".tmp", a.out)
    print("tier_record.json %.1f KB, %d plays" % (len(payload) / 1000, len(ps)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
