# Prop calibration tests: rules written before anything is scored

Written 2026-10-25, before any of the three tests below was scored. Committed alone, ahead of the runner (`scripts/test_prop_calibration.py`),
so the order is visible in git. The rules are the verdict: a result is judged by what is written here, not by how the numbers look afterwards.
Every result is reported, including the ones that fail. **Nothing here changes what the page prices or bets.** A pass only earns a
shadow-tracked candidate and its own pull request.

Where these come from: the Edge Engine teardown (`docs/edge-engine-teardown.md`, branch `nba-edge-engine-teardown`). On 2026-10-24 their
method and ours were scored on the same props: both were overconfident in the tails, and both lost money where the model disagreed with the
market by the most. Those are diagnostics, not results. The three ideas below are what a small, honest adjustment would look like.

## What has already been looked at (disclosed, so nobody has to guess)

- **2025-26 lines (`data/lean_rows_nba.json`, 5,250 lines, 320 games, 2025-26 ESPN pre-tip main lines, model fit on 2024-25).** This file has already
  been used 26 times (`docs/experiment-log.md` section 1: 15 earlier looks plus the 11 trials in `lean_trials_nba.json`; all 11 rejected). It is not clean. Test 1
  uses it anyway and counts itself as look 27 in the bar below. Its dates are: 207 lines in October, 402 in November, 646 in January, 4,000-plus in April to June
  (playoffs). **It has about 460 lines in the first four weeks, so it cannot carry an early-season test**, which is why Test 3 is forward only.
- **The live ledger and lean log (2026-10-21 to 2026-10-24).** I have read counts and the Edge Engine comparison from them. Tests 2 and 3 therefore use **only
  games that tip on or after 2026-10-26**, so nothing they score has been read.
- Sharp money is context only. It is not an input to any test here and does not count toward an agree total.

## Common rules

- Game is the unit. A game's rows are averaged first; z = mean / standard error across games. Props in one game are not independent.
- Later rounds on the same question face a stricter bar than the first: **game-clustered t of at least 2.5**, not 1.96. Both halves of the sample (split at the
  middle game by date) must have the same sign as the whole.
- Old numbers are never replaced by guessed ones. A price, a closing value, or close minus fair when both are stored are the only inputs. A missing value drops the row from
  that test and is counted in the report.
- Rows with no settled result, pushes and voids are dropped and counted. Preseason never counts.
- No other variant, cut-off or stat split is scored this round. If a result is thin, the answer is "collecting", not a new try.
- Any record that improves is flagged for close monitoring with its sample size. Nothing is quoted under 100 graded rows.

---

## Test 1. Cap the model's tail (runs once, today, on the 2025-26 lines)

**Question.** Both models were overconfident when they disagreed with the market by a lot. The prop stack already learns one weight on the gap between the projection and the line.
Does that one weight over-trust the biggest gaps, so that capping the gap beats leaving it open?

**Harness.** `scripts/lean_search_nba.py`, unchanged: its rows, its three expanding time folds (fit 0 to 40%, score 40 to 60%; fit 0 to 60%, score 60 to 80%; fit 0 to 80%, score 80 to 100%),
its logistic fit with the same ridge, its metric (log-loss over every scored line, not hit rate on a slice).

- **Incumbent:** features `[1, logit(market P(over)), gap]`, gap = (projection - line) / max(|line|, 0.5).
- **Candidate (the only one):** the same, with gap replaced by `clip(gap, -c, c)`.
  **c = the 90th percentile of |gap| over the first 40% of rows** (the first fold's fit window), computed once, frozen before any fold is scored, and printed.
- **Not scored this round:** any other c, a multiplier instead of a cap, a per-stat cap, a cap on the probability instead of the gap.

**ACCEPT only if all four hold:**
1. The candidate has lower log-loss than the incumbent in all three folds.
2. The lower end of the game-clustered paired bootstrap 95% interval of the pooled gain is above 0 (1,000 draws, seed 11, the harness's own).
3. The pooled mean gain beats the harness bar, `0.0003 x ln(1 + looks)` with `looks = 15 + 11 + 1 = 27` (about 0.00099 log-loss), counting this look.
4. The game-clustered t of the pooled gain is at least 2.5, where t = the pooled mean gain / the standard deviation of the 1,000 bootstrap pooled means in condition 2.

**c** is the value at index `int(0.9 x N)` of the sorted |gap| values of the first 40% of rows.

Anything else is REJECT. An ACCEPT here means "worth a shadow-tracked candidate in the pricer", not "ship"; the harness incumbent is a research stand-in for the shipped pricer
(`pricing.py` `Pricer.cal` then `blend`), not the same code, and a pass would need its own pull request and its own forward test.

**Companion table, no verdict.** Over the scored rows, the incumbent's reliability: predicted chance for the side it prefers against how often that side won, in the bands
50 to 55, 55 to 60, 60 to 65, 65 to 70, 70 and over, with n; and the share of scored rows where |gap| is above c. Context for reading the verdict only.

**Forward monitor (already fixed in `docs/lean-tracking.md`, nothing new).** A confidence band on the forward lean log is "verified" only when its hit rate is within 4 points
of its predicted chance over 100 or more leans. The top band (65 and over) is the tail this test is about; it is reported with that label, whichever way Test 1 comes out.

---

## Test 2. Last-look gate (forward only, first read when the sample below is met)

**Question.** A bet is logged at the first poll where its edge reaches 3%. Many of those edges are gone by tip, because a lineup was confirmed or the market moved. If a bettor only
placed a bet when the edge still held at the last look before tip, would the bets they kept do better than the ones they dropped?

**Why this cannot run on history.** The walk harness projects once, at the tip clock. A first-look projection and a last-look projection of the same prop exist only in the live ledger
(`bets/<day>.json` on `nba-data`: `fair`, `edge`, `price` at entry; `fair_close`, `price_close` at the last poll before tip; `result`, `pnl`).

**Data.** Settled bets from the live ledger with a tip on or after **2026-10-26**, regular season only, with a stored `price` (a row with no stored price is out, which includes some pick'em rows), a stored
`fair_close`, and a result of win or loss.

**The gate, fixed now.** For each bet, `edge_at_last_look = edge + (fair_close - fair)`: the entry edge, moved by how much our own blended fair moved between the two looks. The price is
the entry price; only the fair is refreshed. **Kept** = `edge_at_last_look >= 0.03` (the ledger's own entry threshold). **Dropped** = under 0.03, including bets whose edge turned negative.
Using the entry price on purpose: a bettor who skipped the bet at the last look never got the close, and the market moving toward us is not a reason to drop.
Rows missing `fair_close` are counted and left out of both arms.

**Primary statistic.** D = mean `pnl` per bet (1 unit at the stored entry price) of the Kept arm minus the Dropped arm. Game is the unit; z = D / its game-clustered standard error.
Secondary, reported beside it and never in place of it: units per night of each arm; closing-line value of each arm; the share dropped.

**Sample required before it is read:** at least **20 regular-season game nights** since 2026-10-26, at least **100 games** and at least **300 settled bets in the Dropped arm**
(the bar the live-ledger accept rule in `experiment-log.md` section 3 uses). It is read **the first night all three are met, once**, not at the best night.
Earliest that can be, from the schedule: about 2026-11-15.

**GO (shadow-track the gate beside the ledger):** D > 0 at z >= 2.5, and D > 0 in both halves. **WATCH:** D > 0 at z >= 1.65 with the sample met. **NO-GO:** anything else, including D that
is positive but under 1.65. Whatever the result, every bet is still logged at its first 3% price as now; the gate only produces a second set of numbers.

**Caveat, stated now.** `fair_close` is the blended fair, so a market that moved toward us also raises it. The gate cannot separate "the model changed its mind" from "the market agreed".
The bet rows do not store the model-only probability at the close; the lean log does, and a model-only version of this gate is a later round, not this one.

---

## Test 3. Lower model weight early in the season (forward only, one read on 2026-11-18)

**Question.** The first four weeks of a season are the model's weakest (`docs/season-start-results.md`, last season's rates are the prior). The shipped blend weights the model and the market with
fixed per-market coefficients. Would trusting the model less in those weeks, and nothing else, score better?

**Why this cannot run on history.** The 2025-26 lines have about 460 lines in the first four weeks (see above), no stored blended probability, and have been used 26 times. The forward lean log stores the
model-only chance, the shipped blend and the market's no-vig chance on every priced prop (`docs/lean-tracking.md`), which is exactly what the comparison needs.

**Data.** Rows of `leans/<day>.json` on `nba-data` for games that tip from **2026-10-26 through 2026-11-17** (the weeks after the opening 6 days, to the end of week 4; the opening nights were read already),
the first-look clock (`f`), **not held** by the roster guard, with a stored `p_blend` and `p_mkt`, and a graded W or L. `y_over` = 1 when the stat went over the line: side O and W, or side U and L.

**Candidates, both computed only from stored numbers.**
- **Shipped:** `p_blend` as stored.
- **Halved:** `sigmoid(logit(p_mkt) + 0.5 x (logit(p_blend) - logit(p_mkt)))`, which halves how far the blend sits from the market. One fixed factor, chosen now, not fitted.
- Reference only, not a candidate: `p_mkt` alone.

**Metric.** Log-loss per row, `-ln(P(y_over))`. Statistic G = mean(shipped log-loss) - mean(halved log-loss); positive means halving helped. Game is the unit; paired bootstrap 2,000 draws, seed 7.

**Sample required:** at least **100 games** and **3,000 rows**. Read **once, on or after 2026-11-18**, using every qualifying row through 2026-11-17.
If the sample is short, the read waits for it and the window does not stretch.

**GO (shadow-track the halved blend for those four weeks):** G > 0 at t >= 2.5 and the same sign in both halves of the window. **Shipped wins:** G < 0 at t <= -2.5 (the concern is rejected).
**Inconclusive:** anything else. A GO is a claim about the **first four weeks only**. The same comparison on the following four weeks (2026-11-18 to 2026-12-15) is reported when that window closes, with no verdict of its own,
so a gain that also shows up later is read as "the blend over-trusts the model all year", not "early season".

---

## What gets reported, and when

| Test | Runs | Reported as |
|---|---|---|
| 1. Cap the tail | once, 2026-10-25, after this file is committed | `docs/prop-calibration-results.md`, `data/prop_calibration_tests.json`, a row in `experiment-log.md` |
| 2. Last-look gate | first night the sample rule is met, about 2026-11-15 | same files, appended; counts only until then |
| 3. Early-season weight | once, on or after 2026-11-18 | same files, appended; counts only until then |

Until Tests 2 and 3 are read, the runner prints **row counts only** (how many bets and leans qualify, by arm for Test 2). It prints no ROI, win rate or log-loss for them, so the dry runs cannot become peeks.

## Corrections made before anything was scored

- 2026-10-25, before the runner existed: (a) the Test 2 data line said pick'em rows carry no price; some do (the ledger stores a price for them). The rule is simply "a stored price".
  (b) Test 1 condition 4 now says how t is computed, and the 90th percentile is given as an index. Neither changes what is tested.
