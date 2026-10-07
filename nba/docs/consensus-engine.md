# Consensus fair engine: backtest

Generated 2026-10-07T00:44Z by `nba/scripts/build_consensus.py`. 2025-26 only (the seasons with both venues archived):
blends fit on the first half by tip time, scored and bet on the second half, 3%+ edge after fees.
Consensus = one venue's prices moved to the other venue's line through prop model v2's distribution shape
(`scripts/consensus.py`); our projection is not in it. "consensus + model" adds our projection in a fitted blend.

Ship rule (fixed before running): GO = second-half ROI > 0 with z >= 2 over 50+ games; WATCH = positive; else NO-GO.
Baselines on the same rows (not judged): "price only" = the venue's own price recalibrated (catches plain venue
bias, e.g. Kalshi overs), "price + model" = the blend the current GO signals use.

## Books -> Kalshi (Price gap on Kalshi)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 1,114 | 0.4496 | 0.4448 | 0.4971 | 0.4519 | 0.4545 | 0.4540 |
| reb | 1,610 | 0.5079 | 0.5070 | 0.5215 | 0.5027 | 0.5048 | 0.5028 |
| ast | 1,159 | 0.5336 | 0.5269 | 0.5324 | 0.5101 | 0.5123 | 0.5100 |
| 3pm | 1,436 | 0.5120 | 0.5069 | 0.5150 | 0.5015 | 0.5010 | 0.5014 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 70 | 0.501 | 0.457 | 0.510 | 0.6873 | 0.6945 |
| pts | 1 away | 115 | 0.505 | 0.426 | 0.513 | 0.6773 | 0.6760 |
| pts | 2-3 away | 264 | 0.476 | 0.428 | 0.493 | 0.6222 | 0.6271 |
| pts | 4-6 away | 287 | 0.404 | 0.387 | 0.423 | 0.5134 | 0.5093 |
| pts | 7+ away | 378 | 0.189 | 0.143 | 0.208 | 0.2412 | 0.2569 |
| reb | same line | 341 | 0.490 | 0.478 | 0.495 | 0.6893 | 0.6931 |
| reb | 1 away | 373 | 0.506 | 0.488 | 0.510 | 0.6345 | 0.6410 |
| reb | 2-3 away | 637 | 0.481 | 0.449 | 0.481 | 0.4643 | 0.4695 |
| reb | 4-6 away | 259 | 0.323 | 0.255 | 0.314 | 0.2755 | 0.2696 |
| ast | same line | 273 | 0.500 | 0.385 | 0.509 | 0.6888 | 0.6953 |
| ast | 1 away | 329 | 0.500 | 0.395 | 0.507 | 0.6454 | 0.6484 |
| ast | 2-3 away | 419 | 0.392 | 0.329 | 0.391 | 0.4322 | 0.4436 |
| ast | 4-6 away | 138 | 0.209 | 0.159 | 0.205 | 0.2316 | 0.2391 |
| 3pm | same line | 341 | 0.476 | 0.425 | 0.489 | 0.6880 | 0.6943 |
| 3pm | 1 away | 647 | 0.489 | 0.436 | 0.496 | 0.5508 | 0.5548 |
| 3pm | 2-3 away | 446 | 0.262 | 0.217 | 0.263 | 0.3045 | 0.3137 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | NO | +2.2% (498, 37 g, z -0.72) | WATCH |
| pts | consensus + model | NO | +1.2% (524, 37 g, z -0.98) | WATCH |
| pts | price only | NO | +1.3% (449, 37 g, z -0.95) | baseline |
| pts | price + model | NO | +1.3% (461, 37 g, z -0.98) | baseline |
| pts | price + model | YES | -100.0% (1, 1 g, z None) | baseline |
| reb | consensus | NO | +35.5% (83, 24 g, z 1.75) | WATCH |
| reb | consensus | YES | -77.8% (5, 5 g, z -3.5) | NO-GO |
| reb | consensus + model | NO | +18.8% (149, 29 g, z 0.75) | WATCH |
| reb | consensus + model | YES | -72.2% (4, 4 g, z -2.6) | NO-GO |
| reb | price + model | NO | +122.2% (4, 2 g, z 0.55) | baseline |
| ast | consensus | NO | +28.8% (469, 36 g, z 1.91) | WATCH |
| ast | consensus | YES | +900.0% (1, 1 g, z None) | WATCH |
| ast | consensus + model | NO | +29.4% (464, 36 g, z 1.95) | WATCH |
| ast | consensus + model | YES | +900.0% (1, 1 g, z None) | WATCH |
| ast | price only | NO | +28.4% (467, 36 g, z 1.76) | baseline |
| ast | price + model | NO | +27.6% (413, 36 g, z 1.62) | baseline |
| 3pm | consensus | NO | +31.5% (347, 31 g, z 3.12) | WATCH |
| 3pm | consensus + model | NO | +18.8% (478, 31 g, z 2.09) | WATCH |
| 3pm | price only | NO | +18.5% (369, 31 g, z 1.98) | baseline |
| 3pm | price + model | NO | +17.7% (314, 31 g, z 2.13) | baseline |

## Kalshi ladder -> books (Price gap on books)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 329 | 0.6871 | 0.7070 | 0.6945 | 0.7349 | 0.7079 | 0.7271 |
| reb | 379 | 0.6847 | 0.6822 | 0.6880 | 0.7046 | 0.6964 | 0.7039 |
| ast | 302 | 0.6827 | 0.6900 | 0.6834 | 0.6875 | 0.6775 | 0.6855 |
| 3pm | 342 | 0.6909 | 0.6932 | 0.6921 | 0.6736 | 0.6782 | 0.6786 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 69 | 0.534 | 0.464 | 0.501 | 0.6848 | 0.6869 |
| pts | 1 away | 111 | 0.519 | 0.423 | 0.498 | 0.6949 | 0.6905 |
| pts | 2-3 away | 137 | 0.529 | 0.474 | 0.500 | 0.7016 | 0.6900 |
| reb | same line | 340 | 0.488 | 0.479 | 0.491 | 0.6939 | 0.6898 |
| reb | 1 away | 39 | 0.507 | 0.359 | 0.510 | 0.6953 | 0.7076 |
| ast | same line | 273 | 0.508 | 0.385 | 0.500 | 0.6993 | 0.6888 |
| 3pm | same line | 340 | 0.484 | 0.426 | 0.476 | 0.6923 | 0.6886 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | Over | -40.4% (3, 3 g, z -0.68) | NO-GO |
| pts | consensus | Under | -5.1% (121, 34 g, z -1.12) | NO-GO |
| pts | consensus + model | Over | -64.2% (5, 5 g, z -1.8) | NO-GO |
| pts | consensus + model | Under | -6.2% (139, 36 g, z -1.54) | NO-GO |
| pts | price only | Under | -0.4% (121, 35 g, z -1.0) | baseline |
| pts | price + model | Over | -100.0% (2, 2 g, z None) | baseline |
| pts | price + model | Under | -1.7% (151, 36 g, z -0.96) | baseline |
| reb | consensus | Over | -25.1% (15, 11 g, z -0.54) | NO-GO |
| reb | consensus | Under | -8.8% (68, 29 g, z -1.01) | NO-GO |
| reb | consensus + model | Over | -25.1% (15, 11 g, z -0.54) | NO-GO |
| reb | consensus + model | Under | -10.1% (69, 30 g, z -1.26) | NO-GO |
| reb | price only | Over | -13.5% (13, 10 g, z -0.64) | baseline |
| reb | price only | Under | -12.6% (58, 25 g, z -1.86) | baseline |
| reb | price + model | Over | -13.5% (13, 10 g, z -0.64) | baseline |
| reb | price + model | Under | -12.6% (58, 25 g, z -1.86) | baseline |
| ast | consensus | Over | +6.0% (5, 5 g, z 0.09) | WATCH |
| ast | consensus | Under | +9.7% (106, 36 g, z 0.84) | WATCH |
| ast | consensus + model | Over | +6.0% (5, 5 g, z 0.09) | WATCH |
| ast | consensus + model | Under | +12.0% (107, 36 g, z 1.03) | WATCH |
| ast | price only | Over | +76.7% (3, 3 g, z 0.87) | baseline |
| ast | price only | Under | +12.1% (107, 36 g, z 0.64) | baseline |
| ast | price + model | Over | +76.7% (3, 3 g, z 0.87) | baseline |
| ast | price + model | Under | +8.4% (109, 37 g, z 0.22) | baseline |
| 3pm | consensus | Over | +0.0% (2, 2 g, z 0.0) | NO-GO |
| 3pm | consensus | Under | +7.9% (22, 15 g, z 0.24) | WATCH |
| 3pm | consensus + model | Over | -21.3% (3, 3 g, z -0.27) | NO-GO |
| 3pm | consensus + model | Under | +19.8% (57, 24 g, z 0.91) | WATCH |
| 3pm | price only | Under | +97.5% (4, 4 g, z 1.48) | baseline |
| 3pm | price + model | Over | -22.6% (5, 5 g, z -0.47) | baseline |
| 3pm | price + model | Under | +19.5% (89, 28 g, z 1.12) | baseline |

## Kalshi rung from the rest of its ladder (Structural)

| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |
|---|---|---|---|---|---|---|---|
| pts | 12,563 | 0.5040 | 0.5078 | 0.5389 | 0.5026 | 0.5011 | 0.5008 |
| reb | 9,552 | 0.5450 | 0.5451 | 0.5608 | 0.5442 | 0.5434 | 0.5436 |
| ast | 6,678 | 0.5256 | 0.5271 | 0.5309 | 0.5213 | 0.5198 | 0.5199 |
| 3pm | 8,051 | 0.5042 | 0.5023 | 0.5078 | 0.4965 | 0.4974 | 0.4966 |

Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):

| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |
|---|---|---|---|---|---|---|---|
| pts | same line | 66 | 0.329 | 0.151 | 0.321 | 0.4526 | 0.4406 |
| pts | 1 away | 428 | 0.531 | 0.500 | 0.524 | 0.6872 | 0.6855 |
| pts | 2-3 away | 573 | 0.533 | 0.483 | 0.524 | 0.6676 | 0.6596 |
| pts | 4-6 away | 11,439 | 0.440 | 0.401 | 0.435 | 0.5118 | 0.5098 |
| pts | 7+ away | 57 | 0.224 | 0.193 | 0.238 | 0.3793 | 0.4146 |
| reb | 1 away | 3,477 | 0.511 | 0.527 | 0.518 | 0.6574 | 0.6566 |
| reb | 2-3 away | 5,989 | 0.442 | 0.412 | 0.441 | 0.4862 | 0.4886 |
| reb | 4-6 away | 72 | 0.201 | 0.167 | 0.198 | 0.2511 | 0.2469 |
| ast | 1 away | 2,743 | 0.514 | 0.490 | 0.514 | 0.6495 | 0.6490 |
| ast | 2-3 away | 3,866 | 0.390 | 0.368 | 0.385 | 0.4497 | 0.4474 |
| ast | 4-6 away | 47 | 0.133 | 0.149 | 0.153 | 0.2147 | 0.2398 |
| 3pm | 1 away | 7,980 | 0.443 | 0.402 | 0.442 | 0.5183 | 0.5191 |
| 3pm | 2-3 away | 57 | 0.218 | 0.246 | 0.234 | 0.2631 | 0.2683 |

Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:

| Stat | Fair | Side | Result | Verdict |
|---|---|---|---|---|
| pts | consensus | NO | +6.3% (1,743, 381 g, z 1.73) | WATCH |
| pts | consensus | YES | -21.9% (66, 44 g, z -1.17) | NO-GO |
| pts | consensus + model | NO | +8.8% (1,835, 382 g, z 2.38) | GO |
| pts | consensus + model | YES | -22.6% (62, 42 g, z -1.29) | NO-GO |
| pts | price + model | NO | +4.2% (1,359, 303 g, z 1.18) | baseline |
| pts | price + model | YES | +61.6% (1, 1 g, z None) | baseline |
| reb | consensus | NO | +5.8% (670, 225 g, z 1.34) | WATCH |
| reb | consensus | YES | +13.0% (151, 105 g, z 0.9) | WATCH |
| reb | consensus + model | NO | +7.7% (701, 225 g, z 1.5) | WATCH |
| reb | consensus + model | YES | +15.2% (148, 103 g, z 1.18) | WATCH |
| reb | price + model | NO | +8.7% (323, 75 g, z 1.07) | baseline |
| reb | price + model | YES | +6.8% (5, 4 g, z 0.97) | baseline |
| ast | consensus | NO | +21.1% (538, 233 g, z 1.76) | WATCH |
| ast | consensus | YES | -13.7% (204, 110 g, z -0.92) | NO-GO |
| ast | consensus + model | NO | +10.8% (787, 222 g, z 0.41) | WATCH |
| ast | consensus + model | YES | -3.8% (214, 126 g, z -0.81) | NO-GO |
| ast | price + model | NO | +10.8% (469, 120 g, z 1.68) | baseline |
| ast | price + model | YES | +59.7% (35, 18 g, z 2.03) | baseline |
| 3pm | consensus | NO | +15.3% (1,584, 279 g, z 2.95) | GO |
| 3pm | consensus | YES | -7.8% (43, 26 g, z -1.5) | NO-GO |
| 3pm | consensus + model | NO | +16.5% (1,545, 277 g, z 2.84) | GO |
| 3pm | consensus + model | YES | +17.2% (27, 19 g, z 0.04) | WATCH |
| 3pm | price only | NO | +5.9% (1,191, 282 g, z 1.86) | baseline |
| 3pm | price + model | NO | +15.6% (1,350, 258 g, z 2.48) | baseline |
| 3pm | price + model | YES | +19.1% (1, 1 g, z None) | baseline |
