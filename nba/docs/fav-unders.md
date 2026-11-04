# Favorite unders: a watch list, forward-tested

Status: **forward test from 2026-11-04.** A watch list on the Summary page, never a bet. Sharp money plays no part.

## Where it came from

Scenario sweep of this season's priced props, Oct 21 to Nov 2, 2026 (13 nights with props; Nov 3 had no slate). Every prop side on points,
rebounds, assists and 3-pointers was taken at the best stored DraftKings or Pinnacle price an hour before tip, 1 unit flat, settled from the box
score, roster-guard teams left out: 3,344 sides. Sliced by market, side, home/away, favorite/dog, spread size, game total, team implied total,
price, minutes, model agreement and book, up to three at a time, 1,621 slices with enough props. Discovery nights Oct 21 to 27, validation
nights Oct 28 to Nov 2.

| | |
|---|---|
| Every side, no model | 1696-1648, -4.2% ROI, close EV -4.8% |
| Slices at +10% or better in discovery | 128 of 1,621 |
| ... still +10% in validation | 14 (11%), against 6% for any slice |
| Mean validation ROI of the discovery winners | -5.5%, against -5.1% for every slice |

Picking pockets from past nights did not pick winners in general. One family stayed positive in both halves: unders on players whose team is
favored by 4.5 to 8.5. With the model's under chance 5+ points above the price: **103-63, +29.45u, +17.7% ROI** (n=166 props, 28 team-games),
discovery +22%, validation +15%, close EV about -3%. The rule is that slice, unchanged.

## The rule (fav_unders.py, frozen)

As of 60 minutes before tip:

1. the player's team is favored by 4.5 to 8.5 on the DraftKings spread;
2. the under on the main line (sportsbook consensus) for points, rebounds, assists or 3-pointers;
3. model under chance (prop sim `p_exact`) minus the no-vig under chance (`p_price`) is at least 5 points;
4. the roster guard is not holding the team;
5. DraftKings or Pinnacle has an under price at that exact line; the better of the two is the price. A line taken down before the lock has no price.

Every input is a number the recorders stored before tip. Settled from the box score: void when the player did not play, push on the line.

## What argues against it

- **It is one pocket out of 1,621.** Expect it to fade.
- **Close EV is negative** (about -3%). The closing price did not agree these were good bets; results beat it.
- **It is a team bet, not 166 bets.** A team's unders win or lose together. Taking only the top 1 or 2 by gap per team lost
  (12-16 and 27-27). The profit came from the whole group of a favorite's unders, so the real sample is 28 team-games.
- **No mechanism.** Unders on teams favored by 9 or more lost 6.7%, so it is not simply blowout minutes.

## How it is read

The Summary page shows each night's picks on their game with a dashed "Fav under" label, and a Records row with the forward record kept apart
from the in-sample one. track.json carries `favu_days` (settled), `favu_locks` (tonight), `favu_cfg` (the rule).

Read after 60 forward team-games, or on Dec 1, whichever is later. It moves past a watch list only if both hold:

- forward ROI above zero with z of 2 or more, standard error clustered by team-game;
- mean close EV at or above zero.

Otherwise it is a NO-GO and comes off the Summary page.
