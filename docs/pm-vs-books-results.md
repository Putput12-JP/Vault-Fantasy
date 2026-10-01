# Polymarket vs the sportsbooks: results

Rules: docs/pm-vs-books-test.md (committed before this ran). NFL 2026 weeks 1-4, moneylines. Polymarket from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0).

Games matched: 51 (0 without a Pinnacle close). Sportsbook snapshots: 71 fetched, changed snapshots. Game-moments with both prices: 226.

## 1. Who closes the gap

- Books move toward Polymarket: beta_books = **0.47** (SE 0.26)
- Polymarket moves toward the books: beta_pm = **0.16** (SE 0.25)
- Verdict: **Polymarket does not lead** (rule: beta_books > beta_pm and beta_books >= 2 SE above zero)

## 2. Betting the book side Polymarket favors (3+ points apart)

| Threshold | Bets | Games | CLV vs Pinnacle close | SE | CLV vs Polymarket close | Book had just moved | Record | Return |
|---|---|---|---|---|---|---|---|---|
| 3 pts (pre-registered) | 28 | 14 | +3.10% | 2.05 | +3.77% | 18% | 18-10 | -3.7% |
| 2 pts | 103 | 36 | +0.09% | 1.07 | +0.88% | 41% | 64-39 | -10.2% |
| 4 pts | 10 | 9 | +9.07% | 4.66 | +10.01% | 20% | 8-2 | +22.4% |
| 5 pts | 5 | 4 | +18.68% | 6.57 | +18.45% | 0% | 3-2 | +5.0% |

Verdict: **NO-GO** (rule: mean CLV vs Pinnacle's close >= 2 SE above zero at 3 points).

By book (3 points): DraftKings 8, FanDuel 3, BetMGM 5, Fanatics 1, BetRivers 4, Hard Rock Bet 7

## Reading it

Both measures lean toward Polymarket being the better read: books close about half the gap toward Polymarket
(0.47) while Polymarket closes little of it toward the books (0.16), and the bet beat Pinnacle's close by 3.1% at the
pre-registered 3 points, more at wider gaps. Neither clears 2 standard errors. The limit is the sample: the lineup
feed fetches sportsbook lines 2 to 4 times a day, so four weeks give 71 snapshots and 226 moments with a Polymarket
trade alongside, and only 28 bets at 3 points. The wider-gap rows (4 and 5 points) were reported, not pre-registered,
and are too small to act on.

Verdict: NO-GO. Polymarket stays context and a closing-price reference.

## Re-test, declared now (2026-10-01, before the data exists)

The same rules, unchanged, on NFL weeks 5 through 8 alone as a fresh sample (no overlap with weeks 1-4), run after
week 8 settles. If it passes, the signal ships as a forward test; if not, the idea is closed. To make that sample
bigger, sportsbook moneylines will be snapshotted more often before then (see the plan below); the rule that the
observation time is when the book line was fetched stays.
