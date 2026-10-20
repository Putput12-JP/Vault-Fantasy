# Prop prices behind Pinnacle (pre-registered)

Written and committed before any `p_behind` alert has been logged or graded. The thresholds were chosen by hand on
2026-10-20 from the game-market `behind` signal (`sharp.py`, `BEHIND_ALERT`) and from the rules in a public NBA betting
course (summarized in chat, results unverified). None of them is fitted. The one number looked at to size the signal is
under "Sizing". No outcome and no closing line was looked at.

## The idea

A soft book that hangs a player prop at the same number as Pinnacle, at a price clearly better than Pinnacle's
no-vig fair price, is "behind". We already log this for game spreads, totals and moneylines (`type: 'behind'`). Player
props have Pinnacle moves, sharp Polymarket accounts and heavy Kalshi flow (`p_pin`, `p_acct`, `p_kal`), but no
soft-price-vs-fair signal. This adds it as `type: 'p_behind'`, logged and graded like the others. It is context, not a
bet signal, until it passes the rule below. It never counts toward an agree total.

## The signal

Evaluated on every poll for each prop with a Pinnacle market on the board, before tip:

1. **Fair price.** Pinnacle quotes both Over and Under at line L. Fair P(Over) = power de-vig of Pinnacle's two
   prices (`sharp.devig`, the same de-vig as the game signal). Fair P(Under) = 1 minus that.
2. **Soft price.** DraftKings (via ESPN, the only straight-bet US sportsbook in the props feed) hangs the **same line L**.
   Only American prices between -300 and +300 count (the game signal's range).
3. **Edge.** EV = fair x (1 + payout) - 1, for the side's DraftKings price. The alert needs **3% <= EV < 25%**. The
   cap is the game signal's: past it, the quote is more likely broken or stale than real.
4. **Settled.** Pinnacle's line and both prices have not changed for **20 minutes** (the last change in the recorder's
   Pinnacle series is at least 20 minutes old), and Pinnacle was quoting in the latest poll. A market still moving is
   skipped; the alert can fire later once it settles. This is the course's "don't bet a market that is still moving" rule.
5. **Fresh.** Pinnacle and ESPN each answered a poll within the last **10 minutes** (`src_ok`, when a source last
   answered, not when a price last changed).
6. **One alert per prop side.** Keyed on (game, player, stat, side, line). The first poll that meets all of the above
   wins and keeps its time, DraftKings price, Pinnacle fair and hours to tip; later prices are not alerts. The id does
   not include the price, so a price that improves later does not create a second alert.

Frozen now: 3% alert, 25% cap, +/-300 range, 20-minute settle, 10-minute freshness, same line only, DraftKings only, first sighting wins.

**Not in the signal:** Polymarket (a taker fee and thin books make its price a different question), pick'em apps
(payout multipliers, not straight prices), Kalshi (already `p_kal`), and any alternate line.

## What is graded

For each alert, once the game is final:

- **Close.** Pinnacle's closing no-vig fair for the same side at the same line (`propclose.json`, source `pin`).
  If Pinnacle closed at a **different line**, there is no like-for-like close. That alert is **not CLV-graded**; it is
  counted as moved **toward** (the line moved so the soft number was better: Over alert and Pinnacle's line went up, or
  Under alert and it went down) or **against**.
- **EV at the close** = close fair x (1 + payout of the alert's DraftKings price) - 1. This is the number that goes
  in the rule.
- **Drift** = close fair - alert fair, on the alert's side, in probability points. Reported with the rule.
- **Result** from the box score (did the stat finish on the alert's side; a DNP is void, a tie is a push) and units
  at the DraftKings price. Context only.

## Why the rule is not "CLV above zero"

Alerts are chosen for 3% or more EV against Pinnacle's fair. If Pinnacle's fair moves like a coin flip between the alert
and the close, the average EV at the close is about the alert's EV, above zero by construction. "Mean CLV > 0 with t >= 2"
would then pass for any alert rule. What the data can show is whether **the edge survives to the close**, that is,
whether Pinnacle's price at the alert was a fair forecast of its own close (a stale Pinnacle number fails this, and so
does a DraftKings price that was ahead of Pinnacle). So the bar below is a share of the alert threshold, not zero.

## The rule

At the **first look**, once **100 regular-season `p_behind` alerts are CLV-graded** (same-line close), the signal passes
only if **all** of these hold:

1. **The edge survives.** Mean EV at the close is **at least 2.0%** (two thirds of the 3% alert bar) and its mean is above
   zero with **t >= 2** (standard error from the 100 alerts' own spread).
2. **Both halves.** Mean EV at the close is above zero in the first 50 and the last 50 graded alerts, by alert time.
3. **Line moves are not adverse.** Among alerts where Pinnacle closed at a different line, "against" is not
   significantly more common than "toward": the one-sided binomial test (50/50) of the "against" count has p > 0.05.
   And alerts with no like-for-like close are **at most 35%** of all alerts that reached grading, else the result is
   called unmeasurable, not a pass.
4. **Not one player.** No single player has more than 10 of the 100 alerts, and the alerts span at least 10 game days.

Anything else is a **NO-GO**. The signal then stays on the page as labeled context, and the result goes in the decision
log. No threshold, venue, window or market is changed after the first look; a new version is a new pre-registration.
Preseason alerts are graded apart and do not count.

If 100 graded alerts have not accrued by **2026-12-31**, the status at that date is written down as "not enough
alerts" and a decision is made then about waiting. It is not a pass, and nothing is re-cut to reach 100.

## What this does not test

- **Profit.** Results and units at the DraftKings price are reported with a confidence interval, but 100 bets cannot
  confirm a 2% edge (one bet's standard deviation is about 1 unit, so 100 bets carry about +/-10%). The rule is a
  test of whether the price gap is real and lasts, not of ROI.
- **Whether Pinnacle is right.** Pinnacle's player props are specials with low limits.
  A pass says DraftKings was off Pinnacle and Pinnacle did not walk away from that gap by the close. It does not say
  Pinnacle's prop price is sharp.
- **Whether the price can be bet.** Book limits, line-up lag after we see it, and account limiting are not measured.
- **Other soft books.** FanDuel, BetMGM and the rest are not in the props feed.

## Sizing

One board, 2026-10-20 13:54 UTC (16 games, 1,834 props): 492 props had a Pinnacle market, 458 of those had DraftKings
on the same line, giving 790 priceable DraftKings sides. Median EV against Pinnacle's fair was -6.2%. **33 sides were at 1% or more, 16 at 2%, 5 at 3%, 1 at 5%**, before the settle gate. So alerts are rare, a
slate will produce a handful, and 100 graded alerts may take weeks. That is why the rule allows a time-out rather than
loosening the 3% bar.

## Known limits

- Pinnacle covers about a quarter of the props (492 of 1,834 on that board).
- One soft book, so one alert is one price.
- The 20-minute settle needs the recorder to have seen Pinnacle for 20 minutes; a market first seen later cannot alert
  until it has been unchanged that long.
- Sharp-money context only: this does not feed Best Bets, the Edges page or any agree count.

## Where it lives

`nba/scripts/sharp.py`: `prop_signals` writes `p_behind` alerts into the day's `signals.json`; `grade_prop` adds the
close, the EV at the close, the drift and the result. The track record's `signals` block already rolls alerts up by
type, so `p_behind` appears next to `behind`, `p_pin`, `p_acct` and `p_kal` with no new storage.
