#!/usr/bin/env python3
"""Can a market-blind college football efficiency model beat the betting line? (replication study)

JP+ (jpplusratings.com) describes its method: opponent-adjusted play-by-play efficiency (ridge
regression on success rate and explosiveness), preseason priors carried forward with mean
reversion, picks only where the model and the market differ by 5+ points. It reports 61.6% ATS.
This script builds that kind of model from public data and tests it walk-forward, week by week,
against ESPN's spread (the market line), so no game is ever predicted with its own data.

  Data   sportsdataverse-data releases: ESPN play-by-play (EPA, success) and schedules, 2021-2025
  Model  per team: offense and defense EPA/play, ridge-adjusted for opponent and home field;
         prior = last season's ratings x S (mean reversion); predicted margin = K x rating gap + home field
  Test   every FBS-vs-FBS regular-season game 2022-2025, graded against the ESPN spread
  Tuned  S, ALPHA, K were chosen on 2022-2023 only; 2024-2025 is the untouched test

Result (see docs/retro/cfb-efficiency-replication.md): after week 3 the model misses by about 12.5-12.6
points per game against the market's 11.9-12.1, and its 5+ point disagreements cover 47.5-51% of the
time depending on the period. It does not beat the closing line. Needs: pandas, numpy, scipy, scikit-learn, pyarrow. ~300 MB of downloads.

Run: python3 scripts/cfb_efficiency_study.py [--dir /tmp/cfbstudy]
"""
import argparse, os, sys, urllib.request, itertools
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.linear_model import Ridge

REL = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
TEAMS = 'https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/teams/teams_colors_logos.csv'
YEARS = [2021, 2022, 2023, 2024, 2025]
GARBAGE = {1: 43, 2: 37, 3: 27, 4: 22}      # score gap per quarter beyond which plays are dropped
COLS = ['season', 'game_id', 'week', 'seasonType', 'pos_team_id', 'def_pos_team_id', 'scrimmage_play', 'kneel_down', 'EPA',
        'period', 'pos_score_diff_start', 'penalty_no_play', 'homeTeamId', 'awayTeamId', 'homeFinalScore',
        'awayFinalScore', 'homeTeamSpread', 'status_type_completed']
S, ALPHA, K, HFA = 0.85, 300, 70, 2.5      # tuned on 2022-2023


def fetch(url, dest):
    if not os.path.exists(dest):
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault'}), timeout=300) as r, open(dest, 'wb') as f:
            f.write(r.read())
    return dest


def load(d, years=None):
    tgs, gms = [], []
    for y in (years or YEARS):
        p = pd.read_parquet(fetch(f'{REL}/espn_cfb_pbp/play_by_play_{y}.parquet', f'{d}/pbp_{y}.parquet'), columns=COLS)
        p = p[p.seasonType == 2]
        sch = pd.read_parquet(fetch(f'{REL}/espn_cfb_schedules/cfb_schedule_{y}.parquet', f'{d}/sched_{y}.parquet'), columns=['game_id', 'neutral_site'])
        g = p.drop_duplicates('game_id')[['season', 'week', 'game_id', 'homeTeamId', 'awayTeamId', 'homeFinalScore', 'awayFinalScore', 'homeTeamSpread', 'status_type_completed']].merge(sch, on='game_id', how='left')
        s = p[p.scrimmage_play & ~p.kneel_down & ~p.penalty_no_play]
        s = s[s.pos_score_diff_start.abs() <= s.period.map(GARBAGE).fillna(22)]
        s = s.assign(epa=s.EPA.clip(-3, 3))
        a = s.groupby(['game_id', 'pos_team_id', 'def_pos_team_id']).agg(plays=('epa', 'size'), epa_sum=('epa', 'sum')).reset_index()
        a['season'] = y; tgs.append(a); gms.append(g)
    tg, gm = pd.concat(tgs), pd.concat(gms)
    tg = tg.merge(gm[['game_id', 'week', 'homeTeamId', 'neutral_site']], on='game_id')
    tg['home_off'] = np.where(tg.neutral_site == True, 0, np.where(tg.pos_team_id == tg.homeTeamId, 1, -1))
    tg['epa'] = tg.epa_sum / tg.plays
    return tg, gm


def fbs_sets(gm, d, years=None, min_games=5):
    t = pd.read_csv(fetch(TEAMS, f'{d}/teams.csv'), encoding='latin-1')
    seed = set(t[t.conference.notna()].team_id.astype(int)); out = {}
    for y in (years or YEARS):                      # FBS = plays 5+ games against FBS (catches teams that moved up since the 2021 file)
        g = gm[gm.season == y]; cur = set(seed)
        for _ in range(3):
            cnt = {}
            for h, a in zip(g.homeTeamId, g.awayTeamId):
                if a in cur: cnt[h] = cnt.get(h, 0) + 1
                if h in cur: cnt[a] = cnt.get(a, 0) + 1
            cur = {k for k, v in cnt.items() if v >= min_games}
        out[y] = cur
    return out


def fit(obs, pa, pb):
    if len(obs) < 30: return dict(pa), dict(pb)
    teams = sorted(set(obs.pos_team_id) | set(obs.def_pos_team_id)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    r = np.arange(len(obs)); o = obs.pos_team_id.map(ix).values; dd = obs.def_pos_team_id.map(ix).values
    X = sp.csr_matrix((np.r_[np.ones(len(obs)), np.ones(len(obs)), obs.home_off.values * 10.0], (np.r_[r, r, r], np.r_[o, n + dd, np.full(len(obs), 2 * n)])), shape=(len(obs), 2 * n + 1))
    base = obs.pos_team_id.map(lambda t: pa.get(t, 0.0)).values + obs.def_pos_team_id.map(lambda t: pb.get(t, 0.0)).values
    m = Ridge(alpha=ALPHA).fit(X, obs.epa.values - base, sample_weight=obs.plays.values)
    a, b = dict(pa), dict(pb)
    for t, i in ix.items(): a[t] = pa.get(t, 0.0) + m.coef_[i]; b[t] = pb.get(t, 0.0) + m.coef_[n + i]
    return a, b


def walk_forward(tg, gm, fbs, years=None, finals=None):
    """finals (a dict, optional) is filled with {season: (offense, defense)} ratings after the last game of that season"""
    prior = ({}, {}); out = []
    for y in (years or YEARS):
        F = fbs[y]
        T = tg[(tg.season == y) & tg.pos_team_id.isin(F) & tg.def_pos_team_id.isin(F)]
        G = gm[(gm.season == y) & gm.homeTeamId.isin(F) & gm.awayTeamId.isin(F) & (gm.status_type_completed == True)]
        cur = prior
        for w in range(1, 17):
            cur = fit(T[T.week < w], *prior) if (T.week < w).sum() >= 30 else prior   # only games BEFORE week w
            gw = G[G.week == w]
            for r in gw.itertuples():
                P = lambda t: cur[0].get(t, 0.0) - cur[1].get(t, 0.0)
                hf = 0 if r.neutral_site == True else 1
                out.append((y, w, r.homeFinalScore - r.awayFinalScore, r.homeTeamSpread, K * (P(r.homeTeamId) - P(r.awayTeamId)) + HFA * hf))
        if finals is not None: finals[y] = cur
        prior = ({t: S * v for t, v in cur[0].items()}, {t: S * v for t, v in cur[1].items()})
    return pd.DataFrame(out, columns=['season', 'week', 'hm', 'mkt', 'pred'])


def report(r, label, minweek=1):
    r = r[(r.week >= minweek)].dropna(subset=['mkt']).copy(); r['edge'] = r.pred - r.mkt; r['cover'] = r.hm - r.mkt
    print(f'{label} (weeks {minweek}+): n={len(r)}  miss: model {np.abs(r.hm - r.pred).mean():.2f}  market {np.abs(r.hm - r.mkt).mean():.2f}')
    for T in (3, 5, 7):
        b = r[(r.edge.abs() >= T) & (r.cover != 0)]; w = int(((b.cover * np.sign(b.edge)) > 0).sum())
        print(f'   edge >= {T}: {w}-{len(b) - w}  ({w / max(len(b), 1) * 100:.1f}% ATS, break-even 52.4%)')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    os.makedirs(a.dir, exist_ok=True)
    tg, gm = load(a.dir); fbs = fbs_sets(gm, a.dir); res = walk_forward(tg, gm, fbs)
    for ys, lab in (([2022, 2023], 'TUNING 2022-2023'), ([2024, 2025], 'TEST 2024-2025 (untouched)')):
        for mw in (1, 4): report(res[res.season.isin(ys)], lab, mw)
    print('\nby season, weeks 4+, edge >= 5:')
    for y in (2022, 2023, 2024, 2025):
        r = res[(res.season == y) & (res.week >= 4)].dropna(subset=['mkt']); e = r.pred - r.mkt; c = r.hm - r.mkt
        b = (e.abs() >= 5) & (c != 0); w = int(((c[b] * np.sign(e[b])) > 0).sum()); print(f'   {y}: {w}-{b.sum() - w}')


if __name__ == '__main__':
    sys.exit(main())
