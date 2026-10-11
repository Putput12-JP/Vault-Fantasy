# Do minutes gains survive into probabilities?

Negative binomial over minutes x per-minute rate, scored by log loss on a ladder of rungs (lower is better). Oracle absences, as in
minutes-gbm.md. The oracle row uses the true minutes: it is the ceiling, not a model.

## Train (2023, 2024, 2025), test 2026: 28,071 player-games

| Stat | log loss linear | log loss GBM | log loss oracle | GBM vs linear | share of gap closed | t |
|---|---|---|---|---|---|---|
| pts | 0.25131 | 0.24978 | 0.21542 | +0.610% | 4.3% | +5.37 |
| reb | 0.34344 | 0.34073 | 0.29596 | +0.789% | 5.7% | +5.85 |
| ast | 0.30187 | 0.30006 | 0.27545 | +0.597% | 6.8% | +5.79 |
| fg3m | 0.35684 | 0.35705 | 0.32864 | -0.058% | -0.7% | -0.68 |

## Train (2023, 2024), test 2025: 27,637 player-games

| Stat | log loss linear | log loss GBM | log loss oracle | GBM vs linear | share of gap closed | t |
|---|---|---|---|---|---|---|
| pts | 0.25117 | 0.24933 | 0.21414 | +0.733% | 5.0% | +6.19 |
| reb | 0.34814 | 0.34575 | 0.29920 | +0.687% | 4.9% | +5.03 |
| ast | 0.29894 | 0.29768 | 0.27421 | +0.420% | 5.1% | +4.17 |
| fg3m | 0.36079 | 0.36057 | 0.32981 | +0.060% | 0.7% | +0.70 |

Read: perfect minutes would cut log loss by roughly 14% on points, so minutes ARE a big uncertainty, but the GBM closes only
the small share of that gap shown; the rest (blowouts, foul trouble, in-game injuries) is not knowable before tip.
A market already prices minutes, so this bounds, and does not predict, an edge.
