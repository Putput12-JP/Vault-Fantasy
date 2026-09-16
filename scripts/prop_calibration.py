#!/usr/bin/env python3
"""prop_calibration.py — is Vault's prop "Win %" honest?

Every settled prop in data/bet_results.json carries the model's projection
(`proj`) and the line it settled against. We reconstruct the EXACT calibrated
win probability the board shows — apply_calib(prob_fn_for(mp)(proj, line)) — for
the side the model picked, then compare that predicted Win % to what actually
happened (`won_close`). If the model is well-calibrated, the picks it graded at
"60%" should hit about 60% of the time.

This is NOT a simulation. The board's Win % is a closed-form probability, so the
honest check is empirical: bucket predictions, compare to real outcomes. Outputs
a reliability table, Brier score and calibration error (ECE), and writes
data/prop_calibration.json.

    python3 scripts/prop_calibration.py            # latest settled week
    python3 scripts/prop_calibration.py --week 1
    python3 scripts/prop_calibration.py --line open # judge at the flag line
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import build_prop_projections as B  # noqa: E402  (reuse the exact model math)


def clamp(p, lo=1e-6, hi=1 - 1e-6):
    return max(lo, min(hi, p))


def win_prob(mp, proj, line, side):
    """Calibrated model win probability for `side`, mirroring settle_bets.model_p_over."""
    if mp is None or proj is None or line is None:
        return None
    try:
        raw = B.prob_fn_for(mp)(proj, line)
        p = B.apply_calib(mp.get("calib"), raw)
        p = B.shrink_prob(p, mp.get("shrink", 1.0))
        p_over = clamp(p)
    except Exception:
        return None
    return p_over if side == "over" else 1.0 - p_over


BINS = [(0.0, 0.50), (0.50, 0.55), (0.55, 0.60), (0.60, 0.65),
        (0.65, 0.70), (0.70, 0.75), (0.75, 0.80), (0.80, 1.01)]


def bucket_label(lo, hi):
    if lo == 0.0:
        return "< 50%"
    if hi > 1.0:
        return "80%+"
    return f"{int(lo*100)}–{int(hi*100)}%"


def summarize(rows):
    """rows: list of (win_prob, outcome[0/1], market). Returns metrics dict."""
    n = len(rows)
    if not n:
        return None
    pred = sum(r[0] for r in rows) / n
    actual = sum(r[1] for r in rows) / n
    brier = sum((r[0] - r[1]) ** 2 for r in rows) / n
    logloss = sum(-(r[1] * math.log(clamp(r[0])) + (1 - r[1]) * math.log(clamp(1 - r[0]))) for r in rows) / n

    reliability, ece = [], 0.0
    for lo, hi in BINS:
        b = [r for r in rows if lo <= r[0] < hi] if hi <= 1.0 else [r for r in rows if r[0] >= lo]
        if not b:
            continue
        bn = len(b)
        bp = sum(r[0] for r in b) / bn
        ba = sum(r[1] for r in b) / bn
        reliability.append({"bucket": bucket_label(lo, hi), "n": bn,
                            "pred": round(bp * 100, 1), "actual": round(ba * 100, 1),
                            "gap": round((ba - bp) * 100, 1)})
        ece += bn / n * abs(ba - bp)

    return {"n": n, "pred_avg": round(pred * 100, 1), "actual_avg": round(actual * 100, 1),
            "brier": round(brier, 4), "logloss": round(logloss, 4),
            "ece": round(ece * 100, 1), "reliability": reliability}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, default=None, help="settled week (default: the latest settled)")
    ap.add_argument("--line", choices=["open", "close"], default="close",
                    help="judge at the flag/open line or the settle/close line (default: close)")
    args = ap.parse_args()

    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]
    res = json.load(open(os.path.join(DATA, "bet_results.json")))
    props = [p for p in res.get("props", []) if p.get("kind") == "prop"]
    if not props:
        print("No settled props in bet_results.json.")
        return

    weeks = sorted({p.get("week") for p in props if p.get("week") is not None})
    line_key = "line_" + args.line
    won_key = "won_" + args.line

    # Collect graded (win_prob, outcome, market) rows, per week and cumulative.
    per_week_rows, cum_rows, skipped = {}, [], 0
    for p in props:
        wk = p.get("week")
        mkt = p.get("market")
        mp = model.get(mkt)
        proj, line, side, won = p.get("proj"), p.get(line_key), p.get("side"), p.get(won_key)
        if wk is None or mp is None or proj is None or line is None or side not in ("over", "under") or won not in (0.0, 1.0) or p.get("push"):
            skipped += 1
            continue
        wp = win_prob(mp, proj, line, side)
        if wp is None:
            skipped += 1
            continue
        row = (wp, 1.0 if won >= 0.5 else 0.0, mkt)
        per_week_rows.setdefault(wk, []).append(row)
        cum_rows.append(row)

    def block(rows):
        ov = summarize(rows)
        if not ov:
            return None
        mk = {m: summarize([r for r in rows if r[2] == m]) for m in {r[2] for r in rows}}
        mk = {m: mk[m] for m in sorted(mk, key=lambda x: -mk[x]["n"])}
        return {"overall": ov, "by_market": mk}

    by_week = {str(wk): block(rows) for wk, rows in sorted(per_week_rows.items())}
    cumulative = block(cum_rows)
    latest_week = weeks[-1] if weeks else None

    out = {"season": res.get("props", [{}])[0].get("season"), "generated": res.get("generated"),
           "line_basis": args.line, "latest_week": latest_week, "skipped": skipped,
           "cumulative": cumulative, "by_week": by_week}
    json.dump(out, open(os.path.join(DATA, "prop_calibration.json"), "w"), indent=2)

    # ── report (the requested week, or the latest) ───────────────────────────
    week = args.week if args.week is not None else latest_week
    blk = by_week.get(str(week))
    if not blk:
        print(f"No usable settled props for week {week}.")
        return
    overall, markets = blk["overall"], blk["by_market"]
    print(f"\n  PROP WIN% CALIBRATION — Week {week} (judged at the {args.line} line)\n")
    print(f"  Settled picks graded : {overall['n']}   (skipped {skipped}: pushes / no model / unsettled)")
    print(f"  Model said, on avg   : {overall['pred_avg']}% to hit")
    print(f"  Actually hit         : {overall['actual_avg']}%")
    gap = round(overall['actual_avg'] - overall['pred_avg'], 1)
    verdict = "spot on" if abs(gap) <= 1.5 else ("model was UNDER-confident" if gap > 0 else "model was OVER-confident")
    print(f"  Headline gap         : {gap:+} pts  →  {verdict}")
    print(f"  Brier score          : {overall['brier']}   (0 = perfect, 0.25 = coin flip; lower is better)")
    print(f"  Calibration error    : {overall['ece']}%  (avg gap between promised and real, weighted)\n")
    print("  Reliability — when the model promised X, how often did it hit?")
    print("    bucket        n     said    hit     gap")
    print("    " + "-" * 42)
    for r in overall["reliability"]:
        print(f"    {r['bucket']:<11} {r['n']:>4}   {r['pred']:>5}%  {r['actual']:>5}%  {r['gap']:>+5}")
    print("\n  By market (most picks first):")
    print("    market            n    said    hit     gap   brier")
    print("    " + "-" * 50)
    for m, s in markets.items():
        if s and s["n"] >= 5:
            mgap = round(s["actual_avg"] - s["pred_avg"], 1)
            print(f"    {m:<15} {s['n']:>4}   {s['pred_avg']:>5}%  {s['actual_avg']:>5}%  {mgap:>+5}   {s['brier']}")
    print("\n  → data/prop_calibration.json\n")


if __name__ == "__main__":
    main()
