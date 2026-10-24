# Game-model challenger: a possession-efficiency rating model against the shipped Vault line

Written 2026-10-24, before the challenger was coded or scored. Runner: `nba/scripts/test_ratings_challenger.py`.
Results land in `nba/docs/game-model-challenger-results.md` only after this file is committed.

## Why

`samthemodelman.smmodel.workers.dev` publishes an NBA model whose method can be read off its public pages (fitted from 28 games in `docs/game-picks.md` context): points per 100
possessions scored and allowed per team plus pace, additive (`baseline + own offense + opponent defense`), ratings that move about 0.11 x each game's surprise (a moving
average of about 9 games), shrunk toward last season early, home court, and the published margin pulled partway toward the middle. On the 28 regular-season games played so far, with the
same DraftKings line and the same finals: our Vault line margin MAE 14.08, his 13.87, the market 12.79; winner picks 14-13 against 13-15; spread picks against that line 12-16
against 15-13. At n = 28 that is a tie in noise, so it settles nothing. This experiment asks the question on 2,641 games.

**Question.** Does a possession-efficiency moving-average rating model predict NBA margins better than the shipped model, alone or combined with it?

## What is held fixed

Same cut the shipped model uses: warm-up 2021-22 (label 2022); parameters fit on 2022-23 and 2023-24 (labels 2023, 2024) only; scored on 2024-25 and 2025-26 (labels 2025, 2026) with the
games and lines the shipped model is scored on (`build_game_model.run` records, DraftKings then ESPN BET closing and opening lines, the injury report as of 30 minutes before tip).
Nothing in any fit sees a test season. The shipped parameters and `data/game_model.json` are not touched by this experiment unless the ship rule below passes.

## The challenger (fixed now)

- **Possessions.** Per team-game from the box score: FGA - OREB + TOV + 0.44 x FTA. Game possessions = the mean of the two teams, scaled by 480 / total player minutes of both teams (overtime).
- **Ratings.** Offense O[t], defense D[t] (points allowed above average, so higher is worse) and pace P[t], each relative to the league. Per 100 possessions:
  expected points per 100 for team A = BASE + O[A] + D[B]. Expected pace = PACE0 + P[A] + P[B].
- **Update after each game.** surprise_A = actual points per 100 - expected. O[A] += K x surprise_A, D[B] += K x surprise_A, and the same for B. P[A] and P[B] each += KP x (actual pace - expected pace).
  BASE and PACE0 are the running league averages. Home court is learned online as the shipped model does (starts 2.0).
- **New season.** O, D and P are multiplied by CARRY.
- **Prediction.** Points = per-100 expected x expected pace / 100 for each side; margin = home - away + home court. No injury or rest term: this is what the public model has.
- **Tuning (tune seasons only).** Two coordinate sweeps from K 0.06, CARRY 0.6, KP 0.10, minimising tune-season margin MAE. Grids: K {0.02, 0.04, 0.06, 0.08, 0.11, 0.14, 0.18},
  CARRY {0.3, 0.45, 0.6, 0.75, 0.9}, KP {0.05, 0.10, 0.15}. A parameter that ends on a grid endpoint is reported.
- **Shrink.** After the sweep, least squares of actual margin on the challenger's raw margin over the tune seasons gives (a, b); the scored margin is a + b x raw. (The public model pulls
  its published margin toward the middle by about a third.)

## The four variants scored (fixed now; no others are scored this round)

| | Margin |
|---|---|
| S | the shipped model with the injury report at tip (`recs[...]['tip']`), the reference |
| A | challenger with shrink |
| B | A plus the shipped model's injury adjustment (its 'tip' margin minus its 'none' margin) |
| C | the mean of S and B |

## Metrics (test seasons, games that have a closing spread)

1. Margin MAE against the actual margin, by season and pooled.
2. Winner accuracy (the side the margin favours).
3. Against the closing spread: the information test already in `build_game_model.info_test` (actual margin on the line and on model minus line; g > 0 at t >= 2 would mean the model knows
   something the line does not), and ATS win rate at edge >= 0 and >= 3 against 52.4% break-even.
4. The market's own closing margin MAE, as the bar neither is expected to clear.

Differences between variants are `mean(|error_S| - |error_V|) / SE` across games: positive means V is closer.

## Verdicts (fixed now)

- **Matches** the shipped model: pooled margin-MAE t > -2 against S.
- **Better**: pooled margin-MAE t >= 2 against S, positive in each test season, and the information test's t for g not lower than S's by more than 1.
- **Replace the shipped model's margin** only if a variant is Better. Otherwise `game_model.json`, the Slate and the Game Picks record stay as they are. Even if Better, the live change would go
  in its own pull request with the record restated (CLAUDE.md), not in this one.
- Whether anything beats the market is reported but does not decide: the shipped model does not, and a challenger that merely ties it has not changed what the picks are.

## About refining until it wins

Each variant above is one more look at the same two test seasons, so a rule of thumb: with four looks, some pass by chance. Therefore:

- This round scores exactly the four variants above, once, and the results file reports all four.
- If a later round is wanted, it is registered here before it runs, tuned on the tune seasons only, and its Better threshold is raised to t >= 2.5 (three-plus looks) and t >= 3 (five-plus).
  A variant first noticed while reading these test seasons is a hypothesis for the next round, not a result of this one.
- The forward record (`docs/game-picks.md`) is the only out-of-sample data beyond these seasons, and it is too small to decide anything yet.
