"""Walk-forward week runner: build State once per process, simulate a week with data strictly before it."""
import zlib
import numpy as np
import pandas as pd
import data, model

_ST = None
N_SIMS = 10000
MIN_ACT = 2   # games played for the team in its last 8 (else the player is not covered)
KAPPA = 50.0     # tuned on 2023 weeks 8-12 only (scripts/nfl_sim/tune.py); best at the edge of the grid
SIGMA_TE = 0.06
STAT = {"rec_yd": "rec_yd", "rush_yd": "rush_yd", "rec": "rec", "pass_yd": "pass_yd"}


def get_state(shapes_before=2024):
    global _ST
    if _ST is None:
        _ST = model.State(data.team_games(), data.player_weeks(), data.snaps(), data.injuries(), data.games(),
                          data.yardage_shape(shapes_before))
    return _ST


def p_over(arr, line):
    return float((arr > line).mean() + 0.5 * (arr == line).mean())


def run_week(args):
    """args = (season, week, props_df_rows(list of dict), kappa, sigma_te, n). Returns (prop rows w/ p, game rows)."""
    season, week, rows, kappa, sigma_te, n = args
    st = get_state()
    before = (season, week)
    prm = st.fit_game_params(before)
    g = st.tg[(st.tg.season == season) & (st.tg.week == week)]
    sims = {}
    games = []
    done = set()
    for r in g.itertuples():
        if r.game_id in done:
            continue
        done.add(r.game_id)
        row = st.tg[(st.tg.game_id == r.game_id)]
        home = row[row.home == 1].team.iloc[0]
        away = row[row.home == 0].team.iloc[0]
        want = {x["gsis"] for x in rows if x["team"] in (home, away)}
        if not want:
            continue
        seed = zlib.crc32(f"{season}-{week}-{r.game_id}".encode())   # stable across runs (str hash() is salted)
        res = model.simulate_game(st, away, home, before, n=n, seed=seed, params=prm, kappa=kappa, sigma_te=sigma_te)
        if res is None:
            continue
        sims[home], sims[away] = res[home], res[away]
        # QB passing yards vs top WR receiving yards correlation, per team
        for team in (home, away):
            tm = res[team]
            qbs = [(k, v) for k, v in tm.items() if k != "_team_pass_yd" and "pass_yd" in v]
            wrs = [(k, v) for k, v in tm.items() if k != "_team_pass_yd" and v["pos"] == "WR"]
            if qbs and wrs:
                qb = max(qbs, key=lambda kv: kv[1]["pass_yd"].mean())
                wr1 = max(wrs, key=lambda kv: kv[1]["rec_yd"].mean())
                wr2 = sorted(wrs, key=lambda kv: -kv[1]["rec_yd"].mean())[1] if len(wrs) > 1 else None
                games.append(dict(season=season, week=week, team=team, qb=qb[0], wr1=wr1[0],
                                  corr_qb_wr1=float(np.corrcoef(qb[1]["pass_yd"], wr1[1]["rec_yd"])[0, 1]),
                                  corr_qb_wr2=float(np.corrcoef(qb[1]["pass_yd"], wr2[1]["rec_yd"])[0, 1]) if wr2 else None,
                                  corr_wr1_wr2=float(np.corrcoef(wr1[1]["rec_yd"], wr2[1]["rec_yd"])[0, 1]) if wr2 else None,
                                  team_pass_mean=float(tm["_team_pass_yd"].mean()), team_pass_sd=float(tm["_team_pass_yd"].std())))
    out = []
    for x in rows:
        tm = sims.get(x["team"])
        if tm is None or x["gsis"] not in tm or STAT[x["market"]] not in tm[x["gsis"]]:
            continue
        if tm[x["gsis"]]["n_act"] < MIN_ACT:      # no real role history: the model has no view, so no projection
            continue
        arr = tm[x["gsis"]][STAT[x["market"]]]
        y = dict(x)
        y["sim_mean"] = float(arr.mean())
        y["sim_sd"] = float(arr.std())
        y["p_o"] = p_over(arr, x["line_o"]) if pd.notna(x["line_o"]) else None
        y["p_c"] = p_over(arr, x["line_c"]) if pd.notna(x["line_c"]) else None
        qs = np.quantile(arr, [0.1, 0.9])
        y["q10"], y["q90"] = float(qs[0]), float(qs[1])
        y["rank_pit"] = None if pd.isna(x.get("actual")) else float((arr < x["actual"]).mean() + 0.5 * (arr == x["actual"]).mean())
        out.append(y)
    return out, games
