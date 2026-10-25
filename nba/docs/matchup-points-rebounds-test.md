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
