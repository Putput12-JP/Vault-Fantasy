# Game-model experiments: results

Generated 2026-10-13T14:34Z by `nba/scripts/backtest_total_anchor.py` and, when present, `retune_game_model.py`.
Rules, committed before either run: `nba/docs/game-model-experiments.md`.

## Experiment A — sportsbook opening total as the Kalshi ladder anchor

**Verdict: NO-GO.** a time half is not positive

The anchor is the DraftKings opening total, else ESPN BET. The close is not used. Pinnacle's tape on
`nba-data` starts 2026-09-30 and covers none of these seasons. The distribution is a normal centered on
that open, sigma 18.09 (tune opening-total MAE * sqrt(pi/2), seasons 2024).

Sigma sample: 1316 tune games, residual MAE 14.433, mean actual−open +0.176 (not used to shift the center).

Opening-total coverage by season (a tune season under 80% is dropped from sigma):

| Season | Games | With an open total | Share |
|---|---|---|---|
| 2023 | 1320 | 0 | 0.0% |
| 2024 | 1319 | 1316 | 99.8% |
| 2025 | 1321 | 1321 | 100.0% |
| 2026 | 1322 | 1321 | 99.9% |

Common set: 11,429 strikes in 1,300 games that have both a 1pm Kalshi price and an opening total.
All Kalshi total strikes passing the usual filters, including games with no open: 11,437 in 1,301 games.

### Brier (lower is better)

| Set | Strikes | Anchor | Shipped model | Kalshi 1pm | Price-only (2nd half, fit on the 1st) |
|---|---|---|---|---|---|
| all | 11437 | — | 0.2189 | 0.2151 | — |
| common | 11429 | 0.2139 | 0.2188 | 0.2151 | — |
| common 1st half | 5714 | 0.2171 | 0.2244 | 0.2194 | — |
| common 2nd half | 5715 | 0.2106 | 0.2133 | 0.2107 | 0.2127 |

### ROI after fees, one contract per strike

ROI is profit / dollars risked. z is game-clustered. The decision uses the 8% row only.

| Edge | Anchor: strikes, games, ROI, z | Model | Price-only (2nd half only) |
|---|---|---|---|
| 4%+ | 5042, 1072g, +3.5%, z 3.63 | 7170, 1173g, +1.7%, z 2.59 | 2278, 552g, -11.8%, z -2.30 |
| 8%+ | 1604, 496g, +9.9%, z 3.92 | 3976, 816g, +2.0%, z 3.00 | — |
| 12%+ | 483, 222g, +32.8%, z 4.96 | 1934, 479g, +4.2%, z 3.95 | — |

Profit per contract and equal-dollar-stake ROI are not the decision. They are here so the two
conventions in the repo can both be read off the 8% bucket.

| 8%+ | Profit per contract | Equal-stake ROI | One-contract ROI |
|---|---|---|---|
| Anchor, all | +0.0396 | +18.8% | +9.9% |
| Anchor, 1st half | +0.0722 | +31.2% | +18.0% |
| Anchor, 2nd half | -0.0135 | -1.6% | -3.4% |
| Model, all | +0.0091 | +7.1% | +2.0% |
| Model, 2nd half | +0.0228 | +8.1% | +4.9% |
| Price-only, 2nd half | — | — | — |

### Both halves at 8%, and the two sides

| Slice | Anchor | Model |
|---|---|---|
| 1st half | 995, 334g, +18.0%, z 4.13 | 1960, 502g, -1.2%, z 2.82 |
| 2nd half | 609, 162g, -3.4%, z 0.57 | 2016, 314g, +4.9%, z 1.15 |
| 2nd half YES | 179, 62g, +9.2%, z 1.37 | 1444, 211g, +5.5%, z 1.48 |
| 2nd half NO | 430, 105g, -8.8%, z -0.43 | 572, 111g, +3.5%, z 0.01 |

Price-only coefficient fit on the first half: a = -0.111, w = 0.858.

Drift, descriptive only: on games where the 1pm ladder crosses 50%, the interpolated strike minus the
opening total averages +0.18 points (MAE 2.04, 1293 games).


The shipped model on every Kalshi total strike, not just games with an opening total, is the
reproduction of the ladder already in `game-model.md`. It is a check that this run sees the same
tape, not a second verdict.

| | This run | Written 2026-09-30 |
|---|---|---|
| Strikes / games | 11437 / 1301 | 11447 / 1301 |
| Brier model / 1pm / pre-tip | 0.2189 / 0.2151 / 0.2109 | 0.2188 / 0.2150 / 0.2108 |
| 8%+ strikes, games, ROI | 3982, 817, +1.9% | 3987, 817, +1.9% |

The September half table is a different column. Its +19.3% and +8.1% are ROI per game (each game's mean
return on stake, then the mean across games), which is the mean inside the z above, not profit divided by
dollars. On this tape the model's ROI per game at 8% is +19.5% then +7.9%, z 2.82 then 1.15. The decision uses the one-contract ROI, the column that was about +2%.

Price-only's largest gap versus the 1pm price on the second half is 0.054. Where that is under 0.08, the 8% and 12% price-only rows are empty and the GO test treats that baseline as ROI 0.

## Experiment B — widened grids, and C on the injury report

**Verdict: NOT SHIPPED.** neither spread nor total improved by 2 SE (t -1.45, 1.51); CT is not 0, and the paper bot stops trading NBA totals when CT is not 0

### The edge check

Shipped parameters on an endpoint of the old grid: K, REP, CT, ALPHA.
The four named in the rules are K, REP, ALPHA, CT. All four are on that edge.

### Did the tune seasons have a 1pm report?

A season counts when 80% of its game dates have a snapshot at or before 1pm. C is retuned on the
report only when both tune seasons count.

| Season | Game dates | With a 1pm-or-earlier report | Share |
|---|---|---|---|
| 2023 | 212 | 211 | 99.5% |
| 2024 | 208 | 207 | 99.5% |

C objective: **1pm injury report, tune games on a covered date.**

Test-season games with a 1pm-or-earlier report (spread MAE and the margin Briers need 80%):

| Season | Games | Covered | Share |
|---|---|---|---|
| 2025 | 1321 | 1316 | 99.6% |
| 2026 | 1322 | 1319 | 99.8% |

### Parameters

| Param | Shipped | After the widened search | On the new edge? |
|---|---|---|---|
| K | 0.04 | 0.03 |  |
| CARRY | 0.5 | 0.6 |  |
| C | 0.5 | 0.5 |  |
| REP | 0.4 | 0.4 |  |
| B2B | 2.0 | 2.0 |  |
| KP | 0.05 | 0.05 |  |
| CT | 0.0 | 0.2 |  |
| ALPHA | 0.06 | 0.06 |  |

Tune-season oracle MAE is the search objective (in sample, not the ship test).

| | Margin | Total |
|---|---|---|
| Shipped | 10.525 | 14.606 |
| Widened | 10.510 | 14.593 |

### Test seasons: MAE and Kalshi 1pm Brier

MAE is points, mean absolute error on the paired games that have a closing spread. Brier is
strike-weighted, the same average the existing Kalshi table uses; t is the paired difference of
each game's mean squared error, so a long ladder counts as one game. Positive t means the widened
parameters are closer. "Not measured" fails the ship rule.

| Metric | Shipped | Widened | Games | t |
|---|---|---|---|---|
| Spread MAE, 1pm report | 11.163 | 11.184 | 2632 | -1.45 |
| Total MAE | 14.839 | 14.811 | 2632 | 1.51 |
| Kalshi 1pm Brier, moneyline | 0.2056 | 0.2065 | 1395 | -1.88 |
| Kalshi 1pm Brier, spread ladder | 0.1907 | 0.1917 | 1301 | -1.84 |
| Kalshi 1pm Brier, total ladder | 0.2189 | 0.2182 | 1301 | 1.97 |

Total MAE and the total-ladder Brier improved. Monitor closely: neither t reached 2, and the spread, moneyline and spread ladder moved the other way. The candidate was not shipped.

### Paper bot

Not shipped, so the bot's inputs do not change. Had these parameters shipped, the daily model state would rebuild ratings from K, CARRY, CT and sigma from the new tune MAE. The candidate CT is not 0. Shipping it would make `nba_total.py` refuse every NBA total, because that bot does not read injury reports. It was not shipped.

