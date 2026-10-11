# Minutes spread: per-player error size

Gaussian CRPS and negative log-likelihood of actual minutes (lower is better). t = paired on per-row CRPS vs row (b).

## Train (2023, 2024, 2025), test 2026: 28,071 player-games, mean RMSE 6.003

| sd model | CRPS | NLL | 80% interval coverage | t vs (b) |
|---|---|---|---|---|
| (a) one constant sd | 3.3230 | 3.2112 | 82.5% | -2.94 |
| (b) c x player EWMA volatility (shipped idea) | 3.3166 | 3.2424 | 79.8% | +0.00 |
| (c) LightGBM on squared miss | 3.2916 | 3.1901 | 82.4% | +13.60 |

(c) vs (b): CRPS +0.75%, t +13.60.

## Train (2023, 2024), test 2025: 27,637 player-games, mean RMSE 6.039

| sd model | CRPS | NLL | 80% interval coverage | t vs (b) |
|---|---|---|---|---|
| (a) one constant sd | 3.3416 | 3.2174 | 82.3% | -4.71 |
| (b) c x player EWMA volatility (shipped idea) | 3.3311 | 3.2470 | 79.4% | +0.00 |
| (c) LightGBM on squared miss | 3.3044 | 3.1897 | 82.4% | +13.82 |

(c) vs (b): CRPS +0.80%, t +13.82.

Pass rule (CRPS gain >= 1% and t >= 3 on both holdouts): **FAIL**.
