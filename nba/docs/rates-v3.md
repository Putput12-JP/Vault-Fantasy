# Per-stat memory (rates v3): backtest

Generated 2026-09-30T17:28Z by `nba/scripts/build_rates_v3.py`. Each learning rate tuned on 2022-23 and 2023-24,
tested on 2025-26. Both models are given the TRUE minutes, so this isolates the per-minute rates.

| Stat | Player-games | RMSE v1 (one EWMA) | RMSE v3 (components) | MAE v1 | MAE v3 | Bias v1 | Bias v3 |
|---|---|---|---|---|---|---|---|
| pts | 28,071 | 5.038 | 4.994 | 3.743 | 3.721 | -0.069 | -0.032 |
| reb | 28,071 | 2.132 | 2.113 | 1.603 | 1.591 | +0.013 | +0.028 |
| ast | 28,071 | 1.676 | 1.673 | 1.215 | 1.213 | -0.013 | -0.017 |
| 3pm | 28,071 | 1.158 | 1.145 | 0.816 | 0.815 | -0.007 | +0.010 |

## Tuned memory

| Component | Learning rate | Half-life (games) |
|---|---|---|
| fg2a per minute | 0.1 | 6.6 |
| fg3a per minute | 0.07 | 9.6 |
| fta per minute | 0.05 | 13.5 |
| oreb per minute | 0.035 | 19.5 |
| dreb per minute | 0.035 | 19.5 |
| ast per minute | 0.07 | 9.6 |
| p2 | decay 0.01/game, plus 100 attempts at the position average | 69.0 |
| p3 | decay 0.01/game, plus 200 attempts at the position average | 69.0 |
| ft | decay 0.01/game, plus 25 attempts at the position average | 69.0 |

v1 used one learning rate, 0.10 (half-life 6.6 games), for points, rebounds, assists and 3PM per minute.
