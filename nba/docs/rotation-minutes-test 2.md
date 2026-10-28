# Rotation-aware minutes: who is in the rotation, with injuries and blowouts

Written 2026-10-25, before any model was fitted or scored. The rules are the verdict; every result is reported, pass or fail.
Nothing here changes what the page prices or bets. A pass earns a shadow-tracked candidate and its own pull request.

## The problem

Today every player with minutes state on the team in the last 30 days who is not ruled out gets minutes, and the pool is rescaled to a team total (`pricing.py` `game_minutes`;
`build_prop_model_v2.walk`). About 1.3 players per team do not dress (`docs/leakage-audit-2026-10-06.md`, addendum 13), and many more dress but play garbage time. They take minutes that belong to the
rotation. The only rotation rule is a fixed one (10 or more average minutes in the last 21 days) used for injury redistribution. Blowouts enter as one linear term on the pre-game spread
(starter -0.107 min and bench -0.024 min per point beyond 6), but a real blowout changes **who plays**, not just how long.

## Definitions (fixed now)

- **Pool and labels.** The as-of candidate pool of the v2 walk (everyone with minutes state on the team in the last 30 days and not Out on the pre-tip report; 2022-23 and 2023-24 use "who actually sat"
  because no reports exist). Per candidate: actual minutes (0 if he did not dress). **Rotation = 12 or more minutes.** The raw minutes are kept so a different cut-off can be read later without relabelling; no other cut-off is scored.
- **Game state** = the final absolute margin: **close** (under 10), **middle** (10 to 19), **blowout** (20 or more). Overtime is not a separate state.
- **Features, all known before tip:** EWMA minutes `m`, starter rate `st`, games on the team `n` (capped 30), rank in the pool by `m`, indicator rank over 8, the last-3 mean minus `m`, **team games since he last played (0 to 10)**,
  days since his last game (capped 30), minutes vacated by Out players at his position and at other positions (the v2 `vs`, `vo`), the number of rotation players Out, back-to-back, home. No outcome information of the game itself.
- **Per game state s, three small models**, fitted on that state's games: (1) logistic P(plays), (2) logistic P(rotation | plays), (3) OLS minutes given rotation, plus the mean minutes of players who play without reaching the rotation. Ridge 1.0, Newton iterations fixed at 12. Nothing is tuned.
- **State probabilities** from the pre-game expected margin `e` (the game model's walk-forward margin, `build_minutes_model.expected_margins`): margin ~ Normal(e, 13.2), so pi_close, pi_middle, pi_blowout are the probabilities of each bucket.
- **Candidate C (the mixture):** `E[min | plays]` = sum over s of `pi_s x E_s[min | plays]`, with `E_s[min | plays] = P_s(rot | plays) x mu_s + (1 - P_s(rot | plays)) x g_s`. The unconditional expectation `P(plays) x E[min | plays]` (with `P(plays)` likewise mixed) is rescaled so the pool sums to the mean actual team total of the fit seasons; the conditional minutes are that rescaled value divided by `P(plays)`, capped at 48.
- **Control B (not a candidate):** one set of models over all games with the pre-game blowout probability and its interactions with rank and starter as features, no state split. Reported to show what the mixture adds.
- **Baseline A:** the minutes the walk projected (`pm`), as first graded.
- **Split.** Fit on the walk's 2022-23, 2023-24 and 2024-25 (`P(plays)` only on 2024-25, the first season with injury reports, because the earlier two use "who actually sat" and would teach that rotation players always play). **Test: 2025-26.** Frozen before it is read.

## Tests on 2025-26 (players who played, as in every earlier minutes test)

Statistic: paired per player-game gain `|min - pm| - |min - C|`, game as the unit, bootstrap 2,000 draws, seed 7, t = mean / sd of the bootstrap means.

**Primary.** Minutes MAE, C against A, whole season. **Required cuts:** (a) games with at least one rotation player Out, (b) pre-game |margin| over 8, (c) players ranked 9 to 12 in the pool by `m`, (d) starters in games that finish 20 or more apart, (e) each team's first 15 games.
**Props.** The approximation used by the blend test: `mu_new = mu x C / pm`, pts / reb / ast / 3pm, each stat's error as a share of its own MAE, pooled.
**Calibration.** P(rotation | plays) from C in five bands (under 20, 20 to 40, 40 to 60, 60 to 80, 80 and over); reported with n, and a band with 100 or more players must be within 4 points.

**PASS** needs all of:
1. Whole-season minutes MAE lower, t >= 2.5.
2. Gain positive in all five cuts, with t >= 2.5 in cut (a) and in cut (c); no cut with t <= -2.5.
3. Props pooled gain > 0, t >= 2.5, and no stat's MAE worse.
4. Calibration within 4 points in every band with 100 or more players.

Anything else is FAIL, and a minutes gain without a prop gain is reported as exactly that. **Context, no verdict:** B against A and C against B (what the mixture adds); the state-conditional accuracy of C (given the true state, MAE against the box score), which is what a simulation that draws the game state can use; the share of pool players whose P(plays) is under 0.5.

## Simulation (the "test both")

This round builds and scores the state-conditional minutes; it does **not** wire them into the Game Simulation. The frozen B3 model (`data/game_script_frozen.json`) is awaiting its 2026-27 holdout on 2026-11-16 and is not touched, so
the two efforts cannot double count. Whether the simulation should draw from the state-conditional models is decided after that read, with this round's state-conditional accuracy beside B3's.

## Not scored

Other rotation cut-offs, other state boundaries or a continuous margin, per-player blowout sensitivity, coach effects, a gradient-boosted version, a pooled refit including the test season, and 2022 as a scored season.

## Forward step if it passes

Shadow-field the minutes next to v2 and the blend (logged in the Minutes record, never priced), with its own pre-registered forward read. The live feature state (team games since last played, last-3 minutes, rank) needs the daily state job to export it; that is the build step, not part of this round.
