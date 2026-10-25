# Early-season minutes blend, round 2: results

Rules: [early-minutes-blend-round2.md](early-minutes-blend-round2.md), committed before the runner (`60d60739f`, runner `120b8f786`). Numbers: `nba/data/early_minutes_blend_round2.json`.
Run once on 2026-10-25 with w = 0.3939 frozen from round 1. Nothing here changes what the page prices or bets.

## Verdict: **MIXED** (one season passes, one fails on minutes)

| Season, team games 4 to 10 | Rows blended | Games | Minutes MAE old to new | Gain | Minutes t | Props pooled gain | Props t | No stat worse | Both halves | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022-23 | 1,819 | 114 | 4.906 to 4.845 | 0.061 min | **1.87** | 0.7% | 3.75 | yes | yes (+0.091, +0.019) | **FAIL** (minutes t under 2.5) |
| 2023-24 | 1,813 | 113 | 5.237 to 4.674 | 0.564 min | **6.99** | 2.0% | 5.78 | yes | yes (+0.820, +0.238) | **PASS** |
| 2025-26 (round 1, for reference) | 1,886 | 132 | 5.119 to 4.622 | 0.497 min | 7.25 | 1.9% | 5.97 | yes | yes | PASS |

By the rule, "round 2 holds" needed both seasons. It does not. **Round 1 stays a finding about 2025-26 and 2023-24, and 2022-23 shows a small gain that does not clear the bar.** No condition was relaxed after seeing this.

## What it does and does not say

- The direction is the same in all three seasons: the blend never made minutes or any of the four stats worse in the window (in 2022-23 every stat's MAE still fell, and props reach t 3.75). The size is not the same: about 0.5 minutes in two seasons, about 0.06 in the other.
- The bucket pattern repeats where the gain is large. 2023-24: gain 0.83 (games 4 to 6), 0.37 (7 to 10), 0.16 (11 to 15), then negative from game 16 on. 2022-23: 0.10 (4 to 6), 0.03 (7 to 10), negative from game 11. The blend only ever helps early, as in round 1.
- **Why the seasons differ is not tested here.** One plausible reading is that the gain scales with how much rotations change between seasons (more turnover, more to learn from three games); another is that 2022-23 is the first scored season after a single warm-up season, so the model's own starting state is different. Neither was checked, and this paragraph is a hypothesis, not a result.
- Caveat in the rules, restated: the minutes model was fitted on 2022-23 and 2023-24, so these two seasons flatter v2 a little. That makes the 2023-24 pass if anything conservative for the blend and the 2022-23 weakness not explained by it.

## Where this leaves the blend

The forward shadow (PR 244, read on or after 2026-11-18) is now the deciding evidence for the size of the effect in 2026-27. The honest summary is "positive in three of three seasons on props and in two of three on minutes at the registered bar; the size varies a lot by season". Nothing about pricing changes, and no edge over the market is claimed.
