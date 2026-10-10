#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · PROP MODEL AS A MARKET OFFSET — BACKTEST ON ESPN BET HISTORY
#
#  scripts/fit_prop_offset.py asks, on 5 weeks of Vault's own ledger, whether the
#  prop model adds anything on top of the market price. This asks it on ~15k real
#  ESPN BET two-way lines (2024-25, open AND close), using the cached crawl from
#  build_prop_market_prior.py and the same replay of the shipped model.
#
#      logit P(over) = logit(q) + c * ( logit(p_model) - logit(q) )
#
#  q = the line's vig-free (power) over probability, p_model = the shipped model's
#  calibrated P(over). c = 0 -> market, c = 1 -> model. Unlike the ledger there is
#  no side selection: every line enters once per snapshot, over/under symmetric.
#
#  Honest-ness:
#    * c is only ever scored on rows it was NOT fit on (season split both ways,
#      and an expanding walk-forward by week across 2024 -> 2025).
#    * LEAK WARNING: the shipped prop_model.json's calibration / shrink / priors
#      were fit on seasons through 2025, so p_model here is mildly optimistic.
#      The projection itself is walk-forward (prior games only). Treat the model
#      side as an upper bound; the CONSTRAINT it faces (beat a market) is real.
#    * One book (ESPN BET), not Pinnacle.
#
#  Also reports a betting sim (flat 1u at ESPN's own price on the side with the
#  best EV) for raw-model EV vs tilted EV, and whether the tilt predicts the
#  open -> close line move.
#
#  Usage: python3 scripts/backtest_prop_offset_espn.py [--json=path] [--min-n=150]
# ════════════════════════════════════════════════════════════════════════════
import json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_prop_market_prior as P
import build_prop_projections as B

ARG = dict((a.lstrip("-").split("=", 1) + [True])[:2] for a in sys.argv[1:])
MIN_N = int(ARG.get("min-n", 150))
EPS = 1e-4


def clamp(p): return min(1 - EPS, max(EPS, p))
def lg(p): p = clamp(p); return math.log(p / (1 - p))
def sig(x): return 1 / (1 + math.exp(-max(-40.0, min(40.0, x))))
def ll(y, p): p = clamp(p); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def imp(a): return 1 / dec(a)


def devig_power(o, u):
    po, pu = imp(o), imp(u)
    if po + pu <= 1: return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(60):
        k = (lo + hi) / 2
        if po ** k + pu ** k > 1: lo = k
        else: hi = k
    return po ** ((lo + hi) / 2)


def build_rows():
    games = list(P.csv.DictReader(P.io.StringIO(P.get_text(P.GAMES_URL))))
    gmap = {g["game_id"]: g for g in games}
    e2n = {r["espn_id"]: r["display_name"] for r in P.csv.DictReader(P.io.StringIO(P.get_text(P.PLAYERS_URL))) if r.get("espn_id")}
    model = json.load(open(os.path.join(P.DATA, "prop_model.json")))["markets"]
    W = P.load_weeks([min(P.SEASONS) - 1, *P.SEASONS])
    rows, skipped = [], defaultdict(int)
    for season in P.SEASONS:
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in P.load_lines(season, games, False):
            m = model.get(mkt)
            if not m: skipped["no model market"] += 1; continue
            name = e2n.get(ath); g = gmap.get(gid)
            if not name or not g: skipped["no id/game"] += 1; continue
            yr, wk = int(g["season"]), int(g["week"])
            pos, cur = W.get((P.nkey(name), yr), (None, []))
            if pos is None or pos not in m["pos"]: skipped["no log/position"] += 1; continue
            row = next((w for w in cur if B.num(w.get("wk")) == wk), None)
            if row is None: skipped["did not play"] += 1; continue
            prev = W.get((P.nkey(name), yr - 1), (None, []))[1]
            proj = P.project(m, mkt, prev + [w for w in cur if (B.num(w.get("wk")) or 0) < wk])
            act = P.actual_of(m, row)
            if proj is None or act is None: skipped["thin history"] += 1; continue
            snap = {}
            for when, line, o, u in (("open", lo, oo, uo), ("close", lc, oc, uc)):
                if line is None or o is None or u is None or abs(act - line) < 1e-9: continue
                snap[when] = {"when": when, "line": line, "o": o, "u": u, "q": devig_power(o, u), "p": P.p_over(m, proj, line), "y": 1.0 if act > line else 0.0}
            for s in snap.values():
                s.update(m=mkt, season=yr, wk=wk, t=(yr, wk), grp=P.posgroup(pos), game=gid, ath=ath)
                s["off"] = lg(s["q"]); s["d"] = lg(s["p"]) - lg(s["q"])
                s["move"] = (snap["close"]["q"] - snap["open"]["q"]) if len(snap) == 2 and snap["close"]["line"] == snap["open"]["line"] else None
                rows.append(s)
    print(f"[offset-espn] {len(rows)} line snapshots; skipped {dict(skipped)}")
    return rows


def fit_c(rows, ridge=1e-3):
    c = 0.0
    for _ in range(30):
        g = h = 0.0
        for r in rows:
            p = sig(r["off"] + c * r["d"])
            g += (r["y"] - p) * r["d"]; h += p * (1 - p) * r["d"] ** 2
        g -= ridge * c; h += ridge
        step = g / h if h > 0 else 0.0
        c += step
        if abs(step) < 1e-8: break
    info = sum(sig(r["off"] + c * r["d"]) * (1 - sig(r["off"] + c * r["d"])) * r["d"] ** 2 for r in rows) + ridge
    return c, (1 / math.sqrt(info) if info > 0 else float("nan"))


def score(test, cmap, default_c):
    """Log-loss of market / model / offset on `test`, with c looked up per market. Returns dict incl. paired z."""
    n = len(test)
    if not n: return None
    lm = lo = lt = 0.0; diffs = []
    for r in test:
        c = cmap.get(r["m"], default_c)
        pt = sig(r["off"] + c * r["d"]); a = ll(r["y"], r["q"])
        lm += a; lo += ll(r["y"], r["p"]); lt += ll(r["y"], pt); diffs.append(a - ll(r["y"], pt))
    mu = sum(diffs) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / max(n - 1, 1))
    return {"n": n, "market": lm / n, "model": lo / n, "offset": lt / n, "skill_vs_mkt": 1 - (lt / lm), "z": mu / (sd / math.sqrt(n)) if sd > 0 else None}


def fit_maps(train):
    pooled, _ = fit_c(train)
    by = defaultdict(list)
    for r in train: by[r["m"]].append(r)
    cm = {}
    for m, rs in by.items():
        if len(rs) >= MIN_N:
            c, se = fit_c(rs)
            # shrink the per-market c toward the pooled one by its own precision (se^2 vs a 0.15 prior sd)
            w = 0.15 ** 2 / (0.15 ** 2 + se ** 2)
            cm[m] = w * c + (1 - w) * pooled
    return pooled, cm


def line(tag, s):
    if not s: return
    z = "  -  " if s["z"] is None else f"{s['z']:+.2f}"
    print(f"  {tag:24} n={s['n']:6}  LL market {s['market']:.4f}  model {s['model']:.4f}  offset {s['offset']:.4f}   skill vs mkt {s['skill_vs_mkt'] * 100:+.2f}%  z={z}")


def bet_sim(test, cmap, pooled, thr):
    out = {}
    for name in ("model", "offset", "market"):
        n = w = 0; u = 0.0
        for r in test:
            if name == "model": p = r["p"]
            elif name == "offset": p = sig(r["off"] + cmap.get(r["m"], pooled) * r["d"])
            else: p = r["q"]
            eo, eu = p * dec(r["o"]) - 1, (1 - p) * dec(r["u"]) - 1
            side, ev, px = ("over", eo, r["o"]) if eo >= eu else ("under", eu, r["u"])
            if ev < thr: continue
            win = (r["y"] == 1.0) == (side == "over")
            n += 1; w += win; u += (dec(px) - 1) if win else -1.0
        out[name] = {"n": n, "hit": round(w / n, 4) if n else None, "roi": round(u / n, 4) if n else None}
    return out


def main():
    rows = build_rows()
    res = {}
    print("\n== c fit on all rows (descriptive) ==")
    pooled, se = fit_c(rows); print(f"  pooled c = {pooled:+.3f} (se {se:.3f})")
    by = defaultdict(list)
    for r in rows: by[r["m"]].append(r)
    res["c_all"] = {"pooled": round(pooled, 4)}
    for m in sorted(by, key=lambda k: -len(by[k])):
        c, s = fit_c(by[m]); res["c_all"][m] = round(c, 4)
        print(f"  {m:9} n={len(by[m]):6}  c={c:+.3f} (se {s:.3f})")

    print("\n== out-of-sample: fit on one season, score the other (per-market c, shrunk to pooled) ==")
    for fit_s, test_s in ((2024, 2025), (2025, 2024)):
        for when in ("open", "close"):
            tr = [r for r in rows if r["season"] == fit_s and r["when"] == when]
            te = [r for r in rows if r["season"] == test_s and r["when"] == when]
            pc, cm = fit_maps(tr)
            line(f"fit {fit_s} -> {test_s} {when}", score(te, cm, pc))
            res[f"{fit_s}->{test_s}|{when}"] = score(te, cm, pc)

    print("\n== expanding walk-forward by week (2024 wk1 -> 2025 wk18), c refit each week ==")
    for when in ("open", "close"):
        rs = sorted([r for r in rows if r["when"] == when], key=lambda r: r["t"])
        weeks = sorted({r["t"] for r in rs}); test = []; cmaps = {}
        for t in weeks:
            tr = [r for r in rs if r["t"] < t]
            if len(tr) < 1500: continue
            cmaps[t] = fit_maps(tr)
            test += [r for r in rs if r["t"] == t]
        # score with the c that was available at each row's week
        lm = lo = lt = 0.0; diffs = []
        for r in test:
            pc, cm = cmaps[r["t"]]; pt = sig(r["off"] + cm.get(r["m"], pc) * r["d"]); a = ll(r["y"], r["q"])
            lm += a; lo += ll(r["y"], r["p"]); lt += ll(r["y"], pt); diffs.append(a - ll(r["y"], pt))
        n = len(test); mu = sum(diffs) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (n - 1))
        s = {"n": n, "market": lm / n, "model": lo / n, "offset": lt / n, "skill_vs_mkt": 1 - lt / lm, "z": mu / (sd / math.sqrt(n))}
        line(f"walk-forward {when}", s); res[f"walkforward|{when}"] = s

    print("\n== per market, out-of-sample (2024->2025 and 2025->2024 pooled), OPEN lines ==")
    per = {}
    for m in sorted(by, key=lambda k: -len(by[k])):
        parts = []
        for fit_s, test_s in ((2024, 2025), (2025, 2024)):
            tr = [r for r in rows if r["season"] == fit_s and r["when"] == "open"]
            te = [r for r in rows if r["season"] == test_s and r["when"] == "open" and r["m"] == m]
            pc, cm = fit_maps(tr); parts.append((te, cm, pc))
        te_all = [];
        lm = lt = lo = 0.0; diffs = []
        for te, cm, pc in parts:
            for r in te:
                pt = sig(r["off"] + cm.get(r["m"], pc) * r["d"]); a = ll(r["y"], r["q"])
                lm += a; lo += ll(r["y"], r["p"]); lt += ll(r["y"], pt); diffs.append(a - ll(r["y"], pt))
        n = len(diffs)
        if n < MIN_N: continue
        mu = sum(diffs) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in diffs) / (n - 1))
        per[m] = {"n": n, "market": lm / n, "model": lo / n, "offset": lt / n, "skill_vs_mkt": 1 - lt / lm, "z": mu / (sd / math.sqrt(n))}
        line(m, per[m])
    res["per_market_oos_open"] = per

    print("\n== betting sim on OPEN lines, out-of-sample (fit other season), flat 1u at ESPN's own price ==")
    for thr in (0.0, 0.02, 0.05, 0.10):
        agg = {k: [0, 0, 0.0] for k in ("model", "offset", "market")}
        for fit_s, test_s in ((2024, 2025), (2025, 2024)):
            tr = [r for r in rows if r["season"] == fit_s and r["when"] == "open"]
            te = [r for r in rows if r["season"] == test_s and r["when"] == "open"]
            pc, cm = fit_maps(tr)
            for k, v in bet_sim(te, cm, pc, thr).items():
                if v["n"]: agg[k][0] += v["n"]; agg[k][1] += v["hit"] * v["n"]; agg[k][2] += v["roi"] * v["n"]
        print(f"  EV >= {thr * 100:>4.0f}%   " + "   ".join(f"{k:7} n={a[0]:5} hit {a[1] / a[0] if a[0] else 0:.3f} ROI {a[2] / a[0] if a[0] else 0:+.3f}" for k, a in agg.items()))
        res[f"sim_ev{int(thr * 100)}"] = {k: {"n": a[0], "roi": round(a[2] / a[0], 4) if a[0] else None} for k, a in agg.items()}

    print("\n== does the tilt predict the open -> close move? (same-line moves only, OPEN snapshot) ==")
    mv = [r for r in rows if r["when"] == "open" and r.get("move") is not None and abs(r["move"]) > 0.004]
    pooled_c = pooled
    ok_t = ok_m = 0
    for r in mv:
        pt = sig(r["off"] + pooled_c * r["d"])
        ok_t += (pt - r["q"]) * r["move"] > 0; ok_m += (r["p"] - r["q"]) * r["move"] > 0
    print(f"  moved lines n={len(mv)}   tilt direction matches the move {ok_t / len(mv):.3f}   raw-model direction matches {ok_m / len(mv):.3f}   (0.5 = no information)")
    res["move_dir"] = {"n": len(mv), "tilt": round(ok_t / len(mv), 4), "model": round(ok_m / len(mv), 4)}

    print("\n== CLV of leaning with the model at the OPEN: mean change in the leaned side's no-vig prob, open -> close ==")
    print("   (all same-line snapshots, moved or not; positive = the market came to the model's side)")
    same = [r for r in rows if r["when"] == "open" and r.get("move") is not None]
    def clv_of(r): return r["move"] * (1 if r["d"] > 0 else -1)
    def summ(xs):
        v = [clv_of(r) for r in xs]; n = len(v)
        if n < 30: return None
        mu = sum(v) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1))
        return {"n": n, "mean_clv_prob": round(mu, 5), "t": round(mu / (sd / math.sqrt(n)), 2), "beat": round(sum(x > 0 for x in v) / n, 3), "lost": round(sum(x < 0 for x in v) / n, 3)}
    clv = {}
    for lo_, hi_ in ((0, 0.10), (0.10, 0.25), (0.25, 0.5), (0.5, 9)):
        xs = [r for r in same if lo_ <= abs(r["d"]) < hi_]
        o = summ(xs); clv[f"|d| {lo_}-{hi_}"] = o
        if o: print(f"  |d| in [{lo_:.2f},{hi_:.2f})  n={o['n']:5}  mean CLV {o['mean_clv_prob'] * 100:+.2f} pts (t={o['t']:+.1f})  beat {o['beat']:.3f}  lost {o['lost']:.3f}")
    for m in sorted({r["m"] for r in same}):
        o = summ([r for r in same if r["m"] == m and abs(r["d"]) >= 0.25]); clv[m] = o
        if o: print(f"  {m:9} (|d| >= 0.25)  n={o['n']:5}  mean CLV {o['mean_clv_prob'] * 100:+.2f} pts (t={o['t']:+.1f})  beat {o['beat']:.3f}")
    for se in (2024, 2025):
        o = summ([r for r in same if r["season"] == se and abs(r["d"]) >= 0.25]); clv[f"season {se}"] = o
        if o: print(f"  season {se} (|d| >= 0.25)  n={o['n']:5}  mean CLV {o['mean_clv_prob'] * 100:+.2f} pts (t={o['t']:+.1f})")
    res["clv_by_disagreement"] = clv
    if ARG.get("json"): json.dump(res, open(ARG["json"], "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
