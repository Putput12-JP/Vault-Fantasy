# Game prices behind Pinnacle (pre-registered)

Written and committed before any regular-season `behind` alert has been graded under this rule, and before the script
that computes it exists. The rule was chosen by hand on 2026-10-20. It is the prop version's rule
(`docs/prop-behind-pinnacle.md`) moved to games, with the changes the game data forced. None of the numbers is fitted.

## What was already seen

Said first, because for this signal it is nearly everything. Read the bar below knowing it.

**Preseason `behind` record (preseason never counts toward this test):** 652 alerts on 62 games, which are 284 distinct bets
(a bet is game, market, side and line), a median of 5 bets per game. First alert per bet came from bet365 (84), FanDuel (66),
BetRivers (61), DraftKings (34), BetMGM (31) and Kalshi (8). Of the 284 bets, 173 had a same-number closing price.

**Seen results, all preseason, all per distinct bet:**

- Mean EV of the price at the alert: +4.8%. Mean EV of the same price at Pinnacle's close: +0.6% (standard error 0.9).
  Pinnacle's fair for the bet's side fell 2.3 probability points between the alert and the close (it moved toward the soft
  book). By game, the mean EV at the close was +0.3% (56 games, standard error 0.8).
- Results at the soft price (Kalshi out): -2.3% per bet (standard error 8.3%, 165 bets); the side won 47.9% against a
  fair of 53.3% at the alert and 51.2% at the close.
- By market, EV at the close: moneyline +1.5%, spread -0.8%, total +1.4%. By half of the sample: +0.5% and +0.7%.
- By hours to tip (buckets chosen after looking): under 3 hours +2.7% (71 bets), 3 to 8 hours -0.4% (35), 8 or more hours
  -1.1% (67). By alert EV: 3 to 4% +1.1%, 4 to 6% -2.9%, 6% or more +6.9%. These are not evidence; they are noted so nobody
  re-cuts the rule from them.
- 39% of the bets have no same-number close (the closing ladder holds about five numbers and the line had moved off).

**Regular season so far:** 24 alerts, 16 bets, 8 games, none on a finished game. Counts only.

So this rule is registered knowing that preseason did **not** clear its bar. The question it asks is whether the regular
season does, and it fixes the answer's form so a future result is not argued after the fact.

## The signal (unchanged)

A **behind alert** (`type: 'behind'` in `sharp.py`) fires when a soft book (DraftKings, FanDuel, BetMGM, BetRivers, bet365,
ESPN BET, Caesars) or Kalshi (after its fee) prices a moneyline, spread or total side **3% or more** (under 25%) better than
Pinnacle's no-vig fair price **at the same number**, for prices between -300 and +300. Pinnacle's fair price is the power
de-vig of its own two prices at that number. Frozen: all of these thresholds. There is no settle gate on this signal.

## The question

When a soft price is behind Pinnacle's, was the price still better than Pinnacle's **close**? That is closing-line value on
the price you could have taken. It is context, not a bet, until it passes.

## What is measured

- **A bet and its alert.** One bet per (game, market, side, line): its earliest alert, the best EV among alerts at the same
  time (`behind_firsts`, #194). Its venue and price at that alert are the bet's.
- **EV at the close**, when Pinnacle's closing ladder has the same number: closing fair x (1 + payout of the bet's price) - 1
  (for Kalshi, closing fair / (price + fee) - 1). This is the existing `clv` for `behind`.
- **No same-number close.** If the bet's number is not in the closing ladder, there is no like-for-like price. The bet is
  not given an EV. It is classified when the closing ladder lies entirely on one side of the bet's number, using the
  direction that makes the bet's side more likely to win:

  | Side | Bet's chance rises when the number is |
  |---|---|
  | home spread | higher (a smaller handicap to give) |
  | away spread | lower |
  | over | lower |
  | under | higher |

  If every closing number is worse for the side than the bet's number the bet is **toward** (the soft number was better than
  anything Pinnacle later offered); if every one is better for the side, **against**. A bet whose number lies inside the
  ladder's range but is missing from it is **unclassified**.
- **Game score** c = the mean EV at the close over that game's graded bets (all markets, all venues). One number per game.

## The rule

At the **first look**, once **100 regular-season games** each have at least one bet with a same-number close, the signal passes
only if **all** of these hold. The first look takes the first 100 such games by tip time, so later games cannot change it.

1. **The edge survives.** The mean of c over the 100 games is **at least 2.0%** and above zero with **t >= 2** (standard error
   from the spread of c across games, so a game counts once however many bets it has).
2. **Both halves.** The mean of c is above zero in the first 50 and the last 50 games, by tip time.
3. **Line moves are not adverse.** Among the bets on those games with no same-number close that could be classified, "against"
   is not significantly more common than "toward": the one-sided binomial test (50/50) of the "against" count has p > 0.05.
   And bets with a same-number close are **at least 50%** of the bets on those games, else the result is unmeasurable, not
   a pass.
4. **Spread out.** The 100 games span at least 15 game days, and no day has more than 15 of them.

Anything else is a **NO-GO**. `behind` then stays on the page as labeled context and the result goes in the decision log. No
threshold, venue, window, market or unit is changed after the first look; a new version is a new pre-registration.
Preseason alerts are never counted.

If 100 games have not accrued by **2026-12-31**, the status at that date is written down as "not enough games" and a decision
is made then about waiting. It is not a pass, and nothing is re-cut to reach 100.

The first look is run by `nba/scripts/behind_first_look.py` on the files on `nba-data`. Until 100 games it prints counts only.

## What a pass would and would not mean

- **Means:** over 100 games, the soft price that was behind Pinnacle was still, on average, at least 2% better than Pinnacle's
  close, so the gap was not just Pinnacle being stale.
- **Does not mean:** a profitable bet. A pass would earn a "price survives" label and the right to a separate pre-registered
  rule on timing or venue. It does not test results at the soft price: 100 games leave a profit figure several percent wide (preseason: 8.3% on
  165 bets), so results are reported with their interval and are not part of passing.
- **Not tested:** whether a bettor could have the price (limits, account limiting, the minutes between our poll and a click),
  and whether Pinnacle's close is the right yardstick.

## Not in the rule

By-venue, by-market, by-hours-to-tip, by-EV-size and drift (closing fair minus alert fair) are reported alongside the result.
None is part of passing, and none may be used to re-cut the rule. The hours-to-tip result seen in preseason (alerts within 3
hours of tip held up best) is a hypothesis for a new registration with fresh data, not a reason to add a time gate here.

## Known limits

- One feed for the fair price (Pinnacle through the recorder), polled every 5 to 15 minutes; an alert's time is our poll's.
- No control group: prices 1 to 3% behind Pinnacle are not logged, so a general tendency of Pinnacle to drift toward soft
  books cannot be separated from the effect of the alert threshold.
- Alerts within a game share news and lineups, which is why the unit is the game.
- Preseason prices (rest and lineup decisions) may not look like the regular season, which is why they are kept out.
