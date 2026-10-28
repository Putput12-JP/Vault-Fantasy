# Minutes: left tail (quantile minutes distribution)

Written 2026-10-28, before any number below was computed. Script: `scripts/test_minutes_tail.py`. Results go to `minutes-left-tail-results.md`. Nothing here changes pricing.
Motivation: [minutes-autopsy-and-implied-results.md](minutes-autopsy-and-implied-results.md): early exits (actual under 40% of GP minutes, not a blowout) are 15.6% of GP's 8+ minute misses, GP was too high in every one, by 12.9 minutes on average. A point forecast cannot say "he may leave early"; a distribution can.

## Candidates (2025-26, players who played; props are priced "if he plays")
- **Point (GP)**: the promoted point minutes. Its spread is the empirical spread of (actual - GP) on the FIT half (below), so the baseline has the same information about error size.
- **Tail (GQ)**: LightGBM quantile regression (`objective='quantile'`, same features and params as the mean GBM, 150 trees) at 19 levels, 0.05 to 0.95 in steps of 0.05, fitted on 2023, 2024, 2025 only, played rows, gn >= 5. Each row's 19 quantiles (sorted, clipped to 0 to 48) are multiplied by GP / G (the factor the C3 rescale applied to his point minutes), so the distribution lives on the same 239.67-expected scale. The 19 values are an equal-weight sample.
- Rows with no GBM history keep GP and the baseline spread.

## Split (fixed now)
2025-26 games with an even game id are the FIT half (used only to fit the baseline's residual spread and the stat dispersion); odd game ids are the HOLDOUT half. All scores below are on the HOLDOUT half. The game is the cluster unit.

## Stat layer (no new model of players)
Per stat s in pts, reb, ast, 3pm: rate_s = mu_s / pm (the v2 priced projection per v2 minute, from the stored rows). Mean given minutes m is rate_s x m. Count distribution: negative binomial with variance mu + phi mu^2, phi per stat per candidate chosen by max likelihood on the FIT half over a grid of 0 to 0.5 in steps of 0.01. Point: m = GP. Tail: m ~ the 19-value sample (probability = average over the 19). Lines scored: for each row and stat, the half-lines floor(rate x GP) + 0.5 + {-1, 0, +1}, counted as over/under; score = log loss of P(over).

## Rule (fixed now). The tail model is a candidate for promotion only if ALL hold
1. **Calibration** (all played holdout rows): the share of actual minutes under the model's q10, q25, q50, q75, q90 is within 2 points of 10, 25, 50, 75, 90 percent.
2. **Minutes pinball loss** averaged over the 19 levels is below the point baseline's, paired cluster t >= 3.
3. **Early exit**: the model's predicted share of the 19-value sample below 0.4 x GP, averaged over holdout rows, is within 1.5 points of the actual share of rows whose minutes were under 0.4 x GP.
4. **Props**: mean log loss over all lines below the point baseline's, paired cluster t >= 3, and no stat's mean log loss worse.
5. **Mean preserved**: the average of the model's 19 values minus the actual minutes, mean over holdout rows, within 0.5 minutes of zero.
If 1 to 5 hold, the next step is a separate promotion (pricing integrates over the distribution, JS twin, parity) in its own step with old and new numbers; this test does not change pricing. If any fails, nothing is promoted and the failing item is reported as it is.
Context only: results split by top-5 and other rotation, pool size, and starters; and the loss at the under side only (under bets are where an early exit helps).
