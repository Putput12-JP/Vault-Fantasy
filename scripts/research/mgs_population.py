#!/usr/bin/env python3
"""Move grade search (docs/sharps-v2-movegrade-search.md): the tape population, one row per side, features at the cut and targets after it.

Point in time: every feature reads only tape rows with t <= cut (cut = start - 15 min) through the v2f-2 functions of flags_v2.py, unchanged.
Targets: (a) Pinnacle no-vig move cut -> close at the same line; (b) Pinnacle close fair minus the best US-book implied price at the cut (overlaps
the inputs, report only); (c) needs scores, joined by mgs_results.py. Every value is a stored price or line, or arithmetic on them.

  python3 -I scripts/research/mgs_population.py --tape data/book_tape --out scratch/mgs_pop.json
"""
import argparse, glob, json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from sharps_v2 import flags_v2 as F  # noqa: E402
import sf_signals as SIG  # noqa: E402

CUT_BEFORE = 900
BOOKS = set(F.FLAGS_BOOKS)
NFL_ALIAS = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX", "LVR": "LV", "OAK": "LV"}
GAP = 12 * 3600
MARKETS = ("ml", "spread", "total")
SIDES = {"ml": ("home", "away"), "spread": ("home", "away"), "total": ("over", "under")}

# mg-1 cutoff tables, copied from docs/sharps-v2-movegrade-spec.md 2.3 (branch sharps-v2-movegrade 6275de62a5e), fixed, not fitted here
MG_M_A = {"nba": {"ml": 2.0, "spread": 0.5, "total": 1.0}, "nfl": {"ml": 0.5, "spread": 1.0, "total": 0.5},
          "cbb": {"ml": 1.0, "spread": 1.0, "total": 0.5}, "cfb": {"ml": 1.0, "spread": 0.5, "total": 0.5}}
MG_X_A = {"nba": {"ml": 9.0, "spread": 2.0, "total": 2.5}, "nfl": {"ml": 3.0, "spread": 2.5, "total": 2.5},
          "cbb": {"ml": 4.5, "spread": 2.5, "total": 2.5}, "cfb": {"ml": 4.5, "spread": 2.5, "total": 2.0}}
MG_M_C = {"nba": {"spread": 1.0, "total": 1.5}, "nfl": {"spread": 0.5, "total": 0.5}, "cbb": {"spread": 0.5, "total": 1.0}, "cfb": {"spread": 0.5, "total": 0.5}}
MG_X_C = {"nba": {"spread": 3.5, "total": 4.0}, "nfl": {"spread": 1.5, "total": 1.5}, "cbb": {"spread": 2.0, "total": 4.0}, "cfb": {"spread": 2.5, "total": 2.0}}


def load(tape, sport):
    """{game id: {"rows": [...], "away", "home", "start"}}: sd sports by gk, the NFL by the two teams and a start within 12 h."""
    games = {}
    raw = []
    for fn in sorted(glob.glob(os.path.join(tape, sport, "[0-9][0-9][0-9][0-9]-[0-9][0-9].jsonl"))):
        with open(fn) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("bf") or r.get("t") is None or r.get("book") not in BOOKS:
                    continue
                raw.append(r)
    raw.sort(key=lambda r: r["t"])
    for r in raw:
        if r.get("gk"):
            k = r["gk"]
        else:
            a, h = NFL_ALIAS.get(r.get("away"), r.get("away")), NFL_ALIAS.get(r.get("home"), r.get("home"))
            if not a or not h or r.get("start") is None:
                continue
            k = None
            for kk, g in games.items():
                if g["away"] == a and g["home"] == h and abs(g["start"] - r["start"]) <= GAP:
                    k = kk
                    break
            if k is None:
                k = "nfl:%s@%s:%d" % (a, h, r["start"])
        g = games.setdefault(k, {"rows": [], "away": None, "home": None, "start": None})
        c = {x: r[x] for x in ("t", "book", "ml", "sp", "tot", "lim") if x in r}
        g["rows"].append(c)
        g["away"] = NFL_ALIAS.get(r.get("away"), r.get("away")) if not r.get("gk") else r.get("away")
        g["home"] = NFL_ALIAS.get(r.get("home"), r.get("home")) if not r.get("gk") else r.get("home")
        if r.get("start") is not None:
            g["start"] = r["start"]            # the newest row's start (rows sorted by time)
    return games


def pin_at(rows, g, norm, asof):
    """Pinnacle's last clean readable row for the side at or before asof (v2f-2 _pin_clean), or None."""
    clean, _ = F._pin_clean(F._by_book(rows, asof), g, norm)
    rs = [r for r in clean if r["fair"] is not None]
    return rs[-1] if rs else None


def after_move(rows, g, norm, cut, start):
    """(a): (fair at close - fair at cut) x 100 at the same line; ('line_changed', None) when the close is at another line."""
    at, cl = pin_at(rows, g, norm, cut), pin_at(rows, g, norm, start)
    if at is None or cl is None:
        return None, "no_pin"
    if g != "ml" and not (F._n(at["line"]) and F._n(cl["line"]) and abs(at["line"] - cl["line"]) <= F.LINE_EPS):
        return None, "line_changed"
    return round((cl["fair"] - at["fair"]) * 100, 4), None


def best_us(rows, g, norm, cut, line):
    """The best (lowest implied probability) stored US-book price for the side at the cut at `line` (moneyline: any). -> (price, book) or None."""
    by = F._by_book(rows, cut)
    best = None
    for b in F.FLAGS_US:
        rd = F._reads(by.get(b), g, norm)
        if not rd:
            continue
        r = rd[-1]
        if not F._n(r.get("px")):
            continue
        if g != "ml" and not (F._n(r["line"]) and F._n(line) and abs(r["line"] - line) <= F.LINE_EPS):
            continue
        p = SIG.american_prob(r["px"])
        if p is not None and (best is None or p < best[0]):
            best = (p, r["px"], b)
    return best


def features(rows, g, norm, cut, sport):
    pin, w_pin = F.flag_pin(rows, g, norm, cut, sport, None)
    line, w_line = F.flag_line(rows, g, norm, cut, sport, None)
    a = pin["pts"] if pin else None
    c = None
    nb = None
    if line:
        mv, _ = F._book_moves(rows, g, norm, cut)
        us = [b for b in F.FLAGS_US if b in mv]
        if g == "ml":
            mvs = [(mv[b]["to"]["fair"] - mv[b]["fr"]["fair"]) * 100 for b in us]
            c = round(statistics.median(mvs), 4) if mvs else None
            thr = F.FLAGS_T_A[sport]["ml"]
        else:
            s = F._dir_sign(g, norm)
            c = round(s * (line["pin"]["to"] - line["pin"]["from"]), 4)
            mvs = [s * (mv[b]["to"]["line"] - mv[b]["fr"]["line"]) for b in us]
            thr = F.FLAGS_C_BOOK_MOVE
        if len(mvs) >= 2:
            up = sum(1 for x in mvs if round(x, 2) >= thr)
            dn = sum(1 for x in mvs if round(x, 2) <= -thr)
            nb = round((up - dn) / len(mvs), 4)
    return {"a": a, "a_state": pin["state"] if pin else None, "c": c, "c_state": line["state"] if line else None,
            "c_pts": (round(F._dir_sign(g, norm) * (line["pin"]["to"] - line["pin"]["from"]), 2) if line and g != "ml" else None),
            "nb": nb, "why_a": w_pin, "why_c": w_line}


def mg1(fe, g, sport):
    """mg-1 per docs/sharps-v2-movegrade-spec.md 1.3. -> 'A'|'B'|'C'|'D'|'against'|None."""
    a, c = fe["a_state"], fe["c_state"]
    if a is None and c is None:
        return None
    pts, c_pts = fe["a"], fe["c_pts"]
    if a == "away" or c == "away":
        return "against"
    if a == "toward" or c == "toward":
        if a == "toward" and pts >= MG_X_A[sport][g]:
            return "A"
        if c == "toward" and c_pts is not None and c_pts >= MG_X_C[sport][g]:
            return "A"
        return "B"
    m_c = (MG_M_C.get(sport) or {}).get(g)
    dt = (pts is not None and pts >= MG_M_A[sport][g]) or (c_pts is not None and m_c is not None and c_pts >= m_c)
    da = (pts is not None and pts <= -MG_M_A[sport][g]) or (c_pts is not None and m_c is not None and c_pts <= -m_c)
    return "C" if dt and not da else "D"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape", default="data/book_tape")
    ap.add_argument("--out", required=True)
    ap.add_argument("--now", type=int)
    a = ap.parse_args(argv)
    out = []
    newest = 0
    for sport in ("nba", "nfl", "cfb", "cbb"):
        games = load(a.tape, sport)
        for gid, gm in games.items():
            newest = max(newest, max(r["t"] for r in gm["rows"]))
        for gid, gm in games.items():
            if gm["start"] is None:
                continue
            gm["gid"] = gid
        now = a.now or newest
        for gid, gm in sorted(games.items(), key=lambda kv: kv[1]["start"] or 0):
            st = gm["start"]
            if st is None or st > now:
                continue
            cut = st - CUT_BEFORE
            rows = gm["rows"]
            if not any(r["book"] == "Pinnacle" and r["t"] <= cut for r in rows):
                continue
            for g in MARKETS:
                for norm in SIDES[g]:
                    fe = features(rows, g, norm, cut, sport)
                    at = pin_at(rows, g, norm, cut)
                    after, why_after = after_move(rows, g, norm, cut, st)
                    clv = None
                    if at is not None:
                        bu = best_us(rows, g, norm, cut, at["line"])
                        cl = pin_at(rows, g, norm, st)
                        if bu and cl and (g == "ml" or (F._n(cl["line"]) and abs(cl["line"] - at["line"]) <= F.LINE_EPS)):
                            clv = round((cl["fair"] - bu[0]) * 100, 4)
                    out.append(dict(fe, sport=sport, gid=gid, away=gm["away"], home=gm["home"], start=st, cut=cut, g=g, norm=norm,
                                    mg1=mg1(fe, g, sport), pin_line=at["line"] if at else None, pin_px=at["px"] if at else None,
                                    pin_fair=round(at["fair"], 6) if at else None, after=after, why_after=why_after, clv_us=clv))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"now": a.now or newest, "rows": out}, open(a.out, "w"))
    print("sides %d, games %d" % (len(out), len({r["gid"] for r in out})), file=sys.stderr)


if __name__ == "__main__":
    main()
