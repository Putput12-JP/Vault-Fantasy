# Game model: roster-continuity carry at season start, pre-registration

Written 2026-11-19, before `nba/scripts/test_carry.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

Correction to the record: in the Nov 19 session a message said an early-season carry lever already had a frozen forward test. It does not. The only frozen forward test is shooting luck (PR 510); the early-season K result (PR 505) was never frozen.

## Why

At each new season every team's rating is multiplied by CARRY (shipped 0.5), the same for every team. A team that kept its roster should carry more of last season's rating, and one that turned over should carry less. The earlier roster-carry test (`season-start-results.md`, ROSTER_K) added the value of players who joined or left and was a no-go; this tests the simpler thing, how much to trust last season's rating, scaled by how much of last season's team is still there. Trigger: the Memphis case, rated off last season's -11.4 after a different offseason.

## Method (leak-free)

- Last season's team minutes by player come from the box scores, regular season only.
- **Continuity** for team t = the share of t's last-season minutes played by players who play for t in its first 3 games of the new season. It is known only after that team's third game, so **games 1 to 3 use the shipped carry**. After the team's third game the rating R is corrected by `(f - CARRY) x R_end`, where R_end is the team's rating at the end of last season and `f = clip(a + b x (continuity - 0.5), 0.05, 0.95)`. This treats the updates since the season start as additive, which is an approximation. Only the margin rating R is touched; offense, defense, totals and every other parameter are unchanged.
- Shipped reference **S**: `data/game_model.json`, injury report as of tip. The cell a = 0.5, b = 0 is exactly S and is run as a sanity check.

## Variant and tuning

**CC**: grid a in {0.4, 0.5, 0.6}, b in {0, 0.3, 0.6, 1.0}. Chosen on 2022-23 and 2023-24 (2021-22 warm-up) by margin MAE over the **first 28 days of each season**, against the actual margin, who actually sat. This lever is early-season by design, so that window is the one judged.

## Scoring and verdict rules (fixed now)

Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games (1,000 draws, seed 11). Report margin MAE vs S for the first 28 days and the whole season, the information test against the close, and margin MAE against the close.

CC is **Better** only if: (1) pooled first-28-days t of -2 or less against S; (2) negative in each test season; (3) not worse over the whole season at t +2 or more; (4) the information test against the close within 1 t of S. A pass leads to a frozen forward test, never to shipping.

## Not in this test

Carrying offense and defense with continuity, value-of-movers adjustments (already tested), a continuity from preseason rosters or depth charts (not on disk for past seasons), and the early-season K boost (PR 505).
