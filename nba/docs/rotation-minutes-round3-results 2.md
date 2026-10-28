# Rotation-aware minutes, round 3: results

Rules: [rotation-minutes-round3.md](rotation-minutes-round3.md), committed before the round 3 runner (`b0749a4f6`). Numbers: `nba/data/rotation_minutes_round3.json`. Run once on 2026-10-25.
Verdict slice: the last 40% of 2024-25 (523 games, 10,904 player-games who played), unseen by every model in this round. 2025-26 is context only. Nothing here changes what the page prices or bets.

## Verdict: **FAIL** (3 of 6 conditions met), but the pool-size problem is fixed

C3 = round 1's candidate with four pool-size features. Fit on 2022-23, 2023-24 and the first 60% of 2024-25.

| Ex-ante top 8, bias (projected minus actual) | Old model A | Round 1 features (C) | **C3** |
|---|---|---|---|
| Pool of 12 or fewer (2,505 player-games) | +0.67 | +0.38 | **+0.07** |
| Pool of 13 to 14 (3,186) | -0.50 | -0.21 | **-0.07** |
| Pool of 15 or more (2,297) | **-2.50** | -0.85 | **-0.22** |

| Condition | Needed | Got | Met |
|---|---|---|---|
| Top-8 bias within 0.5 in every pool-size bucket | all three | 0.07, 0.07, 0.22 | yes |
| Overall minutes MAE | t >= 2.5 | 5.155 to 4.971, gain 0.184, t 6.96 | yes |
| Fringe (ranks 9 to 12) gain | >= 0 | -0.071 (t -1.86) | **no** |
| Rotation player Out gain | t >= 2.5 | +0.151 (t 5.69) | yes |
| Props pooled gain, no stat worse | t >= 2.5 | -0.02% (t -0.16); rebounds, assists, 3PM slightly worse | **no** |
| Top-8 bias within 0.3; ranks 9 to 10 within 0.5 | both | -0.07; **-0.80** | **no** |

## Read

- **Your concern is answered on held-out data.** With the pool size known, a padded pool no longer takes minutes from the rotation: the top 8 go from 2.5 minutes short to 0.2, and short pools from +0.67 to +0.07. Adding pool size to the models is what did it (round 1 features alone: -0.85 in padded pools).
- **Context, 2025-26 (fit on all three seasons, no verdict):** minutes MAE 4.922 to 4.771 (gain 0.151, t 9.69); +0.228 in each team's first 15 games (t 6.09); +0.132 with a rotation player out. Top-8 bias by pool size: +0.52 / +0.46 / +0.34, down from +1.22 / -0.39 / -1.83 (A), so the spread across pool sizes is gone though a positive offset of about +0.45 remains.
- **Still unresolved: ranks 9 and 10 are about 0.8 minutes under-projected**, in every round and every season. These players are two groups: those who play real minutes (actual 18.9, projected 14.5) and those who barely play (actual 6.5, projected 12.3). A single expected value is wrong for both, because the real outcome is two-humped. P(rotation) itself is calibrated (62% predicted, 64% actual in the 0.5 to 0.7 band). Fixing this needs a different treatment of the fringe (a probability of being in the rotation carried to the prop, not one minutes number), not another feature.
- **Props do not move**, in any of the three rounds (t between -1.3 and 2.1). The average minutes error was already small for the top 8, so the aggregate prop gain is below what this test can detect. The pool-size effect is concentrated in specific games (pools of 15 or more, about a fifth of rotation player-games), where a 2-minute miss is 6 to 8% of a starter's stats. The prop result for that subset alone was not a pre-registered cut; a forward read should register it.

## Where this leaves the minutes work

- **Usable:** C3 fixes the pool-size error in the rotation's minutes and improves minutes overall, most in the first 15 games and with players out.
- **Not proven to help props**, and it carries a known fringe weakness.
- **Next step:** ship C3 as a never-priced shadow (needs the daily state job to export rank, last-3 minutes, games since a player last played and the pool size), with a forward read on 2026-27 whose registered cuts are padded pools (15 or more candidates), short pools (12 or fewer) and the first 15 team games, props included.
