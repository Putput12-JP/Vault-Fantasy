# Steals, blocks, turnovers and steals + blocks

Generated 2026-10-07T23:49Z. Same walk-forward projection as `build_prop_model.py`; these markets only.

## Verdict: NO-GO for all four

No prior season of main-line prices to fit a calibration or a market blend on (ESPN steals/blocks main lines start in 2025-26), no book history for the other markets, and Kalshi lists none of them. Shown on the board, never a gated best bet.

## Projection accuracy (2025-26, injury report 30 min pre-tip)

| market | MAE | bias | mean actual | player-games |
|---|---|---|---|---|
| stl | 0.716 | -0.028 | 0.776 | 56,083 |
| blk | 0.508 | -0.011 | 0.456 | 56,083 |
| tov | 0.883 | -0.034 | 1.275 | 56,083 |
| fgm | 1.737 | -0.133 | 3.9 | 56,083 |
| fga | 2.711 | -0.251 | 8.329 | 56,083 |
| ftm | 1.298 | -0.074 | 1.66 | 56,083 |
| fta | 1.575 | -0.094 | 2.125 | 56,083 |
| tpa | 1.482 | -0.117 | 3.477 | 56,083 |
| oreb | 0.848 | -0.033 | 1.051 | 56,083 |
| dreb | 1.535 | -0.078 | 3.053 | 56,083 |
| pf | 1.057 | -0.034 | 1.81 | 56,083 |
| sb | 0.926 | -0.039 | 1.232 | 56,083 |

## Against ESPN 2025-26 closing lines (main lines only)

| market | rows | games | Brier model | Brier market | log loss model | log loss market | bets at 3+ pts | win | ROI |
|---|---|---|---|---|---|---|---|---|---|
| stl | 606 | 72 | 0.2354 | 0.2353 | 0.6635 | 0.6636 | 473 | 0.5666 | 0.0648 |
| blk | 529 | 67 | 0.2291 | 0.2247 | 0.6576 | 0.6404 | 409 | 0.5819 | -0.0033 |

## Self-check at the line a book would post (floor of the mean + 0.5)

| market | player-games | over rate | Brier model | Brier base rate |
|---|---|---|---|---|
| stl | 47,036 | 0.447 | 0.2418 | 0.2472 |
| blk | 28,991 | 0.389 | 0.2303 | 0.2378 |
| tov | 49,992 | 0.46 | 0.2414 | 0.2484 |
| fgm | 51,921 | 0.497 | 0.2512 | 0.25 |
| fga | 51,997 | 0.52 | 0.2543 | 0.2496 |
| ftm | 48,253 | 0.411 | 0.2395 | 0.242 |
| fta | 49,860 | 0.426 | 0.2442 | 0.2445 |
| tpa | 47,522 | 0.496 | 0.2491 | 0.25 |
| oreb | 46,658 | 0.439 | 0.2418 | 0.2463 |
| dreb | 51,870 | 0.482 | 0.2493 | 0.2497 |
| pf | 51,715 | 0.489 | 0.2481 | 0.2499 |
| sb | 50,561 | 0.462 | 0.2447 | 0.2485 |

Variance fits (v0, v1, v2): {"stl": [0.11237, 1.07623, -0.11654], "blk": [0.05421, 1.02121, 0.04624], "tov": [0.0397, 1.09486, -0.03891], "fgm": [0.43267, 1.32802, -0.01934], "fga": [1.87246, 1.33914, -0.0069], "ftm": [0.04571, 2.0408, -0.00981], "fta": [0.23151, 2.13469, -0.00418], "tpa": [0.11389, 1.29333, -0.03259], "oreb": [0.04125, 1.25946, 0.01427], "dreb": [0.44887, 1.09862, 0.02042], "pf": [0.50626, 0.84569, -0.08065], "sb": [0.1786, 1.04093, 0.00337]}
