# Stale number, priced (registration, step 2)

Written on 2026-11-19 and committed **before** the priced results were computed; this commit is the registration. Rules change only by a new dated
registration. Context only (CLAUDE.md): a measurement, not a pick, a size or an agree total. Follows `docs/stale-number-prereg.md` and
`docs/stale-number-results.md`, which measured line CLV in points and said the soft book's price was not converted. This converts it.

## What is converted

The same signals and control as `docs/stale-number-prereg.md` (nothing about who fires changes). For each play the **stored price** of the stale
book at the stale number is read from the tape row that set the line (spread and total only). No price is estimated: a play whose stale book
row has no stored price for that side is counted and left out.

## Two measures

1. **Realized.** The play graded against the stored final score (`data/exchange_edge_results.json`): win pays the stored price, loss costs 1, push
   returns the stake. Only games with a stored final. Mean profit per 1 unit staked, standard errors clustered by game.
2. **Expected, from outcomes.** A points-to-probability map measured per sport from every tape game with a stored final and a Pinnacle closing
   line: the closing-line residual e (side-oriented: spread = side's margin plus its closing number, total = points minus the closing total for
   the over, the reverse for the under), pooled over both orientations so there is no home bias. A play whose stale number is `clv` points better
   than the close wins when e > -clv, pushes when e = -clv, loses otherwise. Expected profit = P(win) x payout - P(loss) at the stored price.
   `clv` is the signal's line CLV from the first registration. This map is fitted on all games, including the play's own (a small leak, stated,
   and the same for treatment and control).

## Pass rule

Primary cut T = 2. A pass needs, on **both** measures, treatment mean profit above the control's by more than the 95% interval of the difference,
with at least 100 games in treatment (as before) and the same sign in each sport with 20 or more games. The control is read at the same price
rule. If the realized measure has fewer than 100 graded games, it is reported and cannot pass. Anything less is "not proven".

## Reported, not tested

Mean stored price (juice) and mean `edge` points, so the cost of the juice is visible next to the gain from the number. A slice found after
looking is flagged for monitoring with its sample size and is not a pass.
