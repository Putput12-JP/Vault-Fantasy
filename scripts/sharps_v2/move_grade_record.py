#!/usr/bin/env python3
"""move_grade_record.json: the per-sport record of the Move grade (rule mg-1, docs/sharp-movegrade-prereg.md), published beside tier_record.json and
flag_record.json on `pm-cards-live`. Rebuilt every run from the frozen cards, the graded rows and the book tape, point in time: a play's grade comes
from its own card at its cut, never from its result and never recomputed after the lock.

Slices (a play is in exactly one): a, b, c, d (the letters), against (a market-move flag fired against the play: the marker, no letter) and
unreadable (no grade: neither flag could be read at the cut, or the side did not map to a team), kept apart so it never pads D.
Where each play's grade comes from, in this order (`src`): `logged` (the `mg` of its v2_tier log row, never recomputed, even when the card's stored
flags would now give another letter), `frozen` (the card's stored v2.move_grade), `frozen_flags` (move_grade() on the card's stored v2.flags), `derived`
(move_grade() on flags re-derived from the tape rows at or before the cut, exactly as the live builder reads them). A failure is unreadable with a
warning, never a guess.
Flat 1 unit at the stored price at the cut (a win pays 1 / price - 1, a loss -1, a push 0), variant `all`, voided plays left out; `units` is that flat
sum and `roi` is units / n as a fraction, null at n = 0. NOT the size the page shows (flat 1u on NBA, NFL, CBB; none on CFB: CFB is a flat-1u
reference). Buckets exactly as flag_record.json: in_sample = cut strictly before the first forward log row that carries `mg` (all plays when none),
forward = only plays whose grade was logged at lock (`mg` on the v2_tier row) joined to the graded record, which starts at zero. Context only: a record,
never a signal, never an input to Top Reads, SM_GATE or an agree total.

  python3 -I scripts/sharps_v2/move_grade_record.py --data-dir pmdata --book-tape data/book_tape --out live/move_grade_record.json [--data-ref SHA]
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import move_grade as MG  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
from sharps_v2 import tier_record as TR  # noqa: E402

SPORTS = ("nba", "nfl", "cfb", "cbb")
ALL_SPORTS = TR.ALL_SPORTS                        # the sports that show a size (the page headline); CFB is reference only
SLICES = ("a", "b", "c", "d", "against", "unreadable")
LABEL = {"a": "A", "b": "B", "c": "C", "d": "D", "against": "moved against", "unreadable": "no grade"}
SMALL_N = TH.SMALL_N
FORWARD_NOTE = "forward starts at the first logged lock that carries the Move grade"
RULE = ("Move grade mg-1 (docs/sharp-movegrade-prereg.md), read from each play's own card at its cut. Flat 1u at the stored price at the cut, not the size the "
        "page shows. a to d are the letters, against = a market-move flag fired against the play (a marker, no letter), unreadable = no grade (neither flag "
        "readable). A play is in exactly one slice. in_sample = every play cut before the first logged lock that carries the grade (the rule was written after "
        "those results, so these grades are derived after the fact); forward = only plays whose grade was logged at lock, joined to the graded record. A record, "
        "not a signal: the grade describes what the market did and does not predict results.")


def derive_grade(c, g, side, quotes):
    """-> {"mg": the full v2.move_grade block or None, "src": ...} for the shown `side` of market `g` on stored card `c`. Order: the card's stored block
    (frozen), the card's stored flags (frozen_flags), the tape at the cut (derived). A failure is mg None with src error, never a guess."""
    m = (c.get("markets") or {}).get(g) or {}
    v2 = m.get("v2") if isinstance(m.get("v2"), dict) else None
    mine = v2 is not None and v2.get("side") == side
    if mine and isinstance(v2.get("move_grade"), dict):
        return {"mg": v2["move_grade"], "src": "frozen"}
    try:
        sides = list((m.get("sides") or {}).keys())
        norm = BSC.side_norms(g, sides, BSC.team_names(c.get("vault"), c["ev"], c["sport"])).get(side)
        if mine and isinstance(v2.get("flags"), dict):
            return {"mg": MG.move_grade(v2["flags"], g, norm, c["sport"]), "src": "frozen_flags"}
        if quotes is None:
            return {"mg": None, "src": None}
        rows, _ = quotes.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
        fl, _ = F.flags_block(rows, g, norm, c["cut"], c["sport"], None)
        return {"mg": MG.move_grade(fl, g, norm, c["sport"]), "src": "derived"}
    except Exception as e:                           # context: a bad row leaves this play unreadable, never stops the record
        print("::warning::move grade record: %s %s: %s: %s" % (c.get("ev"), g, type(e).__name__, e), file=sys.stderr)
        return {"mg": None, "src": "error"}


def with_logged(ps, logged):
    """Each play gets `forward`: True when its log row carries `mg`, and then its grade is the log's projection, read as written (an `mg` of None is a
    dropped block: unreadable). A play with no `mg` row is not forward and keeps the grade the card gave it."""
    out = []
    for p in ps:
        row = logged.get(p["key"])
        if isinstance(row, dict) and "mg" in row:
            out.append(dict(p, forward=True, mg=row["mg"] if isinstance(row["mg"], dict) else None, msrc="logged"))
        else:
            out.append(dict(p, forward=False))
    return out


def _in(p, sl):
    return MG.bucket_of(p.get("mg")) == sl


def block(ps, sl, first_cut):
    sub = [p for p in ps if _in(p, sl)]
    return {"all": TR.cell(sub), "in_sample": TR.cell([p for p in sub if first_cut is None or p["cut"] < first_cut]),
            "forward": TR.cell([p for p in sub if p.get("forward")])}


def shape(ps, first_cut):
    return {sl: block(ps, sl, first_cut) for sl in SLICES}


def build(ps, built, data_ref, logged=None):
    logged = logged or {}
    ps = with_logged(ps, logged)
    has = lambda r: isinstance(r, dict) and "mg" in r
    cuts = [r["cut"] for r in logged.values() if has(r) and isinstance(r.get("cut"), (int, float))]
    first_cut = min(cuts) if cuts else None
    n_fwd = sum(1 for p in ps if p["forward"])
    return {"built": built, "data_ref": data_ref, "rule": RULE, "mg_rule": MG.MG_RULE, "units_basis": "flat 1u at the stored price at the cut",
            "slices": list(SLICES), "first_logged_cut": first_cut, "logged_rows": sum(1 for r in logged.values() if has(r)),
            "forward_graded": n_fwd, "forward_note": FORWARD_NOTE if not n_fwd else "forward = plays whose grade was logged at lock by the live builder",
            "all_sports": list(ALL_SPORTS),
            "sports": {sp: shape([p for p in ps if p["sport"] == sp], first_cut) for sp in SPORTS},
            "all": shape([p for p in ps if p["sport"] in ALL_SPORTS], first_cut)}


def logged_rows(reader):
    """{graded sf key: row} of every v2_tier log row (the rows without `mg` are kept: they say the play is not forward for the grade)."""
    return TR.logged_rows(reader)


# ---------- the printed report (tier_history.py) ----------

def compute(ps):
    """Every number the report prints, as data: per sport (and the NBA+NFL+CBB headline and all four) and slice, the full stats (n, w-l, units, roi, se,
    CLV), the OLD record (no grade, every play) beside them, and the flag list: EVERY slice whose record improves (units above 0), with its n."""
    out = {"plays": len(ps), "old": {}, "slices": {}, "flagged": [], "src": {s: sum(1 for p in ps if p.get("msrc") == s) for s in ("frozen", "frozen_flags", "derived", "error")}}
    groups = [(sp, [p for p in ps if p["sport"] == sp]) for sp in ("nba", "nfl", "cbb", "cfb")] + [("headline", [p for p in ps if p["sport"] in ALL_SPORTS]), ("all", list(ps))]
    for name, sub in groups:
        out["old"][name] = TH.stats(sub)
        out["slices"][name] = {}
        for sl in SLICES:
            st = TH.stats([p for p in sub if _in(p, sl)])
            out["slices"][name][sl] = st
            label = {"headline": "Headline (NBA+NFL+CBB)", "all": "All four"}.get(name, name.upper() + (" (no size)" if name == "cfb" else "")) + " " + LABEL[sl]
            if st["n"] and st["units"] > 0:
                out["flagged"].append({"slice": label, "metric": "flat ROI", "n": st["n"], "small_sample": st["n"] < SMALL_N, "stats": st})
    return out


def fmt_cell(st):
    return TH.fmt(st).split("; ")[0]


def print_report(out):
    print("\nMOVE GRADE mg-1 (docs/sharp-movegrade-prereg.md): the same plays by letter, point in time; in-sample; context only; the letter describes the market and is not a bet signal")
    print("A to D = how strongly the market moved toward the play before the cut; moved against = a market-move flag fired against it (no letter); no grade = neither flag readable.")
    s = out["src"]
    print(f"Grades read from a stored card block: {s['frozen']}, from stored flags: {s['frozen_flags']}, re-derived from the tape at the cut: {s['derived']}, errors: {s['error']}.")
    for name in ("nba", "nfl", "cbb", "cfb", "headline", "all"):
        title = {"headline": "HEADLINE NBA+NFL+CBB", "all": "ALL FOUR"}.get(name, name.upper() + (" (no size shown)" if name == "cfb" else ""))
        print(f"\n{title}: OLD (no grade, every play) {fmt_cell(out['old'][name])}")
        for sl in SLICES:
            st = out["slices"][name][sl]
            if st["n"]:
                print(f"  NEW {LABEL[sl]:<14} {fmt_cell(st)}")
    print(f"\nFLAGGED FOR CLOSE MONITORING (Move grade): every slice whose record improves, with its n (tag under n={SMALL_N}); in-sample, none promoted, none a signal")
    if not out["flagged"]:
        print("  none")
    for f in out["flagged"]:
        tag = "  [small sample]" if f["small_sample"] else ""
        print(f"  {f['slice']} ({f['metric']}, n={f['n']}){tag}: {fmt_cell(f['stats'])}")


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
    ps = TH.play_rows(rd, TH.graded_rows(rd), BSC.BookTape(a.book_tape), BSC.QuoteTape(a.book_tape))
    doc = build(ps, int(a.now or time.time()), ref, logged_rows(rd))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    payload = json.dumps(doc, separators=(",", ":"))
    with open(a.out + ".tmp", "w") as f:
        f.write(payload)
    os.replace(a.out + ".tmp", a.out)
    print("move_grade_record.json %.1f KB, %d plays" % (len(payload) / 1000, len(ps)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
