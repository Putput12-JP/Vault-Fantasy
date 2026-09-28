#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · PROP MODEL A/B ON REAL LINES
#
#  The go/no-go for any prop-model change (model-upgrade plan, Week 2+). Scores
#  two prop_model.json files on Vault's OWN settled real lines
#  (data/bet_results.json) at the closing line, against the de-vigged closing
#  market, using the model scoreboard's math:
#
#    • per market: log-loss of A, of B and of the market; skill vs market;
#      paired z of B vs A (same bets: positive = B better)
#    • "leans over" share: how often each model's probability favors the over,
#      next to how often the over actually hit (a lopsided curve shows up here)
#    • walk-forward market blend: fit p = sig(a*logit(market) + b*logit(model))
#      on the weeks before each week, score that week. b near 0 means the model
#      adds nothing the market doesn't already know at the close.
#
#  Both files are re-priced at the same projections (the ledger's `proj`), so
#  the comparison isolates the distribution / calibration change. Note: a
#  prop_model.json built with the in-season overlay was partly fitted on these
#  same weeks; build candidates with and without it when that matters.
#
#  Usage:
#    python3 scripts/backtest_props_vs_market.py --b=/path/to/candidate.json
#    python3 scripts/backtest_props_vs_market.py --a=old.json --b=new.json --markets=rec_yd,rush_yd
# ════════════════════════════════════════════════════════════════════════════
import argparse, json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)
import build_model_scoreboard as M
import settle_bets as SB


def load(path):
    return json.load(open(path))["markets"]


def lg(p): p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))
def sig(x): return 1 / (1 + math.exp(-max(-60, min(60, x))))


def fit_blend(rows, key):
    """Grid MLE for p = sig(a*logit(q) + b*logit(model)). Stdlib, small grid."""
    best = None
    for a10 in range(0, 16):
        a = a10 / 10
        for b20 in range(-6, 13):
            b = b20 / 20
            s = sum(M.ll(r["y"], sig(a * lg(r["q"]) + b * lg(r[key]))) for r in rows)
            if best is None or s < best[0]: best = (s, a, b)
    return best[1], best[2]


class Pair:
    """B vs A on the same bets (paired z, positive = B better)."""
    def __init__(self): self.n = 0; self.d = 0.0; self.d2 = 0.0
    def add(self, y, pa, pb):
        dd = M.ll(y, pa) - M.ll(y, pb); self.n += 1; self.d += dd; self.d2 += dd * dd
    def z(self):
        if self.n < 2: return None
        m = self.d / self.n; v = max(self.d2 / self.n - m * m, 0)
        return round(m / math.sqrt(v / self.n), 2) if v > 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=os.path.join(DATA, "prop_model.json"))
    ap.add_argument("--b", required=True)
    ap.add_argument("--markets", default="")
    args = ap.parse_args()
    A, Bm = load(args.a), load(args.b)
    only = set(x for x in args.markets.split(",") if x)
    br = json.load(open(os.path.join(DATA, "bet_results.json")))

    rows = []
    for p in br.get("props") or []:
        mk, a, lc, proj = p["market"], p.get("actual"), p.get("line_close"), p.get("proj")
        if only and mk not in only: continue
        if a is None or lc is None or proj is None or abs(a - lc) < 1e-9: continue
        q = M.devig_power(p.get("close_over"), p.get("close_under"))
        pa = SB.model_p_over(A.get(mk), proj, lc)
        pb = SB.model_p_over(Bm.get(mk), proj, lc)
        if q is None or pa is None or pb is None: continue
        rows.append({"m": mk, "w": p["week"], "y": 1.0 if a > lc else 0.0, "q": q, "A": pa, "B": pb})
    if not rows:
        print("no comparable settled props"); return

    acc = defaultdict(lambda: {"A": M.Acc(), "B": M.Acc()}); pair = defaultdict(Pair)
    over = defaultdict(lambda: [0, 0, 0, 0])   # A over, B over, actual over, n
    for r in rows:
        for g in ("all", r["m"]):
            acc[g]["A"].add(r["y"], r["A"], r["q"]); acc[g]["B"].add(r["y"], r["B"], r["q"])
            pair[g].add(r["y"], r["A"], r["B"])
            o = over[g]; o[0] += r["A"] > 0.5; o[1] += r["B"] > 0.5; o[2] += r["y"]; o[3] += 1

    print(f"A = {args.a}\nB = {args.b}\nat the close, market = power-de-vigged consensus\n")
    print(f"{'market':<12}{'n':>5}  {'LL A':>7} {'LL B':>7} {'LL mkt':>7}  {'skill A':>8} {'skill B':>8}  {'z B vs A':>8}   leans over A / B / actual")
    for g in ["all"] + sorted(k for k in acc if k != "all"):
        a, b = acc[g]["A"].out(), acc[g]["B"].out(); o = over[g]; z = pair[g].z()
        print(f"{g:<12}{a['n']:>5}  {a['logloss_vault']:>7.4f} {b['logloss_vault']:>7.4f} {a['logloss_market']:>7.4f}  "
              f"{a['skill']:>+8.3f} {b['skill']:>+8.3f}  {('  –' if z is None else f'{z:+.1f}'):>8}   "
              f"{o[0] / o[3]:4.0%} / {o[1] / o[3]:4.0%} / {o[2] / o[3]:4.0%}")

    weeks = sorted({r["w"] for r in rows})
    if len(weeks) >= 2:
        print("\nwalk-forward market blend (fit on earlier weeks, scored on the next):")
        for key in ("A", "B"):
            cum = M.Acc()
            for w in weeks[1:]:
                tr = [r for r in rows if r["w"] < w]; te = [r for r in rows if r["w"] == w]
                a, b = fit_blend(tr, key)
                for r in te: cum.add(r["y"], sig(a * lg(r["q"]) + b * lg(r[key])), r["q"])
                print(f"  {key} wk {w}: weight on market {a:.1f}, on model {b:+.2f}")
            o = cum.out()
            print(f"  {key} blended: n={o['n']} skill {o['skill']:+.3f} z {o['z']:+.1f}")


if __name__ == "__main__":
    main()
