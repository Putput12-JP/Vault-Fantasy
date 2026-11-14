# Game model round 2: results

Generated 2026-11-10T22:41Z by `nba/scripts/test_game_model_round2.py`. Rules: [game-model-round2.md](game-model-round2.md) (committed before this ran).

## What the tune seasons chose

- **E, early step:** B = 0, N = None (tune margin MAE 10.5252; shipped 10.5252).
- **M, blowout cap:** CAP = None (tune margin MAE 10.5252; shipped 10.5252).

| E grid | B0 NNone | B1 N10 | B1 N20 | B1 N30 | B2 N10 | B2 N20 | B2 N30 | B3 N10 | B3 N20 | B3 N30 | B4 N10 | B4 N20 | B4 N30 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Tune MAE | 10.5252 | 10.5336 | 10.5364 | 10.5511 | 10.551 | 10.5653 | 10.6004 | 10.5749 | 10.6059 | 10.6593 | 10.6055 | 10.652 | 10.7204 |
| First 4 weeks | 10.245 | 10.2841 | 10.2727 | 10.2757 | 10.3595 | 10.3791 | 10.3934 | 10.4736 | 10.5367 | 10.5659 | 10.6288 | 10.7293 | 10.7755 |

| M grid | None | 10 | 13 | 16 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|
| Tune MAE | 10.5252 | 10.5534 | 10.5373 | 10.5322 | 10.5302 | 10.5265 | 10.5252 |
| First 4 weeks | 10.245 | 10.2121 | 10.211 | 10.2219 | 10.2305 | 10.234 | 10.2404 |

## Test seasons (2024-25 and 2025-26, injury report at tip)

| Variant | Season | Games | Margin MAE | Shipped minus variant | t | First 4 weeks MAE | t | Closing line MAE |
|---|---|---|---|---|---|---|---|---|
| S | 2025 | 1320 | 10.907 | +0.000 | +0.00 | 9.632 (n 210) | +0.00 | 10.636 |
| S | 2026 | 1321 | 11.294 | +0.000 | +0.00 | 10.674 (n 206) | +0.00 | 11.012 |
| S | all | 2641 | 11.101 | +0.000 | +0.00 | 10.148 (n 416) | +0.00 | 10.824 |
| E | 2025 | 1320 | 10.907 | +0.000 | +0.00 | 9.632 (n 210) | +0.00 | 10.636 |
| E | 2026 | 1321 | 11.294 | +0.000 | +0.00 | 10.674 (n 206) | +0.00 | 11.012 |
| E | all | 2641 | 11.101 | +0.000 | +0.00 | 10.148 (n 416) | +0.00 | 10.824 |
| M | 2025 | 1320 | 10.907 | +0.000 | +0.00 | 9.632 (n 210) | +0.00 | 10.636 |
| M | 2026 | 1321 | 11.294 | +0.000 | +0.00 | 10.674 (n 206) | +0.00 | 11.012 |
| M | all | 2641 | 11.101 | +0.000 | +0.00 | 10.148 (n 416) | +0.00 | 10.824 |
| EM | 2025 | 1320 | 10.907 | +0.000 | +0.00 | 9.632 (n 210) | +0.00 | 10.636 |
| EM | 2026 | 1321 | 11.294 | +0.000 | +0.00 | 10.674 (n 206) | +0.00 | 11.012 |
| EM | all | 2641 | 11.101 | +0.000 | +0.00 | 10.148 (n 416) | +0.00 | 10.824 |

| Variant | Info test g (t) | Spread 0+ | 3+ | 5+ | Verdict |
|---|---|---|---|---|---|
| S | 0.118 (1.23) | 1342-1299 50.8% | 422-398 51.5% | 132-147 47.3% | reference |
| E | 0.118 (1.23) | 1342-1299 50.8% | 422-398 51.5% | 132-147 47.3% | Tie |
| M | 0.118 (1.23) | 1342-1299 50.8% | 422-398 51.5% | 132-147 47.3% | Tie |
| EM | 0.118 (1.23) | 1342-1299 50.8% | 422-398 51.5% | 132-147 47.3% | Tie |

## This season, replayed (154 games; reported, not part of the verdict)

| Variant | Margin MAE | Shipped minus variant | t | Spread 0+ | 3+ | 5+ | Winner | Picks that change side |
|---|---|---|---|---|---|---|---|---|
| S | 11.673 | +0.000 | +0.00 | 68-85 | 24-27 | 12-4 | 100-53 | 0 |
| E | 11.673 | +0.000 | +0.00 | 68-85 | 24-27 | 12-4 | 100-53 | 0 |
| M | 11.673 | +0.000 | +0.00 | 68-85 | 24-27 | 12-4 | 100-53 | 0 |
| EM | 11.673 | +0.000 | +0.00 | 68-85 | 24-27 | 12-4 | 100-53 | 0 |

The locked line's MAE on these games is 11.084. Row S is the shipped model replayed and equals the locked record.

## Verdict

**NO-GO, both.** On the tune seasons no early step and no cap beat the shipped model over the whole season, so the grid chose no change for E and for M and the scored variants are the shipped model. A bigger step early did not even help the first four weeks (it was worse at every B). The cap helped the first four weeks by about 0.03 points and was no better over the whole season at any value. `game_model.json` is unchanged.

The audit tables this round promised (the record by grade, injury adjustment, favourite or underdog and stage of the season, this season and in the two test seasons) are in [game-picks-audit.md](game-picks-audit.md).
