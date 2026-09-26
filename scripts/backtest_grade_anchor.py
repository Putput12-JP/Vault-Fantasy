#!/usr/bin/env python3
"""Backtest: where should the grade's sample-size shrink pull toward?

The prop grade shrinks Vault's win-prob by sample size before comparing it to
the side's break-even price:  padj = anchor + (p - anchor) * g/(g+K), anchor a
COIN FLIP (0.5). On a juiced market that can manufacture edge: a +133 side only
needs 42.9%, so a prop Vault calls ~50/50 grades A on the plus-money side
(Chris Olave rec 5.5 U, 2026 w3). Worse, on a side Vault puts UNDER 50% the pull
raises the number: a +298 TD over graded A at 24% vs a 25% bar.

This replays every settled prop in data/bet_results.json, grades BOTH sides
against their OPENING price (what the OVER|UNDER cards do), and scores each
graded side flat 1u at the opening price and at the closing price:

  boost        OLD rule (to 2026-09-26): shrink toward 0.5 on every side
  live         CURRENT rule: same, but a sub-50% side keeps its raw prob
               (index.html _shrinkP / settle_bets.shrink_p)
  market       SHADOW: anchor = the side's no-vig OPENING market prob
  market+dir   market anchor + cap A/B at C when Vault's own prob < 50%

Findings, 2026 w1-3 (board scale): boost vs live is neutral (A+B ROI +9.7% vs
+9.2% at open, +-5); the market anchor did not beat either, and the picks it
would demote won above their bar. So `live` ships, `market` is shadow-tracked
(settle_bets grade_mkt / grade_mkt_alt) until more weeks settle.

No parameters are fitted here (K=6 is the production constant), so nothing is
in-sample. Letter cut-offs: --scale board (default) uses the board's
gradeLetter (A >= +5pt margin); --scale settle uses settle_bets.grade_letter
(A >= +10pt), the scale bet_results.json / the Track Record records. The last
block reads the SHADOW grades settle_bets now records (grade_mkt, grade_alt,
grade_mkt_alt) so the replay and the live record can be checked against each
other; with --scale settle they should match.

Usage:  python3 scripts/backtest_grade_anchor.py [--scale board|settle]
"""
import argparse, json, math, os, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
K = 6
MAX_HOLD = 0.15
GRADES = ["A", "B", "C", "D", "F"]


def am_prob(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def dec(a):
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def two_way(o, u):
    """(p_over_implied, p_under_implied) if a sane two-way price, else None."""
    if o is None or u is None:
        return None
    po, pu = am_prob(o), am_prob(u)
    if po + pu < 1.005 or po + pu > 1 + MAX_HOLD:
        return None
    return po, pu


SCALES = {   # margin over break-even -> letter
    "board": (0.05, 0.03, 0.01, -0.02),    # index.html gradeLetter
    "settle": (0.10, 0.05, 0.02, 0.0),     # settle_bets.grade_letter
}
CUTS = SCALES["board"]


def letter(m):
    a, b, c, d = CUTS
    return "A" if m >= a else "B" if m >= b else "C" if m >= c else "D" if m >= d else "F"


def main():
    global CUTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=sorted(SCALES), default="board")
    CUTS = SCALES[ap.parse_args().scale]
    print(f"letter scale: {ap.parse_args().scale} {CUTS}")
    rows = json.load(open(os.path.join(DATA, "bet_results.json")))["props"]
    sides = []   # one entry per (prop, side)
    for r in rows:
        if r.get("push") or r.get("won_open") is None or r.get("p_model") is None or not r.get("side"):
            continue
        tw = two_way(r.get("open_over"), r.get("open_under"))
        if not tw:
            continue
        cw = two_way(r.get("close_over"), r.get("close_under"))
        p_over = r["p_model"] if r["side"] == "over" else 1 - r["p_model"]
        over_won = r["won_open"] if r["side"] == "over" else 1 - r["won_open"]
        q_over = tw[0] / (tw[0] + tw[1])
        g = r.get("grade_n") or 0
        w = g / (g + K)
        for s in ("over", "under"):
            p = p_over if s == "over" else 1 - p_over
            q = q_over if s == "over" else 1 - q_over
            be = tw[0] if s == "over" else tw[1]
            won = over_won if s == "over" else 1 - over_won
            po = r["open_over"] if s == "over" else r["open_under"]
            pc = (r["close_over"] if s == "over" else r["close_under"]) if cw else None
            sides.append(dict(week=r["week"], market=r["market"], p=p, q=q, w=w, be=be, won=won,
                              u_open=(dec(po) - 1) if won else -1.0,
                              u_close=((dec(pc) - 1) if won else -1.0) if pc is not None else None,
                              plus=po > 0))

    def grade(x, rule):
        if rule.startswith("market"):
            padj = x["q"] + (x["p"] - x["q"]) * x["w"]
        elif rule == "live" and x["p"] < 0.5:
            padj = x["p"]
        else:
            padj = 0.5 + (x["p"] - 0.5) * x["w"]
        l = letter(padj - x["be"])
        if rule.endswith("+dir") and x["p"] < 0.5 and l in ("A", "B"):
            l = "C"
        return l

    def line(lbl, X, key="u_open"):
        X = [x for x in X if x[key] is not None]
        n = len(X)
        if not n:
            return f"  {lbl:10} n=   0"
        us = [x[key] for x in X]
        m = sum(us) / n
        se = statistics.pstdev(us) / math.sqrt(n) if n > 1 else float("nan")
        plus = sum(1 for x in X if x["plus"])
        return (f"  {lbl:10} n={n:4} plus$={plus:4} win={sum(x['won'] for x in X)/n:.3f} "
                f"units={sum(us):+7.1f} roi={m*100:+6.1f}% (±{se*100:.1f})")

    print(f"settled props with a sane two-way OPEN price: {len(sides)//2}  (graded sides: {len(sides)})\n")
    for rule in ["boost", "live", "market", "market+dir"]:
        G = [dict(x, grade=grade(x, rule)) for x in sides]
        print(f"== {rule}")
        for key, lbl in (("u_open", "at OPEN price"), ("u_close", "at CLOSE price")):
            print(f"  -- {lbl}")
            for gr in GRADES:
                print(line(gr, [x for x in G if x["grade"] == gr], key))
            print(line("A+B", [x for x in G if x["grade"] in ("A", "B")], key))
        ab = [x for x in G if x["grade"] in ("A", "B")]
        for wk in sorted({x["week"] for x in G}):
            print(line(f"A+B w{wk}", [x for x in ab if x["week"] == wk]))
        by_mk = defaultdict(list)
        for x in ab:
            by_mk[x["market"]].append(x)
        for mk in sorted(by_mk, key=lambda k: -len(by_mk[k]))[:6]:
            print(line(f"A+B {mk}"[:10], by_mk[mk]))
        print()

    # ── recorded shadow (what settle_bets wrote; always the settle scale) ─────
    rec = [r for r in rows if not r.get("push") and "grade_mkt" in r]
    if rec:
        print("== recorded shadow in bet_results.json (settle scale, units at -110)")
        def rl(lbl, gk, wk):
            ws = [r[wk] for r in rec if r.get(gk) in ("A", "B") and r.get(wk) is not None]
            n = len(ws); u = sum(100 / 110 if w == 1.0 else -1.0 for w in ws)
            print(f"  {lbl:28} n={n:4} win={(sum(ws)/n if n else 0):.3f} units={u:+7.1f}")
        rl("lean side, old boost grade", "grade_boost", "won_close")
        rl("lean side, live grade", "grade", "won_close")
        rl("lean side, market grade", "grade_mkt", "won_close")
        rl("alt side, live grade", "grade_alt", "won_alt")
        rl("alt side, market grade", "grade_mkt_alt", "won_alt")


if __name__ == "__main__":
    main()
