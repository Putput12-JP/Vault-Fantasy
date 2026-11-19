# Game model: stint RAPM and garbage time, results

Generated 2026-11-19T18:32Z by `nba/scripts/test_rapm.py`. Rules, committed before this ran: [rapm-prereg.md](rapm-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Stint validity: 3904 of 3961 games kept (55 dropped for a substitution that did not match the floor, 2 without five starters per team). Correlation of stint-derived minutes with box-score minutes: 0.9975 over 16658 player-games.

Chosen on 2023-24 (games from 28 days in, n=1118; shipped tune MAE 11.0922): AO = {'lam': 3000.0, 'x': 1.0}, AB = {'lam': 10000.0, 'x': 2.0}, GO = {'lam': 3000.0, 'x': 1.0}, GB = {'lam': 10000.0, 'x': 2.0}.

Tune MAE: AO|lam=3000.0|x=0.5: 11.1099, AO|lam=3000.0|x=0.75: 11.0923, AO|lam=3000.0|x=1.0: 11.0868, AO|lam=10000.0|x=0.5: 11.1447, AO|lam=10000.0|x=0.75: 11.1349, AO|lam=10000.0|x=1.0: 11.1294, AB|lam=3000.0|x=0.5: 11.0774, AB|lam=3000.0|x=1.0: 11.0715, AB|lam=3000.0|x=2.0: 11.0907, AB|lam=10000.0|x=0.5: 11.0835, AB|lam=10000.0|x=1.0: 11.0763, AB|lam=10000.0|x=2.0: 11.068, GO|lam=3000.0|x=0.5: 11.1074, GO|lam=3000.0|x=0.75: 11.0896, GO|lam=3000.0|x=1.0: 11.0848, GO|lam=10000.0|x=0.5: 11.1433, GO|lam=10000.0|x=0.75: 11.1329, GO|lam=10000.0|x=1.0: 11.1267, GB|lam=3000.0|x=0.5: 11.0771, GB|lam=3000.0|x=1.0: 11.0713, GB|lam=3000.0|x=2.0: 11.0897, GB|lam=10000.0|x=0.5: 11.0834, GB|lam=10000.0|x=1.0: 11.076, GB|lam=10000.0|x=2.0: 11.0678.

Variants: A = all stints, G = garbage stints removed; O = replace the player value, B = add to it.

## AO (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.938 | 0.026 | 0.039 | 0.67 |
| 2026 | 1322 | 11.288 | 11.277 | -0.011 | 0.041 | -0.27 |
| pooled | 2643 | 11.1 | 11.108 | 0.008 | 0.03 | 0.26 |

Against the close: {'variant': {'model': 11.108, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.073, 'g_model_gap': 0.14, 'g_se': 0.097, 't': 1.44}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## AB (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.913 | 0.001 | 0.024 | 0.05 |
| 2026 | 1322 | 11.288 | 11.303 | 0.015 | 0.027 | 0.54 |
| pooled | 2643 | 11.1 | 11.108 | 0.008 | 0.018 | 0.43 |

Against the close: {'variant': {'model': 11.109, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.064, 'g_model_gap': 0.108, 'g_se': 0.092, 't': 1.17}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## GO (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.933 | 0.021 | 0.04 | 0.52 |
| 2026 | 1322 | 11.288 | 11.272 | -0.016 | 0.041 | -0.39 |
| pooled | 2643 | 11.1 | 11.103 | 0.002 | 0.03 | 0.08 |

Against the close: {'variant': {'model': 11.103, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.075, 'g_model_gap': 0.15, 'g_se': 0.097, 't': 1.55}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## GB (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.912 | 0.0 | 0.025 | 0.01 |
| 2026 | 1322 | 11.288 | 11.301 | 0.013 | 0.027 | 0.46 |
| pooled | 2643 | 11.1 | 11.107 | 0.006 | 0.019 | 0.34 |

Against the close: {'variant': {'model': 11.107, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.064, 'g_model_gap': 0.111, 'g_se': 0.092, 't': 1.2}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| AO, RAPM replaces, all stints (lambda 3000, C 1.0) | +0.26 (worse) | no (+0.026, -0.011) | 1.44 vs 1.23 | **NO-GO** |
| AB, RAPM added, all stints (lambda 10000, LAM 2) | +0.43 (worse) | no (+0.001, +0.015) | 1.17 vs 1.23 | **NO-GO** |
| GO, replaces, garbage removed | +0.08 | no (+0.021, -0.016) | 1.55 vs 1.23 | **NO-GO** |
| GB, added, garbage removed | +0.34 (worse) | no (0.000, +0.013) | 1.20 vs 1.23 | **NO-GO** |

## Reading it

- **Nothing moves.** All four variants sit within 0.01 points of the shipped margin MAE (11.100 to 11.102 to 11.108) with SEs of 0.02 to 0.03. RAPM, built from real lineups with teammates and opponents adjusted, tells the injury adjustment nothing that the game-score value does not already.
- **The tuning gain did not carry.** On 2023-24 the best added-RAPM cell beat shipped by 0.024 (11.068 against 11.092), and the chosen cell sits on the grid corner (lambda 10000, LAM 2). On the test seasons the same setting is a wash.
- **Garbage time changes almost nothing.** A and G differ by 0.005 or less in every comparison (for example 11.108 against 11.103 for replace, 11.108 against 11.107 for add). That is exploratory and carries no verdict, but it agrees with the earlier garbage-time test.
- **The stints are sound.** 3,904 of 3,961 games rebuilt (55 dropped for a substitution that did not match the floor, 2 without five starters per team); stint points sum to the final score; stint minutes correlate 0.9975 with box-score minutes over 16,658 player-games. So a null here is not a data-plumbing artifact.
- **What this does not rule out.** Only 3 seasons of play-by-play exist on disk, the RAPM is single-coefficient (no separate offense and defense), possessions are approximated by time, and the tune season count is one. A longer history or a better prior (for example last year's RAPM carried at a tuned weight) might help, but nothing here suggests it would clear t 2.
- **Nothing ships.** `game_model.json`, the Slate and the Game Picks record are unchanged.

## What this closes

Together with on/off (PR 508): player-value alternatives to game score in the availability adjustment have now failed in box-score and stint forms. The remaining open lead from this series is shooting luck (PR 509, frozen forward test in PR 510).
