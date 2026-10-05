#!/usr/bin/env python3
# ============================================================================
# VAULT · TARGET-FUNNEL BACKTEST  (research gate, writes nothing to data/)
#
# Question: does an opponent "target funnel" (the share of targets a defense
# allows to RBs / WRs / TEs) improve the receiving prop projections (rec,
# rec_yd) beyond the DvP term that already ships?
#
# What ships today (build_best_bets.mjs matchupAdjFor + build-lineup-feed.mjs
# buildDvP): oppMult = clamp(PPR pts allowed to pos per game / league avg,
# .88, 1.15), from current-season weeks once 2+ are complete, else last season
# shrunk by data/dvp_shrink.json λ. It multiplies every market.
#
# Variants, all multiplying the same player-autoregressive base projection
# (prop_model.json hyperparameters, prior-games-only, so leakage-free):
#   none        base only
#   dvp_prod    the shipped DvP term, reproduced exactly
#   dvp_tuned   FPA ratio, empirical-Bayes blended + exponent fitted on TRAIN
#   fun_share   share of targets allowed to pos / league share   (fitted)
#   fun_vol     targets allowed to pos per game / league         (fitted)
#   dvp+share   dvp_tuned with a fun_share term fitted ON TOP (the real test)
#
# Defense stats only ever use weeks < the game's week (plus last season as a
# prior). Fit on TRAIN seasons, score on TEST seasons. Pure stdlib.
#
# Usage: python3 scripts/backtest_target_funnel.py [--train 2016-2021] [--test 2022-2025]
# ============================================================================
import argparse, json, math, os, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
POS = ["RB", "WR", "TE"]
MKTS = ["rec", "rec_yd", "tgt"]            # tgt = diagnostic (the thing a funnel should move)
MIN_PRIOR, LOOKBACK, REG_MAX_WK = 3, 17, 18
TEAM_ALIAS = {"LA": "LAR", "STL": "LAR", "SD": "LAC", "OAK": "LV", "JAC": "JAX", "WSH": "WAS"}

K_GRID = [0, 1, 2, 4, 8, 16]               # games of weight on last season's prior
A_GRID = [0.0, 0.25, 0.5, 0.75]            # how much of last season's deviation carries
W_GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
CLAMP = (0.85, 1.18)


def num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def tm(t):
    t = (t or "").upper()
    return TEAM_ALIAS.get(t, t)


def _norm(w):
    """Seasons <= 2022 spell receiving yards/TDs `reyds`/`retds` and omit the
    receiving keys entirely on a zero-target game; 2023+ always carry them as
    `recyds`/`rectds`. Normalize to the 2023+ shape (a played game with no
    target is a real 0)."""
    w = dict(w)
    if "recyds" not in w and "reyds" in w:
        w["recyds"] = w["reyds"]
    if "rectds" not in w and "retds" in w:
        w["rectds"] = w["retds"]
    for k in ("tgt", "rec", "recyds"):
        w.setdefault(k, 0)
    return w


def load(season):
    p = os.path.join(DATA, f"nflverse_stats_{season}.json")
    if not os.path.exists(p):
        return []
    blob = json.load(open(p))
    players = list(blob.values()) if isinstance(blob, dict) else blob
    for pl in players:
        pl["weeks"] = [_norm(w) for w in (pl.get("weeks") or [])]
    return players


# ── defense allowed tables ──────────────────────────────────────────────────
def defense_weeks(players):
    """{def: {wk: {pos: [tgt, pts]}}} for regular-season weeks."""
    d = defaultdict(lambda: defaultdict(lambda: {p: [0.0, 0.0] for p in ["QB"] + POS}))
    for pl in players:
        pos = pl.get("pos")
        if pos not in ("QB", "RB", "WR", "TE"):
            continue
        for w in pl.get("weeks") or []:
            wk = num(w.get("wk"))
            opp = tm(w.get("opp"))
            if not wk or wk > REG_MAX_WK or not opp:
                continue
            cell = d[opp][int(wk)][pos]
            cell[0] += num(w.get("tgt")) or 0
            cell[1] += num(w.get("pts")) or 0
    return d


def season_to_date(dw, wk_lt):
    """Per-defense aggregates over weeks < wk_lt: games, tgt[pos], pts[pos]."""
    out = {}
    for t, weeks in dw.items():
        g, tg, pt = 0, defaultdict(float), defaultdict(float)
        for wk, cells in weeks.items():
            if wk >= wk_lt:
                continue
            g += 1
            for p, (a, b) in cells.items():
                tg[p] += a
                pt[p] += b
        out[t] = (g, tg, pt)
    return out


def metrics(agg):
    """Raw per-defense ratios vs league for each family; returns {def:{fam:{pos:ratio}}}, games."""
    fams = {}
    games = {}
    vals = {"fpa": defaultdict(dict), "share": defaultdict(dict), "vol": defaultdict(dict)}
    for t, (g, tg, pt) in agg.items():
        if g <= 0:
            continue
        games[t] = g
        tot = sum(tg[p] for p in ["QB"] + POS) or 0
        for p in POS:
            vals["fpa"][t][p] = pt[p] / g
            vals["vol"][t][p] = tg[p] / g
            vals["share"][t][p] = (tg[p] / tot) if tot else None
    for fam, tab in vals.items():
        fams[fam] = {}
        for p in POS:
            xs = [tab[t][p] for t in tab if tab[t].get(p) is not None]
            if not xs:
                continue
            lg = statistics.fmean(xs)
            for t in tab:
                v = tab[t].get(p)
                if v is not None and lg:
                    fams[fam].setdefault(t, {})[p] = v / lg
    return fams, games


def build_def_context(seasons):
    """{(season, wk, def): {fam: {pos: (cur_ratio, n_games, prev_ratio)}, 'prod': {pos: mult}}}"""
    shrink = {}
    try:
        shrink = json.load(open(os.path.join(DATA, "dvp_shrink.json"))).get("lambda") or {}
    except Exception:
        pass
    dw_by = {s: defense_weeks(load(s)) for s in seasons}
    full_prev = {}
    for s in seasons:
        prev = dw_by.get(s - 1)
        if prev is None:
            prev = defense_weeks(load(s - 1))
        full_prev[s] = metrics(season_to_date(prev, 99))[0] if prev else {}
    ctx = {}
    for s in seasons:
        dw = dw_by[s]
        prevm = full_prev[s]
        for wk in range(1, REG_MAX_WK + 1):
            cur, games = metrics(season_to_date(dw, wk))
            for t in set(list(dw.keys())):
                rec = {}
                for fam in ("fpa", "share", "vol"):
                    rec[fam] = {}
                    for p in POS:
                        c = cur.get(fam, {}).get(t, {}).get(p)
                        pv = prevm.get(fam, {}).get(t, {}).get(p)
                        rec[fam][p] = (c, games.get(t, 0), pv)
                # shipped DvP, reproduced: 2+ completed weeks -> raw current; else
                # last season shrunk toward the mean by λ. ratio clamp .88/1.15.
                prod = {}
                for p in POS:
                    c, n, pv = rec["fpa"][p]
                    if wk - 1 >= 2 and c is not None:
                        r = c
                    elif pv is not None:
                        L = shrink.get(p, 0) or 0
                        r = (1 - L) * pv + L * 1.0
                    else:
                        r = 1.0
                    prod[p] = min(1.15, max(0.88, r))
                rec["prod"] = prod
                ctx[(s, wk, t)] = rec
    return ctx


# ── base projection (mirror build_prop_projections / prop-model.js) ──────────
def wmean(vals, hl):
    n = len(vals)
    acc = sw = 0.0
    for i, v in enumerate(vals):
        w = 0.5 ** (((n - 1) - i) / hl)
        acc += w * v
        sw += w
    return (acc / sw if sw else None), sw


def shrunk(vals, prior, hl, k):
    wm, sw = wmean(vals, hl)
    return prior if wm is None else (sw * wm + k * prior) / (sw + k)


def base_points(seasons, model):
    """Walk-forward base projections. One row per player-game:
    (season, wk, opp, pos, {mkt: (proj, actual)})"""
    m_rec, m_ry = model["rec"], model["rec_yd"]
    hist = defaultdict(list)       # (name,pos) -> [(season, wk, row)] across seasons
    for s in sorted(set([min(seasons) - 1] + list(seasons))):
        for pl in load(s):
            if pl.get("pos") not in POS:
                continue
            for w in pl.get("weeks") or []:
                wk = num(w.get("wk"))
                if wk and wk <= REG_MAX_WK:
                    hist[(pl.get("name"), pl.get("pos"))].append((s, int(wk), w))
    pts = []
    for (name, pos), rows in hist.items():
        rows.sort(key=lambda r: (r[0], r[1]))
        for i, (s, wk, w) in enumerate(rows):
            if s not in seasons:
                continue
            prior = rows[max(0, i - LOOKBACK):i]
            tg = [num(r[2].get("tgt")) for r in prior]
            tg = [v for v in tg if v is not None]
            if len(tg) < MIN_PRIOR:
                continue
            a_tgt, a_rec, a_ry = num(w.get("tgt")), num(w.get("rec")), num(w.get("recyds"))
            if a_tgt is None or a_rec is None or a_ry is None:
                continue
            rc = [num(r[2].get("rec")) for r in prior]
            rc = [v for v in rc if v is not None]
            eff = [num(r[2].get("recyds")) / num(r[2].get("tgt")) for r in prior
                   if num(r[2].get("tgt")) and num(r[2].get("recyds")) is not None]
            if len(eff) < MIN_PRIOR:
                continue
            p_rec = shrunk(rc, m_rec["prior"]["rec"], m_rec["half_life"], m_rec["k_vol"])
            p_vol = shrunk(tg, m_ry["prior"]["rec_yd|vol"], m_ry["half_life"], m_ry["k_vol"])
            p_eff = shrunk(eff, m_ry["prior"]["rec_yd|eff"], m_ry["half_life"], m_ry["k_eff"])
            pts.append((s, wk, tm(w.get("opp")), pos,
                        {"rec": (p_rec, a_rec), "rec_yd": (p_vol * p_eff, a_ry), "tgt": (p_vol, a_tgt)}))
    return pts


# ── variant multipliers ──────────────────────────────────────────────────────
def est_ratio(triple, k, a):
    c, n, pv = triple
    prior = 1.0 + a * ((pv if pv is not None else 1.0) - 1.0)
    if c is None or n <= 0:
        return prior
    return (n * c + k * prior) / (n + k) if (n + k) else prior


def mult(triple, k, a, w):
    r = est_ratio(triple, k, a)
    if r <= 0:
        return 1.0
    return min(CLAMP[1], max(CLAMP[0], r ** w))


def score(rows, f):
    """rows: [(proj, actual, ctxrec)] → (rmse, mae)"""
    se = ae = 0.0
    for proj, act, cr in rows:
        e = act - proj * f(cr)
        se += e * e
        ae += abs(e)
    n = len(rows) or 1
    return math.sqrt(se / n), ae / n


def fit(rows, fam, base_f=None):
    best = None
    for k in K_GRID:
        for a in A_GRID:
            for w in W_GRID:
                if w == 0.0 and (k or a):
                    continue       # w=0 is the same for every k/a; score it once
                if base_f:
                    f = lambda cr, k=k, a=a, w=w: base_f(cr) * mult(cr[fam], k, a, w)
                else:
                    f = lambda cr, k=k, a=a, w=w: mult(cr[fam], k, a, w)
                r, _ = score(rows, f)
                if best is None or r < best[0]:
                    best = (r, k, a, w)
    return best


def directional(rows, f, min_move=0.03):
    """Treat the base projection as the 'line'. When the adjustment moves the
    projection by >= min_move, how often is the actual on that side?"""
    hit = tot = 0
    for proj, act, cr in rows:
        m = f(cr)
        if abs(m - 1) < min_move or act == proj:
            continue
        tot += 1
        hit += (act > proj) == (m > 1)
    return (hit / tot if tot else None), tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2016-2021")
    ap.add_argument("--test", default="2022-2025")
    args = ap.parse_args()
    rng = lambda s: list(range(int(s.split("-")[0]), int(s.split("-")[1]) + 1))
    train, test = rng(args.train), rng(args.test)
    model = json.load(open(os.path.join(DATA, "prop_model.json")))["markets"]

    seasons = train + test
    print(f"[funnel] defense context {seasons[0]}..{seasons[-1]} …")
    ctx = build_def_context(seasons)
    print("[funnel] base projections …")
    pts = base_points(seasons, model)
    print(f"[funnel] {len(pts):,} player-games")

    def rows_for(seas, pos, mkt):
        out = []
        for s, wk, opp, p, d in pts:
            if s in seas and p == pos:
                cr = ctx.get((s, wk, opp))
                if cr is None:
                    continue
                proj, act = d[mkt]
                out.append((proj, act, {fam: cr[fam][pos] for fam in ("fpa", "share", "vol")} | {"prod": cr["prod"][pos]}))
        return out

    report = {"train": args.train, "test": args.test, "cells": []}
    print(f"\n{'mkt':7}{'pos':4}{'n_test':>8}  {'none':>8}{'dvp_prod':>10}{'dvp_tun':>10}{'fun_shr':>10}{'fun_vol':>10}{'dvp+shr':>10}   fitted (k,a,w)")
    for mkt in MKTS:
        for pos in POS:
            tr, te = rows_for(train, pos, mkt), rows_for(test, pos, mkt)
            f_none = lambda cr: 1.0
            f_prod = lambda cr: cr["prod"]
            b_dvp = fit(tr, "fpa")
            b_shr = fit(tr, "share")
            b_vol = fit(tr, "vol")
            f_dvp = lambda cr, b=b_dvp: mult(cr["fpa"], *b[1:])
            f_shr = lambda cr, b=b_shr: mult(cr["share"], *b[1:])
            f_vol = lambda cr, b=b_vol: mult(cr["vol"], *b[1:])
            b_both = fit(tr, "share", base_f=f_dvp)
            f_both = lambda cr, b=b_both: f_dvp(cr) * mult(cr["share"], *b[1:])
            res = {}
            for nm, f in [("none", f_none), ("dvp_prod", f_prod), ("dvp_tuned", f_dvp),
                          ("fun_share", f_shr), ("fun_vol", f_vol), ("dvp+share", f_both)]:
                rm, ma = score(te, f)
                hr, hn = directional(te, f)
                res[nm] = {"rmse": round(rm, 4), "mae": round(ma, 4), "dir_hit": hr and round(hr, 4), "dir_n": hn}
            base = res["none"]["rmse"]
            lift = lambda nm: 100 * (base - res[nm]["rmse"]) / base
            print(f"{mkt:7}{pos:4}{len(te):8,}  {base:8.3f}" + "".join(f"{lift(n):+9.2f}%" for n in ["dvp_prod", "dvp_tuned", "fun_share", "fun_vol", "dvp+share"])
                  + f"   dvp{b_dvp[1:]} shr{b_shr[1:]} vol{b_vol[1:]} +shr{b_both[1:]}")
            report["cells"].append({"mkt": mkt, "pos": pos, "n_train": len(tr), "n_test": len(te), "res": res,
                                    "fit": {"dvp": b_dvp[1:], "share": b_shr[1:], "vol": b_vol[1:], "share_on_dvp": b_both[1:]}})

    print("\nDirectional hit rate when the term moves the projection >=3% (base projection as the 'line'):")
    print(f"{'mkt':7}{'pos':4}" + "".join(f"{n:>17}" for n in ["dvp_prod", "dvp_tuned", "fun_share", "fun_vol", "dvp+share"]))
    for c in report["cells"]:
        line = f"{c['mkt']:7}{c['pos']:4}"
        for n in ["dvp_prod", "dvp_tuned", "fun_share", "fun_vol", "dvp+share"]:
            r = c["res"][n]
            line += f"{(f'{100*r['dir_hit']:.1f}% n={r['dir_n']:,}' if r['dir_hit'] else '-'):>17}"
        print(line)
    out = os.path.join(os.environ.get("OUT_DIR", "/tmp"), "target_funnel_backtest.json")
    json.dump(report, open(out, "w"), indent=1)
    print(f"\n[funnel] wrote {out}")


if __name__ == "__main__":
    main()
