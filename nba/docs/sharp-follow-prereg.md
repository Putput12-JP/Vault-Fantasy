# Following sharp accounts: shadow ledger and first-look rule (pre-registered)

Written and committed on 2026-10-22, before any regular-season follow has been graded and before anyone has looked at a
closing-line result for one. Nothing below is fitted. The code is `scripts/follow_ledger.py`; the tests are
`tests/test_follow_ledger.py`. This is the first step of Sharp Price V2. It adds no UI and changes no existing record.

## The question

Sharp-money study (`docs/retro/sharp-money-study.md`): Polymarket accounts that beat the close keep beating it, but a
copier who buys at the ask 15 minutes later does not (+0.09%, SE 0.59, 36 copies, NFL and CFB). The same study saw the
sharp side's price drift their way afterwards (+0.32% at an hour, +1.05% by kickoff) while takers pay 0.6 to 0.8% to cross
the spread. That suggests one idea worth testing: **copy with a resting bid at the account's own price instead of paying the
ask.** This ledger measures that against taker copies, on NBA game markets, with a control group.

## What is logged

An **event** is the first ticket of $1,000 or more by one wallet on one outcome of one Polymarket NBA game market
(moneyline, spread or total), before tip. One event per wallet, market and outcome; later adds are ignored. Props are not in
this version: they trade too thin.

Each event is tagged once, when first seen, with a **cohort** (never changed afterwards):

- **sharp**: the wallet is in the scorecard's `sharp` list (`data/pm_wallets_nba.json`, else NFL or CFB for a wallet with no NBA record).
- **dull**: the wallet is in the usually-losing list.
- **other**: every other wallet. This is the control; without it a positive number cannot be told from "the market drifts after any $1k ticket".

Flags kept on every event: `hedge` (the same wallet already bought the other outcome of the same market) and `bf` (backfill:
the ticket came before this document was committed, or the scorecard that labelled the wallet was built after the game's tip,
so the label could include the game itself). Backfill and hedged events are logged but **never count toward the test**.

## What a follow is (stored prices only)

| Follow | Entry price | Rule |
|---|---|---|
| `tk2`, `tk5`, `tk15`, `tk60` | Polymarket's stored ask for that outcome | At the first successful Polymarket poll at or after the delay. If that poll is more than 20 minutes late, or after tip, the follow is skipped, not estimated. |
| `mk` | The wallet's own price | A resting bid placed at the first poll after the ticket. Filled the first time a stored ask is at or below that price before tip. Quotes are change-only and polled every 5 to 15 minutes, so fills are a **lower bound**. |

**Close** = the mid of the last stored quote at or before tip (needs both a bid and an ask), and only if a Polymarket poll
answered in the 30 minutes before tip. Otherwise the event stays ungraded. **clv = close / entry - 1.** The primary metric
**val** equals clv for a filled follow and **0 for a maker bid that never filled**, so a rule that only fills when the price
falls against it cannot look good by dropping its losers. A game is graded 3 hours after tip.

## What was already seen

Said up front, so nobody reads the bar as untouched. From the recorder data of 2026-10-20 to 2026-10-22, **counts only**:
34 sharp-cohort events in 13 games and 974 other-cohort events in 25 games, 83 of those hedged, **no dull-cohort events**
(the NBA scorecard lists one usually-losing wallet). All of those are backfill and cannot count. Their closing-line values were
not printed or looked at. The NFL and CFB numbers above are the only prior.

## The rule

The **unit is the game**: a game's score is the mean `val` of the qualifying events in that cohort in that game (so one wallet
splitting a position into five tickets, or five wallets piling into one side, is one observation).

Qualifying = regular season (first tip 2026-10-20 23:00 UTC), `bf` false, `hedge` false, graded.

**First look** happens once, at the later of: 100 graded sharp-cohort games, and 2026-11-30. The primary test is `mk` in the
sharp cohort. It **passes** only if all of these hold:

1. Mean `val` above zero with **t >= 2** across games.
2. Mean `val` positive in **both halves** (first 50 and last 50 games by tip).
3. The sharp cohort's mean `val` for `mk` is **above the other cohort's** mean for `mk`.
4. Maker bids filled at least **10%** of the time (below that there is nothing to follow).

Anything else is a NO-GO and the result is written to the decision log. No threshold, delay, size or method changes after
the first look; a new version is a new pre-registration.

Reported for context, with no pass rule: `tk2`, `tk5`, `tk15`, `tk60` for all three cohorts; fill rate and mean clv of filled
maker bids; the dull cohort (does fading it work).

## What a pass would mean

Only that the Sharp Price page may show a **follow price** (the resting bid) on a sharp account's side, labelled as tracked and
as context. It is still not a bet signal and does not count toward any agree total. Turning it into a play needs its own
registered live test.

## What this does not test

- **A Pinnacle-confirmation rule** (copy only if Pinnacle's fair moved the same way) and **multi-wallet consensus**. Both are
  logged-for-later ideas; adding them after seeing results would be fitting. They are a separate registration.
- **Props**, **Kalshi**, **Novig** and **Pinnacle** (anonymous, no wallet to follow).
- **Real fills.** A resting bid also needs a venue that lets us rest one at that price and size; this only prices the idea.

## Known limits

- The scorecard is rebuilt weekly, so a wallet's label can change; events keep the label they had when first seen.
- Close is a mid, not a trade, so a wide spread at the close adds noise to every follow equally.
- Wallets are pseudonymous proxies. One person can run several, which makes games look more independent than they are.
- NBA's sharp list is short (1 wallet passed t >= 3 of 36 tested), so most sharp-cohort events come from wallets that earned the label in NFL or CFB. That is the study's finding about skill travelling, and it is a risk here.
