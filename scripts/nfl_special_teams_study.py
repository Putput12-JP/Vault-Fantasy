#!/usr/bin/env python3
"""NFL game model: does a special teams rating improve it? Walk-forward, 2017-2025, against the closing spread.

The CFB model gained a special teams rating (scripts/cfb_v2_st_study.py). This asks the same question of the NFL Vault line (data/game_model.json,
the model behind the NFL Model page). Rules set before the run, in the same order as the CFB study:

  Special teams value  every punt, kickoff and field goal has an EPA from the possessing team's side (nflverse play-by-play, clipped to +-3).
                       A game's special teams net, from the home side, is the home team's EPA on those plays minus the away team's. Extra points
                       are left out (almost no variance). One number per game, in points.
  Rating               ridge on (home net) ~ r_home - r_away, centred on last season's final rating x CARRY, refit each week from EARLIER games only.
  Model                the existing walk-forward margin (build_game_model.run, fitted values from game_model.json) + WEIGHT x (r_home - r_away).
  Tuning               lam / carry / weight are chosen on 2017-2021 by the average miss (root mean square of the final margin vs the model) only,
                       never by pick record. 2022-2025 is read once. 2026 so far is shown separately and is not used for any choice.
  Go / no-go           GO only if, on 2022-2025, the miss falls by more than 2 standard errors of the paired difference AND the 3+ point pick record
                       against the close is not worse than the baseline. Anything else is NO-GO and nothing changes on the page.

Run: python3 scripts/nfl_special_teams_study.py [--dir /tmp/nflst]     (pandas, numpy, pyarrow)
"""
import argparse, itertools, json, math, os, sys, urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_game_model as bgm

PBP = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.parquet'
YEARS = list(range(2016, 2027))
COLS = ['season', 'week', 'home_team', 'away_team', 'posteam', 'play_type', 'epa']
TUNE, TEST = range(2017, 2022), range(2022, 2026)
GRID = dict(lam=(5, 20, 50), carry=(0.4, 0.6, 0.8), weight=(0.5, 1.0, 1.5))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(y, d):
    dest = f'{d}/pbp_{y}.parquet'
    if not os.path.exists(dest):
        with urllib.request.urlopen(urllib.request.Request(PBP.format(y=y), headers={'User-Agent': 'vault'}), timeout=600) as r, open(dest, 'wb') as f: f.write(r.read())
    return dest


def st_games(d):
    """one row per game: st_home = special teams net EPA from the home side"""
    out = []
    for y in YEARS:
        p = pd.read_parquet(get(y, d), columns=COLS)
        p = p[p.play_type.isin(['punt', 'kickoff', 'field_goal']) & p.epa.notna() & p.posteam.notna()].copy()
        for c in ('home_team', 'away_team', 'posteam'): p[c] = p[c].map(bgm.norm_team)
        p['h'] = p.epa.clip(-3, 3) * np.where(p.posteam == p.home_team, 1, -1)
        g = p.groupby(['season', 'week', 'home_team', 'away_team']).agg(st_home=('h', 'sum'), plays=('h', 'size')).reset_index()
        out.append(g)
    return pd.concat(out, ignore_index=True)


def ridge(obs, prior, lam):
    """team ratings centred on the prior; obs has home, away, st_home"""
    if len(obs) < 20: return dict(prior)
    teams = sorted(set(obs.home) | set(obs.away) | set(prior)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    X = np.zeros((len(obs), n)); X[np.arange(len(obs)), obs.home.map(ix).values] = 1; X[np.arange(len(obs)), obs.away.map(ix).values] = -1
    p0 = np.array([prior.get(t, 0.0) for t in teams]); y = obs.st_home.values - X @ p0
    return dict(zip(teams, p0 + np.linalg.solve(X.T @ X + lam * np.eye(n), X.T @ y)))


def walk(stg, lam, carry):
    """per-game (season, week, home, away) -> r_home - r_away from games BEFORE that week; also the final rating of each season"""
    final, feat = {}, {}
    prior = {}
    for y in YEARS:
        G = stg[stg.season == y]
        p0 = {t: carry * v for t, v in prior.items()}
        for w in sorted(G.week.unique()):
            r = ridge(G[G.week < w].rename(columns={'home_team': 'home', 'away_team': 'away'}), p0, lam)
            for q in G[G.week == w].itertuples(): feat[(y, int(w), q.home_team, q.away_team)] = r.get(q.home_team, 0.0) - r.get(q.away_team, 0.0)
        prior = ridge(G.rename(columns={'home_team': 'home', 'away_team': 'away'}), p0, lam); final[y] = prior
    return feat, final


def baseline():
    gm = json.load(open(os.path.join(ROOT, 'data', 'game_model.json')))
    bgm.HFA = gm['hfa'] - ((gm.get('inseason_overlay') or {}).get('hfa') or {}).get('delta', 0)
    bgm.QB = {'margin': gm['qb']['margin'], 'total': gm['qb']['total']}
    bgm.MKT = {'margin': gm['market_learning']['w']['margin'], 'total': gm['market_learning']['w']['total']}
    games = bgm.fetch_games()
    _, _, _, preds, _, _ = bgm.run(games, collect_from=2014, qb=bgm.QB)
    played = [g for g in games if g['played'] and g['season'] >= 2014]
    assert len(played) == len(preds), (len(played), len(preds))
    return pd.DataFrame([dict(season=g['season'], week=g['week'], home=g['ht'], away=g['at'], pm=p['pm'], result=p['result'], spread=p['spread']) for g, p in zip(played, preds)])


def rmse(x): return float(np.sqrt(np.mean(np.square(x))))


def picks(df, col, edge):
    d = df[df.spread.notna() & ((df[col] - df.spread).abs() >= edge)]
    c = np.sign(d[col] - d.spread) * (d.result - d.spread)
    return [int((c > 0).sum()), int((c < 0).sum())]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/nflst'); a = ap.parse_args(); os.makedirs(a.dir, exist_ok=True)
    stg = st_games(a.dir); base = baseline()
    base['key'] = list(zip(base.season, base.week, base.home, base.away))
    print(f'special teams games {len(stg)}, baseline games {len(base)}')
    cache = {}
    def scored(lam, carry, weight, rows):
        if (lam, carry) not in cache: cache[(lam, carry)] = walk(stg, lam, carry)
        feat, _ = cache[(lam, carry)]
        d = rows.copy(); d['f'] = d.key.map(feat); d = d[d.f.notna()]
        d['new'] = d.pm + weight * d.f
        return d
    tune = base[base.season.isin(TUNE)]
    res = []
    for lam, carry, weight in itertools.product(GRID['lam'], GRID['carry'], GRID['weight']):
        d = scored(lam, carry, weight, tune); res.append((rmse(d.result - d.new), lam, carry, weight, len(d)))
    res.sort(); print('tuning 2017-2021 (miss = RMSE of the final margin; baseline', round(rmse(tune.result - tune.pm), 3), ')')
    for r in res[:5]: print('  ', [round(x, 3) if isinstance(x, float) else x for x in r])
    _, lam, carry, weight, _ = res[0]
    out = dict(chosen=dict(lam=lam, carry=carry, weight=weight), tune_baseline=round(rmse(tune.result - tune.pm), 3), tune_best=round(res[0][0], 3))
    for name, yrs in (('test 2022-2025', TEST), ('2026 so far', [2026])):
        rows = base[base.season.isin(yrs)]
        d = scored(lam, carry, weight, rows)
        e0, e1 = (d.result - d.pm).values, (d.result - d.new).values
        diff = e0 ** 2 - e1 ** 2; se = diff.std(ddof=1) / math.sqrt(len(diff))
        # the plain regression: does the special teams difference explain what the model missed?
        x = d.f.values; y = (d.result - d.pm).values; b = float((x * y).sum() / (x * x).sum()); bse = float(np.sqrt(((y - b * x) ** 2).sum() / (len(x) - 1) / (x * x).sum()))
        o = dict(n=len(d), miss_base=round(rmse(e0), 3), miss_new=round(rmse(e1), 3), market_miss=round(rmse((d.result - d.spread).dropna()), 3),
                 paired_t=round(float(diff.mean() / se), 2), coef_on_st_diff=round(b, 3), coef_se=round(bse, 3),
                 picks_base={str(t): picks(d, 'pm', t) for t in (1.5, 3, 5)}, picks_new={str(t): picks(d, 'new', t) for t in (1.5, 3, 5)})
        out[name] = o; print(name, json.dumps(o))
    _, fin = cache[(lam, carry)]
    yrs = [y for y in range(2017, 2026)]
    cors = [float(np.corrcoef([fin[y - 1].get(t, 0) for t in fin[y]], [fin[y].get(t, 0) for t in fin[y]])[0, 1]) for y in yrs]
    out['st_rating_sd'] = round(float(np.std(list(fin[2025].values()))), 2); out['year_to_year_corr'] = round(float(np.mean(cors)), 2)
    print('rating sd (points)', out['st_rating_sd'], 'mean year-to-year correlation of final ratings', out['year_to_year_corr'])
    json.dump(out, open(os.path.join(a.dir, 'result.json'), 'w'), indent=1)


if __name__ == '__main__':
    sys.exit(main())
