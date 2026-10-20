#!/usr/bin/env python3
"""
Section C of docs/preseason-signals-test.md (rules and amendments 4 to 8 fixed there before any C result):
is what preseason adds already in the opening prop line?

  nba/.venv/bin/python nba/scripts/build_preseason_market.py     # needs build_preseason_signals.py's inputs; writes data/preseason_market.json

Held-out season: 2025-26 (label 2026), models fit on 2023-24 and 2024-25. First 15 team games, veterans only.
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_preseason_signals as B

RAW, DATA = B.RAW, B.DATA
HELD = 2026
MARKETS = ['pts', 'reb', 'ast', '3pm', 'pra']
GRID = (10, 20, 40, 80, 160, 320, 640)


def fit_minutes(tr):
    tr = tr[(tr.E_gp >= 10)]
    return B.ols(tr[['L_mpg']].values, tr.E_mpg.values), B.ols(tr[['L_mpg', 'mpg_1h']].values, tr.E_mpg.values)


def fit_rate(tr, s):
    L, P1, _ = B.rate_pairs(tr, s)
    y = tr['F_usage'] if s == 'usage' else tr['F_r_' + s]
    ok = (tr.F_min >= 500) & L.notna() & P1.notna() & y.notna()
    L, P1, y, m = L[ok].values, P1[ok].values, y[ok].values, tr.h1_min[ok].values
    best = None
    for k in GRID:
        x = m / (m + k) * (P1 - L)
        b = (x * (y - L)).sum() / (x * x).sum()
        sse = ((L + b * x - y) ** 2).sum()
        if best is None or sse < best[2]:
            best = (k, b, sse)
    return best[0], best[1]


def project(d, S):
    """per-row deltas for season S, models fit on the other seasons only"""
    tr = d[(d.S != S) & (d.L_min >= 400) & (d.box_min >= 40)]
    te = d[(d.S == S) & (d.L_min >= 400) & (d.box_min >= 40)].copy()
    return project_with(tr, te)


def project_with(tr, te):
    """fit on tr (rows with outcomes), project te (rows with preseason + last-season only)"""
    b0, b1 = fit_minutes(tr)
    te['M0'] = np.clip(B.pred(b0, te[['L_mpg']].values), 0, 42)
    te['M1'] = np.clip(B.pred(b1, te[['L_mpg', 'mpg_1h']].values), 0, 42)
    coefs = {'minutes_last': [float(x) for x in b0], 'minutes_last_1h': [float(x) for x in b1]}
    # last-season 3P%, shrunk to 36% with a prior of 100 attempts. Computed BEFORE the rate loop: the loop's
    # 'L_<stat>' per-36 columns would otherwise overwrite the last-season 3PA total this reads (bug fixed 2026-10-20)
    pct0 = (te.L_fg3m + 100 * 0.36) / (te.L_fg3a + 100)
    for s in ('pts', 'reb', 'ast', 'fg3a'):
        k, b = fit_rate(tr, s)
        L, P1, _ = B.rate_pairs(te, s)
        w = te.h1_min / (te.h1_min + k)
        R1 = (L + b * w * (P1 - L)).where(P1.notna(), L)
        te['Lr_' + s], te['R1_' + s] = L, R1
        coefs['rate_' + s] = {'k': k, 'b': float(b)}
    for s in ('pts', 'reb', 'ast'):
        te['d_' + s] = (te.M1 * te['R1_' + s] - te.M0 * te['Lr_' + s]) / 36
        te['mu0_' + s] = te.M0 * te['Lr_' + s] / 36
    te['d_3pm'] = (te.M1 * te.R1_fg3a - te.M0 * te.Lr_fg3a) / 36 * pct0
    te['mu0_3pm'] = te.M0 * te.Lr_fg3a / 36 * pct0
    te['d_pra'] = te.d_pts + te.d_reb + te.d_ast
    te['mu0_pra'] = te.mu0_pts + te.mu0_reb + te.mu0_ast
    # split of the delta: minutes only vs rates only (exploratory)
    for s in ('pts', 'reb', 'ast'):
        te['dm_' + s] = (te.M1 - te.M0) * te['Lr_' + s] / 36
    te['dm_3pm'] = (te.M1 - te.M0) * te.Lr_fg3a / 36 * pct0
    te['dm_pra'] = te.dm_pts + te.dm_reb + te.dm_ast
    return te, coefs


def cluster_ols(y, X, g):
    if X.ndim == 1:
        X = np.column_stack([np.ones(len(X)), X])        # 2-D X must already carry its intercept column
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    G = 0
    for gi in np.unique(g):
        idx = g == gi
        s = X[idx].T @ u[idx]
        meat += np.outer(s, s)
        G += 1
    V = XtXi @ meat @ XtXi * (G / (G - 1))
    return b, np.sqrt(np.diag(V)), G


def main():
    d, _, _ = B.build_table()
    te, coefs = project(d, HELD)
    te = te.set_index('pid')
    p = pd.read_csv(os.path.join(RAW, 'tables', 'props_espn.csv'), dtype={'athlete_id': str})
    p = p[(p.season == HELD) & (p.kind == 'main') & p.market.isin(MARKETS)].copy()
    p = p.sort_values(['game_id', 'athlete_id', 'market', 'book_id', 'last_updated'], ascending=[True, True, True, True, True])
    p = p[p.book_id == 58].drop_duplicates(['game_id', 'athlete_id', 'market'], keep='first')
    rs = B.load_rs(HELD)
    rs['gid'] = rs.game_id.astype('int64')
    gm = rs[['gid', 'pid', 'tgn']].drop_duplicates()
    p = p.merge(gm, left_on=['game_id', 'athlete_id'], right_on=['gid', 'pid'], how='inner')
    p = p[p.tgn <= 15]
    p = p[p.pid.isin(te.index) & (p.played == 1)]
    p = p[(p.actual.notna()) & (p.line_open.notna())]
    out = {'coefs': coefs, 'rows_main_first15_vets': int(len(p)), 'players': int(p.pid.nunique())}
    rows = []
    for mk in MARKETS:
        q = p[p.market == mk].copy()
        q['delta'] = q.pid.map(te['d_' + mk])
        q['delta_min'] = q.pid.map(te['dm_' + mk])
        q['mu0'] = q.pid.map(te['mu0_' + mk])
        rows.append(q)
    q = pd.concat(rows, ignore_index=True)
    q = q[q.delta.notna()].copy()
    q['resid'] = q.actual - q.line_open
    q['rel'] = q.delta / q.line_open
    q['res_rel'] = q.resid / q.line_open
    q['name'] = q.player
    res = {}
    # 1. slope test by market and pooled (relative units)
    sl = {}
    for mk in MARKETS + ['pooled']:
        z = q if mk == 'pooled' else q[q.market == mk]
        if mk == 'pooled':
            y, x = z.res_rel.values, z.rel.values
        else:
            y, x = z.resid.values, z.delta.values
        b, se, G = cluster_ols(y, x, z.pid.values)
        sl[mk] = {'n': int(len(z)), 'players': int(G), 'slope': float(b[1]), 'se': float(se[1]), 't': float(b[1] / se[1]),
                  'mean_delta_abs': float(np.abs(z.delta).mean()), 'sd_delta': float(z.delta.std())}
    res['slope'] = sl
    # pass-through: how much of delta the line already holds (line - mu0 on delta)
    z = q.copy()
    y, x = ((z.line_open - z.mu0) / z.line_open).values, z.rel.values
    b, se, G = cluster_ols(y, x, z.pid.values)
    res['pass_through'] = {'g': float(b[1]), 'se': float(se[1]), 't': float(b[1] / se[1])}
    # minutes-only vs rate-only split (exploratory)
    z = q.copy()
    z['rel_min'] = z.delta_min / z.line_open
    z['rel_rate'] = (z.delta - z.delta_min) / z.line_open
    X = np.column_stack([np.ones(len(z)), z.rel_min.values, z.rel_rate.values])
    b, se, G = cluster_ols(z.res_rel.values, X, z.pid.values)
    res['split'] = {'minutes_slope': float(b[1]), 'minutes_se': float(se[1]), 'rate_slope': float(b[2]),
                    'rate_se': float(se[2]), 'sd_minutes_part': float(z.rel_min.std()), 'sd_rate_part': float(z.rel_rate.std())}
    # 2. betting rule: top third of |delta| / line, side = sign(delta)
    cut = q.rel.abs().quantile(2 / 3)
    bet = q[q.rel.abs() >= cut].copy()
    bet['side'] = np.sign(bet.delta)
    bet['win'] = np.where(bet.actual == bet.line_open, np.nan, np.where((bet.actual > bet.line_open) == (bet.side > 0), 1.0, 0.0))
    dec = bet.dropna(subset=['win'])
    n, w = len(dec), dec.win.sum()
    be = 110 / 210
    zbin = (w / n - be) / np.sqrt(be * (1 - be) / n)
    roi110 = (w * (100 / 110) - (n - w)) / n
    # labeled price (unreliable side labels, reported only)
    def px(r):
        v = r.over_px_open if r.side > 0 else r.under_px_open
        return v
    pxs = dec.apply(px, axis=1)
    def payout(v):
        v = float(v)
        return v / 100 if v > 0 else 100 / abs(v)
    prof = np.array([payout(v) if wv == 1 else -1.0 for v, wv in zip(pxs.fillna(-110), dec.win)])
    res['bet'] = {'n_bets': int(len(bet)), 'n_decided': int(n), 'wins': int(w), 'hit': float(w / n), 'breakeven': be,
                  'z_vs_breakeven': float(zbin), 'roi_flat_110': float(roi110), 'roi_labeled_px': float(prof.mean()),
                  'cut_rel_delta': float(cut), 'players': int(dec.pid.nunique())}
    # by side and market
    bym = {}
    for mk in MARKETS:
        x = dec[dec.market == mk]
        if len(x):
            bym[mk] = {'n': int(len(x)), 'hit': float(x.win.mean())}
    res['bet_by_market'] = bym
    bys = {}
    for sd, nm in ((1, 'over'), (-1, 'under')):
        x = dec[dec.side == sd]
        bys[nm] = {'n': int(len(x)), 'hit': float(x.win.mean())}
    res['bet_by_side'] = bys
    # dose response: hit rate by |rel| tercile among all rows (sign of delta, no top-third cut)
    q2 = q.copy()
    q2['side'] = np.sign(q2.delta)
    q2['win'] = np.where(q2.actual == q2.line_open, np.nan, np.where((q2.actual > q2.line_open) == (q2.side > 0), 1.0, 0.0))
    q2 = q2.dropna(subset=['win'])
    q2['bin'] = pd.qcut(q2.rel.abs(), 3, labels=['low', 'mid', 'high'])
    res['dose'] = {k: {'n': int(len(v)), 'hit': float(v.win.mean())} for k, v in q2.groupby('bin', observed=True)}
    # mean line-relative result in the direction of delta, by tercile
    res['dose_edge'] = {k: float((v.resid * v.side).mean()) for k, v in q2.groupby('bin', observed=True)}
    # ---- exploratory robustness (added AFTER the slope and betting results were seen; see doc amendment 9)
    ex = {}
    q['mu_gap'] = (q.mu0 - q.line_open) / q.line_open
    X = np.column_stack([np.ones(len(q)), q.rel.values, q.mu_gap.values])
    b, se, G = cluster_ols(q.res_rel.values, X, q.pid.values)
    ex['slope_with_mean_reversion_control'] = {'slope': float(b[1]), 'se': float(se[1]), 't': float(b[1] / se[1]),
                                               'control_slope': float(b[2]), 'control_se': float(se[2])}
    allr = q[q.actual != q.line_open]
    ex['baseline_all_rows'] = {'n': int(len(allr)), 'over_hit': float((allr.actual > allr.line_open).mean()),
                               'under_hit': float((allr.actual < allr.line_open).mean()),
                               'pushes': int((q.actual == q.line_open).sum())}
    ex['baseline_by_market'] = {mk: {'n': int(len(x)), 'under_hit': float((x.actual < x.line_open).mean())}
                                for mk, x in allr.groupby('market')}
    # matched baseline: for each decided bet, the under rate for that market on all rows
    ub = dec[dec.side < 0]
    ex['under_bets_vs_market_under_baseline'] = {
        'n': int(len(ub)), 'hit': float(ub.win.mean()),
        'baseline_same_mix': float(np.mean([ex['baseline_by_market'][m]['under_hit'] for m in ub.market]))}
    ob = dec[dec.side > 0]
    ex['over_bets_vs_market_over_baseline'] = {
        'n': int(len(ob)), 'hit': float(ob.win.mean()),
        'baseline_same_mix': float(np.mean([1 - ex['baseline_by_market'][m]['under_hit'] for m in ob.market]))}
    # by player-cluster bootstrap of the bet hit rate
    gp = {pid: np.asarray(ix) for pid, ix in dec.reset_index(drop=True).groupby('pid').indices.items()}
    keys = list(gp)
    wv = dec.win.values
    rng = np.random.default_rng(7)
    bh = []
    for _ in range(2000):
        pick = rng.choice(len(keys), len(keys))
        idx = np.concatenate([gp[keys[i]] for i in pick])
        bh.append(wv[idx].mean())
    ex['bet_hit_cluster_se'] = float(np.std(bh))
    # does the slope fade after the first five games?
    for nm, lo, hi in (('games_1_5', 1, 5), ('games_6_15', 6, 15)):
        z = q[(q.tgn >= lo) & (q.tgn <= hi)]
        b, se, G = cluster_ols(z.res_rel.values, z.rel.values, z.pid.values)
        ex['slope_' + nm] = {'n': int(len(z)), 'slope': float(b[1]), 'se': float(se[1]), 't': float(b[1] / se[1])}
    res['exploratory'] = ex
    out['results'] = res
    # top movers for the live read
    cols = ['name', 'market', 'delta', 'line_open', 'actual']
    out['top_rows'] = bet.assign(side=bet.side).sort_values('rel', key=np.abs, ascending=False)[cols + ['side']].head(15).round(2).to_dict('records')
    with open(os.path.join(DATA, 'preseason_market.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k != 'top_rows'}, indent=1, default=float))


if __name__ == '__main__':
    main()
