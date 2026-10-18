#!/usr/bin/env python3
"""Rebuild the walk-forward rows for the CURRENT CFB model (v2 prior + special teams, K 70, HFA 2.5), 2022-2025, so a candidate change can be tested on the same rows.

Seasons 2022-2025 plus the 2026 season to date (the live model, replayed week by week with only earlier games, so 2026 is an out-of-sample read).
Writes <dir>/base_rows.csv: game_id, season, week, hm (home margin), mkt (ESPN close, home margin convention of the pbp), v1, v2, gap (special teams gap), v2st (the live number).
Needs only the sportsdataverse parquet files (downloaded into --dir). Run: python3 scripts/cfb_week7_base_rows.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
import cfb_v2_st_study as sts

LAM, CARRY, WEIGHT = sts.LAM, sts.CARRY, sts.WEIGHT


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    ALL = [2021, 2022, 2023, 2024, 2025, 2026]; YEARS = [2022, 2023, 2024, 2025, 2026]
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL)
    # the 5-games-vs-FBS rule needs a finished season; mid-season 2026 uses the CollegeFootballData FBS list instead (as the live model does)
    fbs[2026] = {t['id'] for t in json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfbd', 'teams_fbs_2026.json')))}
    finals = {}; v1 = st.walk_forward(tg, gm, fbs, years=ALL, finals=finals)
    tab = {}
    for y in YEARS:
        tab[y] = v2.features(y, finals[y - 1], fbs[y])
        tab[y]['t_o'] = tab[y].team.map(lambda t: finals[y][0].get(t, 0.0)); tab[y]['t_d'] = tab[y].team.map(lambda t: finals[y][1].get(t, 0.0))

    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    v2r = st.walk_forward(tg, gm, fbs, years=ALL, prior_fn=prior_fn)
    order = [o for o in sts.game_order(gm, fbs, ALL) if o[0] in YEARS]; ids = [o[1] for o in order]
    v1 = v1[v1.season.isin(YEARS)].reset_index(drop=True); v2r = v2r[v2r.season.isin(YEARS)].reset_index(drop=True)
    assert len(ids) == len(v1) == len(v2r)
    df = pd.DataFrame(dict(game_id=ids, season=v1.season, week=v1.week, hm=v1.hm, mkt=v1.mkt, v1=v1.pred, v2=v2r.pred,
                           home_id=[o[2] for o in order], away_id=[o[3] for o in order], neutral=[o[4] for o in order]))
    sts.order_weeks = dict(zip(df.game_id, df.week)); stg = sts.st_games(a.dir, YEARS)
    gap = sts.st_walk(order, stg, YEARS, LAM, CARRY); df['gap'] = df.game_id.map(gap).fillna(0.0); df['v2st'] = df.v2 + WEIGHT * df.gap
    df.to_csv(os.path.join(a.dir, 'base_rows.csv'), index=False); print(len(df), 'rows ->', a.dir)


if __name__ == '__main__':
    main()
