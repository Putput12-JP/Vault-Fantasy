# Target funnel (targets allowed by position): NO-GO

**Date:** 2026-10-05 · **Script:** `scripts/backtest_target_funnel.py`

**Question:** a defense's target funnel (the share of targets it allows to RB / WR / TE, as shown on
statrankings' Magic Sports Breakdown) gets cited as a matchup signal. Does it improve `rec` /
`rec_yd` props beyond the DvP term that already ships?

## Method

- Base = the prop model's own player-autoregressive projection (prop_model.json hyperparameters,
  prior games only).
- Each variant multiplies the base by an opponent term built only from weeks before the game
  (current season), blended with last season as a prior. Shrink `k`, carry `a` and exponent `w` are
  fitted on 2016-2021 and scored on 2022-2025 (44.6k player-games).
- Variants: shipped DvP reproduced exactly, tuned DvP, funnel share, funnel volume (targets allowed
  per game), and tuned DvP + funnel stacked.
- Market check: 1,493 unique settled 2026 Wk 1-4 rec/rec_yd props from `bet_results.json`
  against `line_close`.

## Results

| test | funnel | verdict |
|---|---|---|
| Projection RMSE, 2022-25 holdout | +0.00% to +0.24% (best: RB rec, funnel volume) | noise |
| Stacked on tuned DvP | +0.00% to +0.14% | adds nothing |
| WR (any variant) | fitted weight is ~0 | no signal at all |
| Side picked vs base, skew-adjusted | RB/TE +3 to +5 pts over the base rate | real but small, vs our base |
| **Side picked vs 2026 closing line** | **47.8% (n=203)** | **market already prices it** |

The skew adjustment matters. Projections are means, so an RB's receptions beat the projection only
~35% of the time. A raw "down calls hit 69%" looks like an edge but is mostly that base rate.

## Side finding: the shipped DvP term

On the 2022-25 holdout, the shipped DvP (`clamp(FPA/league, .88, 1.15)` from raw current-season
weeks) **worsens** projection RMSE in every cell, by -0.3% to -1.3%. The fitted version collapses to
a heavily shrunk `w≈0.25`. Against 2026 closing lines it picks the winning side 52.3% (n=926),
54.6% for RB/TE. That's 4 weeks of data and conflicting evidence, so nothing was changed. It's a
candidate for a dedicated shrink-and-damp test.

## Also found

Seasons ≤ 2022 in `nflverse_stats_*.json` spell receiving yards `reyds` and omit the receiving keys
on zero-target games. `build_prop_projections.py` reads only `recyds`, so the rec_yd model trains on
2023+ only. The backtest normalizes this in `_norm()`. The model fix is tracked separately.
