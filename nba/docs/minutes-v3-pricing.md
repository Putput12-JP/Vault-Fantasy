# v2 pricing with minutes model v3: pre-registered test

Generated 2026-09-30T20:44Z by `nba/scripts/build_minutes_v3_pricing.py`. Fit on 2024-25, tested on 2025-26,
28,252 identical player-games and prices. Only the minutes change: v1 per-minute rates and the v2 adjustments
everywhere, refit to each candidate's minutes.

- **v2**: shipped (minutes model v2). **v2m3**: minutes model v3. **v2m3s**: minutes model v3 with NBA.com's
  confirmed starters and inactive list.

Rule (fixed before running): replace v2's minutes only if every v2 GO stays GO with ROI at least v2's; then
the lowest Kalshi log loss.

**Shipped: v2** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).

## Projection accuracy, 2025-26

| Stat | RMSE v2 | RMSE v2m3 | RMSE v2m3s | MAE v2 | MAE v2m3 | MAE v2m3s | Bias v2 | Bias v2m3 | Bias v2m3s |
|---|---|---|---|---|---|---|---|---|---|
| minutes |  |  |  | 4.899 | 4.867 | 4.723 | 8+ miss 18.5% | 8+ miss 18.4% | 8+ miss 17.1% |
| pts | 5.879 | 5.869 | 5.841 | 4.491 | 4.482 | 4.455 | +0.088 | +0.080 | +0.076 |
| reb | 2.451 | 2.445 | 2.429 | 1.863 | 1.857 | 1.847 | +0.024 | +0.021 | +0.019 |
| ast | 1.791 | 1.789 | 1.780 | 1.323 | 1.321 | 1.314 | +0.007 | +0.006 | +0.004 |
| 3pm | 1.223 | 1.222 | 1.220 | 0.890 | 0.889 | 0.886 | +0.020 | +0.020 | +0.019 |
| pra | 7.589 | 7.567 | 7.499 | 5.890 | 5.871 | 5.813 | +0.119 | +0.106 | +0.098 |
| pr | 6.995 | 6.977 | 6.926 | 5.406 | 5.392 | 5.348 | +0.112 | +0.101 | +0.095 |
| pa | 6.432 | 6.420 | 6.375 | 4.944 | 4.931 | 4.887 | +0.095 | +0.086 | +0.079 |
| ra | 3.326 | 3.317 | 3.288 | 2.555 | 2.548 | 2.528 | +0.032 | +0.027 | +0.022 |

## Every player-game: log score of the outcome, and range Brier

| Stat | Log score v2 | Log score v2m3 | Log score v2m3s | Range Brier v2 | Range Brier v2m3 | Range Brier v2m3s |
|---|---|---|---|---|---|---|
| pts | 3.1198 | 3.1180 | 3.1101 | 0.1840 | 0.1834 | 0.1812 |
| reb | 2.1429 | 2.1408 | 2.1348 | 0.1776 | 0.1767 | 0.1744 |
| ast | 1.7391 | 1.7385 | 1.7335 | 0.1812 | 0.1810 | 0.1794 |
| 3pm | 1.2958 | 1.2946 | 1.2921 | 0.1843 | 0.1839 | 0.1827 |
| pra | 3.3992 | 3.3958 | 3.3849 | 0.1663 | 0.1657 | 0.1624 |
| pr | 3.3137 | 3.3107 | 3.3010 | 0.1723 | 0.1712 | 0.1688 |
| pa | 3.2158 | 3.2134 | 3.2044 | 0.1756 | 0.1747 | 0.1720 |
| ra | 2.5619 | 2.5589 | 2.5491 | 0.1699 | 0.1690 | 0.1666 |

## Kalshi ladders, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2m3 | v2m3s |
|---|---|---|---|---|---|
| pts | 18,840 | 0.5290 | 0.5504 (3.95) | 0.5490 (4.35) | 0.5468 (4.14) |
| reb | 14,117 | 0.5621 | 0.5737 (5.11) | 0.5719 (5.59) | 0.5687 (6.11) |
| ast | 10,742 | 0.5405 | 0.5477 (6.29) | 0.5475 (6.37) | 0.5454 (6.63) |
| 3pm | 10,814 | 0.5281 | 0.5285 (6.64) | 0.5274 (7.07) | 0.5262 (6.72) |

Blended fair price (market + model, fit on the first half) scored on the second half:

| Stat | Market alone | v2 | v2m3 | v2m3s |
|---|---|---|---|---|
| pts | 0.51083 | 0.50810 | 0.50811 | 0.50801 |
| reb | 0.55337 | 0.55157 | 0.55132 | 0.55089 |
| ast | 0.53194 | 0.52783 | 0.52757 | 0.52748 |
| 3pm | 0.51172 | 0.50581 | 0.50517 | 0.50574 |

## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)

| Stat | Rows | Market | v2 | v2m3 | v2m3s |
|---|---|---|---|---|---|
| pts | 906 | 0.6922 | 0.6960 (1.31) | 0.6968 (1.26) | 0.6970 (1.24) |
| reb | 911 | 0.6930 | 0.6921 (2.5) | 0.6922 (2.51) | 0.6891 (3.02) |
| ast | 816 | 0.6784 | 0.6813 (1.21) | 0.6794 (1.56) | 0.6798 (1.51) |
| 3pm | 781 | 0.6714 | 0.6779 (-0.09) | 0.6760 (0.36) | 0.6782 (-0.23) |
| pra | 403 | 0.6913 | 0.7019 (-0.15) | 0.7024 (-0.22) | 0.7014 (-0.21) |
| pr | 458 | 0.6912 | 0.6956 (0.56) | 0.6968 (0.44) | 0.6970 (0.36) |
| pa | 392 | 0.6902 | 0.7008 (-0.14) | 0.7021 (-0.49) | 0.7056 (-0.76) |
| ra | 583 | 0.6900 | 0.6904 (2.13) | 0.6896 (2.29) | 0.6884 (2.48) |

## Betting it, out of sample, 3%+ edge

Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.

| Stat | Side | Price only | v2 | v2m3 | v2m3s |
|---|---|---|---|---|---|
| pts | YES | none | +33.2% (3, z 0) | +104.0% (4, z 0.88) | +61.6% (1, z 0) |
| pts | NO | +2.1% (5,703, z 1.76) | +3.5% (5,022, z 2.14) | +3.0% (4,874, z 2.01) | +3.2% (4,973, z 1.94) |
| reb | YES | none | +12.5% (29, z 1.81) | +27.3% (36, z 2.32) | +28.2% (23, z 1.62) |
| reb | NO | none | +5.4% (2,341, z 0.33) | +6.1% (2,415, z 0.92) | +5.8% (2,302, z 0.75) |
| ast | YES | none | +13.6% (65, z 1.52) | +15.3% (57, z 1.23) | +29.2% (73, z 1.3) |
| ast | NO | none | +7.3% (1,387, z 1.46) | +7.8% (1,302, z 1.65) | +10.2% (1,314, z 1.68) |
| 3pm | YES | none | +44.3% (20, z 1.13) | +68.9% (14, z 1.29) | +5.3% (13, z 0.13) |
| 3pm | NO | +5.1% (3,836, z 2.26) | +9.4% (3,200, z 3.53) | +10.0% (3,193, z 3.55) | +9.3% (3,208, z 3.46) |

| Sportsbook stat (24-25 fit, 25-26 close) | v2 | v2m3 | v2m3s |
|---|---|---|---|
| pts | -6.1% (68, z -0.5) | -1.5% (95, z -0.14) | +4.5% (106, z 0.47) |
| reb | +7.5% (633, z 1.34) | +6.2% (602, z 1.08) | +9.7% (549, z 1.66) |
| ast | -2.9% (450, z -0.47) | -3.5% (463, z -0.58) | -3.0% (437, z -0.48) |
| 3pm | +0.2% (438, z 0.03) | +6.7% (410, z 1.08) | -0.2% (377, z -0.04) |
| pra | +10.8% (77, z 0.86) | +19.6% (98, z 1.81) | +15.3% (113, z 1.49) |
| pr | +7.5% (58, z 0.53) | +13.6% (105, z 1.27) | +6.2% (138, z 0.63) |
| pa | +2.3% (36, z 0.14) | +5.4% (35, z 0.31) | -11.8% (71, z -0.93) |
| ra | +2.5% (434, z 0.46) | +2.2% (426, z 0.41) | +3.0% (425, z 0.55) |

## Gates

| Stat | v2 | v2m3 | v2m3s |
|---|---|---|---|
| pts | GO (NO) | GO (NO) | WATCH (YES) |
| reb | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| ast | WATCH (YES) | WATCH (YES) | WATCH (YES) |
| 3pm | GO (NO) | GO (NO) | GO (NO) |
| pra | NO-GO | NO-GO | NO-GO |
| pr | NO-GO | NO-GO | NO-GO |
| pa | NO-GO | NO-GO | NO-GO |
| ra | NO-GO | NO-GO | NO-GO |

Team minutes targets: v2m3 251.3, v2m3s 251.2. Related: [prop-model-v3-full.md](prop-model-v3-full.md),
[starters-feed.md](starters-feed.md), [minutes-model-v3.md](minutes-model-v3.md).
