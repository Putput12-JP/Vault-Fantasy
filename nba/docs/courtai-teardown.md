# CourtAI teardown, and what it means for Vault NBA

Written 2026-10-19. Method: REA (`capture_browser_scenario`, headless Chrome, signed out) against https://www.courtai.app/, two captures
(home plus `/matchups`, `/matchups/<id>`, `/targets`, `/help`, `/connect`). Evidence = retained network bodies (3 JSON APIs, 11 JS chunks)
and page DOM. **Boundary:** public, signed-out surface only. No sign-in, no auth bypass, no calls beyond what the page makes on load.

## What was and was not observed

| Observed (signed out) | Not observed (behind Google sign-in) |
|---|---|
| Home slate, `/api/games/ladder`, `/api/games/slate`, `/api/games/slate/edges` bodies | Matchup detail page data, Defense Sheet numbers |
| Route table, API route names, UI strings from every page chunk | The Matchup Score formula (the page says "Scores and deltas are delivered by the API", so it is server side) |
| Help page clause grammar, Connect page (MCP tool list) | Targets, Backtests, saved filter sets, natural language query results |

Everything below about the score is **inference from field names and UI copy**, not a read of the formula.

## What CourtAI is

A Vite + React SPA (Firebase Google auth, axios, Barlow fonts) over a Python-looking API (snake_case, ISO timestamps). One product idea:

1. **Diet.** What share of a player's possessions, shots or assists come from each slice.
   - Play types (10): Transition, Isolation, P&R ball handler, P&R roll man, Spot up, Cut, Handoff, Off screen, Post up, Putback.
   - Shot zones (5): Restricted area, Paint non-RA, Mid-range, Corner 3, Above-break 3.
   - Shot types (3): Catch and shoot, Pull-up, Inside 10 ft.
   - Assist locations (5): At rim, Corner 3, Arc 3, Short mid, Long mid.
2. **Defense Sheet.** What each opponent allows per 48 in those same slices, with a 1 to 30 rank (30 = allows the most) and a `vs_avg_pct` deviation.
3. **Matchup Score.** Diet joined to Defense, reported as "% vs league" per stat. Example copy: "Cut 28% of plays, UTA allow the 3rd most" gives Ayton +9.6%.
   Likely a diet-weighted sum of defense deviations (inference). Shows the "why" rows that drive it, plus a sigma filter (at least 1 or 2 sigma).
4. **Slate** (public): per game, top 3 players by absolute score. Real payload: `games[].effects[] {name, season_scoring, thin, value}` and `scores[] {canonical_id, value}` for every player in the game. `thin` flags low diet evidence.
5. **Targets.** A saved rule of the form "opposing team X, players whose diet slice is at or above N%" (for example P&R ball handler at least 30% vs Charlotte). Flags every fit on game day and **backtests** it (games graded by margin vs season average, with a red/green deviation scale).
6. **Game-log search.** Plain-English clauses compile to filters: `last N`, `since`, `with` / `without` teammate, `against top/bottom N <defense stat>`, `at home`, `10+ FGA`, `playing 30+ minutes`. Defense stats include all the slices above plus OPP_PTS/REB/AST/STL/BLK/FTA/TOV and assist locations.
   Public demo ladder: Jalen Johnson 22.5 PTS (72 games), 22.1 without Trae Young (63), 23.1 vs bottom-10 defenses at 25+ min (18). **The sample size is printed on every step.**
7. **Lines overlay.** Matchup page shows posted lines by provider (Dabble, Kalshi, Novig, Polymarket, PrizePicks, Underdog), flags "lines disagree", and compares to season scoring. Per-provider freshness is tracked and shown ("Lines last read ...").
8. **Other:** injury report plus "Players leaning on X" (usage ripple), rotation and minutes, on/off per-36 splits, "Last 15" window that stays closed until every team has 15 games, preseason caveats, point-in-time snapshots of the pool and injuries per game.
9. **MCP connector** at `mcp.courtai.app/mcp` (Claude and ChatGPT): one tool per question type (Slate, Matchup, Game logs, Rotation, Injury report, Injury Scenarios, On/off splits, Targets, Backtest). Every answer ends with an "as of" date. Stated policy: **"Facts, not picks."**

Observed freshness problem on their own page: pool/lines providers all `missing`, schedule `stale`, the slate showing the previous game day (Apr 12). It is the offseason, so that is expected, but they do surface it.

## What Vault NBA already has vs the gap

| Capability | Vault today | Gap |
|---|---|---|
| Opponent effect | `data/matchups.json`: positional DvP (PG..C) per stat, rank 1 to 30, `mix` blend weight | **No play-type, shot-zone, shot-type or assist-location defense**, and no player diet |
| Teammate ripple | `usage_cascade.json`, minutes model, injury scenarios in the model | Not exposed as "who leans on X" |
| Game-log filters | `gamelogs.json`, `hit_rates.json` | No clause grammar, no with/without, no opponent-rank filter |
| Lines | Prop board with Kalshi, Novig, pick'em, consensus fair, per-source ages | Already ahead of CourtAI (fair value, de-vig, CLV) |
| Backtested rules | Walk-forward backtests everywhere | No user-defined "Target" rule or its backtest |

## The caution that matters

Vault's own numbers say positional DvP carries little: `matchups.json` persistence for pts is 0.03 (reb 0.18, blk 0.21, tov 0.20), and
[differentiation.md](differentiation.md) records that the prop model is less accurate than every market price on its own and only adds
information when anchored to a price. CourtAI sidesteps this by never claiming an edge. **Copy the framing, not the implied edge.**

Play-type matchups are a *better-specified* version of DvP, so it is worth a test, but the prior is that a free-data matchup feature adds little over a closing prop line.

## Proposed build, in order

1. **Context layer first (no edge claim).** Add a per-player diet and per-team defense sheet to the NBA page: "why" rows, rank 1 to 30, thin-sample flag, as-of date. Cheap, honest, and it is the part users actually see.
2. **Game-log clauses.** Port the grammar (`without X`, `against bottom 10 <slice>`, `playing 25+`). Always print n at every step, like their ladder. We already have the logs.
3. **Pre-registered test before any pricing use.** Feature = diet-weighted defense deviation. Target = residual of the v2 projection vs the closing Kalshi/consensus line, per market, walk-forward, thin-diet rows excluded, point-in-time diet only. Same bar as the rest of `docs/`: fail means it stays a display-only fact.
4. **Targets as saved rules** only after 1 to 3, backtested with the same sample-size and CI printing.

## Step 1 result (2026-10-19): data check and the context layer

**Data reachability.** `stats.nba.com` (synergy play types, shot locations) timed out after 25 s from this Mac with and without the sandbox, and `fetch_hoopr.py`
already records that it blocks cloud IPs. So it is not usable locally or in CI. Reachable instead: ESPN play-by-play through hoopR on GitHub (shot coordinates, shot
labels, assister, dated rows, 2025-26 included). `nba_data` shot details stop at 2024-25.

| Want | Available | Point in time |
|---|---|---|
| Shot zones, assist locations | Yes, from coordinates (validated: threes start at 22.0 ft, twos end at 23.4 ft) | Yes, every row is dated |
| Shot kinds (pull-up, driving, cutting, putback) | Partly, from ESPN shot labels | Yes |
| Synergy play types (transition, iso, P&R, spot up, handoff, off screen, post up) | **No** | Not applicable |

Built: `scripts/build_diet_defense.py` writes `data/diet_defense.json` (2025-26 regular season, 1,234 games, 30 teams, 478 players), shown on the Slate page.

**Persistence (first half vs second half of 2025-26)**, compared with positional DvP in `matchups.json` (0.03 for points, 0.18 rebounds):

- Team rank of shots allowed: rim 0.59, paint 0.71, mid 0.48, corner 3 0.67, above-break 3 0.38. Three slices fall under the 0.36 cut and are not used: putback 0.28, arc-3 assists 0.28, long-mid assists 0.03.
- A player's own zone mix: 0.86 to 0.93 across the five zones (288 players with 100+ shots in each half).

So the inputs are stable, far more than positional DvP. That says the measurement is real; it says nothing yet about whether it predicts a prop result beyond the line. Step 3 still has to test that.

## Open questions (unknown, not assumed)

- **Play types.** Need a Synergy-like feed. Not found free and reachable. Without it the "Cut", "Transition" and "Pick and roll" rows in CourtAI have no equivalent here.
- Their exact score formula, diet window (season vs last 15) and sigma definition. Would need a signed-in capture, which this teardown did not do.
- Their terms of use. This note only reads the public page; do not copy their data or branding.
