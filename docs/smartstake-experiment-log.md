# SmartStake experiments: rules fixed before any outcome is read

Written 2026-10-17 and committed before any graded result exists. The SmartStake tape starts 2026-10-17, no tape game has been
played, and every scorer prints 0 graded props. Internal research only: SmartStake's API terms allow storing and testing the
data but not publishing it or showing it without written permission (`docs/smartstake-permission-request.md`). Nothing in this
file or its results goes into a published number, grade, record or page.

If a rule here changes after outcomes arrive, it is added to the Amendments table at the bottom with the date and the reason, and
the result is reported against the original rule first. Nobody edits a rule above the table.

## 1. What has been looked at already (disclosed)

| When | What | Why it does not decide anything |
|---|---|---|
| 2026-10-17 | `smartstake_close_score.py --league nfl --selftest-week 5`: the current tape (Week 7 lines) graded against Week 5 box scores on purpose, to exercise the code. Printed 429 graded props, SS consensus minus FanDuel log loss +0.0002, SS consensus minus DraftKings 0.0000, sharp minus soft +0.0016, all "no difference". | Wrong week by design; output is marked invalid and never written. The rules below were not tuned to it. |
| 2026-10-17 | `smartstake_alt_ladders.py` first run: 91 ladders fitted, many at the top edge of the variance grid. | Counts and fit quality only, no outcomes. The edge rule in T8 comes from that observation. |
| 2026-10-17 | `smartstake_close.py`, `smartstake_lead_log.py`, `smartstake_book_weights.py` first runs. | 0 closes, 0 of 50 games, 0 graded rows. |

## 2. Window, data and what counts

- **Forward only.** NFL tests use games from Week 7 on (kickoffs 2026-10-18 onward). NBA tests use regular-season games from opening night, 2026-10-20 on. Preseason games and anything before the tape started are excluded.
- **A close** is a book's last read before kickoff (`updated_at` and pass time both before the start). A read at or after kickoff is live and dropped. A book must be two-sided within -500 to +500 (a wider quote is a skewed ladder rung, not a main line).
- **Shared line.** Each prop is scored at the one line the most books priced two-way, with at least 3 books. Ladder-style venues (Kalshi, Polymarket) are not used for the main line. Pushes are dropped. A player who did not play is void, not guessed.
- **Results** come from nflverse (NFL, via `settle_bets.actual_for`) and ESPN box scores (NBA, completed games with at least 300 player minutes).
- **Scoring** is log loss on the over chance, with a paired bootstrap (2,000 resamples) of the log-loss gap, A minus B, on props both priced. Negative means A is closer to the truth.
- **First read:** NFL on Wed 2026-10-21 after Week 7 settles. NBA when each test below first reaches its n. Reads before that are descriptive only and are logged, not acted on.

## 3. The tests (the family)

| ID | League | Question | Pass rule (all must hold) |
|---|---|---|---|
| T1 | NFL, NBA | SS consensus (mean de-vigged chance across at least 3 books) closer than FanDuel? | n of at least 150 shared props; 95% CI of the gap excludes 0 on the negative side |
| T2 | NFL, NBA | SS consensus closer than DraftKings? | same as T1 |
| T3 | NFL, NBA | Sharp books (Circa, Bookmaker, Novig, ProphetX; at least 2 priced) closer than the soft books (at least 2 priced)? | n of at least 150; CI of sharp minus soft excludes 0 on the negative side |
| T5 | NFL (3 apps), NBA (PrizePicks, ParlayPlay) | At a pick'em app's exact line, when at least 3 sportsbooks also posted that line and the consensus sits 4 or more points from 50%, does the leaning side hit more than the consensus chance? | lean count n of at least 150 per app; hit rate minus mean lean chance at least 2 standard errors, SE = sqrt(hit x (1 - hit) / n). No payout or ROI claim is made |
| T6 | NFL, NBA | Do Circa or Bookmaker game-line moves lead the market? (spread, total, moneyline) | at least 50 games for the lead book; gap over the better of FanDuel and DraftKings of at least 2 standard errors (as coded in `smartstake_lead_log.py`) |
| T7 | NBA | Fitted per-book consensus weights beat the hand-set `consensus.WEIGHTS` (Pinnacle 3.0, others 1.5)? | existing ship rule unchanged: second-half ROI above 0, z of at least 2, 50 or more games; weights chosen on the first half by tip time only, scored on the second half |
| T8 | NBA | Ladder-fitted mean and variance (variance scalar s, grid 0.5 to 5.8) beat s = 1 on held-out results? | paired log-loss gain z of at least 2 on 50 or more games, second half only; any fit with s on the top edge of the grid is excluded from the gain, not trusted |

Family size m = 25: NFL 12 (T1, T2, T3, T5 for 3 apps, T6 for 3 markets x 2 lead books) plus NBA 13 (T1, T2, T3, T5 for 2 apps, T6 for 3 markets x 2 lead books, T7, T8). A test is called only if (a) its pass rule above holds AND (b) its Holm-adjusted one-sided p across
m = 25 is below 0.05. For the bootstrap tests p comes from the normal approximation of the printed gap and CI (SE is about
the CI width divided by 3.92). Anything that passes (a) but fails (b) is reported as WATCH, not GO.

## 4. What a pass or fail means

- **Pass:** the finding may be carried into a SHADOW blend or shadow log only. It does not change any published price, grade, Vault line, record or page. Publishing anything derived from SmartStake needs their written permission and a separate decision.
- **Fail or "too few":** logged as tracking (n of its bar) or NO-GO. A failed test is not rerun on the same games with a different rule.
- **No ROI claim** is made from any test here. Closes measure who is closer to the truth, not whether a price can be beaten after vig.

## 5. Amendments

| Date | Test | Change | Reason |
|---|---|---|---|
| (none yet) | | | |
