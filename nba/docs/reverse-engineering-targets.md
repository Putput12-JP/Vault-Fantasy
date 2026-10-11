# Reverse-engineering targets for the NBA model

Written 2026-10-11. Source: a web sweep plus a read of `morluto/rea` (REA, "Reverse Engineer Anything"). Results of the
experiments run from this list are in the **Results** section at the bottom, updated as each finishes.

## What REA is good for here

REA is an MCP toolkit for taking apart native binaries, JS/Electron apps, websites, saved network captures (HAR) and
Android APKs. For this model the useful modes are:

- **Websites and HAR captures:** find the JSON feeds behind a page (lineups, injuries, prop ladders, projections).
- **Android APKs:** read how pick'em apps (PrizePicks, Underdog, Sleeper) structure their feeds.
- Native-binary work is not relevant to any target below.

**Boundary:** public endpoints and formats of venues we already read only. We do not crack paywalled projection
products (DARKO, EPM, LEBRON) or bypass auth. For those we rebuild from published methods (patent filings, interviews).

## Ranked targets

| # | Source | License | Use | Status |
|---|---|---|---|---|
| 1 | [shufinskiy/nba_data](https://github.com/shufinskiy/nba_data) | Apache-2.0 | Bulk play-by-play 1996-2025, shot details, pbpstats possession data | Ingested (`build_pbp_stints.py`) |
| 2 | [pbpstats](https://pypi.org/project/pbpstats/0.0.10/) | MIT | Possession / lineup / shot-zone parsing | Not needed yet; our stint builder covers lineups |
| 3 | DARKO ([patent filing](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12611586), [interview](https://thepowerrank.libsyn.com/kostya-medvedovsky-on-the-darko-nba-player-projections)) | public patent | Daily Kalman-filtered true-talent state | Patent text not readable from the build sandbox (host unreachable); rates v3 already borrows the per-stat-memory idea |
| 4 | Dunks & Threes EPM | proprietary | Predictive plus-minus; methodology not confirmed | Only secondary descriptions found. RAPM is our public stand-in |
| 5 | Polymarket data API | public | Trades yes, order-book history no | We already record depth live; our archive is the asset |
| 6 | [propedge](https://github.com/vntw0n3/propedge), [open-prop](https://github.com/WalrusQuant/open-prop), [Bball](https://github.com/jlwin1995-alt/Bball/pull/1) | various | Ideas only (same-player correlation, rate-per-minute) | Copula work already covers correlation |
| 7 | [UBC-MDS minutes predictor](https://github.com/UBC-MDS/NBA-Minutes-Predictor) | check repo | Minutes benchmark: R² 0.65 with LightGBM | Compare our minutes R² against it |

Caveats: the web sweep found no peer-reviewed study of NBA prop-market efficiency or closing-line value. "Props are less
efficient than sides" comes from betting blogs; our own backtests are the evidence we trust.

## Pipeline added

```
nba_data nbastats_<yr>.tar.xz -> build_pbp_stints.py -> raw/stints_*.csv -> build_rapm.py -> rapm json
```

`nba_data` stops at the 2024-25 season, so the 2025-26 season has no play-by-play from this source. Anything built here is
a prior from past seasons, not a live feed.

## Results

All four ran on free data only, holdout kept apart from tuning. Scripts: `build_pbp_stints.py`, `build_rapm.py`,
`build_garbage_time.py`, `build_kalman_rates.py`. Raw outputs are in `nba/raw/` (gitignored).

**1. Play-by-play stints.** Lineups rebuilt from substitutions for 2022-23 to 2024-25: 3,341 of 3,690 regular-season
games parsed (about 90%; the rest had starters we could not infer). Sanity: about 114 home points and 100 possessions a
game, which matches the league. The 2025-26 season is not in `nba_data`, so this is a prior, not a live feed.

**2. Ridge RAPM (lineup-based player rating).** Fit on 2022-24, tested on 2024-25 stints: +0.33% lower RMSE than a
constant, which is expected for stints that short. Top ratings are plausible (Jokic, Embiid, Shai, Kawhi, Lillard).
Year-to-year correlation for players with 1,000+ minutes is 0.39 (offence 0.31, defence 0.38). **It adds nothing**
to next-season per-minute production (R² 0.781 with and without it) or minutes per game (0.580 vs 0.581) once last
season's box score is in the model. **Verdict: NO-GO as a feature for the season-level projections.** It may still help
for players who change role or team, which this season-level test does not cover.

**3. Garbage time.** Using a Q4 lead threshold that shrinks from 25 points (9:00 left) to 8 (1:00 left), 64-72% of games
reach it, so the definition is loose. The pregame strength gap (prior-season margins, standing in for the spread
because ESPN is blocked from this sandbox) explains under 1% of garbage-time minutes either way: linear
`max(0, |gap|-6)` R² 0.0054, quadratic 0.0070. **Verdict: no case for replacing the minutes model's linear blowout term
with a different pregame shape.** Whether a game becomes a blowout is decided during the game. The ESPN-line version of
this test should be rerun where ESPN is reachable.

**4. Kalman filter vs tuned EWMA** (per-minute rates, tuned on 2023-24, scored on 2025-26, minutes-weighted RMSE):

| stat | EWMA | Kalman | gain |
|---|---|---|---|
| points | 0.2127 | 0.2120 | +0.34% |
| rebounds | 0.0929 | 0.0923 | +0.65% |
| assists | 0.0705 | 0.0701 | +0.47% |
| 3PA | 0.0768 | 0.0763 | +0.69% |
| 3PM | 0.0491 | 0.0489 | +0.42% |

Consistent sign on all five stats, but small. The baseline here is a plain EWMA, weaker than rates v3 (which already
adds position priors and separate percentage handling), so this does **not** show a gain over v3. Next step if wanted:
swap the Kalman state into `build_rates_v3.py` and rerun the Kalshi edge backtest under the pre-registered rules.

## Follow-up (same day)

**5. Does play-by-play help the minutes model? No, on the one idea tested.** `build_pbp_minutes_test.py` strips garbage time
out of recent minutes (an EWMA of competitive minutes and one of garbage minutes, against one EWMA of total minutes) and
predicts next-game minutes, trained on 2022-24 and tested on 2024-25, players with 10+ prior games. RMSE 6.804 with
and without the split, a 0.00% gain, so it fails the 1% rule. Together with the RAPM and pregame-garbage-time results
above, play-by-play has not moved the minutes forecast. What it has not tried: in-game signals the model cannot see
before tip (foul trouble, first-sub timing), which would matter for live repricing rather than the pregame number.

**6. Kalman volume rates vs rates v3** (`build_kalman_rates_v4.py`, same harness and seasons as v3, given true minutes):

| stat | RMSE v3 | RMSE v4 | gain |
|---|---|---|---|
| points | 4.9937 | 4.9870 | +0.13% |
| rebounds | 2.1126 | 2.1108 | +0.09% |
| assists | 1.6735 | 1.6684 | +0.30% |
| 3PM | 1.1451 | 1.1450 | +0.01% |

It passes the pre-registered rule (better on 4 of 4, none worse), but the gains are tiny, and widening the tuning grid (the
first grid hit its edges) moved nothing, so the ceiling is about 0.1-0.3%. I did not run a significance test on the paired
errors. Rates v3 and minutes v3 both beat v2 on accuracy and still did not move the Kalshi edge, so I would not expect this
to. **Verdict: a wash. Not wired into pricing; kept as a candidate (`data/rates_v4_candidate.json`).**

**7. Kalman on the shooting percentages, plus paired significance** (`build_kalman_pct_v4.py`; details in
`docs/rates-v4-kalman-pct.md`). Four models scored on the same 28,071 player-games:

| stat | v3 RMSE | Kalman volume | t | Kalman percentages | t |
|---|---|---|---|---|---|
| points | 4.9937 | 4.9870 (+0.14%) | +4.17 | 4.9945 (-0.01%) | -0.51 |
| rebounds | 2.1126 | 2.1108 (+0.08%) | +2.76 | unchanged | n/a |
| assists | 1.6735 | 1.6684 (+0.30%) | +5.83 | unchanged | n/a |
| 3PM | 1.1451 | 1.1450 (+0.01%) | +0.35 | 1.1452 (-0.00%) | -0.21 |

- **Kalman percentages: FAIL.** No gain on either stat they touch. v3's decayed makes plus prior attempts already
  extracts what there is in shooting percentages, which are mostly noise at game level.
- **Kalman volume: the gain is real but small.** Significant on points, rebounds and assists (t = 4.2, 2.8, 5.8), not on 3PM,
  and no larger than 0.3% RMSE. This revises item 6 from "a wash" to "statistically real, practically tiny".
- Combining both is no better than volume alone.
- Rule amendment, stated openly: the first run crashed because the percentage model leaves rebounds and assists identical to v3
  by construction. I changed its pass rule (better on both affected stats, none worse, t >= 2 on one) before reading any
  result. It fails either way.
- Not tested: whether a 0.1-0.3% rate improvement moves the Kalshi edge. That needs the price archive (`raw/tables`), which
  is not in this sandbox. Rates v3 and minutes v3 were both more accurate than v2 and did not move the edge, so the
  default expectation is that this will not either.

## Round 2: attacking minutes directly

**8. Gradient-boosted minutes (LightGBM) vs the linear model: PASS on both holdouts** (`build_minutes_gbm.py`, full tables in
`docs/minutes-gbm.md`). Minutes is the biggest error term in every prop, so this is where accuracy is. Same pre-tip features for
every model (three EWMAs of minutes, last game, last-5 mean/std, starter rate, rest, back-to-back, games in 7 days, home,
position, teammates' vacated minutes, game-model margin), absences taken from who actually sat.

| Holdout | Linear (shipped-style) RMSE | Richer linear | LightGBM | Gain | t |
|---|---|---|---|---|---|
| train 2022-25, test 2025-26 | 6.311 | 6.215 | 5.999 | +4.94% | +20.5 |
| train 2022-24, test 2024-25 | 6.369 | 6.248 | 6.031 | +5.30% | +21.2 |

- About two thirds of the gain is nonlinearity, not new information: LightGBM beats the *richer* linear model by 3.5% on both
  holdouts. Most of its signal comes from the three EWMA speeds together (ew2 46%, ew3 32%, ew1 9% of split gain), so the model is
  mainly learning how to blend slow and fast recent-minutes signals depending on context.
- Misses of 8+ minutes drop from 18.3% to 16.4%.
- **It barely moves the stat projections:** points RMSE 6.024 to 5.985 (0.65%), rebounds 2.510 to 2.496, assists 1.827 to 1.820,
  3PM 1.245 to 1.243. Stat noise given minutes dominates. A 5% minutes gain is worth roughly a 0.6% gain on points.
- A small version ships: 300 trees x 15 leaves (8,700 nodes) loses 0.1% RMSE vs 600 x 31 (36,600 nodes). That size exports as a
  JSON file of a couple hundred KB and can be scored in plain Python/JS like the rest of the pricing code. Caveat: that size sweep was
  scored on the 2025-26 holdout, so pick the size on 2024-25 before shipping.

**Caveats that matter before shipping.** (a) The linear baseline is a stand-in built from the shipped feature list, not the actual v3
code, and this sandbox has no injury reports, so the comparison uses oracle absences. v3 scores 6.065 with the real report and
5.907 knowing starters; the table above is not comparable to those. (b) The shipped model is judged on Kalshi edge, not RMSE, and
accuracy gains in minutes v3, rates v3 and starters did not move the edge. That test needs the price archive, which is not here.
(c) The GBM must be re-scored with injury-report absences, where vacated-minutes inputs are noisier.

**9. Per-player minutes spread: statistically real, below my bar (FAIL).** `build_minutes_spread.py` (tables in
`docs/minutes-spread.md`) models how wrong the minutes forecast will be for each player tonight. Pricing today widens each prop by
one per-player number (an EWMA of squared misses). A LightGBM on the squared miss scores a better Gaussian CRPS on both holdouts
(3.292 vs 3.317, then 3.304 vs 3.331: +0.75% and +0.80%, t = 13.6 and 13.8) and has better-calibrated 80% intervals (82.4% vs 79.8%
and 79.4%), but the pre-set bar was 1%, so it fails. Even a single constant sd is within 0.2-0.3% of the per-player
EWMA, so per-player minutes volatility is worth very little either way. Not pursued.

**10. Shadow model wired in (2026-10-11).** The GBM now runs live as a shadow, never priced:
- `scripts/minutes_gbm.py` is the single definition of the state, the features and the scorer (stdlib only). The training walk
  (`build_minutes_gbm.py`), the daily job (`build_model_state.py` writes `live.gbm`) and pricing (`Pricer.game_minutes_gbm`) all
  call it. `data/minutes_gbm.json` (300 trees, 260 KB) matches LightGBM to 1.4e-11.
- `ledger.py` logs the GBM minutes as a fifth value on every minutes row, and each settled day gets a `gbm` block (average miss
  and 8+ misses for v2 and the GBM on the same players). The Tonight page's Track Record prints a one-line comparison.
- `check_minutes_gbm_parity.py`: live pricing and the backtest agree to 0.00000 minutes on 833 player-games (39 games). Two bugs
  were found and fixed by it: the exported EWMAs were rounded to 4 decimals, which flipped split thresholds and moved projections by
  up to 0.9 minutes, and the training walk used the position on tonight's box row where live only has the last known one
  (accuracy numbers above are from after that fix and moved by at most 0.02%).
- Live differences from the backtest, stated so nobody is surprised: absences come from the injury report, not from who sat; the
  margin is the market spread, not the game model's; there is no team-total rescale (the backtest scored it raw); a just-traded
  player is scored on his old team's history, as in the backtest.
- Not wired: the Tonight table has no GBM column. The page prices in JavaScript and would need a JS copy of the tree scorer and
  a parity test; not worth building before the shadow earns it.

## Not done

- DARKO patent text: the USPTO host is not reachable from the build sandbox. Read it from a machine with access.
- ESPN lines: blocked by the sandbox network policy (CONNECT 403), so no spread-based garbage-time test.
- REA was not run against any app. It adds nothing until we pick a specific public site or app to inspect.

