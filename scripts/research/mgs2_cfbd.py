#!/usr/bin/env python3
"""Move grade search 2 (docs/sharps-v2-movegrade-search-2.md): DraftKings CFB open-to-close move letters vs the result at the closing number.

  --phase select                  fit (2023) marks from moves only, fit and validation (2024) outcomes, the choice
  --phase sealed --system Mx      2025, read once, then the exploratory all-systems table

Input: data/cfbd/lines_<year>.json from origin/cfbd-lines-probe 6825116ec526 (extracted with git show into --dir). No price is stored: no ROI.
"""
import argparse, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mgs_analyze as MA  # noqa: E402  (slope_ci, perm_p, holm; same seed, resample and shuffle counts)

BOOK = "DraftKings"
YEARS = {"fit": 2023, "val": 2024, "sealed": 2025}
SYSTEMS = ("M1", "M2", "M3")
SCORE = MA.SCORE


def sides(dirn, year):
    rows, seen = [], set()
    for r in json.load(open(os.path.join(dirn, "lines_%d.json" % year))):
        if r.get("p") != BOOK or (r["id"], r["p"]) in seen:
            continue
        seen.add((r["id"], r["p"]))
        fin = r.get("hs") is not None and r.get("as_") is not None
        if r.get("sp") is not None and r.get("so") is not None:
            for norm, sgn in (("home", 1), ("away", -1)):
                s = sgn * (r["so"] - r["sp"])
                v = sgn * ((r["hs"] - r["as_"]) + r["sp"]) if fin else None
                vo = sgn * ((r["hs"] - r["as_"]) + r["so"]) if fin else None
                rows.append(dict(gid="%d:%s" % (year, r["id"]), wk=r["wk"], g="spread", norm=norm, s=s, v=v, vo=vo))
        if r.get("ou") is not None and r.get("ouo") is not None:
            for norm, sgn in (("over", 1), ("under", -1)):
                s = sgn * (r["ou"] - r["ouo"])
                v = sgn * (r["hs"] + r["as_"] - r["ou"]) if fin else None
                vo = sgn * (r["hs"] + r["as_"] - r["ouo"]) if fin else None
                rows.append(dict(gid="%d:%s" % (year, r["id"]), wk=r["wk"], g="total", norm=norm, s=s, v=v, vo=vo))
    for x in rows:
        x["win"] = None if x["v"] is None or x["v"] == 0 else (1.0 if x["v"] > 0 else 0.0)
        x["cover"] = None if x["v"] is None else (1.0 if x["v"] > 0 else 0.0)
        x["win_open"] = None if x["vo"] is None or x["vo"] == 0 else (1.0 if x["vo"] > 0 else 0.0)
    return rows


def letters(rows, marks):
    for x in rows:
        m = marks.get(x["g"])
        s = round(x["s"], 4)
        p50, p80, p95 = m
        x["L"] = ("A" if s > 0 and s >= p95 else "B" if s > 0 and s >= p80 else "C" if s > 0 and s >= p50
                  else "against" if s < 0 and s <= -p80 else "D")


def in_sys(x, sid):
    if sid == "M1":
        return x["g"] == "spread"
    if sid == "M2":
        return True
    return x["g"] == "spread" and x["wk"] >= 4


def data(rows, sid, t):
    return [(("cfb", x["g"]), x["gid"], SCORE[x["L"]], x[t]) for x in rows if in_sys(x, sid) and x["L"] in SCORE and x[t] is not None]


def cell(rows, t):
    ys = [(x["gid"], x[t]) for x in rows if x[t] is not None]
    n = len(ys)
    if not n:
        return {"n": 0, "mean": None, "se": None}
    m = sum(y for _, y in ys) / n
    g = {}
    for gid, y in ys:
        g[gid] = g.get(gid, 0.0) + (y - m)
    G = len(g)
    return {"n": n, "mean": m, "se": math.sqrt(sum(v * v for v in g.values()) * G / (G - 1)) / n if G > 1 else None}


def evaluate(rows, sid, perm=True):
    out = {"win": dict(MA.slope_ci(data(rows, sid, "win")) or {}, p=MA.perm_p(data(rows, sid, "win")) if perm else None),
           "cover": MA.slope_ci(data(rows, sid, "cover")), "win_open": MA.slope_ci(data(rows, sid, "win_open")), "letters": {}}
    for L in ("A", "B", "C", "D", "against"):
        sub = [x for x in rows if in_sys(x, sid) and x["L"] == L]
        out["letters"][L] = {t: cell(sub, t) for t in ("win", "cover", "win_open")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="scratch/cfbd")
    ap.add_argument("--phase", choices=("select", "sealed"), required=True)
    ap.add_argument("--system")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    S = {k: sides(a.dir, y) for k, y in YEARS.items()}
    fit_ho = [x for x in S["fit"] if x["norm"] in ("home", "over")]
    marks = {g: (MA.q([round(abs(x["s"]), 4) for x in fit_ho if x["g"] == g], 0.50), MA.q([round(abs(x["s"]), 4) for x in fit_ho if x["g"] == g], 0.80),
                 MA.q([round(abs(x["s"]), 4) for x in fit_ho if x["g"] == g], 0.95)) for g in ("spread", "total")}
    for k in S:
        letters(S[k], marks)
    counts = {k: {g: len({x["gid"] for x in S[k] if x["g"] == g}) for g in ("spread", "total")} for k in S}
    shares = {k: {sid: {L: sum(1 for x in S[k] if in_sys(x, sid) and x["L"] == L) for L in ("A", "B", "C", "D", "against")} for sid in SYSTEMS} for k in S}
    doc = {"marks": marks, "games": counts, "shares": shares}
    if a.phase == "select":
        res = {sid: {"fit": evaluate(S["fit"], sid), "val": evaluate(S["val"], sid)} for sid in SYSTEMS}
        for st in ("fit", "val"):
            for sid, p in MA.holm({sid: res[sid][st]["win"].get("p") for sid in SYSTEMS}).items():
                res[sid][st]["win"]["p_holm"] = p
        screen = [sid for sid in SYSTEMS if (res[sid]["fit"]["win"].get("t") or 0) > 0]
        pool = screen or list(SYSTEMS)
        chosen = sorted(pool, key=lambda s: (-(res[s]["val"]["win"].get("t") or -99), SYSTEMS.index(s)))[0]
        doc.update(results=res, screen_passing=screen, chosen=chosen)
    else:
        sid = a.system
        sealed = S["sealed"]
        doc["system"] = sid
        doc["sealed"] = evaluate(sealed, sid)
        doc["halves"] = {h: MA.slope_ci(data([x for x in sealed if (x["wk"] <= 7) == (h == "wk1_7")], sid, "win")) for h in ("wk1_7", "wk8_15")}
        ag = cell([x for x in sealed if in_sys(x, sid) and x["L"] == "against"], "win")
        dd = cell([x for x in sealed if in_sys(x, sid) and x["L"] == "D"], "win")
        if ag["n"] and dd["n"]:
            diff, se = ag["mean"] - dd["mean"], math.sqrt(ag["se"] ** 2 + dd["se"] ** 2)
            doc["against_vs_D"] = {"against": ag, "D": dd, "diff": diff, "lo": diff - 1.96 * se, "hi": diff + 1.96 * se}
        ex = {s: evaluate(sealed, s) for s in SYSTEMS}
        for s, p in MA.holm({s: ex[s]["win"].get("p") for s in SYSTEMS}).items():
            ex[s]["win"]["p_holm"] = p
        doc["exploratory_all_sealed"] = {s: ex[s]["win"] for s in SYSTEMS}
    json.dump(doc, open(a.out, "w"), default=str)


if __name__ == "__main__":
    main()
