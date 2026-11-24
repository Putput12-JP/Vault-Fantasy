#!/usr/bin/env python3
"""Move grade search (docs/sharps-v2-movegrade-search.md): letters for the 10 candidate systems, the time split, and the statistics.

  --phase select   fit marks from the fit set's moves, then fit and validation outcomes for all 10 systems, the screen and the choice.
                   Never computes a sealed-set outcome.
  --phase sealed --system Sx   the one frozen system on the sealed set (run once), then the exploratory all-systems table.

Clarifications fixed before any outcome was read (results doc, "Deviations"): a letter above D needs s > 0 and the against marker needs s < 0,
so a side with no move is always D even where a mark is 0 (many NFL lines never move).
"""
import argparse, bisect, json, math, random, sys

SEED = 20261111
NBOOT = 2000
NPERM = 5000
SPORTS3 = ("nba", "nfl", "cfb")
SCORE = {"D": 0, "C": 1, "B": 2, "A": 3}
SYSTEMS = ["S%d" % i for i in range(1, 11)]
DESC = {"S1": "mg-1 as specified (fixed tables)", "S2": "Flag A magnitude", "S3": "Flag C magnitude", "S4": "larger of A and C, percentile-scaled",
        "S5": "agreement: mean of A and C percentiles", "S6": "US books agreeing (net share)", "S7": "S4, spreads and totals only",
        "S8": "S4, moneylines only", "S9": "S4 pooled over sports", "S10": "S2 pooled over sports"}


# ---------- data ----------

def load(pop, scores):
    rows = json.load(open(pop))["rows"]
    sc = json.load(open(scores))
    for r in rows:
        r["res"], r["roi"], r["win"] = None, None, None
        fin = (sc.get(r["sport"]) or {}).get(r["gid"])
        if fin is None or r["pin_line"] is None and r["g"] != "ml" or r["pin_px"] is None:
            continue
        aw, hm = fin
        if r["g"] == "total":
            v = (aw + hm - r["pin_line"]) * (1 if r["norm"] == "over" else -1)
        else:
            m = hm - aw if r["norm"] == "home" else aw - hm
            v = m if r["g"] == "ml" else m + r["pin_line"]
        px = r["pin_px"]
        dec = 1 + (px / 100 if px > 0 else 100 / -px)
        r["res"] = "win" if v > 0 else "loss" if v < 0 else "push"
        r["roi"] = dec - 1 if v > 0 else -1.0 if v < 0 else 0.0
        r["win"] = 1.0 if v > 0 else 0.0 if v < 0 else None
    return rows


def split(rows):
    """Per sport, games by cut time: fit first 60%, validation next 20%, sealed last 20%; ties at a boundary to the earlier set."""
    out = {}
    for sp in set(r["sport"] for r in rows):
        g = sorted({(r["cut"], r["gid"]) for r in rows if r["sport"] == sp})
        n = len(g)
        b1, b2 = round(0.6 * n), round(0.8 * n)
        while 0 < b1 < n and g[b1][0] == g[b1 - 1][0]:
            b1 += 1
        while 0 < b2 < n and g[b2][0] == g[b2 - 1][0]:
            b2 += 1
        for i, (_, gid) in enumerate(g):
            out[gid] = "fit" if i < b1 else "val" if i < b2 else "sealed"
    for r in rows:
        r["set"] = out[r["gid"]]
    return rows


# ---------- systems ----------

def q(vals, p):
    v = sorted(vals)
    return v[max(0, math.ceil(p * len(v)) - 1)] if v else None


def ecdf(vals):
    v = sorted(vals)
    return lambda x: bisect.bisect_right(v, x) / len(v) if v else None


def build_systems(rows):
    """Adds r['L'][sys] = 'A'|'B'|'C'|'D'|'against'|None. Every mark and CDF is from the fit set's home or over sides only."""
    fit_ho = [r for r in rows if r["set"] == "fit" and r["norm"] in ("home", "over")]
    marks = {}

    def cdfs(feat, pooled):
        key = (lambda r: r["g"]) if pooled else (lambda r: (r["sport"], r["g"]))
        d = {}
        for r in fit_ho:
            if r[feat] is not None:
                d.setdefault(key(r), []).append(abs(r[feat]))
        return {k: ecdf(v) for k, v in d.items()}, key

    def pct(feat, pooled):
        F, key = cdfs(feat, pooled)
        name = feat + ("_pp" if pooled else "_p")
        for r in rows:
            x, f = r[feat], F.get(key(r))
            r[name] = None if x is None or f is None else (0.0 if x == 0 else math.copysign(f(abs(x)), x))
        return name

    pa, pc, pa_pool, pc_pool = pct("a", False), pct("c", False), pct("a", True), pct("c", True)

    def larger(r, x, y):
        u, v = r[x], r[y]
        if u is None and v is None:
            return None
        if u is None:
            return v
        if v is None:
            return u
        return u if abs(u) >= abs(v) else v

    score = {
        "S2": lambda r: r["a"], "S3": lambda r: r["c"],
        "S4": lambda r: larger(r, pa, pc),
        "S5": lambda r: None if r[pa] is None or r[pc] is None else (r[pa] + r[pc]) / 2,
        "S6": lambda r: r["nb"],
        "S7": lambda r: larger(r, pa, pc) if r["g"] != "ml" else None,
        "S8": lambda r: larger(r, pa, pc) if r["g"] == "ml" else None,
        "S9": lambda r: larger(r, pa_pool, pc_pool),
        "S10": lambda r: r["a"],
    }
    pooled = {"S9", "S10"}
    for s, fn in score.items():
        key = (lambda r: r["g"]) if s in pooled else (lambda r: (r["sport"], r["g"]))
        d = {}
        for r in fit_ho:
            v = fn(r)
            if v is not None:
                d.setdefault(key(r), []).append(round(abs(v), 4))
        mk = {k: (q(v, 0.50), q(v, 0.80), q(v, 0.95)) for k, v in d.items()}
        marks[s] = {("|".join(k) if isinstance(k, tuple) else k): m for k, m in mk.items()}
        for r in rows:
            v, m = fn(r), mk.get(key(r))
            r.setdefault("L", {})
            if v is None or m is None:
                r["L"][s] = None
                continue
            v = round(v, 4)
            p50, p80, p95 = m
            if v > 0 and v >= p95:
                L = "A"
            elif v > 0 and v >= p80:
                L = "B"
            elif v > 0 and v >= p50:
                L = "C"
            elif v < 0 and v <= -p80:
                L = "against"
            else:
                L = "D"
            r["L"][s] = L
    for r in rows:
        r["L"]["S1"] = r["mg1"]
    return marks


# ---------- statistics ----------

def tval(r, t):
    return {"a": r["after"], "b": r["clv_us"], "c": r["roi"], "w": r["win"]}[t]


def strata_data(rows, sysid, t):
    """[(stratum, game, x, y)] over lettered sides with a target value."""
    out = []
    for r in rows:
        L = r["L"].get(sysid)
        y = tval(r, t)
        if L in SCORE and y is not None:
            out.append(((r["sport"], r["g"]), r["gid"], SCORE[L], y))
    return out


def fe_slope_from(acc):
    num = den = 0.0
    for n, sx, sy, sxy, sxx in acc.values():
        if n < 2:
            continue
        num += sxy - sx * sy / n
        den += sxx - sx * sx / n
    return num / den if den > 0 else None


def per_game(data):
    """{game: {stratum: [n, sx, sy, sxy, sxx]}}"""
    g = {}
    for st, gid, x, y in data:
        a = g.setdefault(gid, {}).setdefault(st, [0, 0.0, 0.0, 0.0, 0.0])
        a[0] += 1; a[1] += x; a[2] += y; a[3] += x * y; a[4] += x * x
    return g


def slope_ci(data, level=0.95, rng=None):
    if not data:
        return None
    pg = per_game(data)
    games = list(pg)
    sport_of = {gid: next(iter(pg[gid]))[0] for gid in games}
    def agg(gl):
        acc = {}
        for gid in gl:
            for st, v in pg[gid].items():
                a = acc.setdefault(st, [0, 0.0, 0.0, 0.0, 0.0])
                for i in range(5):
                    a[i] += v[i]
        return acc
    est = fe_slope_from(agg(games))
    if est is None:
        return None
    rng = rng or random.Random(SEED)
    by_sport = {}
    for gid in games:
        by_sport.setdefault(sport_of[gid], []).append(gid)
    bs = []
    for _ in range(NBOOT):
        gl = []
        for sp, lst in by_sport.items():
            gl += [lst[rng.randrange(len(lst))] for _ in lst]
        b = fe_slope_from(agg(gl))
        if b is not None:
            bs.append(b)
    bs.sort()
    lo_p, hi_p = (1 - level) / 2, 1 - (1 - level) / 2
    m = sum(bs) / len(bs)
    se = math.sqrt(sum((b - m) ** 2 for b in bs) / (len(bs) - 1))
    return {"slope": est, "lo": bs[int(lo_p * len(bs))], "hi": bs[min(len(bs) - 1, int(hi_p * len(bs)))], "se": se,
            "t": est / se if se > 0 else None, "n": len(data), "games": len(games)}


def perm_p(data, rng=None):
    """One-sided: letters shuffled within stratum among lettered sides; the pooled FE slope recomputed."""
    if not data:
        return None
    st = {}
    for s, gid, x, y in data:
        st.setdefault(s, ([], []))
        st[s][0].append(x); st[s][1].append(y)
    # FE slope = sum_s (sum xy - n xbar ybar) / den; den and the means do not change under a within-stratum shuffle
    den, const = 0.0, 0.0
    for xs, ys in st.values():
        n = len(xs)
        if n < 2:
            continue
        sx, sy = sum(xs), sum(ys)
        den += sum(x * x for x in xs) - sx * sx / n
        const += sx * sy / n
    if den <= 0:
        return None
    obs = (sum(sum(x * y for x, y in zip(xs, ys)) for xs, ys in st.values() if len(xs) >= 2) - const) / den
    rng = rng or random.Random(SEED)
    k = 0
    items = [(list(xs), ys) for xs, ys in st.values() if len(xs) >= 2]
    for _ in range(NPERM):
        tot = 0.0
        for xs, ys in items:
            rng.shuffle(xs)
            tot += sum(x * y for x, y in zip(xs, ys))
        if (tot - const) / den >= obs - 1e-12:
            k += 1
    return (k + 1) / (NPERM + 1)


def cell(rows, t):
    """n, mean, cluster-by-game se."""
    ys = [(r["gid"], tval(r, t)) for r in rows if tval(r, t) is not None]
    n = len(ys)
    if not n:
        return {"n": 0, "mean": None, "se": None}
    m = sum(y for _, y in ys) / n
    g = {}
    for gid, y in ys:
        g[gid] = g.get(gid, 0.0) + (y - m)
    G = len(g)
    se = math.sqrt(sum(v * v for v in g.values()) * (G / (G - 1))) / n if G > 1 else None
    return {"n": n, "mean": m, "se": se}


def holm(ps):
    """{key: p} -> {key: adjusted p}"""
    items = sorted((p, k) for k, p in ps.items() if p is not None)
    m, out, run = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def letter_table(rows, sysid, sports):
    out = {}
    for L in ("A", "B", "C", "D", "against", None):
        sub = [r for r in rows if r["sport"] in sports and r["L"].get(sysid) == L]
        out[str(L)] = {t: cell(sub, t) for t in ("a", "b", "c", "w")}
    return out


def evaluate(rows, sysid, set_name, sports_for_pass=SPORTS3, level=0.95, perm=True):
    sub = [r for r in rows if r["set"] == set_name]
    res = {"pooled": {}, "sport": {}, "letters": {}}
    for t in ("a", "c", "w", "b"):
        d = strata_data([r for r in sub if r["sport"] in sports_for_pass], sysid, t)
        ci = slope_ci(d, level)
        res["pooled"][t] = dict(ci or {}, p=perm_p(d) if perm and t in ("a", "c") else None)
        for sp in ("nba", "nfl", "cfb", "cbb"):
            if t in ("c", "w") and sp == "cbb":
                continue
            ds = strata_data([r for r in sub if r["sport"] == sp], sysid, t)
            res["sport"].setdefault(sp, {})[t] = slope_ci(ds, level)
    res["letters"]["pooled"] = letter_table(sub, sysid, sports_for_pass)
    for sp in ("nba", "nfl", "cfb", "cbb"):
        res["letters"][sp] = letter_table(sub, sysid, (sp,))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", default="scratch/mgs_pop.json")
    ap.add_argument("--scores", default="scratch/mgs_scores.json")
    ap.add_argument("--phase", choices=("select", "sealed"), required=True)
    ap.add_argument("--system")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = split(load(a.pop, a.scores))
    marks = build_systems(rows)
    sets = {s: {sp: len({r["gid"] for r in rows if r["set"] == s and r["sport"] == sp}) for sp in ("nba", "nfl", "cfb", "cbb")} for s in ("fit", "val", "sealed")}
    bounds = {s: {sp: [min((r["cut"] for r in rows if r["set"] == s and r["sport"] == sp), default=None),
                       max((r["cut"] for r in rows if r["set"] == s and r["sport"] == sp), default=None)] for sp in ("nba", "nfl", "cfb", "cbb")} for s in ("fit", "val", "sealed")}
    shares = {}
    for s in SYSTEMS:
        for st in ("fit", "val", "sealed"):
            c = {}
            for r in rows:
                if r["set"] == st:
                    c[str(r["L"][s])] = c.get(str(r["L"][s]), 0) + 1
            shares.setdefault(s, {})[st] = c
    doc = {"sets_games": sets, "set_bounds_cut": bounds, "marks": {s: {k: list(v) for k, v in m.items()} for s, m in marks.items()}, "shares": shares}
    if a.phase == "select":
        res = {}
        for s in SYSTEMS:
            print("select", s, file=sys.stderr)
            res[s] = {"fit": evaluate(rows, s, "fit"), "val": evaluate(rows, s, "val")}
        for st in ("fit", "val"):
            ps = {(s, t): res[s][st]["pooled"][t].get("p") for s in SYSTEMS for t in ("a", "c")}
            hp = holm(ps)
            for (s, t), v in hp.items():
                res[s][st]["pooled"][t]["p_holm"] = v
        screen = {s: (res[s]["fit"]["pooled"]["a"].get("t") or 0) + (res[s]["fit"]["pooled"]["c"].get("t") or 0) for s in SYSTEMS}
        V = {s: ((res[s]["val"]["pooled"]["a"].get("t") or 0) + (res[s]["val"]["pooled"]["c"].get("t") or 0)) / 2 for s in SYSTEMS}
        passing = [s for s in SYSTEMS if screen[s] > 0]
        pool = passing or SYSTEMS
        chosen = sorted(pool, key=lambda s: (-V[s], SYSTEMS.index(s)))[0]
        doc.update(results=res, screen=screen, V=V, screen_passing=passing, chosen=chosen)
        print("chosen", chosen, "V", V[chosen], "screen passing", passing, file=sys.stderr)
    else:
        s = a.system
        doc["system"] = s
        doc["sealed"] = evaluate(rows, s, "sealed", level=0.975)
        # alternative framing: moved against minus D on the sealed set (95%), chosen system and mg-1
        alt = {}
        for sid in sorted({s, "S1"}):
            sub = [r for r in rows if r["set"] == "sealed" and r["sport"] in SPORTS3]
            for t in ("a", "c", "w"):
                ag = cell([r for r in sub if r["L"][sid] == "against"], t)
                dd = cell([r for r in sub if r["L"][sid] == "D"], t)
                if ag["n"] and dd["n"] and ag["se"] and dd["se"]:
                    diff = ag["mean"] - dd["mean"]
                    se = math.sqrt(ag["se"] ** 2 + dd["se"] ** 2)
                    alt.setdefault(sid, {})[t] = {"against": ag, "D": dd, "diff": diff, "lo": diff - 1.96 * se, "hi": diff + 1.96 * se}
        doc["against_vs_D"] = alt
        # exploratory, after the frozen read: every system on the sealed set, Holm-adjusted
        ex = {}
        for sid in SYSTEMS:
            print("explore", sid, file=sys.stderr)
            ex[sid] = evaluate(rows, sid, "sealed")
        ps = {(sid, t): ex[sid]["pooled"][t].get("p") for sid in SYSTEMS for t in ("a", "c")}
        for (sid, t), v in holm(ps).items():
            ex[sid]["pooled"][t]["p_holm"] = v
        doc["exploratory_all_sealed"] = {sid: {"pooled": ex[sid]["pooled"], "sport": ex[sid]["sport"]} for sid in SYSTEMS}
    json.dump(doc, open(a.out, "w"), default=str)


if __name__ == "__main__":
    main()
