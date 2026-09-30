# NBA game model: backtest

Generated 2026-09-30T02:23Z by `nba/scripts/build_game_model.py`. Walk-forward, out of sample.

Tuned on 2022-23 and 2023-24 (2021-22 warm-up) using who actually sat. Tested on 2024-25 and
2025-26 with the **official injury report as of the bet time** (no hindsight), against real ESPN lines
(DraftKings where available, else ESPN BET).

## Verdict

**Context, not an edge.** Against the closing spread the model adds nothing the line has not priced (t = 1.23). It does beat ESPN's OPENING line, but that open has no timestamp and is often posted before the injury news the model uses. The honest bet-time test (Kalshi prices actually tradeable at 1pm, bottom of this page) is the one that decides. Same outcome as the NFL game model.

## Accuracy (mean absolute error, points; lower is better)

| Season | Games | Model, no injuries | Model, report 30 min pre-tip | Model, report 1pm | Model, hindsight lineups | Open line | Close line |
|---|---|---|---|---|---|---|---|
| 2025 spread | 1320 | 11.114 | 10.907 | 10.98 | 10.908 | 11.005 | 10.636 |
| 2026 spread | 1321 | 11.448 | 11.294 | 11.334 | 11.279 | 11.206 | 11.012 |
| all spread | 2641 | 11.281 | 11.101 | 11.157 | 11.094 | 11.105 | 10.824 |
| 2025 total | 1320 | 14.731 | 14.731 | 14.731 | 14.731 | 14.718 | 14.131 |
| 2026 total | 1321 | 14.972 | 14.972 | 14.972 | 14.972 | 14.698 | 14.499 |
| all total | 2641 | 14.852 | 14.852 | 14.852 | 14.852 | 14.708 | 14.315 |

## Against the spread (both test seasons)

Bet the side the model prefers when it disagrees with the line by at least the threshold.
Break-even at -110 is 52.4%.

| Gap (pts) | vs close, report@tip: bets | win% | ROI | vs open, report@1pm: bets | win% | ROI |
|---|---|---|---|---|---|---|
| 0+ | 2641 | 50.8% | -3.0% | 2641 | 52.4% | 0.1% |
| 1+ | 1926 | 50.5% | -3.6% | 1960 | 53.1% | 1.4% |
| 2+ | 1323 | 49.7% | -5.2% | 1352 | 54.2% | 3.5% |
| 3+ | 820 | 51.5% | -1.8% | 889 | 54.4% | 3.9% |
| 4+ | 491 | 49.7% | -5.1% | 555 | 56.6% | 8.0% |
| 5+ | 279 | 47.3% | -9.7% | 321 | 59.2% | 13.0% |

## Totals (both test seasons)

| Gap (pts) | vs close: bets | win% | vs open: bets | win% |
|---|---|---|---|---|
| 0+ | 2641 | 49.9% | 2641 | 53.0% |
| 2+ | 1789 | 49.9% | 1724 | 53.0% |
| 4+ | 1047 | 47.6% | 999 | 56.0% |
| 6+ | 574 | 48.3% | 521 | 58.2% |
| 8+ | 272 | 51.5% | 272 | 59.9% |

## Does the model know anything the line does not?

Regression: result = a + b x line + g x (model - line). If g is not clearly above 0 (t < 2), the model adds
nothing the market has not already priced.

- spread vs close: g = 0.118 (SE 0.096, t = 1.23), n = 2641
- spread vs open (1pm report): g = 0.524 (SE 0.086, t = 6.06), n = 2641
- total vs close: g = -0.073 (SE 0.076, t = -0.96), n = 2641

## Fitted parameters

K 0.04 (rating step), CARRY 0.5 (season carryover), C 0.5 (spread pts per unit of missing value),
CT 0.0 (total pts per unit), REP 0.4 (replacement game score per minute), B2B 2.0 pts,
ALPHA 0.06 (player form smoothing), KP 0.05 (scoring step). Home court 1.7 pts.

Injury status play rates (measured): {'Probable': 0.845, 'Questionable': 0.477, 'Doubtful': 0.023}

## Honest bet-time test: model at 1pm vs the Kalshi price at 1pm (moneyline)

`nba/scripts/backtest_game_vs_kalshi.py`. 2,790 team-sides with a Kalshi trade before 1pm ET and before tip.
Win% = Phi(margin / 13.2), sigma from the tune seasons only.

Brier score (lower is better): model 0.2057, Kalshi 1pm 0.2008, Kalshi pre-tip 0.1991.

Best blend of Kalshi 1pm + model: weight on model 0.20 (Brier 0.2006). Weight 0 = the model adds nothing.

| Model edge vs 1pm price | Bets | Win% | Avg price | ROI after fees | CLV: pre-tip moved toward model |
|---|---|---|---|---|---|
| 2%+ | 1028 | 38.7% | 0.37 | -0.4% | 540 toward / 471 away |
| 4%+ | 783 | 36.8% | 0.36 | -3.1% | 413 toward / 359 away |
| 6%+ | 569 | 36.7% | 0.35 | -0.4% | 303 toward / 258 away |
| 8%+ | 408 | 35.8% | 0.34 | +1.1% | 218 toward / 183 away |
| 10%+ | 283 | 32.9% | 0.32 | -2.2% | 158 toward / 119 away |

Each game has two sides; a bet is a YES buy on the side the model rates higher than its 1pm price.


**Verdict:** moneyline no edge; spread ladder unstable (flips sign between halves, NO-GO); total ladder
positive in both halves and on both sides but the 2nd half alone is not 2 SE, and per CONTRACT (equal stake on
every strike) it is only about +2% (WATCH, marginal). The per-game ROI below weights cheap long-shot contracts
heavily, so it reads much bigger than the money result. Likely mechanism: thin Kalshi total ladders drift from
the sportsbook number at 1pm; test live against Pinnacle before betting.

### Spread ladder (Kalshi, 1pm)

12,657 strikes across 1,301 games. Brier: model 0.1908, Kalshi 1pm 0.1885, pre-tip 0.1860.

| Model edge (either side) | Strikes | Games | ROI after fees | CLV toward / away |
|---|---|---|---|---|
| 4%+ | 7228 | 1220 | +2.3% | 3753 / 3017 |
| 8%+ | 3635 | 805 | +3.2% | 1878 / 1550 |
| 12%+ | 1640 | 454 | +5.6% | 833 / 731 |

YES hit rate 0.349 vs average price 0.338 (no gap = no overs bias here).

| Split (8%+ edge) | Model: strikes, games, ROI/game, z | Model YES side | Model NO side | Always NO |
|---|---|---|---|---|
| 1st half | 1765, 527, +14.6%, 2.56 | 492, 230, +16.4%, 1.24 | 1273, 482, +14.3%, 2.69 | 6328, 824, +1.3%, 0.72 |
| 2nd half | 1870, 278, -6.6%, -0.92 | 590, 163, +0.3%, 0.02 | 1280, 255, -10.8%, -1.79 | 6329, 479, -9.7%, -4.51 |

### Total ladder (Kalshi, 1pm)

11,447 strikes across 1,301 games. Brier: model 0.2188, Kalshi 1pm 0.2150, pre-tip 0.2108.

| Model edge (either side) | Strikes | Games | ROI after fees | CLV toward / away |
|---|---|---|---|---|
| 4%+ | 7185 | 1174 | +1.7% | 3813 / 3017 |
| 8%+ | 3987 | 817 | +1.9% | 2160 / 1617 |
| 12%+ | 1937 | 480 | +4.1% | 1065 / 770 |

YES hit rate 0.512 vs average price 0.513 (no gap = no overs bias here).

| Split (8%+ edge) | Model: strikes, games, ROI/game, z | Model YES side | Model NO side | Always NO |
|---|---|---|---|---|
| 1st half | 1966, 503, +19.3%, 2.79 | 758, 204, +33.1%, 2.45 | 1208, 341, +24.8%, 2.59 | 5723, 749, +3.7%, 1.05 |
| 2nd half | 2021, 314, +8.1%, 1.17 | 1449, 211, +13.3%, 1.51 | 572, 111, +0.1%, 0.01 | 5724, 553, -9.9%, -2.64 |