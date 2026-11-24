# Game model: market-anchored projection, pre-registered

Written 2026-11-23, before the decomposition below was scored on any season. Runner: `nba/scripts/test_game_model_anchored.py`.
Results land in `nba/docs/game-model-anchored-results.md` only after this file is committed.

## Why

Rounds 2 to 5 and the early-clock round asked whether better RATINGS or an earlier CLOCK beat the line. None did (`game-model.md`: t = 1.23 against the close; round 4
NO-GO). On this season's rebuilt record (248 games, lineup lock) the model's gap from the line has a NEGATIVE coefficient (g = -0.76, t = -2.09), the model's error
is 11.40 points against 10.87 for the line, and no blend of the model into the line beat the line. Read together, the likeliest reading is that the line already
holds everything the model holds, and the model adds noise.

This round does not look for a better model. It asks **which part** of the model's gap carries information, so the projection can be anchored on the line and use
only the part that does:

- the **ratings part**: what the model thinks of the two teams before injury news (here the model at the 1pm report minus the line), and
- the **news part**: how much the model moves when the late injury report lands (the model at 30 minutes before tip minus the model at 1pm).

The shipped model has both. If the news part has information the close has not priced (the line moves slower or less than the model on a late scratch), an anchored
projection `close + k * news part` has an edge a ratings model never could. If neither part does, the honest projection is the line itself and the page should say so.

## Data (nothing new is fetched)

- **History:** the 2,641 games of 2024-25 and 2025-26 that `build_game_model.py` already scores, parameters frozen (`data/game_model.json`, tuned on 2022-23 and 2023-24),
  walk-forward. Per game: the model's margin with the injury report as of 1pm ("am"), as of 30 minutes before tip ("tip"), the closing spread, the final.
- **This season:** the 248 games of `data/game_picks.json`. Per game: the first look's margin (the model at the first poll with a spread inside 4 hours, `--rule 4h` rebuild),
  the lineup-lock margin and line, the final. The "ratings part" there is the 4-hour margin minus the lock line; the "news part" is the lock margin minus the 4-hour margin.

## What is scored

Result is the home margin. L is the home margin implied by the closing spread (history) or the lock spread (this season), L = -spread.

1. **Information test.** OLS `result - L = a + g1 * (M1 - L) + g2 * (M2 - M1)`, M1 = model at 1pm and M2 = model at tip (history); M1 = 4-hour margin and M2 =
   lock margin (this season). g1 is the ratings part, g2 the news part. Reported per season, pooled history, and this season, with t.
2. **Anchored projections.** On each history season, fit on the OTHER season and score on this one (two folds):
   A0 the line, A1 `L + w (M2 - L)`, A2 `L + k (M2 - M1)`, A3 the raw model M2. w and k are least-squares through the origin on the fit season. Scored by MSE and
   MAE against the final, with the paired t of the squared-error difference against A0.
3. **Picks.** Home or away at the line by the sign of the news part, for |M2 - M1| of 1 point or more (also 2+ and 3+, reported), and for the ratings part at the same cut.
   Win rate against the line at -110 (break-even 52.4%).

## Verdict (fixed now)

- **GO, news-anchored picks** when g2 has t >= 2.5 pooled over both history seasons, is positive in each season, AND the news-part picks (1+ cut) win >= 52.4% in each
  history season. This season's g2 is then read as a direction check only (n = 248; a point estimate below 0 downgrades to WATCH).
- **GO, ratings-anchored** is the same on g1. (Expected to fail: g1 = 0.118 over the whole model.)
- **Anchored projection ships as display** when an anchored projection beats the line's MSE by 2+ SE paired in both folds. Otherwise the projection shown is the line
  and the model's value is described as context.
- **NO-GO** otherwise. A NO-GO changes nothing in the record and no pick is re-priced.
- A GO would be flagged for close monitoring with its sample size and tracked as its own shadow row beside the Game Picks record. It is never an input to Top Reads or any agree total.

## Limits, stated before the numbers

- History's "1pm" report and "30 minutes before tip" report are the official reports as of those times; the close has no timestamp but is the last line, so the
  news part's information may already be in it by construction. That is the question, not a flaw: a news part with g2 = 1 would mean the line ignored late news.
- The model's injury translation (`C`, `P(out)` by status) was fitted on who sat, not on line moves, so g2 below 1 can mean the model over-reacts or the line is right.
- This season's decomposition uses the Game Simulation's one-decimal margin (`rebuild_game_picks_lineup_lock.py`), noise about 0.1 to 0.4 points.
- Several tests are scored (two parts, three cuts, two folds). A single t of 2.5 is the bar so that one lucky cell does not pass.
