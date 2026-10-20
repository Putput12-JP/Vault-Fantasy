# Minutes Lab: early-season minutes from preseason, and when the preseason term retires

Written 2026-10-20 before the decay backtest was run. Builds on `preseason-signals-test.md` (B1 passed: early-season
minutes MAE 3.42 -> 2.99 with first-half preseason minutes, z 4.3).

## What ships

1. `data/preseason_minutes.json`: per player, preseason games, first-half mpg, box mpg, starts, preseason team; the
   fitted early-season minutes model; the fitted decay (below). Built once from `raw/preseason` (preseason is over; it
   does not change after opening night).
2. `player_projections.json` gets `min0_pre` beside `min0` for eligible players, plus the evidence behind it (`pre`:
   games, 1H mpg, weight).
3. Minutes Lab toggle **Early-season minutes: Standard | With preseason**. Default Standard. `min0` is unchanged, so the
   live ledger (`pricing.py`), the Props page default and every existing number stay exactly as they are. Switching
   the toggle swaps `min0` for `min0_pre` on the page only, for that viewer.

Why not just replace `min0`: the ledger is pricing off it from opening night, and the experiment log's rule is that a
pricing input changes under a pre-registered rule, not mid-record. The minutes gain is established (B1); whether it
survives into prop edges is not (accuracy is not edge). The toggle lets people use it today; the switch of the default
is a decision for the 2026-27 holdout (below).

## Eligibility (fixed)

A player gets `min0_pre` if: 400+ minutes last regular season, 40+ preseason minutes (box), his current roster team
is the team he played preseason games for, and he is not listed Out. Everyone else keeps `min0`: rookies (draft-bucket
fit), under-400-minute players, players traded after the preseason, and players with fewer than 40 preseason minutes.

## The model

`early = b0 + b1 x last mpg + b2 x 1H preseason mpg`, fit on 2023-24 to 2025-26 (all three seasons; the held-out
checks were leave-one-season-out). A moved-player term (preseason team differs from last season's final team) is kept
only if it lowers leave-one-season-out MAE by 2+ paired SE; otherwise one pooled fit.

## The decay (how the preseason term fades as games arrive)

Today's Lab blends `start` with the player's in-season EWMA minutes: `min0 = (n x EWMA + K x start) / (n + K)` with
K = 4 after n games, so the start's weight is 4/(n+4). With the preseason model, `start` becomes the preseason-informed
value. Open questions, answered from data, not set by hand:

1. **K for the preseason-informed start.** Grid K in {2, 4, 8, 12, 16, 24}, chosen by game-1-to-30 MAE on 2023-24 and
   2024-25, scored on 2025-26 (and the reverse; both reported).
2. **When does the preseason term stop earning its place?** Predict each game's minutes (games played only) from
   information before the game, with `start` = last-season-only versus preseason-informed. Paired MAE difference by games
   played so far: 0, 1-2, 3-5, 6-10, 11-15, 16-25, 26-40, 41+, player-clustered bootstrap, 2,000 resamples.
3. **Retire rule (fixed now).** The preseason term retires at game **N_ret** = the first bin whose lower end is after the
   last bin with a paired gain of 0.05+ minutes at z >= 2, rounded up to the bin edge. After N_ret `min0_pre` equals the
   standard `min0` (the preseason weight is zeroed, not just small). Before N_ret the weight is the fitted K's
   `K/(n+K)` share.
4. **Early retire triggers, regardless of n:** the player's team changes (trade, waiver) or he returns from a 5+ game
   absence (his role may have reset). Both drop the preseason term at once. Out for the rest of the season: no change
   needed (min0 is 0).
5. **Sunset of the whole feature.** The toggle and `data/preseason_minutes.json` are removed after game 41 of the
   regular season for the league's slowest team, unless the holdout below says to promote it first. Next preseason a
   new file replaces it; the code stays.

## Promotion or removal (the holdout, read once)

Holdout: first 15 team games of 2026-27, veterans only, preseason model frozen as of this build. Read when 200
player-seasons have 10+ early games. Compare MAE of `min0` vs `min0_pre` against actual minutes per game played.

- **Promote** (make `min0_pre` the default and let `pricing.py` use it): MAE gain >= 0.25 min, z >= 2.
- **Keep as an option** if the gain is positive but under the bar.
- **Remove** (delete the toggle and the data) if the gain is 0 or negative at 200 player-seasons.

Prop edges are not part of this decision; they belong to the pre-registered test in `preseason-signals-test.md`
amendment 12.

## Amendments

2026-10-20, after the decay backtest ran (the retire rule itself is unchanged):

1. **Shape: linear fade, not a cliff.** The rule retires the term at game 11. Switching off abruptly changes a player's
   number by about 0.7 minutes at that game, so the shipped term fades linearly to zero from game 6 to game 11
   (weight 1 through game 5, then (11 - n) / 6). It still reaches exactly zero at N_ret as the rule requires. Backtested:
   MAE in games 6-10 is 4.63 (standard 4.73, untapered 4.59), so the taper gives up 0.04 minutes against the untapered
   curve in those games and removes the jump.
2. **K.** K = 2 won on every held-out season (the grid's lowest value; the grid ends there). The standard Lab blend is
   also better at K = 2 than at today's K = 4 (games 0-30 MAE 4.668 vs 4.731). That is a finding about the existing Lab,
   not applied here: it would change `min0`, which the ledger prices from.
3. **Moved-player term: not kept** (z 0.2), so one pooled fit serves everyone.
4. **Triggers as implemented.** Team change: the depth-chart team differs from the team he played preseason games for.
   Absence: any gap of 5 or more consecutive team games this season (regular season and playoffs), which also drops the
   term for the rest of the season.
5. **Active-13 interaction.** The preseason version re-ranks the top 13 by its own minutes, so a few ineligible players
   (7 of 517) shift because eligible players were promoted or demoted around them. Ineligible players otherwise keep
   their standard number.
6. **Game-day path.** The Lab shows game-day minutes (a separate server-built state) on game days, so the toggle also
   shifts that base by (`min0_pre` - `min0`) on the page for opted-in viewers only. The server state and the ledger do not
   use it. Side effect: a lower modeled total can trip the existing roster guard (WSH did), which then fills newcomers
   from the Lab's numbers; props on a held team are never a Bet, Lean or edge for that viewer.
7. **Rookies are not adjusted.** The preseason model was fit and tested on veterans only. Acuff's 18.5 first-half minutes
   do not move his draft-bucket projection. A rookie fit (about 90 rookies over three preseasons) is the natural next test.

## Results (decay backtest, `build_preseason_decay.py`)

741 veteran player-seasons (2023-24 to 2025-26), 45,375 player-games, each predicted from information before that game.
Standard = today's Lab blend (K = 4, last-season start). Preseason = K = 2, preseason-informed start.

| Games played so far | Rows | MAE standard | MAE preseason | Gain (min) | z |
|---|---|---|---|---|---|
| 0 (game 1) | 741 | 5.57 | 4.64 | +0.93 | 9.9 |
| 1-2 | 1,479 | 5.02 | 4.46 | +0.56 | 9.0 |
| 3-5 | 2,214 | 4.84 | 4.57 | +0.27 | 6.4 |
| 6-10 | 3,678 | 4.73 | 4.59 | +0.14 | 6.1 |
| 11-15 | 3,658 | 4.76 | 4.72 | +0.04 | 2.7 |
| 16-25 | 7,161 | 4.59 | 4.57 | +0.03 | 3.5 |
| 26-40 | 10,221 | 4.69 | 4.68 | +0.01 | 2.3 |
| 41+ | 16,223 | 4.80 | 4.80 | 0.00 | -0.2 |

**Retire rule: the last bin with a gain of 0.05+ minutes at z >= 2 is games 6-10, so the term retires at game 11.**
Against a standard blend that also uses K = 2 the gain is smaller after the first few games (0.31 at games 1-2, 0.09 at
3-5, 0.04 at 6-10, 0.00 at 11-15), so most of the value is the first five games and almost all of it is gone by ten.

### The schedule in plain terms

| Team games played | Weight on the preseason-informed number | What it does |
|---|---|---|
| 0 (season start) | 100% | Start is last-season minutes plus first-half preseason minutes |
| 1 to 5 | 100% of the shift, shrinking as his real minutes arrive (K = 2: 2/(n+2) of the start) | Real games take over quickly |
| 6 to 10 | fades 83% -> 17% | Linear fade to the standard number |
| 11 and later | 0% | `min0_pre` equals `min0` |
| Any time | 0% | Team change, or a gap of 5+ team games |
| Game 41 (slowest team) | feature removed | Toggle and `data/preseason_minutes.json` deleted unless promoted |
