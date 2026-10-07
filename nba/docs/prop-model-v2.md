# Prop model v2: backtest against v1

Generated 2026-10-07T01:03Z by `nba/scripts/build_prop_model_v2.py`. Fit on 2024-25, tested on 2025-26,
identical player-games and prices for both models. Lower log loss is better; the market row is the bar to beat.

## Projection accuracy, 2025-26

MAE rewards the median, RMSE the mean; bias = average (projection - actual).

| Stat | MAE v1 | MAE v2 | RMSE v1 | RMSE v2 | Bias v1 | Bias v2 |
|---|---|---|---|---|---|---|
| pts | 4.549 | 4.509 | 5.942 | 5.904 | +0.146 | +0.011 |
| reb | 1.870 | 1.862 | 2.467 | 2.454 | +0.013 | -0.006 |
| ast | 1.329 | 1.324 | 1.806 | 1.793 | -0.022 | -0.010 |
| 3pm | 0.885 | 0.891 | 1.235 | 1.225 | -0.010 | +0.011 |
| pra | 5.960 | 5.917 | 7.678 | 7.625 | +0.138 | -0.004 |
| pr | 5.465 | 5.426 | 7.069 | 7.024 | +0.160 | +0.005 |
| pa | 5.011 | 4.969 | 6.511 | 6.465 | +0.124 | +0.002 |
| ra | 2.566 | 2.555 | 3.355 | 3.331 | -0.008 | -0.016 |

## Kalshi ladder, 2025-26: every strike at its pre-tip price

| Stat | Rows | Log loss market | v1 | v2 | v2 spread only | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|---|
| pts | 18,803 | 0.5291 | 0.5599 | 0.5543 | 0.5593 | 3.28 | 3.78 |
| reb | 14,087 | 0.5618 | 0.5804 | 0.5750 | 0.5787 | 4.13 | 5.39 |
| ast | 10,726 | 0.5405 | 0.5567 | 0.5482 | 0.5567 | 4.82 | 6.98 |
| 3pm | 10,791 | 0.5283 | 0.5395 | 0.5294 | 0.5392 | 6.32 | 6.75 |

## ESPN pre-tip close lines, 2025-26

| Stat | Rows | Log loss market | v1 | v2 | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|
| pts | 884 | 0.6920 | 0.6959 | 0.6967 | 1.19 | 1.24 |
| reb | 901 | 0.6937 | 0.6942 | 0.6955 | 2.41 | 2.4 |
| ast | 811 | 0.6783 | 0.6881 | 0.6813 | 0.32 | 1.15 |
| 3pm | 776 | 0.6715 | 0.6824 | 0.6778 | -0.08 | 0.18 |
| pra | 403 | 0.6913 | 0.7151 | 0.7091 | -1.49 | -0.97 |
| pr | 457 | 0.6911 | 0.6954 | 0.6978 | 0.69 | 0.24 |
| pa | 392 | 0.6902 | 0.7057 | 0.7056 | -0.53 | -0.69 |
| ra | 583 | 0.6900 | 0.6954 | 0.6910 | 1.47 | 2.35 |

## Betting it: blended fair price, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second half, fees in, ROI per dollar risked, z by game.
Price only = the same recalibration with no model (the overs-bias baseline the model has to beat).

| Stat | Side | Price only | v1 blend | v2 blend |
|---|---|---|---|---|
| pts | YES | none | none | +61.6% (1, z 0) |
| pts | NO | +2.2% (5,771, z 1.8) | +2.0% (5,275, z 1.36) | +2.2% (5,290, z 1.43) |
| reb | YES | none | +13.8% (48, z 1.96) | +4.0% (40, z 1.4) |
| reb | NO | none | +2.8% (2,574, z 0.44) | +4.2% (2,659, z 0.51) |
| ast | YES | none | -14.0% (82, z -0.07) | +35.4% (94, z 1.8) |
| ast | NO | none | +3.6% (1,323, z -0.01) | +8.4% (1,611, z 1.59) |
| 3pm | YES | none | +22.6% (4, z 4.34) | +146.8% (7, z 1.87) |
| 3pm | NO | +5.4% (3,832, z 2.3) | +9.8% (3,201, z 3.4) | +8.6% (3,269, z 2.9) |

| Sportsbook stat (ESPN 24-25 fit, 25-26 close test) | v1 ROI (n, z) | v2 ROI (n, z) |
|---|---|---|
| pts | +3.5% (34, z 0.21) | -6.0% (53, z -0.44) |
| reb | +4.2% (633, z 0.72) | +5.4% (632, z 0.92) |
| ast | -3.3% (616, z -0.59) | -3.6% (502, z -0.63) |
| 3pm | +3.2% (708, z 0.56) | +2.2% (484, z 0.37) |
| pra | -4.5% (88, z -0.35) | +11.4% (97, z 0.99) |
| pr | +12.3% (82, z 1.02) | +13.6% (63, z 0.96) |
| pa | -16.7% (47, z -1.1) | +5.6% (65, z 0.42) |
| ra | -3.8% (462, z -0.72) | -0.3% (440, z -0.06) |

## Gates (Kalshi blend vs the price-only baseline)

| Stat | v1 | v2 |
|---|---|---|
| pts | NO-GO | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) |
| ast | WATCH (NO) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO |
| pr | NO-GO | NO-GO |
| pa | NO-GO | NO-GO |
| ra | NO-GO | NO-GO |

## What the stacker learned (fit on 2024-25; t in brackets)

Each weight multiplies a feature already in stat units, so 1.0 means "take the adjustment at face value".

| Stat | opp | pace | market | shooting | season | home | b2b | scale | const |
|---|---|---|---|---|---|---|---|---|---|
| pts | +0.348 (+5.8) | +0.070 (+0.5) | +0.185 (+2.3) | +0.295 (+9.4) | +0.417 (+8.6) | +0.012 (+2.1) | -0.007 (-0.9) | -0.009 (-1.7) | +0.004 (+0.1) |
| reb | +0.328 (+6.1) | -0.000 (-0.0) | +0.222 (+2.8) | +0.000 (+0.0) | +0.562 (+11.5) | +0.005 (+0.8) | -0.007 (-0.9) | -0.025 (-4.0) | +0.087 (+2.9) |
| ast | +0.503 (+11.7) | -0.261 (-1.8) | +0.484 (+5.5) | +0.000 (+0.0) | +0.424 (+10.0) | +0.024 (+3.4) | -0.014 (-1.5) | -0.027 (-4.7) | +0.076 (+4.3) |
| 3pm | +0.228 (+4.5) | -0.013 (-0.1) | +0.374 (+3.9) | +0.312 (+10.9) | +0.506 (+11.1) | +0.026 (+2.7) | -0.028 (-2.2) | -0.053 (-6.3) | +0.079 (+6.2) |
