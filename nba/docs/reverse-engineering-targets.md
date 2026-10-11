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

## Not done

- DARKO patent text: the USPTO host is not reachable from the build sandbox. Read it from a machine with access.
- ESPN lines: blocked by the sandbox network policy (CONNECT 403), so no spread-based garbage-time test.
- REA was not run against any app. It adds nothing until we pick a specific public site or app to inspect.

