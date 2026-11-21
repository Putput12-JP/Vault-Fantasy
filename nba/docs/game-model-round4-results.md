# Game model round 4: results

Generated 2026-11-10T22:58Z by `nba/scripts/test_game_model_round4.py`. Rules: [game-model-round4.md](game-model-round4.md) (committed before this ran).

Ratings only in every row: no injury report, no lineups, no line. N = the shipped ratings. NL = round 3's line-taught ratings.

## History: 2025-26, the held-out season

1,321 games with an opening and a closing spread. Ratings as of 36 hours before tip. The spread moved 1.48 points on average from open to close.

| Ratings | Gap | Record vs the open | Win% | Line move toward the pick (pts) | t | Moved toward / away |
|---|---|---|---|---|---|---|
| N | 0+ | 661-660 | 50.0% | +0.24 | +4.0 | 537 / 461 |
| N | 2+ | 352-340 | 50.9% | +0.34 | +3.8 | 288 / 235 |
| N | 3+ | 224-230 | 49.3% | +0.33 | +2.9 | 184 / 159 |
| N | 5+ | 94-84 | 52.8% | +0.43 | +2.0 | 70 / 64 |
| NL | 0+ | 682-639 | 51.6% | +0.27 | +4.6 | 554 / 444 |
| NL | 2+ | 316-302 | 51.1% | +0.49 | +5.0 | 284 / 198 |
| NL | 3+ | 184-197 | 48.3% | +0.47 | +3.5 | 164 / 127 |
| NL | 5+ | 65-66 | 49.6% | +0.57 | +2.0 | 55 / 42 |

## History: 2024-25, the season already looked at (in sample for the 2+ cut)

1,320 games with an opening and a closing spread. Ratings as of 36 hours before tip. The spread moved 1.86 points on average from open to close.

| Ratings | Gap | Record vs the open | Win% | Line move toward the pick (pts) | t | Moved toward / away |
|---|---|---|---|---|---|---|
| N | 0+ | 679-641 | 51.4% | +0.53 | +6.7 | 563 / 455 |
| N | 2+ | 394-336 | 54.0% | +0.93 | +7.7 | 335 / 230 |
| N | 3+ | 257-215 | 54.4% | +1.26 | +7.3 | 230 / 139 |
| N | 5+ | 116-86 | 57.4% | +2.44 | +7.2 | 109 / 58 |
| NL | 0+ | 650-670 | 49.2% | +0.66 | +8.4 | 607 / 411 |
| NL | 2+ | 337-265 | 56.0% | +1.25 | +8.7 | 308 / 170 |
| NL | 3+ | 213-172 | 55.3% | +1.56 | +7.7 | 201 / 110 |
| NL | 5+ | 89-63 | 58.6% | +3.46 | +8.6 | 98 / 34 |

## This season: the recorder's tape

154 games. First DraftKings spread seen a median 24.9 hours before tip (quartiles 21.8 and 32.2); it moved 1.27 points on average by the last look. Ratings as of 12 hours before that first sight.

| Ratings | Gap | Record vs the first line | Win% | Line move toward the pick (pts) | t | Moved toward / away | Units at the first-sight price (priced) |
|---|---|---|---|---|---|---|---|
| N | 0+ | 69-85 | 44.8% | +0.36 | +2.5 | 64 / 43 | -22.43 (154) |
| N | 2+ | 38-46 | 45.2% | +0.25 | +1.3 | 34 / 22 | -11.47 (84) |
| N | 3+ | 27-24 | 52.9% | +0.28 | +1.0 | 20 / 14 | +0.56 (51) |
| N | 5+ | 14-6 | 70.0% | +0.65 | +1.2 | 10 / 5 | +6.74 (20) |
| NL | 0+ | 73-81 | 47.4% | +0.30 | +2.0 | 63 / 44 | -14.89 (154) |
| NL | 2+ | 33-30 | 52.4% | +0.59 | +2.2 | 29 / 15 | -0.09 (63) |
| NL | 3+ | 23-15 | 60.5% | +0.47 | +1.4 | 18 / 8 | +5.88 (38) |
| NL | 5+ | 6-7 | 46.2% | +0.85 | +1.2 | 6 / 2 | -1.54 (13) |

For reference, the locked 4-hour record on the same games (shipped model with the injury report, graded at the 4-hour line): gap 0+ 68-85 (-23.02u); gap 2+ 39-44 (-8.44u); gap 3+ 24-27 (-4.91u); gap 5+ 12-4 (+6.95u).

## Verdict (at the 2+ gap)

| Ratings | History (2025-26) | Tape (this season) | Verdict |
|---|---|---|---|
| N | fail | fail | **NO-GO** |
| NL | fail | fail | **NO-GO** |

## What it says

- **The line does move toward the ratings, in every sample.** Held-out 2025-26 at the 2+ gap: +0.34 points for the shipped ratings (t +3.8), +0.49 for the line-taught ones (t +5.0). This season's tape: +0.25 and +0.59. That part of the 2024-25 look was real.
- **It is too small to win with.** A third to a half of a point of line value is worth about one point of win rate. Against the open the picks went 352-340 (50.9%) and 316-302 (51.1%) on 2025-26, under the 52.4% break-even. The 54 to 56% of 2024-25 did not repeat: with ratings held 36 hours back that season still shows it, so it was the season, not look-ahead.
- Locking earlier is not a fix. The pick clock stays at 4 hours.

**Flagged for close monitoring**, tape, n as shown: NL at the 3+ gap 23-15 (+5.88u, n 38); N at the 5+ gap 14-6 (+6.74u, n 20). Neither cut was the registered one. On 2025-26 the same cuts were 184-197 (48.3%) and 94-84 (52.8%).
