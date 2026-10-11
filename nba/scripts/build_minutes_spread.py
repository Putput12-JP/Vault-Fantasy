#!/usr/bin/env python3
"""
Minutes SPREAD: how wrong is the minutes forecast likely to be for THIS player tonight?

Pricing widens each prop's variance by the player's own minutes volatility (an EWMA of squared misses, pricing.py `sdm`).
That is one number per player. Does a model of the error size do better, using tonight's context (role, rest, blowout risk,
teammates out, form)? Scored with the Gaussian CRPS and negative log-likelihood of the actual minutes, which reward both a
good mean and honest width.

  mean      LightGBM minutes model (build_minutes_gbm.py features); training residuals are out-of-fold by season
  sd models (a) one constant sd, (b) c x the player's EWMA volatility (c fit on train), (c) LightGBM on squared residual
  protocol  train 2022-23..2024-25, test 2025-26; second holdout train 2022-23..2023-24, test 2024-25
  pass rule CRPS of (c) beats (b) by >= 1% on both holdouts, paired t >= 3

  python3 nba/scripts/build_minutes_spread.py      -> docs/minutes-spread.md
"""
import math, os, sys
import numpy as np
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_minutes_gbm as G
import lightgbm as lgb

OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-spread.md')
COLS = ['ew1', 'ew2', 'ew3', 'last', 'm5', 'st', 'was_start', 'rest', 'g7', 'home', 'days_off', 'vs', 'vo', 'absm', 'b2b',
        'pos_g', 'pos_c', 'sd5', 'n', 'sgnm', 'n_out']
MEAN_KW = dict(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=60, subsample=0.8, subsample_freq=1,
               colsample_bytree=0.8, reg_lambda=5.0, verbose=-1)


def crps(y, mu, sd):
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(math.pi))


def main():
    box = C.player_games(G.SEASONS)
    df = G.build_rows(box, MM.expected_margins(box))
    df = df[df.y > 0].reset_index(drop=True)
    L = ['# Minutes spread: per-player error size', '',
         'Gaussian CRPS and negative log-likelihood of actual minutes (lower is better). t = paired on per-row CRPS vs row (b).', '']
    ok = []
    for train, test in (((2023, 2024, 2025), 2026), ((2023, 2024), 2025)):
        tr, te = df[df.season.isin(train)].copy(), df[df.season == test].copy()
        # out-of-fold mean predictions on train, one fold per season
        tr['mu'] = 0.0
        for s in train:
            m = lgb.LGBMRegressor(**MEAN_KW).fit(tr[tr.season != s][COLS], tr[tr.season != s].y)
            tr.loc[tr.season == s, 'mu'] = m.predict(tr[tr.season == s][COLS])
        full = lgb.LGBMRegressor(**MEAN_KW).fit(tr[COLS], tr.y)
        te['mu'] = full.predict(te[COLS])
        tr['e2'] = (tr.y - tr.mu) ** 2
        # (a) constant
        sd_a = math.sqrt(tr.e2.mean())
        # (b) c x EWMA volatility
        c = math.sqrt(tr.e2.mean() / (tr.sdm_ewma ** 2).mean())
        # (c) GBM on squared residual (gamma objective keeps it positive)
        X = COLS + ['mu']
        vm = lgb.LGBMRegressor(objective='gamma', n_estimators=250, learning_rate=0.04, num_leaves=15, min_child_samples=100,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=10.0, verbose=-1)
        vm.fit(tr[X], tr.e2 + 0.25)
        sds = {'(a) one constant sd': np.full(len(te), sd_a),
               '(b) c x player EWMA volatility (shipped idea)': np.maximum(1.5, c * te.sdm_ewma.values),
               '(c) LightGBM on squared miss': np.sqrt(np.maximum(2.25, vm.predict(te[X]) - 0.25))}
        y, mu = te.y.values, te.mu.values
        base = crps(y, mu, sds['(b) c x player EWMA volatility (shipped idea)'])
        L += [f'## Train {train}, test {test}: {len(te):,} player-games, mean RMSE {math.sqrt(((y - mu) ** 2).mean()):.3f}', '',
              '| sd model | CRPS | NLL | 80% interval coverage | t vs (b) |', '|---|---|---|---|---|']
        res = {}
        for name, sd in sds.items():
            cr = crps(y, mu, sd)
            d = base - cr
            t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d))) if d.std() > 0 else 0.0
            cov = (np.abs(y - mu) <= 1.2816 * sd).mean()
            nll = (0.5 * np.log(2 * math.pi * sd ** 2) + 0.5 * ((y - mu) / sd) ** 2).mean()
            res[name] = (cr.mean(), t)
            L.append(f'| {name} | {cr.mean():.4f} | {nll:.4f} | {cov * 100:.1f}% | {t:+.2f} |')
        cb, cc = res['(b) c x player EWMA volatility (shipped idea)'][0], res['(c) LightGBM on squared miss'][0]
        gain, tt = 100 * (1 - cc / cb), res['(c) LightGBM on squared miss'][1]
        ok.append(gain >= 1.0 and tt >= 3)
        L += ['', f'(c) vs (b): CRPS {gain:+.2f}%, t {tt:+.2f}.', '']
    L += [f'Pass rule (CRPS gain >= 1% and t >= 3 on both holdouts): **{"PASS" if all(ok) else "FAIL"}**.', '']
    open(OUT_MD, 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
