# Game Simulation v2, step B2: overtime and a shared team minutes shock, results

Rules: docs/game-script-minutes-b2.md (committed before the test). Verdict: **NO-GO**.

- Fit 2022-23 and 2023-24: 55,097 player-games. Test 2024-25: 27,833. Team-games in overtime on the test season: 5.0%.

| Check | Rule | M4 | M3 (margin only) | B0 (independent) | Pass |
|---|---|---|---|---|---|
| Starters: 80% coverage | 76% to 84% | 82.9% | 82.8% | 82.6% | yes |
| Starters: mean rank of actual | 0.50 +/- 0.02 | 0.512 | 0.516 | 0.509 | yes |
| Togetherness, starters with starters | model inside the observed 95% interval | model +0.218, observed +0.221 (+0.194 to +0.248) | +0.105 | +0.001 | yes |
| Togetherness, bench with bench | model inside the observed 95% interval | model +0.165, observed +0.214 (+0.174 to +0.255) | +0.005 | -0.000 | NO |
| Togetherness, starters with bench | model inside the observed 95% interval | model -0.048, observed -0.033 (-0.051 to -0.015) | -0.002 | +0.000 | yes |
| Mean minutes MAE vs M1 | within 0.05 min | M4 5.027 vs M1 5.009 | M3 5.036 | B0 5.037 | yes |
| Overtime share of team-games | within 1.5 points | simulated 5.3% vs observed 5.0% |  |  | yes |
| Starters with starters interval excludes zero | required | yes |  |  | NO (all three togetherness rows and this) |

## Fitted constants (fit seasons)

- Overtime probability by |expected margin| (under 3, 3 to 6, 6 to 10, 10+): 5.7%, 6.8%, 4.7%, 3.3%; two-overtime share of overtime games 12.3%; regulation margin spread 13.91.
- Team shock: starters sd 1.77 min, bench sd 2.87 min, correlation -0.46. Cross-products used: starters +3.14, bench +8.26, starters with bench -2.33.

| Role | const | winner > 10 | loser > 10 | winner > 20 | loser > 20 | per overtime period | noise sd |
|---|---|---|---|---|---|---|---|
| starter | +0.71 | -0.313 | -0.313 | +0.136 | +0.172 | +4.06 | 5.26 |
| bench | +0.23 | -0.102 | -0.026 | +0.181 | +0.166 | +1.13 | 6.47 |

Starter coverage by season type (M4): regular season 0.832, play-in and playoffs 0.790.

## Post-hoc notes (written after the verdict; they do not change it)

The verdict above is the pre-registered one: **NO-GO**, because one of the four togetherness checks missed: bench with bench, model +0.165 against an observed +0.214 with a 95% interval of +0.174 to +0.255, a miss of 0.009. Every other rule passed.

What B2 fixed, against step B's margin-only draw (M3) and today's independent draw (B0), on a season the model never saw:

- Starters with starters: model +0.218, observed +0.221 (interval +0.194 to +0.248). M3 gave +0.105 and B0 gave 0.
- Starters with bench: model -0.048, observed -0.033 (interval -0.051 to -0.015).
- Overtime share of team-games: simulated 5.3%, observed 5.0%.
- Coverage and mean-minutes checks held (starter 80% coverage 82.9%, mean rank 0.512, mean-minutes MAE within 0.02 of the pre-game model).

Why bench with bench probably falls short: the bench's shock (sd 2.9 minutes) is estimated from fit-season cross-products of +8.3, and bench minutes sit close to the zero floor, so clamping at 0 cuts the simulated variation that carries the correlation. The observed bench correlation was also higher on the test season (+0.214) than the fit seasons implied. These are explanations, not tests; no fix was tried on 2024-25.

What this means for use: the part that matters for player props (starters moving together, and starters against bench) is reproduced, and the miss is on the bench. The rule was all four, so the simulation stays as built until a fresh season confirms the same model. Options, none done:

1. Freeze M4 as fitted (on 2022-23 and 2023-24, or all through 2024-25) and score it on the 2026-27 regular season at the same 150-game look as step A2, so one check covers both. No constants change before then.
2. A B3 that handles the zero floor for the bench (for example drawing bench minutes from a distribution that cannot go below zero), pre-registered first and scored on 2026-27 as well.
