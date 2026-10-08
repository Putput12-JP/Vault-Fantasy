# Edge tests, round 2: rules written before anything is run

Written 2026-10-07, before test 3 was run and before any regular-season data exists for tests 1 and 2.
The rules below are the verdict: a result is judged by what is written here, not by what the numbers look like afterwards.
Every result is reported, including the ones that fail. Nothing here changes what the page bets: a market or signal only
moves from NO-GO after a GO on its own test, and then only into shadow tracking.

Common conventions (the same ones the earlier tests used):
- Win rates and ROI are judged with the **game as the unit**: a game's bets are averaged first, and z = mean / standard error
  across games. Bets inside one game are not independent.
- GO needs z >= 2.4, a positive result in both halves of the test period, and the minimum sample stated per test.
  WATCH is z >= 1.65 with the same sample. Anything else is NO-GO.
- Fit and test periods never overlap. A choice made on the fit period is frozen before the test period is read.

---

## Test 1. News lag (forward, tracked by the existing ledger)

**Hypothesis.** When an injury or lineup change posts, some books are slow to reprice the affected teammates' props, so a
bet on the side the minutes model likes, placed while the price is older than the news, beats the closing price.

**Data.** `track.json`'s edge-type cube (`ledger.py`, `pricing.edge_types`): every shadow bet is tagged `news` when its edge
exists and the price is older than news seen in the last 3 hours (NEWS_S). Regular-season games only; preseason is reported
separately and never counted. The recorder polls every 10 minutes, so this tests lag at 10-minute resolution, not seconds.

**Rule.** Compare `news`-tagged bets with `model`-tagged bets that have no `news` tag (same edge threshold, same stakes):
- Primary: ROI per bet of `news` bets, and the closing-line value against Pinnacle's close (mean CLV, clustered by game).
- Secondary: the difference between the two groups (news minus model-only).

**GO** when, after at least 150 settled `news` bets over at least 40 games: ROI > 0 at z >= 2.4, mean CLV > 0 at z >= 2,
and both halves of the sample are positive. **WATCH** at z >= 1.65 on ROI with CLV > 0. First look: 2026-11-23.

---

## Test 2. Pick'em lines against Pinnacle (forward)

**Hypothesis.** PrizePicks and Underdog set one line per player and pay a flat multiple on either side, so a line sitting a
point or so off the sharp price leaves one side better than the flat break-even.

**Data.** The recorder's PrizePicks standard lines and Pinnacle's two-way player props on the nba-data branch.
Regular-season games only. Stats: points, rebounds, assists, 3-pointers and the four combos.

**Rule, frozen now.**
1. Join each PrizePicks line to Pinnacle's main line for the same player, stat and game, using the last poll at least 60
   minutes before tip. Pinnacle's no-vig chance is the proportional de-vig of its over and under.
2. If the two lines differ, move Pinnacle's chance to the pick'em line with the prop model's count distribution (solve the
   mean that reproduces Pinnacle's chance at its own line, then read the chance at the pick'em line). Eligible only when the
   lines are within 1.0 of each other.
3. Pick the side whose fair chance is at least **0.5425 + 0.03** (the flex-entry break-even plus 3 points). One pick per
   player and stat. Grade on the box score; a tie voids the pick.

**GO** when, after at least 150 picks over at least 40 games: hit rate minus 0.5425 > 0 at z >= 2.4 and both halves of the
sample are above 0.5425. **WATCH** at z >= 1.65. Also report the hit rate of the *other* side of the same lines (a sanity
check: if both sides clear, the sample is the problem). First look: 2026-11-23, or sooner if 150 picks arrive.

---

## Test 3. Alternate-line tails (backtest, run now)

**Hypothesis.** Books price far-from-the-line alternate rungs with a favourite-longshot shape: the over at long odds is
overpriced and the over at short odds is underpriced, so some price bucket of alternate overs has a positive return.
Alternate ladders carry only the over, so only overs can be bet.

**Data.** `raw/tables/props_espn.csv`, rows with `kind = alt`, played games only, every market that has them
(points, rebounds, assists, 3-pointers, the combos, steals, blocks). Every line ends in .5, so there are no pushes.
- Fit period: 2024-25, the **open** price (`over_px_open`).
- Test period: 2025-26, the **pre-tip close** price (`over_px_cur`, rows with `cur_is_pretip = 1`).

**Rule, frozen now.**
- Bet $1 on the over at every alternate rung. Price bucket = the price's implied chance, vig included:
  [.02, .10), [.10, .20), [.20, .35), [.35, .50), [.50, .65), [.65, .80), [.80, .95].
- **Fit:** a bucket is *selected* if, in 2024-25, it has at least 1,000 bets, ROI > 0 and z >= 1.5.
- **Test:** each selected bucket is judged on 2025-26 only. **GO** if it has at least 300 bets over at least 40 games,
  ROI > 0 at z >= 2.4, and ROI > 0 in both halves of the season (split by date). **WATCH** at z >= 1.65 with the same
  sample. If no bucket is selected on the fit season, the result is NO-GO and the test table is reported descriptively only.
- Report every bucket in both seasons, overall and per market, whatever the verdict. Per-market rows are descriptive and
  never used to pick anything.

**Known limit.** ESPN's alternate ladders come from one provider and are over-only, so there is no de-vig and no way to
bet the under. A pass here would justify a shadow bet on those rungs and nothing more.
