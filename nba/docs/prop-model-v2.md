# Prop model v2: backtest against v1

Generated 2026-10-07T00:27Z by `nba/scripts/build_prop_model_v2.py`. Fit on 2024-25, tested on 2025-26,
identical player-games and prices for both models. Lower log loss is better; the market row is the bar to beat.

## Projection accuracy, 2025-26

MAE rewards the median, RMSE the mean; bias = average (projection - actual).

| Stat | MAE v1 | MAE v2 | RMSE v1 | RMSE v2 | Bias v1 | Bias v2 |
|---|---|---|---|---|---|---|
| pts | 4.525 | 4.509 | 5.958 | 5.904 | -0.400 | +0.012 |
| reb | 1.858 | 1.862 | 2.473 | 2.454 | -0.191 | -0.006 |
| ast | 1.320 | 1.325 | 1.813 | 1.793 | -0.145 | -0.010 |
| 3pm | 0.877 | 0.891 | 1.236 | 1.225 | -0.071 | +0.011 |
| pra | 5.950 | 5.917 | 7.718 | 7.625 | -0.736 | -0.004 |
| pr | 5.445 | 5.426 | 7.094 | 7.024 | -0.591 | +0.006 |
| pa | 4.998 | 4.969 | 6.542 | 6.466 | -0.545 | +0.002 |
| ra | 2.553 | 2.555 | 3.370 | 3.332 | -0.336 | -0.016 |

## Kalshi ladder, 2025-26: every strike at its pre-tip price

| Stat | Rows | Log loss market | v1 | v2 | v2 spread only | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|---|
| pts | 18,803 | 0.5291 | 0.5597 | 0.5543 | 0.5590 | 3.55 | 3.78 |
| reb | 14,087 | 0.5618 | 0.5796 | 0.5750 | 0.5780 | 4.33 | 5.38 |
| ast | 10,726 | 0.5405 | 0.5566 | 0.5482 | 0.5556 | 4.78 | 6.96 |
| 3pm | 10,791 | 0.5283 | 0.5392 | 0.5297 | 0.5387 | 6.38 | 6.74 |

## ESPN pre-tip close lines, 2025-26

| Stat | Rows | Log loss market | v1 | v2 | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|
| pts | 884 | 0.6920 | 0.6951 | 0.6967 | 1.24 | 1.24 |
| reb | 901 | 0.6937 | 0.6948 | 0.6955 | 2.43 | 2.41 |
| ast | 811 | 0.6783 | 0.6870 | 0.6812 | 0.26 | 1.17 |
| 3pm | 776 | 0.6715 | 0.6820 | 0.6779 | -0.01 | 0.15 |
| pra | 403 | 0.6913 | 0.7130 | 0.7091 | -1.13 | -0.97 |
| pr | 457 | 0.6911 | 0.6943 | 0.6978 | 0.86 | 0.24 |
| pa | 392 | 0.6902 | 0.7045 | 0.7056 | -0.47 | -0.68 |
| ra | 583 | 0.6900 | 0.6959 | 0.6911 | 1.44 | 2.33 |

## Betting it: blended fair price, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second half, fees in, ROI per dollar risked, z by game.
Price only = the same recalibration with no model (the overs-bias baseline the model has to beat).

| Stat | Side | Price only | v1 blend | v2 blend |
|---|---|---|---|---|
| pts | YES | none | none | +61.6% (1, z 0) |
| pts | NO | +2.2% (5,771, z 1.8) | +2.1% (5,134, z 1.19) | +2.2% (5,290, z 1.43) |
| reb | YES | none | +15.9% (46, z 2.0) | +4.0% (40, z 1.4) |
| reb | NO | none | +3.2% (2,524, z 0.74) | +4.1% (2,653, z 0.41) |
| ast | YES | none | -2.9% (80, z 0.74) | +31.8% (90, z 1.7) |
| ast | NO | none | +4.5% (1,316, z 0.89) | +8.5% (1,599, z 1.37) |
| 3pm | YES | none | +22.6% (4, z 4.34) | +108.5% (6, z 1.65) |
| 3pm | NO | +5.4% (3,832, z 2.3) | +10.2% (3,200, z 3.56) | +8.7% (3,262, z 2.86) |

| Sportsbook stat (ESPN 24-25 fit, 25-26 close test) | v1 ROI (n, z) | v2 ROI (n, z) |
|---|---|---|
| pts | +9.3% (28, z 0.5) | -6.0% (53, z -0.44) |
| reb | +2.2% (636, z 0.37) | +5.1% (635, z 0.87) |
| ast | -4.4% (608, z -0.79) | -3.3% (498, z -0.57) |
| 3pm | +2.0% (706, z 0.35) | +0.8% (478, z 0.13) |
| pra | +2.4% (84, z 0.19) | +11.4% (97, z 0.99) |
| pr | +14.3% (77, z 1.13) | +11.7% (62, z 0.81) |
| pa | -9.8% (45, z -0.62) | +5.6% (66, z 0.42) |
| ra | -3.1% (463, z -0.6) | -0.5% (441, z -0.08) |

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
| pts | +0.366 (+5.8) | +0.073 (+0.5) | +0.195 (+2.3) | +0.310 (+9.4) | +0.439 (+8.6) | +0.013 (+2.1) | -0.007 (-0.9) | +0.043 (+7.2) | +0.005 (+0.1) |
| reb | +0.345 (+6.1) | +0.001 (+0.0) | +0.232 (+2.8) | +0.000 (+0.0) | +0.590 (+11.5) | +0.005 (+0.8) | -0.008 (-0.9) | +0.027 (+4.0) | +0.087 (+2.9) |
| ast | +0.529 (+11.7) | -0.261 (-1.8) | +0.502 (+5.5) | +0.000 (+0.0) | +0.445 (+10.0) | +0.025 (+3.4) | -0.015 (-1.5) | +0.024 (+4.0) | +0.076 (+4.3) |
| 3pm | +0.239 (+4.6) | -0.008 (-0.1) | +0.382 (+3.8) | +0.328 (+10.9) | +0.530 (+11.1) | +0.028 (+2.7) | -0.030 (-2.2) | -0.003 (-0.4) | +0.080 (+6.2) |
