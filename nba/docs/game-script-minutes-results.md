# Game Simulation v2, step B: minutes tied to the game's score, results

Rules: docs/game-script-minutes.md (committed before the test). Verdict: **NO-GO**.

- Fit: 82,930 player-games (2022-23 to 2024-25). Holdout 2025-26: 28,254. Spread of (realized margin - expected margin): 14.48 points.

| Check | Rule | Result | Pass |
|---|---|---|---|
| Starters: central-80% coverage, M3 | 76% to 84% | 83.1% (B0, today's independent draw: 82.9%) | yes |
| Starters: mean rank of the actual minutes, M3 | 0.50 +/- 0.02 | 0.520 (B0 0.512) | NO |
| Starters' minute residuals move together | model inside the observed 95% interval, interval excludes 0 | observed +0.194 (+0.170 to +0.218), model +0.103, independent draw 0 | NO |
| Mean minutes, M3 vs M1 | within 0.05 min MAE | M3 5.025, M1 4.995 | yes |

MAE (minutes, all players): M0 base only 4.999; M1 pre-game blowout term 4.995; M2 realized margin (hindsight) 4.856; M3 simulated margin 5.025.

## Informational

- Residual correlation within a team, observed (game-clustered SE) against model-implied: starters with starters +0.194 (SE 0.012) vs +0.103; starters with bench -0.025 (0.007) vs +0.001; bench with bench +0.178 (0.016) vs +0.004.
- Starter coverage by season type: regular season 0.834, play-in and playoffs 0.792.

| Realized margin | Holdout starters (n) | Avg starter minutes | Avg bench minutes |
|---|---|---|---|
| 0-7 | 3,623 | 31.115 | 18.499 |
| 7-14 | 3,904 | 30.369 | 17.349 |
| 14-20 | 2,099 | 28.858 | 15.605 |
| 20+ | 2,836 | 26.562 | 15.785 |

| Season | Realized margin | Sportsbook legs | Over hit rate minus no-vig price |
|---|---|---|---|
| fit 2024-25 | 0-7 | 3,761 | -2.3 pts |
| fit 2024-25 | 7-14 | 3,758 | -2.1 pts |
| fit 2024-25 | 14-20 | 2,453 | -5.3 pts |
| fit 2024-25 | 20+ | 2,623 | -7.5 pts |
| holdout 2025-26 | 0-7 | 3,152 | +0.2 pts |
| holdout 2025-26 | 7-14 | 3,708 | +0.5 pts |
| holdout 2025-26 | 14-20 | 1,900 | -4.9 pts |
| holdout 2025-26 | 20+ | 2,398 | -6.7 pts |

## Coefficients (minutes added to the recency base; margin m = the player's team margin, positive = won)

| Role | const | winner beyond 10 | loser beyond 10 | winner beyond 20 | loser beyond 20 | noise sd |
|---|---|---|---|---|---|---|
| starter | +1.11 | -0.357 | -0.371 | +0.195 | +0.262 | 5.62 |
| bench | +0.44 | -0.125 | -0.048 | +0.204 | +0.166 | 7.09 |

## Post-hoc notes (written after the verdict; they do not change it)

The verdict above is the pre-registered one: **NO-GO**. Two rules failed: the mean rank of the actual minutes was 0.520 (the rule is 0.50 +/- 0.02, the draw runs slightly short of actual minutes), and the model reproduced about half of the observed togetherness of starters' minutes (+0.103 against an observed +0.194, interval +0.170 to +0.218). Coverage and the mean-minutes check passed. The fitted link itself is real: starters average 31.1 minutes in games decided by under 7 points and 26.6 minutes in games decided by 20 or more, and the coefficients have the expected signs (a starter loses about 0.36 minutes per point of margin beyond 10, on both the winning and the losing side).

Looked at afterwards, only to plan the next step:

1. **Overtime is a shared factor the margin link cannot see.** About 4% of team-games went to overtime. In those, starters played 4.25 minutes more than the margin model predicts (the other 96% average +0.02), and the starter-with-starter residual correlation in overtime games is +0.24. Margin alone cannot say a game ran long.
2. **Without overtime, a shared component remains.** Around the hindsight model (realized margin known), starters' residuals are still correlated at +0.075 in regulation games (+0.089 including overtime). Something else moves a team's rotation together (a pace or foul-trouble game, a short bench, an ejection), which independent noise cannot produce.
3. **Bench with bench is +0.178 observed against +0.004 modeled.** The bench moves together far more than the model allows, the same missing common factor seen from the other side (when starters sit, the whole bench plays).
4. **Blowouts show up in prices exactly as the public claim says.** The over hit rate minus the no-vig price was +0.2 and +0.5 points in games decided by under 14 in 2025-26 (-2.3 and -2.1 in 2024-25), and -4.9 to -7.5 points in games decided by 14 or more, in both seasons. That is the realized-margin effect; it is not an edge by itself, since the realized margin is not known before tip.

## Step B2 (to be pre-registered before it is run)

Add the two missing game-level factors to the draw: (a) overtime, drawn with the frequency and minutes effect measured on the fit seasons, and (b) a team-level shared minutes shock with the spread measured on the fit seasons. A fresh scoring season is needed: 2025-26 has now been looked at. Options: score on 2024-25 with a fit on 2022-23 and 2023-24, or wait for 2026-27 as in step A2.
