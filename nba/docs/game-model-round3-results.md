# Game model round 3: results

Generated 2026-11-10T22:45Z by `nba/scripts/test_game_model_round3.py`. Rules: [game-model-round3.md](game-model-round3.md) (committed before this ran).

## What 2024-25 chose

**W = 0.75, KL = 0.16** (2024-25 margin MAE 10.7622; shipped 10.9071). Neither is on a grid endpoint.

| W \ KL | 0.04 | 0.08 | 0.12 | 0.16 | 0.24 | 0.32 | 0.5 |
|---|---|---|---|---|---|---|---|
| 0.25 | 10.8824 | 10.8764 | 10.9622 | 11.0978 | 11.4337 | 11.8513 | 13.2867 |
| 0.5 | 10.8937 | 10.8106 | 10.8157 | 10.8522 | 10.9874 | 11.1869 | 11.9172 |
| 0.75 | 10.9394 | 10.8199 | 10.7779 | 10.7622 | 10.7638 | 10.8035 | 11.0325 |
| 1.0 | 11.0146 | 10.9009 | 10.8584 | 10.8346 | 10.8051 | 10.7882 | 10.7676 |

## 2024-25 (the fit season, in sample for L)

| | Games | Margin MAE | Shipped minus variant | t | First 4 weeks MAE | t | Closing line MAE |
|---|---|---|---|---|---|---|---|
| S | 1320 | 10.907 | +0.000 | +0.00 | 9.632 (n 210) | +0.00 | 10.636 |
| L | 1320 | 10.762 | +0.145 | +3.35 | 9.481 (n 210) | +1.58 | 10.636 |

| | Info test g (t) | Spread 0+ | 3+ | 5+ | Winner | Market favourite | Mean gap to the line | Games at 3+ | at 5+ | sd model / line |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 0.044 (0.32) | 686-634 52.0% | 218-191 53.3% | 61-74 45.2% | 895-425 67.8% | 910-410 68.9% | 2.39 | 31% | 10% | 7.12 / 7.76 |
| L | 0.164 (1.0) | 685-635 51.9% | 129-118 52.2% | 36-36 50.0% | 905-415 68.6% | 910-410 68.9% | 1.81 | 19% | 6% | 7.45 / 7.76 |

## 2025-26 (the test)

| | Games | Margin MAE | Shipped minus variant | t | First 4 weeks MAE | t | Closing line MAE |
|---|---|---|---|---|---|---|---|
| S | 1321 | 11.294 | +0.000 | +0.00 | 10.674 (n 206) | +0.00 | 11.012 |
| L | 1321 | 11.193 | +0.101 | +2.21 | 10.368 (n 206) | +2.54 | 11.012 |

| | Info test g (t) | Spread 0+ | 3+ | 5+ | Winner | Market favourite | Mean gap to the line | Games at 3+ | at 5+ | sd model / line |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 0.186 (1.37) | 656-665 49.7% | 204-207 49.6% | 71-73 49.3% | 901-420 68.2% | 903-418 68.4% | 2.45 | 31% | 11% | 7.5 / 8.24 |
| L | 0.221 (1.33) | 657-664 49.7% | 117-126 48.1% | 31-34 47.7% | 899-422 68.1% | 903-418 68.4% | 1.86 | 18% | 5% | 7.82 / 8.24 |

## This season, replayed (154 games; flagged for monitoring, n = 154)

| | Margin MAE | Shipped minus variant | t | Spread 0+ | 3+ | 5+ | Winner | Disagrees with the favourite (won) | Picks that change side | Mean gap | Games at 3+ | at 5+ | sd model / line |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S | 11.673 | +0.000 | +0.00 | 68-85 | 24-27 | 12-4 | 100-53 | 17 (5) | 0 | 2.49 | 33% | 10% | 5.96 / 7.2 |
| L | 11.421 | +0.252 | +2.11 | 70-84 | 13-12 | 4-3 | 104-50 | 12 (4) | 26 | 1.79 | 16% | 4% | 6.67 / 7.2 |

The locked line's MAE on these games is 11.084. Row S is the shipped model and equals the locked record. Row L is a replay, not a record: no pick was locked with it.

## Verdict

**Tie: not shipped.**

- The bar was a margin-MAE t of 2.5 on 2025-26. L scored +2.21 there (11.294 to 11.193 points), +3.35 on the season it was fitted on, and +2.11 on this season's 154 games (11.673 to 11.421). Closer in every season, and short of the bar that was set before it ran. The bar stands.
- It closes about a third of the distance to the closing line (2025-26: shipped 11.294, L 11.193, the line 11.012) and sits closer to it: mean gap 2.45 to 1.86 points, games at a 5-point gap 11% to 5%.
- **It does nothing for the picks.** Against the closing spread L is 657-664 49.7% on 2025-26 (shipped 656-665 49.7%), 31-34 47.7% at a 5-point gap, and its winner pick is 899-422 68.1% where the market's favourite is 903-418 68.4%. A more accurate margin moved the model toward the line; it did not put it on the right side of the line.
- `game_model.json`, the Slate and the Game Picks record are unchanged. Option L stays in `build_game_model.py`, off unless `MK_W` is set.

**Flagged for close monitoring** (CLAUDE.md), all replays on n = 154: L margin MAE 11.673 to 11.421; L winner 100-53 to 104-50; L spread 68-85 to 70-84. One standard error on a win rate at this n is 4 points.
