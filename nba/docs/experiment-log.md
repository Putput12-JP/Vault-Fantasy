# NBA experiment log and live-ledger accept rules

Written 2026-10-07 as part of the leakage audit (docs/leakage-audit-2026-10-06.md, finding 3). Written and committed
before anyone looks at the live shadow ledger results (`nba/data/track.json`, `bets/`, recorded since 2026-09-30). I have
not read those results.

## 1. What has already used the 2025-26 season

Everything below tested on 2025-26 (or fit on 2024-25 and tested on 2025-26). Whether the rule was written first is taken
from each doc's own words; "not stated" means the doc does not say.

| Experiment | Doc | Rule written first? | Outcome |
|---|---|---|---|
| Game model tune and test | game-model.md | not stated | context only, t 1.23 vs close |
| Minutes model v1, v3 | minutes-model.md, minutes-model-v3.md | not stated | v3 candidate |
| Prop model v1, v2, v3 ladder, v3 full | prop-model*.md, v3-plan.md | v3 plan exists; v1/v2 not stated | v2 shipped; v3 candidate |
| Rates v3 (per-stat memory) | rates-v3.md | not stated | candidate |
| Starters feed | starters-feed.md | not stated | candidate |
| Minutes v3 pricing | minutes-v3-pricing.md | yes ("pre-registered") | decision per doc |
| Moved players | moved-players-test.md | yes (committed before) | NO-GO |
| Season start | season-start-test.md | yes (committed before) | NO-GO |
| Game venue sharpness | game-venues-test.md | yes (committed before) | blend NO-GO (log-loss change +0.0011, SE 0.0011) |
| Hit rates | hit-rates.md | yes ("rule fixed first") | per backtests.json, a streak is not enough to beat the price |
| Pick'em correlation | pickem-correlation.md | yes | GO |
| Copula step A | copula-fit.md | yes | NO-GO |
| Copula step A2 | copula-fit-a2.md, copula-freeze.md | yes, and moved to the **2026-27 holdout** | frozen, waiting |
| Consensus engine | consensus-engine.md | not stated | 3 Kalshi GO cells |
| Lean search (11 trials) | lean_trials_nba.json | yes (all trials logged, bar rises with trials) | all 11 rejected |

So the NBA side is in better shape than the NFL side: most later tests were pre-registered, and the copula test already uses
a season nobody has looked at. The gaps are the early model builds (game, minutes, prop v1/v2) with no written accept rule,
and no single place that counts how many looks the 2025-26 season has had. This file is that place; append a row for every
new test.

## 2. Multiplicity on the Kalshi GO signals

The GO gate is z >= 2 per cell, and there are many cells. Re-counting the cells with 50+ bets across the v2 and consensus
backtests gives 68 (engine variants overlap heavily, so 68 overstates independent tests and the correction below is
conservative). At z >= 2, 68 cells should produce about 1.5 false GO cells by chance alone. Holm-adjusted one-sided p-values,
after the consensus backtest was rebuilt with the as-of candidate rule (see section 5):

| Cell | n | ROI | z | Holm p (68 cells) |
|---|---|---|---|---|
| v1 blend 3pm NO | 3,200 | +10.2% | 3.56 | 0.013 |
| v2 blend 3pm NO | 3,262 | +8.7% | 2.86 | 0.133 |
| Consensus + model 3pm NO | 1,545 | +16.5% | 2.84 | 0.140 |
| Consensus + model pts NO | 1,835 | +8.8% | 2.38 | 0.511 |

Read: only the strongest 3-pointer NO cell clears a 5% family-wise bar; the other two 3-pointer cells sit at about 0.13 to
0.14 and the consensus points NO cell at 0.51. These are the conservative bound, not proof of no edge: the variants are
correlated, so the true family is smaller than 68. Treat points NO as WATCH, and the 3-pointer NO cells as probable but
unproven until the live ledger agrees. These ROIs are also before the Kalshi structural bias check: any NO-side edge must beat
the price-only "bet every NO" baseline (nba/README gotchas). On the ladder test price-only NO earns +5.2% on 3-pointers and
makes no points NO bets at all, so the consensus 3-pointer edge is about 11 points above the plain bias.

## 3. Accept rules for the live ledger (fixed now)

Frozen candidate list, as of the commit that adds this file: **(a)** v2 blend 3pm NO, **(b)** consensus + model 3pm NO,
**(c)** consensus + model pts NO. Live ledger = shadow bets recorded since 2026-09-30, one 1-unit bet per key at its first
3% price, per `nba/scripts/ledger.py`.

- **Evidence needed to promote a cell to a shipped GO:** at least 300 live bets and 50 game days; ROI > 0 after fees; live z >= 2.13
  (one-sided 0.05 split across the 3 frozen cells); mean CLV against the close not negative.
- **Demote (GO becomes WATCH):** live ROI < 0 with z <= -1 once there are 150 live bets.
- **Anything not on this list** (a new stat, side, venue or engine) gets no live credit; it must be pre-registered here first
  and wait for its own 300 bets. Reading the ledger for a new pattern and then proposing it does not count.
- **Looks:** the ledger may be read monthly for monitoring; promotion or demotion decisions are made only when a cell reaches
  its bet count, using the first time it does, not the best time.
- **Changes after the fact:** if this file is edited after the ledger has been read, record the date and the reason below, and
  the result is exploratory.

## 4. Gaps this does not close

- The early NBA models (game, minutes v1, prop v1 and v2) were tuned on 2025-26 and cannot be unseen. Only live and the 2026-27
  copula holdout are clean.
- The multiplicity count is of cells in files on disk; any test that was run and not saved is not in it.
- Not audited this pass: `build_consensus.py` candidates, the live pricing code's bet clock, `lean_search_nba.py` internals.

## 5. Consensus audit (2026-10-07)

`build_consensus.py` uses the v2 walk, so its saved results were built with the old box-score candidate rule and were stale
after the candidate fix. Rebuilt. Changes: consensus 3pm NO z 3.30 -> 2.84 (ROI +16.8% -> +16.5%), pts NO z 2.26 -> 2.38,
ast NO z 1.99 -> 0.41, ast YES dropped below the signal list. Robustness (`nba/scripts/audit_consensus.py`, ladder test,
consensus + model): last trade instead of the 30-minute VWAP leaves 3pm NO intact (+17.3%, z 3.01) and weakens pts NO
(+5.3%, z 1.59). Requiring 500+ contracts in the last 30 minutes leaves too few rungs to test (pts NO n 221, z 0.84; the other
cells fall under the 400-row minimum): median 30-minute volume per rung is 105 contracts and 86% of rungs trade under 1,000, so
none of these edges has been shown to be executable at size. Only the live ledger can show that.
