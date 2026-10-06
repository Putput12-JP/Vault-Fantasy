# Game Simulation v2, step A2: the dependence test, corrected (pre-registered)

Written and committed before anything in it is run. Step A (docs/copula-fit.md, results in docs/copula-fit-results.md)
ended NO-GO, and its post-hoc notes found why: the test assumed the market's single-leg prices are unbiased, and overs
hit 2 to 4 points below their no-vig price, which contaminated the both-over slope. A2 fixes the design and moves the test
to a season nobody has looked at.

Nothing here is tuned on the holdout. The holdout does not exist yet (it is games played from 2026-10-20), so the freeze
below happens first and the commit date proves it.

## The model

Same Gaussian copula as step A: each leg keeps its own chance, a latent correlation rho per family ties two legs
together, the chance of a pair's outcome is P0 + s * D(rho) with the same tetrachoric series (docs/copula-fit.md).
Families: the same 26 (relationship x stat pair: same player 6, teammates 10, opponents 10), stats points, rebounds,
assists, 3-pointers.

Three changes from step A, all fixed now:

1. **Calibrated marginals.** For each stat s, fit one shift b_s on the fit seasons: p' = Phi(Phi^-1(p) - b_s), the b_s that
   minimizes the log loss of over outcomes. Use p' as the single-leg chance everywhere, in the fit and in the holdout.
   The b_s are frozen with the model and never refit on the holdout.
2. **Shrinkage instead of selection.** No family is dropped for a low z. Within each relationship group (same player,
   teammates, opponents), estimate the spread of true correlations by moments: tau^2 = max(0, mean(rho_hat^2) - mean(se^2))
   across the group's families. Each family's frozen rho is rho_hat * tau^2 / (tau^2 + se^2). Standard errors are
   game-clustered as in step A.
3. **A scoring outcome the bias cancels out of.** The calibration slope uses agreement: A = 1 if the two legs went the
   same way (both over or both under), minus the independent chance of that; regressed on the copula's predicted
   difference (2 * D(rho)). Game-clustered, as in step A.

## Freeze (before opening night)

`build_copula_fit_a2.py --freeze` fits on the 2024-25 and 2025-26 seasons together (`raw/tables/props_espn.csv`, opening
prices, the same `real_main` filter, one leg per player, stat and game, pushes dropped) and writes
`data/copula_frozen.json`: the b_s, every family's rho_hat, se, tau^2 and frozen rho. The file is committed to main before
the first 2026-27 regular-season tip (2026-10-20). The test mode refuses to run if the commit that last changed that file is
after that tip, or if the file differs from the committed one.

Fit-set sanity, written into the file and fixed as a gate: after the shift, the mean of (over hit minus p') on the fit
seasons must be within 0.5 points of zero for every stat. If not, the shift is wrong and the freeze is not committed until
it is fixed (a fit-set check, not a holdout peek).

## Holdout

2026-27 regular-season games only (preseason is a rehearsal and excluded). Legs come from the recorder's saved days on
`nba-data` (the ESPN / DraftKings main line and both prices) and results from its `results/<game>.json` box scores:
primary = the last recorded pre-tip quote for each leg (the quote the shadow ledger prices against), same filter and
dedup as the fit set, same no-vig rule, then the frozen shift. Robustness (informational): the first recorded quote.

## Looks and verdicts

Two looks only, to keep the false-positive rate honest.

- **First look: when 150 regular-season games have settled** with at least 20 legs each.
- **Second look: when 300 have.** Only if the first look was INCONCLUSIVE.

At a look, over all holdout pairs scored with the frozen rho:

- total gain = sum over pairs of log P_model - log P_independent (both with the calibrated marginals); game-clustered z.
- agreement slope with its game-clustered 95% interval.

Verdict at a look:

- **GO:** total gain z >= 2.4 at the first look (z >= 2.0 at the second), **and** the slope's interval contains 1 and
  excludes 0.
- **NO-GO:** the slope's interval excludes 1, or total gain z <= 0.
- **INCONCLUSIVE:** anything else (for example an interval that contains both 0 and 1). At the first look this triggers
  the second look; at the second look INCONCLUSIVE counts as NO-GO.

## Fallback groups (declared now)

Always reported: the same test restricted to the same-player families, to teammates, and to opponents (each with the
frozen shrunk rho of that group only). If the whole model is NO-GO, a single group ships alone only if it meets its own
GO rule with z >= 2.4 at the same look (stricter, because three groups are examined). The expected one is the same-player
group: points with rebounds was the one family strong on every cut in step A.

## What GO unlocks, and what it does not

- GO: the simulation couples each team's players and the two teams through the frozen rho, per game: build the full
  correlation matrix over the game's legs from the family table (zero between pairs not in a family), and if it is not
  positive definite multiply every off-diagonal by 0.9 repeatedly until a Cholesky factorization succeeds. The joint odds
  card reads from it. Step B (minutes tied to the game's score) is separate and has its own rules.
- GO does not make any pair a Bet, Lean or Edge. A pair price used for betting needs its own shadow-ledger record, as
  Phase 3 pairs did.
- NO-GO (or INCONCLUSIVE twice): the simulation stays as built, independent stats with the team-score tie.

## Informational (never gating)

- Holdout marginal bias after the frozen shift, per stat: if it is beyond 2 points the page says the prices drifted.
- The shrunk family model against one rho per relationship and against independence.
- Both-over and both-under slopes separately, after calibration.
- Agreement of signs with step A's explore estimates and with the covariance method.

## What it does not test

- Tail dependence (a Gaussian copula has none), three-way and larger dependence, and dependence on the game's score
  (step B).
- Whether a book's same-game price already includes these correlations.
- Preseason games and games with no real two-sided main line.
