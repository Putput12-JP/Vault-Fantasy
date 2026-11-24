#!/usr/bin/env python3
"""flag_record.json: the per-sport record of the market-move flags (docs/sharps-v2-flags-spec.md, rule v2f-2), published beside tier_record.json on
`pm-cards-live`. Rebuilt every run from the frozen cards, the graded rows and the book tape, point in time: a play's flags come from its own card
at its cut (the stored v2.flags on a new card, a re-derivation from the tape rows at or before the cut on an old one), never from its result.

Slices (a play can sit in several: A and C are separate flags; the Pinnacle limit is a fact, not a slice):
  a_toward, a_away    Flag A: Pinnacle's price moved toward / away from the play's side
  c_toward, c_away    Flag C: the market moved the number (spreads, totals) or the price (moneylines) toward / away
  none                at least one flag readable and neither fired toward or away (quiet)
  unreadable          neither flag readable (no tape for the game, too few books, a stale feed): kept apart so it never pads `none`
Flat 1 unit at the stored price at the cut (a win pays 1 / price - 1, a loss -1, a push 0), variant `all`, voided plays left out; `units` is that
flat sum and `roi` is units / n as a fraction, null at n = 0. NOT the size the page shows (flat 1u on NBA, NFL, CBB; none on CFB: CFB is a flat-1u
reference). Buckets exactly as tier_record.json: in_sample = cut strictly before the first forward log row that carries `mf` (all plays when none),
forward = only plays whose flags were logged at lock (`mf` on the v2_tier row) joined to the graded record, which starts at zero. Context only: a
record, never a signal, never an input to Top Reads, SM_GATE or an agree total.

  python3 -I scripts/sharps_v2/flag_record.py --data-dir pmdata --book-tape data/book_tape --out live/flag_record.json [--data-ref SHA]
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402
from sharps_v2 import tier_record as TR  # noqa: E402

SPORTS = ("nba", "nfl", "cfb", "cbb")
ALL_SPORTS = TR.ALL_SPORTS                        # the sports that show a size (the page headline); CFB is reference only
SLICES = ("a_toward", "a_away", "c_toward", "c_away", "none", "unreadable")
LABEL = {"a_toward": "A toward", "a_away": "A away", "c_toward": "C toward", "c_away": "C away", "none": "no flag fired", "unreadable": "flags unreadable"}
SMALL_N = TH.SMALL_N
FORWARD_NOTE = "forward starts at the first logged lock that carries the flags"
RULE = ("Market-move flags v2f-2 (docs/sharps-v2-flags-spec.md), read from each play's own card at its cut. Flat 1u at the stored price at the cut, not the "
        "size the page shows. A and C are separate flags, so a play can sit in more than one slice; none = a readable flag set where neither fired, "
        "unreadable = neither readable. The Pinnacle limit is a fact, not a slice. in_sample = every play cut before the first logged lock that carries the "
        "flags (the rule was written after those results, so these are derived after the fact); forward = only plays whose flags were logged at lock, "
        "joined to the graded record. A record, not a signal.")


def derive_flags(c, g, side, quotes):
    """-> {"a", "c", "src"} for the shown `side` of market `g` on stored card `c`: states toward / away / quiet or None (not readable).
    A card that carries a v2 block with flags for this side answers from it (src frozen); otherwise they are re-derived from the tape rows at or
    before the card's cut (src derived), exactly as the live builder reads them. A failure is None, never a guess."""
    m = (c.get("markets") or {}).get(g) or {}
    v2 = m.get("v2")
    if isinstance(v2, dict) and v2.get("side") == side and "flags" in v2:
        fl = v2["flags"] if isinstance(v2["flags"], dict) else {}
        return {"a": fl.get("a"), "c": fl.get("c"), "src": "frozen"}
    if quotes is None:
        return {"a": None, "c": None, "src": None}
    try:
        rows, _ = quotes.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
        sides = list((m.get("sides") or {}).keys())
        norm = BSC.side_norms(g, sides, BSC.team_names(c.get("vault"), c["ev"], c["sport"])).get(side)
        fl, _ = F.flags_block(rows, g, norm, c["cut"], c["sport"], None)
        return {"a": fl["a"], "c": fl["c"], "src": "derived"}
    except Exception as e:                           # context: a bad row leaves this play unreadable, never stops the record
        print("::warning::flag record: %s %s: %s: %s" % (c.get("ev"), g, type(e).__name__, e), file=sys.stderr)
        return {"a": None, "c": None, "src": "error"}


def slices_of(a, c):
    """The slice names of a play from its Flag A and Flag C states. Every play is in exactly one of {fired, none, unreadable} (fired = at least one
    of the four toward / away slices)."""
    out = [n for n, ok in (("a_toward", a == "toward"), ("a_away", a == "away"), ("c_toward", c == "toward"), ("c_away", c == "away")) if ok]
    if out:
        return out
    return ["none"] if (a is not None or c is not None) else ["unreadable"]


def with_flags(ps, logged):
    """Each play gets `fa`, `fc` (already set by play_rows from the card or the tape) and `forward`: True when its log row carries `mf`, with the
    states the log holds (an `mf` of None is a dropped block: unreadable). A play with no `mf` row is not forward."""
    out = []
    for p in ps:
        row = logged.get(p["key"])
        if isinstance(row, dict) and "mf" in row:
            mf = row["mf"] if isinstance(row["mf"], dict) else {}
            out.append(dict(p, forward=True, fa=mf.get("pin_state"), fc=mf.get("line_state")))
        else:
            out.append(dict(p, forward=False))
    return out


def _in(p, sl):
    return sl in slices_of(p.get("fa"), p.get("fc"))


def block(ps, sl, first_cut):
    sub = [p for p in ps if _in(p, sl)]
    return {"all": TR.cell(sub), "in_sample": TR.cell([p for p in sub if first_cut is None or p["cut"] < first_cut]),
            "forward": TR.cell([p for p in sub if p.get("forward")])}


def shape(ps, first_cut):
    return {sl: block(ps, sl, first_cut) for sl in SLICES}


def build(ps, built, data_ref, logged=None):
    logged = logged or {}
    ps = with_flags(ps, logged)
    cuts = [r["cut"] for r in logged.values() if isinstance(r, dict) and "mf" in r and isinstance(r.get("cut"), (int, float))]
    first_cut = min(cuts) if cuts else None
    n_fwd = sum(1 for p in ps if p["forward"])
    return {"built": built, "data_ref": data_ref, "rule": RULE, "flags_rule": F.FLAGS_RULE, "units_basis": "flat 1u at the stored price at the cut",
            "slices": list(SLICES), "first_logged_cut": first_cut, "logged_rows": sum(1 for r in logged.values() if isinstance(r, dict) and "mf" in r),
            "forward_graded": n_fwd, "forward_note": FORWARD_NOTE if not n_fwd else "forward = plays whose flags were logged at lock by the live builder",
            "all_sports": list(ALL_SPORTS),
            "sports": {sp: shape([p for p in ps if p["sport"] == sp], first_cut) for sp in SPORTS},
            "all": shape([p for p in ps if p["sport"] in ALL_SPORTS], first_cut)}


def logged_rows(reader):
    """{graded sf key: row} of every v2_tier log row (the rows without `mf` are kept: they say the play is not forward for the flags)."""
    return TR.logged_rows(reader)


# ---------- the printed report (tier_history.py) ----------

def compute(ps):
    """Every number the report prints, as data: per sport (and the NBA+NFL+CBB headline) and slice, the full stats (n, w-l, units, roi, se, CLV),
    the OLD record (no flags, every play) beside them, and the flag list: EVERY slice whose record improves (units above 0), with its n."""
    out = {"plays": len(ps), "old": {}, "slices": {}, "flagged": [], "src": {s: sum(1 for p in ps if p.get("fsrc") == s) for s in ("frozen", "derived", "error")}}
    groups = [(sp, [p for p in ps if p["sport"] == sp]) for sp in SPORTS] + [("headline", [p for p in ps if p["sport"] in ALL_SPORTS])]
    for name, sub in groups:
        out["old"][name] = TH.stats(sub)
        out["slices"][name] = {}
        for sl in SLICES:
            st = TH.stats([p for p in sub if _in(p, sl)])
            out["slices"][name][sl] = st
            label = ("Headline (NBA+NFL+CBB)" if name == "headline" else name.upper()) + " " + LABEL[sl]
            if st["n"] and st["units"] > 0:
                out["flagged"].append({"slice": label, "metric": "flat ROI", "n": st["n"], "small_sample": st["n"] < SMALL_N, "stats": st})
    return out


def fmt_cell(st):
    return TH.fmt(st).split("; ")[0]


def print_report(out):
    print("\nMARKET-MOVE FLAGS v2f-2 (docs/sharps-v2-flags-spec.md): the same plays by flag state, point in time; in-sample; context only")
    print("A = Pinnacle's price, C = the market's number or price. A play can sit in an A slice and a C slice; the Pinnacle limit is a fact, not a slice.")
    print(f"Flags read from a stored card block: {out['src']['frozen']}, re-derived from the tape at the cut: {out['src']['derived']}, errors: {out['src']['error']}.")
    for name in [s for s in SPORTS] + ["headline"]:
        old = out["old"][name]
        title = "HEADLINE NBA+NFL+CBB" if name == "headline" else name.upper() + (" (no size shown)" if name == "cfb" else "")
        print(f"\n{title}: OLD (no flags, every play) {fmt_cell(old)}")
        for sl in SLICES:
            st = out["slices"][name][sl]
            if st["n"]:
                print(f"  NEW {LABEL[sl]:<18} {fmt_cell(st)}")
    print(f"\nFLAGGED FOR CLOSE MONITORING: every flag slice whose record improves, with its n (tag under n={SMALL_N}); in-sample, none promoted, none a signal")
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
    print("flag_record.json %.1f KB, %d plays" % (len(payload) / 1000, len(ps)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
