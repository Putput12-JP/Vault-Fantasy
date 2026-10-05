# Prop model v2: backtest against v1

Generated 2026-10-05T11:38Z by `nba/scripts/build_prop_model_v2.py`. Fit on 2024-25, tested on 2025-26,
identical player-games and prices for both models. Lower log loss is better; the market row is the bar to beat.

## Projection accuracy, 2025-26

MAE rewards the median, RMSE the mean; bias = average (projection - actual).

| Stat | MAE v1 | MAE v2 | RMSE v1 | RMSE v2 | Bias v1 | Bias v2 |
|---|---|---|---|---|---|---|
| pts | 4.514 | 4.490 | 5.921 | 5.879 | -0.099 | +0.088 |
| reb | 1.862 | 1.863 | 2.464 | 2.451 | -0.076 | +0.024 |
| ast | 1.321 | 1.323 | 1.806 | 1.791 | -0.075 | +0.007 |
| 3pm | 0.879 | 0.890 | 1.233 | 1.223 | -0.036 | +0.020 |
| pra | 5.921 | 5.890 | 7.650 | 7.589 | -0.250 | +0.120 |
| pr | 5.428 | 5.406 | 7.043 | 6.995 | -0.175 | +0.112 |
| pa | 4.976 | 4.944 | 6.487 | 6.432 | -0.174 | +0.095 |
| ra | 2.556 | 2.555 | 3.351 | 3.326 | -0.151 | +0.032 |

## Kalshi ladder, 2025-26: every strike at its pre-tip price

| Stat | Rows | Log loss market | v1 | v2 | v2 spread only | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|---|
| pts | 18,840 | 0.5290 | 0.5580 | 0.5504 | 0.5571 | 3.56 | 3.95 |
| reb | 14,117 | 0.5621 | 0.5785 | 0.5737 | 0.5771 | 4.11 | 5.11 |
| ast | 10,742 | 0.5405 | 0.5566 | 0.5477 | 0.5564 | 4.19 | 6.29 |
| 3pm | 10,814 | 0.5281 | 0.5387 | 0.5285 | 0.5393 | 6.5 | 6.64 |

## ESPN pre-tip close lines, 2025-26

| Stat | Rows | Log loss market | v1 | v2 | Blend t v1 | Blend t v2 |
|---|---|---|---|---|---|---|
| pts | 906 | 0.6922 | 0.6972 | 0.6960 | 1.05 | 1.31 |
| reb | 911 | 0.6930 | 0.6934 | 0.6921 | 2.16 | 2.5 |
| ast | 816 | 0.6784 | 0.6858 | 0.6813 | 0.67 | 1.21 |
| 3pm | 781 | 0.6714 | 0.6827 | 0.6779 | -0.24 | -0.09 |
| pra | 403 | 0.6913 | 0.7073 | 0.7019 | -0.59 | -0.15 |
| pr | 458 | 0.6912 | 0.6926 | 0.6956 | 1.21 | 0.56 |
| pa | 392 | 0.6902 | 0.6991 | 0.7008 | 0.35 | -0.14 |
| ra | 583 | 0.6900 | 0.6951 | 0.6904 | 1.25 | 2.13 |

## Betting it: blended fair price, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second half, fees in, ROI per dollar risked, z by game.
Price only = the same recalibration with no model (the overs-bias baseline the model has to beat).

| Stat | Side | Price only | v1 blend | v2 blend |
|---|---|---|---|---|
| pts | YES | none | -100.0% (1, z 0) | +33.2% (3, z 0) |
| pts | NO | +2.1% (5,703, z 1.76) | +2.8% (4,966, z 1.51) | +3.5% (5,023, z 2.11) |
| reb | YES | none | +25.4% (47, z 2.89) | +12.5% (29, z 1.81) |
| reb | NO | none | +1.3% (2,271, z 0.47) | +5.4% (2,341, z 0.33) |
| ast | YES | none | +7.7% (38, z 1.19) | +13.6% (65, z 1.52) |
| ast | NO | none | +4.2% (1,072, z 0.72) | +7.3% (1,387, z 1.46) |
| 3pm | YES | none | +24.1% (7, z 5.34) | +44.3% (20, z 1.13) |
| 3pm | NO | +5.1% (3,836, z 2.26) | +11.4% (3,181, z 3.69) | +9.4% (3,200, z 3.53) |

| Sportsbook stat (ESPN 24-25 fit, 25-26 close test) | v1 ROI (n, z) | v2 ROI (n, z) |
|---|---|---|
| pts | +13.4% (31, z 0.78) | -6.1% (68, z -0.5) |
| reb | +5.0% (607, z 0.86) | +7.5% (633, z 1.34) |
| ast | +0.1% (554, z 0.02) | -2.9% (450, z -0.47) |
| 3pm | +4.5% (726, z 0.78) | +0.2% (438, z 0.03) |
| pra | -6.6% (65, z -0.48) | +10.8% (77, z 0.86) |
| pr | +15.0% (48, z 1.01) | +7.5% (58, z 0.53) |
| pa | -11.5% (25, z -0.58) | +2.3% (36, z 0.14) |
| ra | -1.3% (455, z -0.27) | +2.5% (434, z 0.46) |

## Gates (Kalshi blend vs the price-only baseline)

| Stat | v1 | v2 |
|---|---|---|
| pts | WATCH (NO) | GO (NO) |
| reb | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO |
| pr | NO-GO | NO-GO |
| pa | NO-GO | NO-GO |
| ra | NO-GO | NO-GO |

## What the stacker learned (fit on 2024-25; t in brackets)

Each weight multiplies a feature already in stat units, so 1.0 means "take the adjustment at face value".

| Stat | opp | pace | market | shooting | season | home | b2b | scale | const |
|---|---|---|---|---|---|---|---|---|---|
| pts | +0.375 (+6.1) | +0.023 (+0.1) | +0.192 (+2.4) | +0.269 (+8.5) | +0.494 (+9.9) | +0.017 (+2.8) | -0.001 (-0.1) | +0.027 (+4.7) | -0.087 (-1.3) |
| reb | +0.341 (+6.2) | -0.015 (-0.1) | +0.228 (+2.9) | +0.000 (+0.0) | +0.595 (+11.8) | +0.009 (+1.4) | -0.003 (-0.4) | +0.008 (+1.2) | +0.071 (+2.4) |
| ast | +0.522 (+11.9) | -0.319 (-2.2) | +0.491 (+5.5) | +0.000 (+0.0) | +0.453 (+10.4) | +0.029 (+4.0) | -0.009 (-0.9) | +0.004 (+0.7) | +0.067 (+3.9) |
| 3pm | +0.242 (+4.7) | -0.030 (-0.2) | +0.385 (+4.0) | +0.298 (+10.3) | +0.556 (+11.9) | +0.028 (+2.8) | -0.022 (-1.7) | -0.023 (-2.6) | +0.075 (+6.0) |
