# Exchange price gap against the US books (pre-registered, shadow, context only)

Written 2026-11-18 (Central), before any row of this test exists. Registration only: this PR adds this document and nothing else.
The recorder and grader are separate PRs, written after this one merges.

## How this differs from `p_dep`

`docs/exchange-depth-prereg.md` (PR 447, merged 2026-11-16) asks whether the **heavier side of a Novig book** is where **Pinnacle's close**
ends up. It names this test as a separate registration: "A price edge against the books is a separate test and would need its own
registration." This is that test. It leaves `p_dep` untouched, shares none of its thresholds, and is read on its own.

| | `p_dep` (already running) | this test |
|---|---|---|
| Exchange | Novig | Novig and Kalshi, read separately |
| Trigger | one side has $500+ and 2x the other | the exchange prices a side at least 3 points above the US books |
| Graded against | Pinnacle's close at the same line | the US books' own last pre-tip price at the same line |
| Question | does depth point where Pinnacle ends up? | does a price gap plus size predict a US-book move toward the exchange? |

## What is stored today (checked on `nba-data`, snapshots/2026-11-18)

- **US book prop prices:** `actionprops.jsonl`, one row per prop x book x side `[line, american price]`. This is the book side of the gap.
- **Novig:** `novigprops.jsonl` (bid, ask) and `novigdepth.jsonl` (per-side dollars within 3 cents of the best bid, rounded to $100).
- **Kalshi:** `kalshi.jsonl` stores yes bid and ask per rung. **Contracts resting at the best price are held in memory only
  (`snapshot.py` `KAL_SIZE`) and are not written to a day file.** There is no Kalshi depth history and nothing to backfill.
- **Not stored, so out of this test:** ProphetX, Pinnacle's per-prop limit, Polymarket NBA prop depth.

## What the recorder PR adds (not in this PR)

A day file `kaldepth.jsonl` beside `kalshi.jsonl` (built in the recorder PR, `nba/scripts/kal_depth.py`): per prop rung
`[yes bid, yes ask, over $, under $]`, over $ = bid x contracts at the best yes bid, under $ = (1 - ask) x contracts at the best yes ask.
Kalshi contracts pay $1, so dollars = price x contracts, rounded to $10. **Top of book only**: the market list gives the best level, so
Kalshi depth is not the same measure as Novig's (orders within 3 cents of the best bid), and the thresholds below are read per exchange.
No new requests: the sizes are already read each poll.

## Rule (frozen)

- **Unit:** one prop x line x side, per exchange (Novig and Kalshi are separate samples; a prop on both is two rows, and they are never averaged).
- **Book price:** the best (highest probability for that side) no-vig price among the US books in `actionprops` at the same line. A prop with
  fewer than 2 US books, or no price at that line, is left out and counted.
- **Exchange price:** the exchange's mid for that side at the same line (bid/ask mid; a quote wider than 10 cents is left out, as `novig.TIGHT`).
  Kalshi's fee is not added: the test is about direction of the book move, not a bettable edge.
- **Gap:** exchange mid probability minus the best-book no-vig probability for that side, in probability points.
- **Cohort A:** gap >= 3 points and exchange depth on that side >= $250.
- **Control B:** gap >= 3 points and depth under $100. Same gap with no size.
- **Control C:** depth >= $250 and |gap| under 1 point. Size with no gap.
- **First look:** the first pre-tip read where the row qualifies, with its time and both prices kept. One row per prop x line x side x exchange.
- **Last look:** the last pre-tip US-book price stored at the same line (`actionprops`). A row whose line changed, or with no later look, is
  left out and counted. No close is estimated.
- **Primary measure:** how far the best-book no-vig probability for the exchange's side moved from first to last look, in probability points
  (positive means the books moved toward the exchange).
- **Context, not tests:** win rate of the exchange side at the first-look best-book price with its interval, and the overlap with `p_dep`
  alerts on the same prop. No profit number is quoted: no stake is recorded.
- Standard errors are clustered by game. A missing price, depth or close leaves the row out; no number is invented.

## Sample

- **Discovery:** none. Depth for this test was never stored, so nothing is fitted and no threshold was tuned on data.
- **Forward:** snapshot days from the first day `kaldepth.jsonl` exists (the recorder PR states that date in its description before any row is
  graded). Interim reads are report-only.

## When a test is cleared

Each exchange x cohort is read separately. Cohort A on an exchange is **cleared** when all hold:

1. n >= 500 observations across >= 30 games, and not before four weeks of recorded days;
2. mean movement minus 2 standard errors is above 0;
3. the same sign in the first and second half by game date;
4. neither control B nor control C on that exchange is itself cleared.

Two exchanges at 2 standard errors is not a multiple-test correction, so a clear is read again on the next 500 observations before it ships.
A clear lets the user consider a labeled context line on the prop page (exchange price versus best US book). It makes no signal, size, gate,
Top Reads input or agree total.

**Kill:** mean plus 2 standard errors below 0 at n >= 500 for an exchange (the data rule out a move toward the exchange). That exchange's strip is not built. A mean that is not cleared but is not below zero by that margin is read as not cleared and is read again on the next 500.

## Known limits

- Books move toward whoever is sharper or later, and Pinnacle usually leads; a US-book move toward an exchange may be those books catching up
  to Pinnacle, which `p_dep` measures separately. A clear here means the exchange gap leads the US books, not that anyone beats a number.
- Resting size is offers, not fills, and exchange accounts are anonymous.
- Novig rotates its prop reads under a request budget, so a first look can be a few polls after the gap appeared.
- `p_dep` reads on or after 2026-12-07. This test reads later, so neither result is used to tune the other.

## Not in this PR

No code, UI, changelog entry, record or data change. No tracking change, so no history or record needs fixing. Sharp money stays context only
(CLAUDE.md): nothing here feeds Top Reads, SM_GATE, Sharp Plays or an agree total.
