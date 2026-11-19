# Game model: longer-history RAPM prior, results

Generated 2026-11-19T18:51Z by `nba/scripts/test_rapm_history.py`. Rules, committed before this ran: [rapm-history-prereg.md](rapm-history-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Stints, 2021-22 to 2025-26: 6518 of 6604 games kept (79 dropped for a substitution that did not match the floor, 7 without five starters per team).

Chosen on 2022-23 and 2023-24 (games from 28 days in, n=2233; shipped tune MAE 10.5761): LO = {D 0.5, lambda 3000.0, C 1.0, tune MAE 10.5784}, LB = {D 0.5, lambda 3000.0, LAM 0.5, tune MAE 10.5673}.

Tune MAE by cell: LO|D=0.5|lam=3000.0|x=0.5: 10.6208, LO|D=0.5|lam=3000.0|x=0.75: 10.5928, LO|D=0.5|lam=3000.0|x=1.0: 10.5784, LO|D=0.5|lam=10000.0|x=0.5: 10.6657, LO|D=0.5|lam=10000.0|x=0.75: 10.645, LO|D=0.5|lam=10000.0|x=1.0: 10.6282, LO|D=0.7|lam=3000.0|x=0.5: 10.6154, LO|D=0.7|lam=3000.0|x=0.75: 10.5906, LO|D=0.7|lam=3000.0|x=1.0: 10.5791, LO|D=0.7|lam=10000.0|x=0.5: 10.6601, LO|D=0.7|lam=10000.0|x=0.75: 10.6383, LO|D=0.7|lam=10000.0|x=1.0: 10.6217, LO|D=0.85|lam=3000.0|x=0.5: 10.6122, LO|D=0.85|lam=3000.0|x=0.75: 10.5899, LO|D=0.85|lam=3000.0|x=1.0: 10.5827, LO|D=0.85|lam=10000.0|x=0.5: 10.6565, LO|D=0.85|lam=10000.0|x=0.75: 10.6341, LO|D=0.85|lam=10000.0|x=1.0: 10.6185, LO|D=1.0|lam=3000.0|x=0.5: 10.6097, LO|D=1.0|lam=3000.0|x=0.75: 10.5888, LO|D=1.0|lam=3000.0|x=1.0: 10.5862, LO|D=1.0|lam=10000.0|x=0.5: 10.6532, LO|D=1.0|lam=10000.0|x=0.75: 10.6307, LO|D=1.0|lam=10000.0|x=1.0: 10.616, LB|D=0.5|lam=3000.0|x=0.5: 10.5673, LB|D=0.5|lam=3000.0|x=1.0: 10.5723, LB|D=0.5|lam=3000.0|x=2.0: 10.6384, LB|D=0.5|lam=10000.0|x=0.5: 10.571, LB|D=0.5|lam=10000.0|x=1.0: 10.5687, LB|D=0.5|lam=10000.0|x=2.0: 10.5776, LB|D=0.7|lam=3000.0|x=0.5: 10.5678, LB|D=0.7|lam=3000.0|x=1.0: 10.5773, LB|D=0.7|lam=3000.0|x=2.0: 10.6597, LB|D=0.7|lam=10000.0|x=0.5: 10.5708, LB|D=0.7|lam=10000.0|x=1.0: 10.5691, LB|D=0.7|lam=10000.0|x=2.0: 10.5861, LB|D=0.85|lam=3000.0|x=0.5: 10.5684, LB|D=0.85|lam=3000.0|x=1.0: 10.5812, LB|D=0.85|lam=3000.0|x=2.0: 10.676, LB|D=0.85|lam=10000.0|x=0.5: 10.5708, LB|D=0.85|lam=10000.0|x=1.0: 10.57, LB|D=0.85|lam=10000.0|x=2.0: 10.5934, LB|D=1.0|lam=3000.0|x=0.5: 10.5688, LB|D=1.0|lam=3000.0|x=1.0: 10.5844, LB|D=1.0|lam=3000.0|x=2.0: 10.6903, LB|D=1.0|lam=10000.0|x=0.5: 10.5708, LB|D=1.0|lam=10000.0|x=1.0: 10.5708, LB|D=1.0|lam=10000.0|x=2.0: 10.6003.

## LO (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 1.0, 'mae': 10.578357987703912}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.927 | 0.014 | 0.038 | 0.38 |
| 2026 | 1322 | 11.288 | 11.265 | -0.023 | 0.04 | -0.58 |
| pooled | 2643 | 11.1 | 11.096 | -0.004 | 0.029 | -0.15 |

Against the close: {'variant': {'model': 11.096, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.071, 'g_model_gap': 0.132, 'g_se': 0.097, 't': 1.36}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## LB (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 0.5, 'mae': 10.567321293643614}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.91 | -0.002 | 0.013 | -0.14 |
| 2026 | 1322 | 11.288 | 11.287 | -0.001 | 0.013 | -0.11 |
| pooled | 2643 | 11.1 | 11.099 | -0.002 | 0.009 | -0.17 |

Against the close: {'variant': {'model': 11.099, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.066, 'g_model_gap': 0.119, 'g_se': 0.094, 't': 1.27}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## LO at D 0.5 (exploratory) (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 1.0, 'mae': 10.578357987703912}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.927 | 0.014 | 0.038 | 0.38 |
| 2026 | 1322 | 11.288 | 11.265 | -0.023 | 0.04 | -0.58 |
| pooled | 2643 | 11.1 | 11.096 | -0.004 | 0.029 | -0.15 |

Against the close: {'variant': {'model': 11.096, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.071, 'g_model_gap': 0.132, 'g_se': 0.097, 't': 1.36}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## LB at D 0.5 (exploratory) (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 0.5, 'mae': 10.567321293643614}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.91 | -0.002 | 0.013 | -0.14 |
| 2026 | 1322 | 11.288 | 11.287 | -0.001 | 0.013 | -0.11 |
| pooled | 2643 | 11.1 | 11.099 | -0.002 | 0.009 | -0.17 |

Against the close: {'variant': {'model': 11.099, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.066, 'g_model_gap': 0.119, 'g_se': 0.094, 't': 1.27}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| LO, RAPM replaces (D 0.5, lambda 3000, C 1.0) | -0.15 | no (+0.014, -0.023) | 1.36 vs 1.23 | **NO-GO** |
| LB, RAPM added (D 0.5, lambda 3000, LAM 0.5) | -0.17 | yes (-0.002, -0.001) | 1.27 vs 1.23 | **NO-GO** (t far below 2) |

The two exploratory runs at D 0.5 are the same cells as the chosen ones, because the tuner picked D 0.5 for both.

## Reading it

- **More history did not help.** Margin MAE is 11.100 shipped against 11.096 (LO) and 11.099 (LB); SEs are 0.029 and 0.009. Five seasons of stints is no better than the three used in PR 512 (which were 11.108 and 11.108).
- **The tuner wanted the shortest memory.** Both variants chose a yearly decay of 0.5, the bottom of the grid. On the two tune seasons, best MAE by decay for LO: 0.5 = 10.578, 0.7 = 10.579, 0.85 = 10.583, 1.0 = 10.586; for LB: 10.567, 10.568, 10.568, 10.569; shipped is 10.576. The more old seasons count, the worse, so the data say players change too fast for a long RAPM prior to help.
- **LB's tune gain is 0.009 points** (10.567 against 10.576) with LAM at the lowest value on the grid, the tuner asking for as little RAPM as it could. On the test seasons it is zero.
- **Stints are sound.** 6,518 of 6,604 games rebuilt for 2021-22 to 2025-26 (79 dropped for a substitution that did not match the floor, 7 without five starters per team).
- **What this does not test.** An informative prior (draft slot, age, box-score rates) rather than a prior of zero, and separate offense and defense coefficients. Those are separate registrations and, given this series, I would not expect a different outcome for the injury adjustment.
- **Nothing ships.** `game_model.json`, the Slate and the Game Picks record are unchanged.
