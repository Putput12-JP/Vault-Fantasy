"""Free-data loaders for the NFL joint-sim prototype (nflverse GitHub release CSVs only).

Raw files are cached outside the repo (NFL_SIM_CACHE, default /tmp/nfl_sim_cache) and parsed with pandas.
No sportsbook data is read here: scores come from nflverse games.csv (the `spread_line` / `total_line` /
moneyline columns are dropped on load so they cannot leak into a projection).
"""
import os, subprocess, pickle
import numpy as np
import pandas as pd

CACHE = os.environ.get("NFL_SIM_CACHE", "/tmp/nfl_sim_cache")
REL = "https://github.com/nflverse/nflverse-data/releases/download"
SEASONS = (2022, 2023, 2024, 2025, 2026)


def _fetch(rel_path, name):
    os.makedirs(CACHE, exist_ok=True)
    dst = os.path.join(CACHE, name)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        subprocess.run(["curl", "-sfL", "-o", dst, f"{REL}/{rel_path}"], check=True)
    return dst


def _fetch_raw(url, name):
    os.makedirs(CACHE, exist_ok=True)
    dst = os.path.join(CACHE, name)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        subprocess.run(["curl", "-sfL", "-o", dst, url], check=True)
    return dst


PBP_COLS = ["game_id", "season", "week", "season_type", "posteam", "defteam", "play_type", "pass_attempt", "sack",
            "rush_attempt", "qb_kneel", "qb_spike", "qb_scramble", "complete_pass", "yards_gained",
            "receiver_player_id", "rusher_player_id", "two_point_attempt"]


def load_pbp(season):
    p = _fetch(f"pbp/play_by_play_{season}.csv.gz", f"pbp_{season}.csv.gz")
    d = pd.read_csv(p, usecols=PBP_COLS, low_memory=False)
    return d[d.season_type == "REG"]


def team_games(seasons=SEASONS):
    """One row per team-game: plays, dropbacks, attempts, sacks, carries (regular season, scrimmage plays only)."""
    out = []
    for s in seasons:
        d = load_pbp(s)
        d = d[(d.play_type.isin(["pass", "run"])) & (d.qb_kneel != 1) & (d.qb_spike != 1) & d.posteam.notna()]
        d = d[d.two_point_attempt != 1]
        g = d.groupby(["season", "week", "game_id", "posteam", "defteam"]).agg(
            plays=("play_type", "size"), att=("pass_attempt", "sum"), sacks=("sack", "sum"),
            carries=("rush_attempt", "sum")).reset_index().rename(columns={"posteam": "team", "defteam": "opp"})
        # nflverse `pass_attempt` already includes sack plays: dropbacks = that flag, attempts exclude the sacks
        g["dropbacks"] = g.att
        g["att"] = g.att - g.sacks
        out.append(g)
    return pd.concat(out, ignore_index=True)


def games(seasons=SEASONS):
    p = _fetch_raw("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv", "games.csv")
    g = pd.read_csv(p)
    g = g[(g.game_type == "REG") & g.season.isin(seasons)]
    return g[["game_id", "season", "week", "away_team", "away_score", "home_team", "home_score"]].copy()


def yardage_shape(before_season):
    """Per-event yardage mean and sd measured on pbp strictly before `before_season` (no test-period peeking).
    Returns gamma shape k = (mean/sd)^2 for catches and for carries (QB vs non-QB handled by caller via position).
    """
    pos = pd.read_csv(_fetch_raw("https://github.com/nflverse/nflverse-data/releases/download/players/players.csv",
                                 "players.csv"), usecols=["gsis_id", "position"]).set_index("gsis_id").position
    rows = []
    for s in [x for x in SEASONS if x < before_season]:
        d = load_pbp(s)
        rows.append(d[["complete_pass", "rush_attempt", "yards_gained", "receiver_player_id", "rusher_player_id",
                       "play_type", "sack"]])
    d = pd.concat(rows)
    rec = d[(d.complete_pass == 1)]
    rec = rec.assign(pos=rec.receiver_player_id.map(pos))
    run = d[(d.rush_attempt == 1) & (d.play_type == "run")]
    run = run.assign(pos=run.rusher_player_id.map(pos))
    shape = {}
    for k, df, key in (("rec", rec, "pos"), ("run", run, "pos")):
        for p in ("WR", "TE", "RB", "QB"):
            x = df[df[key] == p].yards_gained
            if len(x) > 200:
                shape[f"{k}_{p}"] = dict(mean=float(x.mean()), sd=float(x.std()), n=int(len(x)))
    return shape


def player_weeks(seasons=SEASONS):
    out = []
    for s in seasons:
        p = _fetch(f"stats_player/stats_player_week_{s}.csv", f"stats_{s}.csv")
        d = pd.read_csv(p, low_memory=False)
        d = d[d.season_type == "REG"]
        out.append(d[["player_id", "player_display_name", "position", "season", "week", "team", "opponent_team",
                      "completions", "attempts", "passing_yards", "carries", "rushing_yards", "receptions", "targets",
                      "receiving_yards"]])
    d = pd.concat(out, ignore_index=True).rename(columns={"player_id": "gsis", "player_display_name": "name",
                                                         "position": "pos", "opponent_team": "opp"})
    return d


def snaps(seasons=SEASONS):
    """(season, week, team, gsis) for every player with an offensive snap; pfr_id mapped to gsis via players.csv."""
    pl = pd.read_csv(_fetch_raw("https://github.com/nflverse/nflverse-data/releases/download/players/players.csv",
                                "players.csv"), usecols=["gsis_id", "pfr_id"]).dropna()
    m = dict(zip(pl.pfr_id, pl.gsis_id))
    out = []
    for s in seasons:
        d = pd.read_csv(_fetch(f"snap_counts/snap_counts_{s}.csv", f"snaps_{s}.csv"))
        d = d[(d.game_type == "REG") & (d.offense_snaps > 0)]
        d = d.assign(gsis=d.pfr_player_id.map(m)).dropna(subset=["gsis"])
        out.append(d[["season", "week", "team", "gsis", "offense_pct"]])
    return pd.concat(out, ignore_index=True)


def injuries(seasons=SEASONS):
    out = []
    for s in seasons:
        d = pd.read_csv(_fetch(f"injuries/injuries_{s}.csv", f"inj_{s}.csv"))
        d = d[d.game_type == "REG"]
        out.append(d[["season", "week", "team", "gsis_id", "report_status"]])
    return pd.concat(out, ignore_index=True)


def id_map():
    p = pd.read_csv(_fetch_raw("https://github.com/nflverse/nflverse-data/releases/download/players/players.csv",
                               "players.csv"), usecols=["gsis_id", "espn_id", "display_name", "position"])
    return p


def roster_ids(season):
    d = pd.read_csv(_fetch(f"rosters/roster_{season}.csv", f"roster_{season}.csv"), usecols=["gsis_id", "sleeper_id"])
    return d
