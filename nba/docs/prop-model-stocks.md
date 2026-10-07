# Steals, blocks, turnovers and steals + blocks

Generated 2026-10-07T23:43Z. Same walk-forward projection as `build_prop_model.py`; these markets only.

## Verdict: NO-GO for all four

No prior season of main-line prices to fit a calibration or a market blend on (ESPN steals/blocks main lines start in 2025-26), no book history for turnovers or steals + blocks, and Kalshi lists none of them. Shown on the board, never a gated best bet.

## Projection accuracy (2025-26, injury report 30 min pre-tip)

| market | MAE | bias | mean actual | player-games |
|---|---|---|---|---|
| stl | 0.716 | -0.028 | 0.776 | 56,083 |
| blk | 0.508 | -0.011 | 0.456 | 56,083 |
| tov | 0.883 | -0.034 | 1.275 | 56,083 |
| sb | 0.926 | -0.039 | 1.232 | 56,083 |

## Against ESPN 2025-26 closing lines (main lines only)

| market | rows | games | Brier model | Brier market | log loss model | log loss market | bets at 3+ pts | win | ROI |
|---|---|---|---|---|---|---|---|---|---|
| stl | 606 | 72 | 0.2354 | 0.2353 | 0.6635 | 0.6636 | 473 | 0.5666 | 0.0648 |
| blk | 529 | 67 | 0.2291 | 0.2247 | 0.6576 | 0.6404 | 409 | 0.5819 | -0.0033 |

Variance fits (v0, v1, v2): {"stl": [0.11237, 1.07623, -0.11654], "blk": [0.05421, 1.02121, 0.04624], "tov": [0.0397, 1.09486, -0.03891], "sb": [0.1786, 1.04093, 0.00337]}
