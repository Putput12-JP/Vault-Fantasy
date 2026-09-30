# Confirmed starters feed: accuracy and backtest

Generated 2026-09-30T17:44Z by `nba/scripts/build_starters.py`. Source: NBA.com daily lineups (free, no key), the file
behind nba.com/players/todays-lineups. Fit on 2024-25, tested on 2025-26, 28,252 identical player-games and prices.

## The feed, 2024-25 and 2025-26

| Team-games | With a full five | All five right | Wrong starters | Inactive listed | Of those, played |
|---|---|---|---|---|---|
| 5,286 | 5,286 | 5,285 (100.0%) | 1 | 21,485 | 0 |

Timing: past files are stamped with their final update (about 2.5 hours after tip), so history cannot say how early
each lineup was confirmed. The live recorder logs every Expected to Confirmed change from 2026-27. The backtest
prices (Kalshi 30-minute pre-tip VWAP, ESPN last pre-tip line) come from a market that could see the same lineups,
so this measures whether the model catches up with the market, not whether it beats a stale price.

- **v2**: shipped. **v3m**: v3 base (minutes v3 x per-stat memory), role from last game.
- **v3s**: v3 base with the feed: tonight's starters drive the role term (minutes v3's starters-known weights) and
  the inactive list joins the injury report. **v3s_shape** / **v3s_shape_linecal**: v3s with workstream A's ladder shape.

**Shipped: v2** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v3m | RMSE v3s | MAE v2 | MAE v3m | MAE v3s | Bias v2 | Bias v3m | Bias v3s |
|---|---|---|---|---|---|---|---|---|---|
| minutes |  |  |  | 4.899 | 4.867 | 4.723 | 8+ miss 18.5% | 8+ miss 18.4% | 8+ miss 17.1% |
| pts | 5.879 | 5.862 | 5.834 | 4.491 | 4.479 | 4.452 | +0.088 | +0.057 | +0.054 |
| reb | 2.451 | 2.439 | 2.423 | 1.863 | 1.853 | 1.843 | +0.024 | +0.036 | +0.034 |
| ast | 1.791 | 1.789 | 1.780 | 1.323 | 1.321 | 1.313 | +0.007 | +0.000 | -0.002 |
| 3pm | 1.223 | 1.220 | 1.217 | 0.890 | 0.885 | 0.882 | +0.020 | +0.023 | +0.023 |
| pra | 7.589 | 7.562 | 7.494 | 5.890 | 5.866 | 5.807 | +0.119 | +0.093 | +0.086 |
| pr | 6.995 | 6.970 | 6.919 | 5.406 | 5.388 | 5.343 | +0.112 | +0.093 | +0.088 |
| pa | 6.432 | 6.415 | 6.371 | 4.944 | 4.928 | 4.884 | +0.095 | +0.057 | +0.052 |
| ra | 3.326 | 3.312 | 3.283 | 2.555 | 2.544 | 2.523 | +0.032 | +0.036 | +0.032 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v3m | Log score v3s | Log score v3s_shape | Range Brier v2 | Range Brier v3m | Range Brier v3s | Range Brier v3s_shape | Range Brier v3s_shape_linecal |
|---|---|---|---|---|---|---|---|---|---|
| pts | 3.1198 | 3.1169 | 3.1090 | 3.0560 | 0.1840 | 0.1828 | 0.1810 | 0.1777 | 0.1802 |
| reb | 2.1429 | 2.1387 | 2.1321 | 2.1305 | 0.1776 | 0.1761 | 0.1741 | 0.1728 | 0.1738 |
| ast | 1.7391 | 1.7382 | 1.7332 | 1.7327 | 0.1812 | 0.1810 | 0.1793 | 0.1783 | 0.1793 |
| 3pm | 1.2958 | 1.2922 | 1.2898 | 1.2918 | 0.1843 | 0.1831 | 0.1820 | 0.1811 | 0.1821 |
| pra | 3.3992 | 3.3946 | 3.3838 | 3.3410 | 0.1663 | 0.1653 | 0.1622 | 0.1593 | 0.1616 |
| pr | 3.3137 | 3.3094 | 3.2998 | 3.2534 | 0.1723 | 0.1711 | 0.1684 | 0.1651 | 0.1678 |
| pa | 3.2158 | 3.2125 | 3.2032 | 3.1542 | 0.1756 | 0.1743 | 0.1717 | 0.1687 | 0.1709 |
| ra | 2.5619 | 2.5569 | 2.5470 | 2.4956 | 0.1699 | 0.1687 | 0.1661 | 0.1645 | 0.1657 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|---|---|
| pts | 18,840 | 0.5290 | 0.5504 (3.95) | 0.5477 (4.59) | 0.5453 (4.56) | 0.5399 (4.24) | 0.5470 (4.12) |
| reb | 14,117 | 0.5621 | 0.5737 (5.11) | 0.5718 (5.64) | 0.5690 (6.17) | 0.5687 (6.47) | 0.5685 (6.34) |
| ast | 10,742 | 0.5405 | 0.5477 (6.29) | 0.5480 (6.13) | 0.5460 (6.32) | 0.5462 (6.31) | 0.5458 (6.58) |
| 3pm | 10,814 | 0.5281 | 0.5285 (6.64) | 0.5265 (7.17) | 0.5253 (6.81) | 0.5238 (6.6) | 0.5252 (6.54) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|---|
| pts | 0.51083 | 0.50810 | 0.50821 | 0.50803 | 0.50827 | 0.50810 |
| reb | 0.55337 | 0.55157 | 0.55136 | 0.55092 | 0.55070 | 0.55083 |
| ast | 0.53194 | 0.52783 | 0.52783 | 0.52780 | 0.52785 | 0.52762 |
| 3pm | 0.51172 | 0.50581 | 0.50553 | 0.50610 | 0.50648 | 0.50626 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|---|---|
| pts | 906 | 0.6922 | 0.6960 (1.31) | 0.6995 (0.77) | 0.7001 (0.66) | 0.7092 (1.03) | 0.6971 (1.05) |
| reb | 911 | 0.6930 | 0.6921 (2.5) | 0.6928 (2.41) | 0.6909 (2.77) | 0.6940 (2.89) | 0.6910 (2.77) |
| ast | 816 | 0.6784 | 0.6813 (1.21) | 0.6813 (1.29) | 0.6795 (1.54) | 0.6793 (1.69) | 0.6798 (1.52) |
| 3pm | 781 | 0.6714 | 0.6779 (-0.09) | 0.6763 (0.26) | 0.6767 (0.08) | 0.6786 (0.03) | 0.6757 (0.41) |
| pra | 403 | 0.6913 | 0.7019 (-0.15) | 0.7049 (-0.57) | 0.7013 (-0.34) | 0.7166 (-0.56) | 0.7028 (-0.57) |
| pr | 458 | 0.6912 | 0.6956 (0.56) | 0.6988 (0.16) | 0.6996 (-0.07) | 0.7097 (0.1) | 0.6986 (0.04) |
| pa | 392 | 0.6902 | 0.7008 (-0.14) | 0.7034 (-0.5) | 0.7061 (-1.14) | 0.7191 (-1.08) | 0.7047 (-1.01) |
| ra | 583 | 0.6900 | 0.6904 (2.13) | 0.6908 (2.1) | 0.6887 (2.37) | 0.6915 (2.32) | 0.6892 (2.26) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|---|---|
| pts | YES | none | +33.2% (3, z 0) | +18.8% (9, z 0.17) | +172.0% (3, z 0) | +63.2% (5, z 0.54) | +61.6% (1, z 0) |
| pts | NO | +2.1% (5,703, z 1.76) | +3.5% (5,022, z 2.14) | +2.4% (4,859, z 1.44) | +2.2% (4,905, z 1.51) | +2.1% (4,787, z 1.72) | +3.1% (5,094, z 2.08) |
| reb | YES | none | +12.5% (29, z 1.81) | +15.2% (50, z 1.35) | +30.3% (41, z 2.91) | +42.2% (30, z 2.58) | +28.8% (39, z 2.42) |
| reb | NO | none | +5.4% (2,341, z 0.33) | +5.5% (2,441, z 0.86) | +7.0% (2,377, z 0.94) | +9.0% (2,291, z 1.87) | +6.9% (2,377, z 0.95) |
| ast | YES | none | +13.6% (65, z 1.52) | +10.1% (56, z 1.07) | +21.7% (66, z 1.25) | +26.4% (69, z 1.13) | +21.9% (80, z 1.23) |
| ast | NO | none | +7.3% (1,387, z 1.46) | +7.2% (1,242, z 1.85) | +10.1% (1,219, z 1.67) | +7.5% (1,210, z 1.15) | +10.1% (1,271, z 1.81) |
| 3pm | YES | none | +44.3% (20, z 1.13) | +44.6% (26, z 0.85) | +13.0% (26, z 0.2) | +18.0% (27, z 0.53) | +37.7% (17, z 0.92) |
| 3pm | NO | +5.1% (3,836, z 2.26) | +9.4% (3,200, z 3.53) | +9.8% (3,243, z 3.43) | +9.1% (3,233, z 3.2) | +7.8% (3,262, z 2.62) | +8.6% (3,273, z 3.33) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|
| pts | -6.1% (68, z -0.5) | +0.1% (123, z 0.02) | +0.4% (160, z 0.05) | +0.9% (173, z 0.12) | +8.7% (124, z 0.98) |
| reb | +7.5% (633, z 1.34) | +8.5% (598, z 1.45) | +10.9% (595, z 1.91) | +11.5% (543, z 1.96) | +9.4% (594, z 1.63) |
| ast | -2.9% (450, z -0.47) | -5.2% (440, z -0.85) | -0.9% (454, z -0.15) | +5.1% (416, z 0.83) | -3.0% (453, z -0.5) |
| 3pm | +0.2% (438, z 0.03) | +4.5% (433, z 0.73) | +0.0% (411, z 0.0) | +2.6% (385, z 0.39) | +2.5% (399, z 0.38) |
| pra | +10.8% (77, z 0.86) | +11.9% (79, z 0.97) | +13.0% (113, z 1.32) | +10.2% (141, z 1.09) | +5.2% (110, z 0.51) |
| pr | +7.5% (58, z 0.53) | +11.0% (132, z 1.13) | +0.2% (147, z 0.02) | +12.3% (151, z 1.36) | +2.5% (167, z 0.28) |
| pa | +2.3% (36, z 0.14) | -1.2% (50, z -0.07) | -13.0% (86, z -1.09) | -4.1% (101, z -0.37) | -5.1% (84, z -0.43) |
| ra | +2.5% (434, z 0.46) | +0.1% (428, z 0.02) | +3.1% (407, z 0.56) | -0.2% (367, z -0.04) | +0.3% (401, z 0.06) |

## Gates

| Stat | v2 | v3m | v3s | v3s_shape | v3s_shape_linecal |
|---|---|---|---|---|---|
| pts | GO (NO) | WATCH (YES) | WATCH (YES) | WATCH (YES) | GO (NO) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO | NO-GO | NO-GO |

Team minutes target: v3m 251.3, v3s 251.2. Related: [prop-model-v3-full.md](prop-model-v3-full.md),
[minutes-model-v3.md](minutes-model-v3.md).
