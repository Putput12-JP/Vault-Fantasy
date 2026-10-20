# Vault Fantasy betting features: code-grounded inventory (for OddsJam comparison)

All sources are local repo paths (repo root `/Users/jacobputman/Desktop/Draft Tool`), read on 2026-09-26 at HEAD `f683ebb4`. Line numbers refer to that snapshot. No web research was done; claims about OddsJam are not made here except as the checklist given in the assignment.

## 1. What betting pages/tabs exist, what each shows, and how it is ranked

### Takeaway
Betting is one page (`#page-betting`) with three views reached from a nav dropdown: Game Markets, Player Props (the "Edge Board"), and Prop Outlook, plus a Best Bets hero above the boards, a Track Record dashboard (My Picks / Vault Record / Vault Game Record / Win % Check), and a Lineup Command "Market check" card outside the betting page. It is a single-sport (NFL), pregame-only, model-first product: ranking is by de-vigged EV and a Vault A-F grade, not a pure market-vs-market screen.

### Cited Findings
**Page shell and navigation**
- Single container `<div class="page z1" id="page-betting">`; `showPage('betting')` calls `window.initBetting()` - [index.html:5706](index.html), [index.html:15072](index.html)
- The whole betting module is inlined in index.html (roughly lines 41094-48465: VaultBettingMath, VaultPropHistory, VaultPropModel, VaultMarketProj, then the UI IIFE). Standalone `betting-app.js`/`betting-data.js`/`betting-math.js` files still exist in the repo root but index.html does not load them via `<script src>` (only auth scripts and vault-mobile.js are external) - [index.html:171-176, 53782](index.html), [index.html:41094-48465](index.html)
- Nav dropdown entries: "Game Markets (Spreads · totals · moneylines)", "Player Props (Edge Board · every book)", "Prop Outlook (0-100 grade · role + matchup)" - [index.html:48935-48956](index.html)
- On mobile the dropdown is replaced by an in-page Games / Props / Outlook segmented control - [index.html:47029-47036](index.html); changelog "Betting now works on your phone" (2026-09-09) - [index.html:13827](index.html)
- Header provenance line reads "VEGAS · props · <source> · N games · N players" - [index.html:48427-48429](index.html)

**Game Markets**
- Desktop is a full-slate odds-screen table: one row per game with spread, total and ML at best available price, +EV side flagged, Vault model line and Polymarket money as columns; click to expand every book inline (changelog 2026-09-12) - [index.html:13729-13734](index.html)
- 2026-09-25 redesign: each game opens with Vault's projected score and win %, best spread/total/ML, a plain-English "Vault vs market" read; filter by day; sort by kickoff, biggest Vault-vs-market gap, best price, or most money traded; season record of Vault's line at top - [index.html:13527-13534](index.html)
- Per-game EV: `gameBets()` computes consensus fair via per-book de-vig median, best price among quotes AT the consensus line only (alt lines excluded), after exchange fees; EV = `findEdge(fairProb, impliedProb(bestPrice))` - [index.html:43208-43252](index.html)
- "Vault vs. the market" board: 3 biggest spread gaps, 3 total gaps, 3 ML gaps; these are auto-tracked into Track Record - [index.html:13864-13870](index.html), [index.html:44131-44148](index.html)
- Line movement tag (STEAM / SHARP / RLM) from open vs current using `lineMovement()` - [index.html:43176-43191](index.html). Caveat: "open" is the first time Vault's hourly snapshot saw the line, not the true market open - [scripts/snapshot-line-history.mjs:1-15](scripts/snapshot-line-history.mjs)
- Kalshi "Real Money" strip (contracts traded, open interest, 24h volume, "Heating up" flag, "Real money leans BUF +4pt") - [index.html:13847-13854](index.html); Polymarket strip in dollars with 24h net directional flow ("$4.2k into BUF") - [index.html:13738-13748](index.html)
- Kalshi cross-venue ARB tag ("ARB x% · Spread") on game markets - [index.html:43407-43408, 43740-43741](index.html)
- Preseason / sample-slate banners when no live lines - [index.html:47037-47045](index.html)

**Player Props Edge Board**
- Rows = player x market; columns include best line/price, fair price, EV, Vault projection, Vault grade, Sim %, opponent rank, # books, injury/role/cascade chips; sortable by any column (changelog 2026-08-27) - [index.html:14264](index.html), render fns `renderPropsBoard`, `gradeColCell`, `projCellHTML`, `simCellHTML`, `oppRankCell`, `nBooksTag` at [index.html:44732, 46423-46672](index.html)
- Prop EV: `rowFairEV()` - fair = `consensusFair` (median of each two-sided book's own de-vig), best price per side after exchange fees, EV per side via `findEdge` - [index.html:44471-44505](index.html)
- Flat-priced DFS lines with no two-sided price get `pickemFE()`: line and best price shown, fair/EV = null, sorted below priced edges - [index.html:44507-44538](index.html)
- Filters drawer: book filter (added 2026-09-25; board recomputes line/best price/edge/grade from only chosen books, persisted), Over/Under lean filter, min grade, trend (hit-rate) range, games range, "fade Vault's team lean" filter (2026-09-26) - [index.html:44634-44677, 46874-46952](index.html), [index.html:13476-13480, 13536-13543](index.html)
- "Grade vs" picker: grade against price-implied break-even (default since 2026-09-25) or a DFS entry break-even (2-5 pick Power, Flex, even money) - [index.html:43902-43920, 47161-47162](index.html), [index.html:14240-14245, 13560-13566](index.html)
- Prop detail: both Over and Under cards side by side, per-book "Compare Books" table (exchange shows posted and after-fee price), game-log chart and hit rates incl. H2H split, projection hero, wind note - [index.html:45814-45929, 46634](index.html), [index.html:14057](index.html), [index.html:13504-13510](index.html)
- Safety gates surfaced to users: single-book lines flagged not graded (2026-09-06), "thin edge" cap to C on markets below break-even this season (pass yds, completions, INT, rush+rec yds) (2026-09-25), big "Vault edge" warns rather than tempts, injury flags, role-change flags, vacated-share and gameday-inactive ripple adjustments - [index.html:13879, 13552-13558, 14075, 14205, 14010, 13712, 13721](index.html); `edgeCaution()` / `edgeUnverified()` / `projGapCaution()` at [index.html:46083-46296](index.html)
- Props vanish at kickoff (pregame only; no live/in-play) - [index.html:13791](index.html), `ebGameOver` [index.html:44540](index.html)
- Separate Anytime TD board - [index.html:46954-47022](index.html)

**Best Bets hero**
- Shown above both views; top precomputed props (default `--top=4`) plus up to 3 "Model leans" game cards explicitly labeled context-not-edge - [index.html:47470-47476](index.html), [scripts/build_best_bets.mjs:1-60](scripts/build_best_bets.mjs)
- Ranked by "confidence-adjusted EV vs the best available price", 9 modeled markets only, >=2 books corroborating, >=1 true sportsbook (not only PrizePicks/Underdog/Sleeper), price band -250..+200, MIN_GAMES 8, MAX_PROJ_GAP 0.40, Kalshi sharp-anchor demotion - [scripts/build_best_bets.mjs:7-35, 55-79](scripts/build_best_bets.mjs); feed note: "Top props by confidence-adjusted EV on corroborated lines (≥2 books), modeled markets only." - [data/lineup-feed.json best_bets.note](data/lineup-feed.json)
- Current feed (week 3, 2026-09-26): 4 props, 3 game leans; example row Dawson Knox rec o1.5 bet365 +145, EV 26.9, grade A, 9 books - [data/lineup-feed.json best_bets](data/lineup-feed.json)

**Prop Outlook**
- Line-free 0-100 grade per player/prop from Opportunity, Quality, Matchup, Environment pillars, GOOD/BAD/EVEN matchup chip, FADE flag - [index.html:13605-13611](index.html); data from `data/market_grades.json` built by `scripts/build_market_grades.py` in update-lineup and check-prop-feed workflows - [.github/workflows/update-lineup.yml](.github/workflows/update-lineup.yml), `renderGrades` [index.html:48185](index.html)

**Track Record**
- My Picks: user taps Track on a prop side or a game lean; stored in browser `localStorage` keys `vault-bet-picks` / `vault-game-picks` only (no account sync found) - [index.html:43931-43934, 44047](index.html)
- Logged fields: grade, vaultEV, projection, price, book, week, opp, timestamp - [index.html:43998-44019](index.html)
- Auto-settles props against nflverse/ESPN box scores (W/L), games against final score - [index.html:44022-44045, 44149](index.html)
- My Picks aggregates: W/L, win rate, "units" = flat ROI computed against the user's chosen break-even, breakdowns by grade, side, market, position - [index.html:45091-45115](index.html). It does NOT use the actual logged price for ROI, and has no stake sizes and no CLV per user pick.
- Vault Record / Vault Game Record: league-wide ledger of the model's calls from `data/bet_results.json`, week and single-game filters, CLV as headline read for games - [index.html:13690-13694, 13677](index.html), [index.html:45027-45700](index.html)
- Win % Check: calibration/reliability chart of promised vs realized win % - [index.html:13624](index.html), `_drawCalib` [index.html:45442](index.html)

**Lineup Command "Market check" (outside Betting)**
- Lists players where props imply a different week than Sleeper's projection, scored in each league's settings, e.g. "Rec yds 81 vs 64"; swap previews show market number; "market's stat lines landed closer ... than Sleeper's in 7 of 8 stat types" over weeks 1-3; lineups still optimized on Sleeper - [index.html:13495-13502](index.html); engine `window.VaultMarketProj` [index.html:41726-41870](index.html)

**Related research page**
- Offense Blueprints (pace, PROE, target trees) under Research, used as betting context - [index.html:13937-13940, 47185-47450](index.html)

### Inferences
- Vault is positioned as "model + market" (own projections, grades, track record) rather than OddsJam's "market vs market" (sharp-book fair price). Its EV math is market-derived (consensus de-vig), but the headline selector (grade, Best Bets) blends Vault's own projection.
- Every surface is NFL-only and pregame-only.

### Gaps
- Could not visually verify current rendering; inventory is from code and changelog text. Exact column set on mobile vs desktop not enumerated.

## 2. Data sources, pipelines, books, cadence, latency

### Takeaway
Everything is static JSON committed to the repo by GitHub Actions crons and served by GitHub Pages; there is no backend odds service. Sportsbook odds come from ParlayAPI on a free-tier credit budget (hourly only in game windows), DFS pick'em lines are scraped keyless hourly, and Kalshi/Polymarket keyless hourly. Effective latency is roughly 1 hour plus Actions queueing plus Pages deploy, so it is not a real-time screen.

### Cited Findings
**Pipelines (workflow → script → output)**
- `update-lineup.yml` → `scripts/build-lineup-feed.mjs` (+ `scripts/src-vegas.mjs`) → `data/lineup-feed.json` (`vegas_games`, `vegas_player_props`, `vegas_teams`, `vegas_meta`). Uses `PROPS_API_KEY`/`PARLAY_API_KEY` (ParlayAPI, "10+ books incl. DFS") and optional `ODDS_API_KEY` (The Odds API), ESPN scoreboard fallback, preseason workbook fallback - [.github/workflows/update-lineup.yml:60-80](.github/workflows/update-lineup.yml), [scripts/src-vegas.mjs:1-30, 93-110, 332-381](scripts/src-vegas.mjs)
- `update-lineup.yml` cadence: offseason Feb-Aug once daily 09 UTC; in-season Sep-Jan daily 08 UTC + hourly Sun 13-23 UTC + hourly Mon/Thu 15-23 UTC; comment sizes this at 876-996 credits/month, busiest month 166 runs = 996 credits "the most whole 6-credit runs that fit under 1,000" - [.github/workflows/update-lineup.yml:18-36](.github/workflows/update-lineup.yml)
- `update-props.yml` hourly at :17, year-round: `fetch-pickem-props.mjs` (PrizePicks via partner-api.prizepicks.com, Underdog `api.underdogfantasy.com/v1/over_under_lines`, Sleeper `api.sleeper.com/lines/available`; keyless, no credits) → `fetch-kalshi-props.mjs` → `fetch-weather.mjs` (Open-Meteo) → `build_best_bets.mjs`; commits only on change - [.github/workflows/update-props.yml:1-70](.github/workflows/update-props.yml), [scripts/fetch-pickem-props.mjs:1-50, 152, 435, 528](scripts/fetch-pickem-props.mjs)
- `check-prop-feed.yml` every 3h: health check, refetches pick'em + best bets + market grades if the feed looks bad - [.github/workflows/check-prop-feed.yml:18-75](.github/workflows/check-prop-feed.yml)
- `update-kalshi.yml` hourly :37 → `fetch-kalshi.mjs` → `data/prediction_markets.json` (KXNFLGAME winner + KXNFLTOTAL / KXNFLSPREAD strike ladders, volume/OI) - [.github/workflows/update-kalshi.yml:13-31](.github/workflows/update-kalshi.yml), [scripts/fetch-kalshi.mjs:1-30, 136-178](scripts/fetch-kalshi.mjs)
- `update-polymarket.yml` hourly :47 → `fetch-polymarket.mjs` (Gamma API, main ML market + event-level dollar flow) → `data/polymarket.json` - [.github/workflows/update-polymarket.yml:12-30](.github/workflows/update-polymarket.yml), [scripts/fetch-polymarket.mjs:1-25](scripts/fetch-polymarket.mjs)
- Snapshotters (no API calls, read the feed): `update-line-history.yml` :47 → `data/line_history.json`; `update-prop-history.yml` :27 → `data/prop_line_history.json`; `update-game-history.yml` :29 → `data/game_line_history.json` - [.github/workflows/update-line-history.yml:13-31, update-prop-history.yml:14-32, update-game-history.yml:15-33](.github/workflows/)
- `update-bet-settlement.yml`: daily 13:10 UTC fallback + every 15 min in game windows (Sun 17-23 UTC, Sun-night/Mon/Thu 00-04 UTC) → `fetch_espn_boxscores.py`, `settle_bets.py`, `prop_calibration.py`, `build_market_implied_calib.py`, weekly prop/game retros - [.github/workflows/update-bet-settlement.yml:25-106](.github/workflows/update-bet-settlement.yml)
- Model refits: `update-game-model.yml` Wed 15:40 UTC + in-season Sat 16:00; `update-prop-projections.yml` Wed 15:20 UTC - [.github/workflows/update-game-model.yml:12-40](.github/workflows/update-game-model.yml), [.github/workflows/update-prop-projections.yml:14-32](.github/workflows/update-prop-projections.yml)

**Books actually present (live feed snapshot, 2026-09-26)**
- Game markets, 15 venues: FanDuel, Novig, DraftKings, BetRivers, Bovada, Fliff, Pinnacle, bet365, BetMGM, BetOnline, Caesars, Fanatics, Hard Rock Bet, Parx Casino, ProphetX; 32 games - [data/lineup-feed.json vegas_games](data/lineup-feed.json)
- Player props, 16 venues: Underdog Fantasy (1682 quotes), PrizePicks (943), Sleeper (490), Hard Rock Bet, Parx Casino, BetMGM, BetRivers, bet365, Fanatics, Fliff, DraftKings (82), FanDuel (80), Caesars, Pinnacle (70), Novig, Pick6 - [data/lineup-feed.json vegas_player_props](data/lineup-feed.json). Note DK/FD prop coverage is thin relative to DFS apps.
- `vegas_meta`: live_source and props_source "parlay-api.com", 580 prop players, 9 prop events, feed `generated` 2026-09-26T12:41Z vs pick'em refresh 13:05Z - [data/lineup-feed.json vegas_meta](data/lineup-feed.json)
- 21 prop markets in feed: rush_rec_td, rec_yd, rec, anytime_td, long_rec, sacks, tackles, rush_yd, long_rush, rush_att, rush_rec_yd, pass_td, pass_yd, pass_att, pass_cmp, pass_rush_yd, long_pass, pass_int, fg_made, kick_pts, rush_td - [data/lineup-feed.json](data/lineup-feed.json). Game markets: spread, total, ML only (no alt lines, halves, quarters, team totals as bettable markets; implied team totals are derived).
- Other inputs: nflverse stats/games.csv for projections and settlement, ESPN box scores overlay (props settle minutes after games), `data/weather.json`, `data/vacated_share.json`, `data/role_volume.json` - [scripts/settle_bets.py:1-45](scripts/settle_bets.py), [index.html:41404-41446](index.html), [scripts/fetch-weather.mjs:1-12](scripts/fetch-weather.mjs)

### Inferences
- Best-case freshness for sportsbook prices is hourly during Sun/Mon/Thu windows and daily otherwise (e.g., a Tuesday-Saturday line move is not reflected until the next 08 UTC run). DFS lines are hourly all week. OddsJam-style screens update in seconds, so any "+EV finder" claim from Vault is structurally stale for fast-moving books.
- Coverage breadth is bounded by what ParlayAPI returns; there is no direct per-book scraping of sportsbooks.

### Gaps
- Actual end-to-end latency (cron fire to Pages deploy) was not measured here; GitHub cron slippage is noted in workflow comments ("hourly game-history cron routinely slips to every 4-6h" on busy Sundays) - [.github/workflows/update-bet-settlement.yml:34](.github/workflows/update-bet-settlement.yml).
- ParlayAPI per-request pricing is inferred (6 credits/run), not from published pricing (per project memory note).

## 3. Models and how EV is computed

### Takeaway
EV is computed the standard way (no-vig fair from a consensus of books vs best price), with careful per-book de-vig and exchange-fee netting. On top sits Vault's own statistical prop projection (calibrated, market-shrunk) that drives grades, plus a game model that is explicitly labeled context because it does not beat the market.

### Cited Findings
- `VaultBettingMath`: JS port of the MIT `betting` skill from machina-sports/sports-skills; exposes americanToProb, devig, devigTwoWay, findEdge, kelly, evaluateBet, findArbitrage, parlay (with correlation input), lineMovement, fairFromRow, netAmerican, feeKind, kalshiCost, consensusFair - [index.html:41083-41094, 41388-41391](index.html)
- Consensus fair = de-vig each book that hangs both sides with hold 0-15%, dedupe shared feeds (bwin→BetMGM, Pick6→DraftKings), take median - [index.html:41361-41386](index.html). Changelog 2026-09-26 "Fairer fair prices" - [index.html:13504-13510](index.html)
- Exchange fees: Kalshi taker 0.07·P·(1−P), ProphetX 2% on winnings, Novig none; best price and EV use net payout - [index.html:41326-41359](index.html)
- Note: consensus is an unweighted median across all books; there is no Pinnacle/sharp-book-weighted fair (Pinnacle is just one input) - inferred from [index.html:41370-41386](index.html)
- Prop projection model (`VaultPropModel`, `scripts/build_prop_projections.py`, `data/prop_model.json`): recency-weighted volume × efficiency, role-anchored volume, per-market distribution (Normal / lognormal / negative binomial / Poisson for TDs), isotonic calibration, shrink/blend toward vig-free market; weekly refit - [docs/prop-model.md:1-30](docs/prop-model.md), [index.html:41496-41676](index.html)
- In-season feedback: settle_bets writes `data/edge_scoreboard.json` with per-market win rate, CLV beat rate, model vs market log-loss, reliability, projection bias, and a measured model/market blend weight (e.g. rec_yd blend w_measured 0.25) - [data/edge_scoreboard.json](data/edge_scoreboard.json), changelog "projections now learn from every settled result" [index.html:13697-13702](index.html)
- Honest-signal evidence: for rec_yd, model log-loss 0.7046 vs market 0.6920 (market better), win rate at close 53.9%, CLV beat rate 60% - [data/edge_scoreboard.json markets.rec_yd](data/edge_scoreboard.json)
- Price-aware grades: grade judged vs the side's actual price break-even, sub-50% sides not lifted by shrink, "Price Value" tag - [index.html:13488-13493, 13560](index.html), `gradeLetter`/`cappedGradeLetter` [index.html:46393-46406](index.html)
- Game model ("Vault line"): team power ratings from nflverse games.csv; walk-forward backtest margin RMSE 13.21 vs market 12.87, ATS 48.4%, O/U 48.9%; "context, not an edge"; line anchored halfway to live market for display - [docs/game-model.md:1-25](docs/game-model.md), [index.html:13805-13809](index.html), `gmPredict` [index.html:43129](index.html)
- Game-script multiplier (`_scriptMult`, `data/game_script_model.json`), wind multiplier on pass_yd (>10 mph, floor 0.85), DvP matchup, vacated-share and QB-out re-projection adjustments - [index.html:46583-46660](index.html), [index.html:13512-13518](index.html)
- Kalshi sharp anchor for props: de-vigged Kalshi prop mids with OI/spread; Best Bets demotes picks that disagree with a liquid Kalshi strike - [scripts/fetch-kalshi-props.mjs:1-35](scripts/fetch-kalshi-props.mjs), [index.html:13750-13755](index.html)

### Inferences
- Methodologically Vault is sound on de-vig mechanics and more transparent than typical +EV tools about model limits (thin-edge caps, "context not edge"), which is a differentiator; but its fair price is not sharp-weighted, a known weakness vs OddsJam-style "Pinnacle/sharp fair" approaches.

### Gaps
- No closing-line-based evaluation of the market-only (de-vig) EV flags themselves was found separate from model picks.

## 4. Bet tracking/CLV, alerts, deep links, bankroll/Kelly, arbitrage/middles, promo conversion

### Takeaway
Tracking exists (auto-settling, per-grade stats) and CLV is computed server-side for the model ledger, but user-level tracking is local-only, flat-unit, and without CLV. Kelly and parlay math exist in the library but are not surfaced. Arbitrage is limited to sportsbook-vs-Kalshi on game markets. There are no alerts, no sportsbook deep links, no middles, no promo converter, no public API.

### Cited Findings
- CLV: `settle_bets.py` computes line CLV, no-vig probability CLV, price CLV and beat_close for every snapshotted prop and game in the model ledger - [scripts/settle_bets.py:1-20, 462-485, 556, 705-717](scripts/settle_bets.py). Ledger size: 1483 settled props, 99 settled games, 963 unsettled props, 168 unmatched names - [data/bet_results.json meta](data/bet_results.json)
- User My Picks: localStorage, W/L auto-settle, flat ROI at a chosen break-even, no CLV, no stake/units entered, no sync - [index.html:43931-44045, 45091-45115](index.html)
- Kelly: `kelly()` and `kellyFraction` defined in VaultBettingMath, but no UI call site found (grep for `.kelly(` returns only the definition) - [index.html:41172, 41179-41186](index.html). No bankroll feature in the app (the "Vault Ledger" $1k paper bankroll is a separate artifact per project memory, not in index.html).
- Parlay: `parlay({..., correlation})` defined; no UI call site found; `.bxo-parlay` CSS class exists in the mobile board styles but no parlay builder logic was found - [index.html:41225-41256, 42728-42734](index.html). Project memory notes a measured QB~WR1 correlation opportunity not yet productized.
- Arbitrage: only book + Kalshi, game markets (ML direct; spread/total via Kalshi strike-ladder interpolation), gated sum < 0.99 and must use a Kalshi leg (`usedK`); Kalshi leg priced at bid/ask mid plus taker fee - [index.html:43252-43280](index.html). Book-vs-book arbitrage and prop arbitrage are not detected.
- Middles: no middle detection found (grep for "middle" returns only unrelated hits).
- Alerts/notifications: no Notification/PushManager/showNotification usage in index.html, sw.js or vault-mobile.js (grep empty).
- Sportsbook deep links / bet slips: no links to DraftKings/FanDuel/BetMGM/PrizePicks/Underdog/Kalshi found; no affiliate or promo-code code (grep empty).
- Promo/bonus converter: none found.
- Public API: none; data is static JSON on GitHub Pages (`putput12-jp.github.io/Vault-Fantasy/data`) - [index.html:41413-41416](index.html)
- Line movement: open-vs-current tags on game markets only; prop line history is captured (`prop_line_history.json`) for settlement/CLV - [index.html:43176](index.html), [.github/workflows/update-prop-history.yml](.github/workflows/update-prop-history.yml)
- DFS pick'em: lines from PrizePicks/Underdog/Sleeper shown; grades can be judged against 2-5 pick Power/Flex break-evens - [index.html:14240-14245](index.html); flat lines get no EV number - [index.html:44507-44538](index.html)

### Inferences (first-pass gap list vs an OddsJam-style +EV product)
| OddsJam-style capability | Vault today | Gap severity |
|---|---|---|
| Positive EV finder | Yes: de-vig consensus EV per prop/game side + Best Bets; NFL only, hourly-to-daily stale, unweighted fair | Medium: freshness, sharp-weighting, sports breadth |
| Arbitrage finder | Book-vs-Kalshi on NFL game markets only | High: no book-vs-book, no props |
| Middles | None | High |
| Odds screen | Yes for NFL game markets (15 venues) and props (16 venues, heavy DFS); no alt lines/derivatives | Medium |
| Promo/bonus converter | None | High (if targeting sportsbook bettors) |
| Bet tracker with CLV | Model ledger has CLV; user tracker local-only, flat units, no CLV, no sync, no manual entry of arbitrary bets | Medium-High |
| Alerts | None | High |
| Sportsbook deep links / bet slip | None | High (also affects monetization via affiliates) |
| Parlay / correlated parlay tools | Math exists (with correlation param), unused; correlation research exists | Medium (quick-win candidate) |
| DFS pick'em EV | Partial: entry break-even grading; no slip optimizer, no per-app payout EV, no correlated slips | Medium |
| Kelly / bankroll sizing | Math exists, unused | Low-Medium (quick win) |
| API | None (static JSON only) | Low for consumer, High for B2B |
| Live/in-play | None (props vanish at kickoff) | High, but infrastructure-bound |
| Multi-sport | NFL only | High for breadth |
- Distinctive Vault assets OddsJam lacks (from findings above): own projection model with public track record and calibration chart, exchange money-flow (Kalshi + Polymarket), fantasy integration (Lineup Command market check), transparent "thin edge"/"context not edge" caveats.

### Gaps
- Could not confirm whether any pick sync to Firebase exists outside index.html (grep of index.html, auth/, vault-mobile.js found the localStorage keys only in index.html).

## 5. Paywall/tier or monetization code related to betting

### Takeaway
There is no paywall, tier gate, subscription, affiliate, or referral code anywhere in the betting module; all betting features are free and ungated.

### Cited Findings
- Grep of index.html for paywall / season pass / isPro / premium / subscription / stripe / founder / entitlement returned no betting-related hits (only unrelated dynasty "premium" and tier words) - [index.html](index.html)
- No affiliate links or promo codes in code (grep for affiliate / referral code / promo code / sportsbook URLs empty) - [index.html](index.html)
- Changelog frames Kalshi money flow as "it stays free, no new data cost" - [index.html:13853](index.html)

### Inferences
- The only monetization-adjacent hooks are indirect: GA4 events (per project memory) and the share card; betting is currently a pure cost center (ParlayAPI budget) with no revenue path. Sportsbook/DFS affiliate deep links would be the most natural first hook given the existing "best book" column.

### Gaps
- Project memory references a planned tiered Season Pass / Founder's Lifetime strategy, but nothing implementing it for betting was found in code.

## 6. Constraints discovered

### Takeaway
Hosting and data economics are the binding constraints: static GitHub Pages, GitHub Actions crons (best-effort scheduling, hourly at best), and a 1,000-credit/month ParlayAPI free tier sized to the credit.

### Cited Findings
- Static hosting: frontend reads committed JSON from GitHub Pages; data base URL `https://putput12-jp.github.io/Vault-Fantasy/data` - [index.html:41413-41416](index.html)
- ParlayAPI: 6 credits/run, 1,000/month free tier; in-season schedule sized to 876-996 credits/month; offseason daily - [.github/workflows/update-lineup.yml:18-36](.github/workflows/update-lineup.yml)
- GitHub cron is best-effort: props cron runs at :17 because "top-of-hour is GitHub's most congested/most-skipped slot"; "hourly is the practical max for a free cron that also rebuilds Pages on each change" - [.github/workflows/update-props.yml:8-12](.github/workflows/update-props.yml)
- Multiple crons push to main and must rebase to avoid conflicts - [.github/workflows/update-line-history.yml:42](.github/workflows/update-line-history.yml), [.github/workflows/update-bet-settlement.yml:106](.github/workflows/update-bet-settlement.yml)
- PrizePicks public API is Cloudflare-blocked; uses partner-api host - [scripts/fetch-pickem-props.mjs:5-8, 68-70](scripts/fetch-pickem-props.mjs)
- ProphetX/Novig deeper anchors sit behind authenticated partner APIs (paid follow-up) - [scripts/fetch-kalshi-props.mjs:10-13](scripts/fetch-kalshi-props.mjs)
- Settlement name-matching misses: 168 unmatched prop names in ledger - [data/bet_results.json meta](data/bet_results.json)

### Inferences
- Matching OddsJam on freshness (seconds), breadth (dozens of books, many sports), alerts, and live betting would require a real backend (always-on poller + push), a paid odds feed, and an auth/entitlement layer; these are architectural changes, not features. Vault's realistic lane is model-driven, NFL/fantasy-native +EV with honest track record, adding cheap wins (Kelly sizing, correlated pick'em slips, affiliate deep links, synced tracker with CLV).

### Gaps
- Cost of a paid odds feed tier or ParlayAPI upgrade not verified here (memory mentions a $5/mo option, unverified).
