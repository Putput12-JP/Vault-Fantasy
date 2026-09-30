# NBA usage cascade: backtest

Generated 2026-09-30T00:42Z by `nba/scripts/build_usage_cascade.py`. Fit 2022-23 + 2023-24, tested 2024-25 +
2025-26 with the injury report 30 min pre-tip. Uses each player's ACTUAL minutes, so this is the per-minute
effect only (the minutes model handles extra playing time).

| Stat | Use? | Test player-games | MAE: rate only | MAE: + cascade | Teammate out: n | MAE: rate only | MAE: + cascade | Bias: rate only | Bias: + cascade |
|---|---|---|---|---|---|---|---|---|---|
| pts | yes | 55,278 | 3.8 | 3.794 | 41,356 | 3.826 | 3.817 | -0.266 | +0.098 |
| reb | yes | 55,278 | 1.632 | 1.631 | 41,356 | 1.647 | 1.646 | +0.001 | +0.02 |
| ast | no | 55,278 | 1.224 | 1.227 | 41,322 | 1.233 | 1.236 | -0.042 | +0.033 |
| 3pm | no | 55,278 | 0.823 | 0.831 | 40,663 | 0.831 | 0.841 | -0.033 | +0.007 |
| fga | yes | 55,278 | 2.118 | 2.112 | 41,356 | 2.138 | 2.129 | -0.12 | +0.051 |
| pra | yes | 55,278 | 4.468 | 4.454 | 41,356 | 4.502 | 4.483 | -0.307 | +0.119 |

Bias < 0 means the plain rate UNDER-predicts: the player does more when teammates sit.

**Finding:** the per-minute effect is small. When a teammate sits, most of the extra production comes from
extra MINUTES (see minutes-model.md), not a higher rate. Only stats marked "yes" beat the plain rate out of
sample; the prop model uses the cascade for those and the plain rate for the rest.

Weights per stat: [same-position vacated, other-position vacated, same x relative rate, other x relative rate],
each per unit of (minutes / 48) x the out players' per-game production of that stat.
