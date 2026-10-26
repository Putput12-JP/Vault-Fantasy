# Matchup term for steals and turnovers: wiring and forward record (registered before anything is built)

Written 2026-10-26. Evidence: [matchup-stl-blk-tov-results.md](matchup-stl-blk-tov-results.md) (steals and turnovers PASS, blocks FAIL). Nothing is built live from that test alone; this registers what would be built and how it is confirmed.
Every result is reported. Nothing here changes what the page prices or bets until the build is merged, and the extras are never bets.

## What the extras are today (so the wiring is not guessed)

- Steals, blocks, turnovers (and the other extra markets) are priced **only in the page**: minutes x a per-player rate from `data/prop_model_extra.json`, no stacker, no opponent, pace or home term, blended 0.7 with a negative-binomial price (`EXTRA_BLEND`).
- **Python never projects them**: `pricing.price_board` skips every extra stat, so the recorder, the ledger, the lean log and the simulations have no extras projection and nothing records one against results.
- `v2Terms` returns a zero term for any stat without a stacker, which includes every extra, so the existing matchup term (`matchupTerm`) is zero for them by construction.

## What is built (scope fixed now)

**Steals and turnovers only.** Blocks failed Stage 1 and are not wired. The combo steals plus blocks (`sb`) inherits the steals part and nothing else.

**The term, in the form that passed.** Stage 1 judged the matchup **jointly with a pace index** against pace alone, so the wired form is the joint pair with the frozen 2024-25 slopes:
- Steals: `clip(1 - 0.0515 x Pace + 0.6818 x S_tov, 0.7, 1.3)`
- Turnovers: `clip(1 - 0.4652 x Pace + 0.7917 x T_forced, 0.7, 1.3)`

`S_tov`, `T_forced` and `Pace` are the opponent's team-level indices as the test built them (box scores, real teams, point in time, last season blended in until 15 games, league mean over exactly 30 teams). They are added to `data/team_allowance.json` by `build_team_allowance.py` with the same arithmetic as `test_matchup_stl_blk_tov.py`; the runner's own functions are imported, not copied.

**Page.** The matchup term applies to a stat that has `team_terms` in `data/matchup_terms.json` even without a stacker (steals and turnovers); it shows in the build panel as **Shot matchup** (renamed there for these stats if the label misleads: "Opponent matchup"). The kill switch is the same file and the same switch (`enabled`, or each stat's slopes set to 0).
**Python parity.** `pricing.py` gets the same arithmetic (`matchup_x` already handles `team_terms`); `check_matchup_js_parity.py` is extended to steals and turnovers and must agree to 1e-9.

## The forward record (new; the only way this is ever confirmed)

A new recorder source, `xstat`, written after each poll for games within 24 hours of tip, one row per player-game and stat (steals, turnovers):
`[minutes, mu_without_term, matchup_term]` where `mu_without_term` is minutes x the player's rate from `prop_model_extra.json` (as the page computes it) and the term is stored separately, so the read never needs the counterfactual rebuilt.
`ledger.settle` grades each row against the box score (`steals`, `turnovers`; players who did not play are void) and writes `xstats/<day>.json` on `nba-data`, with a count in `track.json`. Same first-look rule as every record: the last row before tip is the one scored.
Rows of games before the build merges do not exist and are not rebuilt.

## Forward read (fixed now)

Per stat (steals, turnovers), population: settled `xstat` rows with minutes above zero and a non-zero rate. gain = `|actual - mu_without_term| - |actual - (mu_without_term + term)|`; game is the unit; bootstrap 2,000 draws, seed 7; t = mean / sd of the bootstrap means.
Read once per stat when it has **500 rows from 25 nights**; **KEEP** if gain > 0 with t >= 1.65, else **DEMOTE** (the stat's slopes set to 0 through a pull request). **Early stop** at any monthly look: gain negative with t <= -2.5, demote at once.
Context, no verdict: gain by index fifth; the same gain over a pace-only variant (does the matchup still add beyond pace on live data); the term's size distribution.

## Not in scope

Blocks; pace as a term for blocks and for steals on its own (Stage 1 found pace alone helps both over the bare projection, t 3.43 and 4.36; a registered change to the extras model, not part of this); the other extra markets; any price or ROI measure (no price history exists for these markets); the Game Simulation (it does not use extras).

## Order of work

1. Add the three team-level indices to `team_allowance.json` and its builder, with a test that the new columns equal the test runner's tables on a fixed sample.
2. Python: `xstat` projection and the term; recorder source; settle; tests (settle end to end on a fake `nba-data` folder, as the game-pick tests do).
3. Page: the term for stacker-less stats; parity check; browser check.
4. One pull request with a before-and-after (steals and turnovers props change; every other stat identical), a kill switch note, and the scheduled read.
