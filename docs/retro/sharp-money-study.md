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

## 3. Other sports (2026-09-29)

The account scorecard now runs per sport (`build_pm_wallets.py --sport=cfb|nba`,
`data/pm_wallets_<sport>.json`). College football is thin on Polymarket: 560 games
this season but only 228 accounts made $1k+ trades, 6 of them sharp on their own
CFB record.

Skill travels across sports. Accounts that are sharp on their NFL record, judged on
their CFB trades (which were never used to label them):

| Group (labelled on NFL) | CFB trades | vs the close |
|---|---|---|
| NFL-sharp | 194 | +2.18% (t 7.0) |
| NFL-usually-losing | 57 | -0.38% (t -1.1) |
| Everyone else | 1,071 | +0.33% (t 2.7) |

NBA (195 most recent games, mostly the 2026 playoffs; closes there often fall
back to the last $1k+ trade before tip because in-game trading buries the true
close): NFL-sharp accounts +1.76% on 439 NBA trades (t 3.0), everyone else -0.17%.
The NBA scorecard has 32 sharp / 62 usually-losing accounts of its own.

So the live watch labels an account sharp in a sport where it has no record yet if
it is sharp in another sport, and says which sport it earned that in.

## 4. Sharp Money watch (live)

`scripts/fetch-sharp-money.mjs` polls Pinnacle (guest API: main + alternate lines,
limits), Action Network (bets % vs money %, opening line, five US books),
Polymarket (account-level tape) and Kalshi (big tickets) for NFL, CFB and NBA,
and turns changes into time-stamped alerts: Pinnacle steam, US book behind
Pinnacle (+EV priced from Pinnacle's own alt ladder, power de-vig, -300 to +300
only), sharp-account buys, big tickets, and money-vs-bets splits. Every alert is
graded against Pinnacle's last pre-game price (CLV) and the final score (ESPN).
State lives in `.claude/sharp-money/` (gitignored); a local scheduled task runs it
every 5 minutes and republishes the Sharp Money artifact. Nothing here is a Vault
pick until an alert type beats the close over a real sample.

## 4. Exact quotes from the orderbook archive (2026-10-01)

Pre-registered test: docs/pm-accounts-copy-test.md; results: docs/pm-accounts-copy-results.md. NFL weeks 1-3 and
college football from Aug 22, priced at the Pendulum Flow archive's best bid and ask (archive.pendulumflow.com,
CC BY 4.0) instead of later trade prices.

- Copying a sharp account at the ask 15 minutes later: +0.09% vs the close (SE 0.59, 36 copies). NO-GO; context only
  stands.
- After a sharp account trades, the mid of its side barely moves for 30 minutes, then drifts its way: +0.32% at an
  hour, +0.76% at two hours, +1.05% by kickoff. Usually-losing accounts: about -0.6% throughout. Takers pay about
  0.6-0.8% to cross the spread.
- 40 sharp-account trades is far too few to settle it; a re-test on the next four weeks is declared in the test doc.
