# NFL: does a special teams rating improve the game model? (2026-10-14)

`scripts/nfl_special_teams_study.py`. The CFB model gained a special teams rating, so this asks the same of the NFL Vault line
(`data/game_model.json`, the model behind the NFL Model page). Rules were written before the run: lam, carry and weight chosen on
2017-2021 by the average miss only, 2022-2025 read once, and GO only if the miss falls by more than 2 standard errors of the paired
difference and the 3+ point pick record against the close is not worse.

**Special teams value.** Every punt, kickoff and field goal has an EPA from the possessing team's side (nflverse play-by-play,
clipped to +-3, extra points left out). A game's special teams net from the home side is the home team's EPA on those plays minus the
away team's. Ratings are a ridge on that net, centred on last season's final rating times a carry, refit each week from earlier games
only, and added to the existing walk-forward margin as weight x (home rating - away rating).

**Tuning, 2017-2021** (27 settings, 1,355 games). Baseline miss 13.249 points (root mean square of the final margin). Best setting
(ridge 50, carry 0.8, weight 0.5) 13.244. The best three settings sit at the edge of the grid (the strongest shrinkage, the smallest
weight): the data is asking for the rating to be turned down.

| | Baseline | With special teams | Market |
|---|---|---|---|
| Miss, test 2022-2025 (1,139 games) | 12.663 | 12.659 | 12.423 |
| Miss, 2026 so far (79 games, not used for any choice) | 12.697 | 12.675 | 12.429 |
| Paired difference in squared miss, test | t = 0.63 | | |
| Slope of the model's miss on the rating gap | 0.65 (standard error 0.69) | | |

| Picks vs the close, test 2022-2025 | Baseline | With special teams |
|---|---|---|
| 1.5+ points | 273-266 | 275-271 |
| 3+ points | 103-105 | 102-103 |
| 5+ points | 35-30 | 36-29 |

Rating spread: one standard deviation of 0.42 points across teams (CFB ratings run about +-3). The 0.71 year-to-year correlation
of final ratings is inflated, because each final rating is built on last year's rating as its prior.

**What this says: NO-GO.** The miss moves by 0.004 points, 0.6 standard errors, the slope on the rating gap is one standard error
from zero, and the pick records are within noise of each other. Special teams in the NFL are too small a part of the margin
(a rating that varies by under half a point) and the market already sits 0.24 points better than the model with or without it.
Nothing ships; the NFL Model page and `game_model.json` are unchanged. The unmeasured part is a larger weight than the grid's top
(1.5), which the tuning gave no reason to expect.

Where this leaves the NFL model: the offense/defense split was already tested (`nfl-efficiency-backtest.md`) and lost, and this
rules out special teams. What is left is the information the market prices that a team rating cannot see, starting quarterback
and injury news, which the model only handles for a backup quarterback today.
