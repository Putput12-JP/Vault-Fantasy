#!/usr/bin/env python3
# ============================================================================
# VAULT · DAMPENED DvP BACKTEST  (research gate, writes nothing to data/)
#
# The shipped opponent term (build_best_bets.mjs matchupAdjFor, fed by
# build-lineup-feed.mjs buildDvP) is
#     oppMult = clamp(PPR pts allowed to pos per game / league avg, .88, 1.15)
# from RAW current-season weeks once 2+ are complete (else last season shrunk
# by dvp_shrink.json λ), and it multiplies every prop market.
# docs/target-funnel-backtest.md found it worsens receiving projections on a
# holdout. This tests a dampened version on every market it touches:
#
#     est  = (n·cur + k·prior) / (n + k)        prior = 1 + a·(last season − 1)
#     mult = clamp(est ** w, .88, 1.15)
#
# Variants: none · prod (shipped, reproduced) · damp_cell (k,a,w fitted per
# market×pos) · damp_global (ONE k,a,w for everything, the shippable one).
# Fit on TRAIN seasons, scored on TEST; then a market check against 2026
# settled closing lines (bet_results.json). Pure stdlib.
#
# Usage: python3 scripts/backtest_dvp_damp.py [--train 2016-2021] [--test 2022-2025]
# ============================================================================
import argparse, json, math, os, re, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
ALLPOS = ["QB", "RB", "WR", "TE"]
REG_MAX_WK, MIN_PRIOR, LOOKBACK = 18, 3, 17
CLAMP = (0.88, 1.15)                       # same clamp as the shipped term
DAMP_POS = ["RB", "WR", "TE"]              # positions that get the damped term (QB keeps the shipped one)
TEAM_ALIAS = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV", "JAC": "JAX", "WSH": "WAS"}
STAT_KEYS = ("cmp", "att", "pyds", "ptds", "ints", "car", "ryds", "rtds", "tgt", "rec", "recyds", "rectds")

# market → (positions, kind). kind 'yards' = vol × eff, 'count' = direct.
MARKETS = {
    "pass_yd": ["QB"], "pass_att": ["QB"], "pass_cmp": ["QB"], "pass_td": ["QB"],
    "rush_yd": ["RB", "QB"], "rush_att": ["RB", "QB"],
    "rec": ["RB", "WR", "TE"], "rec_yd": ["RB", "WR", "TE"],
}
COMBOS = {"rush_rec_yd": ("rush_yd", "rec_yd"), "pass_rush_yd": ("pass_yd", "rush_yd")}
ACTUAL = {"pass_yd": "pyds", "pass_att": "att", "pass_cmp": "cmp", "pass_td": "ptds",
          "rush_yd": "ryds", "rush_att": "car", "rec": "rec", "rec_yd": "recyds"}

K_GRID = [0, 1, 2, 4, 8, 16, 32]
A_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
W_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]


def num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def tm(t):
    t = (t or "").upper()
    return TEAM_ALIAS.get(t, t)


def nkey(n):
    n = re.sub(r"[^a-z ]", "", (n or "").lower().replace(".", "").replace("'", ""))
    return re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n).replace(" ", "")


def _norm(w):
    """<=2022 seasons spell receiving `reyds`/`retds` and omit stat keys that are
    zero; 2023+ always write them. Normalize to the 2023+ shape."""
    w = dict(w)
    if "recyds" not in w and "reyds" in w:
        w["recyds"] = w["reyds"]
    if "rectds" not in w and "retds" in w:
        w["rectds"] = w["retds"]
    for k in STAT_KEYS:
        w.setdefault(k, 0)
    return w


_cache = {}
def load(season):
    if season in _cache:
        return _cache[season]
    p = os.path.join(DATA, f"nflverse_stats_{season}.json")
    players = []
    if os.path.exists(p):
        blob = json.load(open(p))
        players = list(blob.values()) if isinstance(blob, dict) else blob
        for pl in players:
            pl["weeks"] = [_norm(w) for w in (pl.get("weeks") or [])]
    _cache[season] = players
    return players


# ── DvP context ──────────────────────────────────────────────────────────────
def fpa_weeks(players):
    d = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # def → wk → pos → pts
    for pl in players:
        pos = pl.get("pos")
        if pos not in ALLPOS:
            continue
        for w in pl["weeks"]:
            wk, opp = num(w.get("wk")), tm(w.get("opp"))
            if wk and wk <= REG_MAX_WK and opp:
                d[opp][int(wk)][pos] += num(w.get("pts")) or 0
    return d


def ratios(dw, wk_lt):
    """{def: {pos: ratio-to-league}}, {def: games} over weeks < wk_lt."""
    per, games = {}, {}
    for t, weeks in dw.items():
        ws = [c for wk, c in weeks.items() if wk < wk_lt]
        if not ws:
            continue
        games[t] = len(ws)
        per[t] = {p: sum(c[p] for c in ws) / len(ws) for p in ALLPOS}
    out = {}
    for p in ALLPOS:
        xs = [per[t][p] for t in per]
        lg = statistics.fmean(xs) if xs else 0
        for t in per:
            if lg:
                out.setdefault(t, {})[p] = per[t][p] / lg
    return out, games


def build_ctx(seasons):
    """{(season, wk, def): {pos: (cur, n, prev, prod_mult)}}"""
    lam = {}
    try:
        lam = json.load(open(os.path.join(DATA, "dvp_shrink.json"))).get("lambda") or {}
    except Exception:
        pass
    ctx = {}
    for s in seasons:
        dw = fpa_weeks(load(s))
        prev, _ = ratios(fpa_weeks(load(s - 1)), 99)
        for wk in range(1, REG_MAX_WK + 1):
            cur, games = ratios(dw, wk)
            for t in set(dw) | set(prev):
                rec = {}
                for p in ALLPOS:
                    c, n, pv = cur.get(t, {}).get(p), games.get(t, 0), prev.get(t, {}).get(p)
                    if wk - 1 >= 2 and c is not None:
                        r = c
                    elif pv is not None:
                        L = lam.get(p, 0) or 0
                        r = (1 - L) * pv + L
                    else:
                        r = 1.0
                    rec[p] = (c, n, pv, min(CLAMP[1], max(CLAMP[0], r)))
                ctx[(s, wk, t)] = rec
    return ctx


def damp(cell, k, a, w):
    c, n, pv, _ = cell
    prior = 1.0 + a * ((pv if pv is not None else 1.0) - 1.0)
    est = prior if (c is None or n <= 0) else (n * c + k * prior) / (n + k)
    if est <= 0 or w == 0:
        return 1.0
    return min(CLAMP[1], max(CLAMP[0], est ** w))


# ── base projection (prop_model.json hyperparameters, prior games only) ─────
def wmean(vals, hl):
    n = len(vals)
    acc = sw = 0.0
    for i, v in enumerate(vals):
        wt = 0.5 ** (((n - 1) - i) / hl)
        acc += wt * v
        sw += wt
    return (acc / sw if sw else None), sw


def shrunk(vals, prior, hl, k):
    wm, sw = wmean(vals, hl)
    return prior if wm is None else (sw * wm + k * prior) / (sw + k)


def project(spec, prior_rows):
    vals = lambda key: [num(r.get(key)) for r in prior_rows if num(r.get(key)) is not None]
    hl, kv, ke, pr = spec["half_life"], spec["k_vol"], spec["k_eff"], spec["prior"]
    if spec["kind"] == "yards":
        vk, ek = spec["vol"], spec["eff_num"]
        mk = next(iter(pr)).split("|")[0]
        vol = vals(vk)
        eff = [num(r.get(ek)) / num(r.get(vk)) for r in prior_rows
               if num(r.get(vk)) and num(r.get(ek)) is not None]
        if len(vol) < MIN_PRIOR or len(eff) < MIN_PRIOR:
            return None
        return shrunk(vol, pr[mk + "|vol"], hl, kv) * shrunk(eff, pr[mk + "|eff"], hl, ke)
    s = vals(spec["stat"])
    if len(s) < MIN_PRIOR:
        return None
    return shrunk(s, next(iter(pr.values())), hl, kv)


def player_hist(seasons):
    hist = defaultdict(list)                 # (nkey, pos) → [(season, wk, row)]
    for s in sorted(set([min(seasons) - 1] + list(seasons))):
        for pl in load(s):
            if pl.get("pos") not in ALLPOS:
                continue
            for w in pl["weeks"]:
                wk = num(w.get("wk"))
                if wk and wk <= REG_MAX_WK:
                    hist[(nkey(pl.get("name")), pl.get("pos"))].append((s, int(wk), w))
    for v in hist.values():
        v.sort(key=lambda r: (r[0], r[1]))
    return hist


def base_points(seasons, model, hist):
    """[(season, wk, opp, pos, mkt, proj, actual)] walk-forward."""
    pts = []
    for (_, pos), rows in hist.items():
        for i, (s, wk, w) in enumerate(rows):
            if s not in seasons:
                continue
            prior = [r[2] for r in rows[max(0, i - LOOKBACK):i]]
            for mkt, poss in MARKETS.items():
                if pos not in poss:
                    continue
                proj = project(model[mkt], prior)
                act = num(w.get(ACTUAL[mkt]))
                if proj is not None and act is not None:
                    pts.append((s, wk, tm(w.get("opp")), pos, mkt, proj, act))
    return pts


# ── scoring ──────────────────────────────────────────────────────────────────
def mse(rows, f):
    return statistics.fmean([(a - p * f(c)) ** 2 for p, a, c in rows]) if rows else None


def grid():
    for k in K_GRID:
        for a in A_GRID:
            for w in W_GRID:
                if w == 0 and (k or a):
                    continue
                yield k, a, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2016-2021")
    ap.add_argument("--test", default="2022-2025")
    ap.add_argument("--write", action="store_true",
                    help="publish the global fit to data/dvp_damp.json (read by build-lineup-feed.mjs)")
    args = ap.parse_args()
    rng = lambda s: list(range(int(s.split("-")[0]), int(s.split("-")[1]) + 1))
    train, test = rng(args.train), rng(args.test)
    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]

    print("[dvp-damp] context + base projections …")
    ctx = build_ctx(train + test + [2026])
    hist = player_hist(train + test + [2026])
    pts = base_points(train + test, model, hist)
    cells = defaultdict(lambda: {"tr": [], "te": []})
    for s, wk, opp, pos, mkt, proj, act in pts:
        c = ctx.get((s, wk, opp))
        if c:
            cells[(mkt, pos)]["tr" if s in train else "te"].append((proj, act, c[pos]))
    print(f"[dvp-damp] {len(pts):,} market×player-games")

    # global fit over the positions that get the damped term: mean over cells of
    # MSE(variant)/MSE(none), so market scales don't mix
    fit_cells = {key: c for key, c in cells.items() if key[1] in DAMP_POS}
    base_tr = {key: mse(c["tr"], lambda _: 1.0) for key, c in fit_cells.items()}
    best_g = None
    for k, a, w in grid():
        obj = statistics.fmean([mse(c["tr"], lambda x: damp(x, k, a, w)) / base_tr[key] for key, c in fit_cells.items()])
        if best_g is None or obj < best_g[0]:
            best_g = (obj, k, a, w)
    G = best_g[1:]
    print(f"[dvp-damp] global fit (k, a, w) = {G}")

    fit_cell = {}
    for key, c in cells.items():
        fit_cell[key] = min(grid(), key=lambda g: mse(c["tr"], lambda x: damp(x, *g)))

    print(f"\nHoldout {args.test}: RMSE change vs no opponent term (+ = better)")
    print(f"{'mkt':9}{'pos':4}{'n':>7}  {'prod':>8}{'d_glob':>8}{'d_cell':>8}  cell(k,a,w)")
    agg = defaultdict(list)
    report = {"global": G, "cells": []}
    for key in sorted(cells, key=lambda k: (list(MARKETS).index(k[0]), k[1])):
        te = cells[key]["te"]
        b = math.sqrt(mse(te, lambda _: 1.0))
        r = {nm: 100 * (b - math.sqrt(mse(te, f))) / b for nm, f in [
            ("prod", lambda x: x[3]), ("d_glob", lambda x: damp(x, *G)),
            ("d_cell", lambda x, g=fit_cell[key]: damp(x, *g))]}
        for nm, v in r.items():
            agg[nm].append(v)
        print(f"{key[0]:9}{key[1]:4}{len(te):7,}  " + "".join(f"{r[n]:+7.2f}%" for n in ("prod", "d_glob", "d_cell")) + f"  {fit_cell[key]}")
        report["cells"].append({"mkt": key[0], "pos": key[1], "n_test": len(te), "lift_pct": r, "fit": fit_cell[key]})
    print(f"{'MEAN':13}{'':7}  " + "".join(f"{statistics.fmean(agg[n]):+7.2f}%" for n in ("prod", "d_glob", "d_cell")))
    print(f"{'cells better':20}" + "".join(f"{sum(v > 0 for v in agg[n]):>5}/{len(agg[n])}" for n in ("prod", "d_glob", "d_cell")))

    # ── market check: 2026 settled props vs closing line ─────────────────────
    B = json.load(open(os.path.join(DATA, "bet_results.json")))["props"]
    seen, rows = set(), []
    for r in B:
        mkt, pos = r.get("market"), r.get("pos")
        if pos not in ALLPOS or not (mkt in MARKETS or mkt in COMBOS):
            continue
        key = (nkey(r.get("name")), mkt, r.get("week"))
        if key in seen:
            continue
        seen.add(key)
        line, act, wk = num(r.get("line_close")) or num(r.get("line_open")), num(r.get("actual")), int(r["week"])
        if line is None or act is None or act == line:
            continue
        h = hist.get((nkey(r.get("name")), pos)) or []
        idx = next((i for i, (s, w, _) in enumerate(h) if s == 2026 and w == wk), None)
        if idx is None:
            continue
        prior = [x[2] for x in h[max(0, idx - LOOKBACK):idx]]
        c = ctx.get((2026, wk, tm(r.get("opp"))))
        if not c:
            continue
        parts = COMBOS.get(mkt, (mkt,))
        projs = [project(model[m], prior) if pos in MARKETS[m] else 0.0 for m in parts]
        if any(p is None for p in projs):
            continue
        rows.append({"mkt": mkt, "pos": pos, "line": line, "over": act > line, "parts": list(zip(parts, projs)), "c": c[pos]})
    print(f"\nMarket check: {len(rows):,} settled 2026 props (Wk 1-4) vs closing line")
    print("Base projection = prop-model core only (no role / env / script terms), so read the DIFFERENCES.")
    sides = {}
    for nm in ("none", "prod", "d_glob", "d_cell"):
        out = []
        for x in rows:
            if nm == "none":
                p = sum(v for _, v in x["parts"])
            elif nm == "prod":
                p = sum(v for _, v in x["parts"]) * x["c"][3]
            elif nm == "d_glob":
                p = sum(v for _, v in x["parts"]) * damp(x["c"], *G)
            else:
                p = sum(v * damp(x["c"], *fit_cell.get((m, x["pos"]), G)) for m, v in x["parts"])
            out.append(p > x["line"])
        sides[nm] = out
        hit = sum(o == x["over"] for o, x in zip(out, rows)) / len(rows)
        print(f"  {nm:7} model side wins {100 * hit:5.1f}%")
    for nm in ("prod", "d_glob", "d_cell"):
        fl = [(o, x) for o, n0, x in zip(sides[nm], sides["none"], rows) if o != n0]
        if fl:
            w = sum(o == x["over"] for o, x in fl)
            print(f"  {nm:7} flips the side on {len(fl):4} props; the flipped side wins {w}/{len(fl)} = {100 * w / len(fl):.1f}%")
    out = os.path.join(os.environ.get("OUT_DIR", "/tmp"), "dvp_damp_backtest.json")
    json.dump(report, open(out, "w"), indent=1)

    if args.write:
        # QB keeps the shipped (undamped) term: its direction beat 2026 closing
        # lines well beyond a shuffled null (backtest_dvp_damp_market.py), while
        # RB/WR/TE matched or trailed the null. See docs/dvp-damp-backtest.md.
        pos_cells = [c for c in report["cells"] if c["pos"] in DAMP_POS]
        pub = {
            "generated": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"),
            "k": G[0], "a": G[1], "w": G[2], "clamp": list(CLAMP), "positions": DAMP_POS,
            "fit": {"train": args.train, "test": args.test,
                    "holdout_rmse_lift_pct": {
                        "shipped": round(statistics.fmean(c["lift_pct"]["prod"] for c in pos_cells), 3),
                        "damped": round(statistics.fmean(c["lift_pct"]["d_glob"] for c in pos_cells), 3)},
                    "cells_better": sum(c["lift_pct"]["d_glob"] > 0 for c in pos_cells), "cells": len(pos_cells)},
            "doc": "docs/dvp-damp-backtest.md",
        }
        dst = os.path.join(DATA, "dvp_damp.json")
        json.dump(pub, open(dst, "w"), indent=1)
        print(f"[dvp-damp] wrote {dst}")
    print(f"\n[dvp-damp] wrote {out}")


if __name__ == "__main__":
    main()
