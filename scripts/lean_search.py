#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · LEAN SEARCH  →  data/lean_trials.json
#
#  A refine-and-rerun loop with the guardrails that make it safe to repeat:
#    - each CANDIDATE (a feature set for the stack in lean_loop.py) is scored on THREE
#      folds it never trained on: replay 2024 -> 2025, replay 2025 -> 2024, and
#      replay -> live 2026 (forward). Metric = log-loss over ALL lines in the fold
#      (thousands of rows), not hit rate on a hand-picked slice, so picking the best of
#      many tries cannot flatter it much.
#    - ACCEPT only if it beats the incumbent on all three folds AND the pooled paired
#      bootstrap 95% interval for the improvement excludes 0. Otherwise REJECT.
#    - EVERY trial is appended to the log with its numbers, so how many looks we have
#      taken is on the record (more looks = a higher bar, see MIN_GAIN).
#
#    python3 scripts/lean_search.py
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, random, statistics as st, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lean_loop as L

DATA = L.DATA; TRIALS = os.path.join(DATA, "lean_trials.json")
MARKETS = ["pass_att", "pass_cmp", "pass_td", "pass_yd", "rec", "rec_yd", "rush_att", "rush_yd"]
lg, sig = L.lg, L.sig

# ── candidates: row -> feature vector ───────────────────────────────────────
def base(r): return [1.0, lg(r["p"]), lg(r["q"]), r["gap"]]
def market_only(r): return [1.0, lg(r["q"])]
def per_market_icpt(r): return base(r) + [1.0 if r["mkt"] == m else 0.0 for m in MARKETS]
def per_market_model(r): return base(r) + [lg(r["p"]) * (1.0 if r["mkt"] == m else 0.0) for m in MARKETS]
def side_split(r):
    ov = 1.0 if r["p"] >= 0.5 else 0.0
    return base(r) + [ov, ov * lg(r["p"]), ov * lg(r["q"])]
def agree(r):                                           # model and market on the same side
    same = 1.0 if (r["p"] >= .5) == (r["q"] >= .5) else 0.0
    return base(r) + [same, same * abs(lg(r["p"]) - lg(r["q"]))]
def drop_qbvol(r):                                      # QB volume markets carry no information: zero the model there
    z = 1.0 if r["mkt"] in ("pass_att", "pass_cmp", "pass_yd") else 0.0
    return [1.0, lg(r["p"]) * (1 - z), lg(r["q"]), r["gap"] * (1 - z)]
def squares(r): return base(r) + [lg(r["q"]) ** 2, (lg(r["p"]) - lg(r["q"])) ** 2]
def _mv(r): return r.get("mv") or 0.0
def _dq(r): return (lg(r["q"]) - lg(r["qo"])) if r.get("qo") else 0.0
def line_move(r): return base(r) + [_mv(r)]
def price_move(r): return base(r) + [_dq(r)]
def move_both(r): return base(r) + [_mv(r), _dq(r)]
def move_vs_model(r):                                   # did the market move TOWARD or AWAY from the model's side?
    side = 1.0 if r["p"] >= .5 else -1.0
    return base(r) + [side * _dq(r), side * _mv(r)]
def open_price(r): return base(r) + [lg(r["qo"]) if r.get("qo") else lg(r["q"])]
CANDS = {"market_only": market_only, "incumbent(base)": base, "per_market_icpt": per_market_icpt, "per_market_model": per_market_model,
         "side_split": side_split, "agree_interaction": agree, "zero_model_on_QB_volume": drop_qbvol, "squares": squares,
         "line_move": line_move, "price_move": price_move, "move_both": move_both, "move_vs_model_side": move_vs_model, "open_price": open_price}


def fit(rows, feats, lam=1.0, it=25):
    X = [feats(r) for r in rows]; y = [r["y"] for r in rows]; sw = [L.LIVE_W if r["live"] else 1.0 for r in rows]; k = len(X[0]); w = [0.0] * k
    for _ in range(it):
        g = [0.0] * k; H = [[0.0] * k for _ in range(k)]
        for xi, yi, wi in zip(X, y, sw):
            p = sig(sum(a * b for a, b in zip(w, xi)))
            for a in range(k):
                g[a] += wi * (p - yi) * xi[a]
                for b in range(k): H[a][b] += wi * p * (1 - p) * xi[a] * xi[b]
        for a in range(1, k): g[a] += lam * w[a]; H[a][a] += lam
        for a in range(k): H[a][a] += 1e-9
        A = [H[i][:] + [g[i]] for i in range(k)]
        for i in range(k):
            piv = max(range(i, k), key=lambda q: abs(A[q][i])); A[i], A[piv] = A[piv], A[i]
            for j in range(i + 1, k):
                f = A[j][i] / A[i][i]
                for c in range(i, k + 1): A[j][c] -= f * A[i][c]
        dw = [0.0] * k
        for i in reversed(range(k)): dw[i] = (A[i][k] - sum(A[i][j] * dw[j] for j in range(i + 1, k))) / A[i][i]
        w = [a - b for a, b in zip(w, dw)]
    return w


def losses(rows, feats, w):
    out = []
    for r in rows:
        p = min(max(sig(sum(a * b for a, b in zip(w, feats(r)))), 1e-6), 1 - 1e-6)
        out.append(-math.log(p if r["y"] else 1 - p))
    return out


def folds():
    rep = L.load_replay(); live = L.load_live()
    for r in rep: r["live"] = False
    return {"2024->2025": ([r for r in rep if r["yr"] == 2024], [r for r in rep if r["yr"] == 2025]),
            "2025->2024": ([r for r in rep if r["yr"] == 2025], [r for r in rep if r["yr"] == 2024]),
            "replay->live2026": (rep, live)}


def score(feats, F):
    per = {}
    for name, (tr, te) in F.items():
        w = fit(tr, feats); ls = losses(te, feats, w)
        hit = st.mean(((sig(sum(a * b for a, b in zip(w, feats(r)))) >= .5) == bool(r["y"])) for r in te)
        per[name] = {"ll": st.mean(ls), "hit": hit, "n": len(te), "_l": ls}
    return per


def main():
    random.seed(11)
    F = folds(); prior = json.load(open(TRIALS))["trials"] if os.path.exists(TRIALS) else []
    inc = score(base, F); results = []
    print(f"{'candidate':26s} " + " ".join(f"{k:>20s}" for k in F) + "   verdict")
    for name, fn in CANDS.items():
        s = score(fn, F); better = {k: inc[k]["ll"] - s[k]["ll"] for k in F}      # >0 = lower log-loss than incumbent
        diffs = [a - b for k in F for a, b in zip(inc[k]["_l"], s[k]["_l"])]; n = len(diffs)
        boots = sorted(st.mean(random.choices(diffs, k=n)) for _ in range(300)); lo = boots[7]
        n_looks = len(prior) + len(results) + 1
        min_gain = 0.0003 * math.log(1 + n_looks)                                       # the bar rises with the number of looks taken
        ok = name not in ("incumbent(base)", "market_only") and all(v > 0 for v in better.values()) and lo > 0 and st.mean(diffs) > min_gain
        verdict = "ACCEPT" if ok else "reject"
        print(f"{name:26s} " + " ".join(f"{s[k]['ll']:.4f} ({better[k]*1e4:+5.1f}e-4) {s[k]['hit']*100:4.1f}%" for k in F) + f"   {verdict} (pooled gain {st.mean(diffs)*1e4:+.1f}e-4, CI lo {lo*1e4:+.1f}e-4)")
        results.append({"t": datetime.now(timezone.utc).isoformat(), "candidate": name, "verdict": verdict, "pooled_gain": round(st.mean(diffs), 6),
                        "ci_lo": round(lo, 6), "min_gain": round(min_gain, 6), "folds": {k: {"ll": round(s[k]["ll"], 5), "hit": round(s[k]["hit"], 4), "n": s[k]["n"], "vs_incumbent": round(better[k], 6)} for k in F}})
    json.dump({"note": "Every candidate tried, with its out-of-fold numbers. ACCEPT needs all 3 folds better, bootstrap CI > 0, and gain > a bar that rises with trials taken.",
               "trials": prior + results}, open(TRIALS, "w"), indent=1)
    print(f"\n[lean-search] {len(results)} candidates scored, {len(prior)+len(results)} total looks logged → {TRIALS}")


if __name__ == "__main__":
    main()
