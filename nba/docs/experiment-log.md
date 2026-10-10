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
- **Which price counts:** promotion is judged on the **entry price**, the first poll the edge reached 3% (the price a live
  bettor could actually take, paying the ask for YES or 1 minus the bid for NO, plus the taker fee). Close ROI and CLV are
  reported beside it as diagnostics, never as a substitute. The backtest's clock (Kalshi 30-minute pre-tip VWAP, no spread, no
  size limit) is not comparable to either, so backtest ROI is never used to meet or excuse a live threshold. Added 2026-10-07,
  before the ledger was read.
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

## 6. Starters feed and minutes v3 (2026-10-07)

The starters feed used in backtests is stamped about 2.5 hours after tip and is effectively post-game truth (5,285 of 5,286
team-games all five starters right; 0 of 21,485 listed inactives played). Rule fixed now: **minutes v3 with starters (v3s) does
not ship, and its backtest gain is not cited, until it is re-tested on live Expected -> Confirmed timestamps (recorder logs them
from 2026-27) with candidates built by the as-of rule.** Minutes v3 without the feed is unaffected in ranking (still ahead of v2
by about 0.04 minutes) but its absolute error is 5.00, not 4.65, once non-dressed candidates take minutes
(`nba/scripts/audit_minutes_v3.py`).

## 7. Execution cost sensitivity (2026-10-07), `nba/scripts/audit_spread.py`

Historical Kalshi data here is trades only (no bid or ask), and the live recorder has almost no Kalshi player-prop books yet
(8 points rungs on 2026-10-05, none for 3-pointers), so the real spread is unmeasured. Instead, an extra half-spread h was added to
both the 3% edge test and the bet cost (YES at the ask, NO at 1 minus the bid). Consensus + model, Kalshi ladder, second half:

| Half-spread h | 3pm NO | pts NO |
|---|---|---|
| 0.00 | +15.7%, z 2.80, n 1,548 | +8.9%, z 2.38, n 1,834 |
| 0.01 | +17.0%, z 2.41, n 1,109 | +3.9%, z 1.68, n 1,105 |
| 0.02 | +15.0%, z 1.86, n 794 | -2.5%, z 0.22, n 614 |
| 0.03 | +14.8%, z 1.15, n 527 | -11.0%, z -1.70, n 331 |

Read: the 3-pointer NO edge keeps its ROI up to a 3-cent half-spread (fewer bets qualify, so z falls), while the points NO edge is
gone by 2 cents. Points NO therefore needs a half-spread under about 1 cent, which thin rungs (median 105 contracts per 30 minutes)
rarely offer. Once regular-season props list, measure the real half-spread per stat from the recorder's bid and ask before
trusting either cell; this section's table is the bar to compare it against.

## 8. Tier 2 trading gate (DRAFT 2026-10-10, not in force until the owner signs below)

Written before the live ledger has been read (the file header still holds: no one has looked at `track.json` or `bets/`). It replaces
the "300 live bets and 50 game days" promotion rule in section 3 **for real-money sizing only**. Section 3 still governs the page's
"Proven" label. Context and tiers: `docs/update-plan.md` Phase 1.5. Numbers below are computed from `data/consensus_bets.json`
(consensus + model, 3PM NO, 2,022 bets over 277 games, `kalshi_ladder` plus `books_to_kalshi`), game-clustered like `calibrate_edge.py`.

### 8.1 What the data can and cannot prove

Backtest ROI on this cell is +16.6% per bet (z 3.5, game-clustered). The game-clustered SE is about **0.79 / sqrt(games)** per unit
risked. Games needed for z >= 2.13 at a true ROI of:

| True ROI | Games |
|---|---|
| 15% | ~130 |
| 10% | ~285 |
| 7% | ~580 |
| 5% | ~1,140 |
| 3% | ~3,170 |

About half of all games produce a 3PM NO entry bet (277 games in the backtest's second half), so a season is roughly 600 such games.
A fixed "prove it first" bar therefore cannot open at a realistic edge this season. Group-sequential test with looks at 150, 300 and 450
games, one-sided alpha 0.05/3 (boundaries z 3.76, 2.66, 2.17, simulated): chance of passing by game 450 is **21% at a true 5% ROI, 39% at
7%, 69% at 10%, 97% at 15%**, and 1.5% at 0%. That is a sound test and a slow one.

### 8.2 Rule: size on the evidence, do not wait for a verdict

Real-size stake for a cell is **quarter Kelly on the posterior-mean ROI**, after every game day, so size grows as evidence accumulates
and falls if it does not.

- **Prior (judgement, fixed here):** true ROI ~ Normal(mean 5%, sd 5%). About 30% of the backtest's 16.6%, consistent with the calibration
  table (promised edges keep about half) and the 68-cell multiplicity. The sd lets the data move it.
- **Data:** shadow-ledger entry-price bets for the cell, ROI per unit risked after fees, game-clustered SE = 0.79 / sqrt(games).
- **Posterior:** normal-normal update. Examples (observed ROI -> posterior mean, P(ROI > 0)): at 150 games, 5% -> 5.0%, 90%; 10% -> 6.9%,
  96%; 15% -> 8.7%, 99%. At 300 games, 5% -> 5.0%, 93%; 10% -> 7.7%, 99%. At 150 games, 0% observed -> 3.1% posterior, 79%.
- **Conditions to trade above Tier 1 size** (all required): at least 100 games on the cell; **observed** ROI after fees > 0 (the prior must
  not carry a flat or losing cell); P(ROI > 0) >= 0.90; mean CLV against the close not negative; cell not demoted.
- **Caps:** 1% of bankroll per order, 3% per game, daily loss stop, and no more than 2x the previous week's average order size in any week
  (so a lucky run cannot jump the size).
- **Demote (stop real size, back to Tier 1):** observed ROI < 0 with z <= -1 after 150 games, or P(ROI > 0) falls below 0.80.
- **Frozen cells:** 3PM NO (consensus + model) first. Points NO needs a measured half-spread under about 1 cent before it trades at all.
  Anything else follows section 3's "pre-register first" rule.
- **"Proven" label unchanged:** the page's Proven badge still needs section 3 (or the group-sequential bound in 8.1 at games 150, 300,
  450). Sizing on the posterior is not a claim of proof.

### 8.3 Why this is acceptable

Decision-wise, a modest stake on a plausible 5% edge has positive expected value even when it is not proven, and the posterior shrinks
it toward zero size if the live record disagrees. The costs are a prior chosen by judgement and no formal false-positive guarantee on the
trading decision. Both are disclosed here, and the demote rule and the loss budget bound the damage.

### 8.4 Owner sign-off

- Prior (mean 5%, sd 5%), the 100-game minimum, P(ROI > 0) >= 0.90 and the weekly size ramp are **proposals**. Replace any before signing.
- Signed by: ____________  Date: ____________  (until signed, Tier 2 stays closed and Tier 1 micro-stakes run as in the plan)
- After signing, any edit is dated with its reason, and a result read after the edit is exploratory (see section 3).

