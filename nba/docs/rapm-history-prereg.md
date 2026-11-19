# Game model: longer-history RAPM prior, pre-registration

Written 2026-11-19, before `nba/scripts/test_rapm_history.py` was run. Follows `rapm-results.md` (PR 512, stacked on it). Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why

PR 512's RAPM had three seasons of play-by-play, a fixed 0.5 yearly decay and one tune season with no prior at all, and every variant tied the shipped model. The open question it left: does a longer history, with the carry of old seasons tuned, give RAPM enough signal to matter?

## Data (downloaded with the project's own `fetch_hoopr.py --only-pbp 2022 2023`, 2026-11-19)

`raw/hoopr/pbp_2022.csv` (2021-22) and `pbp_2023.csv` (2022-23), about 270 MB each from the sportsdataverse releases, gitignored. With the three files already on disk, every season from 2021-22 to 2025-26 has play-by-play, so both tune seasons now have a prior and the test seasons have up to four prior seasons.

## Method

Exactly as `rapm-prereg.md` (stints from substitutions, time-based possessions, ridge on a net coefficient with a home-court intercept, conjugate gradient, refit every 28 days, minimum 300 possession weight, `rapm value = max(0, coefficient) x 0.99 x mpg / 48`, no overtime, garbage stints kept), except:

- **The yearly decay D applied to accumulated sums at each new season is tuned**, not fixed. Grid: D in {0.5, 0.7, 0.85, 1.0}; ridge lambda in {3000, 10000}.
- Only the all-stints set is used. PR 512 found removing garbage time changed nothing, so it is not repeated.

## Variants, inside the shipped model, everything else at shipped values

Shipped reference **S**: parameters in `data/game_model.json`, injury report as of tip.

- **LO, replace.** Player value = rapm value where the player has one, otherwise the shipped value. C in {0.5, 0.75, 1.0}.
- **LB, add.** Player value = shipped value + LAM x rapm value; C stays 0.5. LAM in {0.5, 1, 2}.

Tuning: **2022-23 and 2023-24**, games from 28 days into each season on, margin MAE against the actual margin, who actually sat, scored against the shipped model on the same games. The (D, lambda, C or LAM) cell with the lowest tune MAE is chosen for each of LO and LB.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report margin MAE vs S for the whole season, the information test against the close, and margin MAE against the close, and the chosen D. Also report, exploratory only, the same variant at D = 0.5 (PR 512's setting) on the same five-season history, to separate the effect of more history from the effect of the tuned decay.

A variant is **Better** only if: (1) pooled whole-season t of at least 2 against S; (2) the difference has the same sign in each test season; (3) the information test against the close is within 1 t of S. A pass leads to a frozen forward test, never to shipping.

## Not in this test

Separate offense and defense coefficients, an informative prior (draft pick, age, box-score rates), using RAPM for team ratings, NBA.com lineup data, and forward scoring.
