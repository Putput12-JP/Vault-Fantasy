# Which market is sharpest on NBA game lines: results

Rules: nba/docs/game-venues-test.md (committed before this ran). 2025-26 season, every game with a Polymarket, Kalshi and ESPN BET closing moneyline; home team's chance; lower is better.

Games: 1300. Home token matched by team name. Games where Polymarket and the sportsbook closed 35+ points apart: 0 (kept).

## 1. Sharpness at the close

| Venue | Log loss | Brier |
|---|---|---|
| Sportsbook (ESPN BET) | 0.5751 | 0.1967 |
| Polymarket | 0.5755 | 0.1971 |
| Kalshi | 0.5838 | 0.1979 |

| Comparison | Log-loss difference | SE |
|---|---|---|
| Kalshi minus Polymarket | +0.0082 | 0.0059 |
| Sportsbook (ESPN BET) minus Polymarket | -0.0005 | 0.0010 |
| Sportsbook (ESPN BET) minus Kalshi | -0.0087 | 0.0060 |

Decision rule: a venue moves ahead of the sportsbook in the Slate's fallback order only if its log loss is lower by 2+ SE. Polymarket: **no**. Kalshi: **no**.

## 2. Does the game model add to Sportsbook (ESPN BET)?

Blend weight fit on 716 games before Feb 1: w = 0.12. On the 584 games after: log-loss change +0.0011 (SE 0.0011). Verdict: **NO-GO** (rule: lower by 2+ SE).

## Cross-check against the orderbook archive

Polymarket price-history close vs the archive's mid one minute before tip (2026 playoff games):

| Game | Date | Price history | Archive mid |
|---|---|---|---|
| NY@SA | 2026-06-14 | 0.635 | 0.635 |
| SA@NY | 2026-06-11 | 0.545 | 0.545 |
| SA@NY | 2026-06-09 | 0.535 | 0.535 |

