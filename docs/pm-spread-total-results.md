# Sharp Polymarket accounts on spreads and totals: results

Rules: docs/pm-spread-total-test.md (committed before this ran). Script: scripts/pm_spread_total_test.py. Data: data/pm_spread_total_test.json.
Games: the 150 most recently settled per sport (NFL 150, CFB 150, NBA 150; NBA spreads/totals on 131). $1k+ pre-kickoff taker trades, CLV against the last trade before kickoff.

## Depth ($1k+ pre-kickoff taker trades per game)

| | Moneyline | Spread | Total |
|---|---|---|---|
| NFL | 80.7 | 36.5 | 15.0 |
| NBA | 104.6 | 31.1 | 21.7 |
| CFB | 4.6 | 3.5 | 2.3 |

## Test 1: accounts the moneyline scorecard calls sharp, on each market (mean CLV, SE)

| | Moneyline (control) | Spread | Total |
|---|---|---|---|
| NFL | +0.93% (0.09), n 2180 | +1.03% (0.09), n 1686 | +1.05% (0.18), n 576 |
| NBA | +2.89% (0.34), n 1938 | +1.23% (0.33), n 632 | +1.95% (0.21), n 477 |
| CFB | +1.70% (0.33), n 235 | -0.23% (0.49), n 174 | +0.09% (0.31), n 114 |

Dull accounts lose to the close on NFL spreads (-1.17%, t -9.2) and CFB/NBA mostly too thin or flat.

## Test 2: own-market skill, labelled on the first half, measured on the second

| | Spread | Total |
|---|---|---|
| NFL | +4.37% (0.59), n 104, 2 accounts | n 34 (too few) |
| NBA | +0.49% (0.29), n 382 (t 1.7) | +1.17% (0.38), n 110, 7 accounts |
| CFB | -0.16% (0.50), n 35 | no accounts |

## Verdict (rule: 2+ SE on 100+ trades)

- **NFL spread and total: GO** (test 1). Test 2 passes for spreads on 2 accounts, too few to lean on.
- **NBA spread and total: GO** (test 1). Test 2 passes for totals (7 accounts), spreads fall just short (t 1.7).
- **CFB spread and total: NO-GO.** 2-4 qualifying trades per game and CLV indistinguishable from zero. College moneyline itself is thin (4.6 per game).

## Read this with
- Test 1 is not fully out-of-sample (labels come from moneyline in the same games). Test 2 is clean but rests on few accounts.
- CLV here is measured at the moment of the trade against the close. It says these accounts get a better price than the closing line, not that a viewer who sees the trade later can profit: on moneyline, copying 15 minutes later was NO-GO (docs/pm-accounts-copy-results.md). Spreads and totals have not been copy-tested.
- So a spread/total net-money table is supported as context ("where informed money went"), not as a bet to copy.
