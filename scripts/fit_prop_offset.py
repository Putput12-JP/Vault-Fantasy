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
#  --plays[=path]  score the LIVE Sharp Money play ledger instead (prop_plays.json
#      from the sharp-data branch; default: git show origin/sharp-data:prop_plays.json).
#      Each play carries model.d, the model's logit gap to the Pinnacle/Kalshi fair
#      on the called side. Reports, by d bucket (model confirms / neutral / disagrees):
#      how far the fair price moved to the close, settled units at the called price,
#      and (once n allows) c fit on settled outcomes with the fair price as offset.
#
#  Usage: python3 scripts/fit_prop_offset.py [--min-n=60] [--json=path] [--plays[=path]]
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


def load_plays(path):
    import subprocess
    if path is True:
        raw = subprocess.run(["git", "-C", os.path.join(HERE, ".."), "show", "origin/sharp-data:prop_plays.json"],
                             capture_output=True, text=True, check=True).stdout
    else:
        raw = open(path).read()
    d = json.loads(raw)
    return list((d.get("plays") or d).values())


def mean_se(v):
    n = len(v)
    if n < 2: return (v[0] if v else None), None
    mu = sum(v) / n
    return mu, math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1) / n)


def plays_report(path):
    P = load_plays(path)
    withm = [p for p in P if p.get("model") and p["model"].get("d") is not None]
    print(f"{len(P)} logged plays, {len(withm)} carry a model block "
          f"({sum(p.get('status') in ('won', 'lost') for p in withm)} settled, "
          f"{sum(p.get('closeFair') is not None for p in withm)} with a close)")
    if not withm:
        print("no plays logged since the model block shipped yet: nothing to score"); return {}
    out = {}
    print("\nBy how the model sees the called side (d = model logit minus fair logit):")
    print("  bucket            n   fair->close (pts)        settled  W-L    units/bet")
    for name, lo, hi in (("model disagrees", -9, -0.10), ("neutral", -0.10, 0.10), ("model confirms", 0.10, 0.30), ("strong confirm", 0.30, 9)):
        xs = [p for p in withm if lo <= p["model"]["d"] < hi]
        mv = [(p["closeFair"] - p["called"]["fair"]) * 100 for p in xs if p.get("closeFair") is not None and p["called"].get("fair") is not None]
        st = [p for p in xs if p.get("status") in ("won", "lost")]
        mu, se = mean_se(mv)
        units = sum(p.get("units", 0) for p in st)
        w = sum(p["status"] == "won" for p in st)
        mtxt = "   -   " if mu is None else f"{mu:+.2f}" + (f" (se {se:.2f})" if se is not None else "")
        print(f"  {name:15} {len(xs):4}   {mtxt:22} {len(st):6}  {w}-{len(st) - w}  {units / len(st) if st else float('nan'):+.3f}")
        out[name] = {"n": len(xs), "move_pts": mu, "se": se, "settled": len(st), "units": round(units, 3)}
    st = [p for p in withm if p.get("status") in ("won", "lost") and p["called"].get("fair") is not None]
    if len(st) >= MIN_N:
        rows = [{"y": 1.0 if p["status"] == "won" else 0.0, "off": lg(p["called"]["fair"]), "d": p["model"]["d"]} for p in st]
        c, se = fit_c(rows)
        print(f"\nc fit on {len(st)} settled plays, fair price as offset: c = {c:+.3f} (se {se:.3f})")
        out["c_live"] = {"c": c, "se": se, "n": len(st)}
    else:
        print(f"\nc on settled outcomes needs {MIN_N}+ settled plays with a model block (have {len(st)}); the move column is the early read")
    return out


def main():
    if ARG.get("plays"):
        res = plays_report(ARG["plays"])
        if ARG.get("json"): json.dump(res, open(ARG["json"], "w"), indent=1)
        return
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
