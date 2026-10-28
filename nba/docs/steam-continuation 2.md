# Steam: does Pinnacle keep moving? (pre-registered)

Written and committed before any regular-season steam alert has been graded under this rule, and before the script that
computes it exists. The rule was chosen by hand on 2026-10-20 from the signal's existing definition and from what the
last few weeks showed about how it fails. None of the numbers below is fitted.

## What was already seen

Said up front, so nobody reads the bar as untouched:

- The preseason steam record on the Sharp Price page: 264 alerts fired, 168 graded, average closing-line value (CLV)
  +0.55 probability points (standard error 0.45). Preseason alerts do not count toward this test.
- Counts only, from the alert files: 289 steam alerts on 66 games, a median of 4 per game and at most 10; spreads 126,
  moneylines 89, totals 74; 68 of 148 game-and-market pairs fired in **both** directions (the line went one way and then back).
- 36% of preseason steam alerts (96 of 264) have no like-for-like closing price, because the closing ladder holds about
  five numbers and Pinnacle's line had moved off the alert's number. Those are mostly spreads (59) and totals (36).
- **Not seen:** how often Pinnacle continued versus reversed, per game or in total, for any market. The rule's result
  has not been looked at in any sample.

## The signal (unchanged)

A **steam alert** (`type: 'steam'` in `sharp.py`) fires when Pinnacle's main line for a game's spread, total or
moneyline moves past a threshold within 30 minutes: 1.0 points on a spread, 1.5 on a total, 3 probability points on a
moneyline, with a price change at the same number counting as 1/20 of a point (`level()` in `sharp.py`). It needs a poll in
the 25 minutes before, and fires at most once per market and side per 3 hours. Frozen: all of these thresholds.

## The question

After Pinnacle makes a steam move, does it **keep going in that direction** by the close, or come back? That is
continuation. It is context, not a bet: a soft book that has not moved is a different question (the `behind` signals), and
Pinnacle's own price at the alert is not one a bettor can get.

## Why not the existing CLV number

The Sharp Price page's steam record is CLV at the **same number**: Pinnacle's closing fair for that side at the alert's
number, minus the fair when it fired. Two problems, both measured:

1. **It drops the big moves.** Without a same-number close there is no CLV, and that happens exactly when Pinnacle moved the
   line away. 36% of alerts are ungraded for that reason, so the graded 64% under-represent large continuations and large
   reversals alike.
2. **Alerts are not independent.** A game's spread and moneyline move together, the same market can fire twice 3 hours
   apart, and half of the game-market pairs fire in both directions. Counting alerts overstates the evidence (the same
   problem #194 found in `behind`).

## What is measured

For every steam alert whose game is final and has a closing ladder (`pinclose.json`):

- **Alert level.** The `level()` of Pinnacle's main line at the alert, rebuilt from the alert's own line and fair price
  (spread: `-line + (home fair - 0.5) x 2.5`; total: `line + (over fair - 0.5) x 2.5`; moneyline: the home win probability).
- **Close level.** The same `level()` on Pinnacle's main line at the close. The main line is the ladder number whose two
  prices are closest to even, the same rule the recorder uses (`_snap_flat`), so it exists for every game with a ladder.
- **Move** = (close level - alert level) x (+1 for home or over, -1 for away or under). Positive means Pinnacle continued
  in the steam direction; negative means it reversed. **d** = the sign of the move (+1, -1, or 0 if exactly equal).
- **Game score** c = the mean of d over that game's steam alerts (all markets, both directions). One number per game.

Sign, not size: levels mix points and probabilities across markets, and the sign is the part that does not depend on that.

## The rule

At the **first look**, once **100 regular-season games** each have at least one graded steam alert, the signal passes only if
**all** of these hold:

1. **Continuation.** The mean of c over the 100 games is above zero with **t >= 2** (standard error from the spread of c across
   the 100 games, so a game counts once however many alerts it fired). Because c averages a few alerts, this needs
   roughly 57 to 60% of moves continuing against the rest reversing.
2. **Both halves.** The mean of c is above zero in the first 50 and the last 50 games, by tip time.
3. **Not one night.** The 100 games span at least 15 game days, and no single day has more than 15 of them.
4. **Measurable.** At least 80% of the steam alerts on those games have a closing ladder (so a result is not carried by
   whichever games happened to be recorded).

Anything else is a **NO-GO**. Steam then stays on the page as labeled context, and the result goes in the decision log.
No threshold, window, market or unit is changed after the first look; a new version is a new pre-registration.
Preseason alerts are never counted.

If 100 games have not accrued by **2026-12-31**, the status at that date is written down as "not enough games" and a
decision is made then about waiting. It is not a pass, and nothing is re-cut to reach 100.

The first look is run by `nba/scripts/steam_first_look.py`, which applies exactly this rule to the files on `nba-data`. Until
100 games it prints counts only.

## What a pass would and would not mean

- **Means:** after a steam move, Pinnacle's main line goes further the same way more often than it comes back, over 100 games.
- **Does not mean:** a bet. It would earn the row a "continues" label and the right to a separate pre-registered rule that
  prices a soft book's stale number against the close. It says nothing about size: a 60/40 continuation can be worth
  nothing after a soft book's vig.
- **Not tested:** who moved first (soft books can lead Pinnacle, as the `behind` data in #194 suggested), the cause of the move, and whether the
  alert arrives before a bettor could still get the old number. Alerts are stamped at our poll time, not the move's.

## Not in the rule

By-market results (spread, total, moneyline), size of the move in points, time to tip, and the old same-number CLV are
reported alongside the result for context. None of them is part of passing, and none may be used to re-cut the rule.

## Known limits

- One feed (Pinnacle through the recorder), polled every 5 to 15 minutes, so a move's timing is only known to the poll.
- Steam fires in bursts around news, so 100 games may include a few nights that dominate; rule 3 is the guard.
- Preseason results (rest and lineup decisions) may not look like the regular season, which is why they are kept out.
