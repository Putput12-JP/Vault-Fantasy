# Game Simulation v2, step A2: frozen model

Rules: docs/copula-fit-a2.md. Fitted on 2024-25 and 2025-26 opening prices and frozen before the 2026-27 holdout exists. The numbers below are the whole model; `data/copula_frozen.json` is the file the test checks.

- Fit set: 918 games, 23,753 legs. Fingerprint `5d6b2a209672a88d`.
- Fit-set gate (mean over hit minus price within 0.5 points after the shift, every stat): **passed**.

| Stat | Shift b | Over bias before | After |
|---|---|---|---|
| 3-pointers | +0.098 | -3.9 pts | -0.0 pts |
| assists | +0.114 | -4.5 pts | -0.0 pts |
| points | +0.040 | -1.6 pts | -0.0 pts |
| rebounds | +0.081 | -3.2 pts | -0.0 pts |

Spread of true correlations by group (tau^2): same player 0.05545, teammates 0.00154, opponents 0.00007.

| Family | Pairs | rho hat | SE | Weight | Frozen rho |
|---|---|---|---|---|---|
| Same player: points with 3-pointers | 2,872 | +0.450 | 0.040 | 0.97 | +0.437 |
| Same player: points with rebounds | 4,660 | +0.259 | 0.022 | 0.99 | +0.257 |
| Same player: rebounds with assists | 3,181 | +0.190 | 0.029 | 0.99 | +0.187 |
| Same player: points with assists | 3,755 | +0.129 | 0.026 | 0.99 | +0.127 |
| Same player: rebounds with 3-pointers | 2,293 | +0.126 | 0.032 | 0.98 | +0.124 |
| Teammates: assists with 3-pointers | 11,263 | +0.063 | 0.013 | 0.90 | +0.057 |
| Teammates: points with assists | 22,644 | +0.053 | 0.010 | 0.94 | +0.050 |
| Teammates: points with points | 17,970 | -0.052 | 0.010 | 0.94 | -0.048 |
| Teammates: points with 3-pointers | 17,015 | -0.050 | 0.012 | 0.92 | -0.046 |
| Teammates: assists with assists | 7,479 | -0.046 | 0.017 | 0.85 | -0.039 |
| Teammates: 3-pointers with 3-pointers | 4,406 | -0.047 | 0.022 | 0.76 | -0.036 |
| Teammates: rebounds with rebounds | 12,504 | -0.022 | 0.014 | 0.89 | -0.020 |
| Teammates: rebounds with 3-pointers | 14,597 | +0.014 | 0.012 | 0.91 | +0.013 |
| Teammates: rebounds with assists | 19,266 | -0.012 | 0.011 | 0.93 | -0.012 |
| Opponents: points with rebounds | 33,413 | -0.021 | 0.008 | 0.51 | -0.011 |
| Same player: assists with 3-pointers | 2,045 | +0.008 | 0.035 | 0.98 | +0.008 |
| Opponents: rebounds with rebounds | 14,058 | +0.028 | 0.013 | 0.28 | +0.008 |
| Opponents: rebounds with assists | 21,702 | -0.016 | 0.010 | 0.41 | -0.007 |
| Opponents: assists with 3-pointers | 12,865 | +0.016 | 0.012 | 0.32 | +0.005 |
| Opponents: rebounds with 3-pointers | 16,351 | -0.014 | 0.012 | 0.35 | -0.005 |
| Opponents: assists with assists | 8,588 | +0.016 | 0.015 | 0.23 | +0.004 |
| Opponents: points with 3-pointers | 19,175 | +0.004 | 0.011 | 0.39 | +0.002 |
| Teammates: points with rebounds | 29,749 | -0.001 | 0.009 | 0.95 | -0.001 |
| Opponents: points with points | 20,215 | +0.001 | 0.009 | 0.45 | +0.001 |
| Opponents: points with assists | 25,735 | +0.001 | 0.009 | 0.48 | +0.001 |
| Opponents: 3-pointers with 3-pointers | 5,071 | -0.001 | 0.020 | 0.16 | -0.000 |
