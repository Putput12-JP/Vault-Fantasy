# Sharp Polymarket accounts: how long does their edge last? (pre-registered)

Written and committed before any result was computed. Builds on docs/retro/sharp-money-study.md, which found that
accounts with a winning record against the close keep beating it, but that copying them 30 minutes or more later
lost money. That study priced the copy at later trade prices, an approximation. The Pendulum Flow orderbook archive
(archive.pendulumflow.com, CC BY 4.0) has the exact best bid and ask at every moment, so the copy can be priced at
the ask a follower would actually have paid.

## The question

If Vault sees a sharp account's trade some minutes later and buys the same side at the best ask then, does it beat
the closing price? And how fast does the market move toward these accounts after they trade?

## Data

- **Trades:** $1,000+ taker trades on each game's full-game moneyline before kickoff, with the account, from
  Polymarket's trade API (the same unit as `scripts/build_pm_wallets.py`). A sell of one side is read as a buy of the
  other side at 1 minus the price.
- **Games:** every NFL game and every college football game whose kickoff falls inside the archive's high-grade era
  and the 2026 seasons: NFL weeks 1-3 (Sept 10-29) and college football from Aug 22 through Sept 28.
- **Quotes:** the archive's `best_bid_ask` for the token bought: the prevailing quote at any moment is the last one at
  or before it. Close = the mid of that token at kickoff (when its spread is 10 cents or less).
- **Account labels:** the NFL scorecard (`data/pm_wallets.json`) with every test game's trades removed, so each
  account is judged only on games before the test window. Sharp = t-stat 2+ against the close over 10+ trades in
  5+ games; usually losing = t-stat -2 or lower; same rule as the scorecard. NFL labels are used for college trades
  too (the earlier study found the skill travels).
- One copy per account, game and side: its first qualifying trade.

## Measures (fixed now)

1. **The copy (verdict).** For each sharp-account trade, buy the same token at the best ask d minutes later, for
   d = 2, 5, 10, 15, 30 and 60 minutes, when that moment is still before kickoff and the spread is 5 cents or less.
   Value = close / ask - 1. **Primary: d = 15 minutes** (the fastest Vault can realistically alert).
   **GO** if the average at 15 minutes is above zero by 2+ standard errors (bootstrap over games, NFL and college
   pooled). The other delays and each sport alone are reported, not used for the verdict.
2. **How fast the market moves toward them (reported).** Markout at d = mid of the token bought at d minutes after
   the trade / the price they paid - 1, for d = 1, 5, 15, 30, 60, 120 minutes and kickoff, for sharp, usually losing,
   and every other account. Also the spread they paid: their price against the mid at the moment of the trade.

## What happens next

- **GO:** sharp-account alerts show a copy window ("the market usually follows within N minutes; still worth
  copying for M minutes"), shipped as a forward test and called proven only if the live record agrees.
- **NO-GO:** sharp accounts stay context. The markout curve is published so the alerts can say how stale a
  sharp trade is likely to be by the time anyone sees it.
- Either way, each account's profile gains its measured speed (how much of its edge is in the price after 5 and
  30 minutes), from the same archive data.

## Limits stated now

- Copying at the ask assumes a small order; the archive cannot say what a large one would have paid beyond the touch.
- Only the high-grade archive era is used (from Aug 18, 2026), so the sample is about seven weeks of football.
- Labels rest on the scorecard's older seasons; accounts new this season are in the "every other" group.
