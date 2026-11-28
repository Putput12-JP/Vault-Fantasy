# Game model: garbage-time capping, results

Generated 2026-11-19T18:05Z by `nba/scripts/test_garbage_time.py`. Rules, committed before this ran: [garbage-time-prereg.md](garbage-time-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters, no retune.

G1 cap chosen on the tune seasons: 25 points. Tune margin MAE by cap: None: 10.5252, 10: 10.7834, 12: 10.7152, 15: 10.6468, 20: 10.5804, 25: 10.5512.
G2: 1846 games reach the garbage-time state in the play-by-play (2023-24 to 2025-26).

## G1 (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.921 | 0.009 | 0.023 | 0.4 |
| 2026 | 1322 | 11.288 | 11.346 | 0.057 | 0.029 | 1.96 |
| pooled | 2643 | 11.1 | 11.134 | 0.033 | 0.019 | 1.77 |
| exploratory: |margin| >= 27 | 281 | 26.824 | 27.563 | 0.739 | 0.058 | 12.81 |
| exploratory: the rest | 2362 | 9.23 | 9.179 | -0.051 | 0.018 | -2.76 |

Against the close: {'variant': {'model': 11.134, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.082, 'g_model_gap': 0.139, 'g_se': 0.106, 't': 1.32}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## G2 (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.902 | -0.01 | 0.022 | -0.47 |
| 2026 | 1322 | 11.288 | 11.27 | -0.018 | 0.023 | -0.77 |
| pooled | 2643 | 11.1 | 11.086 | -0.014 | 0.016 | -0.86 |
| exploratory: |margin| >= 27 | 281 | 26.824 | 26.641 | -0.183 | 0.052 | -3.54 |
| exploratory: the rest | 2362 | 9.23 | 9.236 | 0.006 | 0.016 | 0.38 |

Against the close: {'variant': {'model': 11.087, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.144, 'g_se': 0.092, 't': 1.56}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| G1, margin capped at 25 | +1.77 (worse) | both worse (+0.009, +0.057) | 1.32 vs 1.23 | **NO-GO** |
| G2, margin frozen at garbage time | -0.86 (better, not significant) | both better (-0.010, -0.018) | 1.56 vs 1.23 | **NO-GO** (t below 2) |

## Reading it

- **Capping hurts.** On the tune seasons every cap was worse than no cap (10.525 uncapped, 10.551 at 25, 10.783 at 10), so the chosen cap is just the mildest one on the grid. The test seasons agree: pooled MAE 11.100 to 11.134. Big margins carry real information about team strength, and clipping them throws it away.
- **G2, the cleaner definition, is a small non-significant gain.** 11.100 to 11.086 (t -0.86), same direction in both seasons, and the information test against the close ticks up (1.56 vs 1.23, still under 2). Only about 600 games a season reach the garbage-time state (614, 605 and 628 in the three seasons with play-by-play), and the first test season's ratings are built partly from 2021-22 and 2022-23 games where G2 had no data. A fully consistent run would need play-by-play for those seasons.
- **The blowout/rest split is exploratory and mostly mechanical.** The |margin| >= 26 games were chosen by their final margin, so G1 looks terrible there by construction (it learns less from the very games it is then scored against). G2 improves that group (26.82 to 26.64) and leaves the rest unchanged (9.230 to 9.236), which is the pattern you would hope for, but it carries no verdict.
- **Nothing ships.** `game_model.json`, the Slate and the Game Picks record are unchanged.

## If you want to pursue G2

Fetch 2021-22 and 2022-23 play-by-play so the whole history uses the same definition, pre-register the ladder as is, and rerun once. At the current effect size (-0.014 points, SE 0.016) it would need a much larger sample to reach t 2, so I would not expect it to clear the bar.
