# Game-model experiments: rules

Written 2026-10-13, before either experiment was scored. Runners:
`nba/scripts/backtest_total_anchor.py` and `nba/scripts/retune_game_model.py`.
Results land in `nba/docs/game-model-experiments-results.md` only after this file is committed.

Both experiments keep the walk-forward cut the game model already uses. Warm-up is 2021-22
(season label 2022). Parameters and the anchor's distribution are fit on 2022-23 and 2023-24
(labels 2023 and 2024) only. Nothing in the fit sees 2024-25 or 2025-26 (labels 2025 and 2026).

## What was already true in the code, checked before the runs

The shipped parameters in `nba/data/game_model.json` are K 0.04, REP 0.4, ALPHA 0.06, CT 0.0.
Those are the low end, high end, low end and low end of the grids in `build_game_model.tune`
as it stood: K `{0.04…0.08}`, REP `{0.20…0.40}`, ALPHA `{0.06…0.16}`, CT `{0.0…1.6}`.
The runner prints this check again from `OLD_GRID` before it searches.

ESPN game lines have an open and a close and no timestamps on either (`backfill_espn_odds.py`).
The close is not a 1pm number, so it is not an anchor. The `nba-data` branch's Pinnacle tape
starts at `snapshots/2026-09-30` and does not cover a single game in the Kalshi test seasons.

While the lines were downloading, and before any strike was priced: season 2023 stores no
DraftKings or ESPN BET open or close total (the `current` total is present and unlabeled).
Season 2024 stores opening totals. That is why the sigma rule below drops a tune season that
does not actually have opens, instead of borrowing the test seasons.

## Experiment A — price the Kalshi total ladder from the sportsbook total

**Anchor.** For each game, the opening total from DraftKings, else ESPN BET, the same book
order as `nba_common.closing_lines`. A number outside 150 to 320 is rejected (that range is
a sanity check against a price that landed in the total field, not a fitted bound). No
Pinnacle number is available for these seasons, and the close is not used.

**Distribution.** Normal, centered on that opening total. No bias correction.
`sigma = MAE(actual total − open) × sqrt(π/2)` on tune-season games. A tune season counts
only if at least 80% of its games have an opening total; otherwise that season is dropped.
If the games that remain are fewer than 500, sigma falls back to the shipped model's tune
total MAE (`game_model.json` `tune_mae[1]`) times the same constant. Sigma is never fit on
2025 or 2026. `P(over the strike) = 1 − Φ((strike − open) / sigma)`, with the strike the
same `floor_strike` the current ladder test uses.

**The bet.** Same prices, fee and filters as `backtest_game_vs_kalshi.ladder_test` for
`KXNBATOTAL`: a 1pm trade and a pre-tip trade, 1pm price between 0.05 and 0.95, settled
yes or no. Buy the side the anchor likes when it disagrees with the 1pm price by at least
4%, 8% or 12%, paying the 1pm price plus the Kalshi taker fee. The 8% bucket is the one
the decision uses. The other two are reported the way the current table reports them.

**Money and z.** ROI after fees is one contract per strike: total profit divided by dollars
risked. That is the column the current total-ladder table calls "ROI after fees", the number
the writeup called about +2% per contract. Profit per contract (profit divided by strikes)
and equal-dollar-stake ROI (the unweighted mean of each strike's return on stake) are
reported beside it and do not decide. z is the game-clustered z already in
`backtest_game_vs_kalshi.clustered`: each game's mean return on stake, then the mean across
games. Halves are a split of strikes by tip time, half and half, as that function's table does.

**Comparisons, all on the strikes that have an anchor.**

- The current model, with the shipped parameters and the shipped total sigma
  (`tune_mae[1] × sqrt(π/2)`), same 1pm total the ladder already uses. With CT at 0
  the total does not depend on the injury report.
- Price-only: on the first half of those strikes, fit `P(yes) = logistic(a + w × logit(1pm price))`.
  On the second half only, bet when that probability disagrees with the price by the same
  thresholds. The first half is the fit, so it is not a bet for this baseline. This is the
  "price recalibrated on earlier data" baseline from `build_prop_model.py`.

Brier score of the anchor, the model and the raw 1pm price is reported on the full common
set and on each half. The second half also reports the recalibrated price's Brier. Brier
does not decide. A drift note (Kalshi's 50% strike versus the opening total) is descriptive
and does not decide.

**Verdict, 8% bucket only.** Evaluated by the runner, not by hand.

- **NO-GO** if full-sample ROI is not positive, or either half's ROI is not positive.
- **GO** only if it is not NO-GO and all of these hold: second half has at least 50 games and
  z at least 2; second-half ROI is greater than the price-only second-half ROI (a price-only
  sample under 20 bets counts as ROI 0); second-half ROI is at least the model's second-half
  ROI; each of the YES and NO sides with at least 20 second-half bets has ROI at least 0.
- **WATCH** otherwise.

This experiment does not change the Slate, the paper bot, or `game_model.json`, even on GO.
The merged paper bot prices the model total, not a sportsbook anchor, and there is still no
historical Pinnacle 1pm tape to be the live version of this test.

## Experiment B — widen the four edge grids, and retune C on the report if we can

**Grids.** Only the four that sat on the boundary move. The search is still two coordinate
sweeps starting from the shipped parameters, keeping a step only when its own objective
improves by more than 0.0001.

| Param | Was | Now |
|---|---|---|
| K | 0.04, 0.05, 0.06, 0.07, 0.08 | 0.01, 0.02, 0.03, then the old values |
| REP | 0.20, 0.25, 0.30, 0.35, 0.40 | the old values, then 0.50, 0.60, 0.80 |
| ALPHA | 0.06, 0.09, 0.12, 0.16 | 0.02, 0.03, 0.04, then the old values |
| CT | 0.0, 0.4, 0.8, 1.2, 1.6 | −0.8, −0.4, −0.2, 0.0, 0.2, 0.4, 0.8 |

K, CARRY, C, REP, B2B and ALPHA still minimize oracle margin MAE. KP and CT still minimize
oracle total MAE. Test seasons are not in the loss.

**C on the report.** The archive is there for the tune years only if each of 2023 and 2024
has a snapshot at or before 1pm ET on at least 80% of its game dates. Then the C axis
minimizes 1pm-report margin MAE on those covered tune games, walk-forward, with play rates
learned only inside the tune window. Every other axis stays on who actually sat. If either
tune season is under 80%, C stays on the oracle objective and the results say the coverage.
Early PDFs (through 2022-23) split the column titles and sit higher on the page;
`fetch_injury_reports.parse` reads that layout and leaves the later one-token layout
unchanged (checked against two 2024 reports before this ran).

**Before and after, test seasons only.** Recomputed in this run for the shipped parameters
and the new ones, on the same games. Spread MAE is the 1pm-report margin. Total MAE is the
projected total (the 1pm report only matters if CT is not 0). Kalshi 1pm Brier is the
moneyline, the spread ladder and the total ladder, with the same filters as
`backtest_game_vs_kalshi.py`. Each parameter set is turned into a probability with its own
tune-season MAE converted the way that backtest converts it (`MAE × sqrt(π/2)`), margin
sigma from the margin MAE and total sigma from the total MAE. A difference is
`mean(error_old − error_new) / SE` across games, so a positive number means the new
parameters are closer. A market whose price file is missing, or a margin number whose 1pm
reports cover under 80% of the test games, is "not measured".

**Ship into `game_model.json` only if all of these hold.** Otherwise the shipped file stays,
and the live Slate and the paper bot keep today's inputs.

1. Spread t ≥ 2 or total t ≥ 2.
2. Spread t > −2 and total t > −2. An unmeasured one fails this.
3. Moneyline, spread-ladder and total-ladder Brier each have t > −2. An unmeasured one fails this.
4. K, REP, ALPHA and CT are not on an endpoint of the widened grid.
5. CT is still 0. `scripts/paper_bot/signals/nba_total.py` refuses to trade when CT is not 0,
   because it does not read an injury report. This experiment does not change that bot.
   A non-zero CT can pass 1–4 and still not ship.

t needs at least 50 games or that metric is not measured.
