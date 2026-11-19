# Shooting-luck variants: frozen forward test

Written 2026-11-19, before any forward game was scored. Follows `shooting-luck-prereg.md` and `shooting-luck-results.md` (PR 509: T and M passed the backtest rule, not shipped).

## What is frozen

`nba/data/shooting_luck_frozen.json`, written once by `nba/scripts/test_shooting_luck_forward.py --freeze` and committed. It holds the two settings exactly as the backtest chose them on 2022-23 and 2023-24 (T: L 0.5, K0 1000; M: L 0.25, K0 300), the shipped parameters at freeze time (`data/game_model.json`), and the freeze time in Central. `--check` fails if the file changes after it is committed or if the shipped parameters change. Nothing is retuned.

## Scored games

Regular season 2026-27 games that tip after the freeze time. Every model (shipped, M, T) is replayed walk-forward from 2021-22 with the box scores available, each game predicted before it is learned. All three use no injury adjustment (`none` mode), because the as-of injury reports are not on disk for 2026-27; the comparison is paired, and the variants only change the ratings, so the injury adjustment is common to both.

## Rule, fixed now

Read once at **300 scored games** (earlier reads print the count and no verdict). Metric: T on total MAE, M on margin MAE, each paired against the shipped model with a bootstrap SE over games (1,000 draws, seed 11).

- **Pass:** variant minus shipped is negative with t of -2 or less, and negative in both halves of the scored games (first 150, last 150).
- **No-go:** the difference is zero or positive at 300 games.
- **Otherwise:** keep reading to 600 games, then apply the same rule; no change to the rule or settings in between.

Not a pass for shipping by itself: a pass moves the question to whether the live model should use the variant, which needs its own change and the PR/record rules in the project instructions. Market totals are not stored forward, so no forward comparison against the closing total is made; the backtest gap to the close (0.44 points) stands.

## Also reported, no verdict

All 2026-27 games to date, including those before the freeze. The parameters were chosen on 2022-23 and 2023-24 and tested on 2024-25 and 2025-26, so these games are out of sample for the settings, but the idea was proposed after they were played, so they are not the forward read.
