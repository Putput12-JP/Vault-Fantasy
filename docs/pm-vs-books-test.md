# Polymarket vs the sportsbooks: who is right when they disagree? (pre-registered)

Written and committed before any result was computed. Data: the Pendulum Flow Polymarket orderbook archive
(archive.pendulumflow.com, CC BY 4.0, credit "pendulumflow") and our own sportsbook snapshots.

## The question

NFL moneylines on Polymarket are deep (about $400,000 resting within 1 cent of the best price before Sunday kickoffs,
$18 million lifetime per game). If Polymarket's price is the better read of where the market is going, a sportsbook
still hanging a different price is stale, and the side Polymarket favors is worth betting at that book. If instead
Polymarket follows the books, there is nothing to bet.

## Data

- **Sportsbooks:** every committed snapshot of `data/lineup-feed.json` (`vegas_games`) from 2026 week 1 through week 4,
  read from git history. Observation time = the file's `generated` stamp. Each snapshot carries 15 books' moneylines
  (Pinnacle, DraftKings, FanDuel, BetMGM, Caesars, bet365, Fanatics, BetRivers, Hard Rock Bet, and others). Snapshots
  with no live sportsbook source in `vegas_meta` are skipped. Only snapshots before kickoff count.
- **Polymarket:** the archive's `last_trade_price` rows for each game's moneyline market (both outcome tokens; a trade on
  the away token at q is a home price of 1 - q). Polymarket's price at time t = the size-weighted average price of
  trades in the 15 minutes before t; with no trade in that window the observation is skipped. Polymarket close = the
  same at kickoff.
- **Closing prices:** a book's close = its last snapshot before kickoff. Pinnacle's close is the primary truth because
  it is independent of Polymarket.
- Vig removed proportionally from every two-sided book price (the same way the app does).
- Games are matched by team and kickoff (Polymarket event slug and outcome names to our team codes).

## Measures (fixed now)

1. **Who closes the gap.** For each snapshot and game: gap = Polymarket home chance - consensus home chance, where
   consensus = the median no-vig home chance of the US retail books (DraftKings, FanDuel, BetMGM, Caesars, bet365,
   Fanatics, BetRivers, Hard Rock Bet). Then regress the consensus move to its close on the gap (beta_books) and the
   Polymarket move to its close on minus the gap (beta_pm). Standard errors by bootstrap over games.
   **Polymarket leads** if beta_books > beta_pm and beta_books is at least 2 standard errors above zero.
2. **The bet.** At each snapshot, for each retail book whose no-vig home chance is 3+ points away from Polymarket's,
   take the side Polymarket favors at that book's price (one bet per game, book and side: the first time it triggers).
   Closing-line value = Pinnacle's no-vig close for that side divided by what the book's price charged, minus one.
   **GO** if the average closing-line value is above zero by 2+ standard errors (bootstrap over games). Reported, not
   used for the verdict: the same against Polymarket's close, the win-loss result, and thresholds of 2, 4 and 5 points.
3. Spreads and totals at the same number (a book line that matches a Polymarket ladder line) are reported as
   secondary, not used for the verdict.

## What happens next

- **GO:** a "Book behind Polymarket" signal on NFL Game Markets and the Sharp Money watch, graded live from week 5 on
  (forward test); it is called proven only if the live record agrees.
- **NO-GO:** Polymarket stays context and a closing-price reference only.
- Either way, the archive supplies exact Polymarket closing prices for grading NFL and NBA game calls.

## Limits stated now

- Snapshots are hours apart, so this measures who is closer to the close, not minute-by-minute timing.
- A book snapshot is as fresh as the feed it came from; a few minutes of feed delay make books look staler than they
  were, which favors Polymarket. Reported alongside the result: the share of triggers where the book had moved since
  the previous snapshot.
- Four weeks is about 60 games; the result is a first read, and the forward test decides.

## Result and re-test (added 2026-10-01, after the run)

Results: docs/pm-vs-books-results.md. The sample is every game played through Sept 29, which is weeks 1-3 (week 4
starts Oct 1); "weeks 1-4" above meant everything played to date.

Both measures lean toward Polymarket being the better read: books close about half the gap toward Polymarket (0.47)
while Polymarket closes little of it toward the books (0.16), and the bet beat Pinnacle's close by 3.1% at the
pre-registered 3 points, more at wider gaps. Neither clears 2 standard errors. The limit is the sample: the lineup
feed fetches sportsbook lines 2 to 4 times a day, so three weeks give 71 snapshots, 226 moments with a Polymarket
trade alongside, and 28 bets at 3 points. The 4- and 5-point rows were reported, not pre-registered, and are too small
to act on. **Verdict: NO-GO.** Polymarket stays context and a closing-price reference.

**Re-test, declared now, before the data exists:** the same rules, unchanged, on NFL weeks 4 through 7 alone (every
game from Oct 1 on), run after week 7 settles. No overlap with the first sample. If it passes, the signal ships as a
forward test; if not, the idea is closed. Sportsbook moneylines will be snapshotted more often before then to grow the
sample; the observation time stays the time the book line was fetched.
