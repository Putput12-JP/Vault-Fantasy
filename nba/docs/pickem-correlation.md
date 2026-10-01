# Correlated pick'em pairs: pre-registered test

Written and committed before any result was computed. Phase 3 of Player Props v2 ships only if this passes.

## The idea

Pick'em apps (PrizePicks, Underdog, Sleeper) pay a flat multiple per entry, for example 3x on a 2-pick power play,
whatever the picks are. That flat price assumes the picks are independent. If two picks from the same game tend to hit
together (both stars' points over in a fast, close game, or a point guard's assists with his scorer's points), the
entry wins more often than the app's price assumes. In the NFL this worked: QB passing yards with his WR1's receiving
yards hit together 41% of the time against 34% if independent. This test asks whether NBA props have pairs like that
that the market does not already price.

## Data

- Legs: ESPN sportsbook main lines (`raw/tables/props_espn.csv`, kind = main), opening price, with the same
  `real_main` filter as the streak test (both sides between -200 and +200, 2-10% hold). One leg per player, stat and
  game. Stats: points, rebounds, assists, 3-pointers made, pts + reb + ast. Pushes are dropped.
- Exploration set: the 2024-25 season. Test set: the 2025-26 season, untouched until the families are frozen.
- Robustness: the 2025-26 pre-tip close where the feed has it.

## Measure

For each leg, the market's no-vig chance of the over (p) and what happened (1 if over, else 0). The residual
r = outcome - p is the part the market's single-leg price did not see. For a pair of legs from **different players in
the same game**, the product of their residuals measures how much they move together beyond what each price already
says. Its average over a family is the covariance c.

- c > 0: over / over (and under / under) hit together more than independent prices say.
- c < 0: over / under is the correlated combination.
- For two legs priced near 50%, the joint chance is about 0.25 + c, so the lift on a 2-pick entry is 1 + c / 0.25.

Families: relationship (teammates or opponents) x the two stats (15 unordered stat pairs), 30 families.
Standard errors are clustered by game (pairs within a game share legs, so they are not independent): the variance of
the per-game sums of residual products.

## Ship rules (fixed now)

1. Exploration (2024-25): a family is a candidate if it has 2,000+ pairs and |z| >= 3 (strict, because 30 families
   are looked at).
2. Test (2025-26): a candidate passes if its covariance has the same sign with z >= 2 (game-clustered) and the implied
   2-pick lift is at least 4% (|c| >= 0.01). Below that, the app's rounding and line differences swamp it.
3. Phase 3 ships only the families that pass, shown as "these two tend to hit together" with the measured lift. No
   family is added later without its own test.
4. If no family passes, Phase 3 does not ship as a pick builder; the page says correlation was tested and what was
   found.

## What it does not test

- Whether the apps' lines match the sportsbook lines (they usually sit within half a point; Phase 3 would price each
  pick at the app's own line with our fair, as the Props page already does).
- App rules: some apps block certain same-game combinations; the page would show only combinations the app allows.
- Same-player pairs (points and assists of one player): most apps do not allow the same player twice in an entry.
