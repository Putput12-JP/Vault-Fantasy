#!/usr/bin/env python3
"""v2 preseason prior: does a regression on talent, returning production, recruiting and portal movement (CollegeFootballData,
all known BEFORE the season) beat v1's "last season's rating x 0.85"?  Same protocol as cfb_efficiency_study.py: the feature set is fixed
up front, each season's prior is fit only on EARLIER seasons, and 2024-2025 are read once.

  python3 scripts/cfb_v2_prior_study.py      # needs data/cfbd/ (workflow: Fetch CFBD data) and the sportsdataverse downloads
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfbd')
ld = lambda n, y: json.load(open(f'{D}/{n}_{y}.json'))
K = st.K


def team_ids(y):
    return {t['school']: t['id'] for t in ld('teams_fbs', y)}


def features(y, prev, teams):
    """one row per ESPN/CFBD team id, using only what was known before season y kicked off"""
    ids = team_ids(y); rows = {}
    tal = {ids.get(r['team']): r['talent'] for r in ld('talent', y) if r['team'] in ids}
    ret = {ids.get(r['team']): r for r in ld('returning', y) if r['team'] in ids}
    rec = {}
    for yy in range(y - 3, y + 1):      # four classes of recruiting points, the current signing class included (signed in Dec/Feb, before the season)
        try:
            for r in ld('recruiting_teams', yy):
                if r['team'] in ids: rec[ids[r['team']]] = rec.get(ids[r['team']], 0) + r['points']
        except FileNotFoundError: pass
    pin, pout = {}, {}
    for r in ld('portal', y):
        if r['destination'] in ids: pin[ids[r['destination']]] = pin.get(ids[r['destination']], 0) + (r['stars'] or 2.5)
        if r['origin'] in ids: pout[ids[r['origin']]] = pout.get(ids[r['origin']], 0) + (r['stars'] or 2.5)
    df = pd.DataFrame({'team': sorted(teams)})
    df['prev_o'] = df.team.map(lambda t: prev[0].get(t, 0.0)); df['prev_d'] = df.team.map(lambda t: prev[1].get(t, 0.0))
    df['talent'] = df.team.map(tal); df['rec'] = df.team.map(rec)
    df['ret_ppa'] = df.team.map(lambda t: ret[t]['percentPPA'] if t in ret else np.nan)
    df['ret_pass'] = df.team.map(lambda t: ret[t]['percentPassingPPA'] if t in ret else np.nan)
    df['portal_net'] = df.team.map(lambda t: pin.get(t, 0.0) - pout.get(t, 0.0))
    for c in ('talent', 'rec', 'ret_ppa', 'ret_pass', 'portal_net'):
        df[c] = df[c].fillna(df[c].median()); df[c] = (df[c] - df[c].mean()) / (df[c].std() or 1)
    df['year'] = y
    return df


FEATS = ['prev_o', 'prev_d', 'talent', 'rec', 'ret_ppa', 'ret_pass', 'portal_net']


def ridge(X, y, lam):
    X = np.c_[np.ones(len(X)), X]; I = np.eye(X.shape[1]) * lam; I[0, 0] = 0
    return np.linalg.solve(X.T @ X + I, X.T @ y)


def main():
    d = '/tmp/cfbstudy'; os.makedirs(d, exist_ok=True)
    tg, gm = st.load(d); fbs = st.fbs_sets(gm, d)
    finals = {}; v1 = st.walk_forward(tg, gm, fbs, finals=finals)            # v1, plus each season's end-of-season ratings (the targets)
    tab = {}
    for y in range(2022, 2026):
        prev = finals[y - 1]; tab[y] = features(y, prev, fbs[y])
        tab[y]['t_o'] = tab[y].team.map(lambda t: finals[y][0].get(t, 0.0)); tab[y]['t_d'] = tab[y].team.map(lambda t: finals[y][1].get(t, 0.0))
    LAM = 10.0
    coefs = {}

    def prior_fn(y, _):
        train = pd.concat([tab[k] for k in range(2022, y)]) if y > 2022 else None
        if train is None: return ({}, {})          # 2022 has nothing earlier to learn from, so it opens flat
        X = train[FEATS].values
        bo, bd = ridge(X, train.t_o.values, LAM), ridge(X, train.t_d.values, LAM); coefs[y] = (bo, bd)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))

    v2 = st.walk_forward(tg, gm, fbs, prior_fn=prior_fn)
    for lab, r in (('v1 (last season x 0.85)', v1), ('v2 (regression prior)', v2)):
        print('\n=====', lab)
        for ys, name in (([2023], 'tune 2023 (2022 only to learn from)'), ([2024, 2025], 'TEST 2024-2025')):
            st.report(r[r.season.isin(ys)], name, 4)
        for y in (2023, 2024, 2025):
            q = r[(r.season == y) & (r.week >= 4)].dropna(subset=['mkt']); e = q.pred - q.mkt; c = q.hm - q.mkt
            b = (e.abs() >= 5) & (c != 0); w = int(((c[b] * np.sign(e[b])) > 0).sum()); print(f'   {y}: 5+ pt picks {w}-{int(b.sum()) - w}')
    print('\ncoefficients (offense | defense) by season, features:', FEATS)
    for y, (bo, bd) in coefs.items(): print(y, np.round(bo, 2), np.round(bd, 2))
    # does the model add anything beyond the market? weight on (pred - market) when predicting the final margin, weeks 4+
    for lab, r in (('v1', v1), ('v2', v2)):
        q = r[(r.season.isin([2024, 2025])) & (r.week >= 4)].dropna(subset=['mkt']); q = q.assign(edge=q.pred - q.mkt)
        X = np.c_[np.ones(len(q)), q.mkt, q.edge]; b = np.linalg.lstsq(X, q.hm, rcond=None)[0]
        print(f'{lab}: final margin ~ market + w*(model-market), 2024-25: w = {b[2]:.3f}; miss market {np.abs(q.hm-q.mkt).mean():.3f} model {np.abs(q.hm-q.pred).mean():.3f}')


if __name__ == '__main__':
    main()
