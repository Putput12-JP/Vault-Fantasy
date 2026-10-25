# Early-season minutes: blend a team's first three games into the projection

Written 2026-10-25, before the test was scored and before the runner existed. The rules are the verdict. Every result is reported, pass or fail.
Nothing here changes what the page prices or bets: a pass earns a shadow-tracked candidate and its own pull request.

## Why

Prop projections are minutes times a per-minute rate (plus the usage cascade): `mu = pm x rate`, in `build_prop_model_v2.walk` and live in `pricing.py` `game_minutes`.
Re-scoring v2 with each player's true minutes removes 28.5% of the squared error on points, 25.5% on rebounds, 14.5% on assists and 12.3% on 3-pointers (`docs/v3-plan.md`).
Minutes are the largest fixable error, and in the first weeks of a season the minutes model is leaning on last season. The idea: after a team's first three games,
how many minutes each player really played is strong evidence of the new rotation. Does leaning on those three games, beyond what the minutes model already carries, predict better?

Interpretation of the request, stated so it can be corrected: "the first 2/3 games for each team and the time players played" is read as **each team's first three games of the season and the minutes each player played in them**;
"what was used when first grading them" is read as the **minutes and stat projections the walk-forward prop model made for those later games** (`pm` and `mu`). **N = 3 only**; N = 2 is not scored this round.

## Definitions (fixed now)

- **Data.** `build_prop_model_v2.walk`, the same walk-forward records the prop model was graded on (seasons 2022 to 2026; `FIT` = 2025, the 2024-25 season; `TEST` = 2026, the 2025-26 season). Each record has the projected minutes `pm`, the actual minutes `min`, the projected `mu` and the actual result `y` for pts, reb, ast, 3pm.
  Players who played (`min` > 0) only, as in `docs/minutes-model.md`.
- **Team game number** k = the order of the team's games in that season by game id. **Early window E** = team games 4 to 10. **Context window** = team games 11 to 20 (reported, no verdict).
- **First-three average f** = the mean of a player's actual minutes in his team's games 1 to 3 of that season **for games in which he played, for that team**. He needs **at least 2 of the 3**; otherwise his projection is left as it was (counted as "not blended").
- **Blend.** `pm_new = pm + w x (f - pm)`, one scalar w in [0, 1].
- **w is fitted once, on the FIT season's window E only:** `w = sum((min - pm)(f - pm)) / sum((f - pm)^2)`, clipped to [0, 1], then **frozen** and applied to the TEST season. It is never refitted on test data.
- **Prop projection under the blend.** `mu_new = mu x pm_new / pm` (rows with pm > 0). This holds the per-minute rate and the cascade fixed and moves only minutes, so it isolates the minutes effect. It is an approximation: the cascade term is not rescaled separately.

## Tests on the TEST season, window E (everything else is context)

**Primary, minutes.** MAE of minutes, `pm` against `pm_new`, over the blended rows, paired by player-game. Game is the unit; bootstrap over games, 2,000 draws, seed 7; t = mean paired gain / the standard deviation of the bootstrap means.

**Primary, props.** For each of pts, reb, ast, 3pm: per-row gain d = `(|y - mu| - |y - mu_new|) / MAE_old` where MAE_old is that stat's MAE under `mu` on the same rows (so each stat counts equally). Pool the four stats, game-clustered bootstrap as above.

**PASS (shadow-track the blend, early-season only)** needs all of:
1. Minutes MAE lower under the blend, game-clustered t >= 2.5.
2. Props pooled gain > 0, t >= 2.5.
3. Each of the four stats' MAE no worse under the blend (a stat that gets worse fails the test).
4. Same sign for the minutes gain in both halves of the window (team games 4 to 7, and 8 to 10).
5. The fitted w is strictly between 0 and 1 (a w that hits a bound means the blend is the wrong shape, and is reported as such).

**FAIL / no effect:** anything else. A minutes gain with no prop gain is reported as exactly that.

**Not scored this round:** N = 2, other windows or weights, a weight by position or role, a ratio blend, the 2022 to 2024 seasons as extra tests, a blend with the rest of the season (it is early-season only by construction).

## Context, reported with no verdict

- w fitted on FIT, and the same MAE comparison in FIT window E (in-sample, for the size of the effect only).
- The same comparison on TEST for team games 11 to 20, with the same w. If the gain survives there, it says the minutes model under-weights recent games all year, not only early.
- Counts: rows blended, rows not blended (fewer than 2 of 3 games), and players per team.
- Lines: the 2025-26 priced lines in window E number only a few hundred (`docs/prop-calibration-tests.md`), too few for a price-level test; their count is reported, not scored.

## Forward check, not part of the verdict

If this passes, the confirmation is the 2026-27 season's own window E (team games 4 to 10, ending about 2026-11-17), scored the same way from the lean log's first-look minutes and the box scores. It is registered in a separate follow-up before it is read.

## Shadow field and forward rule (added 2026-10-25, after the historical result, before any shadow row exists)

The historical run passed (`early-minutes-blend-results.md`), so the blend is logged live as a **shadow, never priced**:
- `build_model_state.py` records each player's minutes in his team's first three games of the season (`live.first3`) and each team's games played (`live.team_gn`), and carries the frozen w (`minutes.early_blend`).
- `pricing.py` `game_minutes_blend` returns the blended minutes for team games 4 to 10 for players with 2 of the 3 games with that team; empty otherwise.
- `ledger.minutes_log` stores it as the sixth value of the Minutes record row (after v2, recent average, v3, starters flag, GBM); `minutes_record` scores it each day beside v2 on the same players (`blend` block).
- Priced output is unchanged: `check_pricing_regression.py` is identical on the example board, v2 minutes, and both v3 shadows against main.

**Forward rule, fixed now.** Players who played in games logged with a blend value; last pre-tip value for each, minutes MAE of the blend against v2 on the same players, game as the unit, paired bootstrap (2,000 draws, seed 7).
Read **once, on or after 2026-11-18**, when every team has passed game 10. Needs at least **60 games and 800 player-games**. **Confirmed** if the blend's MAE is lower with t >= 2.5; **not confirmed** otherwise.
The shadow starts at the first daily state job after this merges, so it covers each team's games from about number 6 on, not the whole window. A price-level companion (the blend's effect on the lean's probability against the line) is registered separately before it is read.

## Reading rules

Nothing under 100 rows is quoted as a rate. Any improving cell is flagged for close monitoring with its sample size. Sharp money is not an input. This question has not been run before; the 2025-26 walk has been used many times for other questions
(`docs/experiment-log.md` section 1), so a row is added there for this look.
