# Matchup test for points and rebounds (Stage 1, registered before any index is built)

Written 2026-10-25. Same design as the 3PM and assist test that passed (`matchup-volume-test.md`, `matchup-volume-corrected-results.md`), applied to the next counting stats. Every result is reported, pass or fail. Nothing here changes what the page prices or bets.

## Lessons carried over (so they are rules, not hopes)

1. **Real teams only.** The play-by-play carries the All-Star game with invented teams; the first matchup run was invalid because they entered the league mean. The runner keeps only teams with 20 or more games and **asserts the league mean is over exactly 30 teams** (the run stops otherwise).
2. **Opponent-only indices.** The player-specific mix added nothing over the opponent's overall allowance (3PM volume t 3.56 against 3.59; assists 4.12 against 3.88), so the indices here are team-level and cheaper to build and check.
3. **Slope fitted on 2024-25, frozen, tested on 2025-26**, with a random-defense control, both halves positive, and a point-in-time index (data from days before the game, last season blended in until a team has 15 games; 2024-25 has no prior season, so its defenses count only from game 15).
4. The effect is `projection x (clip(1 + beta x index, 0.7, 1.3))`; the index is a fraction (0.10 = ten percent above the league).

## What the data has to add

The current shot table has attempts, zones and assist locations but **not whether a shot was made, nor rebounds**. A new reader (`read_events`, a new function; `build_diet_defense.read` and the page's file are not touched) will add, per regular-season shot with a coordinate: made or missed, the shot value (2 or 3), and for a miss the rebound that follows (offensive or defensive, the rebounder's team). Free throws are not in the table, so the points index covers **field-goal points**.

## Three indices (fixed now)

Each is a team's rate per 48 minutes (overtime adjusted, as the page does) against the league mean over the 30 real teams, minus one, point in time, for the **opponent of the player's team**.

- **P_vol (points, volume):** field-goal attempts the opponent defense allows.
- **P_eff (points, efficiency):** field-goal points the opponent defense allows per attempt allowed (shot value x made), against the league.
- **R_miss (rebounds):** misses per 48 in the opponent's games: the opponent's own misses plus the misses it forces on the other team (the pool of rebounds a game with this team offers). Rebounds are the team's pool, not a player's share of it, so v2's pace term and a player's own rate remain the base.

## Tests (each index judged alone)

Target: the miss of the walk's projection in that stat (`y - mu`, points for P_vol and P_eff, rebounds for R_miss), players who played, the walk's own `mu`. Fit and test as in `matchup-volume-test.md`: beta by least squares through the origin of the miss on `mu x index` over 2024-25 rows with an index, frozen, scored on 2025-26 with a game-clustered bootstrap (2,000 draws, seed 7).

**Per-index PASS** needs all of:
1. beta fitted on 2024-25 is positive.
2. Applying the frozen beta to 2025-26 lowers the stat MAE, t >= 2.5.
3. The control (a random other defense, seed 7) does not reach t >= 2.5; and beta re-estimated on 2025-26 alone is positive with t >= 2.5.
4. The gain is positive in both halves of 2025-26 (by game id).
5. The league mean in the run is over exactly 30 teams (a failed assertion voids the run).

Three tests against the same two seasons: each must reach t >= 2.5 alone; nothing is pooled and no index is chosen afterwards.

**Context, no verdict:** gain by index fifth (monotone or not); P_vol and P_eff together against P_vol alone (is efficiency separate information); the share of rows scored; the effect on the combos (PRA, PR, PA, RA) from the parts, as one line.

## Not scored

Steals, blocks, turnovers (registered separately once the events they need are extracted), free throws, player-specific mixes, per-zone betas, a different prior weight, refitting on 2025-26, and any price or ROI measure.

## If one passes

Same route as 3PM and assists: a frozen slope in `data/matchup_terms.json`, the same Python and page arithmetic with a parity check, a kill switch, the term logged on bet rows, and a forward read registered before any game. The Game Simulation and Props Simulation take it through `mu_for` automatically. Points feed PRA, PR and PA; rebounds feed PR and RA.

## Clarification made before any index was built (2026-10-25): data source

The three indices are **computed from the team box scores** (`raw/hoopr/player_box_<season>.csv`, summed per team per game: field-goal attempts and makes, points minus free throws made, minutes), not from a new play-by-play reader. Same quantities, exact, and no coordinates are needed.
Consequences, fixed now: (1) the All-Star game is not in the box-score game list, so the invented-team problem cannot occur, and the runner still asserts the league mean is over exactly 30 teams; (2) **2024-25 now has a full prior season (2023-24)**, so the fit season uses the same blend rule as 2025-26 (w = games / 15, last season's rate before that), instead of counting defenses only from game 15; (3) the "`read_events`" extraction named above is not built.
Per-48 rates use team minutes (the sum of player minutes over five), so overtime is handled. P_eff = blended field-goal points allowed divided by blended field-goal attempts allowed. R_miss = (the defense's own misses + the misses it forces on its opponent) per 48.
Steals, blocks and turnovers are also in the box score, so their registration (still separate, still later) will not need the play-by-play either.

## Rule for the live form of points, fixed before the joint context was computed (2026-10-26)

P_vol and P_eff are both about how many points a defense allows, so using both separately would count the same thing twice. The registered context (P_vol and P_eff together against P_vol alone) decides:
fit one least-squares slope for each on 2024-25 jointly (`miss = b1 x mu x P_vol + b2 x mu x P_eff`), freeze, and score on 2025-26 against P_vol alone, paired, game as the unit, same bootstrap.
**If the joint pair beats P_vol alone with t >= 2.0, the live points term uses the joint pair with those two slopes; otherwise it uses P_vol alone with its registered slope.** Rebounds use R_miss with its registered slope. No other form is considered.
