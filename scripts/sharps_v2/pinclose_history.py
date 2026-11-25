#!/usr/bin/env python3
"""The Pinnacle-close record by sport and tier, read from the stored `pinclose` rows (scripts/sharps_v2/pinclose.py), for the PR and the docs.

Reads the graded rows, the frozen cards and the stored `pinclose` rows of a `pm-holders-data` checkout (a folder with --data-dir, or a git ref
with --ref, read with `git show`) and prints, per sport and evidence tier (rule v2t-1, derived point in time by tier_history.py), the plays with
a stored Pinnacle close, the CLV (close fair minus the price at the cut, points) and the market move after the cut (close fair minus fair at the
cut, points), each as mean, one standard error and n, and the reasons a close is missing. Every cell is IN-SAMPLE for a play graded before the
rule existed (the tier rule was written after those results); it is a record, never a signal. Every cell whose mean CLV is above 0 is flagged
for close monitoring with its n (a tag under n=30).

It also cross-checks the stored rows against the two on-the-fly reads the repo already had, so the stored close and the derived one cannot
silently disagree: tier_history.pin_close_pts (CLV, from the tape) and move_grade_history.after_moves (the move).

  python3 -I scripts/sharps_v2/pinclose_history.py --data-dir DIR [--book-tape data/book_tape] [--json OUT.json]
  python3 -I scripts/sharps_v2/pinclose_history.py --repo . --ref origin/pm-holders-data [--book-tape data/book_tape]
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
from sharps_v2 import pinclose as PC  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402

HEADLINE = ("nba", "nfl", "cbb")
TIERS = TH.TIERS


def closes_of(rows):
    """{sf result key: pinclose row}: the stored Pinnacle closes only (a Polymarket `close` row also has an `of`, and is not one of these)."""
    return {r["of"]: r for r in rows if isinstance(r, dict) and r.get("kind") == "pinclose" and isinstance(r.get("of"), str)}


def _slice(plays, closes):
    return PC.summary(plays, closes)


def compute(ps, closes):
    """{sport|headline: {tier|all: summary}} for the play records `ps` (tier_history.play_rows) joined to the stored pinclose rows `closes` ({sf key: row})."""
    out = {}
    for name, sports in [(s, (s,)) for s in TH.SPORTS] + [("headline", HEADLINE)]:
        sp = [p for p in ps if p["sport"] in sports]
        cell = {"all": _slice(sp, closes)}
        for t in TIERS:
            sub = [p for p in sp if p["tier"] == t]
            if sub:
                cell[t] = _slice(sub, closes)
        out[name] = cell
    return out


def flagged(table):
    """Every cell whose mean CLV is above 0, with its n: for close monitoring, in-sample, none a signal."""
    out = []
    for name, cell in table.items():
        for t, s in cell.items():
            c = s["clv"]
            if c["n"] and c["mean_pts"] is not None and c["mean_pts"] > 0:
                out.append({"slice": f"{name} {TH.slice_label(t) if t != 'all' else 'all shown plays'}", "n": c["n"], "mean_pts": c["mean_pts"],
                            "se_pts": c["se_pts"], "small_sample": c["small_sample"]})
    return out


def cross_check(ps, closes, tape, rows, git, quotes):
    """-> {clv_compared, clv_mismatch, move_compared, move_mismatch, examples}: the stored pts against tier_history's on-the-fly CLV (they differ at most
    by the rounding of the 4 digit fair there, 0.01 point) and the stored move against move_grade_history.after_moves."""
    from sharps_v2 import move_grade_history as MGH
    moves = MGH.after_moves(git, rows, quotes, ps)
    res = {"clv_compared": 0, "clv_mismatch": 0, "move_compared": 0, "move_mismatch": 0, "clv_only_stored": 0, "clv_only_derived": 0,
           "move_only_stored": 0, "move_only_derived": 0, "examples": []}
    for p in ps:
        c = closes.get(p["key"])
        if c is None:
            continue
        a, b = c.get("pts"), p.get("clv")
        if a is not None and b is not None:
            res["clv_compared"] += 1
            if abs(a - b) > 0.0101:
                res["clv_mismatch"] += 1
                res["examples"].append(("clv", p["key"], a, b))
        elif a is not None:
            res["clv_only_stored"] += 1
        elif b is not None:
            res["clv_only_derived"] += 1
        a, b = c.get("move_pts"), moves.get(p["key"])
        if a is not None and b is not None:
            res["move_compared"] += 1
            if abs(a - b) > 0.0101:
                res["move_mismatch"] += 1
                res["examples"].append(("move", p["key"], a, b))
        elif a is not None:
            res["move_only_stored"] += 1
        elif b is not None:
            res["move_only_derived"] += 1
    return res


def fmt_stat(s):
    if not s["n"]:
        return "n=0"
    se = f", se {s['se_pts']:.2f}" if s["se_pts"] is not None else ""
    return f"{s['mean_pts']:+.2f} pts{se}, n={s['n']}" + ("  [small sample]" if s["small_sample"] else "")


def print_report(table, flags, x=None):
    print("PINNACLE CLOSE, stored `pinclose` rows (points; CLV = close fair minus price at the cut; move = close fair minus fair at the cut). In-sample, a record not a signal.")
    for name, cell in table.items():
        a = cell["all"]
        if not a["graded"]:
            continue
        print(f"\n{name.upper()}: {a['graded']} graded shown plays, {a['with_close']} with a stored close, {a['pending']} without a pinclose row yet")
        if a["no_close_by_reason"]:
            print("  no close:", ", ".join(f"{k} {v}" for k, v in a["no_close_by_reason"].items()))
        if a["clv_unreadable_by_reason"]:
            print("  close readable but not at the ticket line:", ", ".join(f"{k} {v}" for k, v in a["clv_unreadable_by_reason"].items()))
        for t in ("all",) + TIERS:
            if t in cell:
                s = cell[t]
                print(f"  {('all shown plays' if t == 'all' else TH.slice_label(t)):<16} plays {s['graded']:>3}, close {s['with_close']:>3} | CLV {fmt_stat(s['clv'])} | move {fmt_stat(s['move'])}")
    print(f"\nFLAGGED FOR CLOSE MONITORING: every cell with a mean CLV above 0, with its n (tag under n={PC.SMALL_N}); in-sample, none promoted, none a signal")
    for f in flags:
        se = f", se {f['se_pts']:.2f}" if f["se_pts"] is not None else ""
        print(f"  {f['slice']}: CLV {f['mean_pts']:+.2f} pts{se}, n={f['n']}" + ("  [small sample]" if f["small_sample"] else ""))
    if not flags:
        print("  none")
    if x:
        print(f"\nCROSS-CHECK against the on-the-fly reads: CLV {x['clv_compared']} compared, {x['clv_mismatch']} differ by more than 0.01 pt "
              f"(stored only {x['clv_only_stored']}, derived only {x['clv_only_derived']}); move {x['move_compared']} compared, {x['move_mismatch']} differ "
              f"(stored only {x['move_only_stored']}, derived only {x['move_only_derived']})")
        for e in x["examples"][:10]:
            print("  differs:", e)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="origin/pm-holders-data")
    ap.add_argument("--book-tape", default="data/book_tape")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    git = TH.FsReader(a.data_dir) if a.data_dir else TH.Git(a.repo, a.ref)
    sha = None
    if not a.data_dir:
        sha = git.sha
    rows = TH.graded_rows(git)
    tape, quotes = BSC.BookTape(a.book_tape), BSC.QuoteTape(a.book_tape)
    ps = TH.play_rows(git, rows, tape)
    closes = closes_of(rows)
    table = compute(ps, closes)
    flags = flagged(table)
    x = cross_check(ps, closes, tape, rows, git, quotes)
    git.close()
    if sha:
        print(f"Data: {a.ref} at commit {sha}.")
    print_report(table, flags, x)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"table": table, "flagged": flags, "cross_check": x, "data_ref_sha": sha}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
