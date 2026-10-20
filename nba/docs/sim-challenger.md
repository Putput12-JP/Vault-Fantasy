# Simulation challenger: rules (written before the first run)

Written 2026-10-12. Prompted by a public NBA prop page that shows 50 simulated games per player and calls the share over the line
its probability. Question: does turning a projection into N simulated games add anything over our analytic prop model (v2), and
what does a 50-game version cost?

## Variants (all single props: pts, reb, ast, 3pm)

| Variant | Mean | Spread | Draws | Calibration |
|---|---|---|---|---|
| v2 | v2 stacked mean | v2 spread | none (closed form) | isotonic, fit on 2024-25 ESPN open lines |
| sim10k | v2 | v2 | 10,000, negative binomial counts, Normal points | v2's |
| sim50 | v2 | v2 | 50, smoothed (k+.5)/(N+1) | v2's |
| sam50 | v1 (rate x minutes) | v1 | 50, Normal for every stat floored at 0, smoothed | own isotonic |
| sam50_shown | v1 | v1 | 50, raw share over, no smoothing | none (what a page would display) |

"Sam style" is an assumption: his NBA method is not published (his NBA page returns 404 as of 2026-10-12). sam50 is the simplest
version of what the screenshots show, not a reconstruction.

## Data and protocol

The v2 walk-forward, unchanged. Fit 2024-25, test 2025-26. Test rows: every ESPN pre-tip close line and every Kalshi pre-tip strike
with a price, identical across variants. Fixed seed 20261020. Nothing here uses the 2026-27 season.

## What counts

- **Metric:** log loss against the outcome; paired difference against v2 per row, standard error clustered by game.
- **A variant beats v2 in a cell** only if dLL <= -2 SE. It is worse at dLL >= +2 SE. Otherwise the same.
- **sim10k must match v2** (every cell "same", |dLL| < 0.001). If not, the simulator has a bug and nothing else is read.
- **Noise check:** sim50's root-mean-square gap from v2 should be close to sqrt(p(1-p)/50), about 0.06 to 0.07. A flip rate
  (variant on the other side of the price from v2) is reported for sim50 and sam50.
- **Blend t:** does the variant add information on top of the price (same test as the v2 backtests). Reported, not gated.

## Decisions this can produce

- **Simulation adds nothing for single props** if sim10k = v2 and sim50/sam50 are the same or worse. Expected. The simulator then
  stays a tool for joint outcomes (the Game Simulation record and the frozen copula), and 50 draws are a display only.
- **Sam-style beats v2** in any cell: not adopted from this alone. It would need the same result on the live ledger (CLV, 300+ bets),
  per docs/experiment-log.md section 3.
- Record the outcome in `docs/sim-challenger-results.md`, NO-GO included, and add a row to experiment-log.md section 1.

## Not tested here

Combo markets and joint outcomes (needs the copula, test frozen for the 2026-27 holdout), and any betting ROI. Both belong to the
live ledger.

## Amendment, 2026-10-12 (after the first run, disclosed)

The first run gave sim10k its own isotonic fit and showed a gap from v2 of about 0.01 against 0.005 expected from Monte Carlo error, and
3 Kalshi cells "worse" by 0.0005. A synthetic check (4,000 random means and variances per stat, simulator vs closed form) matched at the
expected noise with zero bias, so the simulator is right; the gap was a second calibration fit on noisy simulated probabilities.
sim10k and sim50 now reuse v2's calibration, so the only thing that differs from v2 is how the probability is made. sam50 keeps its own
(its mean and spread differ). The pass bars are unchanged.

## Live record (added 2026-10-12, before opening night, before any live result)

`nba/scripts/prop_sim_record.py` records, for every priced pts / reb / ast / 3pm prop in the 3 hours before tip, the probability of the over three
ways at the main line: the minutes model (closed form, calibrated), the same distribution played 10,000 times, and played 50 times (one fixed draw per
prop, smoothed). The ledger settles them from the box score into `track.json` (`psim_days`; preseason kept apart). Track Record shows it under
"Props: minutes model vs simulations".

Rules, fixed now:
- **Scored:** log loss and Brier on the last pre-tip row of each prop. Void when the player does not play or the stat lands on the line. Props held by the
  roster or source holds are not recorded.
- **Call:** a simulation is better or worse than the minutes model only when its paired log-loss difference clears 2 standard errors, clustered by game,
  and only after 300 scored props (the page says "collecting" before that). Same bars as the backtest.
- **Expected:** 10,000 games equals the minutes model; 50 games worse. A result that disagrees (50 games better) is a WATCH, not an adoption: it needs
  the same result on a second month, per docs/experiment-log.md section 3.
- **Not a bet source.** Nothing here changes a price, a Bet, a Lean or an Edge.

## Biggest gap record (added 2026-10-20, opening night, before any live result)

The Props Simulation page headlines one prop per game, **Biggest gap**: the priced prop where the model's chance differs most from the price.
`prop_sim_record.gap_pick()` makes the same choice from the recorded rows and `ledger.py` settles it into `track.json` (`gap_days`; preseason kept
apart in `preseason.gap_days`).

Rules, fixed now:
- **Pick:** per game, from the last pre-tip rows. Candidates are the priced props (pts / reb / ast / 3pm) of each team's five highest-minute players,
  as the page lists them. The model's side is the side it gives more than 50%. Gap = the model's chance for that side minus the price's chance for it
  (vig removed). The largest gap is the pick. A game with no priced prop has no pick: the page's flat-line "Strongest lean" is not tracked.
- **Scored:** W or L against the box score at the pick's line. P when the stat lands on the line, D when the player did not play; both are voids, kept in
  the count but outside the record.
- **Not profit.** No stake or payout is stored, so there is no ROI. The test is the hit rate against what the price implied: expected wins =
  sum of the price's chance for each pick, z = (wins - expected) / sqrt(sum p(1-p)).
- **Call:** none before 100 settled (non-void) picks; the page says "collecting". After that, a result is "ahead of the price" or "behind the price" only
  when |z| >= 2. An improving record is flagged for close monitoring with its sample size, never promoted to a bet signal.
- **Not a bet source.** Nothing here changes a price, a Bet, a Lean or an Edge.
