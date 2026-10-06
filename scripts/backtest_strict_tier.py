#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
#  VAULT · BEST BETS "STRICT TIER" BACKTEST  →  docs/strict-tier-backtest.md
#
#  The strict tier (build_best_bets.mjs strictOk) is a play where Vault's own
#  P(side) AND the real book's no-vig P(side) both clear a bar, on a market with
#  a measured signal (QB attempts/completions/yards excluded, see
#  docs/retro lean-accuracy notes), at a bettable price. This replays the shipped
#  model on 2024-25 ESPN BET closing lines and answers three questions:
#    1. What hit rate / ROI do the shipped thresholds give each season?
#    2. WALK-FORWARD: pick thresholds on one season only, score them on the
#       other, both directions (so the thresholds are not tuned on the test).
#    3. How sensitive is it to the thresholds, and how many plays per week?
#  Caveats printed with the result: single book (ESPN BET close), no
#  matchup/role multipliers, thresholds were first explored on this same data.
#
#  Usage: python3 scripts/backtest_strict_tier.py [--write]
# ════════════════════════════════════════════════════════════════════════════
import sys, os, json, csv, io, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_prop_market_prior as P
B = P.B
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE = {"pass_att", "pass_cmp", "pass_yd"}          # no measured edge (WEAK_MK)
PRICE_MIN, PRICE_MAX = -250, 200                       # same bettable band as the live gate
SHIPPED = (0.70, 0.58)                                 # (model P(side), market no-vig P(side))
dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)


def load_rows():
    games = list(csv.DictReader(io.StringIO(P.get_text(P.GAMES_URL)))); gmap = {g["game_id"]: g for g in games}
    e2n = {r["espn_id"]: r["display_name"] for r in csv.DictReader(io.StringIO(P.get_text(P.PLAYERS_URL))) if r.get("espn_id")}
    model = json.load(open(os.path.join(ROOT, "data/prop_model.json")))["markets"]
    W = P.load_weeks([min(P.SEASONS) - 1, *P.SEASONS])
    rows = []
    for season in P.SEASONS:
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in P.load_lines(season, games, False):
            m = model.get(mkt); name = e2n.get(ath); g = gmap.get(gid)
            if not (m and name and g) or mkt in EXCLUDE: continue
            yr, wk = int(g["season"]), int(g["week"])
            pos, cur = W.get((P.nkey(name), yr), (None, []))
            if pos is None or pos not in m["pos"]: continue
            row = next((w for w in cur if B.num(w.get("wk")) == wk), None)
            if row is None: continue
            prev = W.get((P.nkey(name), yr - 1), (None, []))[1]
            proj = P.project(m, mkt, prev + [w for w in cur if (B.num(w.get("wk")) or 0) < wk]); act = P.actual_of(m, row)
            if proj is None or act is None or lc is None or oc is None or uc is None or abs(act - lc) < 1e-9: continue
            p = P.p_over(m, proj, lc); q = P.imp(oc) / (P.imp(oc) + P.imp(uc))
            over = p >= 0.5
            rows.append({"mkt": mkt, "yr": yr, "wk": wk, "conf": max(p, 1 - p), "mq": q if over else 1 - q,
                         "px": oc if over else uc, "hit": (act > lc) == over})
    return [r for r in rows if PRICE_MIN <= r["px"] <= PRICE_MAX]


def tier(rows, t, m):
    return [r for r in rows if r["conf"] >= t and r["mq"] >= m]


def stats(X):
    n = len(X)
    if not n: return {"n": 0, "hit": None, "roi": None, "imp": None, "se": None}
    h = sum(r["hit"] for r in X) / n
    return {"n": n, "hit": h, "roi": sum((dec(r["px"]) - 1) if r["hit"] else -1 for r in X) / n,
            "imp": sum(r["mq"] for r in X) / n, "se": math.sqrt(h * (1 - h) / n)}


def fmt(s):
    return "no plays" if not s["n"] else (f"{s['hit']*100:4.1f}% hit (±{s['se']*100:.1f}) | market {s['imp']*100:4.1f}% | "
                                          f"ROI {s['roi']*100:+5.1f}% | n={s['n']}")


def main():
    rows = load_rows()
    out = [f"STRICT TIER BACKTEST: {len(rows)} real lines, 2024-25 ESPN BET close, QB volume markets excluded",
           f"price band {PRICE_MIN}..{PRICE_MAX}", ""]
    t, m = SHIPPED
    out.append(f"1) Shipped thresholds (model >= {t:.2f}, market >= {m:.2f}):")
    for y in (2024, 2025, None):
        X = tier([r for r in rows if y is None or r["yr"] == y], t, m)
        wks = len({(r["yr"], r["wk"]) for r in X}) or 1
        out.append(f"   {y or 'both':>4}: {fmt(stats(X))} | {len(X)/wks:.1f} plays/week")
    out += ["", "2) Walk-forward: best thresholds on ONE season (hit>=65%, n>=60, max ROI), scored once on the OTHER:"]
    grid = [(a, b) for a in (0.60, 0.65, 0.70, 0.75) for b in (0.52, 0.55, 0.58, 0.60)]
    for fit, test in ((2024, 2025), (2025, 2024)):
        ok = []
        for a, b in grid:
            s = stats(tier([r for r in rows if r["yr"] == fit], a, b))
            if s["n"] >= 60 and s["hit"] >= 0.65: ok.append((s["roi"], a, b))
        if not ok: out.append(f"   fit {fit}: no threshold met hit>=65% with n>=60"); continue
        _, a, b = max(ok)
        out.append(f"   fit {fit} -> model>={a:.2f} mkt>={b:.2f}: in-sample {fmt(stats(tier([r for r in rows if r['yr']==fit], a, b)))}")
        out.append(f"      scored on {test}: {fmt(stats(tier([r for r in rows if r['yr']==test], a, b)))}")
    out += ["", "3) Sensitivity (both seasons):"]
    for a, b in grid:
        out.append(f"   model>={a:.2f} mkt>={b:.2f}: {fmt(stats(tier(rows, a, b)))}")
    out += ["", "By market at the shipped thresholds:"]
    for mk in sorted({r["mkt"] for r in rows}):
        X = tier([r for r in rows if r["mkt"] == mk], t, m)
        if X: out.append(f"   {mk:9s} {fmt(stats(X))}")
    out += ["", "Caveats: one book's closing line (live uses the median of real books at the posted price); the replay",
            "omits matchup/role/script multipliers the live board adds; the shipped thresholds were first found on this",
            "same data, so the walk-forward in (2) is the honest number. Live shadow tracking is the real test."]
    txt = "\n".join(out); print(txt)
    if "--write" in sys.argv:
        os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
        open(os.path.join(ROOT, "docs/strict-tier-backtest.md"), "w").write("```\n" + txt + "\n```\n")


if __name__ == "__main__":
    main()
