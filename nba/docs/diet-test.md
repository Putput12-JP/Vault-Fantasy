# Shot diet score vs v2: pre-registered test

Generated 2026-10-19T14:54Z by `nba/scripts/build_diet_test.py`. Fit on 2024-25, tested on 2025-26,
27,797 identical player-games and prices for every model.

Run 1 was void (no usable prior season for the fit year, so the column was zero); see the script docstring. This is run 2, same rule.

- **v2**: shipped. **v2d**: v2 plus one stacker column per stat, projected mean x the point-in-time shot diet score (zones that held up
  from the prior season's first half to its second). **v2d_ctl**: the control, same column with a random other team's defense.

Rule (fixed before running): the score becomes a pricing input only if v2d keeps every v2 GO at GO with ROI at least v2's, AND its
out-of-sample blended Kalshi log loss beats v2's on at least 3 of 4 stats, AND the control does not. Otherwise it stays display-only.

**Shipped: v2 (diet score stays display-only)** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v2d | RMSE v2d_ctl | MAE v2 | MAE v2d | MAE v2d_ctl | Bias v2 | Bias v2d | Bias v2d_ctl |
|---|---|---|---|---|---|---|---|---|---|
| minutes |  |  |  | 4.922 | 4.922 | 4.922 | 8+ miss 18.8% | 8+ miss 18.8% | 8+ miss 18.8% |
| pts | 5.904 | 5.926 | 5.907 | 4.509 | 4.552 | 4.510 | +0.011 | +0.482 | +0.016 |
| reb | 2.454 | 2.455 | 2.454 | 1.862 | 1.868 | 1.862 | -0.006 | +0.061 | -0.006 |
| ast | 1.793 | 1.795 | 1.793 | 1.325 | 1.333 | 1.325 | -0.010 | +0.069 | -0.009 |
| 3pm | 1.225 | 1.225 | 1.225 | 0.891 | 0.895 | 0.892 | +0.011 | +0.039 | +0.011 |
| pra | 7.625 | 7.652 | 7.628 | 5.918 | 5.960 | 5.917 | -0.004 | +0.612 | +0.001 |
| pr | 7.024 | 7.049 | 7.027 | 5.426 | 5.468 | 5.429 | +0.005 | +0.543 | +0.011 |
| pa | 6.466 | 6.490 | 6.468 | 4.969 | 5.013 | 4.969 | +0.002 | +0.551 | +0.007 |
| ra | 3.332 | 3.335 | 3.332 | 2.555 | 2.568 | 2.555 | -0.016 | +0.130 | -0.015 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v2d | Log score v2d_ctl | Range Brier v2 | Range Brier v2d | Range Brier v2d_ctl |
|---|---|---|---|---|---|---|
| pts | 3.1262 | 3.1292 | 3.1265 | 0.1859 | 0.1872 | 0.1859 |
| reb | 2.1460 | 2.1462 | 2.1459 | 0.1783 | 0.1789 | 0.1783 |
| ast | 1.7422 | 1.7423 | 1.7421 | 0.1819 | 0.1822 | 0.1818 |
| 3pm | 1.2989 | 1.2991 | 1.2991 | 0.1853 | 0.1857 | 0.1854 |
| pra | 3.4055 | 3.4082 | 3.4056 | 0.1686 | 0.1696 | 0.1687 |
| pr | 3.3197 | 3.3224 | 3.3199 | 0.1744 | 0.1750 | 0.1745 |
| pa | 3.2228 | 3.2256 | 3.2230 | 0.1770 | 0.1783 | 0.1770 |
| ra | 2.5657 | 2.5663 | 2.5656 | 0.1711 | 0.1714 | 0.1711 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | 18,803 | 0.5291 | 0.5543 (3.78) | 0.5598 (3.64) | 0.5551 (3.78) |
| reb | 14,087 | 0.5618 | 0.5750 (5.39) | 0.5760 (5.13) | 0.5749 (5.41) |
| ast | 10,726 | 0.5405 | 0.5482 (6.98) | 0.5487 (7.35) | 0.5480 (7.11) |
| 3pm | 10,791 | 0.5283 | 0.5294 (6.75) | 0.5302 (6.97) | 0.5295 (6.92) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v2d | v2d_ctl |
|---|---|---|---|---|
| pts | 0.51072 | 0.50796 | 0.50796 | 0.50794 |
| reb | 0.55363 | 0.55182 | 0.55185 | 0.55179 |
| ast | 0.53192 | 0.52737 | 0.52670 | 0.52731 |
| 3pm | 0.51195 | 0.50573 | 0.50548 | 0.50563 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | 884 | 0.6920 | 0.6967 (1.24) | 0.6973 (1.38) | 0.6976 (1.06) |
| reb | 901 | 0.6937 | 0.6955 (2.4) | 0.6957 (2.33) | 0.6955 (2.4) |
| ast | 811 | 0.6783 | 0.6813 (1.15) | 0.6820 (1.17) | 0.6810 (1.23) |
| 3pm | 776 | 0.6715 | 0.6778 (0.18) | 0.6778 (0.19) | 0.6772 (0.33) |
| pra | 403 | 0.6913 | 0.7091 (-0.97) | 0.7107 (-1.06) | 0.7098 (-1.09) |
| pr | 457 | 0.6911 | 0.6978 (0.23) | 0.6982 (0.31) | 0.6983 (0.19) |
| pa | 392 | 0.6902 | 0.7056 (-0.69) | 0.7062 (-0.6) | 0.7073 (-0.85) |
| ra | 583 | 0.6900 | 0.6910 (2.35) | 0.6909 (2.3) | 0.6906 (2.44) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | YES | none | +61.6% (1, z 0) | +61.6% (1, z 0) | +61.6% (1, z 0) |
| pts | NO | +2.2% (5,771, z 1.8) | +2.2% (5,291, z 1.48) | +3.1% (5,372, z 1.85) | +2.4% (5,341, z 1.48) |
| reb | YES | none | +4.0% (40, z 1.4) | +4.6% (30, z 0.74) | +6.7% (39, z 1.48) |
| reb | NO | none | +4.2% (2,659, z 0.51) | +3.9% (2,615, z 0.58) | +4.3% (2,644, z 0.67) |
| ast | YES | none | +35.4% (94, z 1.8) | +23.1% (99, z 1.46) | +28.4% (114, z 1.85) |
| ast | NO | none | +8.4% (1,611, z 1.59) | +10.0% (1,622, z 1.87) | +8.7% (1,618, z 1.92) |
| 3pm | YES | none | +146.8% (7, z 1.87) | +117.5% (9, z 1.85) | +108.3% (10, z 1.71) |
| 3pm | NO | +5.4% (3,832, z 2.3) | +8.6% (3,269, z 2.9) | +9.8% (3,246, z 3.25) | +9.0% (3,271, z 2.82) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v2d | v2d_ctl |
|---|---|---|---|
| pts | -6.0% (53, z -0.44) | +2.2% (67, z 0.19) | -8.6% (62, z -0.67) |
| reb | +5.4% (632, z 0.92) | +4.2% (626, z 0.73) | +5.5% (629, z 0.96) |
| ast | -3.6% (502, z -0.63) | -4.7% (490, z -0.77) | -3.4% (504, z -0.58) |
| 3pm | +2.2% (484, z 0.37) | +0.4% (464, z 0.06) | +2.1% (476, z 0.35) |
| pra | +11.4% (97, z 0.99) | -0.4% (82, z -0.03) | +8.7% (91, z 0.74) |
| pr | +13.6% (63, z 0.96) | +4.1% (80, z 0.33) | +12.0% (64, z 0.85) |
| pa | +5.6% (65, z 0.42) | +0.4% (58, z 0.03) | -1.3% (61, z -0.1) |
| ra | -0.3% (440, z -0.06) | -0.2% (439, z -0.04) | -0.9% (440, z -0.16) |

## Gates

| Stat | v2 | v2d | v2d_ctl |
|---|---|---|---|
| pts | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO |

Coverage (player-games with a diet score / all): {'2025': '25,444 / 27,355', '2026': '25,755 / 27,799'}. Related: [courtai-teardown.md](courtai-teardown.md), [prop-model-v3-full.md](prop-model-v3-full.md).

## The diet column in the stacker (fit on 2024-25)

Score sd 0.0687 (a fraction: 0.01 = one percent more shots than average in his spots). Coefficient is on projected mean x score; t is the fit-season t.

| Stat | v2d coef (t) | control coef (t) |
|---|---|---|
| pts | +0.458 (5.13) | -0.097 (-1.21) |
| reb | +0.174 (2.05) | -0.020 (-0.26) |
| ast | +0.341 (3.44) | -0.044 (-0.48) |
| 3pm | +0.240 (2.1) | +0.054 (0.5) |

## Rule

1. v2d keeps every v2 GO at GO with ROI at least v2's: **True**.
2. v2d beats v2's blended Kalshi log loss on 2 of 4 stats (need 3).
3. The control beats v2 on 4 of 4 stats (must be under 3).

**Result: v2 (diet score stays display-only).**
