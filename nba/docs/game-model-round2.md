# Game model round 2: faster early-season learning and a blowout cap

Written 2026-11-10, before either variant was scored on a test season or on this season. Runner: `nba/scripts/test_game_model_round2.py`.
Results land in `nba/docs/game-model-round2-results.md` only after this file is committed. Round 1 was the possession-efficiency challenger
(`docs/game-model-challenger.md`), which asked for any further round to be registered first and to clear t >= 2.5.

## Why

The Game Picks record through 2026-11-09 is 68-85 against the spread and 100-53 straight up on 153 picks, with the market's favourite at 107-46.
An audit of the shipped model (descriptive, nothing tuned; tables in the results file) found the grading, the finals, the lock times and the prices
all correct, and found where the model and the line part ways:

1. **The same teams, every night.** The model sits above the market on LAC (+5.5 points a game), CHA (+4.1), MIL (+3.5) and SAC (+3.1) and below it on
   MIA (-2.9), PHI (-2.7) and BOS (-2.5). Those are last season's ratings, shrunk by half at the season start and then moved 4% of each game's miss. Ten
   games in, a team that changed over the summer has closed about a third of the distance. Across the 30 teams the model's average gap and the team's
   average result against the spread correlate -0.21: where they disagreed, the line was closer.
2. **Blowouts.** A 35-point miss moves a team's rating as far as seven 5-point misses. The season has had an unusual number of them (sd of the final
   margin 16.8 against 16.2 in the two test seasons).

Neither is a bug. Both are places a rating system is commonly improved, and neither was tried in the earlier rounds (roster carry, scoring level,
widened retune, possession ratings).

**Question.** Does a larger rating step in a team's first games of a season, or a cap on how far one blowout moves the ratings, predict NBA margins
better than the shipped model?

## What is held fixed

The cut the shipped model uses: warm-up 2021-22 (label 2022); anything fitted is fitted on 2022-23 and 2023-24 (labels 2023, 2024) only; scored on
2024-25 and 2025-26 (labels 2025, 2026) with the games, lines and injury report (30 minutes before tip) the shipped model is scored on. Every other
parameter keeps its shipped value in `data/game_model.json`. Nothing here writes that file.

## The variants (fixed now; no others are scored this round)

| | Change to the shipped model |
|---|---|
| S | none: the shipped model, the reference |
| E | **Early step.** A team's rating step is `K x (1 + B x max(0, 1 - n / N))`, n = its regular-season games already played this season. The home and away team each use their own step. B from {0, 1, 2, 3, 4}, N from {10, 20, 30} |
| M | **Blowout cap.** The miss that moves the team ratings is clipped to plus or minus CAP points. Scoring (offense, defense) and home court are untouched. CAP from {none, 10, 13, 16, 20, 25, 30} |
| EM | E and M together, each with the value it was given on its own |

**Choosing B, N and CAP.** One pass each over the grid on the tune seasons, minimising whole-season margin MAE with who actually sat (the objective
the shipped parameters were tuned on). B = 0 and CAP = none are in the grids, so "no change" can win; a variant whose grid picks no change is reported
as that and scored as a tie. A value on a grid endpoint is reported.

## Metrics (test seasons, games that have a closing spread)

1. Margin MAE against the final margin, by season and pooled, and for each season's first 4 weeks (28 days from its first game).
2. Against the closing spread: the information test in `build_game_model.info_test` (the final margin on the line and on model minus line), and the
   win rate against the spread at a gap of 0+, 3+ and 5+ against the 52.4% break-even. Reported; only the information test enters a verdict.
3. The closing line's own MAE, the bar none is expected to clear.

A difference is `mean(|error S| - |error V|) / SE` over games: positive means the variant is closer.

## Verdicts (fixed now)

- **Better**: pooled margin-MAE t >= 2.5 against S, positive in each test season, and the information test's t not lower than S's by more than 1.
- **Ship** only a Better variant, and the simplest one when more than one is Better and they are within 1 SE of each other. Otherwise
  `game_model.json`, the Slate and the Game Picks record stay as they are.
- A shipped change goes live for picks from its merge forward. Locked picks are never re-priced (`docs/game-picks.md`); the results file states what
  the record would have been under the variant beside the record as locked, clearly labelled as a replay.

## This season (reported, not part of the verdict)

The 154 regular-season games through 2026-11-09, each variant walked the way the live state is built (the two seasons before this one, then this
one). The variant's margin for a game is its ratings-only margin plus the injury and rest adjustment the live recorder actually applied (the locked
margin minus the shipped model's ratings-only margin), scored against the locked first-look line. At n = 154 one standard error on a win rate is 4
points, so these rows are flagged for monitoring with their sample size whichever way they point.

## Also reported from the audit (descriptive, nothing fitted)

The shipped model's record against the closing spread by grade, by the size of the injury adjustment, by favourite or underdog and by stage of the
season, in the two test seasons and this one, so the grade A run (12-4 on 16 picks) can be read next to its 279-pick history.
