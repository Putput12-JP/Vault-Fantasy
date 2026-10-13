"""Unify the stored prop lines (ESPN BET 2024-25 open/close, Vault ledger 2026 open/close) into one table of
props on the four modelled markets, joined to nflverse box scores for settlement. Reads only repo data files and
nflverse; produces no projections."""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data")
MARKETS = ("rec_yd", "rush_yd", "rec", "pass_yd")
COL = {"rec_yd": "receiving_yards", "rush_yd": "rushing_yards", "rec": "receptions", "pass_yd": "passing_yards"}


def build(pw, idm, roster26):
    pwi = pw.set_index(["season", "week", "gsis"])
    team_of = pw.set_index(["season", "week", "gsis"]).team.to_dict()
    rows = []
    # ---- ESPN BET 2024-25: open and close both present ----
    e2g = {}
    for e, g in zip(idm.espn_id, idm.gsis_id):
        if pd.notna(e) and pd.notna(g):
            e2g[str(int(e))] = g
    for yr in (2024, 2025):
        d = json.load(open(os.path.join(DATA, f"espn_prop_lines_{yr}.json")))
        for gid, ath, mkt, lo, oo, uo, lc, oc, uc in d["rows"]:
            if mkt not in MARKETS:
                continue
            s, w = int(gid[:4]), int(gid[5:7])
            g = e2g.get(str(ath))
            if not g:
                rows.append(dict(src="espn", season=s, week=w, gsis=None, market=mkt)); continue
            rows.append(dict(src="espn", season=s, week=w, gsis=g, market=mkt, line_o=lo, over_o=oo, under_o=uo,
                             line_c=lc, over_c=oc, under_c=uc))
    # ---- Vault ledger 2026 ----
    br = json.load(open(os.path.join(DATA, "bet_results.json")))["props"]
    s2g = {str(int(a)): g for a, g in zip(roster26.sleeper_id, roster26.gsis_id) if pd.notna(a) and pd.notna(g)}
    name2g = {}
    for (s, w, g), r in pwi.iterrows():
        if s == 2026:
            name2g[(r["name"], r["team"])] = g
    for x in br:
        if x["market"] not in MARKETS:
            continue
        g = s2g.get(str(x["pid"])) or name2g.get((x["name"], x["team"]))
        if not g:
            rows.append(dict(src="vault26", season=int(x["season"]), week=x["week"], gsis=None, market=x["market"])); continue
        p_over = None
        if x.get("p_model") is not None:
            p_over = x["p_model"] if x["side"] == "over" else 1 - x["p_model"]
        rows.append(dict(src="vault26", season=int(x["season"]), week=x["week"], gsis=g, market=x["market"],
                         line_o=x["line_open"], over_o=x["open_over"], under_o=x["open_under"], line_c=x["line_close"],
                         over_c=x["close_over"], under_c=x["close_under"], vault_p_over=p_over,
                         vault_proj=x.get("proj"), vault_grade=x.get("grade")))
    df = pd.DataFrame(rows)
    df["mapped"] = df.gsis.notna()
    # settle
    act, team, opp = [], [], []
    for r in df.itertuples():
        if r.gsis is None or (r.season, r.week, r.gsis) not in pwi.index:
            act.append(np.nan); team.append(None); opp.append(None); continue
        row = pwi.loc[(r.season, r.week, r.gsis)]
        act.append(float(row[COL[r.market]])); team.append(row["team"]); opp.append(row["opp"])
    df["actual"], df["team"], df["opp"] = act, team, opp
    return df
