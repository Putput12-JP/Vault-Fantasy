# Minutes: left tail (quantile minutes), results

Rule registered first in [minutes-left-tail.md](minutes-left-tail.md) (commit e95557439). Script `test_minutes_tail.py`, numbers `data/minutes_tail.json`. Nothing here changes pricing.

**Verdict: fails the rule as registered (items 1, 2, 3 and 4 fail; 5 passes). Nothing to promote.** Two of the failures are by a hair, and the stat-level result is real but small. Detail below, with no re-scoring of the rule.

Holdout: 13978 played rows in 656 games (odd game ids); fit half 13821 rows (even); tail model trained on 80397 rows from 2023 to 2025.

| Item | Point (GP + fit-half spread) | Tail (quantile) | Rule | Result |
|---|---|---|---|---|
| 1. Share of actual minutes under q10 / q25 / q50 / q75 / q90 | 10.3 / 25.5 / 50.2 / 75.5 / 90.0 | 10.5 / 26.4 / 52.0 / 76.7 / 91.1 | each within 2 points | **fail**: q50 is 52.01%, 0.01 points past the limit |
| 2. Minutes pinball loss (19 levels) | 1.7436 | 1.7407 | gain with t of 3+ | **fail**: gain 0.0053, t 1.91 |
| 3. Predicted share under 40% of GP minutes (actual 5.9%) | 3.5% | 4.2% | within 1.5 points | **fail**: 1.7 points short |
| 4. Props log loss, all lines | 0.6136 | 0.6128 | gain with t of 3+, no stat worse | **fail**: gain 0.0009, t 3.60; 3pm is worse by 0.000001 |
| 5. Mean of the 19 values minus actual | +0.09 | +0.28 | within 0.5 | pass |

Props log loss by stat (point, tail): pts 0.6746, 0.6729; reb 0.6404, 0.6397; ast 0.6083, 0.6074; 3pm 0.5311, 0.5311. Dispersion (phi) fell for every stat once the distribution carried the minutes uncertainty (for example points 0.29 to 0.17).

## What the data says, as context

- **The tail model helps exactly where it should.** On the 831 holdout rows where the player left early (under 40% of GP minutes), log loss improves by 0.027 per line, 24 times the average gain. Top-5 players: 0.0001, rank 6 and lower: 0.0016.
- **The overall prop gain is about 0.0009 log loss and is statistically clear (t 3.6) but economically small.** The registered bar for "worth promoting" included minutes pinball at t of 3, which it did not reach (t 1.9).
- **The model under-predicts early exits**: 4.2% predicted against 5.9% actual. The quantile model sits slightly high at the median (52.0% of actual minutes below q50) and its mean is +0.28 minutes high, so the lower quantiles are not low enough.
- Because fewer early exits are predicted than occur, the next version would need a dedicated early-exit component (a probability model for leaving early, mixed with the quantiles), not more quantile levels.

## Options (a decision for you, not run)

1. **Stop here.** The tail is real but small at the prop level; nothing in pricing changes.
2. **Register a second version** with an explicit early-exit mixture and a calibration step, with a fresh rule, a fresh split (2025-26 odd games are now seen) and the first result on record here. The honest holdout for it would be the live season.
3. **Wait for live data.** GP minutes are logged from 2026-10-29; the market-implied gap and the tail can both be re-tested on live days.
