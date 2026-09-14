#!/usr/bin/env python3
# ============================================================================
# VAULT · GAME TOTALS PROJECTION-BIAS WATCH
#
# A focused monitor for ONE question raised by the Week-1 game retro: does
# Vault's game TOTAL projection systematically run high or low vs the actual
# combined score? Week 1 in-season came in ~7.5pt LOW on 13 games — real, but
# far too thin to correct. This tracks it week to week off the settlement tape
# (data/bet_results.json → in-season total picks) so we know when it's a stable
# signal worth a correction (the totals analog of the QB pass proj_adj) versus
# still noise.
#
# bias = mean(proj_err) over in-season total picks, where proj_err is Vault's
# projected total minus the actual combined score. NEGATIVE = Vault runs LOW
# (under-projects scoring); POSITIVE = runs high. Preseason-rated games
# (model_offseason) are excluded — they use preseason team ratings.
#
# The verdict applies the same shrink discipline as the shipped model overlays:
# a correction is only worth building once the sample is real (ACT_MIN games)
# AND the shrunk bias clears a points threshold, so a lucky few weeks can't
# trigger it. Pure standard library.
#
# Usage:
#   python3 scripts/totals_bias_watch.py           # trend table + verdict
#   python3 scripts/totals_bias_watch.py --json     # machine-readable one-liner
# ============================================================================
import json, os, argparse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

K_SHRINK = 60      # totals accrue ~13/week; K≈4-5 weeks before the shrunk bias bites
ACT_MIN = 45       # in-season total games before a correction is even considered
ACT_PTS = 3.0      # shrunk bias (points) that, with enough sample, warrants acting


def load_total_rows():
    d = json.load(open(os.path.join(DATA, "bet_results.json")))
    rows = []
    for g in d.get("games", []):
        if g.get("market") != "total" or g.get("model_offseason"):
            continue
        if g.get("proj_err") is None or g.get("week") is None:
            continue
        rows.append({"week": g["week"], "err": g["proj_err"]})
    return d.get("generated"), rows


def summarize(rows):
    n = len(rows)
    if not n:
        return None
    bias = sum(r["err"] for r in rows) / n
    mae = sum(abs(r["err"]) for r in rows) / n
    w = n / (n + K_SHRINK)
    return {"n": n, "bias": bias, "mae": mae, "shrunk": w * bias, "w": w}


def verdict(cum):
    if not cum:
        return "NO DATA", "no settled in-season total games yet"
    if cum["n"] < ACT_MIN:
        return "MONITORING", f"n={cum['n']} (<{ACT_MIN}) — too thin to correct; keep watching"
    if abs(cum["shrunk"]) >= ACT_PTS:
        d = "LOW (under-projects scoring)" if cum["bias"] < 0 else "HIGH (over-projects scoring)"
        return "SIGNAL", (f"totals run {d} — {cum['bias']:+.1f}pt raw over {cum['n']} games, "
                          f"shrunk {cum['shrunk']:+.1f}pt. Consider a totals proj_adj (see the QB pass "
                          f"proj_adj precedent: measured, sample-shrunk, bounded).")
    return "STABLE", (f"bias {cum['bias']:+.1f}pt over {cum['n']} games (shrunk {cum['shrunk']:+.1f}pt) "
                      "— within noise; no correction warranted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    generated, rows = load_total_rows()
    byweek = defaultdict(list)
    for r in rows:
        byweek[r["week"]].append(r)
    weeks = sorted(byweek)
    cum = summarize(rows)
    tag, msg = verdict(cum)

    if args.json:
        print(json.dumps({
            "generated": generated, "tag": tag, "message": msg,
            "cumulative": cum,
            "by_week": {str(wk): summarize(byweek[wk]) for wk in weeks},
        }))
        return

    print(f"Totals projection-bias watch  ·  tape {generated}")
    print("(bias = Vault projected total − actual combined score; − = runs LOW / under-projects)\n")
    print(f"{'week':>6s} {'games':>6s} {'bias':>8s} {'MAE':>7s}")
    run = []
    for wk in weeks:
        run += byweek[wk]
        s = summarize(byweek[wk]); c = summarize(run)
        print(f"{('Wk '+str(wk)):>6s} {s['n']:6d} {s['bias']:+7.1f}  {s['mae']:6.1f}"
              f"   cum {c['bias']:+.1f} ({c['n']})")
    if cum:
        print(f"\ncumulative: {cum['bias']:+.1f}pt over {cum['n']} games "
              f"(MAE {cum['mae']:.1f}, shrunk {cum['shrunk']:+.1f}pt)")
    print(f"\n[{tag}] {msg}")


if __name__ == "__main__":
    main()
