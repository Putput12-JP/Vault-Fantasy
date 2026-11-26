# Spread and total price floor: pre-registration (2026-11-25, 10:08 PM CT)

Written before any held-out number was computed. Asked by Jacob on 2026-11-25 (PR #585): with free exchange second prices, every
spread and total row that cleared the other gates went to Pass on the 55% price floor (`GATES.MIN_PRICE`). Does a lower floor for
spreads and totals win out of sample?

## Disclosure
On 2026-11-25 (about 5:30 PM CT) the PR #585 write-up counted, over the whole Oct 17 to Nov 25 Watch ledger, 73 Novig-qualified rows
that failed only the 55% floor and looked at their combined W-L. That look mixed both windows below. No floor was chosen from it,
and nothing split by window had been computed.

## Data (free, stored)
- Rows: `sharp-data/v2_watch.json` and `v2_passed.json`, kind `book`, market spread or total (deduplicated by id). Each holds the
  price at the book it names when it first showed (`first.price`), Pinnacle's no-vig fair then (`first.refs`), the result, and for
  some rows a stored close (`clv`).
- Novig second price at first sight: `data/book_tape/<sport>/*.jsonl` Novig rows (`nsp`, `ntot`: line, bid, ask), the last row at
  or before first sight. Liquidity is not in the tape, so the $1,000 floor cannot be applied; Kalshi and Polymarket spread/total
  quotes were never stored.
- Graded at the stored first-sight price (takeable then, no look-ahead): win pays 100/|am| (or am/100), loss -1, push 0, void out.

## Windows (first sight, Central time)
- Train: Oct 18 to Nov 8, 2026. Held-out: Nov 9 to Nov 25, 2026 (settled rows only).

## Populations
- **P1, the PR #585 rule as far as stored data allows:** Pinnacle plus a Novig quote at the exact number, tape row read within
  10 minutes before first sight, bid-ask 3c or less; Pinnacle and Novig within 4 points; worst edge 2% to 10%; under 48 hours out.
- **P2, wider stand-in:** Pinnacle edge 2% to 10%, under 48 hours (no second price required).

## Floors
52%, 53%, 54%, against the current 55%. For each: the full set at price >= floor, and the added band [floor, 55%).

## Choice on train, then one test
On train, pick the floor whose added band has the best ROI in P1 with 30+ settled rows; if no band reaches 30, pick in P2.
Then report every floor on held-out, P1 and P2, with W-L-P, units, ROI, mean CLV (rows with a stored close) and a 95% bootstrap
interval for ROI (10,000 resamples, seed 585).

## Decision rule
Lower the floor for spreads and totals only if, on held-out, the chosen floor's added band in P1 has ROI above 0 with the 95%
interval's lower end above 0, its mean CLV is not negative, and P2 points the same way. Otherwise keep 55%.
