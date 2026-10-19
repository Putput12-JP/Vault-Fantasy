# Shot diet score vs v2: pre-registered test

Generated 2026-10-19T14:56Z by `nba/scripts/build_diet_test.py`. Fit on 2024-25, tested on 2025-26,
27,797 identical player-games and prices for every model.

Run 1 was void (no usable prior season for the fit year, so the column was zero); see the script docstring. The pre-registered result is run 2 (diet-test.md); this file is the --no-prior SENSITIVITY run: the fit and test seasons share one definition (current season only, all five zones, a defense counts after 15 games).

- **v2**: shipped. **v2d**: v2 plus one stacker column per stat, projected mean x the point-in-time shot diet score (zones that held up
  from the prior season's first half to its second). **v2d_ctl**: the control, same column with a random other team's defense.

Rule (fixed before running): the score becomes a pricing input only if v2d keeps every v2 GO at GO with ROI at least v2's, AND its
out-of-sample blended Kalshi log loss beats v2's on at least 3 of 4 stats, AND the control does not. Otherwise it stays display-only.

**Shipped: v2 (diet score stays display-only)** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v2d | RMSE v2d_ctl | MAE v2 | MAE v2d | MAE v2d_ctl | Bias v2 | Bias v2d | Bias v2d_ctl |
|---|---|---|---|---|---|---|---|---|---|
| minutes |  |  |  | 4.922 | 4.922 | 4.922 | 8+ miss 18.8% | 8+ miss 18.8% | 8+ miss 18.8% |
| pts | 5.904 | 5.902 | 5.904 | 4.509 | 4.508 | 4.510 | +0.011 | +0.012 | +0.012 |
| reb | 2.454 | 2.454 | 2.454 | 1.862 | 1.862 | 1.862 | -0.006 | -0.006 | -0.006 |
| ast | 1.793 | 1.793 | 1.793 | 1.325 | 1.324 | 1.325 | -0.010 | -0.010 | -0.010 |
| 3pm | 1.225 | 1.225 | 1.225 | 0.891 | 0.891 | 0.891 | +0.011 | +0.011 | +0.011 |
| pra | 7.625 | 7.623 | 7.626 | 5.918 | 5.915 | 5.918 | -0.004 | -0.004 | -0.004 |
| pr | 7.024 | 7.022 | 7.025 | 5.426 | 5.424 | 5.427 | +0.005 | +0.006 | +0.006 |
| pa | 6.466 | 6.463 | 6.466 | 4.969 | 4.968 | 4.969 | +0.002 | +0.003 | +0.002 |
| ra | 3.332 | 3.331 | 3.332 | 2.555 | 2.555 | 2.555 | -0.016 | -0.016 | -0.016 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v2d | Log score v2d_ctl | Range Brier v2 | Range Brier v2d | Range Brier v2d_ctl |
|---|---|---|---|---|---|---|
| pts | 3.1262 | 3.1260 | 3.1263 | 0.1859 | 0.1859 | 0.1859 |
| reb | 2.1460 | 2.1459 | 2.1460 | 0.1783 | 0.1785 | 0.1783 |
| ast | 1.7422 | 1.7420 | 1.7422 | 0.1819 | 0.1817 | 0.1819 |
| 3pm | 1.2989 | 1.2989 | 1.2989 | 0.1853 | 0.1854 | 0.1853 |
| pra | 3.4055 | 3.4052 | 3.4056 | 0.1686 | 0.1684 | 0.1687 |
| pr | 3.3197 | 3.3195 | 3.3198 | 0.1744 | 0.1742 | 0.1745 |
| pa | 3.2228 | 3.2225 | 3.2229 | 0.1770 | 0.1770 | 0.1771 |
| ra | 2.5657 | 2.5656 | 2.5657 | 0.1711 | 0.1712 | 0.1711 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | 18,803 | 0.5291 | 0.5543 (3.78) | 0.5544 (3.76) | 0.5546 (3.74) |
| reb | 14,087 | 0.5618 | 0.5750 (5.39) | 0.5753 (5.41) | 0.5749 (5.39) |
| ast | 10,726 | 0.5405 | 0.5482 (6.98) | 0.5477 (7.04) | 0.5482 (6.95) |
| 3pm | 10,791 | 0.5283 | 0.5294 (6.75) | 0.5297 (6.71) | 0.5296 (6.82) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v2d | v2d_ctl |
|---|---|---|---|---|
| pts | 0.51072 | 0.50796 | 0.50797 | 0.50797 |
| reb | 0.55363 | 0.55182 | 0.55177 | 0.55182 |
| ast | 0.53192 | 0.52737 | 0.52736 | 0.52737 |
| 3pm | 0.51195 | 0.50573 | 0.50574 | 0.50561 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | 884 | 0.6920 | 0.6967 (1.24) | 0.6962 (1.21) | 0.6964 (1.27) |
| reb | 901 | 0.6937 | 0.6955 (2.4) | 0.6960 (2.3) | 0.6955 (2.4) |
| ast | 811 | 0.6783 | 0.6813 (1.15) | 0.6821 (1.08) | 0.6811 (1.21) |
| 3pm | 776 | 0.6715 | 0.6778 (0.18) | 0.6774 (0.27) | 0.6771 (0.35) |
| pra | 403 | 0.6913 | 0.7091 (-0.97) | 0.7103 (-1.1) | 0.7090 (-1.03) |
| pr | 457 | 0.6911 | 0.6978 (0.23) | 0.6978 (0.3) | 0.6976 (0.28) |
| pa | 392 | 0.6902 | 0.7056 (-0.69) | 0.7064 (-0.72) | 0.7064 (-0.76) |
| ra | 583 | 0.6900 | 0.6910 (2.35) | 0.6910 (2.3) | 0.6907 (2.42) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v2d | v2d_ctl |
|---|---|---|---|---|---|
| pts | YES | none | +61.6% (1, z 0) | +61.6% (1, z 0) | +61.6% (1, z 0) |
| pts | NO | +2.2% (5,771, z 1.8) | +2.2% (5,291, z 1.48) | +2.8% (5,228, z 1.8) | +2.4% (5,287, z 1.57) |
| reb | YES | none | +4.0% (40, z 1.4) | +1.1% (40, z 0.83) | +4.0% (40, z 1.4) |
| reb | NO | none | +4.2% (2,659, z 0.51) | +4.5% (2,629, z 0.58) | +4.2% (2,650, z 0.62) |
| ast | YES | none | +35.4% (94, z 1.8) | +34.5% (102, z 1.8) | +36.9% (93, z 1.72) |
| ast | NO | none | +8.4% (1,611, z 1.59) | +9.8% (1,579, z 2.05) | +8.2% (1,595, z 1.42) |
| 3pm | YES | none | +146.8% (7, z 1.87) | +146.8% (7, z 1.87) | +108.5% (6, z 1.65) |
| 3pm | NO | +5.4% (3,832, z 2.3) | +8.6% (3,269, z 2.9) | +8.6% (3,272, z 2.71) | +8.7% (3,260, z 2.73) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v2d | v2d_ctl |
|---|---|---|---|
| pts | -6.0% (53, z -0.44) | -4.5% (66, z -0.36) | -6.2% (61, z -0.48) |
| reb | +5.4% (632, z 0.92) | +4.4% (629, z 0.76) | +5.6% (631, z 0.96) |
| ast | -3.6% (502, z -0.63) | -8.0% (501, z -1.34) | -4.4% (501, z -0.76) |
| 3pm | +2.2% (484, z 0.37) | +1.9% (472, z 0.32) | +2.1% (476, z 0.35) |
| pra | +11.4% (97, z 0.99) | +7.7% (89, z 0.65) | +10.4% (90, z 0.89) |
| pr | +13.6% (63, z 0.96) | +7.2% (90, z 0.6) | +12.2% (61, z 0.84) |
| pa | +5.6% (65, z 0.42) | -1.4% (60, z -0.09) | -1.1% (59, z -0.08) |
| ra | -0.3% (440, z -0.06) | +0.0% (442, z 0.0) | -0.9% (440, z -0.16) |

## Gates

| Stat | v2 | v2d | v2d_ctl |
|---|---|---|---|
| pts | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | GO (NO) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO |

Coverage (player-games with a diet score / all): {'2025': '25,444 / 27,355', '2026': '25,755 / 27,799'}. Related: [courtai-teardown.md](courtai-teardown.md), [prop-model-v3-full.md](prop-model-v3-full.md).

## The diet column in the stacker (fit on 2024-25)

Score sd 0.0361 (a fraction: 0.01 = one percent more shots than average in his spots). Coefficient is on projected mean x score; t is the fit-season t.

| Stat | v2d coef (t) | control coef (t) |
|---|---|---|
| pts | +0.458 (5.13) | -0.097 (-1.21) |
| reb | +0.174 (2.05) | -0.020 (-0.26) |
| ast | +0.341 (3.44) | -0.044 (-0.48) |
| 3pm | +0.240 (2.1) | +0.054 (0.5) |

## Rule

1. v2d keeps every v2 GO at GO with ROI at least v2's: **False**.
2. v2d beats v2's blended Kalshi log loss on 2 of 4 stats (need 3).
3. The control beats v2 on 1 of 4 stats (must be under 3).

**Result: v2 (diet score stays display-only).**
