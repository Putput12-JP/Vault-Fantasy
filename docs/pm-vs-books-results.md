# Polymarket vs the sportsbooks: results

Rules: docs/pm-vs-books-test.md (committed before this ran). NFL 2026, every game played through Sept 29 (weeks 1-3), moneylines. Polymarket from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0).

Games matched: 48 (0 without a Pinnacle close). Sportsbook snapshots: 71 fetched, changed snapshots. Game-moments with both prices: 226.

## 1. Who closes the gap

- Books move toward Polymarket: beta_books = **0.47** (SE 0.26)
- Polymarket moves toward the books: beta_pm = **0.16** (SE 0.25)
- Verdict: **Polymarket does not lead** (rule: beta_books > beta_pm and beta_books >= 2 SE above zero)

## 2. Betting the book side Polymarket favors (3+ points apart)

| Threshold | Bets | Games | CLV vs Pinnacle close | SE | CLV vs Polymarket close | Book had just moved | Record | Return |
|---|---|---|---|---|---|---|---|---|
| 3 pts (pre-registered) | 28 | 14 | +3.10% | 2.05 | +3.77% | 18% | 18-10 | -3.7% |
| 2 pts | 103 | 36 | +0.09% | 1.03 | +0.88% | 41% | 64-39 | -10.2% |
| 4 pts | 10 | 9 | +9.07% | 4.66 | +10.01% | 20% | 8-2 | +22.4% |
| 5 pts | 5 | 4 | +18.68% | 6.57 | +18.45% | 0% | 3-2 | +5.0% |

Verdict: **NO-GO** (rule: mean CLV vs Pinnacle's close >= 2 SE above zero at 3 points).

By book (3 points): DraftKings 8, FanDuel 3, BetMGM 5, Fanatics 1, BetRivers 4, Hard Rock Bet 7

