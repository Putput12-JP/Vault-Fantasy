# Minutes bake-off results, 2025-26 (rule: [minutes-bakeoff.md](minutes-bakeoff.md))

Fit rows 80,397 (GBM, 2023-2025); test pool 34,443 rows, 27,799 player-games who played. T = 239.6723. `data/minutes_bakeoff.json` holds every number.

## 1. Players who played

| Model | MAE | RMSE | Bias | Misses 8+ | MAE gain vs v2 | t |
|---|---|---|---|---|---|---|
| A | 4.9217 | 6.3071 | -0.059 | 18.8% | | |
| C3 | 4.7705 | 6.1496 | +0.187 | 17.0% | +0.1512 | 10.12 |
| G | 4.6359 | 6.0216 | -0.004 | 16.5% | +0.2858 | 15.43 |
| GP | 4.6554 | 6.0231 | +0.272 | 16.6% | +0.2664 | 17.07 |

GP against C3: MAE gain +0.1152, t 9.53.

## 2. Top 8 bias (projected minus actual) by pool size

| Pool | n | A | C3 | G | GP |
|---|---|---|---|---|---|
| size_le_12 | 7078 | +1.216 | +0.523 | -0.384 | +0.405 |
| size_13_14 | 8413 | -0.386 | +0.463 | +0.127 | +0.231 |
| size_ge_15 | 4606 | -1.826 | +0.34 | -0.107 | +0.127 |

## 3. Props proxy (MAE of the stat projection)

| Stat | n | A | C3 | G | GP |
|---|---|---|---|---|---|
| pts | 27797 | 4.5495 | 4.5264 | 4.5013 | 4.5079 |
| reb | 27797 | 1.8702 | 1.8651 | 1.8574 | 1.8591 |
| ast | 27797 | 1.3289 | 1.3289 | 1.3249 | 1.3266 |
| 3pm | 27797 | 0.8849 | 0.8865 | 0.8817 | 0.8845 |

## 4. Expected minutes over every pool row (DNP = 0)

| A | C3 | G | GP |
|---|---|---|---|
| 5.2557 | 5.1232 | 4.9897 | 4.9829 |

## 5. Team totals per team-game

| Model | if everyone plays | expected | minutes on players who did not play |
|---|---|---|---|
| A | 264.9 | 236.9 | 26.3 |
| C3 | 267.4 | 239.7 | 26.2 |
| G | 264.0 | 237.1 | 24.9 |
| GP | 266.9 | 239.7 | 24.8 |

Actual minutes of players who played: 239.2 over 2614 team-games.

## Rule

- 1_played_mae: PASS
- 2_top8_bias: PASS
- 3_props: PASS
- 4_expected_minutes: PASS

**PROMOTE GP**
