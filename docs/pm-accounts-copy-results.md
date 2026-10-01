# Sharp Polymarket accounts: copy test results

Rules: docs/pm-accounts-copy-test.md (committed before this ran). Quotes from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0).

Games: 268 (46 NFL weeks 1-3, 222 college). First $1k+ trades per account, game and side: 2142 (sharp 40, usually losing 52, other 2050). Labels from the NFL scorecard with 46 test games taken out.

## 1. Copying a sharp account at the ask, d minutes later (vs the close)

| Delay | Copies | Games | Average vs close | SE | NFL | College |
|---|---|---|---|---|---|---|
| 2 min | 38 | 27 | +0.13% | 0.60 | -1.17% | +1.58% |
| 5 min | 38 | 27 | +0.05% | 0.56 | -1.02% | +1.23% |
| 10 min | 38 | 27 | +0.20% | 0.57 | -1.00% | +1.54% |
| 15 min (pre-registered) | 36 | 27 | +0.09% | 0.59 | -1.00% | +1.31% |
| 30 min | 33 | 25 | +0.12% | 0.64 | -1.01% | +1.66% |
| 60 min | 26 | 21 | +0.59% | 0.70 | -0.70% | +1.87% |

Verdict: **NO-GO** (rule: average at 15 minutes above zero by 2+ standard errors).

## 2. How the market moves after their trade (mid of the side bought vs the price paid)

| Accounts | Trades | Spread paid | 1 min | 5 min | 15 min | 30 min | 60 min | 120 min | Kickoff |
|---|---|---|---|---|---|---|---|---|---|
| Sharp | 40 | +0.57% | -0.18% | -0.01% | -0.10% | -0.05% | +0.32% | +0.76% | +1.05% |
| Usually losing | 52 | +0.73% | -0.70% | -0.64% | -0.42% | -0.30% | -0.35% | -0.34% | -0.63% |
| Everyone else | 2050 | +0.78% | -0.67% | -0.56% | -0.48% | -0.33% | -0.24% | -0.20% | +0.03% |

Spread paid = their price against the mid at the moment of the trade (a taker pays about half the spread).
Account speed profiles: data/pm_account_speed.json (181 accounts with 3+ test-window trades).

