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
backtests gives 67 (engine variants overlap heavily, so 67 overstates independent tests and the correction below is
conservative). At z >= 2, 67 cells should produce about 1.5 false GO cells by chance alone. Holm-adjusted one-sided p-values:

| Cell | n | ROI | z | Holm p (67 cells) |
|---|---|---|---|---|
| v1 blend 3pm NO | 3,200 | +10.2% | 3.56 | 0.012 |
| Consensus + model 3pm NO | 1,526 | +16.8% | 3.30 | 0.031 |
| v2 blend 3pm NO | 3,262 | +8.7% | 2.86 | 0.127 |
| Consensus + model pts NO | 1,782 | +7.3% | 2.26 | 0.691 |
| Consensus + model ast NO | 754 | +14.3% | 1.99 | 1 |

Read: the 3-pointer NO edge survives correction on the stronger cells. **Consensus + model points NO does not** (Holm 0.69), and
it is the only points GO left after the candidate-set fix (docs/leakage-audit-2026-10-06.md, addendum 4). Treat it as WATCH
until the live ledger says otherwise. These ROIs are also before the Kalshi structural bias check: any NO-side edge must beat
the price-only "bet every NO" baseline (nba/README gotchas), which the doc reports separately.

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
