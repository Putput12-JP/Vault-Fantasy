# Vault NBA: update plan (2026-10-10)

Supersedes the ordering in [roadmap.md](roadmap.md); keeps its feature list. Basis: a read of the NBA docs (PLAN, differentiation,
edge-calibration, experiment-log, leakage audit) and a look at the running page (`nba/projections.html`, desktop 1440 and phone 390,
preseason board of Oct 9). The live ledger was **not** read, per the experiment-log rule. Opening night is about **Oct 20**.

## Decisions (owner, 2026-10-10)

1. **Audience:** the owner, plus advanced NBA stat people with betting interest. Stat-forward and depth-friendly, not a casual-bettor
   app. Advanced pages stay reachable and are not hidden; consolidation groups them, it does not bury them.
2. **Real-money execution on Kalshi: yes.** Becomes Phase 1.5 below, in tiers: paper from opening night, micro-stakes live once the
   spread is measured and the risk layer is tested, real size only after a pre-registered sequential gate.
3. **Accent colour: keep as is.** Closed; removed from open items.

## 1. Where we stand

**Model vs market: not top tier on accuracy, and our docs say so.**
- Game model matches the close and adds nothing (t 1.2). Prop model alone is less accurate than every price.
- The money-making pieces are venue (Kalshi props overpriced YES), timing (news before the price moves) and blending
  (`market + measured nudge`). Edge is three Kalshi cells: 3PM NO (two variants) and points NO.
- After multiplicity (68 cells) only v1 3PM NO clears Holm 5% (p 0.013). Others sit at p 0.13 to 0.51. Points NO dies at a 2-cent
  half-spread; median rung volume is ~105 contracts per 30 minutes, so size is unproven.
- A promised edge keeps about half of itself at 5+ points. Kalshi-to-books edges realize ~0.
- The leakage audit's candidate-set and one-season-reuse findings are repaired or disclosed; the live ledger is the only clean test.

**What is genuinely strong:** pre-registration, trial counting, edge calibration, "bias alone" baseline on every edge, and
timestamped multi-venue history that does not exist anywhere else. That, not the projection, is the product.

**Design: good bones, too many rooms.** Findings from the screenshots:

| # | Finding | Evidence |
|---|---|---|
| D1 | **19 sidebar destinations** across 4 groups. Several overlap in purpose: Player Props / Props Table / Edges / Edge Finder / Sharp Price, and What Works / Backtest Lab / Track Record. A new user cannot tell which one answers "what do I bet tonight". | Sidebar: Minutes Lab, Tonight, Slate, Game Simulation, Injury Wire, Game Lines, Player Props, Props Table, Sharp Price, What Works, Edge Finder, Edges, Pick'em Pairs, My Bets, Track Record, Backtest Lab, Control Room, Data Health, Profile |
| D2 | **Empty states dominate.** In preseason Tonight, Props, Edges and Track Record are mostly zeros, "none", "Collecting 0/50". Correct, but opening night will look the same for the first weeks of the ledger. Needs a deliberate "building the record" state, not a wall of zeros. | Tonight: 0 out / 0 / 0. Track Record: every cell "none, 0 bets" |
| D3 | **Methodology wall under an empty list.** Player Props shows "Nothing matches" then ~12 lines of model text. Reads as the page's main content. | d-props.png |
| D4 | **Mobile header spends ~200px** (title, subtitle, theme, Refresh, status) before content; Props filter card stacks 5 control rows. | m-props.png, m-tonight.png |
| D5 | **Game Lines is the best page**: one game, every book, best price highlighted, sharp read, no-vig win %. It is the model for the others (dense, but each number answers a question). | d-lines.png |
| D6 | **Honest-edge UI is a differentiator** (realistic edge beside promised, gate chips Proven / Backtest GO / Tracking / Untested). Keep, and make the realistic edge the headline number. | d-edges.png |
| D7 | **Weight.** `projections.html` is 7.1MB (was 13.6MB; 16MB artifact limit). Local load was fast (1.5s) but that is localhost; the phone cost is untested. | file size |

## 2. Plan

Principle: **make the edge real and measurable first; add features only where they turn the edge into a decision.** Nothing here
promotes a signal to GO. Promotion stays under the experiment-log rule (300 live bets, 50 game days, ROI > 0 after fees,
z >= 2.13, CLV not negative).

### Phase 0: before opening night (now to Oct 20)

| Item | Why | Done when |
|---|---|---|
| 0.1 Run `scripts/check_board.py` the hour before the first tip | Preseason had no sportsbook props. We do not yet know which markets arrive or under which labels | Report saved; unmapped labels fixed |
| 0.2 Map ESPN milestone ladders as a ladder source if books send only those | Otherwise no two-way book prices | Props page shows book rows on opening night |
| 0.3 **Opening-night state for every page** (D2) | First weeks have no record. Show "Record starts Oct 20, N bets so far" with progress bars to 300 bets / 50 days, not zeros | Track Record, Edges, Tonight have a designed pre-record state |
| 0.4 Write the maker-fill replay's accept rule in `experiment-log.md` **before** running it | Pre-registration is how this project stays honest | Rule committed before the replay runs |
| 0.5 Write the Tier 2 gate (sequential test, game-clustered) into `experiment-log.md` before the ledger is first read | The first read of the ledger fixes what counts as pre-registered | Dated entry committed; owner sets the stopping boundary |
| 0.6 Freeze the live-ledger look schedule (monthly monitor, decisions only at the bet count) | Prevents peeking | Already in experiment-log section 3; add calendar reminder |

### Phase 1: measure the edge's real cost (Oct 20 to mid-Nov)

| Item | Why | Done when |
|---|---|---|
| 1.1 **Measure real Kalshi half-spread per stat** from the recorder's bid and ask | The whole Kalshi edge sits on an unmeasured spread. 3PM NO survives to a 3c half-spread, points NO dies at 2c | Table of median and p90 half-spread by stat, compared to the `audit_spread.py` bar |
| 1.2 **Maker-fill replay** (differentiation #2): would a resting NO at our fair price have filled, at what size, and were fills adversely selected? | Taker fee up to 1.75c a contract eats thin edges; being the maker collects the bias instead of paying it | Fill rate, size, adverse-selection delta, net of Kalshi's current maker fee (verify the schedule first) |
| 1.3 **News-reaction clock** (differentiation #3): minutes from injury or lineup status change to each venue moving | The biggest measured mispricing was a price that had not caught up. This needs only data the recorder already writes | Per-venue lag distribution and the edge available inside the window |
| 1.4 Ledger health: realized vs promised edge, live, using `calibrate_edge.py` buckets | The calibration table came from a backtest; live is the test | Live table beside the backtest table |

### Phase 1.5: real-money Kalshi execution (Tier 1 starts after 1.1 and 1.5.3)

No authenticated Kalshi client exists in the repo today: every Kalshi script is a read-only fetch (`novig_client.py` is the only signed
client, for Novig). So this is new code with new risk.

**Why tiers.** The old rule (300 live bets and 50 game days before any real money) is a floor for *detecting* an edge, not a reason to
wait: at a realistic +3% to +5% ROI, z >= 2.13 needs roughly 1,800 to 5,000 bets (about 450 at +10%). Shadow bets accumulate for free from
opening night, so no game is wasted. But paper cannot measure fills, resting-order adverse selection or the real spread, and those are
exactly what real orders teach. So real money enters in two steps, and the big gate guards only the second.

| Tier | What trades | Size | Starts when | Purpose |
|---|---|---|---|---|
| **0. Paper** | Every 3%+ candidate, shadow only | $0 | Opening night (already running) | Detection evidence; the cube is the record |
| **1. Micro-stakes live** | **3PM NO first** (owner's most confident cell); points NO added only if 1.1 shows a half-spread under ~1c; v2-blend variant is shadow only | **$1-$5 per order, total loss budget $200** (owner confirmed 2026-10-10) | After 1.1 (spread measured) and 1.5.3 (risk layer tested) | Execution data: fill rate, maker adverse selection, real spread. **Not promotion evidence.** Promotion is still judged on the shadow ledger's entry price |
| **2. Real size** | A cell that passes the gate below | Quarter Kelly on the *realistic* edge, cap 1% of bankroll per order and 3% per game, daily loss stop | Gate passed and owner approves the first day | Make money |

**Tier 2 gate (replaces "300 bets and 50 days").** Written into `experiment-log.md`, with date and reason, **before the live ledger is first
read** (it has not been). Pre-registered terms:
- A **sequential test** per frozen cell on the shadow entry price, so a strong edge can stop early and a weak one cannot be mistaken for
  luck. The backtest (e.g. 3PM NO, ~1,500 consensus bets) is the **prior**, shrunk hard because the 2025-26 season was reused many times.
- The unit of independence is the **game**, not the bet or the day: bets in one game are correlated, so z and the minimum sample are
  computed with game-clustered errors (as `calibrate_edge.py` already does).
- Floors that stay: ROI > 0 after fees, mean CLV against the close not negative, and the demote rule (below).
- The exact stopping boundary and the minimum number of games are set in the log by the owner. Until then Tier 2 stays closed.

**Execution rules (apply to Tiers 1 and 2):**
- **Kill switch:** one flag stops all orders. Auto-halt if live ROI after 150 orders is below 0 with z <= -1 (the demote rule), if the
  recorder's Kalshi source has not answered in 30 minutes, if a fill price is worse than the quote by more than the model's cost, or when
  the Tier 1 loss budget is spent.
- **Orders:** resting limit orders at our fair price (maker) first; crossing the spread (taker) only if 1.2 shows the edge survives the
  fee. Check Kalshi's current fee schedule and API terms before sizing.
- **Secrets:** API key and private key live in GitHub Actions secrets or a local env file, never in the repo, the page, the data branches
  or this chat. The page never holds a key; execution runs server-side only.
- **Who trades:** the order script, under these rules. Claude writes and tests the code and does not hold keys or place orders.
- **Compliance:** confirm Kalshi's rules on automated trading for the account and any state or tax implications. That check is the owner's.
- **Reconcile:** every order, fill and cancel is logged beside the shadow ledger so live fills are scored on the same cube.

| Item | Done when |
|---|---|
| 1.5.1 Authenticated read-only client (balance, positions, fills) | Fills reconcile to the ledger with no orders placed |
| 1.5.2 Paper-mode order engine on the three frozen cells | Logs the order it would place and the price it would get, beside the later real fill if any |
| 1.5.3 Risk layer and kill switch with tests | Unit tests for every halt rule; dry-run proves the halts fire |
| 1.5.4 Tier 1 micro-stakes live | Owner confirms budget and size and approves the first live day; halts verified live |
| 1.5.5 Tier 2 gate written into `experiment-log.md` | Dated entry made before the ledger is read; owner sets the stopping boundary |
| 1.5.6 Tier 2 real size | Gate passed; owner approves the first day |

### Phase 2: features that turn edge into a decision (Nov)

Ordered by value per effort; each needs no new model.

1. **Pick'em of the night + weekly recap** (roadmap #5). Pick'em correlation is already a GO; this is what a player opens the app for.
2. **Game Lines in-season** (roadmap #4): Vault-line gap row and "best price" skipping stale books. The page is already the strongest.
3. **Price and edge beside each Minutes Lab projection.** Turns a minutes judgement into a bet in seconds (differentiation #6). Nobody else ships it.
4. **Injury re-pricer alerts** from 1.3: push or on-page when a status change reprices teammates beyond the cost line.
5. **Double and triple doubles** (roadmap #6): needs a real price feed; do not show a number without one.
6. **Analyst depth for the advanced audience (new):** surface what the models already compute rather than building new ones. A
   per-player minutes and usage-cascade explainer ("who absorbs the minutes and shots when X sits"), per-stat rate and half-life views
   (`rates_v3`), rolling form and opponent-by-position tables, and export of any table to CSV. Each is a view over existing data.
7. **Profile badges** (roadmap #8): lowest priority; drop if the audience does not use them.

### Phase 3: design consolidation (parallel with Phase 2)

| Item | Detail |
|---|---|
| 3.1 **Group 19 destinations into ~8, without hiding depth** (D1) | Audience is advanced users, so nothing analytical is removed; the goal is that the *first* screen answers "what is mispriced tonight" and the rest is one click deeper. Proposal, to validate with a card sort before building: **Tonight** (Slate + Injury Wire + Minutes Lab as tabs), **Props** (Player Props + Props Table as a view toggle; Edge Finder as a filter), **Game Lines** (+ Game Simulation), **Edges** (Edges + Sharp Price), **Pick'em**, **My Bets + Track Record** (one "Record"), **Models** (What Works + Backtest Lab + Control Room + Data Health, advanced), **Profile**. Keep old hashes redirecting; `viewOf()` already routes by hash. |
| 3.2 **One answer per prop, full workings one click away** | Default view = fair, edge, realistic edge, stake, gate chip. For this audience the "Model details" panel stays open-able on every row and shows every term (as the Props page already does), including v2 vs the v3 shadow. |
| 3.3 **Methodology to a docs page, not under an empty list** (D3) | Empty list says what is missing and when it fills; the methodology moves to a linked "How it works" page this audience will read. |
| 3.4 **Mobile header** (D4) | One 48px bar: title, status dot, refresh. Fold the subtitle and theme toggle into the menu. Collapse Props filters to chips plus one "Filters" sheet. |
| 3.5 **Weight** (D7) | Test on a throttled mobile profile. If load is slow, lazy-load Backtest Lab and Control Room data and keep headshots as shipped palette PNGs. |
| 3.6 **Use the app's motion and segmented-control primitives** | New tabs/filter strips use `.vseg` and the `RAILS` pill; no new CSS (see CLAUDE.md). |

### Phase 4: new edges (only after Phase 1 data is in)

Each needs its own pre-registered row in `experiment-log.md` and its own 300 bets. No live credit without that.
- Polymarket and pick'em flat-payout structure (retail-priced, same logic as Kalshi bias). Pick'em correlation is the starting point.
- Resting-order strategy, if 1.2 shows fills are not adversely selected.
- Re-test minutes v3 with starters on **live** Expected to Confirmed timestamps (the backtest feed is post-game truth and does not count).
- Copula A2 on the 2026-27 holdout (already scheduled, first look Nov 9).

## 3. What would change this plan

- **1.1 shows a half-spread above ~2c on props:** points NO is dead, drop it from promotion; focus on 3PM NO, pick'em and news lag.
- **1.2 shows adverse fills dominate:** maker strategy is NO-GO; the product is the information (Game Lines, alerts), not execution.
- **Live ledger shows the Kalshi YES bias closed:** stop betting it (the differentiation doc already sets this rule) and lean on timing and pick'em.
- **Page is slow on a real phone:** Phase 3.5 jumps ahead of Phase 2.

## 4. Not in scope / do not do

- Do not claim an edge in marketing until the ledger earns it. The Track Record page already says so well.
- Do not add another model variant. Three exist that are not shipped (v3, v3_full, minutes v3); the problem is not model quality.
- Do not read the live ledger for new patterns and propose them; the experiment log says that earns no credit.

## 5. Open questions

1. Tier 2 bankroll, and whether Kalshi's automated-trading terms are confirmed OK for the account. (Blocks 1.5.4 onward.)
2. Tier 2 stopping boundary and minimum games for the sequential gate (owner sets; or Claude proposes one to react to).
