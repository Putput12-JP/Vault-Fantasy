# Prop model v3 candidate (minutes v3 + per-stat memory + ladder shape) vs v2

Generated 2026-10-07T00:30Z by `nba/scripts/build_prop_model_v3_full.py`. Fit on 2024-25, tested on 2025-26,
27,797 identical player-games and identical prices for every model.

- **v2**: shipped. **v3m**: minutes model v3 x per-stat-memory rates, stacker refit, v2-style spread and line
  calibration (isolates workstreams B + C). **v3m_shape**: v3m's mean with workstream A's ladder distribution,
  uncalibrated. **v3m_shape_linecal**: the same, calibrated on 2024-25 sportsbook main lines.

**Shipped: v3m_shape** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v3m | MAE v2 | MAE v3m | Bias v2 | Bias v3m |
|---|---|---|---|---|---|---|
| minutes |  |  | 5.040 | 4.908 | 8+ miss 19.7% | 8+ miss 18.8% |
| pts | 5.904 | 5.885 | 4.509 | 4.497 | +0.011 | -0.008 |
| reb | 2.454 | 2.441 | 1.862 | 1.853 | -0.006 | +0.011 |
| ast | 1.793 | 1.791 | 1.325 | 1.323 | -0.010 | -0.014 |
| 3pm | 1.225 | 1.221 | 0.891 | 0.887 | +0.011 | +0.016 |
| pra | 7.625 | 7.594 | 5.918 | 5.894 | -0.004 | -0.011 |
| pr | 7.024 | 6.995 | 5.426 | 5.408 | +0.005 | +0.003 |
| pa | 6.466 | 6.444 | 4.969 | 4.954 | +0.002 | -0.022 |
| ra | 3.332 | 3.318 | 2.555 | 2.544 | -0.016 | -0.003 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v3m | Log score v3m_shape | Range Brier v2 | Range Brier v3m | Range Brier v3m_shape | Range Brier v3m_shape_linecal |
|---|---|---|---|---|---|---|---|
| pts | 3.1262 | 3.1232 | 3.0671 | 0.1859 | 0.1839 | 0.1799 | 0.1837 |
| reb | 2.1460 | 2.1411 | 2.1402 | 0.1784 | 0.1767 | 0.1743 | 0.1769 |
| ast | 1.7422 | 1.7416 | 1.7414 | 0.1819 | 0.1814 | 0.1797 | 0.1813 |
| 3pm | 1.2989 | 1.2951 | 1.2972 | 0.1853 | 0.1845 | 0.1824 | 0.1842 |
| pra | 3.4055 | 3.4008 | 3.3570 | 0.1686 | 0.1673 | 0.1620 | 0.1665 |
| pr | 3.3198 | 3.3154 | 3.2674 | 0.1744 | 0.1727 | 0.1674 | 0.1721 |
| pa | 3.2228 | 3.2194 | 3.1678 | 0.1770 | 0.1760 | 0.1710 | 0.1750 |
| ra | 2.5657 | 2.5606 | 2.5078 | 0.1711 | 0.1700 | 0.1667 | 0.1695 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | 18,803 | 0.5291 | 0.5543 (3.78) | 0.5494 (4.27) | 0.5446 (4.04) | 0.5528 (4.02) |
| reb | 14,087 | 0.5618 | 0.5750 (5.38) | 0.5725 (6.14) | 0.5717 (6.65) | 0.5726 (6.13) |
| ast | 10,726 | 0.5405 | 0.5482 (6.96) | 0.5481 (6.77) | 0.5479 (6.76) | 0.5481 (6.87) |
| 3pm | 10,791 | 0.5283 | 0.5297 (6.73) | 0.5283 (7.28) | 0.5240 (7.23) | 0.5270 (7.1) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|
| pts | 0.51072 | 0.50796 | 0.50798 | 0.50819 | 0.50805 |
| reb | 0.55363 | 0.55182 | 0.55149 | 0.55118 | 0.55157 |
| ast | 0.53192 | 0.52736 | 0.52741 | 0.52773 | 0.52737 |
| 3pm | 0.51195 | 0.50573 | 0.50562 | 0.50596 | 0.50583 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | 884 | 0.6920 | 0.6967 (1.24) | 0.6997 (0.53) | 0.7119 (1.0) | 0.7008 (0.29) |
| reb | 901 | 0.6937 | 0.6955 (2.41) | 0.6938 (2.63) | 0.7033 (2.57) | 0.6939 (2.57) |
| ast | 811 | 0.6783 | 0.6812 (1.17) | 0.6796 (1.45) | 0.6824 (1.49) | 0.6796 (1.45) |
| 3pm | 776 | 0.6715 | 0.6779 (0.15) | 0.6762 (0.51) | 0.6773 (0.78) | 0.6759 (0.62) |
| pra | 403 | 0.6913 | 0.7091 (-0.97) | 0.7115 (-1.25) | 0.7427 (-1.13) | 0.7110 (-1.25) |
| pr | 457 | 0.6911 | 0.6978 (0.24) | 0.7015 (-0.05) | 0.7246 (-0.05) | 0.7035 (-0.23) |
| pa | 392 | 0.6902 | 0.7056 (-0.68) | 0.7087 (-1.15) | 0.7296 (-0.96) | 0.7082 (-1.06) |
| ra | 583 | 0.6900 | 0.6911 (2.33) | 0.6911 (2.37) | 0.7052 (2.11) | 0.6914 (2.33) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | YES | none | +61.6% (1, z 0) | +99.7% (2, z 0) | +36.0% (6, z 0.28) | +99.7% (2, z 0) |
| pts | NO | +2.2% (5,771, z 1.8) | +2.2% (5,290, z 1.43) | +2.4% (5,131, z 1.22) | +2.7% (4,985, z 1.35) | +2.2% (5,343, z 1.14) |
| reb | YES | none | +4.0% (40, z 1.4) | +14.4% (68, z 1.83) | +6.4% (68, z 0.4) | +10.7% (71, z 1.27) |
| reb | NO | none | +4.1% (2,652, z 0.44) | +6.6% (2,782, z 0.91) | +7.2% (2,768, z 1.86) | +6.9% (2,806, z 1.1) |
| ast | YES | none | +31.8% (90, z 1.7) | +34.2% (83, z 1.36) | +15.4% (114, z 1.16) | +25.8% (93, z 1.19) |
| ast | NO | none | +8.5% (1,599, z 1.37) | +9.2% (1,486, z 1.67) | +8.4% (1,527, z 1.48) | +9.5% (1,503, z 1.57) |
| 3pm | YES | none | +108.5% (6, z 1.65) | +50.9% (16, z 0.77) | +23.4% (21, z 0.85) | +49.2% (17, z 0.81) |
| 3pm | NO | +5.4% (3,832, z 2.3) | +8.7% (3,261, z 2.86) | +9.8% (3,277, z 3.12) | +8.9% (3,253, z 2.74) | +9.1% (3,270, z 2.97) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|
| pts | -6.0% (53, z -0.44) | -8.7% (82, z -0.78) | +6.8% (132, z 0.75) | -7.0% (113, z -0.72) |
| reb | +5.0% (636, z 0.86) | +9.2% (626, z 1.57) | +10.6% (544, z 1.74) | +10.0% (625, z 1.71) |
| ast | -3.3% (498, z -0.57) | -4.8% (535, z -0.82) | -2.9% (481, z -0.49) | -3.4% (524, z -0.6) |
| 3pm | +0.8% (478, z 0.13) | +1.6% (462, z 0.26) | +3.4% (457, z 0.54) | +3.0% (445, z 0.46) |
| pra | +11.4% (97, z 0.99) | +4.9% (89, z 0.4) | +26.4% (118, z 2.68) | +18.5% (104, z 1.72) |
| pr | +11.7% (62, z 0.81) | +9.5% (103, z 0.84) | +15.2% (142, z 1.69) | +11.0% (114, z 1.09) |
| pa | +5.6% (66, z 0.42) | +1.5% (60, z 0.11) | +13.3% (92, z 1.15) | +3.5% (59, z 0.24) |
| ra | -0.5% (441, z -0.08) | -2.6% (443, z -0.49) | -1.1% (405, z -0.2) | -1.8% (423, z -0.33) |

## Gates

| Stat | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|
| pts | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO | NO-GO |

Inputs: [minutes-model-v3.md](minutes-model-v3.md), [rates-v3.md](rates-v3.md), [prop-model-v3.md](prop-model-v3.md). Team minutes target for v3 minutes: 258.5.
