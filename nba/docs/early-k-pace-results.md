# Game model: early-season K and pace, results

Generated 2026-11-19T16:29Z by `nba/scripts/test_early_k_pace.py`. Rules, committed before this ran: [early-k-pace-prereg.md](early-k-pace-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters, no retune.

E chosen on the tune seasons' first 28 days: K x 1.5 for a team's first 30 games.

Tune grid (first-28-days margin MAE, who actually sat): 1.0|0: 10.245, 1.5|10: 10.2648, 1.5|20: 10.2395, 1.5|30: 10.2383, 2.0|10: 10.3194, 2.0|20: 10.2834, 2.0|30: 10.2805, 3.0|10: 10.5121, 3.0|20: 10.4338, 3.0|30: 10.4275, 4.0|10: 10.7635, 4.0|20: 10.6474, 4.0|30: 10.6392

## E (margin MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| first28 | 2025 | 211 | 9.669 | 9.603 | -0.066 | 0.059 | -1.13 |
| first28 | 2026 | 207 | 10.638 | 10.468 | -0.17 | 0.066 | -2.57 |
| first28 | pooled | 418 | 10.149 | 10.031 | -0.117 | 0.044 | -2.69 |
| whole | 2025 | 1321 | 10.912 | 10.924 | 0.012 | 0.02 | 0.6 |
| whole | 2026 | 1322 | 11.288 | 11.296 | 0.007 | 0.022 | 0.34 |
| whole | pooled | 2643 | 11.1 | 11.11 | 0.01 | 0.014 | 0.67 |

Against the close (whole, games with a line): variant, close, n = (11.11, 10.824, 2641); shipped = (11.101, 10.824, 2641).
Information test against the close: variant {'n': 2641, 'b_market': 1.064, 'g_model_gap': 0.125, 'g_se': 0.088, 't': 1.42}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## P (margin MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| first28 | 2025 | 211 | 9.669 | 9.68 | 0.011 | 0.011 | 1.07 |
| first28 | 2026 | 207 | 10.638 | 10.66 | 0.022 | 0.01 | 2.22 |
| first28 | pooled | 418 | 10.149 | 10.165 | 0.017 | 0.007 | 2.29 |
| whole | 2025 | 1321 | 10.912 | 10.913 | 0.001 | 0.006 | 0.1 |
| whole | 2026 | 1322 | 11.288 | 11.286 | -0.002 | 0.006 | -0.41 |
| whole | pooled | 2643 | 11.1 | 11.099 | -0.001 | 0.004 | -0.22 |

Against the close (whole, games with a line): variant, close, n = (11.1, 10.824, 2641); shipped = (11.101, 10.824, 2641).
Information test against the close: variant {'n': 2641, 'b_market': 1.068, 'g_model_gap': 0.124, 'g_se': 0.095, 't': 1.3}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Q (total MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| first28 | 2025 | 211 | 15.385 | 15.154 | -0.231 | 0.149 | -1.55 |
| first28 | 2026 | 207 | 15.212 | 15.162 | -0.05 | 0.157 | -0.32 |
| first28 | pooled | 418 | 15.299 | 15.158 | -0.142 | 0.113 | -1.26 |
| whole | 2025 | 1321 | 14.744 | 14.732 | -0.012 | 0.052 | -0.24 |
| whole | 2026 | 1322 | 14.981 | 15.053 | 0.072 | 0.055 | 1.31 |
| whole | pooled | 2643 | 14.862 | 14.892 | 0.03 | 0.038 | 0.78 |

Against the close (whole, games with a line): variant, close, n = (14.883, 14.315, 2641); shipped = (14.852, 14.315, 2641).
Information test against the close: variant {'n': 2641, 'b_market': 0.982, 'g_model_gap': -0.12, 'g_se': 0.073, 't': -1.64}; shipped {'n': 2641, 'b_market': 0.98, 'g_model_gap': -0.073, 'g_se': 0.076, 't': -0.96}.

## Verdicts, by the registered rules

| Variant | Rule 1 (t, whole season / first 28 days) | Rule 2 (both seasons same sign) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| E, early K x1.5 for 30 games | whole +0.67 (not worse); first 28 days -2.69 (better) | yes (-0.066, -0.170) | 1.42 vs 1.23, ok | **Passes the registered rule, as an early-season-only change. Not shipped.** |
| P, pace-normalised margin | whole -0.22; first 28 days +2.29 (worse) | no | 1.30 vs 1.23 | **NO-GO** |
| Q, pace term in totals | whole +0.78 (worse); first 28 days -1.26 | no | -1.64 vs -0.96 | **NO-GO** |

## Reading it

- **E is real but small.** The first 28 days improve by 0.117 points of margin MAE over 418 games (10.149 to 10.031). It is still worse than the market close in that window (9.44 in 2025, 10.30 in 2026 per `game-model-challenger-results.md`). The whole season is unchanged.
- **The tune surface is thin.** On the tune seasons the chosen cell (K x 1.5 for 30 games) moved first-28-days MAE from 10.245 to 10.238. Larger multipliers were worse, and the best cell sits on the grid's lowest multiplier and longest window, so the true optimum may be milder and longer. The test-season gain is bigger than the tune gain, which is a reason to freeze and read forward, not to trust it.
- **It would not fix the Memphis case.** A 1.5x step is K 0.06. Memphis's gap comes mostly from carrying half of last season's -11.4, and a modest K change moves a 15-game rating by well under a point.
- **P and Q: pace does not help inside this model.** Normalising margins for pace made the first four weeks slightly worse. A pace term made totals worse over the whole season (14.862 to 14.892) and the information test against the close went from t -0.96 to -1.64. This matches the challenger result: the possession-based idea adds nothing here.
- **Not shipped.** `game_model.json`, the Slate and the Game Picks record are unchanged. The first-28-days result alone is a hypothesis, per the prereg.

## Next step if wanted

Freeze E (K x 1.5, 30 games) and score it forward on the first 28 days of 2026-27 and the first 28 days of 2027-28. 2026-27 is already past day 28 (it started Oct 21), so the first full forward read is next October, unless the user wants a partial read on games already played with the frozen setting.
