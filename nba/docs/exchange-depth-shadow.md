# Exchange depth shadow: does resting exchange size on a prop side predict the close?

Written 2026-11-18, before any forward row exists. This is a scope and registration. Nothing here is a pick, a size, a gate or an agree total.
Sharp money is context only (CLAUDE.md).

## Why this test

BetSniper's Smart Money page (teardown: 2026-11-16) lists NBA props where resting orders on Kalshi, Polymarket, Novig and ProphetX sit against
one side, next to the best US book price. It has no record, a signal bar that looked the same on every row, and says itself that it is not an
EV figure. Resting orders are offers anyone can post, so they are not evidence of skilled bettors. We do not know whether depth predicts
anything. This measures it before any of it is shown.

## What we already have (checked in the repo, not assumed)

- Novig props: `nba/scripts/novig.py` reads a ladder per (player, stat): strike, over bid and ask, mid, depth in dollars within 3 cents of the
  best price, and flow. Props rotate by market under a request budget, so not every prop is read each poll.
- Kalshi props: ladders enter `nba/scripts/prop_board.py` as `kal` entries with strike, price and size on each side.
- Book lines and prices, the Props Simulation record (`psim`) and the last pre-tip row, which the existing closing-line shadow
  (`nba/scripts/clv_shadow.py`, `nba/docs/clv-shadow.md`) already uses.

## What we do not have

- ProphetX: not in any feed. It is out of this test.
- Pinnacle limit and x-limit per prop: not stored. Out of this test.
- Polymarket NBA player props: not confirmed in the board. Included only if the first build step finds stored depth for them. If not, it is
  reported as absent, not estimated.

## Rule (frozen)

For every NBA prop with an exchange read (Novig or Kalshi) and a best US book price at the same line, at a look before tip:

- **Exchange side:** the side the exchange prices above the best book's no-vig price for that side. Gap = exchange mid probability minus the
  best US book no-vig probability for that side, in probability points, using the stored price only.
- **Depth:** resting dollars within 3 cents of the best price on that side, as stored.
- **Cohort A (registered):** gap >= 3 points and depth >= $250 on the exchange side.
- **Control B:** gap >= 3 points and depth under $100. Same gap, no size. If B moves like A, depth adds nothing beyond the price gap.
- **Control C:** depth >= $250 and gap under 1 point. If C moves like A, depth is only a liquidity marker.
- **First look** is the earliest qualifying read of a prop on a line. **Last look** is the last pre-tip row on the same line.
- **Primary measure, CLV:** how far the no-vig book price moved toward the exchange side from first to last look, in probability points.
- **Secondary, context only:** win rate of the exchange side at the first-look book price, reported with its interval. No ROI is quoted
  (there is no stake). Never used for a verdict.
- Props that change line between looks are left out and counted.
- One observation per prop x line x look, the mean over exchanges if both read. Standard errors are clustered by game.
- No number is invented. A missing price, depth or close leaves the row out and counts it.

## Samples

- DISCOVERY: none. There is no stored history of depth to fit on, so there is no look-back and nothing is tuned.
- FORWARD: snapshot days from 2026-11-19 (Central) onward. Interim reads are report-only until the bar below.

## When the test is cleared

All of these, for cohort A:

1. n >= 500 observations and >= 30 games;
2. mean CLV minus 2 standard errors is above 0;
3. the same sign in the first and second half of the sample by game date;
4. neither control B nor control C is itself cleared.

A clear lets the user consider showing exchange-versus-book depth as a labeled context strip on the prop detail page. It does not create a
signal, a size, a gate or a Top Reads input, and a clear is read again on the next 500 observations before anything ships.

**Kill:** mean CLV minus 2 standard errors below 0 at n >= 500. The strip is not built.

## Build plan (separate PRs, nothing user-facing here)

1. **Recorder (shadow):** append qualifying reads (prop, line, side, exchange, gap, depth, book price, timestamp) to the daily snapshot
   beside `psim`. Read-only on existing feeds; no extra requests beyond the budgets already in `novig.py`.
2. **Grader:** `nba/scripts/exchange_depth_shadow.py`, modeled on `clv_shadow.py`, stateless, rebuilt from the records each run, with a
   workflow beside `nba-clv-shadow.yml`.
3. **Read:** a results doc when the bar is met. Only then a decision on a context strip.

## Not in this PR

No UI, no changelog entry, no change to Top Reads, SM_GATE, Sharp Plays, a record, or any stored data. There is no tracking change, so no
historical data or record needs fixing. This PR adds this document only.
