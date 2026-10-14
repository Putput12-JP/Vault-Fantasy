#!/usr/bin/env python3
"""CFB model: v1 vs v2 (regression preseason prior) vs v2 + a special-teams rating, walk-forward 2022-2025.

JP+ publishes a separate special teams rating (about +/-3 points) next to offense and defense. This adds one the same
way the others are built, from play-by-play, and asks whether it moves the model's miss and its picks. Rule set up before
the run: lambda / weight / carry are chosen on 2022-2023 by the MISS only (never by pick record); 2024-2025 is read once.

  Special teams value  every punt, kickoff and field goal has an EPA from the receiving/possessing team's side (EPA_punt,
                       EPA_kickoff, EPA_fg). A team's special teams net for a game = its EPA on those plays minus the
                       opponent's. One number per game, in points.
  Rating               ridge on (home net) ~ r_home - r_away, centred on last season's final rating x CARRY, refit each
                       week using only EARLIER games, added to the margin as WEIGHT x (r_home - r_away).
  Grading              5+ point disagreements, weeks 4+, against the ESPN close (pbp homeTeamSpread) and against the
                       opening spread (ESPN core API, DraftKings; data fetched by --opens).

Run: python3 scripts/cfb_v2_st_study.py [--dir /tmp/cfbstudy] [--opens /tmp/cfbstudy/opens_hist.json]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2

ST_COLS = ['season', 'game_id', 'week', 'seasonType', 'pos_team_id', 'def_pos_team_id', 'EPA', 'EPA_punt', 'EPA_kickoff', 'EPA_fg']


def st_games(d, years):
    """one row per game: st_home = special teams net EPA (points) from the home side"""
    out = []
    for y in years:
        p = pd.read_parquet(f'{d}/pbp_{y}.parquet', columns=ST_COLS + ['homeTeamId'])
        p = p[p.seasonType == 2]
        v = p[['EPA_punt', 'EPA_kickoff', 'EPA_fg']].bfill(axis=1).iloc[:, 0]        # a play has at most one of the three
        p = p.assign(v=v.clip(-3, 3)).dropna(subset=['v'])
        p['home_side'] = np.where(p.pos_team_id == p.homeTeamId, 1, -1)
        g = p.assign(h=p.v * p.home_side).groupby('game_id').agg(st_home=('h', 'sum'), plays=('h', 'size')).reset_index()
        g['season'] = y; out.append(g)
    return pd.concat(out)


def game_order(gm, fbs, years):
    """game ids in the exact order st.walk_forward emits its rows"""
    ids = []
    for y in years:
        F = fbs[y]; G = gm[(gm.season == y) & gm.homeTeamId.isin(F) & gm.awayTeamId.isin(F) & (gm.status_type_completed == True)]
        for w in range(1, 17):
            ids += [(y, int(r.game_id), int(r.homeTeamId), int(r.awayTeamId), r.neutral_site == True) for r in G[G.week == w].itertuples()]
    return ids


def st_ratings(obs, prior, lam):
    """ridge team ratings centred on the prior; obs has home_id, away_id, st_home"""
    if len(obs) < 30: return dict(prior)
    teams = sorted(set(obs.home_id) | set(obs.away_id)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    X = np.zeros((len(obs), n)); X[np.arange(len(obs)), obs.home_id.map(ix).values] = 1; X[np.arange(len(obs)), obs.away_id.map(ix).values] = -1
    p0 = np.array([prior.get(t, 0.0) for t in teams]); y = obs.st_home.values - X @ p0
    r = p0 + np.linalg.solve(X.T @ X + lam * np.eye(n), X.T @ y)
    return {t: float(r[i]) for i, t in enumerate(teams)}


def st_walk(order, stg, years, lam, carry):
    """per-game special teams rating gap (home minus away), walk-forward; also returns final ratings per season"""
    sg = stg.set_index('game_id').st_home.to_dict(); wk = {gid: w for gid, w in order_weeks.items()}
    gap = {}; prior = {}
    for y in years:
        rows = [(gid, h, a, sg.get(gid)) for (yy, gid, h, a, n) in order if yy == y]
        df = pd.DataFrame(rows, columns=['game_id', 'home_id', 'away_id', 'st_home']); df['week'] = df.game_id.map(wk); df = df.dropna(subset=['st_home'])
        cur = dict(prior)
        for w in range(1, 17):
            cur = st_ratings(df[df.week < w], prior, lam) if (df.week < w).sum() >= 30 else dict(prior)
            for gid, h, a, _ in [r for r in rows if wk[r[0]] == w]: gap[gid] = cur.get(h, 0.0) - cur.get(a, 0.0)
        prior = {t: carry * v for t, v in cur.items()}
    return gap


def picks(df, col, base_col, th=5.0, minweek=4):
    q = df[(df.week >= minweek)].dropna(subset=[base_col]); e = q[col] - q[base_col]; c = q.hm - q[base_col]
    b = (e.abs() >= th) & (c != 0); w = int(((c[b] * np.sign(e[b])) > 0).sum()); return w, int(b.sum()) - w


def main():
    global order_weeks
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); ap.add_argument('--opens', default='/tmp/cfbstudy/opens_hist.json'); a = ap.parse_args()
    tg, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir); YEARS = [2022, 2023, 2024, 2025]
    finals = {}; v1 = st.walk_forward(tg, gm, fbs, finals=finals)
    tab = {}
    for y in YEARS:
        tab[y] = v2.features(y, finals[y - 1], fbs[y])
        tab[y]['t_o'] = tab[y].team.map(lambda t: finals[y][0].get(t, 0.0)); tab[y]['t_d'] = tab[y].team.map(lambda t: finals[y][1].get(t, 0.0))

    def prior_fn(y, _):
        if y == 2021: return ({}, {})
        if y == 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]) if y > 2022 else None
        if train is None: return ({}, {})
        X = train[v2.FEATS].values; bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    v2r = st.walk_forward(tg, gm, fbs, prior_fn=prior_fn)
    order = game_order(gm, fbs, st.YEARS)
    order = [o for o in order if o[0] in YEARS]
    ids = [o[1] for o in order]
    v1 = v1[v1.season.isin(YEARS)].reset_index(drop=True); v2r = v2r[v2r.season.isin(YEARS)].reset_index(drop=True)
    assert len(ids) == len(v1) == len(v2r), (len(ids), len(v1), len(v2r))
    df = pd.DataFrame(dict(game_id=ids, season=v1.season, week=v1.week, hm=v1.hm, mkt=v1.mkt, v1=v1.pred, v2=v2r.pred))
    op = json.load(open(a.opens)); df['open'] = df.game_id.map(lambda i: -op[str(i)]['so'] if op.get(str(i)) and op[str(i)]['so'] is not None else np.nan)
    stg = st_games(a.dir, YEARS); order_weeks = dict(zip(df.game_id, df.week))
    tune = df.season.isin([2022, 2023])
    best = None
    print('special teams: tuning on 2022-2023 by MISS (v2 base)')
    print(' lam carry  weight   miss(v2+ST)   [v2 alone %.3f]' % np.abs(df[tune].hm - df[tune].v2).mean())
    for lam in (5, 15, 40):
        for carry in (0.3, 0.6):
            gap = st_walk(order, stg, YEARS, lam, carry); df['gap'] = df.game_id.map(gap).fillna(0.0)
            for wt in (0.5, 1.0, 1.5, 2.0):
                m = np.abs(df[tune].hm - (df[tune].v2 + wt * df[tune].gap)).mean(); print(f' {lam:3d} {carry:4.1f}  {wt:4.1f}   {m:.3f}')
                if best is None or m < best[0]: best = (m, lam, carry, wt)
    _, lam, carry, wt = best; print('chosen on 2022-23:', 'lam', lam, 'carry', carry, 'weight', wt)
    gap = st_walk(order, stg, YEARS, lam, carry); df['gap'] = df.game_id.map(gap).fillna(0.0)
    df['v1st'] = df.v1 + wt * df.gap; df['v2st'] = df.v2 + wt * df.gap
    for lab, mask in (('TUNE 2022-23', tune), ('TEST 2024-25', ~tune), ('ALL 2022-25', tune | ~tune)):
        s = df[mask]; w4 = s[s.week >= 4]
        print(f'\n== {lab}  (weeks 4+: n={len(w4)})')
        for c in ('v1', 'v2', 'v1st', 'v2st'):
            q = w4.dropna(subset=['mkt']); qo = w4.dropna(subset=['open'])
            X = np.c_[np.ones(len(q)), q.mkt, q[c] - q.mkt]; b = np.linalg.lstsq(X, q.hm, rcond=None)[0][2]
            wc, lc = picks(w4, c, 'mkt'); wo, lo = picks(w4, c, 'open')
            print(f'  {c:5s} miss {np.abs(q.hm - q[c]).mean():.2f} (market close {np.abs(q.hm - q.mkt).mean():.2f}, open {np.abs(qo.hm - qo.open).mean():.2f}) | weight on edge {b:.2f} | 5+ vs close {wc}-{lc} ({wc / max(wc + lc, 1) * 100:.1f}%) | 5+ vs open {wo}-{lo} ({wo / max(wo + lo, 1) * 100:.1f}%)')
    print('\nby season, weeks 4+, 5+ picks vs open:')
    for y in YEARS:
        s = df[df.season == y]; print(' ', y, {c: '%d-%d' % picks(s, c, 'open') for c in ('v1', 'v2', 'v2st')})
    df.to_csv(os.path.join(a.dir, 'v2_st_study_rows.csv'), index=False)
    json.dump(dict(lam=lam, carry=carry, weight=wt), open(os.path.join(a.dir, 'v2_st_params.json'), 'w'))


if __name__ == '__main__':
    main()
