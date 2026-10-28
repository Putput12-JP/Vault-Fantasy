# Matchup test for steals, blocks and turnovers (Stage 1, registered before any index is built)

Written 2026-10-26. Same design as the tests that passed (`matchup-volume-test.md`, `matchup-points-rebounds-test.md`), with one addition made for these stats: a **pace control**. Every result is reported, pass or fail. Nothing here changes what the page prices or bets.

## What is different about these stats (read this first)

- **They are the "extra" markets.** Steals, blocks and turnovers are projected as minutes times a shrunk per-minute rate with **no opponent, pace, home or back-to-back term** (`build_prop_model_extra.py`: "no usage cascade for these stats"; `docs/prop-model-extra.md`). They are shown on the page only, never logged as bets, never in the simulations, and Kalshi lists none of them.
  So a matchup index here could simply be standing in for pace, which the baseline lacks. The test is therefore **incremental over a pace index**, not over the bare projection.
- **Live use is a separate question.** The extras do not pass through `v2_terms`, the ledger or the lean log, so a pass would first need its own wiring (page and Python) and its own forward record (nothing records extra-stat projections against results today). **Nothing is built live from this test**; a pass earns a registered wiring and forward-record step.
- **Value is lower than for the priced stats**, and that is on the record: these markets are display-only. They are registered because the owner asked for the rest of the counting stats.

## Lessons carried over (as rules)

Real teams only, the runner **asserts every league-mean table is over exactly 30 teams**; opponent-only (team-level) indices from the team box scores; point-in-time (data from days before the game; the previous full season blended in until a team has 15 games); slope fitted on 2024-25 and **frozen**, scored on 2025-26 with a random-defense control and both halves positive; the effect is `projection x clip(1 + beta x index, 0.7, 1.3)`.

## Indices (fixed now), each a team's rate per 48 against the league mean, as a fraction

For the **opponent of the player's team**, from `player_box_<season>.csv` summed per team per game (minutes = sum of players / 5):

- **S_tov (steals):** turnovers the opponent's offense commits per 48. A sloppy offense gives more steals.
- **B_2pa (blocks):** two-point attempts the opponent's offense takes per 48 (field-goal attempts minus three-point attempts), the shots blocks come from.
- **T_forced (turnovers):** turnovers the opponent's defense forces per 48 (the turnovers its opponents commit in its games), which is what a player's own turnovers depend on.
- **Pace (the control index for all three):** the opponent's possessions per 48 in its games, `FGA + 0.44 x FTA + TOV - OREB` summed over both teams and halved, against the league.

## Data and test

Baseline projections `mu` for stl, blk, tov from the extra model's walk (`build_prop_model.walk` with its stat set replaced, as `build_prop_model_extra.py` does: `casc` empty, `team_min` from `prop_model.json`, injury report, **records for 2024-25 and 2025-26**). Players who played; game as the unit; bootstrap 2,000 draws, seed 7; t = mean / sd of the bootstrap means.

**Fit (2024-25, frozen):** `miss = y - mu`; least squares through the origin on two regressors, `b_pace x mu x Pace + b_m x mu x matchup`, fitted jointly. **Test (2025-26), per stat, each judged alone:**

1. **Fitted `b_m` on 2024-25 is positive.**
2. **Incremental gain:** MAE of `mu` scaled by pace and matchup together is lower than MAE of `mu` scaled by pace alone, **t >= 2.5**.
3. **Control:** replace the matchup index with a random other defense's (seed 7) and keep pace: its gain over pace-only does **not** reach t >= 2.5.
4. **Both halves of 2025-26 positive** for the incremental gain (by game id).
5. **`b_m` re-estimated jointly on 2025-26 alone is positive with t >= 2.5.**
6. **The league mean is over exactly 30 teams** in every table (a failed assertion voids the run).

**PASS** needs all six. A stat that passes only without the pace control (matchup alone beats the bare projection but not pace-only) is reported as **FAIL: the matchup is pace**.

**Context, no verdict:** pace alone against the bare projection for each stat (does a pace term belong in the extras model at all); matchup alone against the bare projection; gain by index fifth; the Poisson log-likelihood of each variant; the correlation between the matchup index and the pace index.

## Not scored

Other steal and block indices (live-ball turnovers, rim attempts, opponent starters), per-position slopes, player-specific mixes, a different prior weight, refitting on 2025-26, any price or ROI measure (there is no price history for these markets), and the other extra stats (field goals, free throws, 3PA, offensive and defensive rebounds, fouls).

## If a stat passes

Registered before it is built: wiring through the extras' own path in Python and the page with a frozen slope and a kill switch, a parity check, and a **new forward record** that stores the extra-stat projection against the box score each night (there is none today). Until that record exists, a pass stays a finding and the page does not change.
