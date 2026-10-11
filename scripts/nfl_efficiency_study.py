#!/usr/bin/env python3
"""Does the college-football method (opponent-adjusted EPA per play, ridge, last season's ratings as the prior, walk-forward, graded against the
closing line) find anything in the NFL?  Data: nflverse play-by-play (EPA, win probability) and nflverse games.csv (closing spread).

Protocol, the same as the college study: seasons 2017-2021 are the tuning seasons (2016 only seeds the prior), 2022-2025 are read once at the end,
each week's ratings use only games BEFORE that week, and the market line is the closing spread.

  python3 scripts/nfl_efficiency_study.py [--dir /tmp/nflstudy]
"""
import argparse, itertools, os, sys, urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st

PBP = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.parquet'
GAMES = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
YEARS = list(range(2016, 2026))
COLS = ['season', 'week', 'season_type', 'game_id', 'posteam', 'defteam', 'epa', 'play_type', 'wp', 'qb_kneel', 'qb_spike']
FIX = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}


def get(url, dest):
    if not os.path.exists(dest):
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault'}), timeout=300) as r, open(dest, 'wb') as f: f.write(r.read())
    return dest


def load(d):
    os.makedirs(d, exist_ok=True)
    g = pd.read_csv(get(GAMES, f'{d}/games.csv'))
    g = g[(g.season.isin(YEARS)) & (g.game_type == 'REG') & g.home_score.notna()].copy()
    for c in ('home_team', 'away_team'): g[c] = g[c].replace(FIX)
    g['neutral'] = g.location.eq('Neutral')
    parts = []
    for y in YEARS:
        p = pd.read_parquet(get(PBP.format(y=y), f'{d}/pbp_{y}.parquet'), columns=COLS)
        p = p[(p.season_type == 'REG') & p.play_type.isin(['pass', 'run']) & (p.qb_kneel != 1) & (p.qb_spike != 1) & p.epa.notna() & p.wp.between(0.05, 0.95)]
        p = p.assign(posteam=p.posteam.replace(FIX), defteam=p.defteam.replace(FIX), epa=p.epa.clip(-4, 4))
        a = p.groupby(['season', 'week', 'game_id', 'posteam', 'defteam']).agg(plays=('epa', 'size'), epa=('epa', 'mean')).reset_index()
        parts.append(a)
    tg = pd.concat(parts).rename(columns={'posteam': 'pos_team_id', 'defteam': 'def_team_id'}); tg['def_pos_team_id'] = tg.def_team_id
    gi = g.set_index('game_id')
    tg['home'] = tg.game_id.map(gi.home_team); tg['neu'] = tg.game_id.map(gi.neutral)
    tg['home_off'] = np.where(tg.neu == True, 0, np.where(tg.pos_team_id == tg.home, 1, -1))
    return tg, g


def walk_forward(tg, g, S, ALPHA, K, HFA, years, finals=None, prior_seed=None):
    st.ALPHA = ALPHA
    prior = prior_seed or ({}, {}); out = []
    for y in years:
        T = tg[tg.season == y]; G = g[g.season == y]; cur = prior
        for w in range(1, 19):
            cur = st.fit(T[T.week < w], *prior) if (T.week < w).sum() >= 30 else prior
            for r in G[G.week == w].itertuples():
                P = lambda t: cur[0].get(t, 0.0) - cur[1].get(t, 0.0)
                pred = K * (P(r.home_team) - P(r.away_team)) + (0 if r.neutral else HFA)
                out.append((y, w, r.home_score - r.away_score, r.spread_line, pred))      # spread_line: positive = home favoured, same sign as the margin
        if finals is not None: finals[y] = cur
        prior = ({t: S * v for t, v in cur[0].items()}, {t: S * v for t, v in cur[1].items()})
    return pd.DataFrame(out, columns=['season', 'week', 'hm', 'mkt', 'pred']).dropna(subset=['mkt'])


def report(r, label, minweek=4):
    r = r[r.week >= minweek].copy(); r['edge'] = r.pred - r.mkt; r['cover'] = r.hm - r.mkt
    print(f'{label} (weeks {minweek}+): n={len(r)}  miss: model {np.abs(r.hm - r.pred).mean():.2f}  market {np.abs(r.hm - r.mkt).mean():.2f}')
    for T in (1.5, 2.5, 3.5, 5):
        b = r[(r.edge.abs() >= T) & (r.cover != 0)]; w = int(((b.cover * np.sign(b.edge)) > 0).sum())
        print(f'   edge >= {T}: {w}-{len(b) - w}  ({w / max(len(b), 1) * 100:.1f}% ATS vs the 52.4% break-even)')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/nflstudy'); a = ap.parse_args()
    tg, g = load(a.dir)
    print('tuning on 2017-2021 (2016 seeds the prior)...')
    best = None
    for S, ALPHA, K, HFA in itertools.product((0.6, 0.8), (150, 400), (55, 70), (1.5, 2.5)):
        seed = walk_forward(tg, g, S, ALPHA, K, HFA, [2016], finals=(fin := {}))
        prior = ({t: S * v for t, v in fin[2016][0].items()}, {t: S * v for t, v in fin[2016][1].items()})
        r = walk_forward(tg, g, S, ALPHA, K, HFA, range(2017, 2022), prior_seed=prior); r = r[r.week >= 4]
        miss = np.abs(r.hm - r.pred).mean(); print(f'  S={S} alpha={ALPHA} K={K} hfa={HFA}: miss {miss:.3f}')
        if best is None or miss < best[0]: best = (miss, S, ALPHA, K, HFA)
    _, S, ALPHA, K, HFA = best; print('chosen (lowest average miss on the tuning seasons, not on the test):', best[1:])
    fin = {}; res = walk_forward(tg, g, S, ALPHA, K, HFA, YEARS, finals=fin)
    report(res[res.season.isin(range(2017, 2022))], 'TUNING 2017-2021'); report(res[res.season.isin([2022, 2023, 2024, 2025])], 'TEST 2022-2025 (read once)')
    for y in (2022, 2023, 2024, 2025):
        q = res[(res.season == y) & (res.week >= 4)]; e = q.pred - q.mkt; c = q.hm - q.mkt; b = (e.abs() >= 2.5) & (c != 0); w = int(((c[b] * np.sign(e[b])) > 0).sum())
        print(f'   {y}: edge >= 2.5: {w}-{int(b.sum()) - w}')
    q = res[(res.season >= 2022) & (res.week >= 4)]; q = q.assign(edge=q.pred - q.mkt)
    X = np.c_[np.ones(len(q)), q.mkt, q.edge]; bb = np.linalg.lstsq(X, q.hm, rcond=None)[0]
    print(f'final margin ~ market + w*(model - market), test seasons: w = {bb[2]:.3f}')
    for w in (0.05, 0.1, 0.2): print(f'   blend w={w}: miss {np.abs(q.hm - (q.mkt + w * q.edge)).mean():.3f} vs market {np.abs(q.hm - q.mkt).mean():.3f}')


if __name__ == '__main__':
    main()
