# NBA prop correlation audit (model pregame probabilities vs outcomes)

Question: which player-prop markets hit together more or less often than the model's own probabilities say they should, and does using that dependence beat independence on Brier score? **Nothing in the model, the page or `data/` was changed.** Two new read-only scripts: `nba/scripts/prop_corr_extract.py` and `nba/scripts/prop_corr_analyze.py`.

## Bottom line

1. **Only same-player pairs are clearly supported.** Points with rebounds, points with assists, and rebounds with assists each show a correlation of +0.10 to +0.15, the same sign and size in both seasons and in both fit-one-season-score-the-other directions. Independence understates how often two overs hit together by roughly 12% to 16% (relative) on those pairs.
2. **Points with 3-pointers is huge (+0.56) but mechanical.** A made three is three of the points. It is real, it improves Brier by about 0.05 to 0.07 per pair, and it is not a discovery. It is the one pair where independence is badly wrong.
3. **Teammates: two tiny effects hold up, the rest do not.** Assists with 3-pointers (+0.036) and points with assists (+0.022) are positive in both seasons and survive both Brier directions, but the Brier gain is about 0.0001 to 0.0002 per pair, which is nothing you could price on. Points with points (-0.029) is negative in 2024-25 and zero in 2025-26, so it needs more testing.
4. **Opponents: nothing.** Every opponent family is within about 0.01 of zero except points with rebounds (-0.013), which flips size between seasons.
5. **Minutes explain almost all the non-mechanical same-player link.** When a player's actual minutes land within 4 of the projection, same-player correlations fall to about 0.00 to 0.06. They are +0.18 to +0.36 when the player got more than 4 minutes fewer than projected. Pregame spread and realized margin do not show a game-script effect on same-player pairs.

## Data and design (read this before the tables)

- **Probabilities:** the v2 model replayed exactly as `build_prop_model_v2.py` does (same walk, stacker, variance fit, calibration on 2024-25 opening lines). Each leg's pregame over-probability `pm` is paired with the settled result. Market no-vig price `pk` is used as a robustness check; every conclusion below matches in sign.
- **Legs:** ESPN main lines only, points, rebounds, assists and 3-pointers. Pushes dropped. Combo markets (pra, pr, pa, ra) are excluded from pairs because they contain their parts, so their overlap is arithmetic.
- **Seasons:** 2024-25 opening lines (400,888 pairs, 525 games with at least one pair) and 2025-26 pre-tip closing lines (57,244 pairs, 70 to 130 games per family). **The 2024-25 rows are in-sample for the model** (it was fitted on that season); only 2025-26 is out of sample, and it is thin.
- **Dependence measure:** correlation of the two yes/no outcomes after removing each leg's own probability: mean of z1*z2 with z = (outcome - p) / sqrt(p(1-p)). It is 0 under independence whatever the two probabilities are. Standard errors are clustered by game, because every pair in one game shares the same game.
- **Brier:** four-outcome joint Brier (over/over, over/under, under/over, under/under). Independence uses p1*p2 for over/over. The dependence version adds `phi * sqrt(p1 q1 p2 q2)` with phi fitted per family on one season and scored on the other, run both directions, half-size (shrunk) shown. Positive gain means dependence beat independence.
- **Evidence labels (one fixed rule applied to every family; I wrote it after a first look at the correlation table, so the thresholds are judgment calls):** SUPPORTED needs pooled |z| of at least 3, the same sign in both seasons, and a positive half-size Brier gain in both directions. NEEDS TESTING means |z| of at least 2 pooled (or at least 2.5 in one season) but one of those tests failed. Everything else is NO EVIDENCE.
- **26 families are tested.** At |z| of 2 you expect about one false hit per season by chance, so single-season z values between 2 and 3 should not be believed.

## Supported by the data

| Relationship | Pairs | Both over, observed | Both over, independence | Correlation (z) | 2024-25 | 2025-26 | Brier gain x1000 (fit 25 test 26 / fit 26 test 25) |
|---|---|---|---|---|---|---|---|
| Same player: points with 3-pointers | 3,412 | 33.9% | 21.0% | +0.558 (+36.9) | +0.557 | +0.571 | +54.65 / +50.27 |
| Same player: points with rebounds | 4,916 | 25.4% | 22.1% | +0.154 (+10.8) | +0.159 | +0.109 | +2.19 / +2.69 |
| Same player: rebounds with assists | 4,105 | 23.3% | 20.0% | +0.140 (+8.3) | +0.134 | +0.174 | +3.31 / +2.65 |
| Same player: points with assists | 4,093 | 23.8% | 21.2% | +0.098 (+6.2) | +0.100 | +0.080 | +0.81 / +1.16 |
| Teammates: assists with 3-pointers | 18,592 | 20.1% | 19.3% | +0.036 (+5.0) | +0.037 | +0.027 | +0.08 / +0.15 |
| Teammates: points with assists | 27,226 | 21.2% | 21.4% | +0.022 (+3.7) | +0.020 | +0.036 | +0.15 / +0.05 |

"Both over, observed" is the pooled hit rate of the pair; "independence" is the mean of p1*p2 over the same pairs. Averages hide the spread of probabilities, so use the correlation column for the size of the link.

## Needs more testing

| Relationship | Pairs | Both over, observed | Both over, independence | Correlation (z) | 2024-25 | 2025-26 | Brier gain x1000 (fit 25 test 26 / fit 26 test 25) |
|---|---|---|---|---|---|---|---|
| Same player: rebounds with 3-pointers | 3,361 | 22.0% | 19.8% | +0.090 (+5.2) | +0.095 | +0.062 | -0.17 / +0.75 |
| Teammates: points with points | 16,940 | 21.9% | 23.5% | -0.029 (-4.6) | -0.032 | +0.000 | +0.02 / -0.00 |
| Same player: assists with 3-pointers | 2,954 | 21.0% | 19.6% | +0.068 (+3.7) | +0.080 | +0.018 | -0.13 / +0.25 |
| Opponents: points with rebounds | 37,799 | 21.6% | 21.7% | -0.013 (-2.7) | -0.009 | -0.053 | +0.11 / -0.09 |
| Teammates: rebounds with assists | 28,293 | 19.5% | 20.0% | -0.014 (-2.5) | -0.016 | -0.003 | +0.06 / +0.01 |
| Teammates: points with 3-pointers | 21,902 | 19.9% | 21.0% | -0.017 (-2.4) | -0.015 | -0.027 | +0.11 / +0.11 |
| Teammates: assists with assists | 11,345 | 18.5% | 19.5% | -0.019 (-2.3) | -0.016 | -0.034 | +0.14 / +0.13 |
| Teammates: rebounds with 3-pointers | 22,894 | 20.0% | 19.6% | +0.014 (+2.2) | +0.010 | +0.032 | +0.03 / -0.07 |

Why each is here: same-player rebounds with 3-pointers and assists with 3-pointers are strong in 2024-25 (+0.095, +0.080) but 2025-26 is smaller and the Brier gain is negative in one direction (the 2025-26 sample is only about 75 games). Teammate points with points is -0.032 in 2024-25 and 0.000 in 2025-26. The rest are under -0.02 or over +0.014 pooled with half-size Brier gains of about 0.0001, which is at the edge of what this sample can resolve.

## No evidence of dependence

| Teammates: rebounds with rebounds | 17,541 | 20.4% | 20.6% | -0.014 (-1.9) | -0.016 | +0.004 | +0.10 / -0.02 |
| Opponents: rebounds with 3-pointers | 25,342 | 19.8% | 19.6% | -0.011 (-1.9) | -0.013 | -0.003 | +0.02 / +0.01 |
| Opponents: rebounds with assists | 31,159 | 19.7% | 19.8% | -0.009 (-1.6) | -0.008 | -0.014 | +0.03 / +0.02 |
| Opponents: rebounds with rebounds | 19,312 | 21.4% | 20.4% | +0.009 (+1.3) | +0.010 | +0.002 | -0.05 / +0.00 |
| Teammates: points with rebounds | 34,226 | 21.7% | 22.0% | +0.006 (+1.1) | +0.005 | +0.011 | +0.01 / -0.01 |
| Opponents: points with assists | 30,331 | 20.7% | 21.1% | +0.005 (+0.9) | +0.006 | -0.010 | -0.01 / -0.02 |
| Opponents: assists with 3-pointers | 20,611 | 19.2% | 19.1% | +0.004 (+0.6) | +0.006 | -0.004 | -0.00 / -0.00 |
| Opponents: assists with assists | 12,650 | 18.9% | 19.2% | -0.005 (-0.6) | -0.004 | -0.006 | -0.00 / +0.00 |
| Opponents: points with 3-pointers | 24,297 | 20.7% | 20.9% | +0.002 (+0.3) | +0.004 | -0.014 | -0.01 / -0.02 |
| Teammates: 3-pointers with 3-pointers | 7,553 | 18.9% | 19.1% | +0.003 (+0.3) | +0.014 | -0.032 | -0.15 / -0.08 |
| Opponents: 3-pointers with 3-pointers | 8,566 | 19.3% | 18.9% | +0.002 (+0.2) | +0.003 | -0.003 | -0.01 / -0.00 |
| Opponents: points with points | 18,712 | 22.8% | 23.2% | +0.001 (+0.1) | -0.000 | +0.014 | -0.00 / +0.01 |

Nothing here shows a correlation different from zero at the 3-z bar. These are "no evidence", not "proven independent": an effect of 0.01 to 0.02 would not show at these sample sizes.

## Why: shared factors

All slices pool both seasons with model probabilities. Cell format: correlation (pairs, games). Minutes error uses the player's actual minutes against the model's projected minutes, so it is an after-the-fact mechanism check, not a pregame signal.

**Playing time (same player)**

| Relationship | Minutes >4 under projection | Minutes within 4 | Minutes >4 over projection |
|---|---|---|---|
| Same player: points with rebounds | +0.355 (n 953, 444 g) | +0.042 (n 2,432, 582 g) | +0.207 (n 1,531, 518 g) |
| Same player: points with assists | +0.303 (n 764, 390 g) | -0.003 (n 2,019, 568 g) | +0.133 (n 1,310, 495 g) |
| Same player: rebounds with assists | +0.278 (n 791, 397 g) | +0.057 (n 1,978, 562 g) | +0.180 (n 1,336, 488 g) |
| Same player: rebounds with 3-pointers | +0.207 (n 674, 365 g) | -0.004 (n 1,612, 536 g) | +0.156 (n 1,075, 458 g) |
| Same player: assists with 3-pointers | +0.179 (n 573, 318 g) | +0.019 (n 1,428, 525 g) | +0.076 (n 953, 429 g) |
| Same player: points with 3-pointers | +0.571 (n 683, 371 g) | +0.508 (n 1,678, 549 g) | +0.630 (n 1,051, 459 g) |

Reading it: with minutes pinned near the projection, points with rebounds drops from +0.154 to +0.042, points with assists to about 0, rebounds with 3-pointers to about 0. The link is mostly "the player got more or fewer minutes than expected, so every stat moved together", and it is strongest when minutes came in short (early exit, injury, foul trouble, a blowout bench). Points with 3-pointers stays at +0.51 with minutes pinned because it is arithmetic.

**Player role (teammates)**

| Relationship | Both likely starters | One or both bench |
|---|---|---|
| Teammates: points with points | -0.007 (n 5,451, 611 g) | -0.040 (n 11,489, 621 g) |
| Teammates: assists with 3-pointers | +0.058 (n 6,796, 587 g) | +0.022 (n 11,796, 594 g) |
| Teammates: points with assists | +0.046 (n 9,025, 614 g) | +0.009 (n 18,201, 615 g) |
| Teammates: rebounds with assists | +0.001 (n 8,945, 603 g) | -0.022 (n 19,348, 600 g) |

Teammate points with points is negative mainly when a bench player is involved (-0.040 versus -0.007 for two starters), consistent with bench minutes and shots being a shared pool. Assists with 3-pointers and points with assists are stronger between starters, consistent with passer to shooter. These are plausible readings, not proven mechanisms.

**Game script, pregame (teammates)**

| Relationship | Spread <5 | Spread 5-9 | Spread 9+ |
|---|---|---|---|
| Teammates: points with points | -0.029 (n 5,898, 240 g) | -0.023 (n 5,615, 211 g) | -0.036 (n 5,427, 204 g) |
| Teammates: assists with 3-pointers | +0.035 (n 6,812, 214 g) | +0.016 (n 5,869, 198 g) | +0.056 (n 5,911, 188 g) |
| Teammates: points with assists | +0.008 (n 9,707, 228 g) | +0.029 (n 8,871, 212 g) | +0.029 (n 8,648, 193 g) |
| Teammates: rebounds with rebounds | -0.002 (n 6,374, 220 g) | -0.023 (n 5,776, 200 g) | -0.017 (n 5,391, 189 g) |

No consistent gradient with the pregame spread. Game script is not demonstrated by this cut.

**Game script, realized (after the fact)**

| Relationship | Final margin <8 | Margin 8-17 | Margin 18+ |
|---|---|---|---|
| Teammates: points with points | -0.041 (n 5,864, 226 g) | -0.037 (n 6,494, 249 g) | -0.004 (n 4,582, 180 g) |
| Teammates: assists with 3-pointers | +0.033 (n 6,405, 207 g) | +0.031 (n 6,982, 231 g) | +0.045 (n 5,205, 162 g) |
| Teammates: points with assists | +0.011 (n 9,574, 220 g) | +0.019 (n 10,380, 237 g) | +0.039 (n 7,272, 176 g) |
| Same player: points with rebounds | +0.196 (n 1,719, 210 g) | +0.119 (n 1,888, 236 g) | +0.149 (n 1,309, 165 g) |
| Same player: rebounds with assists | +0.140 (n 1,437, 209 g) | +0.136 (n 1,576, 232 g) | +0.143 (n 1,092, 163 g) |
| Opponents: points with rebounds | -0.014 (n 13,349, 220 g) | -0.012 (n 14,456, 250 g) | -0.012 (n 9,994, 170 g) |

Same-player pairs do not strengthen in blowouts. Teammate points with points is weaker in blowouts (-0.004 at 18+ versus about -0.04 otherwise) and teammate points with assists stronger (+0.039 versus +0.011). Both are single exploratory cuts and need a pre-registered test before anyone leans on them.

**Usage:** the starter-role slice above is the only usage proxy here. A usage-share or shot-attempt measure, pace and game total are not in the leg file, so they are untested.

## What this does not cover

- **Pace, game total, usage share, alternate lines and parlay pricing** are not tested. Only main lines, both legs from the same game.
- **Combo markets** were excluded by design, not found independent.
- **2025-26 is a thin out-of-sample season** (about 75 to 130 games per family, 306 games with any settled leg). The 2024-25 half is in-sample for the model, so a model flaw that is symmetric across both stats would not show here.
- **Marginal bias leaks into "both over".** In 2025-26 the model's average over-probability is off by 1 to 4 points (points 2.6 high, rebounds 3.6 low). The correlation measure and the agreement rate are less exposed than the both-over cell, and the market-probability rerun gives the same signs, but treat the both-over columns as approximate.
- **Not a betting result.** Brier gains are a probability-accuracy measure, not edge against any price.
- Consistent with the existing market-based copula work (`docs/copula-fit-results.md`): same player points with rebounds is the strongest non-mechanical family there too, and teammate effects are small.

## Reproduce

```bash
python3 nba/scripts/prop_corr_extract.py legs.json        # ~40 s, replays the v2 model, writes one row per leg
python3 nba/scripts/prop_corr_analyze.py legs.json out.json   # ~15 s
```
