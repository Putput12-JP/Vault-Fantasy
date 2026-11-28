# Game model round 5: results

Generated 2026-11-10T23:04Z by `nba/scripts/test_game_model_round5.py`. Rules: [game-model-round5.md](game-model-round5.md) (committed before this ran).

## Margin (option L)

Chosen on 2024-25: W 0.75, KL 0.16. Chosen on 2025-26: W 0.75, KL 0.16. Ship parameters (both seasons): W 0.75, KL 0.16.

| Scored on | Parameters from | Games | Shipped MAE | Variant MAE | Shipped minus variant | t | Closing line MAE |
|---|---|---|---|---|---|---|---|
| 2025-26 | 2024-25 (0.75, 0.16) | 1321 | 11.294 | 11.193 | +0.101 | +2.21 | 11.012 |
| 2024-25 | 2025-26 (0.75, 0.16) | 1320 | 10.907 | 10.762 | +0.145 | +3.35 | 10.636 |
| **Pooled, out of sample** | | 2641 | 11.101 | 10.978 | +0.123 | **+3.91** | |

Information test against the closing spread (does the model know something the line does not), pooled out of sample: variant g 0.194 (t 1.66), shipped g 0.118 (t 1.23).
Against the closing spread, pooled out of sample: variant 1342-1299 (50.8%), at a 3+ gap 246-244 (50.2%), at 5+ 67-70 (48.9%). Shipped: 1342-1299 (50.8%), 422-398 (51.5%), 132-147 (47.3%). Break-even is 52.4%.

Grid, MAE on 2024-25 / 2025-26 (shipped 10.9071 / 11.2944):

| W \ KL | 0.04 | 0.08 | 0.12 | 0.16 | 0.24 | 0.32 | 0.5 |
|---|---|---|---|---|---|---|---|
| 0.25 | 10.882 / 11.277 | 10.876 / 11.280 | 10.962 / 11.359 | 11.098 / 11.464 | 11.434 / 11.753 | 11.851 / 12.143 | 13.287 / 13.474 |
| 0.5 | 10.894 / 11.284 | 10.811 / 11.232 | 10.816 / 11.243 | 10.852 / 11.274 | 10.987 / 11.381 | 11.187 / 11.540 | 11.917 / 12.111 |
| 0.75 | 10.939 / 11.328 | 10.820 / 11.224 | 10.778 / 11.197 | 10.762 / 11.193 | 10.764 / 11.205 | 10.803 / 11.236 | 11.033 / 11.355 |
| 1.0 | 11.015 / 11.409 | 10.901 / 11.285 | 10.858 / 11.238 | 10.835 / 11.216 | 10.805 / 11.206 | 10.788 / 11.212 | 10.768 / 11.238 |

## Total (option LT)

Chosen on 2024-25: WT 1.0, KT 0.24. Chosen on 2025-26: WT 0.75, KT 0.24. Ship parameters (both seasons): WT 1.0, KT 0.24.

| Scored on | Parameters from | Games | Shipped MAE | Variant MAE | Shipped minus variant | t | Closing line MAE |
|---|---|---|---|---|---|---|---|
| 2025-26 | 2024-25 (1.0, 0.24) | 1321 | 14.972 | 14.929 | +0.044 | +0.42 | 14.499 |
| 2024-25 | 2025-26 (0.75, 0.24) | 1320 | 14.731 | 14.496 | +0.235 | +2.84 | 14.131 |
| **Pooled, out of sample** | | 2641 | 14.852 | 14.713 | +0.139 | **+2.10** | |

Information test against the closing total (does the model know something the line does not), pooled out of sample: variant g -0.275 (t -2.82), shipped g -0.073 (t -0.96).
Over or under the closing total, pooled out of sample: variant 1301-1340 (49.3%), at a 4+ gap 317-360 (46.8%), at 8+ 40-63 (38.8%). Shipped: 1317-1324 (49.9%), 498-549 (47.6%), 140-132 (51.5%).

Grid, MAE on 2024-25 / 2025-26 (shipped 14.7308 / 14.9724):

| WT \ KT | 0.03 | 0.05 | 0.08 | 0.12 | 0.16 | 0.24 |
|---|---|---|---|---|---|---|
| 0.25 | 14.733 / 15.065 | 14.663 / 14.963 | 14.666 / 14.942 | 14.764 / 15.057 | 14.929 / 15.253 | 15.361 / 15.704 |
| 0.5 | 14.728 / 15.123 | 14.619 / 15.004 | 14.569 / 14.920 | 14.583 / 14.897 | 14.629 / 14.952 | 14.803 / 15.139 |
| 0.75 | 14.754 / 15.205 | 14.616 / 15.084 | 14.521 / 14.982 | 14.481 / 14.909 | 14.476 / 14.873 | 14.496 / 14.866 |
| 1.0 | 14.808 / 15.317 | 14.657 / 15.208 | 14.548 / 15.111 | 14.477 / 15.033 | 14.447 / 14.982 | 14.415 / 14.929 |

## This season, with the ship parameters (154 games; a replay, flagged for monitoring)

| | Games | Shipped MAE | Variant MAE | Shipped minus variant | t | Line MAE |
|---|---|---|---|---|---|---|
| Margin | 154 | 11.673 | 11.426 | +0.248 | +2.09 | 11.084 |
| Total | 154 | 14.783 | 14.885 | -0.101 | -0.36 | 14.26 |

Spread record at the locked line: shipped 68-85 (44.4%), variant 69-85 (44.8%); at a 5+ gap 12-4 (75.0%) and 4-3 (57.1%). Total: average miss (model minus final) shipped +0.09, variant +1.83; over or under the last look, shipped 76-78 (49.4%), variant 67-87 (43.5%).

## Verdict

- **Margin: GO (for accuracy).** Bar: pooled out-of-sample t 3.0, closer in each fold and on this season, information test not worse by more than 1.
- **Total: NO-GO.** Bar: pooled out-of-sample t 2.5, closer in each fold and on this season.
- A GO here is a more accurate Vault line. It is not an edge: read the spread and over/under records above, which stay at a coin flip.
- `game_model.json` is unchanged by this script. Shipping is its own pull request (the daily state build has no closing lines today).

## Notes

- Margin: both seasons chose the same parameters on their own (W 0.75, KL 0.16), so the fold "2025-26 parameters on 2024-25" is numerically the 2024-25 fit round 3 reported as in sample. What the cross-fit adds is that 2025-26 picks that point without seeing 2024-25.
- Total: the line-taught total is closer on average (14.852 to 14.713) and in both folds, but short of the bar (t 2.1) and worse this season, and against the closing total it leans the wrong way (information test t -2.82). Option LT stays off.

**Flagged for close monitoring** (replays, n = 154): margin MAE 11.673 to 11.426; spread record at the locked line 68-85 to 69-85; at a 5+ gap 12-4 to 4-3.
