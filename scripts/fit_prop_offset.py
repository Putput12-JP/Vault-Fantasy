#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · PROP MODEL AS A MARKET OFFSET  (read-only research, writes nothing)
#
#  Does the Vault prop model know anything the market price does not? The price
#  engine (Sharp Money Props) takes the vig-free market as the fair probability.
#  This fits the model as a TILT on top of it:
#
#      logit P(side wins) = logit(p_market) + c * ( logit(p_model) - logit(p_market) )
#
#  c = 0 -> the model adds nothing (use the market), c = 1 -> trust the model
#  fully, 0 < c < 1 -> a measured blend. One parameter per market, fit by Newton
#  on the settled ledger (data/bet_results.json: p_model / p_market are for the
#  side the model leaned, won_open is that side's result at the opening price).
#
#  Reports, per market and pooled:
#    c and its standard error             (is the tilt distinguishable from 0?)
#    in-sample log-loss: market vs offset
#    walk-forward log-loss: fit on weeks < w, score week w (the honest number),
#      with a paired z of offset vs market
#    veto check: realized win% vs the market's own probability, bucketed by how
#      far the model disagrees with the market (does a big disagreement mean the
#      model is onto something, or that the model is wrong?)
#
#  Usage: python3 scripts/fit_prop_offset.py [--min-n=60] [--json=path]
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
EPS = 1e-4

ARG = dict((a.lstrip("-").split("=", 1) + [True])[:2] for a in sys.argv[1:])
MIN_N = int(ARG.get("min-n", 60))


def clamp(p): return min(1 - EPS, max(EPS, p))
def lg(p): p = clamp(p); return math.log(p / (1 - p))
def sig(x): return 1 / (1 + math.exp(-max(-40.0, min(40.0, x))))
def ll(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def load():
    rows = []
    for r in json.load(open(os.path.join(DATA, "bet_results.json")))["props"]:
        y, pm, mk = r.get("won_open"), r.get("p_model"), r.get("p_market")
        if y is None or pm is None or mk is None or r.get("push"): continue
        rows.append({"m": r["market"], "wk": int(r["week"]), "y": float(y), "pm": pm, "mk": mk,
                     "off": lg(mk), "d": lg(pm) - lg(mk)})
    return rows


def fit_c(rows, ridge=1e-3):
    """Newton for the single offset-logistic coefficient. Returns (c, se)."""
    c = 0.0
    for _ in range(25):
        g = h = 0.0
        for r in rows:
            p = sig(r["off"] + c * r["d"])
            g += (r["y"] - p) * r["d"]
            h += p * (1 - p) * r["d"] ** 2
        g -= ridge * c; h += ridge
        step = g / h if h > 0 else 0.0
        c += step
        if abs(step) < 1e-8: break
    info = sum(sig(r["off"] + c * r["d"]) * (1 - sig(r["off"] + c * r["d"])) * r["d"] ** 2 for r in rows) + ridge
    return c, (1 / math.sqrt(info) if info > 0 else float("nan"))


def walk_forward(rows):
    """Fit on weeks < w, score week w. Returns (n, ll_market, ll_offset, paired z, c_last)."""
    diffs, lm, lo, c_last = [], 0.0, 0.0, None
    for w in sorted({r["wk"] for r in rows}):
        tr = [r for r in rows if r["wk"] < w]; te = [r for r in rows if r["wk"] == w]
        if len(tr) < MIN_N or not te: continue
        c, _ = fit_c(tr); c_last = c
        for r in te:
            a, b = ll(r["y"], r["mk"]), ll(r["y"], sig(r["off"] + c * r["d"]))
            lm += a; lo += b; diffs.append(a - b)    # positive = offset better
    n = len(diffs)
    if n < 2: return n, None, None, None, c_last
    mu = sum(diffs) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (n - 1))
    return n, lm / n, lo / n, (mu / (sd / math.sqrt(n)) if sd > 0 else None), c_last


def veto(rows):
    out = []
    for lo, hi in ((-9, -0.30), (-0.30, -0.10), (-0.10, 0.10), (0.10, 0.30), (0.30, 9)):
        xs = [r for r in rows if lo <= r["d"] < hi]
        if len(xs) < 20: continue
        out.append({"model_vs_market_logit": [lo, hi], "n": len(xs),
                    "market_p": round(sum(r["mk"] for r in xs) / len(xs), 4),
                    "model_p": round(sum(r["pm"] for r in xs) / len(xs), 4),
                    "realized": round(sum(r["y"] for r in xs) / len(xs), 4)})
    return out


def report(name, rows):
    if len(rows) < MIN_N: return None
    c, se = fit_c(rows)
    n, lm, lo, z, c_last = walk_forward(rows)
    ins_m = sum(ll(r["y"], r["mk"]) for r in rows) / len(rows)
    ins_o = sum(ll(r["y"], sig(r["off"] + c * r["d"])) for r in rows) / len(rows)
    f = lambda v, d=4: "  -  " if v is None else f"{v:.{d}f}"
    print(f"{name:10} n={len(rows):5}  c={c:+.3f} (se {se:.3f}, {c / se:+.1f}se)  "
          f"in-sample LL mkt {ins_m:.4f} -> offset {ins_o:.4f}   "
          f"walk-fwd n={n:5} mkt {f(lm)} off {f(lo)} z={f(z, 2)}")
    return {"n": len(rows), "c": round(c, 4), "se": round(se, 4), "ll_market": round(ins_m, 5), "ll_offset": round(ins_o, 5),
            "wf": {"n": n, "ll_market": lm, "ll_offset": lo, "z": z}}


def main():
    rows = load()
    by = defaultdict(list)
    for r in rows: by[r["m"]].append(r)
    print(f"{len(rows)} settled sided props, weeks {sorted({r['wk'] for r in rows})}\n")
    res = {"pooled": report("POOLED", rows)}
    for m in sorted(by, key=lambda k: -len(by[k])):
        res[m] = report(m, by[m])
    print("\nVeto check (pooled): realized win% vs market, by how far the model disagrees")
    v = veto(rows)
    for b in v:
        print(f"  d in [{b['model_vs_market_logit'][0]:+.2f},{b['model_vs_market_logit'][1]:+.2f})  n={b['n']:4}  "
              f"market {b['market_p']:.3f}  model {b['model_p']:.3f}  realized {b['realized']:.3f}")
    res["veto"] = v
    if ARG.get("json"): json.dump(res, open(ARG["json"], "w"), indent=1)


if __name__ == "__main__":
    main()
