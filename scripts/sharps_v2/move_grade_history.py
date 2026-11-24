#!/usr/bin/env python3
"""The measurement behind the Move grade (rule mg-1, docs/sharp-movegrade-prereg.md): the cutoffs, the letter shares and the in-sample record by letter.
Prints, for the named refs: the distribution of 24 hour moves on every started game of the book tape (2.2), the cutoffs it gives and whether they equal the
frozen tables in move_grade.py (2.3), the letter shares on both sides of every started market (2.4), the letter counts on the graded plays (2.5), and the
in-sample record by letter (3.1), the prereg's metrics on the same plays (3.2) and every improving cell flagged with its n (3.3).

The cutoffs come from the tape population ONLY: no price at the cut, no close and no graded result is read anywhere in the cutoff code (functions
`population`, `distribution`, `marks`). The record half reads the graded plays and is in-sample: the rule was written after those results. Every number comes
from a stored value at a named ref, stdlib only, read with `python3 -I`:

  python3 -I scripts/sharps_v2/move_grade_history.py [--repo .] [--ref origin/pm-holders-data] [--book-tape data/book_tape] [--tape-ref LABEL] [--json OUT.json]

Point in time: each play's grade is derived from the tape rows at or before its own cut; adding a row after the cut changes no letter.
"""
import argparse, collections, glob, json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import build_side_cards as BSC  # noqa: E402
import sf_signals as SIG  # noqa: E402
from sharps_v2 import flags_v2 as F  # noqa: E402
from sharps_v2 import move_grade as MG  # noqa: E402
from sharps_v2 import move_grade_record as MGR  # noqa: E402
from sharps_v2 import tier_history as TH  # noqa: E402

SPORTS = ("nba", "nfl", "cbb", "cfb")
MARKETS = ("ml", "spread", "total")
MARKET_NAME = {"ml": "moneyline", "spread": "spread", "total": "total"}
PCTS = (0.50, 0.75, 0.80, 0.90, 0.95)
CUT_BEFORE_START = 900                            # the cut is 15 minutes before start (the flag spec's window end)
BOOTSTRAP_N, BOOTSTRAP_SEED = 10000, 20261111
SCORE = {"d": 0, "c": 1, "b": 2, "a": 3}          # the letter score of the prereg slope
TAPE_BOOKS = frozenset(F.FLAGS_BOOKS)


# ---------- the population (tape only: no result, no price at the cut, no close) ----------

def population(root):
    """{sport: [(game key, start, rows)]} for every game on the tape that has started (its start is at or before the newest row of that sport's tape). Rows are
    the stored rows of the six books the flags may read, as the live builder's QuoteTape reads them. A game key is the stored `gk`, else (away, home, start)."""
    out = {}
    for sp in SPORTS:
        games, newest = collections.defaultdict(list), 0
        for fn in sorted(glob.glob(os.path.join(root, sp, "[0-9][0-9][0-9][0-9]-[0-9][0-9].jsonl"))):
            with open(fn) as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(r, dict) or r.get("t") is None:
                        continue
                    newest = max(newest, r["t"])
                    if r.get("book") not in TAPE_BOOKS or r.get("bf"):
                        continue
                    k = r.get("gk") or (r.get("away"), r.get("home"), r.get("start"))
                    games[k].append({x: r[x] for x in ("t", "book", "ml", "sp", "tot", "px", "nsp", "ntot", "start", "lim") if x in r})
        started = []
        for k, rs in games.items():
            starts = [r["start"] for r in rs if r.get("start")]
            if starts:
                s = max(set(starts), key=starts.count)
                if s <= newest:
                    started.append((k, s, rs))
        out[sp] = sorted(started, key=lambda x: (x[1], str(x[0])))
    return out


def pct(xs, p):
    """Linear interpolation between order statistics (the method that reproduces the spec's tables)."""
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    i = (n - 1) * p
    lo = int(i)
    hi = min(lo + 1, n - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def home_side(g):
    return "over" if g == "total" else "home"


def distribution(games, sp):
    """Per market: the absolute Flag A moves (points of Pinnacle no-vig fair) and the absolute Pinnacle main-line moves (spreads and totals, Flag C readable:
    Pinnacle and 2 or more US books), for the home side (spread, moneyline) or the over (total), 24 hours ending at the cut."""
    out = {}
    for g in MARKETS:
        a, ln = [], []
        for _, s, rs in games:
            fl, _ = F.flags_block(rs, g, home_side(g), s - CUT_BEFORE_START, sp, None)
            if isinstance(fl.get("pin"), dict) and F._n(fl["pin"].get("pts")):
                a.append(abs(fl["pin"]["pts"]))
            cp = MG.c_pts_of(fl.get("line"), g, home_side(g)) if g != "ml" else None
            if cp is not None:
                ln.append(abs(cp))
        out[g] = {"games": len(games), "a": a, "line": ln}
    return out


def _half(x, how):
    return {"near": round(x * 2) / 2, "up": math.ceil(x * 2 - 1e-9) / 2}[how]


def marks(dist, sp):
    """The cutoffs of mg-1 from a distribution (spec section 2.1). M_A: the median absolute Flag A move rounded to the nearest 0.5, floor 0.5. M_C: the median
    absolute line move rounded UP to the half point, floor 0.5. X_A: the 95th percentile rounded to the nearest 0.5, at least T_A + 0.5. X_C: the 95th percentile
    rounded up to the half point, at least T_C + 0.5. T_A and T_C are the registered flag thresholds, not re-read."""
    out = {"m_a": {}, "x_a": {}, "m_c": {}, "x_c": {}}
    for g in MARKETS:
        d = dist[g]
        out["m_a"][g] = max(0.5, _half(pct(d["a"], 0.5), "near"))
        out["x_a"][g] = max(_half(pct(d["a"], 0.95), "near"), F.FLAGS_T_A[sp][g] + 0.5)
        if g != "ml":
            out["m_c"][g] = max(0.5, _half(pct(d["line"], 0.5), "up"))
            out["x_c"][g] = max(_half(pct(d["line"], 0.95), "up"), F.FLAGS_T_C[sp][g] + 0.5)
    return out


def shares(games, sp):
    """Letter counts on BOTH sides of every started market: {market: {A, B, C, D, against, none}}."""
    out = {g: collections.Counter() for g in MARKETS}
    for _, s, rs in games:
        for g in MARKETS:
            for norm in (("over", "under") if g == "total" else ("home", "away")):
                fl, _ = F.flags_block(rs, g, norm, s - CUT_BEFORE_START, sp, None)
                gr = MG.move_grade(fl, g, norm, sp)
                out[g][{"against": "against", "unreadable": "none"}.get(MG.bucket_of(gr), MG.bucket_of(gr).upper())] += 1
    return out


# ---------- the printers of section 2 ----------

def print_distribution(pop, dists):
    print("\n2.2 THE DISTRIBUTION (started games, home or over side, absolute points; games, Flag A n, A p50 p75 p80 p90 p95, Line n, Line p50 p75 p80 p90 p95, share with no line move)")
    for sp in SPORTS:
        for g in MARKETS:
            d = dists[sp][g]
            a = " ".join("%.2f" % pct(d["a"], p) for p in PCTS) if d["a"] else "-"
            if g == "ml":
                print(f"  {sp.upper():<3} {MARKET_NAME[g]:<9} games {d['games']:>4}  A n {len(d['a']):>3}  {a}")
            else:
                ln = " ".join("%.2f" % pct(d["line"], p) for p in PCTS) if d["line"] else "-"
                nm = "%.0f%%" % (100 * sum(1 for x in d["line"] if x == 0) / len(d["line"])) if d["line"] else "-"
                print(f"  {sp.upper():<3} {MARKET_NAME[g]:<9} games {d['games']:>4}  A n {len(d['a']):>3}  {a}  |  line n {len(d['line']):>3}  {ln}  no move {nm}")


def print_marks(derived):
    print("\n2.3 THE CUTOFFS (points): C mark M_A / M_C, B mark T_A / T_C (registered, unchanged), A mark X_A / X_C; 'frozen' = equals the table in move_grade.py")
    ok = True
    for sp in SPORTS:
        for g in MARKETS:
            m = derived[sp]
            row = [m["m_a"][g], F.FLAGS_T_A[sp][g], m["x_a"][g]] + ([m["m_c"][g], F.FLAGS_T_C[sp][g], m["x_c"][g]] if g != "ml" else [])
            frozen = [MG.MG_M_A[sp][g], F.FLAGS_T_A[sp][g], MG.MG_X_A[sp][g]] + ([MG.MG_M_C[sp][g], F.FLAGS_T_C[sp][g], MG.MG_X_C[sp][g]] if g != "ml" else [])
            same = row == frozen
            ok = ok and same
            print(f"  {sp.upper():<3} {MARKET_NAME[g]:<9} " + " / ".join("%.1f" % x for x in row) + ("   frozen" if same else "   DIFFERS from the frozen table: " + " / ".join("%.1f" % x for x in frozen)))
    print("  every derived cutoff equals the frozen table" if ok else "  SOME DERIVED CUTOFFS DIFFER FROM THE FROZEN TABLE")
    return ok


def print_shares(sh):
    print("\n2.4 LETTER SHARES ON THE POPULATION (both sides of every started market; % of sides with a grade or the marker, null left out)")
    tot = collections.Counter()
    for sp in SPORTS:
        sp_tot = collections.Counter()
        for g in MARKETS:
            c = sh[sp][g]
            sp_tot.update(c)
            line(f"  {sp.upper():<3} {MARKET_NAME[g]:<9}", c)
        line(f"  {sp.upper():<3} ALL      ", sp_tot, bold=True)
        tot.update(sp_tot)
    line("  ALL FOUR           ", tot, bold=True)


def line(label, c, bold=False):
    sides = sum(c.values())
    gr = sum(c[k] for k in ("A", "B", "C", "D", "against"))
    cell = lambda k: f"{c[k]} ({100 * c[k] / gr:.1f}%)" if gr else f"{c[k]}"
    print(f"{label} sides {sides:>5}  A {cell('A')}  B {cell('B')}  C {cell('C')}  D {cell('D')}  moved against {cell('against')}  no grade {c['none']}")


# ---------- the record half (in-sample) ----------

def _pin_fair(rows, g, norm, t):
    """Pinnacle's no-vig fair and line for the side at its last readable tape row at or before `t`: (fair, line) or None."""
    rd = [r for r in F._reads([r for r in rows if r.get("book") == "Pinnacle" and F._n(r.get("t")) and r["t"] <= t], g, norm) if r["fair"] is not None]
    rd.sort(key=lambda r: r["t"])
    return (rd[-1]["fair"], rd[-1]["line"]) if rd else None


def after_moves(git, rows, tape_quotes, ps):
    """{play key: after} in points for plays that have a readable move after the cut: after = Pinnacle's no-vig fair for the side at the last tape row at or
    before game start (the pinclose row) minus its fair at the cut, both at the SAME Pinnacle line (a play whose close is at another line is left out). Plays with a
    stored price_src of pin would be left out; no graded card carries one. The price at the cut is never read."""
    by_key = {r["key"]: r for r in rows if r.get("kind") == "result"}
    out = {}
    for p in ps:
        r = by_key.get(p["key"])
        raw = git.show("pm_cards/" + r["card"]) if r else None
        if not raw:
            continue
        c = json.loads(raw)
        g = r["group"]
        sf = c["markets"][g]["sf"]["all"]
        if (c["markets"][g].get("v2") or {}).get("price_src") == "pin":
            continue
        rs, _ = tape_quotes.game(c["sport"], c.get("vault"), c["ev"], c["gst"])
        sides = list((c["markets"][g].get("sides") or {}).keys())
        norm = BSC.side_norms(g, sides, BSC.team_names(c.get("vault"), c["ev"], c["sport"])).get(sf["side"])
        if not rs or norm not in F.SIDES:
            continue
        a, b = _pin_fair(rs, g, norm, c["cut"]), _pin_fair(rs, g, norm, c["gst"])
        if a and b and (g == "ml" or (F._n(a[1]) and F._n(b[1]) and abs(a[1] - b[1]) <= F.LINE_EPS)):
            out[p["key"]] = round((b[0] - a[0]) * 100, 2)
    return out


def mean_se(xs):
    n = len(xs)
    if not n:
        return None, None
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    return m, (sd / math.sqrt(n) if sd is not None else None)


def slope(pairs):
    """Least-squares slope of y on x; None when x has no spread."""
    n = len(pairs)
    mx, my = sum(x for x, _ in pairs) / n, sum(y for _, y in pairs) / n
    sxx = sum((x - mx) ** 2 for x, _ in pairs)
    return sum((x - mx) * (y - my) for x, y in pairs) / sxx if sxx else None


def bootstrap_slope(pairs, rng):
    """95% percentile bootstrap of the slope: BOOTSTRAP_N resamples of the plays with replacement (each group is read with a fresh generator at the seed)."""
    n, vals = len(pairs), []
    for _ in range(BOOTSTRAP_N):
        s = slope([pairs[rng.randrange(n)] for _ in range(n)])
        if s is not None:
            vals.append(s)
    vals.sort()
    return pct(vals, 0.025), pct(vals, 0.975)


def print_record(ps, rows, git, quotes):
    print("\n2.5 THE LETTER COUNTS ON THE GRADED PLAYS (read at each play's own cut)")
    for name, sub in [(sp.upper() + (" (no size shown)" if sp == "cfb" else ""), [p for p in ps if p["sport"] == sp]) for sp in SPORTS] + [("All", ps)]:
        c = collections.Counter(MG.bucket_of(p.get("mg")) for p in sub)
        gr = sum(c[k] for k in ("a", "b", "c", "d", "against"))
        print(f"  {name:<18} plays {len(sub):>3}  A {c['a']}  B {c['b']}  C {c['c']}  D {c['d']}  moved against {c['against']}  no grade {c['unreadable']}  (of {gr} with a grade or the marker)")
    out = MGR.compute(ps)
    print("\n3.1 OLD (no grade) AND NEW (by letter), flat 1u at the stored price at the cut, in-sample; se in points of ROI")
    MGR.print_report(out)
    print("\n3.2 THE PREREG'S METRICS ON THE SAME PLAYS (in-sample, report only)")
    aft = after_moves(git, rows, quotes, ps)
    head = [p for p in ps if p["sport"] in MGR.ALL_SPORTS]
    for lab, sl in (("A", "a"), ("B", "b"), ("C", "c"), ("D", "d"), ("moved against", "against")):
        sub = [p for p in head if MG.bucket_of(p.get("mg")) == sl]
        af = [aft[p["key"]] for p in sub if p["key"] in aft]
        cl = [p["clv"] for p in sub if p["clv"] is not None]
        m, se = mean_se(af)
        cm = sum(cl) / len(cl) if cl else None
        print(f"  headline {lab:<14} market move after the cut {'%+.2f' % m if m is not None else 'n/a'} (se {'%.2f' % se if se is not None else 'n/a'}), n={len(af)};  "
              f"Pinnacle CLV {'%+.2f' % cm if cm is not None else 'n/a'}, n={len(cl)}")
    readable = [p for p in ps if p["key"] in aft]
    zero = sum(1 for p in readable if aft[p["key"]] == 0)
    print(f"  {zero} of the {len(readable)} graded plays with a readable move after the cut moved exactly 0")
    print(f"  slope of the move after the cut on the letter score (D=0, C=1, B=2, A=3), 95% bootstrap, {BOOTSTRAP_N} resamples, seed {BOOTSTRAP_SEED}:")
    for name, sub in [(sp.upper() + (" (no size shown)" if sp == "cfb" else ""), [p for p in ps if p["sport"] == sp]) for sp in ("nba", "nfl", "cbb", "cfb")] + [("headline", head)]:
        pairs = [(SCORE[MG.bucket_of(p.get("mg"))], aft[p["key"]]) for p in sub if MG.bucket_of(p.get("mg")) in SCORE and p["key"] in aft]
        s = slope(pairs) if len(pairs) > 1 else None
        if s is None:
            print(f"    {name:<18} n={len(pairs)}: no slope")
            continue
        lo, hi = bootstrap_slope(pairs, random.Random(BOOTSTRAP_SEED))
        print(f"    {name:<18} {s:+.3f} [{lo:+.3f}, {hi:+.3f}] n={len(pairs)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ref", default="origin/pm-holders-data", help="the graded-record data ref; its commit hash is printed")
    ap.add_argument("--book-tape", default="data/book_tape")
    ap.add_argument("--tape-ref", default=None, help="a label for the tape's commit, printed beside the numbers (the tape is read from --book-tape as checked out)")
    ap.add_argument("--json", help="also write the numbers to this file")
    a = ap.parse_args(argv)
    git = TH.Git(a.repo, a.ref)
    sha = git.sha
    print(f"Move grade measurement, rule {MG.MG_RULE}. Graded record: {a.ref} at commit {sha}. Book tape: {a.book_tape}" + (f" at {a.tape_ref}" if a.tape_ref else "") + ".")
    print("Cutoffs read the tape population only (no result, no price at the cut, no close). The record half is IN-SAMPLE: the rule was written after those results.")
    pop = population(a.book_tape)
    dists = {sp: distribution(pop[sp], sp) for sp in SPORTS}
    derived = {sp: marks(dists[sp], sp) for sp in SPORTS}
    print_distribution(pop, dists)
    same = print_marks(derived)
    print_shares(({sp: shares(pop[sp], sp) for sp in SPORTS}))
    tape, quotes = BSC.BookTape(a.book_tape), BSC.QuoteTape(a.book_tape)
    rows = TH.graded_rows(git)
    ps = TH.play_rows(git, rows, tape, quotes)
    voided = sum(1 for r in rows if r.get("play") == "sf" and r.get("variant") == "all" and r.get("status") == "void")
    print(f"\nGraded shown plays (sf, variant all): {len(ps)}; voided and left out: {voided}")
    out = print_record(ps, rows, git, quotes)
    git.close()
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"data_ref_sha": sha, "cutoffs": derived, "cutoffs_equal_frozen": same, "record": out}, fh, indent=1)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
