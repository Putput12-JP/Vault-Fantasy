# Game model: stint RAPM with and without garbage time, pre-registration

Written 2026-11-19, before `nba/scripts/test_rapm.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why

The on/off test (PR 508) used box-score plus-minus and lost to the shipped game-score value, with the note that stint RAPM corrects for teammates and opponents and was not tested. This tests it, and tests whether removing garbage time from the stints matters.

## Data and method (no downloads; stdlib only)

- **Stints from the ESPN play-by-play already on disk** (`raw/hoopr/pbp_2024..2026.csv`, i.e. seasons 2023-24, 2024-25, 2025-26). Starters come from the box score (`starter` flag, five per team). Substitution plays ("X enters the game for Y", with both athlete ids) update the floor five. A stint ends at any substitution or the end of regulation. Points are the score change over the stint, taken from the score columns. Overtime is dropped. A game is dropped if a substitution does not match the current five, or a team has no five starters.
- **Possessions are approximated by time**: a stint of s seconds counts as s x 99 / 2880 possessions per side. This is a simplification of the box-score possession estimate, chosen because it needs no event counting; it is the weight in the fit.
- **Garbage time** uses the ladder from `garbage-time-prereg.md`: the first 4th-quarter play with a lead of at least 25 (9:00 or less left), 20 (6:00) or 15 (3:00). Stints starting at or after it are garbage stints (a stint straddling it is split there). Games that go to overtime have none.
- **RAPM**: one net coefficient per player. For each stint, y = 100 x (home points - away points) / possessions; x = +1 for each home player, -1 for each away player, plus a home-court intercept (not penalised); weight = possessions; ridge penalty lambda on the player coefficients. Solved by conjugate gradient on the normal equations.
- **Walk-forward**: accumulated sums include only games before the current one. At each new season the accumulated sums are multiplied by 0.5 (fixed). The coefficients are refit when 28 or more days have passed since the last fit and at each season's first fit after it has stints. A player has a RAPM value only once his cumulative possession weight is at least 300 (a fixed floor).
- `rapm value = max(0, coefficient) x 0.99 x mpg / 48`: points of margin per game, with mpg the shipped minutes average. Same units and floor at zero as the on/off test.

## Variants, inside the shipped model, everything else at shipped values

Shipped reference **S**: parameters in `data/game_model.json`, injury report as of tip.

Two stint sets, **A** (all stints) and **G** (garbage stints removed), crossed with two uses:

- **O, replace.** Player value = rapm value where the player has one, otherwise the shipped value. C and lambda tuned.
- **B, add.** Player value = shipped value + LAM x rapm value. LAM and lambda tuned; C stays 0.5.

So four variants: OA, OG, BA, BG. Tuning grids: lambda in {3000, 10000}; C in {0.5, 0.75, 1.0}; LAM in {0.5, 1, 2}. **Tuning uses 2023-24 only** (the one tune season with play-by-play) over the games from 28 days into that season on, margin MAE against the actual margin, who actually sat, scored against the shipped model on the same games. The 2022-23 season has no play-by-play on disk, so the tune is thinner than in the earlier tests.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report margin MAE vs S for the whole season, the information test against the close, and margin MAE against the close. Also report the stint validity: share of games kept, and the correlation of stint-derived minutes with box-score minutes.

A variant is **Better** only if: (1) pooled whole-season t of at least 2 against S; (2) the difference has the same sign in each test season; (3) the information test against the close is within 1 t of S. With four variants, one pass at t just above 2 is weak evidence by itself; a pass leads to a frozen forward test, never to shipping. The comparison between A and G (garbage time removed or not) is exploratory and carries no verdict.

## Not in this test

RAPM used for team ratings, separate offense and defense coefficients, longer-than-one-year priors, NBA.com lineup data, and forward scoring (only after a variant passes and its settings are frozen).
