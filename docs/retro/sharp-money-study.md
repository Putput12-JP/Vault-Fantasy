# Sharp money study (2026-09-28)

Question: can Vault tell where sharp money is? Two free sources were tested.

## 1. Pinnacle vs the recreational books (sportsbook odds feed)

Replay of 268 saved versions of the odds feed, Weeks 1-3 2026. Each book's line
de-vigged to a fair margin / total.

- When Pinnacle sat 0.5+ pts off the rec books' median 3h+ out, the rec books
  moved toward it by kickoff 19 times, away 7 (spreads, one per game, +0.50 pts).
- Control: FanDuel treated as "sharp" did 14-6 (+0.34). An off-the-pack book gets
  pulled back toward the pack whoever it is.
- About 24h out, no single book beat the median of the other books at predicting
  the close. Pinnacle ties Caesars / Fanatics / DraftKings / BetOnline.
- Verdict: tracked, not shown in the app. `snapshot-game-history.mjs` logs it live;
  the model scoreboard grades it (GO = 50+ games and Pinnacle beats FanDuel by 2 SE).

## 2. Polymarket accounts (public trade tape)

613 settled NFL games (Sep 2024 - Sep 2026), 31k pre-kickoff $1k+ taker trades on
the full-game moneyline. Score per trade = closing price of the side bought / price
paid - 1. Accounts scored walk-forward (only games before the one being judged).

| Account group (from past trades) | Later trades | vs the close |
|---|---|---|
| Sharp (t >= 2, 10+ trades, 5+ games) | 2,684 | +0.38% (t 7) |
| Middle | 6,934 | 0.0% |
| Usually losing (t <= -2) | 4,871 | -0.90% (t -21) |
| New / thin | 11,205 | -0.62% |

- Skill persists: sharp accounts keep beating the close, losing ones keep losing.
- Trade size alone is not skill: even $100k+ tickets lose to the close on average.
- But the edge is gone fast. Copying a sharp account's side: within 30 min +0.09%,
  30 min - 2 h later -0.19%, 2 - 6 h later -0.90% vs the close.
- By kickoff the price has priced them in: the side sharp accounts net-bought won
  58.1% vs the 59.2% the close implied (260 games). Fading usually-losing accounts
  at $10k+ net: their side won 55.2% vs 59.9% implied (221 games, 1.5 SE, unproven).
- Verdict: context only (where informed money went), never a bet to copy. Vault
  polls Polymarket hourly; the edge lasts minutes.

Code: `scripts/build_pm_wallets.py` (weekly scorecard, `data/pm_wallets.json`),
`scripts/fetch-polymarket.mjs` (hourly 24h split: $1k+ tickets, sharp accounts,
usually-losing accounts per market).
