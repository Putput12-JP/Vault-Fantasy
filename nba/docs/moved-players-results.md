# Players on a new team: results

Generated 2026-10-02T13:28Z by `nba/scripts/build_moved_players_test.py`. Rules: [moved-players-test.md](moved-players-test.md) (committed before this ran). Tested on 2025-26; MAE in minutes, lower is better; bootstrap over games.

**Minutes rule: NO-GO**

| Player-games | n | games | v2 MAE | v2mv MAE | v2mv - v2 | SE | z |
|---|---|---|---|---|---|---|---|
| New-arrival team-games | 10,322 | 727 | 4.95 | 4.941 | -0.01 | 0.007 | -1.34 |
| All team-games | 27,829 | 1,321 | 4.934 | 4.904 | -0.03 | 0.005 | -5.99 |

Returning teammates in new-arrival games, projected minus actual: v2 -0.657 min, v2mv -0.734 min.
The moved players themselves under v2mv (v2 does not project their first game): 1,314 player-games, MAE 5.245, bias -0.526.
Team minutes target: v2 251.6, v2mv 253.6.

## Signals

| Signal | v2 | v2mv | Live after this test |
|---|---|---|---|
| pts | GO (NO) | WATCH (YES) | GO (NO) |
| 3pm | GO (NO) | GO (NO) | GO (NO) |

Signals follow the inputs: if the minutes rule ships, a GO signal that is not GO under v2mv moves to WATCH.

## Note added after the result (not part of the decision)

The overall improvement comes mostly from the re-tuned team minutes target (251.6 to 253.6), which changes every game,
not from the moved players: in the backtest a mover is left out of only his first game for a new team (his history
moves with him after that), and teams almost always dress enough returning players that the rescale barely stretches
anyone (median 10 projected players per team-game; only 19 of 2,642 team-games had 7 or fewer, where projections ran
3.1 minutes high on average and 12 hit 48). The 2026-27 opener is far more extreme than anything in the test: PHI has 7
projectable players and four teams have someone at 48 minutes.

## What shipped instead: the roster guard

Because counting moved players did not earn its place, live pricing keeps the v2 minutes rule and holds the cases the
backtest shows it cannot price (`pricing.roster_hold`, the page's `rosterHold`, same rule): a team the minutes model
projects with fewer than 8 players, or with anyone at 44+ minutes (2 to 4 minutes too high per player in both 2022-24
and 2025-26), and any player with no minutes history on his current team (priced from the Minutes Lab's estimate,
never scored by the backtest). Held props are priced and shown, but never a Bet / Lean, an Edges play, a pick'em leg
or a shadow bet. This changes no projection. On the 2026-27 opener it holds PHI, LAL, MIA, DET, BOS and POR, plus each
moved player and rookie, until they play a game for their team.
