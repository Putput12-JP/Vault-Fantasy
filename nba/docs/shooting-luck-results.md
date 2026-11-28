# Game model: three-point shooting luck, results

Generated 2026-11-19T18:11Z by `nba/scripts/test_shooting_luck.py`. Rules, committed before this ran: [shooting-luck-prereg.md](shooting-luck-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Chosen on the tune seasons: M = {'L': 0.25, 'K0': 300.0}; T = {'L': 0.5, 'K0': 1000.0}. Tune MAE (all games, who actually sat): M|S: 10.5252, M|L=0.25|K0=300: 10.5185, M|L=0.25|K0=1000: 10.5201, M|L=0.5|K0=300: 10.54, M|L=0.5|K0=1000: 10.5436, M|L=0.75|K0=300: 10.5861, M|L=0.75|K0=1000: 10.5927, M|L=1.0|K0=300: 10.654, M|L=1.0|K0=1000: 10.6651, T|S: 14.6057, T|L=0.25|K0=300: 14.5737, T|L=0.25|K0=1000: 14.5722, T|L=0.5|K0=300: 14.5679, T|L=0.5|K0=1000: 14.5652, T|L=0.75|K0=300: 14.5872, T|L=0.75|K0=1000: 14.582, T|L=1.0|K0=300: 14.6317, T|L=1.0|K0=1000: 14.6261.

## M (margin MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| whole | 2025 | 1321 | 10.912 | 10.886 | -0.026 | 0.017 | -1.57 |
| whole | 2026 | 1322 | 11.288 | 11.26 | -0.028 | 0.017 | -1.68 |
| whole | pooled | 2643 | 11.1 | 11.073 | -0.027 | 0.012 | -2.23 |
| first28 | 2025 | 211 | 9.669 | 9.642 | -0.027 | 0.033 | -0.81 |
| first28 | 2026 | 207 | 10.638 | 10.617 | -0.021 | 0.032 | -0.66 |
| first28 | pooled | 418 | 10.149 | 10.125 | -0.024 | 0.022 | -1.08 |

Against the close: {'variant': {'model': 11.074, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.076, 'g_model_gap': 0.152, 'g_se': 0.101, 't': 1.51}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## T (total MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| whole | 2025 | 1321 | 14.744 | 14.636 | -0.108 | 0.04 | -2.7 |
| whole | 2026 | 1322 | 14.981 | 14.889 | -0.091 | 0.038 | -2.41 |
| whole | pooled | 2643 | 14.862 | 14.763 | -0.1 | 0.027 | -3.74 |
| first28 | 2025 | 211 | 15.385 | 15.33 | -0.055 | 0.077 | -0.71 |
| first28 | 2026 | 207 | 15.212 | 15.118 | -0.094 | 0.076 | -1.23 |
| first28 | pooled | 418 | 15.299 | 15.225 | -0.074 | 0.056 | -1.33 |

Against the close: {'variant': {'model': 14.752, 'close': 14.315, 'n': 2641}, 'shipped': {'model': 14.852, 'close': 14.315, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 0.987, 'g_model_gap': -0.034, 'g_se': 0.084, 't': -0.41}; shipped {'n': 2641, 'b_market': 0.98, 'g_model_gap': -0.073, 'g_se': 0.076, 't': -0.96}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| M, margin (L 0.25, K0 300) | -2.23 (better) | yes (-0.026, -0.028) | 1.51 vs 1.23, ok | **Better by the rule; effect trivial. Not shipped.** |
| T, scoring (L 0.5, K0 1000) | -3.74 (better) | yes (-0.108, -0.091) | -0.41 vs -0.96, ok | **Better by the rule. Not shipped; freeze and read forward.** |

## Reading it

- **T is the first variant in this series to pass.** Total MAE falls from 14.862 to 14.763 over 2,643 games, in both seasons (14.744 to 14.636, 14.981 to 14.889). The gain is about 0.1 points. It does not close the gap to the market: against the closing total the model is 14.752 versus 14.315 for the close (2,641 games), so it still loses by 0.44 points.
- **M passes by a hair.** Margin MAE 11.100 to 11.073 (about 0.03 points). The tuner chose the smallest L on the grid (0.25), and every larger L was worse than shipped on the tune seasons (L 1.0: 10.654 against 10.525), so the real optimum may be lower and the gain is likely smaller still.
- **Why scoring benefits more than margin.** The offense and defense ratings drive totals, and they were the ones soaking up hot and cold shooting. The margin rating has a lower learning rate and was less exposed.
- **The tune and test gains differ.** On the tune seasons T improved total MAE by 0.04 (14.606 to 14.565); the test seasons show 0.10. Tune K0 sits on the grid edge (1000) and L is interior (0.5). That is a reason to freeze and read forward, not to trust 0.1.
- **The first 28 days are not significantly better** (T -0.074, SE 0.056). The idea that noise matters most early is not supported here.
- **Not shipped.** `game_model.json`, the Slate and the Game Picks record are unchanged. A pass on the registered rule is not a bet signal: the totals gap against the close is unchanged in sign.

## Next step

Freeze T (L 0.5, K0 1000) and M (L 0.25, K0 300), score them on 2026-27 games from now on against the shipped model and the close, and read after about 300 games. Nothing goes live before that read.
