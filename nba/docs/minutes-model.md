# NBA minutes model: backtest

Generated 2026-09-30T00:40Z by `nba/scripts/build_minutes_model.py`. Walk-forward, out of sample.

Fit on 2022-23 and 2023-24 (who actually sat). Tested on 2024-25 and 2025-26 using the official injury
report 30 min before tip. Scored on players who played: 56,087 player-games.

| Method | MAE (min) | Bias |
|---|---|---|
| Recent minutes only (EWMA) | 4.96 | -0.06 |
| Recent minutes, team scaled to 240 | 4.75 | -0.01 |
| Model, injury report | 4.85 | -0.32 |
| Model, injury report, scaled to 240 | 4.63 | -0.01 |
| Model, hindsight (who actually sat) | 4.84 | +0.25 |

When a same-position rotation teammate (15+ min) is out (21,217 player-games): recent-minutes MAE 5.46 vs model 5.19.

## What the fitted weights say

- Each minute vacated by a same-position teammate: +0.103 min, plus -0.106 x (player's share of 48).
- Each minute vacated by another position: +0.053 min, plus -0.049 x share.
- Blowout (per point of spread beyond 6): starters -0.107 min, bench -0.024 min.
- Back-to-back: +1.135 min, plus -1.476 x share.
- EWMA smoothing alpha 0.25.
