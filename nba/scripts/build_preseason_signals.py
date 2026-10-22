#!/usr/bin/env python3
"""
Sections A and B of docs/preseason-signals-test.md (rules fixed there before any result was computed).

  nba/.venv/bin/python nba/scripts/build_preseason_table.py     # stage 1: rebuild preseason games (needs fetch_preseason.py)
  nba/.venv/bin/python nba/scripts/build_preseason_signals.py   # stage 2: this file -> data/preseason_signals.json

Season label = year the season ends. Test seasons 2024, 2025, 2026; every fit is leave-one-season-out.
"""
import json, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw')
DATA = os.path.join(HERE, '..', 'data')
SEASONS = [2024, 2025, 2026]
RNG = np.random.default_rng(20261020)
STATS = ['fga', 'fg3a', 'fta', 'reb', 'ast', 'pts', 'tov', 'stl', 'blk']
BOOT = 2000


# ------------------------------------------------------------------ regular season (hoopR box scores)
def load_rs(season):
    pb = pd.read_csv(os.path.join(RAW, 'hoopr', f'player_box_{season}.csv'), low_memory=False)
    pb = pb[pb.season_type == 2].copy()
    tb = pd.read_csv(os.path.join(RAW, 'hoopr', f'team_box_{season}.csv'), low_memory=False)
    tb = tb[tb.season_type == 2]
    tcol = 'total_turnovers' if 'total_turnovers' in tb else 'turnovers'
    tb = tb[['game_id', 'team_id', 'field_goals_attempted', 'free_throws_attempted', tcol]].copy()
    tb.columns = ['game_id', 'team_id', 't_fga', 't_fta', 't_tov']
    tb['t_plays'] = tb.t_fga + 0.44 * tb.t_fta + tb.t_tov
    pb['min'] = pd.to_numeric(pb.minutes, errors='coerce').fillna(0)
    for c in ['field_goals_attempted', 'three_point_field_goals_attempted', 'free_throws_attempted', 'rebounds',
              'three_point_field_goals_made', 'assists', 'points', 'turnovers', 'steals', 'blocks']:
        pb[c] = pd.to_numeric(pb[c], errors='coerce').fillna(0)
    pb = pb.rename(columns={'field_goals_attempted': 'fga', 'three_point_field_goals_attempted': 'fg3a', 'three_point_field_goals_made': 'fg3m',
                            'free_throws_attempted': 'fta', 'rebounds': 'reb', 'assists': 'ast', 'points': 'pts',
                            'turnovers': 'tov', 'steals': 'stl', 'blocks': 'blk'})
    pb = pb.merge(tb, on=['game_id', 'team_id'], how='left')
    pb['tmin'] = pb.groupby(['game_id', 'team_id'])['min'].transform('sum')
    pb['plays'] = pb.fga + 0.44 * pb.fta + pb.tov
    pb['u_den'] = pb.t_plays * pb['min'] / (pb.tmin / 5).replace(0, np.nan)
    pb = pb[pd.to_numeric(pb.athlete_id, errors='coerce').notna()].copy()
    pb['pid'] = pd.to_numeric(pb.athlete_id).astype('int64').astype(str)
    pb['date'] = pd.to_datetime(pb.game_date)
    order = pb.drop_duplicates(['team_id', 'game_id']).sort_values(['team_id', 'date'])
    order['tgn'] = order.groupby('team_id').cumcount() + 1
    pb = pb.merge(order[['team_id', 'game_id', 'tgn']], on=['team_id', 'game_id'])
    return pb[pb['min'] > 0]


def agg_rs(df):
    g = df.groupby('pid')
    out = g.agg(gp=('min', 'size'), min=('min', 'sum'), plays=('plays', 'sum'), u_den=('u_den', 'sum'),
                fg3m=('fg3m', 'sum'), **{s: (s, 'sum') for s in STATS})
    out['mpg'] = out['min'] / out.gp
    out['usage'] = 100 * out.plays / out.u_den
    for s in STATS:
        out['r_' + s] = out[s] / out['min'] * 36
    return out


# ------------------------------------------------------------------ preseason (rebuilt from ESPN plays)
def load_pre():
    P = pd.read_csv(os.path.join(RAW, 'preseason_players.csv'), dtype={'pid': str, 'game_id': str})
    T = pd.read_csv(os.path.join(RAW, 'preseason_teams.csv'), dtype={'game_id': str})
    # amendments 1 and 9: drop TEAM-games whose rebuilt minutes do not match the box (one team's substitution chain
    # can fail while the other team's is fine)
    P['err'] = (P.g_min - P.box_min).abs()
    gm = P[P.box_min > 0].groupby(['game_id', 'team']).agg(mae=('err', 'mean'), nst=('starter', 'sum'))
    bad = gm[(gm.mae > 1.0) | (gm.nst != 5)].index
    key = list(zip(P.game_id, P.team))
    P = P[[k not in set(bad) for k in key]]
    T = T[[(g, t) not in set(bad) for g, t in zip(T.game_id, T.team)]]
    return P, T, bad


def agg_pre(P, T):
    P = P[P.box_min > 0].copy()
    tm = T.set_index(['game_id', 'team'])
    P['tmin'] = P.groupby(['game_id', 'team']).box_min.transform('sum')
    P['t_plays_g'] = [tm.loc[(g, t), 'g_fga'] + 0.44 * tm.loc[(g, t), 'g_fta'] + tm.loc[(g, t), 'g_tov']
                      for g, t in zip(P.game_id, P.team)]
    P['own_plays_g'] = P.g_fga + 0.44 * P.g_fta + P.g_tov
    P['u_den_g'] = P.t_plays_g * P.box_min / (P.tmin / 5).replace(0, np.nan)
    P['own_plays_1'] = P.h1_fga + 0.44 * P.h1_fta + P.h1_tov
    P['team_plays_1'] = P.t1_fga + 0.44 * P.t1_fta + P.t1_tov
    g = P.groupby(['season', 'pid'])
    cols = {'n': ('game_id', 'nunique'), 'box_min': ('box_min', 'sum'), 'h1_min': ('h1_min', 'sum'),
            'own_plays_g': ('own_plays_g', 'sum'), 'u_den_g': ('u_den_g', 'sum'),
            'own_plays_1': ('own_plays_1', 'sum'), 'team_plays_1': ('team_plays_1', 'sum'),
            'starts': ('starter', 'sum'), 'name': ('name', 'last'), 'team': ('team', 'last'),
            'h1_fg3m': ('h1_fg3m', 'sum'), 'g_fg3m': ('g_fg3m', 'sum'), 'h1_fgm': ('h1_fgm', 'sum'),
            't1_ast': ('t1_ast', 'sum'), 'h1_ast_made': ('h1_ast_made', 'sum')}
    for s in STATS:
        cols['h1_' + s] = ('h1_' + s, 'sum')
        cols['g_' + s] = ('g_' + s, 'sum')
    out = g.agg(**cols)
    out['mpg_total'] = out.box_min / out.n
    out['mpg_1h'] = out.h1_min / out.n
    out['usage_1h'] = 100 * out.own_plays_1 / out.team_plays_1.replace(0, np.nan)
    out['usage_g'] = 100 * out.own_plays_g / out.u_den_g.replace(0, np.nan)
    for s in STATS:
        out['p1_' + s] = out['h1_' + s] / out.h1_min.replace(0, np.nan) * 36         # first-half rate
        out['pg_' + s] = out['g_' + s] / out.box_min.replace(0, np.nan) * 36          # whole-game rate
    out['ast_share_1h'] = 100 * out.h1_ast / out.t1_ast.replace(0, np.nan)
    return out.reset_index()


# ------------------------------------------------------------------ player-season table
def build_table():
    P, T, bad = load_pre()
    pre = agg_pre(P, T)
    rs = {s: load_rs(s) for s in [2023, 2024, 2025, 2026]}
    rows = []
    for S in SEASONS:
        last = agg_rs(rs[S - 1])
        full = agg_rs(rs[S])
        early_df = rs[S][rs[S].tgn <= 15]
        early = agg_rs(early_df)
        ps = pre[pre.season == S].set_index('pid')
        j = ps.join(last.add_prefix('L_'), how='inner').join(full.add_prefix('F_'), how='inner') \
            .join(early.add_prefix('E_'), how='inner')
        j['S'] = S
        rows.append(j.copy().reset_index())
    return pd.concat(rows, ignore_index=True), pre, bad


# ------------------------------------------------------------------ stats helpers
def ols(X, y):
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def pred(b, X):
    return b[0] + np.asarray(X) @ b[1:]


def loso(df, feats, target):
    """leave-one-season-out OLS predictions"""
    out = pd.Series(index=df.index, dtype=float)
    for S in SEASONS:
        tr, te = df[df.S != S], df[df.S == S]
        b = ols(tr[feats].values, tr[target].values)
        out.loc[te.index] = pred(b, te[feats].values)
    return out


def cluster_boot(df, vals, fn, n=BOOT):
    """bootstrap fn(sample of vals) resampling players (pid clusters) with replacement"""
    groups = {p: np.asarray(ix) for p, ix in df.groupby('pid').indices.items()}
    pids = list(groups)
    out = []
    v = np.asarray(vals)
    for _ in range(n):
        pick = RNG.choice(len(pids), len(pids))
        idx = np.concatenate([groups[pids[i]] for i in pick])
        out.append(fn(idx))
    return np.array(out)


def paired(df, e_a, e_b):
    """mean(e_a - e_b) with cluster-bootstrap SE (positive = b better)"""
    d = np.asarray(e_a) - np.asarray(e_b)
    boots = cluster_boot(df.reset_index(drop=True), d, lambda ix: d[ix].mean())
    return float(d.mean()), float(boots.std()), float(d.mean() / boots.std())


# ------------------------------------------------------------------ A and B1: minutes
def minutes_section(d):
    d = d[(d.E_gp >= 10) & (d.L_min >= 400) & (d.box_min >= 40)].copy().reset_index(drop=True)
    d['y'] = d.E_mpg
    res = {'n': int(len(d)), 'by_season': d.S.value_counts().sort_index().to_dict()}
    corr = {}
    for k, c in (('total preseason', 'mpg_total'), ('1H preseason', 'mpg_1h'), ('last season', 'L_mpg')):
        corr[k] = float(np.corrcoef(d[c], d.y)[0, 1])
    res['corr_with_early_mpg'] = corr
    res['corr_by_season'] = {int(S): {k: float(np.corrcoef(d[d.S == S][c], d[d.S == S].y)[0, 1])
                                      for k, c in (('total', 'mpg_total'), ('1H', 'mpg_1h'), ('last', 'L_mpg'))}
                             for S in SEASONS}
    models = {'total preseason': ['mpg_total'], 'last season': ['L_mpg'], '1H': ['mpg_1h'],
              'last + total': ['L_mpg', 'mpg_total'], 'last + 1H': ['L_mpg', 'mpg_1h'],
              'last + total + 1H': ['L_mpg', 'mpg_total', 'mpg_1h']}
    errs, mae, rmse = {}, {}, {}
    for k, f in models.items():
        p = loso(d, f, 'y')
        e = (p - d.y).abs()
        errs[k] = e.values
        mae[k] = float(e.mean())
        rmse[k] = float(np.sqrt(((p - d.y) ** 2).mean()))
    res['mae'], res['rmse'] = mae, rmse
    comp = {}
    for a, b in (('last season', 'last + 1H'), ('last + total', 'last + 1H'), ('total preseason', '1H'),
                 ('last season', 'last + total')):
        m, se, z = paired(d, errs[a], errs[b])
        comp[f'{a} vs {b}'] = {'mae_diff': m, 'se': se, 'z': z}
    res['paired'] = comp
    # coefficient on the full model, fit on all three seasons (for section C)
    b = ols(d[['L_mpg', 'mpg_1h']].values, d.y.values)
    res['fit_last_1h'] = [float(x) for x in b]
    b2 = ols(d[['L_mpg', 'mpg_total']].values, d.y.values)
    res['fit_last_total'] = [float(x) for x in b2]
    # starters vs bench: games started in preseason vs early-season starts is not tested here
    return res, d


# ------------------------------------------------------------------ A3 and B2: rates
def rate_pairs(d, s):
    """(last, first-half preseason, whole-game preseason, 1H minutes, whole minutes) for one stat"""
    if s == 'usage':
        return d.L_usage, d.usage_1h, d.usage_g
    return d['L_r_' + s], d['p1_' + s], d['pg_' + s]


def rates_section(d0):
    d = d0[(d0.L_min >= 400) & (d0.box_min >= 40)].copy().reset_index(drop=True)
    out = {}
    for s in STATS + ['usage']:
        L, P1, Pg = rate_pairs(d, s)
        for tgt, tag, minc in (('F', 'full', 'F_min'), ('E', 'early', 'E_min')):
            y = d[f'{tgt}_usage'] if s == 'usage' else d[f'{tgt}_r_{s}']
            ok = (d[minc] >= (500 if tgt == 'F' else 150)) & L.notna() & P1.notna() & Pg.notna() & y.notna()
            if s in ('stl', 'blk', 'tov', 'fta'):
                ok &= (L.abs() < 1e9)
            e = d[ok].copy().reset_index(drop=True)
            Lk, P1k, Pgk, yk = L[ok].values, P1[ok].values, Pg[ok].values, y[ok].values
            e['dpre1'] = P1k - Lk
            e['dpreg'] = Pgk - Lk
            e['dy'] = yk - Lk
            e['L'] = Lk
            e['y'] = yk
            r = {}
            r['n'] = int(len(e))
            for k, c in (('1H', 'dpre1'), ('whole', 'dpreg')):
                r['corr_' + k] = float(np.corrcoef(e[c], e.dy)[0, 1])
                boots = cluster_boot(e, e.dy.values, lambda ix, c=c: np.corrcoef(e[c].values[ix], e.dy.values[ix])[0, 1])
                r['ci_' + k] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
            # B2: shrunk beta = b * m / (m + k), fit on the other two seasons, scored on the third
            for k, c, mcol in (('1H', 'dpre1', 'h1_min'), ('whole', 'dpreg', 'box_min')):
                best = None
                for kk in (10, 20, 40, 80, 160, 320, 640):
                    w = e[mcol] / (e[mcol] + kk)
                    pr = pd.Series(index=e.index, dtype=float)
                    for S in SEASONS:
                        tr, te = e.S != S, e.S == S
                        x = (w * e[c])[tr].values
                        b = (x * e.dy[tr].values).sum() / (x * x).sum()
                        pr[te] = e.L[te] + b * (w * e[c])[te]
                    se_ = (pr - e.y) ** 2
                    if best is None or se_.sum() < best[1].sum():
                        best = (kk, se_, pr)
                base = (e.L - e.y) ** 2
                m, se, z = paired(e, base.values, best[1].values)
                x_all = (e[mcol] / (e[mcol] + best[0]) * e[c]).values
                b_all = (x_all * e.dy.values).sum() / (x_all ** 2).sum()
                r['B2_' + k] = {'k': best[0], 'beta_full': float(b_all), 'mse_base': float(base.mean()),
                                'mse_cand': float(best[1].mean()), 'rmse_base': float(np.sqrt(base.mean())),
                                'rmse_cand': float(np.sqrt(best[1].mean())), 'dmse': m, 'se': se, 'z': z,
                                'half_weight_minutes': best[0]}
            out[f'{s}|{tag}'] = r
    return out


def pct_section(d0):
    """3P%: preseason change vs last season against regular-season change (control; expected not to carry)"""
    d = d0[(d0.L_min >= 400) & (d0.box_min >= 40) & (d0.L_fg3a >= 100) & (d0.F_fg3a >= 100) & (d0.h1_fg3a >= 8)]
    d = d.copy().reset_index(drop=True)
    Lp, Pp, Fp = d.L_fg3m / d.L_fg3a, d.h1_fg3m / d.h1_fg3a, d.F_fg3m / d.F_fg3a
    x, y = (Pp - Lp).values, (Fp - Lp).values
    boots = cluster_boot(d, y, lambda ix: np.corrcoef(x[ix], y[ix])[0, 1])
    return {'n': int(len(d)), 'corr_1H': float(np.corrcoef(x, y)[0, 1]),
            'ci_1H': [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}


def main():
    d, pre, bad = build_table()
    res = {'generated': pd.Timestamp.now().isoformat()[:16], 'games_excluded': len(bad),
           'player_seasons_all': int(len(d))}
    m, dm = minutes_section(d)
    res['minutes'] = m
    res['rates'] = rates_section(d)
    res['pct3'] = pct_section(d)
    d.to_csv(os.path.join(RAW, 'preseason_player_seasons.csv'), index=False)
    with open(os.path.join(DATA, 'preseason_signals.json'), 'w') as f:
        json.dump(res, f, indent=1)
    # printout
    print('player-seasons joined', len(d), '| minutes sample', m['n'], m['by_season'])
    print('corr with early mpg', {k: round(v, 3) for k, v in m['corr_with_early_mpg'].items()})
    print('by season', m['corr_by_season'])
    print('MAE', {k: round(v, 2) for k, v in m['mae'].items()})
    print('RMSE', {k: round(v, 2) for k, v in m['rmse'].items()})
    for k, v in m['paired'].items():
        print('  ', k, {a: round(b, 3) for a, b in v.items()})
    print('\nrates (full season target):')
    print('%-6s %5s | %-24s | %-24s | B2 1H: rmse base->cand  z  k | B2 whole z' % ('stat', 'n', 'corr 1H [95%]', 'corr whole [95%]'))
    for key, r in res['rates'].items():
        if not key.endswith('full'):
            continue
        print('%-6s %5d | %.2f [%.2f,%.2f]          | %.2f [%.2f,%.2f]          | %.3f -> %.3f  %5.2f  %3d | %5.2f' % (
            key.split('|')[0], r['n'], r['corr_1H'], *r['ci_1H'], r['corr_whole'], *r['ci_whole'],
            r['B2_1H']['rmse_base'], r['B2_1H']['rmse_cand'], r['B2_1H']['z'], r['B2_1H']['k'], r['B2_whole']['z']))
    print('3P% (1H change vs RS change):', res['pct3'])
    print('\nrates (first 15 team games target):')
    for key, r in res['rates'].items():
        if not key.endswith('early'):
            continue
        print('%-6s %5d | corr1H %.2f corrW %.2f | B2 1H z %5.2f whole z %5.2f' % (
            key.split('|')[0], r['n'], r['corr_1H'], r['corr_whole'], r['B2_1H']['z'], r['B2_whole']['z']))


if __name__ == '__main__':
    main()
