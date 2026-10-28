# Minutes audit against the live record, 2026-10-20 to 2026-10-27

Written 2026-10-28. Descriptive, post hoc. Source: last pre-tip minutes row per player (`nba-data` snapshots/minutes.jsonl) against the box score (`results/`).
1,612 player-games, 112 team-games; 1,234 played, 378 did not (23%).

## Team totals and ghosts
- Projected minutes per team-game, summed over the pool: **282.7** (240 on the floor). The pool averages 14.4 players, 3.4 of whom did not play.
- **46.4 projected minutes per team-game sit on players who did not play** (mean 13.8 each; 247 rows at 10+ minutes, 86 at 20+).
- DNP rate by projected band: 0-8 min 46%, 8-15 40%, 15-22 23%, 22-28 13%, 28-34 7%, 34+ 1%.

## Accuracy, players who played
| Model | n | MAE | Bias (proj - actual) | Misses of 8+ |
|---|---|---|---|---|
| v2 (priced) | 1234 | 5.86 | -0.12 | 26.8% |
| v3 (shadow) | 1234 | 5.57 | -1.11 | 23.9% |
| GBM (shadow) | 1120 | 4.98 | -0.47 | 18.9% |
| early blend (shadow) | 211 | 5.21 | -0.22 | 22.7% |
| rotation C3 (shadow) | 292 | 5.35 | +0.38 | 21.6% |
Same 264 players in all of v2, v3, GBM, C3: 5.72, 5.52, 5.13, 5.39.

## v2 bias by projected minutes (players who played)
0-8: -3.2, 8-15: -1.1, 15-22: -0.5, 22-28: -0.5, 28-34: +1.4, 34+: +3.9. Starters are projected too high and the fringe too low.

## Reading
Samples are 8 days; nothing here is a test. The priced model spreads minutes over players who do not play, over-projects heavy minutes, and trails every shadow. GBM is best on every cut and passed its own backtest rule (docs/minutes-gbm.md).
