# Game Simulation v2, step A: the dependence structure (pre-registered test)

Written and committed before the fit was run. This is step A of the v2 plan: measure how NBA props move together, in a
form the simulation can use, and test it on a season it never saw.

## What is fitted

A Gaussian copula: each leg keeps its own market chance (the no-vig price), and a latent correlation rho ties two legs
together. If a leg's no-vig chance of the over is p, the over happens when a standard normal variable exceeds
h = Phi^-1(1 - p). For two legs the chance both are over is Phi2(h1, h2; rho) (bivariate normal), the chance one is over
and the other under follows from the two single-leg chances. rho = 0 is the independent case. rho is estimated by
maximum likelihood per family, treating each pair's outcome (over or under on each leg) as one observation with the
leg prices fixed.

Why this form: the simulation draws every player's stats from their own distributions and needs a dependence it can
plug in without changing any single-stat chance. The copula does exactly that, and its rho is the number the
simulation would use.

## Data (same legs and filters as docs/pickem-correlation.md)

- ESPN sportsbook main lines, opening price, `real_main` filter, one leg per player, stat and game, pushes dropped
  (`raw/tables/props_espn.csv`). Stats: points, rebounds, assists, 3-pointers made. Pts + reb + ast is left out: it is a
  sum of the others, so its dependence with them is mechanical, and the simulation gets it by adding.
- Explore: 2024-25. Test: 2025-26, untouched until the kept families are frozen.
- Robustness (not gating): the frozen model on 2025-26 pre-tip closing prices.

## Families

Relationship x stat pair: teammates (4 + 6 = 10 pairs of stats), opponents (10), and the same player (6, different
stats only). 26 families. Pairs are two legs in the same game; for teammates and opponents they are different players.

## Fixed rules

1. Keep a family if, in the explore season, it has 2,000+ pairs, |z| >= 2 (z = rho divided by its game-clustered
   standard error) and |rho| >= 0.02. Every other family is frozen at rho = 0 (independent). No later changes.
2. Standard errors are game-clustered: the score of each game (the sum over its pairs of the likelihood's slope in rho)
   is the unit; the variance of rho is the clustered sandwich. Pairs inside a game share legs, so they are not
   independent.
3. Test (2025-26), the frozen model against independence, per pair: gain = log-likelihood of the pair's outcome under
   the copula minus under independence. Game-clustered: the sum of gains per game is the unit.
4. **The model passes (GO) if both hold:**
   a. The total gain over every test pair has z >= 2 (game-clustered).
   b. Calibration slope: regress (observed both-over minus independent chance) on (the copula's predicted
      difference) over the kept families' test pairs. The slope's 95% interval (game-clustered) must contain 1 and
      exclude 0. A slope well below 1 means the correlations were overfit; above 1, underfit.
5. A single family counts as individually confirmed if its test gain has z >= 2. Report them, but the model as a whole
   is what ships; a family that fails individually stays in only if the whole model passes, and is flagged.
6. If the whole model fails, the simulation keeps independent stats except the team-score tie it already has, and
   the page says correlation was tested.

## Informational (does not gate)

- A pooled model: one rho per relationship (self / team / opp) against the family model on the test season.
- The implied 2-pick lift for each kept family at 50% legs: for rho near 0, joint is about 0.25 + 0.159 rho.
- The explore estimates against the existing covariance results (docs/pickem-correlation-results.md), as a check that
  the two methods agree.

## What it does not test

- Dependence in the tails (a 40-point game with 15 assists): the likelihood only sees whether each leg cleared its
  line, which is where the market's prices sit. A Gaussian copula has no tail dependence by construction.
- Three-way and larger dependence, and dependence on the game's score (blowouts): that is step B.
- Whether a book's same-game price already includes these correlations.

Output: `data/copula_corr.json` (frozen families) and `docs/copula-fit-results.md`.
