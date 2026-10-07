# Game Simulation v2, step B: minutes tied to the game's score (pre-registered test)

Written and committed before the test was run.

## The question

A blowout takes minutes from starters and gives them to the bench. The minutes model (docs/minutes-model.md) already lowers a
starter's expected minutes when the game is expected to be lopsided, but the simulation draws each player's minutes
independently of the game it is simulating. In real games the minutes of a team's starters move together with the final
margin, which is a dependence the independent draw cannot produce. Does a minutes draw that is tied to the simulated margin
reproduce the real spread and the real togetherness of starters' minutes better than independent draws?

## Data and split

`raw/hoopr/player_box_*.csv` (minutes, starter flag, both teams' scores) and the game model's walk-forward pre-game home
margin (`build_minutes_model.expected_margins`, no injury information, no leakage). Rows are players who played, with the
recency-weighted minutes base the minutes model uses (`build_minutes_model.State`, alpha 0.20 fixed, not tuned here).
Starter = the player's own running starter share is at least one half, as in the minutes model.

- Warm-up: 2021-22 (keys 2022). Fit: 2022-23, 2023-24, 2024-25 (keys 2023, 2024, 2025). **Holdout: 2025-26 (key 2026).**
- Regular season, play-in and playoffs as `nba_common.games` returns them; the play-in and playoffs are kept because
  blowouts and minutes there follow the same rules, and flagged in the results table.
- Nothing on the holdout is looked at until the coefficients are frozen from the fit seasons.

## Models of a player's minutes (y), per role (starter / bench)

All models start from the base b (recency-weighted minutes). Role means separately for starters and bench.

- **M0:** y = b + role constant.
- **M1 (what the minutes model does):** M0 plus a term in the pre-game expected margin: max(0, |E| - 6) per role.
- **M2 (hindsight, an upper bound):** M0 plus, per role, the realized margin of the player's team m (positive = the team
  won): max(0, m - 10), max(0, -m - 10), max(0, m - 20), max(0, -m - 20). Eight coefficients plus two constants.
- **M3 (the simulation's draw):** the M2 coefficients applied to a simulated margin m ~ the team-side margin whose mean is the
  pre-game expected margin E and whose spread is the standard deviation of (realized margin - E) on the fit seasons, then
  independent noise per player with the standard deviation of the M2 residuals for that role. Minutes are clamped to 0-48.
  No rescale to 240 is applied in this test.
- **B0 (the comparison draw):** M1's mean with independent normal noise, the standard deviation of M1's residuals per role.
  This is how the current simulation treats minutes: no link to the margin.

Coefficients are fitted by ridge least squares (ridge 1.0, the minutes model's routine) on the fit seasons and frozen.

## Pass rules (all on the 2025-26 holdout)

1. **Coverage (starters).** The central 80% interval of M3's predictive distribution (200 simulated draws per player-game,
   fixed seed) contains the actual minutes 80% of the time within 4 points (76% to 84%), **and** the mean of the
   predictive-distribution rank of the actual minutes is within 0.02 of one half, **and** M3's coverage error is not more
   than 1 point worse than B0's.
2. **Togetherness (the point of the step).** Among a team's starters in the same game, the average product of minute
   residuals e = y - (predictive mean given the expected margin) over pairs, divided by the average e squared, is the
   within-team starter correlation. Observed (rho_obs) with a game-clustered 95% interval; model-implied (rho_sim)
   from M3's simulation (20 simulated games per holdout team-game). **Pass: rho_sim lies inside rho_obs's interval and
   rho_obs's interval excludes zero** (so there is a dependence to reproduce). B0 implies about zero by construction.
3. **No harm to the mean.** M3's mean minutes (averaged over its margin draws) have an MAE within 0.05 minutes of M1's.

**GO** if 1, 2 and 3 all pass. **NO-GO** otherwise. Report every number either way.

## What GO unlocks

The Game Simulation page draws each team's minutes conditional on the simulated margin with the frozen coefficients and
noise, and rescales the team's minutes to 240 as it does now. It then flows into points, rebounds, assists and threes
through the existing per-minute rates. A GO changes the simulation's joint draws only; it does not make anything a Bet,
Lean or Edge. NO-GO leaves the simulation as built.

## Informational (does not gate)

- All coefficients, residual spreads, and MAE of M0, M1, M2, M3 and B0.
- The same togetherness statistic for starters with bench, and bench with bench.
- Minutes and over rates by realized |margin| bucket (0-7, 7-14, 14-20, 20+): average starter minutes, and for the
  sportsbook legs in `raw/tables/props_espn.csv` the over hit rate minus the no-vig price, by bucket (the public claim is
  a drop of about 6 points in blowouts of 20 or more; this checks it against our own data).
- Holdout results split by regular season against play-in and playoffs.

## What it does not test

- A quarter-by-quarter game script (when in the game the starters sit); this uses the final margin only, because the data
  has final box scores and not minutes by quarter. Quarter-level structure is a later step.
- The 240-minute rescale and the bench-gets-starters'-minutes accounting; only each player's own minutes are scored.
- Stats given minutes (that is the existing prop model's job); only minutes are scored here.
