# Vault NBA betting model: project plan

Status: WEEK 3 DONE (2026-09-30). Week 3 result: [prop-model.md](prop-model.md). Only Kalshi 3-pointers passes
(blend, mostly NO side); Kalshi player props carry a structural overs bias; sportsbook props show no reliable edge.
Prop model v2 (2026-09-30, [prop-model-v2.md](prop-model-v2.md)): opponent defense by position, market game total,
shooting volume x regressed %, season form, home, back-to-back and player-specific minutes swing, weighted by a ridge
stacker fit on 2024-25. On 2025-26: RMSE better on every stat, Kalshi log loss better on all four (3PM now equals the
market's), Kalshi points NO joins 3PM NO as GO. The page prices with v2; daily refresh job keeps its state current.
Prop model v3 plan: [v3-plan.md](v3-plan.md). Workstream A (ladder distributions) tested: better probabilities, same
blended edge, so v2 keeps pricing ([prop-model-v3.md](prop-model-v3.md)). B (minutes v3) + C (per-stat memory) tested
together: more accurate on every stat, but Kalshi points NO slips to WATCH, so v2 still prices
([prop-model-v3-full.md](prop-model-v3-full.md)); v3 is a shadow candidate. Confirmed starters feed (NBA.com daily
lineups, [starters-feed.md](starters-feed.md)): 99.98% accurate, best model accuracy yet, but backtest prices already knew
the lineups, so v2 stays; the recorder now logs lineup confirmations to test the timing edge live.
Week 4 = live snapshots (RUNNING from 2026-09-30: `scripts/snapshot.py` on GitHub Actions, data on the `nba-data`
branch) + injury re-pricer + shadow the GO/WATCH signals; strategy in [differentiation.md](differentiation.md).
Minutes Lab page: `nba/projections.html` (built by `build_player_projections.py`).
Previously: WEEK 2 (2026-09-29). Week 1 data done ([data-coverage.md](data-coverage.md), [../README.md](../README.md)).
Week 2 results: [game-model.md](game-model.md) (context, not an edge), [minutes-model.md](minutes-model.md),
[usage-cascade.md](usage-cascade.md).
Target: backtested and running in shadow by opening night (~Oct 20, 2026; confirm when the schedule posts).

Everything for this project lives under `nba/`, separate from the NFL betting code:

```
nba/
  docs/        PLAN.md (this), model write-ups, backtest results
  scripts/     fetchers, trainers, backtests (stdlib Python / Node, like the NFL crons)
  data/        fitted params + small published JSON (what a page would read)
  raw/         downloaded history (gitignored: box scores, odds archives)
  backtests/   per-run outputs, one folder per experiment
```

Shared code we reuse rather than copy (imported by path, not duplicated):
`betting-math.js` (de-vig, EV, Kelly), `scripts/prop-quote-guard.mjs` (price-from-own-line guard),
`scripts/fetch-sharp-money.mjs` (already polls NBA: Pinnacle, Action, Polymarket, Kalshi),
`scripts/build_pm_wallets.py` (already produces `data/pm_wallets_nba.json`), `scripts/prop_calibration.py` (isotonic + shrink).

---

## 1. The honest framing (carried over from NFL)

The NFL work already taught us what a betting model can and cannot do. Those lessons
apply here before a line of NBA code gets written:

1. **Game sides and totals are close to efficient.** Our NFL game model matched the
   market to ~0.4 pts and still went 48% ATS. The NBA_Betting repo found the same:
   Vegas misses by 9 to 10.5 pts per game and the author could not consistently beat it.
   Expect the NBA game model to be **context first**; it only earns "edge" status if it
   passes the gate in section 6.
2. **Props are where the edge lives.** Softer, more markets, slower to react to
   rotation news. NBA props also react far more to a single injury than NFL props do,
   which is the lever we are best set up to exploit (see NFL vacated-share work).
3. **The scoreboard is CLV and priced ROI, never accuracy.** "68% accurate on
   moneylines" means nothing when favorites win 68% anyway. Every result is graded
   against the **no-vig closing price** and at the **price actually available**.
4. **Decide the go/no-go rule before looking at results.** Same 50+ bets / 2 SE rule
   the NFL signal tracking uses.

## 2. What we take from each source

| Source | Take | Leave |
|---|---|---|
| [kyleskom/NBA-ML-Sports-Betting](https://github.com/kyleskom/NBA-Machine-Learning-Sports-Betting) | Feature set shape (team rolling stats + rest days), Kelly sizing output, moneyline + O/U as separate targets | XGBoost/Keras stack, no published backtest, odds used as features without a clear as-of time (leakage risk) |
| [NBA-Betting/NBA_Betting](https://github.com/NBA-Betting/NBA_Betting) | Its leakage discipline (features computed only from prior games, keyed by game_id), "relative to league average" normalisation, predicting **spread vs the line** rather than raw margin, its honest benchmark (market MAE 9 to 10.5) | AutoGluon, stats.nba.com as the backbone (rate limits, blocks cloud IPs so it would fail in GitHub Actions) |
| [algorithmic.co platform](https://www.algorithmic.co/works/nba-sports-betting-platform/) | The three feature ideas worth testing: **player fatigue** (back-to-backs, travel, minutes load), **rolling 5/10/20 windows**, **lineup/availability**; "optimise for EV vs market, not accuracy"; a profitability gate before anything ships; auto-reduce exposure on degradation | The 3,000-feature mixture of experts and the "8 to 15% ROI" marketing claim (unverified; treat as noise) |
| Polymarket + Kalshi | Sharp-price anchor and money-flow context (already live for NBA in Sharp Money watch); historical price series for backtesting game markets; any NBA player-prop contracts Kalshi lists | Copying sharp accounts late (our study: edge gone within ~30 min) |

None of the three references do player props. That half is built from our own NFL prop model pattern.

## 3. Data sources (all free, probed 2026-09-29)

No paid services. Every row below was tested against a real 2025-26 game.

| Need | Source | Verified coverage |
|---|---|---|
| Schedules, player + team box, PBP, shots, rosters, officials, 2002 to now | **hoopR-nba-data** GitHub releases (sportsdataverse) | Daily release, no auth, works from Actions. Backbone (the nflverse of NBA). |
| Game lines, **open + close** | **ESPN core API** `.../events/{id}/competitions/{id}/odds` | **Every 2025-26 game** sampled (DraftKings from Dec, ESPN BET before). Spread, total, ML, open and close prices. |
| Game lines, multi-book + public bet % / money % | **Action Network** `web/v2/scoreboard/nba?date=` | Works for past dates, 6 books + ticket/money split per side. |
| Player props, **open line + price** | **ESPN core API** `.../odds/{provider}/propBets` | 2024-25: ~every game, ~1,300 props/slate (pts, reb, ast, 3PM, combos, milestones). 2025-26: Oct/Nov + playoffs; mostly missing Dec to Mar. The "current" value is often updated **after tip** (live), so treat only `open` as trustworthy; close must come from elsewhere. |
| Player props, **pre-tip price from real money** | **Kalshi historical API** `/historical/markets?series_ticker=KXNBAPTS` (+ `KXNBAREB`, `KXNBAAST`, `KXNBA3PT`, `KXNBAPR`, `KXNBARA`, `KXNBAFTM`, `KXNBA2D`) + `/historical/trades?ticker=` | ~1,100 games per market, **Nov 19 2025 to the Finals**, laddered strikes, full trade tape so the price just before tip can be rebuilt. Fills ESPN's Dec to Mar gap. |
| Game markets on exchanges | Kalshi `KXNBAGAME` (Apr 2025 on), `KXNBASPREAD` / `KXNBATOTAL` (from Apr 2026); Polymarket CLOB `prices-history` + data-api trades | Game ML full season; exchange spreads/totals only late season. |
| Injury / availability **as of report time** | **Official NBA injury report PDFs**, archived at `ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMPM.pdf` (older reports use `_HHPM`) | Verified 2025-01-15 and 2026-01-15. Parse with the `nbainjuries` package or our own PDF parse. This solves the "status at line time" problem. |
| Public-bet splits, 2021-22 to Feb 2026 | Kaggle "MGM Grand NBA betting data" | Free download; cross-check for Action splits. |
| Long-history game lines 2007 on | Kaggle "NBA Betting Data Oct 2007 to Jun 2026" | For game-model training depth beyond ESPN. |
| Advanced stats / lineups (local backfills only) | `nba_api` (stats.nba.com), pbpstats, Basketball-Reference | stats.nba.com blocks cloud IPs, so local one-time pulls only, never a cron. |
| Current depth charts + rosters | ESPN team roster + core `depthcharts` + `/transactions`, reconciled in `fetch_depth_charts.py` | 2026-27 preseason: 606 players, 142 changed teams, 96 rookies. Roster is truth, depth chart is order. |
| Live sharp prices | Pinnacle guest API (already polled by Sharp Money) | Go-forward prop anchor; no history. |

**Prop backtest plan, given the gaps (measured in week 1):**
- 2024-25: ESPN BET open lines, mid-Dec 2024 to the Finals (~72k over/under props). Open price only;
  every 2024-25 "current" value is post-tip, so no CLV that season.
- 2025-26: ESPN Oct/Nov + Apr to June (~28k), with a real pre-tip close on ~7k of them.
- 2025-26: Kalshi pre-tip prices on every ladder strike, Nov 19 to the Finals, ~1,100 games per stat.
  This covers the Dec to Mar hole where ESPN has almost nothing.
- Oct to mid-Dec 2024 ESPN BET props are dropped: no way to tell over from under (tested; order is random).

## 4. Models

### A. Game model (spread, total, moneyline)

Start from the NFL `build_game_model.py` shape (online ratings, fitted HFA and residual sd,
walk-forward) and add what matters far more in the NBA:

- **Availability-adjusted ratings.** A team's rating is the minutes-weighted sum of the
  players expected to play, not a team-level number. A star out moves NBA spreads 4 to 7
  pts; a team rating cannot see that. Player value from a box-score plus/minus style
  rating, regressed to the mean.
- **Rest and fatigue:** back-to-back, 3-in-4, travel distance, time zones, altitude (DEN/UTA).
- **Pace** for totals: possessions per 48 from both teams, rolling 10/20 windows.
- **Late-season motivation:** tanking and resting (seeding locked) flagged, not modelled, in v1.
- Target = **margin vs spread** and **total vs line**, per NBA_Betting.
- Output mirrors the NFL "Vault line": spread, total, win%, labelled model estimate.

### B. Player-prop model (the main event)

Same decomposition as the NFL prop model (volume x efficiency, distribution, isotonic
calibration, params in JSON), translated:

1. **Minutes projection** (the NBA "volume"): season start comes from the reconciled depth chart
   (`data/depth_charts.json`); players who changed teams keep their per-minute rates but get minutes from
   their NEW slot, and rookies start from a draft-slot prior. Then recency-weighted, shrunk to role prior, then
   adjusted for rest, blowout risk (spread size), foul-trouble history, and **teammates out**.
2. **Per-minute rates**: pts, reb, ast, 3PM, PRA and combos, stl/blk. Shrunk toward
   position/role priors, harder for noisy stats (3PM, stl, blk).
3. **Usage cascade when a teammate sits.** The NBA version of `build_vacated_share.py`:
   measure from history how a missing starter's usage, shots and rebounds redistribute.
   This is the single most likely source of real edge, because books are slow on
   secondary players after late scratches.
4. **Opponent + pace**: opponent defence by position with shrink-to-mean (the NFL DvP
   shrink showed raw DvP overfits), game pace from the game model.
5. **Distributions**: pts roughly Normal with mean-dependent variance; reb/ast/3PM/stl/blk
   as count models (negative binomial or Poisson); combos simulated from correlated
   components, not summed normals.
6. **Isotonic calibration** with pseudo-count shrink, reusing `prop_calibration.py`.

Markets in scope for v1: points, rebounds, assists, 3PM, PRA. Hold stl/blk/double-doubles
until their calibration earns it (the NFL TD tails overfit the same way).

### C. Market layer (shared by A and B)

- De-vigged consensus with the NFL **modal line** rule and prices only from their own line
  (`prop-quote-guard.mjs`).
- Kalshi / Polymarket / Pinnacle as the sharp anchor: demote any Vault edge that sits far
  off the sharp price, as in the NFL Kalshi anchor.
- **Price-aware grades** (grade vs the side's actual price, not flat 55%): already proven
  on NFL, port as-is.
- Correlation for pairs (player + teammate, player + game total), following the NFL QB/WR1
  correlation finding, for pick'em apps with flat multipliers.

## 5. Backtest protocol (2025-26 season)

- **Walk-forward, day by day.** Train on everything before date D, predict D, never refit
  on the future. Season-start priors from 2024-25 with regression.
- **As-of rule for every input**: box scores only from completed games before tip; lines
  from the snapshot we would actually have had (open, or a fixed time before tip); injury
  status from the report time, not the final box.
- **Two line clocks**: bet at open (or morning) and grade against close. Report both
  "bet at open" ROI and CLV. Most NBA edge decays by tip, so the timing result matters as
  much as the model result.
- **Metrics**: CLV (no-vig close), ROI at available price, calibration curve, hit rate
  with standard error. Accuracy is not reported.
- **Buckets**: every result split by market, side (over/under), line size, player role,
  and "teammate out" vs normal. The NFL week-3 retro showed one bad bucket can hide in a
  good average.
- **Never pool formats that behave differently** (regular season vs playoffs, early vs
  late season).
- **Baselines to beat**: (1) the de-vigged market itself, (2) a naive season-average
  projection. A model that cannot beat baseline 2 is not ready.

## 6. Go / no-go gates (fixed now, before results)

A market goes live as a **graded edge** only if, on the out-of-sample 2025-26 walk-forward:

- 50+ bets in the bucket, and
- positive CLV at 2 SE, and
- positive ROI at the available price, and
- calibration within the pseudo-count band.

Everything else ships as **context** (a model line next to the market) or stays in
**shadow** (logged, settled, graded, not shown), exactly like the NFL withheld-prop shadow.

## 7. Timeline (4 weeks)

| Week | Dates | Deliverable |
|---|---|---|
| 1 | Sep 29 to Oct 5 | Data: hoopR ingest, ESPN odds + propBets backfill (2024-25, 2025-26), Kalshi prop history + trade tape, injury-report PDF archive. Coverage report per month and market. |
| 2 | Oct 6 to Oct 12 | Game model v1 + walk-forward backtest. Minutes model + usage cascade measured from history. |
| 3 | Oct 13 to Oct 19 | Prop model v1 (pts/reb/ast/3PM/PRA) + calibration + full backtest vs gates. Results write-up in `nba/docs/`. |
| 4 | Oct 20 onward | Opening night: live fetch + settle + CLV scoreboard, everything in **shadow** first. Promote per market only when live results agree with the backtest. Board UI in Vault later, once something passes. |

## 8. Not doing (on purpose)

- Neural nets, AutoML, or 3,000-feature ensembles. Stdlib, small params in JSON, same as NFL.
- stats.nba.com as a dependency (blocks cloud IPs).
- Live / in-game betting.
- Any ROI claim that was not produced by our own walk-forward at real prices.

## 9. Open decisions

1. **Historical prop odds: solved for free** (ESPN propBets + Kalshi history, section 3).
   Remaining gap: a true sportsbook *close* for Dec to Mar 2025-26 props; Kalshi pre-tip
   price stands in there.
2. **Live prop feed budget.** NBA on the current ParlayAPI tier does not fit next to NFL.
   Options: upgrade, or lean on Pinnacle (free) + one soft book.
3. **Where it shows up.** Separate NBA tab in Vault Betting, or a standalone artifact
   like the Track Record / Sharp Money pages until it proves out. Recommend artifact first.

## Pages (app sidebar)

The Minutes Lab (`nba/projections.html`) is the app shell: the sidebar is page navigation and teams are picked
from the header slicer. Planned pages, each fed by something the models already produce or week 4 builds:

| Group | Page | What it holds | Fed by |
|---|---|---|---|
| Research | Minutes Lab (live) | Minutes and stat projections per team, editable | `build_player_projections.py` |
| Research | Slate | Tonight's games: Vault line vs market, injuries, back-to-backs, pace | game model + schedule + injury reports |
| Research | Injury Wire | Each injury report change, the teammates it moves, how fast each venue reacted | injury poller + minutes model + snapshots |
| Markets | Game Lines | Spread / total / ML across books, Kalshi, Polymarket; Vault line as context | snapshot pipeline + game model |
| Markets | Player Props (LIVE) | Every prop line and Kalshi ladder next to the Minutes Lab projection, calibrated model %, blended fair %, edge after fees, gate chip; Kalshi overs-bias check; hit rates at the line (L5/L10/L20/Season/H2H) and a game-log chart with minutes per game | `board.json` on nba-live (recorder, each poll), prop model params, Minutes Lab edits, `data/gamelogs.json` (build_gamelogs.py) |
| Markets | Sharp Price | Pinnacle / Kalshi / Polymarket anchor, line moves, sharp-account flow | `scripts/fetch-sharp-money.mjs` (already polls NBA) |
| Betting | Edges | Only gated signals (Kalshi 3PM NO blend, overs-bias tracker, totals watch) with size, price, capacity | prop / game backtests + live prices |
| Betting | Track Record | Shadow + live picks settled: ROI per contract, CLV, each signal vs its gate | settlement (week 4) |
| Model | Backtests | Game, minutes, usage, prop results and what passed | `nba/docs/*.md` |
| Model | Data Health (LIVE) | Recorder status per source, 48h poll timeline, per-game venue coverage, model input freshness, archive sizes | `status.json` + `polls.jsonl` on nba-data (live on vaultfantasy.com), `build_data_health.py` snapshot |

