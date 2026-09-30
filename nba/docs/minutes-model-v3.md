# Minutes model v3: backtest

Generated 2026-09-30T17:27Z by `nba/scripts/build_minutes_model_v3.py`. Fit on 2022-23 to 2024-25, tested on
2025-26 with the injury report 30 min before tip; 28,254 player-games, identical for every row below.

| Model | MAE (min) | RMSE | Bias | Misses of 8+ min |
|---|---|---|---|---|
| v2 (shipped) | 4.690 | 6.119 | +1.075 | 17.1% |
| v3 (role, returns, new team, market spread) | 4.650 | 6.065 | +1.074 | 16.9% |
| v3 knowing who started (sizes a lineups feed) | 4.515 | 5.907 | +1.076 | 16.0% |

## Where the new pieces act (2025-26)

| Slice | Games | MAE v2 | MAE v3 | 8+ misses v2 | 8+ misses v3 |
|---|---|---|---|---|---|
| first game back | 1,221 | 5.49 | 5.04 | 24.7% | 20.6% |
| games 2-3 back | 1,860 | 5.05 | 5.05 | 19.4% | 19.4% |
| role switch (last game role differs from usual) | 1,621 | 6.00 | 5.81 | 28.0% | 26.5% |
| market spread 12+ | 4,716 | 4.65 | 4.62 | 16.7% | 16.8% |

## Fitted weights

- EWMA learning rate 0.2; new team: 0.35 for the first 8 games.
- Role: +0.275 x (his minutes in last game's role - his overall average).
- Returns (x his usual minutes): first game back -0.162, games 2-3 -0.043, games 4-6 +0.007.
- Blowout per point of spread beyond 6: starters -0.077, bench -0.033.
- Vacated minutes: same position +0.108, other +0.057. Back-to-back +0.751.

Learning-rate grid (fit 2022-24, scored on 2024-25):

| EWMA | New-team rate | MAE | 8+ misses |
|---|---|---|---|
| 0.2 | none | 4.671 | 16.8% |
| 0.2 | 0.35 | 4.658 | 16.8% |
| 0.2 | 0.5 | 4.660 | 16.9% |
| 0.25 | none | 4.671 | 16.9% |
| 0.25 | 0.35 | 4.663 | 16.8% |
| 0.25 | 0.5 | 4.664 | 16.9% |
| 0.3 | none | 4.682 | 17.1% |
| 0.3 | 0.35 | 4.679 | 17.0% |
| 0.3 | 0.5 | 4.677 | 17.1% |
| 0.4 | none | 4.726 | 17.5% |
| 0.4 | 0.35 | 4.726 | 17.5% |
| 0.4 | 0.5 | 4.725 | 17.5% |
