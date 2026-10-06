#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · LEAN LEARNING LOOP  →  data/lean_stack.json  (+ data/lean_stack_log.json)
#
#  Goal: the model's LEAN (over/under vs the posted line) should win against the
#  actual result as often as it can, and the confidence we attach must be TRUE.
#  Every refit is judged only on predictions made BEFORE the games, never on data
#  the weights were fit on:
#
#    stack     P(over) = sigmoid(w0 + w1*logit(model) + w2*logit(market) + w3*gap)
#              fit by ridge logistic regression on (a) the 2024-25 replay of the
#              shipped model on real ESPN BET lines (data/lean_replay.json) and
#              (b) this season's settled live props (data/bet_results.json), live
#              rows weighted LIVE_W x because they are the real distribution.
#    walk-fwd  for each live week W: fit on the replay + live weeks < W, predict W,
#              record hit rate / confidence band. These frozen predictions are the
#              scoreboard. (First run, 2026 wks 1-4: replay-tuned stack hit 57.6% at
#              "64.7% confidence", i.e. overconfident, which is why live rows now train it.)
#    publish   a confidence band is "verified" only if its forward hit rate is within
#              CAL_TOL of what it predicted over MIN_N+ plays. Unverified bands are
#              shown as such, never as a number to quote.
#
#  Runs after settlement in update-bet-settlement.yml; each run appends one entry to
#  lean_stack_log.json so progress (or the lack of it) is visible week over week.
#  The stack is a SHADOW: nothing in the app reads it until bands verify.
#
#    python3 scripts/lean_loop.py                 # refit + walk-forward + write
#    python3 scripts/lean_loop.py --build-replay  # rebuild data/lean_replay.json (network, slow)
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, sys, statistics as st
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
REPLAY, RESULTS = os.path.join(DATA, "lean_replay.json"), os.path.join(DATA, "bet_results.json")
OUT, LOG = os.path.join(DATA, "lean_stack.json"), os.path.join(DATA, "lean_stack_log.json")
LIVE_W, LAM = 3.0, 1.0
BANDS = (0.55, 0.60, 0.65)
MIN_N, CAL_TOL = 100, 0.04
lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))
sig = lambda z: 1 / (1 + math.exp(-max(-30, min(30, z))))


def build_replay():
    import csv, io
    sys.path.insert(0, HERE)
    import build_prop_market_prior as P
    B = P.B
    games = list(csv.DictReader(io.StringIO(P.get_text(P.GAMES_URL)))); gmap = {g["game_id"]: g for g in games}
    e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(P.get_text(P.PLAYERS_URL))) if r.get("espn_id")}
    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]
    W = P.load_weeks([min(P.SEASONS) - 1, *P.SEASONS]); rows = []
    for season in P.SEASONS:
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in P.load_lines(season, games, False):
            m = model.get(mkt); name = e2n.get(ath); g = gmap.get(gid)
            if not (m and name and g): continue
            yr, wk = int(g["season"]), int(g["week"]); pos, cur = W.get((P.nkey(name), yr), (None, []))
            if pos is None or pos not in m["pos"]: continue
            row = next((w for w in cur if B.num(w.get("wk")) == wk), None)
            if row is None: continue
            prev = W.get((P.nkey(name), yr - 1), (None, []))[1]
            proj = P.project(m, mkt, prev + [w for w in cur if (B.num(w.get("wk")) or 0) < wk]); act = P.actual_of(m, row)
            if proj is None or act is None or lc is None or oc is None or uc is None or abs(act - lc) < 1e-9: continue
            qo = (P.imp(oo) / (P.imp(oo) + P.imp(uo))) if (oo is not None and uo is not None) else None
            rows.append([mkt, yr, round(P.p_over(m, proj, lc), 4), round(P.imp(oc) / (P.imp(oc) + P.imp(uc)), 4), int(act > lc),
                         round((proj - lc) / max(abs(lc), 0.5), 4), None if lo is None else round((lc - lo) / max(abs(lc), 0.5), 4),
                         None if qo is None else round(qo, 4)])
    json.dump({"cols": ["mkt", "yr", "p", "q", "y", "gap", "mv", "qo"], "rows": rows, "built": datetime.now(timezone.utc).isoformat()}, open(REPLAY, "w"), separators=(",", ":"))
    print(f"[lean-loop] replay: {len(rows)} lines → {REPLAY}")


def load_replay():
    d = json.load(open(REPLAY)); c = d["cols"]
    return [dict(zip(c, r), live=False, wk=0) for r in d["rows"]]


def _devig_open(r):
    try:
        imp = lambda a: 100 / (a + 100) if a > 0 else -a / (-a + 100)
        o, u = r.get("open_over"), r.get("open_under")
        return None if o is None or u is None else imp(o) / (imp(o) + imp(u))
    except Exception:
        return None


def load_live():
    out = []
    for r in json.load(open(RESULTS)).get("props", []):
        if r.get("actual") is None or r.get("line_close") is None or r.get("push") or r.get("p_model") is None or r.get("p_market") is None: continue
        if r["actual"] == r["line_close"] or r.get("side") not in ("over", "under"): continue
        s = r["side"] == "over"
        out.append({"mkt": r["market"], "yr": int(r["season"]), "wk": int(r["week"]), "p": r["p_model"] if s else 1 - r["p_model"],
                    "q": r["p_market"] if s else 1 - r["p_market"], "y": int(r["actual"] > r["line_close"]), "live": True,
                    "gap": ((r.get("proj") or r["line_close"]) - r["line_close"]) / max(abs(r["line_close"]), 0.5),
                    "mv": None if r.get("line_open") is None else (r["line_close"] - r["line_open"]) / max(abs(r["line_close"]), 0.5),
                    "qo": _devig_open(r)})
    return out


feats = lambda r: [1.0, lg(r["p"]), lg(r["q"]), r["gap"]]


def fit(rows, it=25):
    k = 4; w = [0.0] * k
    X = [feats(r) for r in rows]; y = [r["y"] for r in rows]; sw = [LIVE_W if r["live"] else 1.0 for r in rows]
    for _ in range(it):
        g = [0.0] * k; H = [[0.0] * k for _ in range(k)]
        for xi, yi, wi in zip(X, y, sw):
            p = sig(sum(a * b for a, b in zip(w, xi)))
            for a in range(k):
                g[a] += wi * (p - yi) * xi[a]
                for b in range(k): H[a][b] += wi * p * (1 - p) * xi[a] * xi[b]
        for a in range(1, k): g[a] += LAM * w[a]; H[a][a] += LAM
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


prob = lambda w, r: sig(sum(a * b for a, b in zip(w, feats(r))))


def main():
    if "--build-replay" in sys.argv: return build_replay()
    replay, live = load_replay(), load_live()
    if os.path.exists(LOG) and "--force" not in sys.argv:        # settlement runs every ~15 min; only learn from NEW settled lines
        runs = json.load(open(LOG))["runs"]
        if runs and runs[-1]["live_n"] == len(live):
            print(f"[lean-loop] no new settled lines ({len(live)}), nothing to learn"); return
    weeks = sorted({(r["yr"], r["wk"]) for r in live})
    fwd = []                                              # frozen out-of-sample predictions: (p_stack, p_model, p_market, y, week)
    for yr, wk in weeks[1:]:
        train = replay + [r for r in live if (r["yr"], r["wk"]) < (yr, wk)]
        w = fit(train)
        for r in live:
            if (r["yr"], r["wk"]) == (yr, wk): fwd.append((prob(w, r), r["p"], r["q"], r["y"], wk))
    summ = lambda sel, f: (lambda S: {"n": len(S), "hit": round(st.mean(((f(x) >= .5) == bool(x[3])) for x in S), 4)} if S else {"n": 0, "hit": None})(sel)
    res = {"overall": {"stack": summ(fwd, lambda x: x[0]), "model_alone": summ(fwd, lambda x: x[1]), "market_alone": summ(fwd, lambda x: x[2])}, "bands": [], "by_week": {}}
    for thr in BANDS:
        S = [x for x in fwd if max(x[0], 1 - x[0]) >= thr]
        if not S: res["bands"].append({"conf": thr, "n": 0, "verified": False}); continue
        hit = st.mean(((x[0] >= .5) == bool(x[3])) for x in S); pred = st.mean(max(x[0], 1 - x[0]) for x in S)
        res["bands"].append({"conf": thr, "n": len(S), "hit": round(hit, 4), "predicted": round(pred, 4), "overs": sum(1 for x in S if x[0] >= .5),
                             "verified": len(S) >= MIN_N and abs(hit - pred) <= CAL_TOL})
    for wk in sorted({x[4] for x in fwd}):
        res["by_week"][str(wk)] = summ([x for x in fwd if x[4] == wk], lambda x: x[0])
    w = fit(replay + live)
    out = {"generated": datetime.now(timezone.utc).isoformat(), "version": len(json.load(open(LOG))["runs"]) + 1 if os.path.exists(LOG) else 1,
           "method": "ridge logistic: const, logit(model), logit(market), proj gap; live rows x%g" % LIVE_W,
           "weights": [round(a, 4) for a in w], "trained_on": {"replay": len(replay), "live": len(live), "live_weeks": [f"{y}-{k}" for y, k in weeks]},
           "walk_forward": res, "note": "SHADOW. A band is quotable only when verified=true (forward hit rate within %.0f pts of predicted over %d+ plays)." % (CAL_TOL * 100, MIN_N)}
    json.dump(out, open(OUT, "w"), indent=1)
    log = json.load(open(LOG)) if os.path.exists(LOG) else {"runs": []}
    log["runs"].append({"t": out["generated"], "live_n": len(live), "weights": out["weights"], "overall": res["overall"], "bands": res["bands"]})
    json.dump(log, open(LOG, "w"), indent=1)
    o = res["overall"]
    print(f"[lean-loop] forward n={o['stack']['n']}: stack {o['stack']['hit']} | model alone {o['model_alone']['hit']} | market alone {o['market_alone']['hit']}")
    for b in res["bands"]:
        print(f"[lean-loop]   conf>={b['conf']}: n={b['n']} hit={b.get('hit')} predicted={b.get('predicted')} verified={b['verified']}")
    print(f"[lean-loop] weights {out['weights']} (trained on {len(replay)} replay + {len(live)} live)")


if __name__ == "__main__":
    main()
