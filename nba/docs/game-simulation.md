# Game Simulation page: version 1 rules (written before any result)

A menu page that plays one game 10,000 times and reports the score, each player's stat range and joint odds.

## How a simulated game runs

1. Environment. A margin and a total are drawn: normal around the chosen source (the players' own sum, the market line, or the Vault line), with the game model's margin spread (`MS.game.sd_margin`) and total spread (`MS.game.sd_total`, 17 points if it is not exported). Each team's target score is (total +/- margin) / 2. There is no separate bench term: the modeled rotation players carry the whole score.
2. Availability. Anyone Questionable, Doubtful or Probable plays with the probability the game model already uses (`MS.game.p_out`). Anyone Out or Inactive does not play.
3. Raw stat draws. Every player's points come from a normal with the prop model's mean (his minutes times his rate, with the Lab and what-if edits) and the prop model's variance for points; rebounds, assists and 3-pointers from a gamma-Poisson (negative binomial) with the model's variance. The draws are independent.
4. Tie to the game. Each team's raw points are scaled so the team sums to its target score. Teammate points therefore move against each other, and a fast game lifts everyone. Assists and 3-pointers scale with their team's score ratio at exponent 1; rebounds scale with the game total ratio at exponent 0.5. These exponents are fixed here, not fit.
5. Calibration pilot (added during the build, before any real-game result): scaling to the team score nudges high-variance players down and low-variance players up, and a normal cut at zero thins small scorers. A 3,000-game pilot measures each player's mean and spread and corrects the raw points centre (within 0.8x to 1.25x) and spread (within 0.7x to 1.5x) before the 10,000-game run. Rebounds, assists and 3-pointers need no pilot.
6. Minutes are scaled to 240 per team when the projected sum is off by more than 3%, and the page says so. **Revised 2026-10-07, before any
   result:** a player with no injury tag now plays with the measured chance for his projected minutes (`data/dress_table.json`, fit on 2024-25,
   checked on 2025-26: about 99% at 30+ minutes, 87% at 15-20, 33% to 44% under 10), because the model's minutes are for players who dress and
   the candidate list holds about 1.3 players per team who will not. The uniform 240 / sum scaling stays only as a safety net (it cut every
   starter about 9% once the team-minutes target moved from 251.6 to 264.9).

## What version 1 is, and is not

A view, not a bet source. It never produces a Bet, Lean, Edge, Pick'em leg or shadow bet. The roster guard applies exactly as elsewhere: a held team's simulation is shown with the hold reason.

## Checks the page runs on itself (every render)

- Marginal check: each player's simulated mean and standard deviation of every stat against the analytic prop model. Pass if the mean is within 3% (or 0.3, whichever is larger) and the sd within 10%.
- Environment check: the simulated margin and total mean and sd against the source it was given. Pass if the means are within 0.3 and the sds within 5%.
- The page prints each check as it runs. A failing check is shown, not hidden.

## Test before it is allowed to feed anything (after opening night, 2026-10-20)

Pre-registered, to run once at least 150 regular-season games have settled:
1. Port the engine to Python (`build_game_simulation_test.py`) and simulate every settled game from the recorder's tip-time board and minutes.
2. Calibration: the share of actual game totals, margins and player stats inside the simulated 80% range. Pass if 80% +/- 4 points for totals and margins and 80% +/- 5 for player points, rebounds, assists.
3. Joint odds: for teammate pairs on the 2 pick'em combinations that passed (points with assists, assists with 3-pointers, over/over or under/under), the simulated both-hit rate against the observed rate, game-clustered bootstrap, GO at 2 SE, the same bar as pairs.
4. Only if both pass may a pair price use the simulation. Until then it stays a view.

Record the outcome in `docs/game-simulation-results.md`, NO-GO included.

## Known limit at build time

Scorers projected under about 3 points are flagged Off by the marginal check: the prop model's normal for points puts mass below zero there, which a non-negative integer draw cannot match. The page shows the flag.
