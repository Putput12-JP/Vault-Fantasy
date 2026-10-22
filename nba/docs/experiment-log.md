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
| Public-data sweep: RAPM, PBP garbage time, Kalman rates (volume, percentages) | reverse-engineering-targets.md items 2-7 | pass bars written in each script before running (one amendment, disclosed) | RAPM NO-GO; garbage time NO-GO; Kalman volume tiny (<= 0.3% RMSE), percentages NO-GO |
| Minutes GBM vs linear (two holdouts: 2024-25, 2025-26) | minutes-gbm.md | yes (bar in the script header) | PASS on accuracy, oracle absences; shadow only |
| Minutes spread model | minutes-spread.md | yes | FAIL (+0.75% / +0.80% CRPS vs a 1% bar) |
| Simulation challenger (10k and 50-draw sims vs analytic v2, single props) | sim-challenger.md | yes (one disclosed amendment after run 1: calibration) | sim10k = v2 (8/8 cells same); 50-draw sims same or worse (0 better); NO-GO as a probability engine |
| SmartStake multi-book closes, Circa/Bookmaker lead, fitted book weights, ladder fits | docs/smartstake-experiment-log.md | yes (written 2026-10-17, no outcomes read) | not graded yet |
| Kalshi total ladder anchored to the sportsbook open | game-model-experiments.md, game-model-experiments-results.md | yes (committed before scoring) | NO-GO. 8% one-contract ROI +18.0% then −3.4% (z 4.13, 0.57). Second half not positive |
| Game-model widened retune (K, REP, ALPHA, CT, and C on the 1pm report) | game-model-experiments.md, game-model-experiments-results.md | yes (committed before scoring) | NOT SHIPPED. Spread MAE t −1.45, total MAE t 1.51. Candidate CT 0.2 would stop the paper bot. game_model.json unchanged |
| NBA lean tracking: the model's side (model-only P(over) at the modal line) on every priced prop, graded against the box score, compared with always-under and the market side | lean-tracking.md | yes (written 2026-10-22 before any lean was recorded) | FORWARD ONLY from the 2026-10-22 recorder merge (PR 216). No outcome yet: nothing is quoted under 100 graded leans. Backtest series (2025-26, lean 53.3% vs always-under 53.2%, gap +0.1 pts, CI -2.6 to +3.0) and a 13-game psim backfill are descriptive and not counted as clean tests |

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

## 8. Tier 2 trading gate (SIGNED 2026-10-10, in force)

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
- **Signed by the owner, 2026-10-10, by chat message ("I accept"), as drafted:** prior mean 5% / sd 5%, 100-game minimum, P(ROI > 0) >= 0.90,
  weekly size ramp 2x. The stricter option offered (3% prior, 150 games, 95%) was not chosen. The live ledger had not been read at signing.
- After signing, any edit is dated with its reason, and a result read after the edit is exploratory (see section 3).

## 9. Novig paper trading (pre-registered 2026-10-10)

A new venue with no history, so under section 3 it earns no live credit until it has its own rule. The rule, the simulator's settings and its limits are in
`docs/novig-paper-trading.md`, written before the first paper order and before any Novig result was read. Summary: simulated resting orders at our price on Novig player
props (3% edge after a placeholder 2% fee, $5 stake), filled only from the public tape (`touch` and `thru` kept apart), settled from the box score. First look at **100
filled orders under `thru`**: return above zero at z >= 2 clustered by game day, with Novig's real fee confirmed and the results recomputed. Nothing else on Novig
(takers, game markets, other stats) is credited. No real order exists or is authorised by this section.


## 8. Minutes GBM shadow (2026-10-11), fixed before the live ledger is read

What was run: a LightGBM minutes model (`nba/scripts/build_minutes_gbm.py`, `minutes_gbm.py`) tested on 2024-25 and 2025-26 against a
linear stand-in for the shipped features: 6.001 vs 6.311 RMSE and 6.030 vs 6.369, paired t above 20 on both. Those two seasons were
used; the 300-tree size was chosen from a five-size sweep scored on 2025-26, so treat that number as slightly optimistic.

Why the backtest gain is not the evidence: it used **oracle absences** (who actually sat) and only players who played, which is
the weakness section 6 found in the minutes v3 backtest (absolute error 5.00 not 4.65 once non-dressed candidates take minutes).
Live, the GBM sees report-status absences and as-of rosters, so expect a smaller gain than the table shows. Also, the
backtest's expected margin came from the game model while live uses the market spread.

Live ledger rule for the GBM shadow (logged next to v2 and v3 in `track.json` `minutes_days[*].gbm`, never priced):
- **Promote to a pricing candidate** only with at least 3,000 settled player-games over at least 20 game days, a lower
  average miss than v2 on the same players, a lower 8+ minute miss count, and a day-level paired t of the MAE difference of at
  least 3.
- Promotion to a pricing candidate is not promotion to pricing. It still needs its own pre-registered Kalshi-edge test, because
  minutes v3 and rates v3 were more accurate than v2 and did not move the edge.
- Same looks rule as section 3: monthly monitoring, decision only when the sample size is met, using the first time it is met.
- If this section is edited after the ledger has been read, record the date and reason here and the result is exploratory.

Added 2026-10-11 (before the ledger was read): with no price archive available, a market-free check was run
(`nba/docs/minutes-gbm-ladder.md`). It found the GBM improves rung log loss on points, rebounds and assists (+0.4% to +0.8%) and
not on 3PM. That is a reason to expect little from the GBM on the 3PM NO cell, recorded here so a later positive 3PM result is read
as surprising. It does not replace the live rule above.


## 10. Returning-player hold (2026-10-20), a guard, not a model change

Trigger: Haliburton (back from an Achilles tear, no games in 2025-26) was projected at 19.6 minutes for IND at NO, and the owner expects 30+ as the
starting PG. Decomposition from the live state: base 26.0 (his recent-minutes average, dragged by his last two games, 23 and 7 minutes), minus 1.8
(return from absence), minus 4.7 (the team rescale, everyone x0.81). His 2024-25 regular season was 33.6.

Check on 2022-26 hoopR box scores (`player_box_*.csv`), run once, no rule written first, so exploratory: players returning after missing a full
season (330+ days since their last game, 25+ prior games): 57 cases; the 13 with 26+ minutes a game before: those who started their first game back
averaged 30.5 minutes (2 players), those who came off the bench 18.0 (11 players). Across the 8 players with 28+ before, the first game averaged 21.9
and the first five 23.1, against a healthy mean of 32.7; both the healthy mean and the recent-minutes average missed the first game by about 11.5
minutes. Tiny samples; the direction (starter status decides) matches the starters-feed result in section 6.

Rule shipped (page `returningHold`, `pricing.returning_hold`, same rule): a player whose last game was 150+ days before his team's last game is held
(priced and shown, never a Bet / Lean, an edge, a pick'em leg, a shadow bet, a Novig paper order or a prop-sim record) until he plays a game, or on
the page until the user sets his minutes in the Lab or on Tonight. On the 2026-10-19 state it holds 11 players: Irving, Niang, Beekman, VanVleet,
Lyles, Simmons, Lillard, Haliburton, Kessler, Beal, Garcia. Not changed: the minutes model itself. **Open (option B):** a pre-registered test of
"returning player confirmed as a starter gets his healthy-baseline minutes", which needs more returning-starter games than the data holds.


## 11. Combo Check call record (fixed 2026-10-20, before any call has settled)

Every call Combo Check makes is logged by `scripts/combo_calls.py` (local: the prices are SmartStake's), run inside the 5-minute publish job.
- **Calls:** straight (alt bet at a sportsbook, priced -140 to +200, a point off main, edge 3%+), mates (teammate parlay from the two passed pairings, same
  side, one book, edge 3%+, top 6), cross (a book's two best alt legs from different games, edge 3%+, top 4). Edge = fair chance x decimal odds - 1; fair
  chance = median of OTHER venues quoting both sides of the SAME line (margin removed, 2+ venues); parlay chance = legs multiplied plus the measured lift.
- **Entry** = the first poll a call appears; its price then is the bet. Calls that stop being shown stay in the record. **Close** = the last price seen
  for the same legs at the same book before tip. **Grade** = flat 1 unit at the entry price from the ESPN box score; a player who did not play voids the call.
- **Not in the record:** exchange straights (Kalshi, Polymarket, Novig) shown on the page: their fees are not in the tape. The page also sees Pinnacle, Kalshi
  and Polymarket as fair-price sources, and the model's minutes and holds; the tracker uses the tape alone, recent minutes >= 15 and the returning-player hold.
  So the record is "what this rule set called", not a replay of one browser session.
- **Reading it:** monitoring only. No call type is called good or bad before **100 settled calls of that type** and a closing-line value that is positive
  (mean entry price against close, 2 SE). Edges are measured against other books' prices, not against outcomes, so a positive edge with a negative CLV
  means the other books moved toward this book, i.e. the edge was a stale line in the benchmark, not in this book.
- Tested on real box scores with constructed calls (won / lost / under / PRA / two-leg / did-not-play void) and on the live tape (38 calls on the first
  pass: 28 straight, 6 mates, 4 cross). No call has settled yet.

## 12. Bankroll Builder pick record (rules fixed 2026-10-22, before any live pick has settled)

`scripts/bankroll_builder.py` (local: the prices are SmartStake's), run inside the 5-minute publish job after Combo Check. The page is NBA > Bankroll Builder.
- **Pick:** one sportsbook leg, no parlays, main or alt line, priced **-110 to -220**. Exchanges are fair-price sources only (fees are not in the tape).
- **Market gate:** fair chance = median of **3+ other venues** quoting both sides of the same line, margin removed (books up to 16% overround, exchanges 8%);
  market edge = fair x decimal odds - 1 **>= 4%**. (Combo Check needs 2 venues and 3%; this is stricter on purpose.)
- **Model gate:** the model's calibrated chance (nba/scripts/pricing.py, the page's `pv`) **>= the price's cost + 2 points**. No model number, no pick.
- **Player gate:** recent minutes >= 20, no roster / returning-player / preseason hold, not Out / Doubtful / Questionable / Inactive.
- **Caps:** one pick per player per game, at most 2 per team-game, 8 per slate (ET day); a game within 36 hours. First come, ranked by market edge within a poll.
- **Tier:** Core = market edge >= 6% and the model clears the price by 4+ points; Standard = the rest. Recorded on the pick.
- **Entry / close / grade:** logged at the first poll it qualifies (entry price); close = the last price seen for the same leg at the same book before tip;
  graded flat **1 unit at the entry price** from the ESPN box score; a player who did not play voids it.
- **Bankroll:** $1,000 paper, 1 unit = $10 (as Vault Ledger). A quarter-Kelly line (cap 2% of the bankroll, on the market's fair chance, sequential by tip)
  is a **shadow** for comparison and never the headline.
- **Shadow logs (never counted):** `market_only` = passed every gate except the model's; `model_only` = the model clears the price by 4+ points but the market
  edge is under 1%. They test whether each gate adds anything.
- **Reading it:** monitoring only. Nothing is called good or bad before **100 settled picks** and a closing-line value that is positive by 2 SE. Thresholds above
  were set from the logic, not tuned to results; changing one starts a new record.
- **Backtest** (`--backtest`): the stored tape replayed poll by poll through the same code, with each poll's board rebuilt from the recorder's snapshots
  (nba-data branch) and the model files as they stood in git at that moment. Limits: the prop model's fitted parameters (variance, calibration, stacker) are the
  ones on hand, last refit 2026-10-09, before any regular-season game; poll cadence is the tape's (5 to 30 minutes, with gaps). Replayed picks are labelled
  and never merged into the live record.
