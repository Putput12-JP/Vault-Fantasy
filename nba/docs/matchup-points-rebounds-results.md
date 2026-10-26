# Matchup test for points and rebounds, Stage 1: results

Rules: [matchup-points-rebounds-test.md](matchup-points-rebounds-test.md) (committed before the runner, data-source clarification `b9667a68d`, live-form rule committed before the joint context). Numbers: `nba/data/matchup_points_rebounds.json`, `nba/data/matchup_points_joint.json`. Run once on 2026-10-26.
Indices from the team box scores, real teams only, every daily league-mean table asserted over exactly 30 teams (214 and 212 tables, no failure). Nothing here changes what the page prices or bets by itself.

## Verdict: **PASS** for P_vol, P_eff (points) and R_miss (rebounds), each alone

| | P_vol (FGA allowed) | P_eff (points per attempt allowed) | R_miss (misses per 48 in the opponent's games) |
|---|---|---|---|
| Stat | points | points | rebounds |
| Rows, 2024-25 fit / 2025-26 test | 27,345 / 27,797 | 27,345 / 27,797 | 27,345 / 27,797 |
| Slope fitted on 2024-25 (frozen) | **+0.706** | **+0.727** | **+0.259** |
| Slope estimated on 2025-26 alone | +0.840 (t 7.29) | +0.657 (t 6.22) | +0.593 (t 4.54) |
| Frozen slope on 2025-26: stat MAE gain | +0.0064 (**t 4.71**) | +0.0056 (**t 3.43**) | +0.00066 (**t 3.23**) |
| Random-defense control | -0.0055 (t -3.68) | -0.0026 (t -1.61) | -0.00002 (t -0.11) |
| Halves of 2025-26 | +0.0058, +0.0070 | +0.0034, +0.0077 | +0.00095, +0.00038 |
| Multiplier, 5th / 50th / 95th percentile | 0.971 / 0.998 / 1.036 | 0.963 / 0.998 / 1.037 | 0.987 / 1.000 / 1.011 |
| Verdict | PASS | PASS | PASS |

Dose response by index fifth (points or rebounds vs projection): P_vol -5.0%, -4.8%, +0.8%, +1.1%, +3.2%; P_eff -4.6%, -3.8%, -0.7%, +1.2%, +3.2%; R_miss -0.5%, +0.5%, 0.0%, +3.4%, +2.3%.

## Points: both indices, not one (registered rule)

Volume and efficiency of points allowed are almost uncorrelated (correlation of the two regressors 0.03), so they are separate information, not the same thing counted twice. Fitted jointly on 2024-25: **vol 0.6845, eff 0.700**. Against P_vol alone on 2025-26 the joint pair lowers points MAE by **0.0048 (t 3.14)**, above the registered 2.0, so
**the live points term uses both**: `clip(1 + 0.6845 x P_vol + 0.700 x P_eff, 0.7, 1.3)`.

## Read

- **Points are the strongest result so far** (t 4.7 and 3.4, controls negative or flat, slopes stable between seasons: 0.71 against 0.84, 0.73 against 0.66). The effect is a spread of roughly plus or minus 3 to 4% on a points projection, concentrated in the ends.
- **Rebounds pass but are small**: a spread of about plus or minus 1%, a gain of 0.0007 per player-game, a slope that moved a lot between seasons (0.26 fitted, 0.59 on 2025-26 alone), and a dose response that is not monotone. It clears the registered bar; it is not worth much. It goes in with the smallest expectation and the same forward read.
- **Combos** (PRA, PR, PA, RA) inherit the parts: a points and rebounds change of a few percent each.
- **Limits**: the same 2025-26 season has been read many times; the slopes were fitted on a different season, which is the protection. Playoff games are in both the prior-season rates and the walk (the runner used the full game list). Not a price result. No claim of an edge over the market.
- **Not computed:** the effect on a combo as one line (it follows from the parts); steals, blocks and turnovers (registered separately, the box score has them).
