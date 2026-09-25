#!/usr/bin/env python3
# build_wind_model.py ──────────────────────────────────────────────────────────
#   Fits the WIND term for the player-prop model → data/wind_model.json
#
#   Wind cuts passing: over 16 seasons of realized wind the closing total prices
#   only ~a third of the scoring drop, and on archived DAY-BEFORE forecasts (what
#   you actually know pre-game) QB passing yards still fall ~3 yds/mph beyond what
#   the closing total implies. This term turns that into a multiplier on the
#   pass_yd projection:
#
#       windMult = clamp(1 + SLOPE · max(0, wind − KNOT), FLOOR, 1)
#
#   Fit (holdout-validated, never in-sample eyeballed):
#     • forecast: Open-Meteo previous-runs API, wind_speed_10m_previous_day1 —
#       the forecast as issued ~24h before kickoff, averaged over the first 3
#       hours of the game. Archive starts ~Feb 2024, so the fit window is the
#       2024 season onward. Live scoring (fetch-weather.mjs) uses the same
#       variable family from the same provider, so the units match.
#     • target: actual pass yds / Vault's own PREGAME pass_yd projection (the
#       exact projectFrom() math in prop-model.js, priors from prop_model.json,
#       using only weeks BEFORE the game) − 1.
#     • control: the team's implied total from the closing line, so the wind
#       slope is INCREMENTAL to envMult (which already scales by team total).
#     • KNOT chosen by grid search; the term publishes `active:true` only if it
#       lowers out-of-season error in BOTH season folds (fit 2024 → test 2025
#       and the reverse). Otherwise it ships inactive and every reader uses ×1.
#
#   Every reader falls back to windMult = 1 when this file is absent or inactive.
# ──────────────────────────────────────────────────────────────────────────────
import os, io, csv, ssl, json, time, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "wind_model.json")
GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
FCST_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"

SEASONS = [2024, 2025, 2026]          # previous-runs archive begins ~Feb 2024
FOLDS = [(2024, 2025), (2025, 2024)]  # (fit, test) — must improve in BOTH
KNOT_GRID = [0, 4, 6, 8, 10, 12]
FLOOR = 0.85                          # measured plateau: 12+ mph buckets all land ~0.85
MIN_ATT = 15                          # a real start, not a relief appearance
ALIAS = {"OAK": "LV", "LVR": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
MARKET = "pass_yd"


def norm_team(t):
    t = (t or "").upper()
    return ALIAS.get(t, t)


def fetch(url, tries=4):
    ctx = ssl.create_default_context()
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90, context=ctx) as r:
                return r.read()
        except Exception as e:
            if i == tries - 1:
                raise
            print("  retry", e); time.sleep(5 * (i + 1))


# ── games + stadiums ─────────────────────────────────────────────────────────
def load_games():
    stad = json.load(open(os.path.join(DATA, "stadiums.json")))["stadiums"]
    rows = list(csv.DictReader(io.StringIO(fetch(GAMES_URL).decode())))
    games = []
    for r in rows:
        s = int(r["season"])
        if s not in SEASONS or r["game_type"] != "REG" or not r["total"] or not r["total_line"]:
            continue
        st = stad.get(r["stadium_id"])
        roof = r["roof"] or ("closed" if st and st["roof"] != "outdoor" else "outdoors")
        games.append(dict(season=s, week=int(r["week"]), gameday=r["gameday"], gametime=r["gametime"],
                          home=norm_team(r["home_team"]), away=norm_team(r["away_team"]),
                          total_line=float(r["total_line"]), spread_line=float(r["spread_line"] or 0),
                          outdoor=roof in ("outdoors", "open"), sid=r["stadium_id"], st=st))
    return games


def attach_forecasts(games):
    """wind (mph) forecast ~24h ahead, mean over kickoff hour + next 2."""
    need = {}
    for g in games:
        if g["outdoor"] and g["st"]:
            need.setdefault(g["sid"], []).append(g)
    for sid, gs in sorted(need.items()):
        st = gs[0]["st"]
        a = min(g["gameday"] for g in gs); b = max(g["gameday"] for g in gs)
        url = (f"{FCST_URL}?latitude={st['lat']}&longitude={st['lon']}&start_date={a}&end_date={b}"
               "&hourly=wind_speed_10m_previous_day1&wind_speed_unit=mph&timezone=America/New_York")
        h = json.loads(fetch(url))["hourly"]
        byt = dict(zip(h["time"], h["wind_speed_10m_previous_day1"]))
        for g in gs:
            hh = int(g["gametime"].split(":")[0])
            xs = [byt.get(f"{g['gameday']}T{k:02d}:00") for k in range(hh, hh + 3)]
            xs = [x for x in xs if x is not None]
            g["wind"] = sum(xs) / len(xs) if xs else None
        time.sleep(0.3)
    for g in games:
        if not g["outdoor"]:
            g["wind"] = 0.0
        g.setdefault("wind", None)


# ── Vault's pregame pass_yd projection (mirror prop-model.js projectFrom) ────
def wmean(vals, hl):
    n = len(vals); acc = sw = 0.0
    for i, v in enumerate(vals):
        w = 0.5 ** (((n - 1) - i) / hl); acc += w * v; sw += w
    return (acc / sw if sw else None), sw


def shrink(vals, prior, hl, k):
    wm, sw = wmean(vals, hl)
    return prior if wm is None else (sw * wm + k * prior) / (sw + k)


def pregame_proj(prior_weeks, m, min_prior):
    vs = [w["att"] for w in prior_weeks if w.get("att") is not None]
    es = [w["pyds"] / w["att"] for w in prior_weeks if w.get("att") and w.get("pyds") is not None]
    if len(vs) < min_prior or len(es) < min_prior:
        return None
    pv = shrink(vs, m["prior"][MARKET + "|vol"], m["half_life"], m["k_vol"])
    pe = shrink(es, m["prior"][MARKET + "|eff"], m["half_life"], m["k_eff"])
    return pv * pe


def build_rows(games):
    P = json.load(open(os.path.join(DATA, "prop_model.json")))
    m = P["markets"][MARKET]; min_prior = (P.get("meta") or {}).get("min_prior", 3)
    gidx = {}
    for g in games:
        gidx[(g["season"], g["week"], g["home"])] = (g, True)
        gidx[(g["season"], g["week"], g["away"])] = (g, False)
    # per-player chronological weeks across seasons (prev season feeds the prior)
    hist = {}
    for s in [SEASONS[0] - 1] + SEASONS:
        path = os.path.join(DATA, f"nflverse_stats_{s}.json")
        if not os.path.exists(path):
            continue
        for name, p in json.load(open(path)).items():
            if p.get("pos") != "QB":
                continue
            for w in p.get("weeks") or []:
                hist.setdefault(name, []).append(dict(w, season=s))
    rows = []
    for name, weeks in hist.items():
        weeks.sort(key=lambda w: (w["season"], w.get("wk") or 0))
        for i, w in enumerate(weeks):
            if w["season"] not in SEASONS or (w.get("att") or 0) < MIN_ATT or w.get("pyds") is None:
                continue
            opp = norm_team(w.get("opp"))
            hit = gidx.get((w["season"], w.get("wk"), opp))
            if not hit:
                continue
            g, opp_is_home = hit
            if g["wind"] is None:
                continue
            proj = pregame_proj(weeks[:i], m, min_prior)
            if not proj or proj <= 0:
                continue
            # team implied total from the close (nflverse spread_line > 0 = home favored)
            team_home = not opp_is_home
            tt = g["total_line"] / 2 + (g["spread_line"] / 2 if team_home else -g["spread_line"] / 2)
            rows.append(dict(season=w["season"], wind=g["wind"], y=w["pyds"] / proj - 1,
                             yds=w["pyds"], proj=proj, tt=tt, outdoor=g["outdoor"]))
    return rows


# ── fit: y = a + c·(tt/avg − 1) + b·max(0, wind − knot) ──────────────────────
def solve(X, y):
    k = len(X[0]); A = [[0.0] * k for _ in range(k)]; v = [0.0] * k
    for xi, yi in zip(X, y):
        for p in range(k):
            v[p] += xi[p] * yi
            for q in range(k):
                A[p][q] += xi[p] * xi[q]
    for c in range(k):                                   # Gauss-Jordan
        piv = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[piv] = A[piv], A[c]; v[c], v[piv] = v[piv], v[c]
        for r in range(k):
            if r != c and A[c][c]:
                f = A[r][c] / A[c][c]
                A[r] = [a - f * b for a, b in zip(A[r], A[c])]; v[r] -= f * v[c]
    return [v[i] / A[i][i] for i in range(k)]


def design(rows, knot, tt_avg, with_wind=True):
    X = []
    for r in rows:
        x = [1.0, r["tt"] / tt_avg - 1]
        if with_wind:
            x.append(max(0.0, r["wind"] - knot))
        X.append(x)
    return X


def fit(rows, knot, tt_avg):
    return solve(design(rows, knot, tt_avg), [r["y"] for r in rows])


def mult(b, knot, wind):
    return max(FLOOR, min(1.0, 1 + b * max(0.0, wind - knot)))


def holdout_mse(train, test, knot, tt_avg):
    """Yards MSE on the test season: control-only model vs control + wind.
    The wind variant applies exactly the deployed clamp."""
    base = solve(design(train, knot, tt_avg, False), [r["y"] for r in train])
    full = fit(train, knot, tt_avg)
    e0 = e1 = 0.0
    for r in test:
        ctrl0 = 1 + base[0] + base[1] * (r["tt"] / tt_avg - 1)
        ctrl1 = 1 + full[0] + full[1] * (r["tt"] / tt_avg - 1)
        e0 += (r["yds"] - r["proj"] * ctrl0) ** 2
        e1 += (r["yds"] - r["proj"] * ctrl1 * mult(full[2], knot, r["wind"])) ** 2
    return e0 / len(test), e1 / len(test), full[2]


def main():
    print("loading games …"); games = load_games()
    print("fetching archived day-1 forecasts …"); attach_forecasts(games)
    rows = build_rows(games)
    out_rows = [r for r in rows if r["outdoor"]]
    tt_avg = sum(r["tt"] for r in rows) / len(rows)
    print(f"{len(rows)} QB starts ({len(out_rows)} outdoor)")

    # knot: pooled SSE on all rows (dome rows sit at wind 0 and anchor the intercept)
    best = None
    for knot in KNOT_GRID:
        b = fit(rows, knot, tt_avg)
        sse = sum((r["y"] - (b[0] + b[1] * (r["tt"] / tt_avg - 1) + b[2] * max(0, r["wind"] - knot))) ** 2 for r in rows)
        print(f"  knot {knot:>2}: slope {b[2]:+.4f}/mph  sse {sse:.3f}")
        if best is None or sse < best[0]:
            best = (sse, knot, b)
    _, knot, b = best

    folds, ok = [], True
    for fs, ts in FOLDS:
        tr = [r for r in rows if r["season"] == fs]; te = [r for r in rows if r["season"] == ts]
        m0, m1, bf = holdout_mse(tr, te, knot, tt_avg)
        te_w = [r for r in te if r["wind"] > knot]
        folds.append(dict(fit=fs, test=ts, n_test=len(te), n_test_windy=len(te_w), slope=round(bf, 5),
                          rmse_no_wind=round(m0 ** .5, 2), rmse_wind=round(m1 ** .5, 2)))
        ok = ok and m1 < m0 and bf < 0
        print(f"  fold fit {fs} → test {ts}: slope {bf:+.4f}  RMSE {m0 ** .5:.2f} → {m1 ** .5:.2f}")

    # what it does in yards, for the explainer
    avg_proj = sum(r["proj"] for r in out_rows) / len(out_rows)
    table = {str(w): round(mult(b[2], knot, w), 4) for w in (5, 10, 15, 20, 25)}
    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "active": bool(ok),
        "markets": [MARKET],
        "knot_mph": knot,
        "slope_per_mph": round(b[2], 5),
        "floor": FLOOR,
        "mult_at_mph": table,
        "yds_per_mph_at_avg_proj": round(b[2] * avg_proj, 2),
        "n": len(rows), "n_outdoor": len(out_rows), "seasons": SEASONS,
        "folds": folds,
        "source": ("Open-Meteo previous-runs wind_speed_10m_previous_day1 (kickoff + 2h mean) × "
                   "Vault pregame pass_yd projection (prop_model.json priors) vs nflverse actuals; "
                   "control = closing team implied total (games.csv)"),
        "form": "windMult = clamp(1 + slope_per_mph * max(0, wind_mph - knot_mph), floor, 1); outdoor/open roof only",
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("active", "knot_mph", "slope_per_mph", "mult_at_mph", "yds_per_mph_at_avg_proj")}))


if __name__ == "__main__":
    main()
