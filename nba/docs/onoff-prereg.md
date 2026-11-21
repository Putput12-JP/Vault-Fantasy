# Game model: on/off player value, pre-registration

Written 2026-11-19, before `nba/scripts/test_onoff.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why, and what data

The injury adjustment prices a missing player by his value, `max(0, game score EWMA - REP x minutes EWMA)`, times C. Game score is a box-score production proxy and says nothing about what the team does with and without him. On/off is the direct measure.

True lineup on/off needs stints, which are not on disk (`raw/stints_*.csv` is absent, and `raw/lineups/` only holds starting-lineup snapshots). **Exact on/off can be built from the box score**, which has each player's plus-minus and minutes: ON = his plus-minus while on court, OFF = (team margin - his plus-minus) over the minutes he sat. This test uses only that, accumulated game by game strictly before each prediction.

This does not use NBA.com. NBA.com's on/off page would add nothing the box score cannot give for the same games, and would not be as-of-date.

## Definitions

Per player, accumulated over past games he played (sums carried into a new season times 0.5, fixed): ON minutes m_on and plus-minus total pm; OFF minutes m_off = (team minutes / 5) - m (OT included) and OFF margin total = team margin - pm.
`swing = 48 x pm / (m_on + K0) - 48 x off_margin / (m_off + K0)`, where K0 is a shrinkage in minutes toward zero.
`oo value = max(0, swing) x mpg / 48`, with mpg the shipped minutes EWMA. Units: points of margin per game the player is worth.

## Variants, inside the shipped model, everything else at shipped values

Shipped reference **S**: parameters in `data/game_model.json`, injury report as of tip.

- **O, replace.** Player value = oo value. Tuned on the tune seasons (2022-23, 2023-24; 2021-22 warm-up) by margin MAE over all games, who actually sat: C in {0.25, 0.5, 0.75, 1.0, 1.5} and K0 in {200, 500, 1000}.
- **B, add.** Player value = shipped value + LAM x oo value, C stays at the shipped 0.5. Tuned the same way: LAM in {0.5, 1, 2, 4} and K0 in {200, 500, 1000}.

The totals adjustment is off in the shipped model (CT 0), so totals are untouched.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, the injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report margin MAE vs S for the whole season, the information test against the close, and margin MAE against the close. Also report the same on games where the injury report lists at least one rotation player out for either team (exploratory; the number is the sample for the claim).

A variant is **Better** only if: (1) pooled whole-season t of at least 2 against S; (2) the difference has the same sign in each test season; (3) the information test against the close is within 1 t of S. Otherwise it changes nothing live.

## Not in this test

Lineup-based on/off from stints, RAPM, using on/off for team ratings (only the injury adjustment is touched), and forward scoring (only after a variant passes and its settings are frozen).
