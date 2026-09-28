#!/usr/bin/env python3
# ============================================================================
# VAULT · NFL GAME MODEL  →  data/game_model.json
#
# A team power-rating model that produces a "Vault line" for each game: a
# projected spread, total, and win probability. Fit from real game scores
# (nflverse games.csv, 1999-present, which also carries the historical closing
# lines used to validate it).
#
# HONEST FRAMING (measured — see the backtest it prints):
#   The model MATCHES the market to ~0.4 pts on margin and total, but does NOT
#   beat the closing line (ATS ~49%, O/U ~49%, win-prob Brier just behind the
#   market). NFL closing lines are the sharpest forecast there is. So the Vault
#   line is shipped as a market-QUALITY *context* number — a model estimate shown
#   next to the market — NEVER as a +EV edge. Do not label it as one.
#
# MODEL (stable online ratings, updated after each game, mean-reverted each
# season):
#   margin: net rating per team; pred_margin = rate[home] − rate[away] + HFA
#   scoring: off/def points ratings; pred_total = home_pts + away_pts
#   win prob: Φ(pred_margin / sd_margin)
#
# Pure stdlib (json/math/statistics/urllib). No numpy/pandas.
#
# Usage:
#   python3 scripts/build_game_model.py            # fit + backtest + write
#   python3 scripts/build_game_model.py --dry      # fit + backtest, no write
# ============================================================================
import argparse, csv, io, json, math, os, ssl, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "game_model.json")
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# fitted online-learning rates (flat RMSE plateau across the grid; these sit at
# the minimum). HFA and the sd's are measured from the walk-forward below.
K_MARGIN = 0.065
# Market learning: after each game the ratings also move toward what that
# game's CLOSING line said (w x the line's miss vs the model's own prediction).
# Final scores can't see a new coach, scheme or roster; the market prices them
# before Week 1, so this is how offseason change reaches the ratings. Fitted +
# gated in fit_mkt(); 0 = scores only (the pre-2026-09-28 model).
MKT = {"margin": 0.0, "total": 0.0}
K_SCORE = 0.045
CARRY = 0.72          # cross-season mean-reversion of ratings
RIDGE = 0.05          # pull scoring ratings toward 0 each update
BASE_PTS = 22.7       # league avg points per team per game
TRAIN_FROM = 2006     # ratings warm up from here
TEST_FROM = 2014      # backtest window (fully warmed ratings)

# nflverse uses current team codes; map any legacy codes the live feed might send.
ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS"}


def norm_team(t):
    t = (t or "").upper()
    return ALIAS.get(t, t)


def fetch_games():
    """games.csv → list of completed-game dicts. requests in CI, urllib locally."""
    text = None
    try:
        import requests
        text = requests.get(GAMES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=90).text
    except Exception:
        import urllib.request
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(GAMES_URL, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=90, context=ctx).read().decode("utf-8", "replace")

    def f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    out = []
    for r in csv.DictReader(io.StringIO(text)):
        hs, as_ = f(r["home_score"]), f(r["away_score"])
        season = int(r["season"]) if r.get("season", "").isdigit() else None
        if season is None or season < TRAIN_FROM:
            continue
        wk = int(r["week"]) if r.get("week", "").isdigit() else 99
        rec = {"season": season, "week": wk, "ht": norm_team(r["home_team"]), "at": norm_team(r["away_team"]),
               "hs": hs, "as_": as_, "spread": f(r.get("spread_line")), "total_line": f(r.get("total_line")),
               "played": hs is not None and as_ is not None,
               # starting QBs (nflverse fills the expected starter for upcoming games)
               "hq": (r.get("home_qb_id") or "").strip() or None, "aq": (r.get("away_qb_id") or "").strip() or None,
               # international games / Super Bowls: nobody is home, so no HFA
               "neutral": (r.get("location") or "").strip().lower() == "neutral"}
        for k in ("home", "away"):
            qid = (r.get(f"{k}_qb_id") or "").strip()
            if qid: QB_NAMES[qid] = (r.get(f"{k}_qb_name") or "").strip()
        out.append(rec)
    out.sort(key=lambda g: (g["season"], g["week"]))
    return out


# Backup-QB adjustment. A team's ESTABLISHED starter = the QB with the most
# starts in its last QB_WINDOW games (across seasons), at least QB_MIN_STARTS
# of them. A game started by anyone else is a backup start. Cross-season on
# purpose: a fill-in who opens a season (Cooper Rush, ATL wks 1-2 2026) must
# not turn the real starter's return into a "backup" game. Window chosen out of
# sample (fit < 2020, scored 2020+): 24/10 beat season-only and 8-40 windows.
QB_WINDOW, QB_MIN_STARTS = 24, 10
QB_NONE = {"margin": 0.0, "total": 0.0}
QB = dict(QB_NONE)   # fitted in main() (fit_qb)
QB_NAMES = {}        # gsis id -> name, filled by fetch_games


def established_qb(recent):
    """Established starter from a team's recent starter ids, or None."""
    c = defaultdict(int)
    for q in recent: c[q] += 1
    if not c: return None
    prim, n = max(c.items(), key=lambda kv: kv[1])
    return prim if n >= QB_MIN_STARTS else None


def backup_start(recent, g, tk, qk, season_starts):
    """1 when this game's listed starter is not the team's established QB AND
    the established QB has started for the team this season. The second part
    drops offseason moves (Rodgers joining PIT is not a backup start behind a
    departed Wilson), which history can't see as roster changes."""
    q = g.get(qk)
    prim = established_qb(recent[g[tk]])
    return 1 if q and prim and q != prim and season_starts[(g["season"], g[tk])].get(prim) else 0


def run(games, collect_from=None, qb=None):
    """
    Walk the games in order, predicting each BEFORE updating (so predictions are
    out-of-sample), mean-reverting ratings each new season. Returns final ratings
    and the list of prediction records from `collect_from` onward.
    qb: backup-QB adjustment {margin, total} in points per backup start (see
    fit_qb); None = off.
    Ratings update against the ADJUSTED prediction, so a loss with the backup
    in does not drag down the team's rating with its starter.
    """
    qb = qb or QB_NONE
    rate = defaultdict(float)                 # net margin rating
    off = defaultdict(float); dff = defaultdict(float)  # scoring ratings (pts vs avg)
    recent = defaultdict(list)                          # team -> starter ids, last QB_WINDOW games
    season_starts = defaultdict(lambda: defaultdict(int))   # (season, team) -> {qb id: starts}
    cur = None
    preds = []
    for g in games:
        if g["season"] != cur:
            if cur is not None:
                for t in rate: rate[t] *= CARRY
                for t in off: off[t] *= CARRY; dff[t] *= CARRY
            cur = g["season"]
        hb, ab = backup_start(recent, g, "ht", "hq", season_starts), backup_start(recent, g, "at", "aq", season_starts)
        hfa = 0.0 if g["neutral"] else HFA
        pm = rate[g["ht"]] - rate[g["at"]] + hfa - qb["margin"] * (hb - ab)
        # a backup start moves that team's points by -(total+margin)/2 and the
        # opponent's by (margin-total)/2: margin -margin, total -total
        own, opp = (qb["total"] + qb["margin"]) / 2, (qb["margin"] - qb["total"]) / 2
        ph = BASE_PTS + off[g["ht"]] - dff[g["at"]] + hfa / 2 - own * hb + opp * ab
        pa = BASE_PTS + off[g["at"]] - dff[g["ht"]] - hfa / 2 - own * ab + opp * hb
        pt = ph + pa
        if not g["played"]:
            continue
        for tk, qk in (("ht", "hq"), ("at", "aq")):
            if g[qk]:
                recent[g[tk]] = (recent[g[tk]] + [g[qk]])[-QB_WINDOW:]
                season_starts[(g["season"], g[tk])][g[qk]] += 1
        if collect_from is not None and g["season"] >= collect_from:
            preds.append({"pm": pm, "pt": pt, "result": g["hs"] - g["as_"], "total": g["hs"] + g["as_"],
                          "spread": g["spread"], "total_line": g["total_line"],
                          "home_win": 1 if g["hs"] > g["as_"] else 0, "backup": hb or ab,
                          "season": g["season"]})
        # updates
        em = (g["hs"] - g["as_"]) - pm
        rate[g["ht"]] += K_MARGIN * em; rate[g["at"]] -= K_MARGIN * em
        eh = g["hs"] - ph; ea = g["as_"] - pa
        off[g["ht"]] += K_SCORE * (eh - RIDGE * off[g["ht"]]); dff[g["at"]] -= K_SCORE * (eh - RIDGE * dff[g["at"]])
        off[g["at"]] += K_SCORE * (ea - RIDGE * off[g["at"]]); dff[g["ht"]] -= K_SCORE * (ea - RIDGE * dff[g["ht"]])
        # market learning (nflverse spread_line = closing expected HOME margin,
        # total_line = closing total; both already price that day's QBs)
        if MKT["margin"] and g["spread"] is not None:
            ex = g["spread"] - pm
            rate[g["ht"]] += MKT["margin"] * ex; rate[g["at"]] -= MKT["margin"] * ex
        if MKT["total"] and g["total_line"] is not None:
            et = (g["total_line"] - pt) / 4   # split over both offenses and both defenses: margin unchanged
            for t in (g["ht"], g["at"]):
                off[t] += MKT["total"] * et; dff[t] -= MKT["total"] * et
    return rate, off, dff, preds, recent, season_starts


HFA = 1.6   # provisional; re-fit from data below


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def backtest(games):
    """Walk-forward metrics from TEST_FROM: model vs the market's closing line."""
    _, _, _, preds, _, _ = run(games, collect_from=TEST_FROM, qb=QB)
    rt = lambda a: math.sqrt(statistics.fmean(a))
    mp = [p for p in preds if p["spread"] is not None]
    tp = [p for p in preds if p["total_line"] is not None]
    m = {
        "n": len(preds),
        "margin_rmse": round(rt([(p["pm"] - p["result"]) ** 2 for p in preds]), 3),
        "market_margin_rmse": round(rt([(p["spread"] - p["result"]) ** 2 for p in mp]), 3),
        "ats_pct": round(statistics.fmean([(1 if p["result"] > p["spread"] else 0) if p["pm"] > p["spread"]
                          else (1 if p["result"] < p["spread"] else 0) for p in mp]) * 100, 1),
        "total_rmse": round(rt([(p["pt"] - p["total"]) ** 2 for p in tp]), 3),
        "market_total_rmse": round(rt([(p["total_line"] - p["total"]) ** 2 for p in tp]), 3),
        "ou_pct": round(statistics.fmean([(1 if p["total"] > p["total_line"] else 0) if p["pt"] > p["total_line"]
                         else (1 if p["total"] < p["total_line"] else 0) for p in tp]) * 100, 1),
        "brier": round(statistics.fmean([(phi(p["pm"] / SD_MARGIN) - p["home_win"]) ** 2 for p in preds]), 4),
        "market_brier": round(statistics.fmean([(phi(p["spread"] / SD_MARGIN) - p["home_win"]) ** 2 for p in mp]), 4),
    }
    # games with a backup QB: where the adjustment acts, next to the market
    bp = [p for p in mp if p["backup"]]
    _, _, _, raw, _, _ = run(games, collect_from=TEST_FROM)
    rb = [r for r, p in zip(raw, preds) if p["backup"] and p["spread"] is not None]
    if bp:
        m["backup_qb"] = {"n": len(bp), "margin_rmse": round(rt([(p["pm"] - p["result"]) ** 2 for p in bp]), 3),
                          "margin_rmse_unadjusted": round(rt([(r["pm"] - r["result"]) ** 2 for r in rb]), 3),
                          "market_margin_rmse": round(rt([(p["spread"] - p["result"]) ** 2 for p in bp]), 3)}
    return m


def fit_blend(games):
    """Headline-line weight on the model: line = market + w * (model - market).
    w is fit by least squares on seasons BEFORE each test season and scored
    walk-forward against the closing line. GATED: w ships only if that
    walk-forward error beats the market's own; otherwise 0 (pure market fair
    line). Model-upgrade plan (reports/NFL prediction model upgrade.md):
    2014-2026, spreads walk-forward 12.712 vs market 12.699 RMSE (w drifting
    0.39 -> 0.06), totals w = 0 every season, the old fixed 0.5 blend worse on
    both (12.800 / 13.373). So the served line is the market fair line."""
    played = [g for g in games if g["played"] and g["season"] >= TEST_FROM]
    _, _, _, preds, _, _ = run(games, collect_from=TEST_FROM, qb=QB)
    for p, g in zip(preds, played): p["season"] = g["season"]
    out = {}
    for name, mk, lk, rk in (("spread", "pm", "spread", "result"), ("total", "pt", "total_line", "total")):
        def w_of(ps):
            ps = [p for p in ps if p[lk] is not None]
            num = sum((p[mk] - p[lk]) * (p[rk] - p[lk]) for p in ps)
            den = sum((p[mk] - p[lk]) ** 2 for p in ps)
            return max(0.0, min(1.0, num / den)) if den else 0.0
        e_wf, e_mkt = [], []
        for s in sorted({p["season"] for p in preds}):
            tr = [p for p in preds if p["season"] < s and p[lk] is not None]
            te = [p for p in preds if p["season"] == s and p[lk] is not None]
            if len(tr) < 500 or not te: continue
            w = w_of(tr)
            for p in te:
                e_wf.append((p[lk] + w * (p[mk] - p[lk]) - p[rk]) ** 2); e_mkt.append((p[lk] - p[rk]) ** 2)
        rm_wf = math.sqrt(statistics.fmean(e_wf)) if e_wf else None
        rm_mk = math.sqrt(statistics.fmean(e_mkt)) if e_mkt else None
        w_all = w_of(preds)
        ok = rm_wf is not None and rm_mk is not None and rm_wf < rm_mk
        out[name] = {"w": round(w_all, 4) if ok else 0.0, "w_fit": round(w_all, 4), "gate": "passed" if ok else "failed",
                     "rmse_walkforward": None if rm_wf is None else round(rm_wf, 3),
                     "rmse_market": None if rm_mk is None else round(rm_mk, 3), "n": len(e_mkt)}
    out["win"] = dict(out["spread"])   # win% moves with the margin blend
    return out


def fit_mkt(games):
    """Market-learning weights (margin, total): grid-fit on seasons before
    TEST_FROM, GATED on the test seasons like fit_qb. 2026-09-28 check:
    margin RMSE 13.123 -> ~13.03 at w 0.1-0.2, still behind the market's own
    12.87 (the model stays context, not an edge)."""
    def err(key, lo, hi):
        _, _, _, ps, _, _ = run(games, collect_from=lo, qb=QB)
        ps = [p for p in ps if p["season"] < hi]
        mk, rk = ("pm", "result") if key == "margin" else ("pt", "total")
        return math.sqrt(statistics.fmean([(p[mk] - p[rk]) ** 2 for p in ps]))
    out = {}
    for key in ("margin", "total"):
        grid = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
        tr = {}
        for v in grid:
            MKT[key] = v; tr[v] = err(key, TRAIN_FROM + 2, TEST_FROM)
        best = min(grid, key=lambda v: tr[v])
        MKT[key] = 0.0; base = err(key, TEST_FROM, 9999)
        MKT[key] = best; adj = err(key, TEST_FROM, 9999)
        ok = best > 0 and adj < base
        out[key] = {"fit": best, "rmse_test": round(adj, 4), "rmse_test_without": round(base, 4), "gate": "passed" if ok else "failed"}
        if not ok: MKT[key] = 0.0
    return dict(MKT), out


def fit_qb(games):
    """Points per backup start (margin, total), fit on seasons before TEST_FROM
    and GATED on the test seasons: each part ships only if it lowers the
    out-of-sample RMSE against the actual result. Ratings update against the
    adjusted prediction, so every grid point re-runs the walk."""
    def err(qb, lo, hi, key):
        _, _, _, ps, _, _ = run(games, collect_from=lo, qb=qb)
        ps = [p for p in ps if p["season"] < hi]
        mk, rk = ("pm", "result") if key == "margin" else ("pt", "total")
        return math.sqrt(statistics.fmean([(p[mk] - p[rk]) ** 2 for p in ps]))
    fitted, out = dict(QB_NONE), {}
    for key in ("margin", "total"):
        grid = [x / 4 for x in range(0, 25)]            # 0 .. 6 pts
        best = min(grid, key=lambda v: err(dict(fitted, **{key: v}), TRAIN_FROM + 2, TEST_FROM, key))
        fitted[key] = best
        base = err(dict(fitted, **{key: 0.0}), TEST_FROM, 9999, key)
        adj = err(fitted, TEST_FROM, 9999, key)
        ok = adj < base
        out[key] = {"fit": best, "rmse_test": round(adj, 4), "rmse_test_without": round(base, 4), "gate": "passed" if ok else "failed"}
        if not ok: fitted[key] = 0.0
    return fitted, out


SD_MARGIN = 13.2   # provisional; re-fit below
SD_TOTAL = 13.5

SB_PATH = os.path.join(ROOT, "data", "edge_scoreboard.json")
K_GAME = 150          # sample the in-season overlay corrections shrink against


def load_overlay():
    """LOOP-CLOSER. Read how the SERVED model line actually did this season
    (scripts/settle_bets.py → edge_scoreboard.games) and return small,
    sample-shrunk deltas for the served hfa / base_pts / sd_margin. Mirrors the
    prop builder's inseason overlay: settle_bets fits the corrections, the
    builder applies them shrunk by n/(n+K). Only IN-SEASON picks count —
    offseason-rating errors (Wk1 on priors) are not the tuned model — so a cold
    season with no in-season results is a clean no-op. These are intercept-level
    corrections on the served numbers; ratings are NOT refit."""
    try:
        sb = json.load(open(SB_PATH))
    except Exception:
        return {}
    g = sb.get("games") or {}
    sp, tot, ml = g.get("spread") or {}, g.get("total") or {}, g.get("ml") or {}
    def shrink(n): return (n or 0) / ((n or 0) + K_GAME)
    out = {}
    # spread proj_bias = mean(model home margin − actual); +bias ⇒ model runs
    # home-high ⇒ trim HFA by the shrunk bias (clamped to ±1.5 pt).
    b, n = sp.get("proj_bias_inseason"), sp.get("n_proj_inseason") or 0
    if b is not None and n:
        out["hfa"] = {"delta": round(max(-1.5, min(1.5, -shrink(n) * b)), 3), "bias": round(b, 3), "n": n}
    # total proj_bias = mean(model total − actual); total = 2·base_pts, so a
    # total bias of x corrects base_pts by −x/2 (clamped to ±3 pt).
    b, n = tot.get("proj_bias_inseason"), tot.get("n_proj_inseason") or 0
    if b is not None and n:
        out["base_pts"] = {"delta": round(max(-3.0, min(3.0, -shrink(n) * b / 2.0)), 3), "bias": round(b, 3), "n": n}
    # win-prob sd scale (k>1 ⇒ model overconfident ⇒ widen sd_margin), shrunk and
    # clamped to [0.8, 1.3] so a thin sample can't swing calibration hard.
    k, n = ml.get("winprob_sd_k"), ml.get("n_cal_inseason") or 0
    if k is not None and n:
        out["sd_margin"] = {"factor": round(max(0.8, min(1.3, 1.0 + shrink(n) * (k - 1.0))), 4), "k": k, "n": n}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-overlay", action="store_true", help="skip the in-season self-correction overlay (pure historical fit)")
    args = ap.parse_args()
    global HFA, SD_MARGIN, SD_TOTAL, QB

    print("[game-model] fetching nflverse games.csv …")
    games = fetch_games()
    played = [g for g in games if g["played"]]
    print(f"[game-model] {len(played)} completed games {games[0]['season']}–{played[-1]['season']}")

    # fit HFA = mean home margin over the last 3 completed seasons (true home
    # games only — a neutral-site "home" team has no crowd or travel edge)
    last3 = sorted({g["season"] for g in played})[-3:]
    HFA = round(statistics.fmean([g["hs"] - g["as_"] for g in played if g["season"] in last3 and not g["neutral"]]), 3)

    QB, qb_fit = fit_qb(games)
    mkt_w, mkt_fit = fit_mkt(games)
    print(f"[game-model] market learning: margin w {mkt_w['margin']}, total w {mkt_w['total']} · {mkt_fit}")
    QB, qb_fit = fit_qb(games)   # refit the backup-QB points with market learning on
    print(f"[game-model] backup QB: margin -{QB['margin']} pts, total -{QB['total']} pts per backup start · {qb_fit}")

    # fit the residual sd's from the walk-forward, then recompute metrics with them
    _, _, _, preds, _, _ = run(games, collect_from=TEST_FROM, qb=QB)
    SD_MARGIN = round(statistics.pstdev([p["pm"] - p["result"] for p in preds]), 3)
    SD_TOTAL = round(statistics.pstdev([p["pt"] - p["total"] for p in preds]), 3)

    m = backtest(games)
    blend = fit_blend(games)
    print(f"[game-model] HFA {HFA} · sd_margin {SD_MARGIN} · sd_total {SD_TOTAL}")
    for k in ("spread", "total"):
        b = blend[k]
        print(f"[game-model] headline blend {k}: fitted w {b['w_fit']} · walk-forward RMSE {b['rmse_walkforward']} vs market {b['rmse_market']} "
              f"→ gate {b['gate']} → served w {b['w']}")
    print(f"[game-model] BACKTEST (n={m['n']}, out-of-sample from {TEST_FROM}):")
    print(f"   margin RMSE {m['margin_rmse']} vs market {m['market_margin_rmse']}  · ATS {m['ats_pct']}%")
    print(f"   total  RMSE {m['total_rmse']} vs market {m['market_total_rmse']}  · O/U {m['ou_pct']}%")
    print(f"   win-prob Brier {m['brier']} vs market {m['market_brier']}")
    if m.get("backup_qb"): print(f"   backup-QB games {m['backup_qb']}")
    print(f"   → matches the market, does NOT beat the close (context line, not an edge)")

    # final ratings from ALL completed games (current strength)
    rate, off, dff, _, recent, season_starts = run(games, qb=QB)
    through = max((g["season"], g["week"]) for g in played)
    # If the latest season is fully complete (Super Bowl played, week >= 22) and no
    # next-season games exist yet, the between-season mean-reversion hasn't fired —
    # apply it once so an offseason "Vault line" is a next-season-start estimate,
    # not a stale end-of-season rating.
    latest = through[0]
    season_done = max((g["week"] for g in played if g["season"] == latest), default=0) >= 22
    offseason = season_done and not any(g["season"] > latest for g in played)
    if offseason:
        for t in rate: rate[t] *= CARRY
        for t in off: off[t] *= CARRY; dff[t] *= CARRY
    # This season's neutral-site games as "AWAY@HOME" — every consumer of the
    # line (app, best bets, line snapshots) drops HFA for these.
    cur_season = max(g["season"] for g in games)
    neutral = sorted({f'{g["at"]}@{g["ht"]}' for g in games if g["neutral"] and g["season"] == cur_season})
    teams = {t: {"rate": round(rate[t], 3), "off": round(off[t], 3), "def": round(dff[t], 3)}
             for t in sorted(set(list(rate) + list(off)))}

    # Loop-closer: apply the in-season self-correction to the SERVED intercepts
    # (hfa / base_pts / sd_margin) after the historical fit + ratings — ratings
    # are not refit; this is a small drift correction the historical backtest
    # can't see. No-op when there are no in-season results yet.
    overlay = {} if args.no_overlay else load_overlay()
    served_hfa, served_base, served_sd = HFA, BASE_PTS, SD_MARGIN
    if overlay.get("hfa"): served_hfa = round(HFA + overlay["hfa"]["delta"], 3)
    if overlay.get("base_pts"): served_base = round(BASE_PTS + overlay["base_pts"]["delta"], 3)
    if overlay.get("sd_margin"): served_sd = round(SD_MARGIN * overlay["sd_margin"]["factor"], 3)
    if overlay:
        print(f"[game-model] in-season overlay: hfa {HFA}→{served_hfa} · base {BASE_PTS}→{served_base} · sd_margin {SD_MARGIN}→{served_sd}")
        print(f"             {overlay}")
    else:
        print("[game-model] in-season overlay: none (no in-season results banked yet)")

    model = {
        "generated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "through_season": through[0], "through_week": through[1], "offseason": offseason,
        "base_pts": served_base, "hfa": served_hfa, "sd_margin": served_sd, "sd_total": SD_TOTAL,
        "params": {"k_margin": K_MARGIN, "k_score": K_SCORE, "carry": CARRY, "ridge": RIDGE},
        "market_learning": {"w": dict(MKT), "fit": mkt_fit},
        "teams": teams, "neutral": neutral, "backtest": m,
        # Headline "Vault line" = market fair line + w * (model - market fair).
        # w = 0 unless the walk-forward check beats the close (see fit_blend).
        "blend": blend,
        # Backup-QB adjustment (points per backup start). Which team is on a
        # backup is decided hourly from Sleeper (fetch-pickem-props.mjs →
        # data/qb_status.json) against `established`, because QB news moves
        # faster than this twice-weekly refit.
        "qb": {"margin": QB["margin"], "total": QB["total"], "window": QB_WINDOW, "min_starts": QB_MIN_STARTS,
               "fit": qb_fit,
               # only QBs who have started for the team this season (same rule
               # as the fit): no flags in week 1 or for offseason departures
               "established": {t: {"id": q, "name": QB_NAMES.get(q)} for t in sorted(recent)
                               for q in [established_qb(recent[t])]
                               if q and season_starts[(through[0], t)].get(q)}},
        "inseason_overlay": (overlay or None),
        "fit": {"hfa": HFA, "base_pts": BASE_PTS, "sd_margin": SD_MARGIN},   # pre-overlay historical fit
        "note": "Context line only — matches the market, does not beat the close. Never present as +EV.",
    }
    if args.dry:
        print("[game-model] --dry: not written")
        return
    with open(OUT, "w") as f:
        json.dump(model, f)
    print(f"[game-model] wrote {OUT} · {len(teams)} teams")


if __name__ == "__main__":
    main()
