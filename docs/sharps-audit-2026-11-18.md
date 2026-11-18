# Sharps audit and plan, 2026-11-18

Question: why do the Proven Sharps plays lose, and what would make following Polymarket wallets profitable?
Short answer: **the "proven" label is hindsight, not skill. Nothing I tested supports a claim of positive ROI today. Below is
what the data does support and a plan that tests it honestly.**

Data used: the 669,840 wallet-position rows in the ledger (`sharp-history`, Apr 2024 to Nov 17 2026, NBA/NFL/CFB/CBB), the 119
graded shown plays and every frozen keyframe (`pm-holders-data`, Nov 11 to Nov 17), `data/pm_wallet_rank.json`, and the earlier
research in `docs/pm-*-results.md`. No external research was done; this is our own data only. Scripts: `scripts/sharps_audit_nov18/`.
ROI is flat 1 unit per position unless stated. t is ROI divided by its standard error (rows in one game are correlated, so
real t is somewhat lower).

## 1. Where the shown plays lose (119 graded plays, 60-59, -9.05u, -8.9% ROI)

| Slice | Record | Units | n |
|---|---|---|---|
| NFL | 12-6 | +7.75u | 18 |
| NBA | 16-13 | -2.84u | 29 |
| CBB | 13-17 | -6.30u | 30 |
| CFB | 19-23 | -7.65u | 42 |
| Moneyline, all sports | 26-25 | -7.65u | 51 |
| 1.5u plays | 0-5 | -7.50u | 5 |
| Price .35 to .50 | 19-27 | -9.10u | 46 |

- CFB plays cost an average 54.7c and won 45.2%. CBB cost 51.8c and won 43.3%. The plays are priced like coin flips and lose
  like coin flips, which is what no edge looks like.
- The size ladder is neutral. Flat 1u is -10.58u, shown size -9.05u. Fixing sizing cannot fix this.
- 119 plays cannot tell a +5% edge from -9%: one standard error on ROI is about 9 points. Judging by this record alone is noise.
  The NFL +7.75u is 18 plays.

## 2. Why: "proven" is picked with hindsight

The universe is built from Polymarket's all-time and monthly PnL leaderboards, read in Nov 2026. Those wallets are on the board
because they won, including in the games we then test them on. The card calls a wallet proven at n >= 6, win rate >= 55%,
dollar ROI > 3%. Walk-forward on the ledger (a wallet's record known only from games settled before each cut):

| Test | Result |
|---|---|
| All 400,204 usable positions, backfill | NBA +1.6%, NFL +1.2%, CFB +1.5%, CBB +2.5% (hindsight universe) |
| Same rows, forward only (Nov 11 to 17, n = 21,680) | NBA +1.0%, NFL -3.6%, CFB +3.1%, CBB +1.6%; all sports +0.9% (t 1.1) |
| Card "proven" rule vs not, backfill, NBA | +0.6% vs +1.5%: **the label carries no signal** |
| Card "proven" rule, forward only (n = 2,138) | **-6.4% (t -3.0)** NBA -4.8%, NFL -9.6%, CFB -11.0%, CBB -2.5% |
| Backfill signal "tracked-wallet money share >= 70%" | looked +7% (t 13) in both train and test halves |
| Same signal, forward only (n = 6,387) | +1.5% (t 1.1) |
| Backfill "skilled for, none against", test half | +4.6% NBA, +3.7% CFB, +3.7% CBB |
| Same signal, forward only (n = 5,356) | -2.5% (CBB -8.0%) |

Every backfill edge, including ones that held in an out-of-time split, vanished forward. A time split does not fix survivorship,
because the wallet list itself was chosen after the fact. **No rule fitted on backfill rows can be trusted, ours or SharpFlow's.**
Their "+4.5% record" has the same flaw (`docs/sharpflow-teardown.md`).

## 3. What is not the problem

- **Entry timing is not the leak.** On 14,940 NBA and NFL positions matched to keyframes, a wallet's average price was 49.6c and
  the T-15 market price was 49.3c. Wallets do not buy meaningfully better than the cut, so following at T-15 gives up little. There
  is no big early-entry edge to be missed.
- **The market is calibrated.** Across 9,488 sides in the keyframes (every holder, no selection), betting every side at mid returns
  NBA +0.2%, CFB +1.8%, CBB +0.3%, NFL -5.8% (n = 878). All-holder money share shows no edge: 80%+ of money on a side returns
  +2.2% (n = 92). Money on one side is not information.
- **Lag matters only for the few with CLV.** The copy test (`docs/pm-accounts-copy-results.md`) found copying 15 minutes later is
  +0.09% vs the close (SE 0.59, 36 copies). The accounts that beat the close do so at the moment they trade, and the gap closes.

## 4. What the data does hint at (all small samples, all flagged for close monitoring)

CLV, not win rate, is the real skill measure: a wallet's CLV persists (rank file rho 0.95), win rate does not. Only a few wallets
pass: 4 of 311 NBA, 5 of 489 NFL after FDR, and 11 "proven" of 2,094 ranked. Using those tiers on the unbiased keyframe sides
(Nov 11 to 17, mid price plus 1c ask):

| Candidate | NBA | NFL | CFB | CBB | All |
|---|---|---|---|---|---|
| Follow CLV-ranked sharps, none against (ask) | +2.2% (n 278) | +15.2% (n 73) | -13.6% (n 178) | -6.1% (n 190) | -2.6% (n 719) |
| Fade sides where a dull (negative CLV) wallet is, none against (ask) | +3.0% (n 162) | +37.1% (n 37) | +1.6% (n 27) | n 4 | +9.3% (n 230) |

- **Flag: fade dull money, +9.3% on 230 sides, t 1.0.** Not significant. NFL +37% is on 37 sides.
- **Flag: CLV-ranked sharps in NFL/NBA, +15.2% (n 73) and +2.2% (n 278).** Not significant.
- **CFB and CBB reverse.** Ranked sharps lose there (-13.6%, -6.1%) and the college moneyline is thin (4.6 trades per game
  in `docs/pm-spread-total-results.md`). College sharp plays should not carry a size.
- NBA backfill "losers" (prior ROI < -5%) won +4.0% in train and lost -3.0% in test. The sign flips, so it is noise.

## 5. Power: the registered tests cannot see a realistic edge

ROI on a coin-flip bet has a standard deviation near 1.0 per bet. With 300 locks per sport (`docs/sharp-card-prereg.md`) one
standard error is 5.8 points, so a pass needs a true edge near +11%. A real edge of +3% needs about 4,300 bets for t = 2. CLV has
a standard error near 0.3 points on a few hundred trades, so **CLV against the close is the metric that can be read this season.**
ROI stays as the second line. This is already half in the prereg (CLV is required for NBA/NFL); the plan makes it the lead.

## 6. Plan

**Step 0, now (needs your decision, CLAUDE.md exception):**
1. Stop labelling n >= 6 wallets "proven". Rename the class on the card and page to "Hot wallets" or "Tracked". Keep a "Proven"
   badge only for CLV-ranked tiers.
2. Show the suggested size as flat 1u, and show none on CFB and CBB, until a forward test says otherwise. The ladder adds
   variance and no return (shown -9.05u vs flat -10.58u on the same plays). Keep the "untested rule" label.
3. Fix the closes feed (`data/pm_closes.json` has no game after Oct 30). Without it no NBA/NFL play gets a CLV. The open branch
   `closes-batch-by-hour` is this fix; it is the critical path for everything below.

**Step 1, wallet skill from CLV, point in time.** One skill table: Bayesian CLV posterior per wallet per sport
(`scripts/rank_pm_wallets.py`), FDR-controlled, minimum 30 graded trades, recomputed nightly, tiers recorded with a timestamp.
Three classes: ranked sharp (proven/probable, 52 wallets today), dull (persistent negative CLV), everyone else. Win rate and
dollar PnL stop being selection inputs. Leaderboard-sourced wallets stay in the universe for coverage but every row from before
the wallet was added is `backfill` and never enters a performance claim.

**Step 2, freeze the universe and the rule, then register (new dated prereg, old ones still read as written).** Candidates, per sport,
NBA and NFL only, moneyline, spread and total reported separately, never pooled, bet at the ask:
- A. A ranked sharp on the side, no ranked sharp and no dull wallet against.
- B. Dull money on a side, fade the other side. Do not require a sharp.
- C. A and B together.
Primary read: CLV against the close, at the ask the card shows, with a 95% bootstrap lower bound above 0 and n >= 300 trades.
Secondary: flat ROI with its interval. Everything starts as a shadow beside the card, never on it.

**Step 3, speed.** CLV is earned at trade time. Poll the trade feed for ranked wallets on NBA/NFL every 30 to 60 seconds, record the
ask at detection and the latency, and paper-follow. `data/pm_account_speed.json` has the speed profiles. Promote an alert only
if CLV at detection ask clears 2 standard errors with n >= 100. If the edge is gone inside one minute, the product answer is
"context after the fact", and that is a fine result to publish.

**Step 4, combine with Vault's own price edge.** Test ranked-sharp agreement as a boost or veto on the existing model rules
(for example the NBA fair-agreement rule, 29-12 in-sample on n = 41, which is too small to build on). Sharp money stays out of
Top Reads and every agree total unless you change CLAUDE.md on forward evidence.

**Step 5, kill rules, written in advance.** Drop a candidate if its CLV interval is below 0 at n >= 300, or if forward ROI
interval lies below 0 at n >= 1,000. Never promote a slice on the data that found it.

## 7. Honest expectation

The best evidence in hand is a small CLV edge for a handful of wallets in NBA and NFL, mostly gone by T-15, on markets where one
cent of spread is about 2% of a bet. A positive ROI is possible on a narrow set (NFL, NBA, ranked tiers, tight spread) but it is
not proven, and the sample to prove it does not exist until about the end of this NBA season. I did not find, and will not
invent, a rule that makes today's shown plays profitable.
