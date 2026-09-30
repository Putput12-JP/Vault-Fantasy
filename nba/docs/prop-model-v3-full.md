# Prop model v3 candidate (minutes v3 + per-stat memory + ladder shape) vs v2

Generated 2026-09-30T17:43Z by `nba/scripts/build_prop_model_v3_full.py`. Fit on 2024-25, tested on 2025-26,
28,252 identical player-games and identical prices for every model.

- **v2**: shipped. **v3m**: minutes model v3 x per-stat-memory rates, stacker refit, v2-style spread and line
  calibration (isolates workstreams B + C). **v3m_shape**: v3m's mean with workstream A's ladder distribution,
  uncalibrated. **v3m_shape_linecal**: the same, calibrated on 2024-25 sportsbook main lines.

**Shipped: v2** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v3m | MAE v2 | MAE v3m | Bias v2 | Bias v3m |
|---|---|---|---|---|---|---|
| minutes |  |  | 4.899 | 4.867 | 8+ miss 18.5% | 8+ miss 18.4% |
| pts | 5.879 | 5.862 | 4.491 | 4.479 | +0.088 | +0.057 |
| reb | 2.451 | 2.439 | 1.863 | 1.853 | +0.024 | +0.036 |
| ast | 1.791 | 1.789 | 1.323 | 1.321 | +0.007 | +0.000 |
| 3pm | 1.223 | 1.220 | 0.890 | 0.885 | +0.020 | +0.023 |
| pra | 7.589 | 7.562 | 5.890 | 5.866 | +0.119 | +0.093 |
| pr | 6.995 | 6.970 | 5.406 | 5.388 | +0.112 | +0.093 |
| pa | 6.432 | 6.415 | 4.944 | 4.928 | +0.095 | +0.057 |
| ra | 3.326 | 3.312 | 2.555 | 2.544 | +0.032 | +0.036 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v3m | Log score v3m_shape | Range Brier v2 | Range Brier v3m | Range Brier v3m_shape | Range Brier v3m_shape_linecal |
|---|---|---|---|---|---|---|---|
| pts | 3.1198 | 3.1169 | 3.0625 | 0.1840 | 0.1828 | 0.1790 | 0.1819 |
| reb | 2.1429 | 2.1387 | 2.1368 | 0.1776 | 0.1761 | 0.1739 | 0.1760 |
| ast | 1.7391 | 1.7382 | 1.7375 | 0.1812 | 0.1810 | 0.1793 | 0.1808 |
| 3pm | 1.2958 | 1.2922 | 1.2944 | 0.1843 | 0.1831 | 0.1816 | 0.1831 |
| pra | 3.3992 | 3.3946 | 3.3514 | 0.1663 | 0.1653 | 0.1611 | 0.1648 |
| pr | 3.3137 | 3.3094 | 3.2621 | 0.1723 | 0.1711 | 0.1667 | 0.1703 |
| pa | 3.2158 | 3.2125 | 3.1622 | 0.1756 | 0.1743 | 0.1703 | 0.1733 |
| ra | 2.5619 | 2.5569 | 2.5036 | 0.1699 | 0.1687 | 0.1660 | 0.1680 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | 18,840 | 0.5290 | 0.5504 (3.95) | 0.5477 (4.59) | 0.5407 (4.4) | 0.5486 (4.27) |
| reb | 14,117 | 0.5621 | 0.5737 (5.11) | 0.5718 (5.64) | 0.5701 (6.12) | 0.5716 (5.75) |
| ast | 10,742 | 0.5405 | 0.5477 (6.29) | 0.5480 (6.13) | 0.5472 (6.18) | 0.5476 (6.36) |
| 3pm | 10,814 | 0.5281 | 0.5285 (6.64) | 0.5265 (7.17) | 0.5235 (7.02) | 0.5258 (6.97) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|
| pts | 0.51083 | 0.50810 | 0.50821 | 0.50843 | 0.50828 |
| reb | 0.55337 | 0.55157 | 0.55136 | 0.55100 | 0.55128 |
| ast | 0.53194 | 0.52783 | 0.52783 | 0.52791 | 0.52772 |
| 3pm | 0.51172 | 0.50581 | 0.50553 | 0.50585 | 0.50572 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | 906 | 0.6922 | 0.6960 (1.31) | 0.6995 (0.77) | 0.7100 (1.07) | 0.6988 (0.8) |
| reb | 911 | 0.6930 | 0.6921 (2.5) | 0.6928 (2.41) | 0.6986 (2.46) | 0.6932 (2.37) |
| ast | 816 | 0.6784 | 0.6813 (1.21) | 0.6813 (1.29) | 0.6798 (1.74) | 0.6801 (1.44) |
| 3pm | 781 | 0.6714 | 0.6779 (-0.09) | 0.6763 (0.26) | 0.6773 (0.45) | 0.6753 (0.53) |
| pra | 403 | 0.6913 | 0.7019 (-0.15) | 0.7049 (-0.57) | 0.7221 (-0.48) | 0.7030 (-0.42) |
| pr | 458 | 0.6912 | 0.6956 (0.56) | 0.6988 (0.16) | 0.7138 (0.15) | 0.6997 (0.11) |
| pa | 392 | 0.6902 | 0.7008 (-0.14) | 0.7034 (-0.5) | 0.7179 (-0.59) | 0.7031 (-0.7) |
| ra | 583 | 0.6900 | 0.6904 (2.13) | 0.6908 (2.1) | 0.6979 (1.96) | 0.6910 (2.03) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|---|---|
| pts | YES | none | +33.2% (3, z 0) | +18.8% (9, z 0.17) | -3.3% (12, z 0.23) | +18.8% (9, z 0.17) |
| pts | NO | +2.1% (5,703, z 1.76) | +3.5% (5,022, z 2.14) | +2.4% (4,859, z 1.44) | +2.3% (4,727, z 1.49) | +2.5% (5,025, z 1.77) |
| reb | YES | none | +12.5% (29, z 1.81) | +15.2% (50, z 1.35) | +19.1% (42, z 1.33) | +15.3% (49, z 1.83) |
| reb | NO | none | +5.4% (2,341, z 0.33) | +5.5% (2,441, z 0.86) | +8.4% (2,385, z 1.83) | +5.3% (2,452, z 0.77) |
| ast | YES | none | +13.6% (65, z 1.52) | +10.1% (56, z 1.07) | +17.1% (74, z 0.9) | +13.7% (73, z 1.35) |
| ast | NO | none | +7.3% (1,387, z 1.46) | +7.2% (1,242, z 1.85) | +8.2% (1,259, z 1.34) | +6.7% (1,329, z 1.44) |
| 3pm | YES | none | +44.3% (20, z 1.13) | +44.6% (26, z 0.85) | +19.0% (28, z 0.55) | +22.0% (23, z 0.51) |
| 3pm | NO | +5.1% (3,836, z 2.26) | +9.4% (3,200, z 3.53) | +9.8% (3,243, z 3.43) | +8.3% (3,265, z 3.16) | +7.8% (3,353, z 3.0) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|
| pts | -6.1% (68, z -0.5) | +0.1% (123, z 0.02) | +12.2% (129, z 1.41) | +9.2% (128, z 1.04) |
| reb | +7.5% (633, z 1.34) | +8.5% (598, z 1.45) | +7.9% (539, z 1.32) | +9.8% (587, z 1.68) |
| ast | -2.9% (450, z -0.47) | -5.2% (440, z -0.85) | -0.2% (443, z -0.04) | -3.4% (459, z -0.56) |
| 3pm | +0.2% (438, z 0.03) | +4.5% (433, z 0.73) | +6.0% (411, z 0.92) | +4.2% (416, z 0.65) |
| pra | +10.8% (77, z 0.86) | +11.9% (79, z 0.97) | +14.3% (118, z 1.43) | +16.4% (86, z 1.41) |
| pr | +7.5% (58, z 0.53) | +11.0% (132, z 1.13) | +11.6% (137, z 1.22) | +9.8% (126, z 0.98) |
| pa | +2.3% (36, z 0.14) | -1.2% (50, z -0.07) | -7.0% (86, z -0.57) | -5.9% (50, z -0.39) |
| ra | +2.5% (434, z 0.46) | +0.1% (428, z 0.02) | +0.5% (395, z 0.09) | -0.2% (396, z -0.03) |

## Gates

| Stat | v2 | v3m | v3m_shape | v3m_shape_linecal |
|---|---|---|---|---|
| pts | GO (NO) | WATCH (YES) | WATCH (NO) | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO | NO-GO |

Inputs: [minutes-model-v3.md](minutes-model-v3.md), [rates-v3.md](rates-v3.md), [prop-model-v3.md](prop-model-v3.md). Team minutes target for v3 minutes: 251.3.
