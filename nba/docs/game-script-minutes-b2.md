# Game Simulation v2, step B2: overtime and a shared team minutes shock (pre-registered test)

Written and committed before the test was run. Step B (docs/game-script-minutes.md, results in
docs/game-script-minutes-results.md) ended NO-GO: tying minutes to the margin reproduced about half of how much a team's
starters' minutes move together. The post-hoc notes there named two missing game-level factors, overtime and a shared team
shock. B2 adds both and is scored on a season step B did not score.

## Data and split

Same data as step B: `raw/hoopr/player_box_*.csv`, the game model's walk-forward pre-game expected home margin
(`build_minutes_model.expected_margins`), the recency-weighted minutes base (alpha 0.20, `build_minutes_model.State`),
starter = running starter share at least one half.

- Warm-up 2021-22 (key 2022). **Fit: 2022-23 and 2023-24 (keys 2023, 2024). Test: 2024-25 (key 2025).**
- Step B scored 2025-26 and fitted on 2022-23 to 2024-25, so 2024-25 was in step B's fit but never scored on this question.
  The post-hoc work after step B looked at 2025-26 only, plus one descriptive count on the fit seasons (about 5% of
  team-games go to overtime). Disclosed here; nothing from 2024-25 outcomes informed this design.
- 2025-26 is not used anywhere in B2.

## The model (M4), frozen from the fit seasons

Per player: y = clamp(base + c_role(m, k) + u_role + noise, 0, 48), per role (starter, bench), where for the player's team:

- m = the team's final margin (positive = won), k = overtime periods (0, 1, 2).
- c_role(m, k) = const + a1 max(0, m - 10) + a2 max(0, -m - 10) + a3 max(0, m - 20) + a4 max(0, -m - 20) + d k,
  fitted by ridge least squares (ridge 1.0) on the fit seasons.
- (u_starter, u_bench) = a team-game shock, bivariate normal with mean 0. Its variances are the average cross-product of
  the fit seasons' residuals for two different starters (starters) and for two different bench players (bench) in the same
  team-game, residuals taken after c_role(m, k); its correlation is the starter-with-bench average cross-product divided by
  the product of the two standard deviations, clamped to [-0.9, 0]. A variance estimate below zero is set to zero.
- noise = independent, with standard deviation sqrt(max(0.25, residual variance of the role minus the role's shock variance)),
  so each player's overall spread is preserved.

Game-level draw for a simulated team-game, with E the pre-game expected margin of the team:

- Overtime: probability p(|E|) in four bins of |E| (under 3, 3 to 6, 6 to 10, 10 or more) = the fit seasons' share of
  team-games that went to overtime. If overtime: k = 1, or 2 with the fit seasons' share of two-overtime games among
  overtime games; the final margin is drawn from the fit seasons' overtime games (absolute margin resampled, sign random).
- No overtime: m ~ Normal(E, s), s the standard deviation of (final margin - E) in the fit seasons' regulation games.
- Overtime is detected from team minutes: round((sum of the team's minutes - 240) / 25), floored at zero.

Comparison models on the same test season: **M3** (step B's draw with its coefficients refit on 2023 and 2024) and **B0**
(independent noise around the pre-game mean, today's simulation).

## Pass rules (all on the 2024-25 test season; 200 simulated draws per team-game, fixed seed)

1. **Coverage (starters):** the central 80% interval of M4 contains the actual minutes 76% to 84% of the time; the mean
   rank of the actual minutes is 0.50 +/- 0.02; M4's coverage error is no more than 1 point worse than B0's.
2. **Togetherness (the point of the step):** within a team, the residual correlations for starters with starters, bench
   with bench and starters with bench (residual = actual minus the model's predictive mean given E; correlation = average
   cross-product over pairs divided by the geometric mean of the two roles' residual variances) must each have the
   model-implied value inside the observed game-clustered 95% interval, and the starters-with-starters interval must
   exclude zero.
3. **No harm to the mean:** M4's mean minutes within 0.05 minutes MAE of M1's (the pre-game blowout term of the minutes
   model).
4. **Overtime frequency:** the share of simulated team-games with overtime within 1.5 points of the test season's share.

**GO** if all four pass. **NO-GO** otherwise. Report every number either way, with M3 and B0 beside it.

## What GO unlocks

The Game Simulation page draws each team's minutes from M4 with the frozen constants (a page change, rescaled to 240 as now),
which flows into points, rebounds, assists and threes through the existing per-minute rates. It does not make anything a
Bet, Lean or Edge. NO-GO leaves the simulation as built, and the dependence the pairs test measured stays the only
thing coupling players.

## Informational (does not gate)

- All fitted constants (coefficients, shock variances and correlation, overtime rates, margin spread).
- Coverage and togetherness by season type (regular season against play-in and playoffs).
- Minutes by margin and by overtime on the test season against M4's simulated averages.

## What it does not test

- Quarter-by-quarter timing of the sit-down, foul trouble and injuries inside a game.
- The coupling of the two teams in one game (overtime and margin are drawn for each team on its own; the teams' shared
  margin is not enforced).
- Stats given minutes, and the 240-minute rescale.
