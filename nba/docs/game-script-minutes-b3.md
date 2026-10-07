# Game Simulation v2, step B3: the bench-floor fix, frozen before the 2026-27 season (pre-registered)

Written and committed before the freeze is fitted and before any 2026-27 game exists. Step B2 (docs/game-script-minutes-b2.md,
results in docs/game-script-minutes-b2-results.md) was NO-GO by one togetherness check, bench with bench, and said why it
probably fell short: bench minutes sit close to zero, so clamping them at zero cuts the simulated variation that carries the
correlation. B3 fixes that and then waits for a season nobody has looked at.

## What changes from B2

The model is B2's M4 unchanged (margin terms, overtime, a starter and a bench team shock, independent noise). One step is
added to the fitting, never to the data the test sees: **clamp calibration.** After M4's constants are fitted, the two shock
variances and the starter-with-bench correlation are adjusted until the simulated within-team cross-products of minute
residuals (draws clamped to 0 and 48 as in play) equal the observed ones on the fit data. Procedure, fixed now:

1. Take every third team-game of the fit data in date order (a fixed subsample), 40 simulated draws per team-game.
2. For each pair type (starters with starters, bench with bench, starters with bench), compute the average cross-product of
   (draw minus the draws' mean) for simulated pairs, and of (actual minus the draws' mean) for observed pairs, both around the
   same predictive mean.
3. Scale each shock variance by observed over simulated cross-product (starters, then bench), and move the correlation by
   (observed minus simulated starters-with-bench cross-product) divided by the product of the two shock standard deviations.
   Clamp the correlation to [-0.9, 0], keep variances at or above zero. Repeat four times. Keep the last values.
4. Recompute each role's noise standard deviation as sqrt(max(0.25, role residual variance minus the new shock variance)).

## Freeze (before the first 2026-27 regular-season tip, 2026-10-20)

`build_game_script_b3.py --freeze` fits M4 and the clamp calibration on 2022-23 through 2025-26 (keys 2023 to 2026, warm-up
2021-22) and writes `data/game_script_frozen.json`: every constant of the model and the fit data's size and date range. The
file is committed to main before the first 2026-27 tip. The test mode refuses to run unless `--check` passes: the file is
committed unchanged and its last commit is before that tip.

## Development check (informational, run once before the freeze, not gating)

To see whether the calibration does what it is meant to, `--selfcheck` fits on 2022-23 and 2023-24, calibrates, and scores
2024-25 exactly as B2 did. That season was already used to find the bench miss, so this is a sanity check, not a test. Its
result is recorded in docs/game-script-minutes-b3-results.md and nothing in the freeze or the pass rules depends on it.

## Test (the pass rules are B2's, fixed)

Holdout: 2026-27 regular season (no play-in or playoffs), scored once **200 settled regular-season team-games**... counted as
games: when 200 games have settled. Minutes come from `raw/hoopr/player_box_2027.csv` (the daily job's fetch of the box
scores), the base and starter flag from the same walk-forward state as the fit, E from the game model's walk-forward
expected margin. 200 simulated draws per team-game, fixed seed.

All four hold, as in B2:

1. Starters: central-80% coverage 76% to 84%; mean rank of the actual minutes 0.50 +/- 0.02; coverage error no more than 1
   point worse than B0's.
2. Togetherness: the model-implied residual correlation for starters with starters, bench with bench and starters with bench
   each inside the observed game-clustered 95% interval, and the starters-with-starters interval excludes zero.
3. M4's mean minutes within 0.05 minutes MAE of M1's.
4. Overtime share of simulated team-games within 1.5 points of the observed share. (At 200 games the observed share has a
   standard error near 1.5 points, so this rule is judged against the interval too: within 1.5 points OR inside the observed
   share's 95% interval.)

**GO** if all four. **NO-GO** if any fails. There is no second look: this model is frozen, and a failed holdout means a new
pre-registered model on the next season, not a retune. Report every number with B0 (independent draw) beside it.

## What GO unlocks

The Game Simulation page draws each team's minutes from the frozen model (rescaled to 240 as now), which flows into points,
rebounds, assists and threes through the existing per-minute rates. It does not make anything a Bet, Lean or Edge. NO-GO
leaves the simulation as built.

## What it does not test

Quarter-level timing, foul trouble and injuries inside a game; the teams' shared margin inside one game; stats given
minutes; the 240-minute rescale.
