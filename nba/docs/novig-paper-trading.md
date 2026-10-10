# Novig paper trading (pre-registered 2026-10-10, before any order)

Written before the first paper order. Nothing here places an order on Novig, uses a Novig key or moves money. It is a simulator that answers one
question first: **do resting orders at our price earn money on Novig's player-prop books once fills and fees are counted honestly?** A real order
needs its own rule and the owner's approval later (see "What comes next").

## What it does

After every recorder poll (`snapshot.py` → `novig_paper.log`), for games tipping within 24 hours:

1. Reads Novig's public player-prop books (`novig.py`, already recorded in `board['novig']`): per player and stat, a ladder of half-line rungs with bid and ask for
   Over and Under.
2. Prices each rung with the **same projection the Props page uses** (minutes model, prop model v2, calibration), blended with the rung's mid price using the
   **sportsbook blend weights** (`PR['book']`). That choice is an assumption: no blend has been fit on Novig, and the book weights lean heavily on the market price
   (so our fair chance sits close to the mid and the model only nudges it).
3. Places a **paper order** on a side when a limit price exists with `fair - break-even(price) >= 3%`, where break-even includes the placeholder fee. The limit is the highest
   whole-cent price that still clears 3%, which is usually a few cents below fair.
   - **maker:** the best ask is above our limit, so the order rests until tip. It may sit below the best bid; it then fills only if sellers come down to it.
   - **taker:** the best ask is already at or below our limit: filled at the ask at once.
4. Fills a resting order from Novig's **public trade tape** (executions of $25 and up, the 60 newest per poll):
   - **touch:** an execution on that rung traded at our price or better after we placed the order.
   - **thru:** an execution traded at least 1 cent better than our price, so we were not merely queued at the back.
   The two are recorded and reported separately and never mixed. A fill is priced at **our limit** (an exchange matches a resting order at its own price), not at the
   better price that printed.
5. Settles each order from the ESPN box score (3 hours after tip). Over wins on `actual > line`, Under on `actual < line` (half-lines never push). A player who did not
   play is void (refunded).

Fixed settings (`novig_paper.py`): edge 3%, stake $5 per order (inside the planned $1 to $5 micro range), at most 4 orders per player-stat (rungs nearest 50% first),
half-lines only, a real two-sided quote only (a one-sided book is not a price), stats pts / reb / ast / 3pm and their combinations, and **never** a player or team the
roster guard holds (new rosters, preseason rotations).

## What is recorded and shown

- `snapshots/<day>/novig_paper.jsonl` on the `nba-data` branch: one row per order, rewritten when its status changes (placed, filled). Row layout is at the bottom of
  `novig_paper.py`. It also stores the ask at placement and the mid, so "what taking the ask would have paid" and every maker-vs-taker question can be answered later.
- `track.json` → `novig_days` (settled orders per tip day, preseason kept apart in `preseason.novig_days`) and `novig_cfg` (the fee, edge and stake the page shows).
- Track Record → **Novig paper trading**: orders placed, maker fills (touch · thru), return on filled orders, the return the unfilled orders would have had at our price
  (a filled return far below it means the fills were the bad ones: adverse selection), and the return from simply taking the ask at placement on every order.

## Honest limits (all shown or stated on the page)

- **The fee is a placeholder.** Novig's fee schedule has not been confirmed. Every number applies 2% of winnings on a win. Results store the gross figure too, so the
  confirmed fee can be applied without re-running anything. Until it is confirmed, no result here is a profit claim.
- **Fills are undercounted.** The tape lists executions of $25 and up only, and the poll returns the 60 newest across all markets. Small executions and busy stretches
  are missed, so true fill rates are higher than shown. That makes the filled-order return a conservative sample, not a flattering one.
- **Queue position is unknown.** `touch` is optimistic, `thru` is conservative. The truth is between them.
- **No market impact.** The simulator assumes a $5 order does not move the book and is matched in full at our limit.
- **No price history.** Novig lists a game only close to tip and we have no history before 2026-09-30, so there is no backtest for this venue at all.
- **Thin books.** Typical resting orders are $100 to $300; props are thinner. A one-sided ladder is skipped.
- **A day-folder seam.** State lives in the ET day's folder, so an order left open across midnight ET (rare late tips) can be placed again with a new time.

## What would count as a result (fixed now)

Paper results are context until **all** of these hold, at the first look (decided only when the count is reached, using the first time it is, not the best time):

1. At least **100 filled orders** under the `thru` assumption.
2. Their return per dollar staked is above zero with **z >= 2**, clustered by game day (orders from one day share a market).
3. Novig's **actual fee schedule is confirmed** and the results recomputed with it.
4. The return of the orders that did not fill, at our price, is reported beside it (adverse selection is read, not hidden). No pass rule is set on it, because a gap
   is expected; a gap that grows over the season is a reason to stop.

Anything else (taker orders, game markets, other stats, a different edge or stake) gets no live credit and must be pre-registered first, per `docs/experiment-log.md`.
Reading the results for a new pattern and then proposing it does not count.

## What comes next (not built)

1. **Novig's own paper host** (`api.paper.novig.com`) with the `vault-desk` subaccount key from `scripts/novig_setup.py`: place real orders on Novig's practice exchange
   to learn the order endpoints, the fee, and how fills actually behave. This needs Novig's API documentation, which could not be reached from the cloud environment
   (the host is blocked). Paste the order endpoints or allow `docs.novig.com` in the environment's network settings.
2. **Micro-stakes live** ($1 to $5 an order, a small total loss budget set by the owner, kill switch) only after the result above and the owner's approval, under the
   same tier rules as Kalshi (`docs/update-plan.md`, Phase 1.5). Whether Novig is available to the owner, and how it is taxed, is the owner's to confirm.
3. **The Edge Finder** gets Novig as a live-record-only option once the paper record has enough orders, labelled "no backtest".
