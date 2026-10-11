# Minutes challenger: gradient boosting vs linear

Oracle absences (who actually sat); no injury report in this sandbox, so numbers compare models to each other, not to
minutes-model-v3.md. t = paired mean(e_base^2 - e_model^2) / s.e. against the first row. "Stat RMSE" multiplies each model's
minutes by the same per-minute rate (EWMA 0.07), so only the minutes differ.

## Train (2023, 2024, 2025), test 2026: 28,071 player-games

| Model | MAE | RMSE | R2 | Misses 8+ min | vs first | t | pts RMSE | reb RMSE | ast RMSE | 3PM RMSE |
|---|---|---|---|---|---|---|---|---|---|---|
| ridge, shipped-style features | 4.872 | 6.311 | 0.630 | 18.3% | +0.00% | +0.00 | 6.024 | 2.510 | 1.827 | 1.245 |
| ridge, + role/rest/form features | 4.785 | 6.215 | 0.641 | 17.7% | +1.52% | +10.73 | 6.006 | 2.498 | 1.824 | 1.244 |
| LightGBM, all features | 4.612 | 6.001 | 0.665 | 16.4% | +4.92% | +20.56 | 5.985 | 2.496 | 1.820 | 1.243 |

Gain over shipped-style linear +4.92%, t +20.56. Nonlinearity alone (vs the richer ridge): +3.46%.

## Train (2023, 2024), test 2025: 27,637 player-games

| Model | MAE | RMSE | R2 | Misses 8+ min | vs first | t | pts RMSE | reb RMSE | ast RMSE | 3PM RMSE |
|---|---|---|---|---|---|---|---|---|---|---|
| ridge, shipped-style features | 4.889 | 6.369 | 0.654 | 18.4% | +0.00% | +0.00 | 6.057 | 2.564 | 1.831 | 1.266 |
| ridge, + role/rest/form features | 4.793 | 6.248 | 0.667 | 17.7% | +1.90% | +13.19 | 6.031 | 2.550 | 1.828 | 1.264 |
| LightGBM, all features | 4.626 | 6.030 | 0.690 | 16.8% | +5.31% | +21.29 | 6.018 | 2.555 | 1.828 | 1.264 |

Gain over shipped-style linear +5.31%, t +21.29. Nonlinearity alone (vs the richer ridge): +3.48%.

Top features by gain (last fit): ew2 (46%), ew3 (32%), ew1 (9%), vs (3%), days_off (2%), vo (2%), last (1%), n_out (1%)

Pass rule: LightGBM beats the shipped-style linear model by >= 1.5% RMSE with t >= 3 on BOTH holdouts. Result: **PASS**.
