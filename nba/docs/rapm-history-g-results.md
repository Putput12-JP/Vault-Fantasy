# Game model: garbage-time RAPM on five seasons, results

Generated 2026-11-19T19:00Z by `nba/scripts/test_rapm_history_g.py`. Rules, committed before this ran: [rapm-history-g-prereg.md](rapm-history-g-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Stints, 2021-22 to 2025-26: 6518 of 6604 games kept (79 dropped for a substitution that did not match the floor, 7 without five starters per team).

Chosen on 2022-23 and 2023-24 (games from 28 days in, n=2233; shipped tune MAE 10.5761): GLO = {D 0.5, lambda 3000.0, C 1.0, tune MAE 10.5734}, GLB = {D 0.5, lambda 3000.0, LAM 0.5, tune MAE 10.5659}.

Tune MAE by cell: LO|D=0.5|lam=3000.0|x=0.5: 10.6177, LO|D=0.5|lam=3000.0|x=0.75: 10.5888, LO|D=0.5|lam=3000.0|x=1.0: 10.5734, LO|D=0.5|lam=10000.0|x=0.5: 10.6643, LO|D=0.5|lam=10000.0|x=0.75: 10.6431, LO|D=0.5|lam=10000.0|x=1.0: 10.6256, LO|D=0.7|lam=3000.0|x=0.5: 10.6133, LO|D=0.7|lam=3000.0|x=0.75: 10.5871, LO|D=0.7|lam=3000.0|x=1.0: 10.5749, LO|D=0.7|lam=10000.0|x=0.5: 10.6596, LO|D=0.7|lam=10000.0|x=0.75: 10.6369, LO|D=0.7|lam=10000.0|x=1.0: 10.6201, LO|D=0.85|lam=3000.0|x=0.5: 10.6109, LO|D=0.85|lam=3000.0|x=0.75: 10.5868, LO|D=0.85|lam=3000.0|x=1.0: 10.578, LO|D=0.85|lam=10000.0|x=0.5: 10.656, LO|D=0.85|lam=10000.0|x=0.75: 10.6332, LO|D=0.85|lam=10000.0|x=1.0: 10.6175, LO|D=1.0|lam=3000.0|x=0.5: 10.6088, LO|D=1.0|lam=3000.0|x=0.75: 10.5861, LO|D=1.0|lam=3000.0|x=1.0: 10.5815, LO|D=1.0|lam=10000.0|x=0.5: 10.6524, LO|D=1.0|lam=10000.0|x=0.75: 10.6295, LO|D=1.0|lam=10000.0|x=1.0: 10.6146, LB|D=0.5|lam=3000.0|x=0.5: 10.5659, LB|D=0.5|lam=3000.0|x=1.0: 10.5696, LB|D=0.5|lam=3000.0|x=2.0: 10.6349, LB|D=0.5|lam=10000.0|x=0.5: 10.5706, LB|D=0.5|lam=10000.0|x=1.0: 10.5679, LB|D=0.5|lam=10000.0|x=2.0: 10.5765, LB|D=0.7|lam=3000.0|x=0.5: 10.5665, LB|D=0.7|lam=3000.0|x=1.0: 10.5741, LB|D=0.7|lam=3000.0|x=2.0: 10.6546, LB|D=0.7|lam=10000.0|x=0.5: 10.5703, LB|D=0.7|lam=10000.0|x=1.0: 10.5682, LB|D=0.7|lam=10000.0|x=2.0: 10.5844, LB|D=0.85|lam=3000.0|x=0.5: 10.5672, LB|D=0.85|lam=3000.0|x=1.0: 10.5782, LB|D=0.85|lam=3000.0|x=2.0: 10.6703, LB|D=0.85|lam=10000.0|x=0.5: 10.5704, LB|D=0.85|lam=10000.0|x=1.0: 10.5691, LB|D=0.85|lam=10000.0|x=2.0: 10.5914, LB|D=1.0|lam=3000.0|x=0.5: 10.5677, LB|D=1.0|lam=3000.0|x=1.0: 10.5817, LB|D=1.0|lam=3000.0|x=2.0: 10.6851, LB|D=1.0|lam=10000.0|x=0.5: 10.5703, LB|D=1.0|lam=10000.0|x=1.0: 10.5698, LB|D=1.0|lam=10000.0|x=2.0: 10.598.

## GLO (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 1.0, 'mae': 10.573384253634696}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.921 | 0.009 | 0.038 | 0.25 |
| 2026 | 1322 | 11.288 | 11.264 | -0.025 | 0.041 | -0.61 |
| pooled | 2643 | 11.1 | 11.093 | -0.008 | 0.029 | -0.27 |

Against the close: {'variant': {'model': 11.093, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.072, 'g_model_gap': 0.141, 'g_se': 0.097, 't': 1.46}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## GLB (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 0.5, 'mae': 10.565930335652082}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.908 | -0.004 | 0.013 | -0.3 |
| 2026 | 1322 | 11.288 | 11.285 | -0.003 | 0.014 | -0.22 |
| pooled | 2643 | 11.1 | 11.097 | -0.003 | 0.01 | -0.36 |

Against the close: {'variant': {'model': 11.097, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.066, 'g_model_gap': 0.122, 'g_se': 0.094, 't': 1.29}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## GLO at D 0.5 (exploratory) (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 1.0, 'mae': 10.573384253634696}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.921 | 0.009 | 0.038 | 0.25 |
| 2026 | 1322 | 11.288 | 11.264 | -0.025 | 0.041 | -0.61 |
| pooled | 2643 | 11.1 | 11.093 | -0.008 | 0.029 | -0.27 |

Against the close: {'variant': {'model': 11.093, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.072, 'g_model_gap': 0.141, 'g_se': 0.097, 't': 1.46}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## GLB at D 0.5 (exploratory) (margin MAE, points)

Cell: {'D': 0.5, 'lam': 3000.0, 'x': 0.5, 'mae': 10.565930335652082}.

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.908 | -0.004 | 0.013 | -0.3 |
| 2026 | 1322 | 11.288 | 11.285 | -0.003 | 0.014 | -0.22 |
| pooled | 2643 | 11.1 | 11.097 | -0.003 | 0.01 | -0.36 |

Against the close: {'variant': {'model': 11.097, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.066, 'g_model_gap': 0.122, 'g_se': 0.094, 't': 1.29}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| GLO, RAPM replaces, garbage removed (D 0.5, lambda 3000, C 1.0) | -0.27 | no (+0.009, -0.025) | 1.46 vs 1.23 | **NO-GO** |
| GLB, RAPM added, garbage removed (D 0.5, lambda 3000, LAM 0.5) | -0.36 | yes (-0.004, -0.003) | 1.29 vs 1.23 | **NO-GO** (t far below 2) |

## Reading it

- **Another tie.** Margin MAE 11.100 shipped against 11.093 (GLO) and 11.097 (GLB), SEs 0.029 and 0.010. Neither is anywhere near t 2.
- **Garbage time versus all stints, five seasons (exploratory).** GLO 11.093 against 11.096 for the all-stints LO in PR 516; GLB 11.097 against 11.099. The tune MAE moves in the same direction by a similar amount (10.573 against 10.578 for replace, 10.566 against 10.567 for add). Removing garbage time helps by about 0.003 points, which is noise; it agrees with the three-season result in PR 512.
- **Same chosen cells as PR 516** (decay 0.5, lambda 3000; C 1.0 and LAM 0.5): the tuner still wants the shortest memory and the least RAPM.
- **Nothing ships.** `game_model.json`, the Slate and the Game Picks record are unchanged.

## Process note

A first run of this script reproduced PR 516's numbers to the last digit because the copied script still built the all-stints snapshots. It was caught by the identical results, fixed, and rerun; only the corrected run is reported here.
