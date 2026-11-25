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
    """Every cell whose mean is above 0, with its n: CLV vs the close (closes after the cut only) and, labelled apart, the price against Pinnacle's
    fair at the cut (closes at or before the cut). For close monitoring, in-sample, none a signal."""
    out = []
    for name, cell in table.items():
        for t, s in cell.items():
            for metric, key in (("CLV vs the close", "clv"), ("price vs Pinnacle fair at the cut", "price_vs_fair_at_cut")):
                c = s[key]
                if c["n"] and c["mean_pts"] is not None and c["mean_pts"] > 0:
                    out.append({"slice": f"{name} {TH.slice_label(t) if t != 'all' else 'all shown plays'}", "metric": metric, "n": c["n"],
                                "mean_pts": c["mean_pts"], "se_pts": c["se_pts"], "small_sample": c["small_sample"]})
    return out


def cross_check(ps, closes, tape, rows, git, quotes):
    """-> {clv_compared, clv_mismatch, move_compared, move_mismatch, examples}: the stored pts against tier_history's on-the-fly CLV (they differ at most
    by the rounding of the 4 digit fair there, 0.01 point) and the stored move against move_grade_history.after_moves.
    NOT an independent proof of the CLV: tier_history.pin_close_pts calls sf_signals.ev_read with the card's sf.line, which is the Polymarket line of
    outcomes[0], as the ticket line, so on a spread where the play is outcomes[1] it compares the wrong sign and reports "ticket line not main" for a
    line that is main. Those plays are the `clv_only_stored_outs1_spread` count; the frozen files are not changed. See independent_check."""
    from sharps_v2 import move_grade_history as MGH
    moves = MGH.after_moves(git, rows, quotes, ps)
    by_key = {r["key"]: r for r in rows if isinstance(r, dict) and r.get("kind") == "result"}
    res = {"clv_only_stored_outs1_spread": 0, "clv_compared": 0, "clv_mismatch": 0, "move_compared": 0, "move_mismatch": 0, "clv_only_stored": 0, "clv_only_derived": 0,
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
            r = by_key.get(p["key"]) or {}
            if r.get("group") == "spread" and isinstance(r.get("outs"), list) and len(r["outs"]) == 2 and r.get("side") == r["outs"][1]:
                res["clv_only_stored_outs1_spread"] += 1      # tier_history / ev_read compare Pinnacle's side line with outcomes[0]'s line: wrong sign here
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


def _prob(o):
    return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)


def raw_close(rows, g, norm, gst):
    """Pinnacle's close for the side straight from the raw tape rows, with its own arithmetic (no flags_v2, no sf_signals): the last row at or
    before `gst` that holds the market with usable numbers. -> (fair, side line, t) or None. ml: [away, home]; sp: [home line, home, away]; tot: [line, over, under]."""
    key = {"ml": "ml", "spread": "sp", "total": "tot"}[g]
    want = 2 if g == "ml" else 3
    best = None
    for r in rows:
        v = r.get(key)
        if not isinstance(r.get("t"), (int, float)) or r["t"] > gst or not isinstance(v, (list, tuple)) or len(v) < want:
            continue
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (v if g == "ml" else v[:3])):
            continue
        if best is None or r["t"] >= best[0]:
            best = (r["t"], v)
    if best is None:
        return None
    t, v = best
    if g == "ml":
        a, h = _prob(v[0]), _prob(v[1])
        fair_home = h / (h + a)
        return (fair_home if norm == "home" else 1 - fair_home), None, t
    if g == "spread":
        h, a = _prob(v[1]), _prob(v[2])
        fair_home = h / (h + a)
        return (fair_home if norm == "home" else 1 - fair_home), (v[0] if norm == "home" else -v[0]), t
    o, u = _prob(v[1]), _prob(v[2])
    fair_over = o / (o + u)
    return (fair_over if norm == "over" else 1 - fair_over), v[0], t


def independent_check(results, closes, card_of, tape):
    """Re-derive every stored row from the raw tape and the stored result row, with separate arithmetic and an explicit side-line rule (line for
    outcomes[0], minus line for outcomes[1]). -> counts: rows compared, close_fair / close_line / pts disagreements, and the sign audit: among
    spread rows with a stored close line, how often Pinnacle's line for the side equals the side's own line, its negative, or neither, split by
    whether the play is outcomes[0] or outcomes[1]. A correct side line shows zero rows equal to the negative."""
    res = {"compared": 0, "fair_mismatch": 0, "line_mismatch": 0, "pts_mismatch": 0, "clv_readable_disagree": 0, "examples": [],
           "sign_audit": {"outs0": {"equals_side_line": 0, "equals_negative": 0, "neither": 0}, "outs1": {"equals_side_line": 0, "equals_negative": 0, "neither": 0}},
           "stored_line_vs_pinnacle": {"outs0": {"equals_line": 0, "equals_negative_line": 0}, "outs1": {"equals_line": 0, "equals_negative_line": 0}}}
    for r in results:
        c = closes.get(r["key"])
        if c is None or c.get("close_fair") is None:
            continue
        card = card_of(r["card"])
        if not card:
            continue
        g = r["group"]
        sides = list(card["markets"][g]["sides"])
        norm = PC.side_norm(g, sides, BSC.team_names(card.get("vault"), card.get("ev"), r["sport"]), r["side"])
        rows, _ = tape.game(r["sport"], card.get("vault"), card.get("ev"), card.get("gst"))
        got = raw_close(rows, g, norm, r["gst"])
        res["compared"] += 1
        if got is None or abs(got[0] - c["close_fair"]) > 1e-5 or got[2] != c["close_t"]:
            res["fair_mismatch"] += 1
            res["examples"].append(("fair", r["key"], c["close_fair"], got))
            continue
        own = PC.side_line(g, r["side"], r.get("outs"), r.get("line"))
        if g != "ml" and (got[1] is None or abs(got[1] - c["close_line"]) > 1e-5):
            res["line_mismatch"] += 1
            res["examples"].append(("line", r["key"], c["close_line"], got[1]))
        readable = g == "ml" or (own is not None and got[1] is not None and abs(got[1] - own) <= PC.F.LINE_EPS)
        if readable != (c.get("pts") is not None):
            res["clv_readable_disagree"] += 1
            res["examples"].append(("readable", r["key"], c.get("pts"), readable))
        if readable and c.get("pts") is not None and abs(round((got[0] - r["price"]) * 100, 2) - c["pts"]) > 0.0101:
            res["pts_mismatch"] += 1
            res["examples"].append(("pts", r["key"], c["pts"], round((got[0] - r["price"]) * 100, 2)))
        if g == "spread" and own is not None and got[1] is not None and isinstance(r.get("outs"), list) and len(r["outs"]) == 2:
            pos = "outs0" if r["outs"][0] == r["side"] else "outs1"
            a = res["sign_audit"][pos]
            if abs(got[1] - own) <= PC.F.LINE_EPS:
                a["equals_side_line"] += 1
            elif abs(got[1] + own) <= PC.F.LINE_EPS:
                a["equals_negative"] += 1
            else:
                a["neither"] += 1
            if isinstance(r.get("line"), (int, float)):
                b = res["stored_line_vs_pinnacle"][pos]
                if abs(got[1] - r["line"]) <= PC.F.LINE_EPS:
                    b["equals_line"] += 1
                elif abs(got[1] + r["line"]) <= PC.F.LINE_EPS:
                    b["equals_negative_line"] += 1
    return res


def fmt_stat(s):
    if not s["n"]:
        return "n=0"
    se = f", se {s['se_pts']:.2f}" if s["se_pts"] is not None else ""
    return f"{s['mean_pts']:+.2f} pts{se}, n={s['n']}" + ("  [small sample]" if s["small_sample"] else "")


def print_report(table, flags, x=None, ind=None):
    print("PINNACLE CLOSE, stored `pinclose` rows (points; CLV = close fair minus price at the cut; move = close fair minus fair at the cut). In-sample, a record not a signal.")
    for name, cell in table.items():
        a = cell["all"]
        if not a["graded"]:
            continue
        print(f"\n{name.upper()}: {a['graded']} graded shown plays, {a['with_close']} with a stored close, {a['pending']} without a pinclose row yet")
        if a["no_close_by_reason"]:
            print("  no close:", ", ".join(f"{k} {v}" for k, v in a["no_close_by_reason"].items()))
        ca = a["close_after_cut"]
        print(f"  closes after the cut {ca['true']}, at or before it {ca['false']}" + (f" ({ca['false_share'] * 100:.0f}%)" if ca["false_share"] is not None else "") +
              f"; older than {PC.STALE_MIN} min before start {ca['older_than_%d_min' % PC.STALE_MIN]}" + (f" ({ca['older_share'] * 100:.0f}%)" if ca["older_share"] is not None else ""))
        if a["move_by_reason"]:
            print("  move not readable:", ", ".join(f"{k} {v}" for k, v in a["move_by_reason"].items()))
        if a["clv_unreadable_by_reason"]:
            print("  close readable but not at the ticket line:", ", ".join(f"{k} {v}" for k, v in a["clv_unreadable_by_reason"].items()))
        for t in ("all",) + TIERS:
            if t in cell:
                s = cell[t]
                print(f"  {('all shown plays' if t == 'all' else TH.slice_label(t)):<16} plays {s['graded']:>3}, close {s['with_close']:>3} (after cut {s['close_after_cut']['true']}) | CLV vs close {fmt_stat(s['clv'])} | "
                      f"price vs fair at cut {fmt_stat(s['price_vs_fair_at_cut'])} | move {fmt_stat(s['move'])}")
    print(f"\nFLAGGED FOR CLOSE MONITORING: every cell with a mean above 0, with its n (tag under n={PC.SMALL_N}); in-sample, none promoted, none a signal")
    for f in flags:
        se = f", se {f['se_pts']:.2f}" if f["se_pts"] is not None else ""
        print(f"  {f['slice']}: {f['metric']} {f['mean_pts']:+.2f} pts{se}, n={f['n']}" + ("  [small sample]" if f["small_sample"] else ""))
    if not flags:
        print("  none")
    if x:
        print(f"\nCROSS-CHECK against the on-the-fly reads: CLV {x['clv_compared']} compared, {x['clv_mismatch']} differ by more than 0.01 pt "
              f"(stored only {x['clv_only_stored']}, derived only {x['clv_only_derived']}); move {x['move_compared']} compared, {x['move_mismatch']} differ "
              f"(stored only {x['move_only_stored']}, derived only {x['move_only_derived']})")
        for e in x["examples"][:10]:
            print("  differs:", e)
        print(f"  (not independent: tier_history / ev_read compare Pinnacle's side line with outcomes[0]'s line; {x['clv_only_stored_outs1_spread']} of the "
              f"{x['clv_only_stored']} stored-only CLVs are outcomes[1] spread plays, where that comparison has the wrong sign)")
    if ind:
        sa, sl = ind["sign_audit"], ind["stored_line_vs_pinnacle"]
        print(f"\nINDEPENDENT CHECK from the raw tape (own arithmetic, explicit side line): {ind['compared']} rows compared; close fair/time differ {ind['fair_mismatch']}, "
              f"close line differ {ind['line_mismatch']}, CLV readable disagrees {ind['clv_readable_disagree']}, pts differ {ind['pts_mismatch']}")
        print(f"  spread sign audit, Pinnacle's line for the side vs the side's own line: outcomes[0] sides equal {sa['outs0']['equals_side_line']}, negative {sa['outs0']['equals_negative']}, "
              f"neither {sa['outs0']['neither']}; outcomes[1] sides equal {sa['outs1']['equals_side_line']}, negative {sa['outs1']['equals_negative']}, neither {sa['outs1']['neither']}")
        print(f"  the stored Polymarket line (outcomes[0]'s) against Pinnacle's line: outcomes[0] sides equal {sl['outs0']['equals_line']} / negative {sl['outs0']['equals_negative_line']}; "
              f"outcomes[1] sides equal {sl['outs1']['equals_line']} / negative {sl['outs1']['equals_negative_line']}")
        for e in ind["examples"][:10]:
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
    cards = {}
    def card_of(rel):
        if rel not in cards:
            raw = git.show("pm_cards/" + rel)
            cards[rel] = json.loads(raw) if raw else None
        return cards[rel]
    ind = independent_check([r for r in rows if PC.shown_graded(r)], closes, card_of, tape)
    git.close()
    if sha:
        print(f"Data: {a.ref} at commit {sha}.")
    print_report(table, flags, x, ind)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"table": table, "flagged": flags, "cross_check": x, "independent_check": ind, "data_ref_sha": sha}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
