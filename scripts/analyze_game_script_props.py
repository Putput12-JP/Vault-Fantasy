#!/usr/bin/env python3
"""analyze_game_script_props.py: how do settled props line up with game script?

Joins every settled prop in data/bet_results.json to its game (closing total +
spread and Vault's game line from data/game_line_history.json, final score from
nflverse games.csv with an ESPN fill, same loaders as settle_bets) and slices
prop results by:

  HINDSIGHT (not bettable; shows how much props ride on game script)
    game_total   the game went over / under its closing total
    team_total   the prop player's team beat / missed its IMPLIED team total
                 (no team-total market is stored, so implied = total/2 - spread/2)
  PRE-GAME (bettable)
    vault_total  Vault's game total vs the market total (lean over/under at 1.5pt,
                 the same bar the Game Markets card uses)
    vault_team   Vault's implied team total vs the market's (lean at 1pt)
    mkt_team     the market's implied team total itself (low / mid / high)

Every prop is graded on BOTH sides (the recorded side's `grade` + `grade_alt`
for the other card), scored flat 1u at the side's closing consensus price
(-110 when no clean two-way close). pass_int is left out of the over/under
alignment rows because its "over" is bad offense.

  python3 scripts/analyze_game_script_props.py [--season 2026] [--json out.json]
"""
import argparse, json, math, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settle_bets as S

DATA = os.path.join(os.path.dirname(HERE), "data")
TOTAL_LEAN, TEAM_LEAN = 1.5, 1.0
GRADE_GROUPS = [("A", ("A",)), ("B", ("B",)), ("A+B", ("A", "B")), ("C", ("C",)), ("D/F", ("D", "F")), ("all", ("A", "B", "C", "D", "F"))]


def pay(price):
    if price is None:
        return 100 / 110
    return price / 100 if price > 0 else 100 / abs(price)


def load_games(season):
    gl = json.load(open(os.path.join(DATA, "game_line_history.json")))["games"]
    reg = {k: g for k, g in gl.items() if str(g.get("season")) == str(season)
           and (g.get("seasonType") or "").lower() == "regular"}
    scores = S.load_games_csv({int(season)})
    need = {(str(g["season"]), str(g["week"]), 2) for g in reg.values()
            if (str(g["season"]), str(g["week"]), S.team_nfl(g["away"]), S.team_nfl(g["home"])) not in scores}
    if need:
        for k, v in S.load_espn_scores(need).items():
            scores.setdefault(k, v)
    out = {}
    for g in reg.values():
        sc = scores.get((str(g["season"]), str(g["week"]), S.team_nfl(g["away"]), S.team_nfl(g["home"])))
        if not sc:
            continue
        samples = (g.get("samples") or []) + [g.get("cur") or {}]
        close = next((s for s in reversed(samples) if s.get("total") is not None and s.get("spread") is not None), None)
        vault = next((s["vault"] for s in reversed(samples) if s.get("vault") and s["vault"].get("total") is not None), None)
        if not close:
            continue
        tot, sp = float(close["total"]), float(close["spread"])      # spread = HOME line
        rec = {"week": int(g["week"]), "away": S.team_nfl(g["away"]), "home": S.team_nfl(g["home"]),
               "total": tot, "spread": sp, "hs": sc["home_score"], "as": sc["away_score"],
               "v_total": vault["total"] if vault else None, "v_spread": vault.get("spread") if vault else None}
        out[(rec["week"], rec["home"])] = out[(rec["week"], rec["away"])] = rec
    return out


def implied(total, home_spread, is_home):
    ts = home_spread if is_home else -home_spread
    return total / 2 - ts / 2


def build_rows(season):
    games = load_games(season)
    props = json.load(open(os.path.join(DATA, "bet_results.json")))["props"]
    rows, unmatched = [], 0
    for p in props:
        if str(p.get("season")) != str(season) or p.get("push") or p.get("won_close") is None or not p.get("side"):
            continue
        g = games.get((int(p["week"]), S.team_nfl(p.get("team"))))
        if not g:
            unmatched += 1
            continue
        is_home = S.team_nfl(p["team"]) == g["home"]
        pts = g["hs"] if is_home else g["as"]
        imp = implied(g["total"], g["spread"], is_home)
        v_imp = implied(g["v_total"], g["v_spread"], is_home) if g["v_total"] is not None and g["v_spread"] is not None else None
        game_pts = g["hs"] + g["as"]
        ctx = {
            "week": p["week"], "market": p["market"],
            "game_total": None if game_pts == g["total"] else ("over" if game_pts > g["total"] else "under"),
            "team_total": None if pts == imp else ("over" if pts > imp else "under"),
            "vault_total": None if g["v_total"] is None else
                ("over" if g["v_total"] - g["total"] >= TOTAL_LEAN else "under" if g["total"] - g["v_total"] >= TOTAL_LEAN else "neutral"),
            "vault_team": None if v_imp is None else
                ("over" if v_imp - imp >= TEAM_LEAN else "under" if imp - v_imp >= TEAM_LEAN else "neutral"),
            "mkt_team": "low (<20)" if imp < 20 else "high (24+)" if imp >= 24 else "mid (20-24)",
        }
        over_won = p["won_close"] if p["side"] == "over" else 1 - p["won_close"]
        for side in ("over", "under"):
            grade = p.get("grade") if side == p["side"] else p.get("grade_alt")
            if not grade:
                continue
            won = over_won if side == "over" else 1 - over_won
            price = p.get("close_over") if side == "over" else p.get("close_under")
            rows.append(dict(ctx, side=side, grade=grade, won=won, u=pay(price) if won else -1.0))
    return rows, games, unmatched


def agg(rs):
    n = len(rs)
    if not n:
        return None
    us = [r["u"] for r in rs]
    return {"n": n, "win": sum(r["won"] for r in rs) / n, "units": sum(us), "roi": sum(us) / n,
            "se": statistics.pstdev(us) / math.sqrt(n) if n > 1 else None}


def fmt(a):
    if not a:
        return "      -"
    return f"n={a['n']:4} win={a['win']*100:5.1f}% {a['units']:+6.1f}u roi={a['roi']*100:+6.1f}% (+-{(a['se'] or 0)*100:.0f})"


def table(rows, dim, title):
    print(f"\n=== {title} ===")
    for val in sorted({r[dim] for r in rows if r[dim] is not None}):
        for side in ("over", "under"):
            sub = [r for r in rows if r[dim] == val and r["side"] == side and r["market"] != "pass_int"]
            print(f"  {dim}={val:11} prop {side:5}")
            for lbl, gs in GRADE_GROUPS:
                a = agg([r for r in sub if r["grade"] in gs])
                if a:
                    print(f"      {lbl:4} {fmt(a)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2026")
    ap.add_argument("--json")
    a = ap.parse_args()
    rows, games, unmatched = build_rows(a.season)
    g_list = {(g["week"], g["home"]): g for g in games.values()}.values()
    print(f"graded prop sides: {len(rows)}  games with scores: {len(g_list)}  props w/o a scored game: {unmatched}")

    # How good are Vault's game leans on their own?
    vt = [(g["v_total"] - g["total"], g["hs"] + g["as"] - g["total"]) for g in g_list if g["v_total"] is not None]
    lean = [(d, r) for d, r in vt if abs(d) >= TOTAL_LEAN and r != 0]
    print(f"Vault total leans (|gap|>={TOTAL_LEAN}): {sum(1 for d, r in lean if (d > 0) == (r > 0))}-"
          f"{sum(1 for d, r in lean if (d > 0) != (r > 0))} on {len(lean)} games")
    tl = []
    for g in g_list:
        if g["v_total"] is None or g["v_spread"] is None:
            continue
        for is_home in (True, False):
            d = implied(g["v_total"], g["v_spread"], is_home) - implied(g["total"], g["spread"], is_home)
            r = (g["hs"] if is_home else g["as"]) - implied(g["total"], g["spread"], is_home)
            if abs(d) >= TEAM_LEAN and r != 0:
                tl.append((d > 0) == (r > 0))
    print(f"Vault team-total leans (|gap|>={TEAM_LEAN}): {sum(tl)}-{len(tl) - sum(tl)} on {len(tl)} team-games")

    table(rows, "game_total", "HINDSIGHT: game went over / under its total")
    table(rows, "team_total", "HINDSIGHT: player's team beat / missed its implied team total")
    table(rows, "vault_total", "PRE-GAME: Vault game-total lean")
    table(rows, "vault_team", "PRE-GAME: Vault team-total lean")
    table(rows, "mkt_team", "PRE-GAME: market implied team total")

    # Alignment: prop side agrees with Vault's team lean
    print("\n=== PRE-GAME: prop side vs Vault TEAM lean ===")
    al = [r for r in rows if r["vault_team"] in ("over", "under") and r["market"] != "pass_int"]
    for lbl, keep in (("with lean", lambda r: r["side"] == r["vault_team"]), ("against lean", lambda r: r["side"] != r["vault_team"])):
        for gl, gs in GRADE_GROUPS:
            x = agg([r for r in al if keep(r) and r["grade"] in gs])
            if x:
                print(f"  {lbl:12} {gl:4} {fmt(x)}")

    # Every pre-game filter x side x grade group, ranked, with week-by-week units
    print("\n=== PRE-GAME filters ranked by units (n>=25) ===")
    cands = []
    for dim in ("vault_total", "vault_team", "mkt_team"):
        for val in {r[dim] for r in rows if r[dim] is not None}:
            for side in ("over", "under"):
                for gl, gs in GRADE_GROUPS:
                    sub = [r for r in rows if r[dim] == val and r["side"] == side and r["grade"] in gs and r["market"] != "pass_int"]
                    x = agg(sub)
                    if x and x["n"] >= 25:
                        wk = {w: round(sum(r["u"] for r in sub if r["week"] == w), 1) for w in sorted({r["week"] for r in sub})}
                        cands.append((x["units"], f"{dim}={val} prop {side} {gl}", x, wk))
    for _, lbl, x, wk in sorted(cands, key=lambda c: -c[0])[:15]:
        print(f"  {lbl:40} {fmt(x)}  by week {wk}")
    if a.json:
        json.dump({"rows": rows}, open(a.json, "w"))


if __name__ == "__main__":
    main()
