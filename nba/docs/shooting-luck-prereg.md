# Game model: three-point shooting luck, pre-registration

Written 2026-11-19, before `nba/scripts/test_shooting_luck.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why

Three-point percentage over a few weeks is mostly noise, so a team that shot 45% from three and won big has a rating that over-reads it, and the opponent that shot cold is under-rated. The rating update currently learns from raw margin and raw points. Test whether discounting the shooting part of a result improves forecasts.

## Definitions

Each team has a pre-game three-point baseline: (3PM + K0 x league rate) / (3PA + K0), built from its own past games (sums carried into a new season times 0.5, fixed), with the league rate a running average over all past games and K0 pseudo-attempts. Team data come from the player box scores.
`luck(team, game) = 3 x (team 3PM - team 3PA x baseline)`, in points above what its own baseline implies. Computed before the game is added to the baseline.

## Variants, inside the shipped model, everything else at shipped values

Shipped reference **S**: parameters in `data/game_model.json`, injury report as of tip.

- **M, margin.** The rating update learns from `actual margin - L x (luck home - luck away)`. L and K0 are chosen on the tune seasons (2022-23, 2023-24; 2021-22 warm-up) by margin MAE against the actual margin, all games, who actually sat. Grid: L in {0.25, 0.5, 0.75, 1.0}, K0 in {300, 1000}.
- **T, scoring.** The offense/defense and scoring-level updates learn from each side's points minus L x its own luck. The home-court update is not adjusted. L and K0 are chosen on the tune seasons by total MAE, same grid.

M affects margins and T affects totals; they are scored on those metrics respectively and are not combined.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, the injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report MAE vs S for the whole season and for the first 28 days of each season, the information test against the close, and MAE against the close. The first-28-days window is reported because noise matters most early; it carries no separate verdict.

A variant is **Better** only if: (1) pooled whole-season t of at least 2 against S; (2) the difference has the same sign in each test season; (3) the information test against the close is within 1 t of S. Otherwise it changes nothing live.

## Not in this test

Free throws, two-point shooting and opponent-quality adjustments, any shot-quality (tracking) data from NBA.com, and forward scoring (only after a variant passes and its settings are frozen).
