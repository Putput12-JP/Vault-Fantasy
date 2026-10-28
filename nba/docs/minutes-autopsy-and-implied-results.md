# Minutes: error autopsy and market-implied minutes, results

Rule registered first in [minutes-autopsy-and-implied.md](minutes-autopsy-and-implied.md) (commit f4b06e0de). Scripts: `test_minutes_autopsy.py`, `test_minutes_implied.py`. Nothing here changes pricing.

## A. Error autopsy (2025-26, GP, 27799 player-games played, 4611 missed by 8+ minutes = 16.6%)

| Cause | Misses | Share of misses | Share of all games | Lift | GP minus actual | Qualifies |
|---|---|---|---|---|---|---|
| blowout | 1246 | 27.0% | 25.4% | 1.07x | +2.8 | no |
| early exit | 721 | 15.6% | 4.7% | 3.30x | +12.9 | no |
| rotation change | 1426 | 30.9% | 5.1% | 6.03x | +2.3 | yes |
| teammate out | 953 | 20.7% | 49.6% | 0.42x | -9.8 | no |
| rest / schedule | 29 | 0.6% | 1.6% | 0.39x | -9.7 | no |
| unexplained | 236 | 5.1% | 13.6% | 0.38x | -9.5 | no |

Registered rule result: only **rotation change** qualifies (31% of misses, 6.0x its base rate).

**Read it with care.** That category is defined partly by the miss itself (a top-8 player 8+ below GP, or an outsider 8+ above), so its lift is built in. I am not treating it as a finding on its own. Context added after seeing the result (not part of the rule):

- **Early exits are one-sided and large**: 721 misses, GP too high every time, average +12.9 minutes. Foul trouble and injury are not separated in this data, so the next step is a left-tail model (quantile minutes), not a better mean.
- **(Withdrawn, see correction below.) Teammate-out games are the opposite**: 953 misses, GP too low in 890 of them (93%), average -9.8 minutes. When a teammate is out, the players who stay get more than GP gives them. This is a real, directional bias and the best-supported build target.
- Blowouts: GP too high 785 times, too low 461. Blowout misses are 27% of misses but 25% of all games, so blowouts are not the problem.
- Top-8 players: GP too high 1806, too low 1357. Outside the top 8: too high 681, too low 767.
- Rest / back-to-back: 29 misses, not a driver.

> **Correction (added after the absorption test, see [minutes-absorb-results.md](minutes-absorb-results.md)).** The direction counts above are an artifact of the order causes are assigned: too-high misses by top-8 players were sorted into other buckets, so "teammate out" looks one-sided (890 of 953 too low). Overall bias in games with a player out is +0.26 minutes, not -9.8. The "teammate-out lift" build target below is withdrawn. The early-exit finding stands (it is defined by the actual and always one-directional).

## B. Market-implied minutes (live 2026-10-20 to 2026-10-28)

| | |
|---|---|
| Player-games usable | 632 (56 games) |
| Correlation, gap vs (actual minus priced minutes) | 0.40 |
| Slope | 0.41 minutes per gap minute, cluster t 8.1 |
| Bottom decile | gap -15.6, actual minus priced -2.2 |
| Top decile | gap +8.4, actual minus priced +7.1 |

Registered rule: **passes** (n over 300, slope positive with t over 2, deciles on the same side as the gap).

**What it does and does not show.**

- It was run against **v2 minutes**, the minutes priced on those days. GP minutes are not logged until 2026-10-29, so the registered GP version could not run. The question that matters, whether the gap still predicts anything once GP is in, is open and is the next test (needs a few days of GP in the ledger).
- The close contains late news (lineups, scratches) that the stored minutes did not have. Part of the signal is "the market heard something". That is the point of a news detector, but it is available only near tip.
- The ratio mixes minutes and per-minute rate. A pass means the market knows something about our minutes or rates, not that it knows minutes.
- Players who did not play have no row (no result), so scratches the market priced out are missing. The true signal is probably stronger than shown.
- 56 games over 9 days. The slope is strong but is one short sample.

## What I would build, ranked by support

1. ~~Teammate-out lift~~ (withdrawn, see correction): fix the one-sided under-projection when a teammate is out, with the replacement-graph idea (who actually absorbs the minutes). Best-supported, directional, large.
2. **Left-tail minutes** (A): early exits are 16% of misses and always high. Price a distribution, not a point.
3. **Market-implied gap as a guard** (B): after GP has live days, test whether the gap adds on top of GP. If yes, use it to hold or reweight props near tip.
