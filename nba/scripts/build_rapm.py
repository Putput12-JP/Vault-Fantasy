#!/usr/bin/env python3
"""
Ridge RAPM (regularised adjusted plus-minus) from play-by-play stints. A free, public stand-in for the impact
ratings DARKO / EPM / LEBRON sell. See docs/reverse-engineering-targets.md.

Model: each stint gives two rows, one per side. y = points per 100 possessions scored by the side on offence;
x = +1 for each of its 5 players in the OFF block, +1 for each of the 5 opposing players in the DEF block;
weight = possessions. Ridge pulls every player to 0 (league average). Offence rating = OFF coef, defence rating =
-DEF coef (higher is better for both), total = off + def.

Validation (the only thing that matters): fit on seasons A, correlate with an independent fit on season B,
and check the lambda by predicting held-out stints' points per possession.

  python3 nba/scripts/build_rapm.py --fit 2023 2024 --test 2025 [--lam 3000]
  python3 nba/scripts/build_rapm.py --fit 2023 2024 2025 --out nba/data/rapm.json     # publish current ratings
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STINTS = os.path.join(HERE, '..', 'raw', 'stints_2023_2025.csv')


def rows(df, idx):
    """Two rows per stint -> (cols list per row, y per 100, weight)."""
    out_c, y, w = [], [], []
    for h5, a5, hp, ap, hq, aq in zip(df.home5, df.away5, df.home_pts, df.away_pts, df.home_poss, df.away_poss):
        h, a = [idx[p] for p in h5.split()], [idx[p] for p in a5.split()]
        if hq >= 0.5:
            out_c.append((h, a)); y.append(100.0 * hp / hq); w.append(hq)
        if aq >= 0.5:
            out_c.append((a, h)); y.append(100.0 * ap / aq); w.append(aq)
    return out_c, np.array(y), np.array(w)


def design(cols, n):
    X = np.zeros((len(cols), 2 * n), dtype=np.float32)
    for i, (off, de) in enumerate(cols):
        X[i, off] = 1.0
        X[i, [n + j for j in de]] = 1.0
    return X


def fit(df, players, lam):
    idx = {p: i for i, p in enumerate(players)}
    n = len(players)
    cols, y, w = rows(df, idx)
    mu = float(np.average(y, weights=w))
    A = np.zeros((2 * n + 1, 2 * n + 1))
    b = np.zeros(2 * n + 1)
    for s in range(0, len(cols), 20000):
        X = design(cols[s:s + 20000], n)
        X = np.hstack([X, np.ones((len(X), 1), dtype=np.float32)])
        ww = w[s:s + 20000]
        Xw = X * ww[:, None]
        A += Xw.T @ X
        b += Xw.T @ (y[s:s + 20000])
    R = np.eye(2 * n + 1) * lam
    R[-1, -1] = 0.0
    beta = np.linalg.solve(A + R, b)
    return beta, idx, mu


def score(beta, idx, df, n):
    """Weighted RMSE of held-out stints; skips stints with unseen players (treated as 0 coef)."""
    cols, y, w = rows(df, {**idx})
    return cols, y, w


def predict_rmse(beta, idx_fit, df_test, lam_name=''):
    n = len(idx_fit)
    err = tot = 0.0
    for h5, a5, hp, ap, hq, aq in zip(df_test.home5, df_test.away5, df_test.home_pts, df_test.away_pts, df_test.home_poss, df_test.away_poss):
        h = [idx_fit.get(p) for p in h5.split()]
        a = [idx_fit.get(p) for p in a5.split()]
        for off, de, pts, q in ((h, a, hp, hq), (a, h, ap, aq)):
            if q < 3:
                continue
            pred = beta[-1] + sum(beta[i] for i in off if i is not None) + sum(beta[n + j] for j in de if j is not None)
            err += q * (100.0 * pts / q - pred) ** 2
            tot += q
    return (err / tot) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit', type=int, nargs='+', required=True)
    ap.add_argument('--test', type=int, nargs='*', default=[])
    ap.add_argument('--lam', type=float, nargs='*', default=[1500, 3000, 6000, 12000])
    ap.add_argument('--out')
    a = ap.parse_args()
    d = pd.read_csv(STINTS, dtype={'home5': str, 'away5': str})
    fit_df = d[d.season.isin(a.fit)]
    players = sorted({p for s in pd.concat([fit_df.home5, fit_df.away5]) for p in s.split()})
    print(f'{len(fit_df)} stints, {len(players)} players', file=sys.stderr)
    best = None
    for lam in a.lam:
        beta, idx, mu = fit(fit_df, players, lam)
        if a.test:
            te = d[d.season.isin(a.test)]
            r = predict_rmse(beta, idx, te)
            base = predict_rmse(np.concatenate([np.zeros(2 * len(idx)), [mu]]), idx, te)
            print(f'lam {lam:>7}: held-out RMSE {r:.3f}  vs constant {base:.3f}  ({(1 - r / base) * 100:+.2f}%)')
            if best is None or r < best[0]:
                best = (r, lam, beta, idx, mu)
        else:
            best = (0, lam, beta, idx, mu)
    _, lam, beta, idx, mu = best
    n = len(idx)
    inv = {i: p for p, i in idx.items()}
    res = {inv[i]: dict(off=round(float(beta[i]), 2), dfn=round(-float(beta[n + i]), 2)) for i in range(n)}
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
        json.dump(dict(lam=lam, fit=a.fit, mu=round(mu, 2), players=res), open(a.out, 'w'), separators=(',', ':'))
        print('wrote', a.out, file=sys.stderr)
    top = sorted(res.items(), key=lambda kv: -(kv[1]['off'] + kv[1]['dfn']))[:8]
    print('lam', lam, 'top total:', [(p, v['off'] + v['dfn']) for p, v in top])


if __name__ == '__main__':
    main()
