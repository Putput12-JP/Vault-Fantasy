# Prop model v3: plan

Written 2026-09-30. v2 is live ([prop-model-v2.md](prop-model-v2.md)). This plan says what v3 should change, why, and how
each change is tested before it ships. Same rules as always: free data only, fit on 2024-25, test on 2025-26 on the
same rows as the model it replaces, ship a component only if it helps where we bet.

## Status

**Workstream A (ladder distributions) done 2026-09-30, result in [prop-model-v3.md](prop-model-v3.md): better
probabilities, same betting edge. v2 keeps pricing bets (pre-registered rule).**

- The fix worked as a distribution. Across every 2025-26 player-game, v3's tails line up (points: v2 said 26%, happened
  15%; v3 says 24%, happens 23%), and log score improves for points and all four combos. On Kalshi ladders, log loss
  improves on all four stats; uncalibrated v3 beats Kalshi's own price on 3PM alone (0.5246 vs 0.5281), a first.
- It did not add betting edge. Blended with the market, v2 and v3 score the same on the held-out half (log loss within
  0.0003), because the blend's fitted weights already recalibrate v2's too-wide shape. Gated ROI: 3PM NO stays GO under
  every variant (+7.4% to +8.1% vs v2 +9.4%, all within 1 SE); points NO falls to WATCH (z 1.65 to 1.85 vs 2.14).
- Kept for later: v3's calibrated distribution is the right model where no blend history exists (Kalshi PRA / PR / PA /
  RA ladders, pick'em apps, Polymarket props), and its minutes scenarios are where workstream B plugs in. Re-run the
  same test after B and C; ship v3 when it wins on the rule.
- Fitted facts worth keeping: given true minutes, 3PA are Poisson (dispersion 0) and 3P% barely varies game to game
  beyond binomial luck (beta concentration 400 to 1000), so 3PM noise is minutes + attempt luck + make luck. Points
  given minutes vary about 2.5x the mean.

## 1. Where v2 stands, and what our own data says to fix

v2 beat v1 on every stat's RMSE and on Kalshi log loss for all four stats (3PM now equals the market). Two diagnostics
on the 2025-26 test season decide v3's priorities:

**Minutes are the largest fixable error.** Re-scoring v2's projection with each player's true minutes removes this
share of the squared error:

| Stat | Share of error that is minutes |
|---|---|
| Points | 28.5% |
| Rebounds | 25.5% |
| Assists | 14.5% |
| 3PM | 12.3% |

Minutes MAE is 4.90, and 18.5% of player-games miss by 8+ minutes. Those are the blowouts, surprise rests, foul
trouble and role changes.

**v2's distribution is too wide on Kalshi ladders.** Model probability vs hit rate vs price, all 2025-26 rungs:

| Points, model says | Hit rate | Kalshi price |
|---|---|---|
| 15% | 10% | 13% |
| 26% | 16% | 20% |
| 53% | 58% | 62% |
| 65% | 75% | 74% |

Far rungs are priced too high, near rungs too low: the signature of too much variance. Same pattern on rebounds,
assists and 3PM. The cause is known: calibration was fit on sportsbook main lines, which sit near 50%, so the tails
of the distribution were never calibrated, and one spread function serves every player. The ladders are where
Kalshi lists most of its markets, and where both GO signals live.

## 2. What the proven public systems do

| Source | What it does | What we take |
|---|---|---|
| [DARKO](https://www.darko.app/about) (Kostya Medvedovsky), the best-regarded public NBA projection system | Each box-score stat gets its own decay rate, fit by an optimizer: minutes and role decay in 1 to 3 games, 3PA volume and usage in 13 to 24, defense in 41 to 75, shooting percentages over seasons. A Kalman filter separates real change from noise. Rookies start from age, draft slot and height. A team change raises the learning rate. Minutes are "the hardest part". | Per-stat decay (our v2 stacker says our single decay over-reacts: season form got weight 0.5, t 10 to 12). Rookie priors. Faster learning after a trade. |
| [propedge](https://github.com/vntw0n3/propedge), [Risky-Scout](https://github.com/Risky-Scout/nba-player-props-model), [propsim](https://github.com/pranavcheedalla/propsim) | Honest GitHub prop models: calibrated probabilities, full outcome distributions (PMFs), Monte Carlo sims, LightGBM quantile ensembles. All three report that the model alone trails the market (Risky-Scout: Brier 0.278 vs market 0.246; propsim: 51.6% hit, about -1.4% ROI at -110). | Confirms our week 3 result: complexity alone does not beat the price. Take their scorecard: actual/expected by outcome level, variance A/E, 90% coverage. Take full PMFs over mean + spread. |
| [Unabated market-based prop projections](https://unabated.com/post/introducing-market-based-prop-projections) | Turns the median lines across books into the market's implied mean, weights books that moved recently, and blends 10 to 20% of that with a model. Warns no book is proven sharp on props. | A market-implied mean from the Kalshi ladder plus books, as an input and as a staleness detector. |
| [Player absence and betting lines](https://ideas.repec.org/a/eee/finlet/v13y2015icp130-136.html) (Finance Research Letters, 2015) | Openers mis-price games with absent players; the close does not. | Same as our week 2 finding (ESPN opens are stale). Speed on injury news is the edge, not better closing numbers. |
| [Polymarket NBA arbitrage](https://arxiv.org/abs/2605.00864) (arXiv 2026) | Single-contract arbitrage is almost nonexistent (median 3.6 s); mispricing across related contracts is more common (about 1% median) but capped by liquidity (about 15 shares). | Cross-contract consistency (ladder vs line vs combo) is real but small and thin. Treat it as a filter, not a strategy. |
| Kalshi series settings (checked in the API today) | NBA player-prop series use `fee_type: quadratic`, with no maker fee; game markets use `quadratic_with_maker_fees`. | A resting order on a prop ladder that gets filled pays no fee. The taker fee is up to 1.75 cents a contract, a big share of a 3 to 9% edge. |
| 3-point shooting literature ([beta-binomial hierarchical model](https://kfoofw.github.io/bayesian-hierarchical-modelling-on-nba-3-point-shooting/), [overdispersion](https://squared2020.com/2017/08/20/basics-in-negative-binomial-regression-predicting-three-point-field-goal-percentages/)) | 3PM = attempts x a make rate that is shrunk hard to the population. Counts are overdispersed, so Poisson is wrong. | Build the 3PM distribution from attempts (negative binomial) and makes (beta-binomial), not a fitted variance. |
| [Cleaning the Glass garbage time](https://cleaningtheglass.com/stats/guide/garbage_time) | A precise definition of garbage time from score and clock. | Label blowout minutes in play-by-play, then model the chance of one from the market spread. |
| Referee studies ([NBAstuffer](https://www.nbastuffer.com/the-referee-effect-in-the-nba/), [arXiv RIM](https://arxiv.org/html/2605.17845v1)) | Crews differ in foul and free-throw rates, worth 3 to 8 total points. | Test only; the game total probably already prices it. Crews are free in ESPN's game summary. |

## 3. v3 workstreams, in order of expected value

Each one: what, why, the test, and how it ships. "Test" always means fit on 2024-25, score 2025-26, same rows as v2.

### A. Ladder distributions (highest value, protects both GO signals)

1. **Minutes-mixture distribution.** Replace "mean + fitted variance" with an explicit mix: P(stat over line) =
   sum over minutes scenarios of P(minutes) x P(stat over line | minutes). Minutes scenarios come from each player's
   own miss history, plus a blowout branch whose chance comes from the market spread (A2).
2. **3PM from attempts and makes.** Attempts ~ negative binomial on (minutes x attempt rate); makes ~ beta-binomial
   with his regressed percentage. Points get the same volume x efficiency split (2PA, 3PA, FTA).
3. **Player-specific dispersion.** Shrink each player's residual dispersion toward his role group (guards, wings,
   bigs; starter or bench).
4. **Calibrate on the ladder itself.** Isotonic calibration by stat on Kalshi rungs, fit on the first half of
   2025-26 and tested on the second, plus a rolling version for live use.

Test: Kalshi log loss and the decile table above (model vs hit must line up), then 3PM NO and points NO blended ROI
against the price-only baseline. Ship: the page's pricing moves from one variance formula to a PMF built from these
pieces (the JavaScript already has negative binomial; add beta-binomial and the minutes mix).

### B. Minutes v3 (largest error source)

1. **Market spread for blowouts.** v2's minutes model uses our game model's margin. Use the market spread, and fit
   separate starter and bench effects from garbage-time minutes labelled in play-by-play.
2. **Return from absence.** Players back after missing N+ games run on restrictions. Measure the first 1 to 5 games
   back from box scores; apply automatically when the injury report shows a return.
3. **Role changes.** DARKO gives minutes and starting role a 1 to 3 game memory. Detect a starter switch and move
   minutes quickly, rather than through our slow average.
4. **Confirmed starters.** Lineups post about 30 minutes before tip on free pages
   ([NBA.com](https://www.nba.com/players/todays-lineups), [RotoWire](https://www.rotowire.com/basketball/nba-lineups.php)).
   Record them live from opening night; size the value now by re-running the backtest with the true starter flag.
5. **Faster learning after a trade** (DARKO): a higher learning rate for the first 10 games with a new team.

Test: minutes MAE, share of 8+ minute misses, then prop log loss. Ship: minutes model v2 in the daily job, and a
starters feed in the recorder.

### C. Per-stat memory (DARKO)

Fit a separate decay for each component (minutes, 2PA, 3PA, FTA, shooting percentages, OREB, DREB, AST, TOV) by
walk-forward likelihood on 2022-24. Expected: v2's season-form weight falls toward zero because the base is no longer
over-reacting. Test: RMSE and log loss vs v2. Ship: `build_player_projections.py` and the model state use the new
decays.

### D. Opponent v3

1. **Attempts allowed, not makes allowed.** Opponent 3P% allowed is mostly luck; 3PA allowed is scheme. Rebuild the
   3PM defense factor from 3PA allowed x regressed percentage.
2. **Rebounding shares.** Rebounds depend on the opponent's own offensive and defensive rebounding rates, not only
   on what the opponent allows.
3. **Opponent personnel.** v2 does not know that the opponent's center is out. Add the opponent's missing rotation
   minutes by position group, from the injury report, as a stacker feature.

Test and ship: as v2 (new stacker features, new state fields).

### E. Teammate usage from play-by-play

hoopR play-by-play (281 MB per season, free) has substitutions, so we can rebuild who was on the floor and measure
each player's share of shots, assists and rebounds with and without each teammate. This replaces the small usage
cascade with player-pair effects, shrunk toward the group average. Test on 2025-26 games where a rotation teammate
sat. Ship: pair table in the model state; the Minutes Lab's OUT button uses it too.

### F. Early season and rookies

The first 15 games are when the market is least sure and our rates are thinnest. Priors from draft slot, age and
height (DARKO), plus preseason minutes as a role signal. Test on the first 15 games of 2024-25 and 2025-26.

### G. Market-implied projection and cross-venue staleness (needs our recorded prices)

Turn the Kalshi ladder and book lines into the market's implied mean and distribution (Unabated method), then:
- use the gap between our projection and the market's as a stacker input
- flag a venue whose price has not moved while the others have (the stale opener is our best documented edge)

Needs 3 to 6 weeks of our own snapshots; history has no timestamps.

### H. Execution: be the maker

Prop ladders charge no maker fee. Simulate resting NO orders at fair price minus a margin against the 2025-26 trade
tape: fill rate, size, and whether fills were adversely selected. Then bet timing: morning vs pre-tip, measured on
our snapshots. This can start now on historical trades.

### I. Correlation and pick'em venues

A game-level simulation with shared shocks (pace, total, margin) plus player noise, correlations fit from box-score
residuals. Uses:
- pick'em apps with flat payouts, where the NFL work found +22% on correlated legs (PrizePicks and Underdog NBA
  boards come from the same free endpoints the NFL pipeline already reads)
- Kalshi combo markets
- PRA vs its parts

Test: predicted vs actual joint hit rates on 2025-26 pairs.

### J. Referees (test only)

Backfill crews from ESPN game summaries for two seasons; crew foul rate as a stacker feature for points and free
throws. Keep only if it survives the test; the total probably prices it.

### K. Challenger model (research only)

A gradient-boosted or quantile model, run locally, must beat the stacker on the same test before it ships, and has
to be exportable to the page. The honest GitHub models suggest it will not beat the market alone; it may still add
information to the blend.

## 4. Not doing

- Neural nets or thousands of features: the evidence (ours and the public repos) says accuracy is not the bottleneck.
- stats.nba.com from GitHub Actions (it blocks cloud IPs). Play-by-play comes from hoopR; tracking data stays out.
- Any paid feed.
- Shipping a component that improves projection error but not log loss or ROI where we bet.

## 5. Sequence

| When | Work | Why then |
|---|---|---|
| Now to opening night (Oct 20) | A (ladder distributions), C (per-stat memory), B1 to B3 and B5 (minutes from spread, returns, roles, trades), D (opponent v3). Start recording starters. | All backtestable today on 2025-26, and A protects the two GO signals. |
| First month of the season | E (play-by-play usage), F (early season), J (referees), H (maker simulation on the historical tape) | Needs new backfills; F matters most in the first 15 games. |
| After 3 to 6 weeks of snapshots | G (market-implied and staleness), H (timing), I (correlation and pick'em) | Needs our own timestamped prices. |

The gate does not change: 50+ games, z of 2 or more, and beating the price-only baseline on the same side.
