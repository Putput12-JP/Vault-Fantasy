# Game model: garbage-time capping, pre-registration

Written 2026-11-19, before `nba/scripts/test_garbage_time.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why

The rating update moves a team by K x (actual margin - predicted margin), so a 30-point finish counts three times a 10-point one even when the last quarter was bench players. Memphis lost to OKC by 31 on Nov 6, for example. Test whether discounting that noise improves margin accuracy.

## Variants, inside the shipped model, shipped parameters otherwise unchanged

Shipped reference **S**: parameters in `data/game_model.json`, injury report as of tip.

- **G1, capped margin (box score only).** The rating update uses the actual margin clipped to +/- C points. C is chosen on the tune seasons (2022-23, 2023-24; 2021-22 warm-up) by margin MAE over all games against the actual (unclipped) margin, who actually sat. Grid: C in {10, 12, 15, 20, 25}. Scores, O/D updates and totals are untouched.
- **G2, frozen margin at garbage time (play-by-play).** The rating update uses the margin at the first play in the 4th quarter (period 4 only) where the lead is at least 25 with 9:00 or less left, or at least 20 with 6:00 or less, or at least 15 with 3:00 or less. If the game never reaches that state, or goes to overtime, the final margin is used. No tuned parameters; the ladder is fixed here. Play-by-play exists on disk for 2023-24, 2024-25 and 2025-26 only (`raw/hoopr/pbp_2024..2026.csv`), so in 2021-22 and 2022-23 G2 falls back to the final margin. G2 is therefore partly inconsistent in the early history and fully in effect in both test seasons.

The comparison target is always the actual final margin. P, Q and E from `early-k-pace-prereg.md` are not combined with these.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report margin MAE vs S for the whole season and for the games in the top decile of |final margin| and the rest; the information test against the close; and margin MAE against the market close.

A variant is **Better** only if: (1) pooled whole-season t of at least 2 against S; (2) the difference has the same sign in each test season; (3) the information test against the close is within 1 t of S. Otherwise it changes nothing live. The blowout/rest split and anything seen after the run are exploratory.

## Not in this test

Forward scoring (only after a variant passes and its setting is frozen), and any use of garbage-time-filtered scoring for totals or player stats.
