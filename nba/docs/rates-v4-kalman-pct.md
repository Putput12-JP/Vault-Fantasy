# Rates v4 step 2: Kalman percentages, with paired significance

Tuned on (2023, 2024), tested on 2026, given true minutes. t = paired mean(e_v3^2 - e_model^2) / s.e.; |t| >= 2 is real.

| Stat | n | RMSE v3 | vol_k | pct_k | both_k | t vol_k | t pct_k | t both_k |
|---|---|---|---|---|---|---|---|---|
| pts | 28,071 | 4.9937 | 4.9870 (+0.14%) | 4.9945 (-0.01%) | 4.9881 (+0.11%) | +4.17 | -0.51 | +2.50 |
| reb | 28,071 | 2.1126 | 2.1108 (+0.08%) | 2.1126 (+0.00%) | 2.1108 (+0.08%) | +2.76 | +0.00 | +2.76 |
| ast | 28,071 | 1.6735 | 1.6684 (+0.30%) | 1.6735 (+0.00%) | 1.6684 (+0.30%) | +5.83 | +0.00 | +5.83 |
| 3pm | 28,071 | 1.1451 | 1.1450 (+0.01%) | 1.1452 (-0.00%) | 1.1452 (-0.01%) | +0.35 | -0.21 | -0.18 |

Pass rule: better than v3 on >= 3 of 4 stats, none worse by > 0.2%, and t >= 2 (better direction) on >= 2 stats.
Amended before reading any result, after the first run crashed: pct_k only changes points and 3PM (rebounds and assists
are identical by construction), so for pct_k the rule is: better on both affected stats, none worse, t >= 2 on at least one.

- **vol_k**: better on 4 of 4 affected stats, materially worse on 0, significant on 3 -> **PASS**
- **pct_k**: better on 0 of 2 affected stats, materially worse on 0, significant on 0 -> **FAIL**
- **both_k**: better on 3 of 4 affected stats, materially worse on 0, significant on 3 -> **PASS**
