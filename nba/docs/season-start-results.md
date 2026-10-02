# Game model season start: results

Generated 2026-10-02T13:49Z by `nba/scripts/build_season_start_test.py`. Rules: [season-start-test.md](season-start-test.md) (committed before this ran). Test seasons 2024-25 and 2025-26, injury report as of tip; bootstrap over games.

## R, roster carry: **NO-GO**

k = 0.5 (tune first-4-weeks margin MAE: k 0.0: 10.245, k 0.25: 10.2031, k 0.5: 10.1719, k 0.75: 10.1759, k 1.0: 10.2155, k 1.25: 10.2774).

Margin, points:

| Games | n | Current MAE | Variant MAE | Variant - current | SE | z |
|---|---|---|---|---|---|---|
| First 4 weeks | 418 | 10.149 | 10.128 | -0.021 | 0.03 | -0.69 |
| Whole season | 2,643 | 11.1 | 11.098 | -0.003 | 0.005 | -0.46 |

## T, scoring level: **NO-GO**

Total, points:

| Games | n | Current MAE | Variant MAE | Variant - current | SE | z |
|---|---|---|---|---|---|---|
| First 4 weeks | 418 | 15.299 | 14.999 | -0.3 | 0.159 | -1.89 |
| Whole season | 2,643 | 14.862 | 14.958 | +0.096 | 0.042 | 2.27 |

First week, model total minus closing total: current -4.17 (87% under), T +0.41 (41% under), 105 games.

Either way the game model stays context only (it has never beaten the closing line).
