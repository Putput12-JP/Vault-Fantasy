#!/usr/bin/env python3
"""Backtest: grade props against each side's REAL price instead of a flat 55%.

Today settle_bets.grade_for() (and the board) grade every prop against one
fixed break-even (0.55). A -130 under really needs 56.5% and a +100 over 50%,
so juiced unders grade too kind and cheap overs too harsh. This replays the
settled picks under four grading rules and scores every one at the CLOSING
consensus price (priced rows only, same rows for every rule):

  flat55       production: grade the model side vs 0.55
  price_open   grade the model side vs its OPENING price's implied prob
               (the price Vault saw when it graded - usable live)
  price_close  same vs the CLOSING price (look-ahead; a ceiling, not usable)
  open_pick    grade BOTH sides vs their opening prices, take the better margin

Only this season has book prices, so the sample is small; the report prints a
standard error per bucket. Usage:
  python3 scripts/backtest_price_grades.py [--data DIR] [--season 2026]
"""
import argparse, json, math, os, sys, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settle_bets as S

GRADES = ["A", "B", "C", "D", "F"]


def dec(a): return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


def open_prices(data_dir):
    """(season, seasonType, week, pid, market) -> validated OPENING prices."""
    props = json.load(open(os.path.join(data_dir, "prop_line_history.json"))).get("props", {})
    out = {}
    for r in props.values():
        k = (str(r.get("season")), (r.get("seasonType") or "").lower(), r.get("week"), r.get("pid"), r.get("market"))
        cp = S.close_prices(r.get("open") or {})           # same two-way sanity check
        if cp["close_over"] is not None:
            out[k] = (cp["close_over"], cp["close_under"])
    return out


def letter(p_side, g, be):
    return S.grade_for(p_side, g, be)


def margin(p_side, g, be):
    return 0.5 + (p_side - 0.5) * g / (g + 6) - be


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=S.DATA)
    ap.add_argument("--season", default="2026")
    a = ap.parse_args()
    S.DATA = a.data
    picks, _ = S.settle_props(a.season)
    opens = open_prices(a.data)

    rows = []
    for p in picks:
        if p["push"] or p["won_close"] is None or p["p_model"] is None or not p["side"]:
            continue
        if p["close_over"] is None:
            continue
        k = (p["season"], p["seasonType"], p["week"], p["pid"], p["market"])
        if k not in opens:
            continue
        oo, ou = opens[k]
        side, g = p["side"], p["grade_n"]
        p_over = p["p_model"] if side == "over" else 1 - p["p_model"]
        over_won = p["won_close"] if side == "over" else 1 - p["won_close"]
        rows.append(dict(week=p["week"], market=p["market"], side=side, g=g, p_over=p_over,
                         over_won=over_won, oo=oo, ou=ou, co=p["close_over"], cu=p["close_under"]))

    def graded(rule):
        out = []
        for r in rows:
            side = r["side"]
            if rule == "open_pick":
                mo = margin(r["p_over"], r["g"], S.am_prob(r["oo"]))
                mu = margin(1 - r["p_over"], r["g"], S.am_prob(r["ou"]))
                side = "over" if mo >= mu else "under"
            ps = r["p_over"] if side == "over" else 1 - r["p_over"]
            if rule == "flat55":
                be = 0.55
            elif rule == "price_close":
                be = S.am_prob(r["co"] if side == "over" else r["cu"])
            else:
                be = S.am_prob(r["oo"] if side == "over" else r["ou"])
            won = r["over_won"] if side == "over" else 1 - r["over_won"]
            px = r["co"] if side == "over" else r["cu"]
            u = (dec(px) - 1) if won == 1 else -1.0
            out.append(dict(grade=letter(ps, r["g"], be), side=side, won=won, u=u, week=r["week"]))
        return out

    def line(lbl, X):
        n = len(X)
        if not n:
            return f"  {lbl:6} n=   0"
        us = [x["u"] for x in X]; m = sum(us) / n
        se = statistics.pstdev(us) / math.sqrt(n) if n > 1 else float("nan")
        ov = sum(1 for x in X if x["side"] == "over")
        return (f"  {lbl:6} n={n:4} overs={ov:4} win={sum(x['won'] for x in X)/n:.3f} "
                f"units={sum(us):+7.1f} roi={m*100:+6.1f}% (±{se*100:.1f})")

    print(f"rows priced at open AND close: {len(rows)} (season {a.season})\n")
    for rule in ["flat55", "price_open", "price_close", "open_pick"]:
        G = graded(rule)
        print(rule)
        for gr in GRADES:
            print(line(gr, [x for x in G if x["grade"] == gr]))
        print(line("A+B", [x for x in G if x["grade"] in ("A", "B")]))
        print(line("A-C", [x for x in G if x["grade"] in ("A", "B", "C")]))
        for w in sorted({x["week"] for x in G}):
            print(line(f"A+B w{w}", [x for x in G if x["grade"] in ("A", "B") and x["week"] == w]))
        print()


if __name__ == "__main__":
    main()
