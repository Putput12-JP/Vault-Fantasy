# Rates v4 candidate: Kalman volume rates vs rates v3

Tuned on (2023, 2024), tested on 2026 (given true minutes). v1 = one EWMA; v3 = per-component EWMA; v4 = v3 with Kalman volume.

| Stat | Player-games | RMSE v1 | RMSE v3 | RMSE v4 | v4 vs v3 | MAE v3 | MAE v4 | Bias v3 | Bias v4 |
|---|---|---|---|---|---|---|---|---|---|
| pts | 28,071 | 5.0383 | 4.9937 | 4.9870 | +0.13% | 3.7206 | 3.7165 | -0.0318 | -0.0144 |
| reb | 28,071 | 2.1318 | 2.1126 | 2.1108 | +0.09% | 1.5915 | 1.5908 | +0.0278 | +0.0285 |
| ast | 28,071 | 1.6758 | 1.6735 | 1.6684 | +0.30% | 1.2133 | 1.2106 | -0.0169 | -0.0124 |
| 3pm | 28,071 | 1.1583 | 1.1451 | 1.1450 | +0.01% | 0.8148 | 0.8142 | +0.0100 | +0.0117 |

Pre-registered rule: v4 beats v3 on >= 3 of 4 stats and no stat is worse by more than 0.2%. Result: **PASS** (4 of 4 better, 0 materially worse).
