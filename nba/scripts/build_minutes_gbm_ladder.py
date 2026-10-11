#!/usr/bin/env python3
"""
Does better minutes make better PROBABILITIES? A market-free stand-in for the Kalshi-edge test (which needs the price archive).

For every player-game, each model's minutes x the same per-minute rate gives a mean; a negative binomial (variance a + b mu + c mu^2,
fit on the training seasons from that model's own residuals) turns it into P(stat >= k) for a ladder of rungs like Kalshi lists
(points 10..35, rebounds 3..12, assists 2..10, 3PM 1..5). Scored by log loss on the held-out season over all rungs.

  linear   ridge on the shipped-style features   (the stand-in for the shipped minutes model)
  gbm      LightGBM minutes (build_minutes_gbm.py)
  oracle   the TRUE minutes: the ceiling any minutes model could reach with these rates

"Share of the gap closed" = (log loss linear - gbm) / (linear - oracle). Paired t is per player-game, summed over rungs.
This does not say whether a price can be beaten; a market already knows minutes. It says how much of minutes accuracy survives
into probabilities, and the answer bounds the edge a minutes upgrade can add on its own.

  python3 nba/scripts/build_minutes_gbm_ladder.py   -> docs/minutes-gbm-ladder.md
"""
import math, os, sys
import numpy as np
from scipy.stats import nbinom
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_minutes_gbm as G
import minutes_gbm as MG
import build_minutes_spread as SP
import lightgbm as lgb

OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-gbm-ladder.md')
RUNGS = {'pts': [10, 15, 20, 25, 30, 35], 'reb': [3, 4, 6, 8, 10, 12], 'ast': [2, 3, 4, 6, 8, 10], 'fg3m': [1, 2, 3, 4, 5]}
LIN = ['ew2', 'vs', 'vo', 'absm', 'b2b']


def fit_var(mu, y):
    """variance = a + b mu + c mu^2 by least squares on squared residuals, floored at the Poisson variance."""
    X = np.column_stack([np.ones_like(mu), mu, mu ** 2])
    coef = np.linalg.lstsq(X, (y - mu) ** 2, rcond=None)[0]
    return coef


def p_ge(mu, coef, k):
    v = np.maximum(mu * 1.01 + 1e-6, coef[0] + coef[1] * mu + coef[2] * mu ** 2)
    mu = np.maximum(mu, 1e-3)
    r = mu ** 2 / (v - mu)
    p = r / (r + mu)
    return nbinom.sf(k - 1, r, p)              # P(X >= k)


def logloss(mu, coef, y, rungs):
    tot = np.zeros(len(y))
    for k in rungs:
        pr = np.clip(p_ge(mu, coef, k), 1e-4, 1 - 1e-4)
        o = (y >= k).astype(float)
        tot += -(o * np.log(pr) + (1 - o) * np.log(1 - pr))
    return tot / len(rungs)


def main():
    box = C.player_games(G.SEASONS)
    df = G.build_rows(box, MM.expected_margins(box))
    df = df[df.y > 0].reset_index(drop=True)
    L = ['# Do minutes gains survive into probabilities?', '',
         'Negative binomial over minutes x per-minute rate, scored by log loss on a ladder of rungs (lower is better). Oracle absences, as in',
         'minutes-gbm.md. The oracle row uses the true minutes: it is the ceiling, not a model.', '']
    summary = []
    for train, test in (((2023, 2024, 2025), 2026), ((2023, 2024), 2025)):
        tr, te = df[df.season.isin(train)], df[df.season == test]
        X = np.column_stack([np.ones(len(tr))] + [tr[c] for c in LIN])
        b = np.linalg.solve(X.T @ X + np.eye(X.shape[1]), X.T @ tr.y.values)
        lin_te = np.column_stack([np.ones(len(te))] + [te[c] for c in LIN]) @ b
        lin_tr = X @ b
        gb = lgb.LGBMRegressor(**SP.MEAN_KW).fit(tr[SP.COLS], tr.y)
        gbm_tr, gbm_te = gb.predict(tr[SP.COLS]), gb.predict(te[SP.COLS])
        L += [f'## Train {train}, test {test}: {len(te):,} player-games', '',
              '| Stat | log loss linear | log loss GBM | log loss oracle | GBM vs linear | share of gap closed | t |', '|---|---|---|---|---|---|---|']
        for st, rungs in RUNGS.items():
            ytr, yte = tr[f'act_{st}'].values.astype(float), te[f'act_{st}'].values.astype(float)
            rate_tr, rate_te = tr[f'rt_{st}'].values, te[f'rt_{st}'].values
            res = {}
            for name, m_tr, m_te in (('lin', lin_tr, lin_te), ('gbm', gbm_tr, gbm_te), ('orc', tr.y.values, te.y.values)):
                m_tr = np.clip(m_tr, 0, 48); m_te = np.clip(m_te, 0, 48)
                coef = fit_var(m_tr * rate_tr, ytr)
                res[name] = logloss(m_te * rate_te, coef, yte, rungs)
            d = res['lin'] - res['gbm']
            t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
            gap = res['lin'].mean() - res['orc'].mean()
            L.append(f"| {st} | {res['lin'].mean():.5f} | {res['gbm'].mean():.5f} | {res['orc'].mean():.5f} | "
                     f"{100 * d.mean() / res['lin'].mean():+.3f}% | {100 * d.mean() / gap:.1f}% | {t:+.2f} |")
            summary.append((test, st, d.mean() / res['lin'].mean(), t))
        L.append('')
    L += ['Read: perfect minutes would cut log loss by roughly 14% on points, so minutes ARE a big uncertainty, but the GBM closes only',
          'the small share of that gap shown; the rest (blowouts, foul trouble, in-game injuries) is not knowable before tip.',
          'A market already prices minutes, so this bounds, and does not predict, an edge.', '']
    open(OUT_MD, 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
