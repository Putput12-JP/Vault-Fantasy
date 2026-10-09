# Novig money against the close (pre-registered)

Written and committed before any regular-season Novig alert has been graded. The signal and its thresholds were chosen by
hand on 2026-10-08, not fitted, so the first honest test is a frozen rule applied to alerts nobody has looked at.

## What the signal is

Novig is a peer-to-peer exchange with public, keyless order books and trade tape (docs.novig.com). Every ticket of $250 or
more on a game's winner, spread or total is saved to the day's tape (`s: 'nov'` in `snapshots/<day>/tape.jsonl`). A **Novig
money alert** (`type: 'novig'` in `sharp.py`) fires when tickets on one side of one market, in one 30-minute bucket, add up
to **$1,000 or more**. It records Pinnacle's no-vig fair price for that side at the time of the last ticket.

Frozen now, before the test: the $250 save threshold, the $1,000 alert threshold, the 30-minute bucket, one alert per
(market, side, line, bucket), and tickets counted only before tip. Spread and total alerts keep their own line.

## What is graded

- **Closing-line value:** Pinnacle's closing fair for the same side and number (`pinclose.json`) minus the fair at the alert.
  Positive means the money moved toward the side Pinnacle ended up pricing higher.
- **Result:** win, loss or push against the final score, for context only. It is not the pass rule.

## The rule

At the **first look**, once **100 regular-season Novig money alerts** have been graded (preseason alerts are graded apart and
do not count), the signal passes only if all of these hold:

1. Mean closing-line value is above zero with **t >= 2**.
2. Mean closing-line value is positive in **both halves** (the first 50 alerts and the last 50, by alert time).

Anything else is a NO-GO and the signal stays on Sharp Price as labeled context, with the result written to the decision log.
No threshold, bucket or market is changed after the first look; a new version is a new pre-registration.

## What this does not test

Whether Novig's *price* is a good fair-price reference. That needs the price history, which the recorder now saves as
`snapshots/<day>/novig.jsonl` (home or over side: bid, ask, depth to the nearest $250, per main line). A price test is
registered separately once a few weeks of regular-season history exist.

## Known limits

- Novig's NBA books are thin (a typical resting order is $100 to $300), so one $1,000 ticket is a large move there. That
  is why the threshold is low, and why the first results may be noisy.
- Tickets are anonymous: there is no sharp or dull account class, unlike Polymarket.
- Novig lists a game only close to tip, so most tickets arrive within a day of the game.
