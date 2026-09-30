# Consensus fair engine: backtest

Generated 2026-09-30T20:05Z by `nba/scripts/build_consensus.py`. 2025-26 only (the seasons with both venues archived):
blends fit on the first half by tip time, scored and bet on the second half, 3%+ edge after fees.
Consensus = one venue's prices moved to the other venue's line through prop model v2's distribution shape
(`scripts/consensus.py`); our projection is not in it. "consensus + model" adds our projection in a fitted blend.

Ship rule (fixed before running): GO = second-half ROI > 0 with z >= 2 over 50+ games; WATCH = positive; else NO-GO.
Baselines on the same rows (not judged): "price only" = the venue's own price recalibrated (catches plain venue
bias, e.g. Kalshi overs), "price + model" = the blend the current GO signals use.

## Books -> Kalshi (Price gap on Kalshi)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 1,114 | 0.4496 | 0.4446 | 0.4867 | 0.4543 | 0.4553 | 0.4560 |
| reb | 1,610 | 0.5079 | 0.5070 | 0.5152 | 0.5044 | 0.5037 | 0.5047 |
| ast | 1,159 | 0.5336 | 0.5270 | 0.5319 | 0.5104 | 0.5124 | 0.5103 |
| 3pm | 1,436 | 0.5120 | 0.5069 | 0.5147 | 0.5013 | 0.5010 | 0.5012 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 70 | 0.501 | 0.457 | 0.510 | 0.6873 | 0.6945 |
| pts | 1 away | 115 | 0.505 | 0.426 | 0.513 | 0.6773 | 0.6760 |
| pts | 2-3 away | 264 | 0.476 | 0.428 | 0.493 | 0.6220 | 0.6271 |
| pts | 4-6 away | 287 | 0.403 | 0.387 | 0.423 | 0.5131 | 0.5093 |
| pts | 7+ away | 378 | 0.188 | 0.143 | 0.208 | 0.2409 | 0.2569 |
| reb | same line | 341 | 0.490 | 0.478 | 0.495 | 0.6893 | 0.6931 |
| reb | 1 away | 373 | 0.506 | 0.488 | 0.510 | 0.6345 | 0.6410 |
| reb | 2-3 away | 637 | 0.481 | 0.449 | 0.481 | 0.4642 | 0.4695 |
| reb | 4-6 away | 259 | 0.323 | 0.255 | 0.314 | 0.2753 | 0.2696 |
| ast | same line | 273 | 0.500 | 0.385 | 0.509 | 0.6888 | 0.6953 |
| ast | 1 away | 329 | 0.500 | 0.395 | 0.507 | 0.6454 | 0.6484 |
| ast | 2-3 away | 419 | 0.392 | 0.329 | 0.391 | 0.4321 | 0.4436 |
| ast | 4-6 away | 138 | 0.209 | 0.159 | 0.205 | 0.2319 | 0.2391 |
| 3pm | same line | 341 | 0.476 | 0.425 | 0.489 | 0.6880 | 0.6943 |
| 3pm | 1 away | 647 | 0.489 | 0.436 | 0.496 | 0.5508 | 0.5548 |
| 3pm | 2-3 away | 446 | 0.262 | 0.217 | 0.263 | 0.3045 | 0.3137 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | NO | +2.3% (501, 37 g, z -0.56) | WATCH |
| pts | consensus + model | NO | +0.7% (523, 37 g, z -0.92) | WATCH |
| pts | price only | NO | +1.3% (449, 37 g, z -0.95) | baseline |
| pts | price + model | NO | +1.1% (461, 37 g, z -0.99) | baseline |
| pts | price + model | YES | -100.0% (2, 2 g, z None) | baseline |
| reb | consensus | NO | +34.8% (83, 24 g, z 1.74) | WATCH |
| reb | consensus | YES | -77.8% (5, 5 g, z -3.5) | NO-GO |
| reb | consensus + model | NO | +14.3% (190, 32 g, z 0.65) | WATCH |
| reb | consensus + model | YES | -72.2% (4, 4 g, z -2.6) | NO-GO |
| reb | price + model | NO | -25.9% (3, 2 g, z 0.1) | baseline |
| ast | consensus | NO | +28.8% (469, 36 g, z 1.9) | WATCH |
| ast | consensus | YES | +900.0% (1, 1 g, z None) | WATCH |
| ast | consensus + model | NO | +29.2% (470, 36 g, z 1.94) | WATCH |
| ast | consensus + model | YES | +900.0% (1, 1 g, z None) | WATCH |
| ast | price only | NO | +28.4% (467, 36 g, z 1.76) | baseline |
| ast | price + model | NO | +28.4% (430, 36 g, z 1.71) | baseline |
| 3pm | consensus | NO | +31.1% (349, 31 g, z 3.08) | WATCH |
| 3pm | consensus + model | NO | +18.3% (473, 31 g, z 1.94) | WATCH |
| 3pm | consensus + model | YES | -100.0% (2, 2 g, z None) | NO-GO |
| 3pm | price only | NO | +18.5% (369, 31 g, z 1.98) | baseline |
| 3pm | price + model | NO | +15.9% (307, 31 g, z 1.99) | baseline |

## Kalshi ladder -> books (Price gap on books)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 329 | 0.6871 | 0.7074 | 0.6896 | 0.7322 | 0.7056 | 0.7233 |
| reb | 379 | 0.6847 | 0.6823 | 0.6791 | 0.7103 | 0.7021 | 0.7117 |
| ast | 302 | 0.6827 | 0.6899 | 0.6828 | 0.6886 | 0.6781 | 0.6863 |
| 3pm | 342 | 0.6909 | 0.6933 | 0.6923 | 0.6744 | 0.6770 | 0.6773 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 69 | 0.536 | 0.464 | 0.501 | 0.6848 | 0.6869 |
| pts | 1 away | 111 | 0.520 | 0.423 | 0.498 | 0.6955 | 0.6905 |
| pts | 2-3 away | 137 | 0.529 | 0.474 | 0.500 | 0.7018 | 0.6900 |
| reb | same line | 340 | 0.488 | 0.479 | 0.491 | 0.6939 | 0.6898 |
| reb | 1 away | 39 | 0.507 | 0.359 | 0.510 | 0.6954 | 0.7076 |
| ast | same line | 273 | 0.507 | 0.385 | 0.500 | 0.6993 | 0.6888 |
| 3pm | same line | 340 | 0.483 | 0.426 | 0.476 | 0.6923 | 0.6886 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | Over | -40.4% (3, 3 g, z -0.68) | NO-GO |
| pts | consensus | Under | -5.1% (119, 34 g, z -1.11) | NO-GO |
| pts | consensus + model | Over | -55.3% (4, 4 g, z -1.24) | NO-GO |
| pts | consensus + model | Under | -6.5% (145, 36 g, z -1.42) | NO-GO |
| pts | price only | Under | -0.4% (121, 35 g, z -1.0) | baseline |
| pts | price + model | Under | -1.8% (155, 36 g, z -0.91) | baseline |
| reb | consensus | Over | -25.1% (15, 11 g, z -0.54) | NO-GO |
| reb | consensus | Under | -8.8% (68, 29 g, z -1.01) | NO-GO |
| reb | consensus + model | Over | -19.7% (14, 13 g, z -1.03) | NO-GO |
| reb | consensus + model | Under | -15.9% (76, 33 g, z -1.76) | NO-GO |
| reb | price only | Over | -13.5% (13, 10 g, z -0.64) | baseline |
| reb | price only | Under | -12.6% (58, 25 g, z -1.86) | baseline |
| reb | price + model | Over | -43.5% (8, 7 g, z -2.1) | baseline |
| reb | price + model | Under | -23.4% (61, 27 g, z -2.47) | baseline |
| ast | consensus | Over | +6.0% (5, 5 g, z 0.09) | WATCH |
| ast | consensus | Under | +9.7% (106, 36 g, z 0.84) | WATCH |
| ast | consensus + model | Over | +6.0% (5, 5 g, z 0.09) | WATCH |
| ast | consensus + model | Under | +12.0% (107, 36 g, z 1.03) | WATCH |
| ast | price only | Over | +76.7% (3, 3 g, z 0.87) | baseline |
| ast | price only | Under | +12.1% (107, 36 g, z 0.64) | baseline |
| ast | price + model | Over | +162.0% (1, 1 g, z None) | baseline |
| ast | price + model | Under | +9.6% (111, 37 g, z 0.22) | baseline |
| 3pm | consensus | Over | +0.0% (2, 2 g, z 0.0) | NO-GO |
| 3pm | consensus | Under | +7.9% (22, 15 g, z 0.24) | WATCH |
| 3pm | consensus + model | Over | -33.3% (3, 3 g, z -0.5) | NO-GO |
| 3pm | consensus + model | Under | +32.0% (41, 21 g, z 1.85) | WATCH |
| 3pm | price only | Under | +97.5% (4, 4 g, z 1.48) | baseline |
| 3pm | price + model | Over | -43.5% (4, 4 g, z -0.77) | baseline |
| 3pm | price + model | Under | +20.2% (72, 28 g, z 0.95) | baseline |

## Kalshi rung from the rest of its ladder (Structural)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 12,591 | 0.5041 | 0.5078 | 0.5357 | 0.5026 | 0.5015 | 0.5008 |
| reb | 9,569 | 0.5446 | 0.5448 | 0.5557 | 0.5440 | 0.5429 | 0.5436 |
| ast | 6,683 | 0.5257 | 0.5271 | 0.5302 | 0.5221 | 0.5208 | 0.5206 |
| 3pm | 8,066 | 0.5038 | 0.5020 | 0.5072 | 0.4968 | 0.4977 | 0.4968 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 66 | 0.329 | 0.151 | 0.321 | 0.4528 | 0.4406 |
| pts | 1 away | 430 | 0.531 | 0.498 | 0.524 | 0.6881 | 0.6861 |
| pts | 2-3 away | 573 | 0.533 | 0.483 | 0.524 | 0.6678 | 0.6596 |
| pts | 4-6 away | 11,465 | 0.440 | 0.402 | 0.435 | 0.5117 | 0.5097 |
| pts | 7+ away | 57 | 0.225 | 0.193 | 0.238 | 0.3797 | 0.4146 |
| reb | 1 away | 3,486 | 0.511 | 0.528 | 0.518 | 0.6575 | 0.6569 |
| reb | 2-3 away | 5,997 | 0.442 | 0.412 | 0.441 | 0.4869 | 0.4891 |
| reb | 4-6 away | 72 | 0.202 | 0.167 | 0.198 | 0.2508 | 0.2469 |
| ast | 1 away | 2,746 | 0.513 | 0.491 | 0.515 | 0.6491 | 0.6488 |
| ast | 2-3 away | 3,868 | 0.390 | 0.368 | 0.385 | 0.4498 | 0.4476 |
| ast | 4-6 away | 47 | 0.133 | 0.149 | 0.153 | 0.2145 | 0.2398 |
| 3pm | 1 away | 7,995 | 0.443 | 0.402 | 0.442 | 0.5179 | 0.5187 |
| 3pm | 2-3 away | 57 | 0.218 | 0.246 | 0.234 | 0.2633 | 0.2683 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | NO | +8.0% (1,763, 380 g, z 2.03) | GO |
| pts | consensus | YES | -20.5% (71, 48 g, z -1.01) | NO-GO |
| pts | consensus + model | NO | +7.3% (1,782, 383 g, z 2.26) | GO |
| pts | consensus + model | YES | -17.2% (65, 45 g, z -0.83) | NO-GO |
| pts | price + model | NO | +3.8% (1,255, 309 g, z 1.38) | baseline |
| pts | price + model | YES | +88.3% (2, 2 g, z 3.3) | baseline |
| reb | consensus | NO | +8.4% (641, 221 g, z 1.51) | WATCH |
| reb | consensus | YES | +2.4% (170, 114 g, z 0.09) | WATCH |
| reb | consensus + model | NO | +7.8% (648, 222 g, z 1.44) | WATCH |
| reb | consensus + model | YES | +6.3% (167, 114 g, z 0.31) | WATCH |
| reb | price + model | NO | +17.5% (127, 39 g, z 1.5) | baseline |
| reb | price + model | YES | +28.6% (3, 3 g, z 1.91) | baseline |
| ast | consensus | NO | +20.8% (524, 228 g, z 1.45) | WATCH |
| ast | consensus | YES | -14.3% (202, 109 g, z -0.84) | NO-GO |
| ast | consensus + model | NO | +14.3% (754, 223 g, z 1.99) | WATCH |
| ast | consensus + model | YES | +10.0% (224, 132 g, z 0.91) | WATCH |
| ast | price + model | NO | +10.9% (437, 138 g, z 1.36) | baseline |
| ast | price + model | YES | +9.4% (42, 23 g, z 0.99) | baseline |
| 3pm | consensus | NO | +15.2% (1,581, 279 g, z 2.92) | GO |
| 3pm | consensus | YES | -12.8% (42, 26 g, z -1.6) | NO-GO |
| 3pm | consensus + model | NO | +16.8% (1,526, 278 g, z 3.3) | GO |
| 3pm | consensus + model | YES | +13.1% (29, 22 g, z -0.08) | WATCH |
| 3pm | price only | NO | +5.2% (1,185, 282 g, z 1.66) | baseline |
| 3pm | price + model | NO | +12.4% (1,300, 257 g, z 2.9) | baseline |
| 3pm | price + model | YES | +19.1% (1, 1 g, z None) | baseline |
