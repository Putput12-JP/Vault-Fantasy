# Week 4 retro + deep dive: props and game model

_Run Monday 2026-10-05, before Monday night (NO @ ATL unsettled). Source: `data/bet_results.json`, `data/best_bets_record.json`, `data/game_rules.json`, the Vault Ledger database, `data/prop_line_history.json`, and git history of `data/prop_model.json`. Prop units are at each side's own price; spreads and totals at -110; moneylines at the opening price._

_Corrected the same day, once point-in-time grading was built: every prop below is graded with the exact model version that was live when its line was first graded (most lines open Monday or Tuesday, before the Wednesday refit). The first draft graded each week with that week's Wednesday model and overstated the A/B record (it said +8.1u for Week 4 and +23.5u for the season)._

## The short version

1. **Week 4 hurt because every surface you watch lost at once**: the paper bankroll went 0-4 (-$162), Vault's Plays went 4-5, and the full prop board lost 69 units. **The props Vault actually grades A or B still finished ahead** (69-63, +3.6u at closing prices, +9.3u at opening prices). Most of the damage came from leans that were never bets (C/D/F: -51.5u), a staking rule that put 3x the money on the model's most extreme calls, and QB volume props.
2. **The honest season record for A/B props** is 323-293, **+15.4u at closing prices (+2.5%)** and +29.9u at opening prices (+5.6%). At the close that is well inside the noise; at the open it is a bit over one standard error. Without QB volume props: +26.8u at the close, +42.1u at the open (about two standard errors). A small edge is plausible, not proven.
3. **The model has real signal but is about 4x too confident.** Measured week by week against the market, Vault's opinion deserves about 22% weight. It has no edge at all on QB attempts, completions and passing yards, and it is clearly ahead on pass TDs.
4. **The biggest fixable problem is data, not math.** 83% of Week 4 props had no real sportsbook price when Vault graded them, only Underdog and Sleeper. With real books, taking the best price alone is worth +3 to 5% per bet, about the size of the model's whole edge.
5. **The game model went 22-19 (+3.5u) but that was luck**: of the 19 spread and total lines that moved before kickoff, 15 moved against Vault's side. Nothing public beats NFL closing lines. Stop making game picks from the model.

---

## Week 4: props

| Surface | Week 4 | Season |
|---|---|---|
| Vault Ledger ($1,000 paper bankroll) | 0-4, **-$162** | 11-12, -$0 on $865 staked (Weeks 1-3 were +$162) |
| Vault's Plays (locked card) | 4-5, 1 void, -1.5u | 20-14, +5.6u |
| Best Bets shown before kickoff | 10-7, +3.3u | 34-21, +12.6u |
| **A/B props** (point-in-time grades) | **69-63, +3.6u** close, +9.3u open | 323-293, +15.4u close, +29.9u open |
| A/B props, excluding QB volume | 66-58, +5.8u close, +11.5u open | 304-264, +26.8u close (+4.7%), +42.1u open (+8.7%) |
| C/D/F leans (Vault says don't bet these) | 230-250, **-51.5u** | 877-842, -101.5u |
| Every lean, graded or not (what the Vault Record headline counts) | 343-373, -69.4u | 1380-1330, -117u |

**Model vs market (scoreboard, at the close):** Week 4 skill -0.023, z -2.1. This was the first week Vault's probabilities were measurably worse than the no-vig market. Season -0.012 (z -2.0).

**Where Week 4 lost:**
- **QB props**, every lean: 94-118, -35u. Passing yards 10-19. A/B QB props 15-19.
- **The ledger's three big bets** were all volume unders the board rated 18 to 29% EV: Herbert under 29.5 pass attempts (31, lost $70), Javonte Williams under 15.5 rush attempts (19, lost $46), Jonathan Taylor under 90.5 rush yards (95, lost $23, plus the $23 parlay of Herbert and Taylor). Pass attempts is a market where the model shows no information beyond the market (finding 2), and A/B rush-attempt unders went 6-9 this week.
- **Vault's Plays**: the first six picks (posted Wednesday and Thursday morning) went 4-1 with a void. The four added Thursday evening through Sunday went 0-4 (Loveland, Pickens, Kittle, McMillan). All ten were receiving-yard unders.

**What worked (A/B):** pass TD overs 4-1 (+4.0u), receptions overs 6-3 (+3.6u), RB props 28-20 (+6.5u), WR props 18-13 (+4.3u).

## Week 4: game model

| | Week 4 | Season |
|---|---|---|
| All game leans | 22-19, +3.5u | 82-81, +1.2u |
| Spreads | 8-5 (2 pushes), +2.3u | 27-31, -6.5u |
| Totals | 6-9, -3.5u | 31-30, -1.8u |
| Moneylines | 8-5, +4.8u | 24-20, +9.4u |
| Game Plays (only "totals 1.5 to 3 points off" was switched on) | 1-1 by my reconstruction (TEN @ BAL over 43.5 lost at 42, DEN @ SF under 48 won at 38) | |

**Read it through closing-line value, not the record.** Of the lines that moved between Vault's first read and kickoff, spreads moved toward Vault twice and away 8 times; totals 2 toward, 7 away. The scoreboard's game skill for Week 4 was +0.002 (z 0.0): Vault's game probabilities carried no information the market didn't have. The moneyline profit is mostly underdogs hitting (NE +250, CAR +164, DAL +126, CLE +126), which is what a model that is flatter than the market will always lean toward.

---

## Deep dive: what is actually wrong

### 1. The season record had hindsight in it (measurement bug, now fixed)

`scripts/settle_bets.py` re-graded every past prop with **today's** `prop_model.json`. Since Sep 28 that file carries in-season corrections fitted on settled results (the real-line recalibration for receptions and receiving yards, `proj_adj`, the in-season overlays), so old weeks were being graded by a model that had seen their outcomes.

Grading each prop with the model version live when its line was first graded changes **448 of 2,007 Week 1-3 grades (22%)** and 42 in Week 4 (most Week 4 lines opened before Wednesday's refit). The hindsight version made Weeks 1-3 A/B look about 7u better at the close and 10u better at the open than they were, and Week 4 about 4.5u better.

**Fixed (this session):** `data/prop_model_versions.json` keeps every published model with the time it went live, and settlement grades each prop with the version live at its first sighting.

### 2. The model knows something, but it is about 4x too confident

Fitting each outcome to the no-vig market probability plus Vault's deviation from it, the best weight on Vault's deviation is:

| Market | Weight on Vault's opinion (0 = ignore it, 1 = trust it fully) |
|---|---|
| All props pooled | **0.22** at the open, 0.24 at the close |
| Pass TDs | 1.00 (Vault is clearly ahead of the market here: A/B 18-11, +8.5u) |
| Rush attempts | 0.08 to 0.32 |
| Receptions | 0.28 to 0.30 |
| Receiving yards | 0.20 to 0.24 |
| Rush yards | 0.14 to 0.20 |
| Pass attempts, completions, passing yards | **0.00** |

Translation: the EV the board prints is roughly 4x too big on most markets, and on QB volume it is noise. That is how Herbert's pass-attempts under showed +29% EV and got a 3-unit bet.

### 3. Claimed EV size is not a reliable guide for staking

Every prop side where the raw model beat its price's break-even by at least 5 points, whole season:

| Raw model edge | At the open (when a bet is placed) | At the close |
|---|---|---|
| 5 to 10 pts | 225-210, +7.5u (+1.7%) | 265-257, -0.1u (0%) |
| 10 to 20 pts | 172-143, +19.2u (+6.1%) | 188-162, +6.6u (+1.9%) |
| **20+ pts** | **46-49, +0.3u (+0.3%)** | 77-55, +23.9u (+18.1%) |

At the prices available when Vault first grades a line, the 20%+ bucket broke even; at the close it did well. That is too unstable to bet 3x on. The ledger rule adopted Sep 26 (3 units on 20%+ Vault EV, mid-range EV on unders only) was fitted on three weeks of results. The same data also contradicts its "unders only" half: high-conviction overs were +11.2% at the open on 262 bets, unders -0.4% on 583.

### 4. QB volume props are a leak

- Vault's projection lands closer to the actual result than the book line on only **about 1 in 3** passing-yards and completions props this season (34%), against 55 to 60% on pass TDs and receptions.
- A/B QB volume picks (before any cap): 24-31, -9.3u at the close, **losing in all four weeks**.
- The board already caps passing yards and completions at C ("thin edge"). **Pass attempts was not capped**, which is how Herbert's under reached the ledger as an A, and the settlement grade didn't apply the cap at all. Both fixed this session.
- Pass TDs are the opposite: the model's best market.

### 5. The odds data is the real bottleneck

In Week 4, **598 of 723 graded props (83%) had no real sportsbook price when Vault first graded them**, only Underdog and/or Sleeper. At the open, FanDuel quoted 30 of them, Pinnacle 21, Caesars 18, DraftKings 14. Even at the close, 536 (74%) were DFS-only. The cause is the ParlayAPI free tier (about 1,000 credits a month), which returns mostly pick'em apps. What it costs us:

- **The "market" Vault measures itself against is mostly a pick'em app's price**, not a sharp book. The scoreboard, the price-aware grades and CLV all inherit that.
- **No line shopping.** On props where 2+ books quoted, taking the best price instead of the median added **+3.3% (2+ books) to +4.6% (4+ books) in payout per bet**. That is worth about as much as the model's entire edge.
- **Pick'em pairs never fired.** The correlation pricer shipped for Week 4 has logged 0 pairs: it needs 2+ real books on both the QB's passing yards and his receiver's yards, which this feed almost never has.
- **Free fix available:** Pinnacle's guest API, which Vault already calls for game lines (`scripts/book_tape.py`, `scripts/fetch-sharp-money.mjs`), lists player props with prices. Tonight's NO @ ATL has 51 (receptions, receiving yards, rushing yards, passing yards, attempts, completions, TDs). They post close to kickoff with low limits ($250 to $1,000), so they work as a sharp anchor and closing reference, not an opening line.

### 6. Timing is real

- A/B props: +29.9u at the opening price vs +15.4u at the closing price. The market moves toward Vault's side after it first grades a line, so posting early captures most of the value.
- The card shows the same thing at small scale (early picks 4-1, late picks 0-4).
- Per-bucket timing data is too thin and noisy to pick an exact cutoff yet.

### 7. Rules keep getting fitted to noise

Fade-team-lean (reversed in Week 3), the 20%+ EV sizing (0-3 on its Week 4 bets), "where Vault differs most" game plays (3-9), and the card and Game Play rule engines that switch a bucket on after 15 plays at +5% are all rules found in slices of 15 to 150 bets. For scale, with a genuine +5% edge:

- 140 graded props a week still lose about **1 week in 4**.
- A 10-bet card loses about **half** its weeks.
- A 4-bet week goes 0-4 about 4% of the time even at 55% per bet.
- Proving a 4% edge at two standard errors takes about **2,000+ bets**.

Week 4 is one draw. Judge changes by closing-line value and log-loss against the market, over hundreds of bets.

Also from the scoreboard: when Vault disagrees with the market by 8+ points **against** recent usage news (snap or target jumps, a teammate out), it loses (skill -0.049, z -1.9 on 290 props). The projection doesn't see role changes the market has already priced.

---

## A better method: market first, model second

The research report from Sep 28 (`reports/NFL prediction model upgrade.md`) said this direction in principle. The Week 4 data says exactly where to apply it.

### Props

1. **Fair price = sharp consensus.** Power de-vig each book, weight sharp books (Pinnacle, FanDuel, DraftKings, Caesars, Circa) over the rest, and put pick'em apps near zero. Requires the data upgrade below.
2. **Vault probability = anchored blend.** `logit(p) = logit(fair) + w_market * (logit(model) - logit(fair))`, with `w_market` refit weekly, walk-forward, per market. This makes every EV on the board honest. Now running in shadow (see below).
3. **Bet the best available price** across every book for the same line, and only where the anchored EV is at least 2 to 3%.
4. **Flat stakes.** 1 unit per play. Never size up on claimed EV.
5. **QB volume = market only.** Show the fair line, never an A/B. Keep pass TDs as a flagship market.
6. **Post early.** Lock the card Tuesday and Wednesday when books open. Late additions need a higher bar.
7. **One scoring engine.** Today the board (index.html), Best Bets (`build_best_bets.mjs`) and settlement (`settle_bets.py`) each grade props their own way, which is how the settlement grade ended up ignoring the thin-edge cap. Compute probability, fair, EV, grade and gates once in the pipeline, store them with a timestamp, and have the board, the card and settlement read the stored numbers.

### Games

1. **Retire model-based Game Plays.** The model loses closing-line value and a 15-play rule engine can't tell luck from skill.
2. **Vault's game line stays the market fair line** (already shipped as `gmFair`).
3. **Game plays only from stale prices.** A US book (or Kalshi, Polymarket, Novig after fees) priced better than Pinnacle's no-vig at the same number. The Sharp Money tracker already computes these ("behind" alerts): 6 NFL alerts since Sep 29, average CLV +1.7%. Expect 0 to 5 a week on NFL main lines; that is the honest size of the opportunity.
4. **Keep the game model as context** and as the source of implied team totals for props.

### Process

1. **Pre-register every NFL rule** (metric, sample size, go/no-go) before it ships, the way the NBA tests already are.
2. **Freeze the card rules for 4 weeks** at a time.
3. **Make the headline record what Vault actually recommends** (A/B and the card), not every lean.
4. **Weekly KPI = CLV against a sharp close plus log-loss skill**, with W-L shown as context.

## Better data, ranked

| # | What | Cost | Why |
|---|---|---|---|
| 1 | Pinnacle player props from the guest API we already use | Free | Sharp anchor and closing reference on ~50 props per game |
| 2 | A real prop odds feed: The Odds API (DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Fanatics, Bovada and others, plus pick'em apps) | $30/mo (20K credits) to $59/mo (100K). Props bill per game x market x region, so verify the count against our cadence before buying. | Line shopping (+3 to 5% per bet), a true consensus, and pick'em pairs that can actually fire |
| 2b | Alternative: SportsGameOdds | $99/mo Rookie (FanDuel, DraftKings, Caesars props); Pinnacle and Circa need the $299 Pro tier | More books, higher cost |
| 3 | Opening-window capture: poll Monday night and Tuesday when books post props, then injury-report afternoons and the Sunday inactives window | Free (cron) | Most of the edge is at the open |
| 4 | Snap counts (nflverse, updated in season) as the role signal instead of Sleeper's depth-chart order | Free | Removes the "against the news" losing disagreements |
| 5 | Route participation (PFF, FantasyPoints Data) | Paid | Free FTN participation data only arrives after the season, so in-season routes need a paid source. Later, only if #4 proves out. |

## What changed this session (free fixes)

1. **Point-in-time grades.** `data/prop_model_versions.json` (rebuilt from git by `scripts/backfill_prop_model_versions.py`, appended by every refit) lets settlement grade each prop with the model live when its line was first graded (`model_from` on every row). The model scoreboard and the Win % check read the same version.
2. **QB volume market-only.** Pass attempts joins passing yards and completions in the thin-edge cap (grade held at C) on the board, in Best Bets and in settlement. Settlement applies each market's cap from the day it joined the list and keeps the uncapped letter in `grade_raw`.
3. **Ledger staking.** The keeper task now stakes a flat 1u (2% of the roll): A/B with Vault +EV of 10%+, real books only, no QB volume, no parlays, no EV-based size-ups, at most 8 bets a week, posted early. The Ledger page's "How this bankroll is run" panel says the same.
4. **Vault Record headline.** Defaults to Vault's A and B grades, with "Every lean" one tap away, and units are now scored at each pick's closing price ("need 52% to profit") instead of a flat 55% pick'em bar.
5. **Pinnacle player props** join the prop feed as a direct source (fetch-pickem-props.mjs), refreshing the mirrored Pinnacle quotes and adding the ones the feed didn't have.
6. **Anchored shadow.** Settlement fits the per-market weights each week on earlier weeks only, grades every priceable prop the anchored way next to the live grade (`grade_anchor`), writes `data/prop_anchor_weights.json`, and the model scoreboard compares the two. First read on Weeks 2-4 (1,565 props, out of sample): log-loss at the open, market 0.6870, live model 0.6970, anchored 0.6862. Decide on switching after two more settled weeks.

**Still your call:** a paid prop odds feed ($30 to $59 a month). Everything in the props plan works better with it, and line shopping alone should cover the cost many times over at any real stake size.

---
Sources for the data options: [The Odds API plans](https://the-odds-api.com/), [SportsGameOdds pricing](https://sportsgameodds.com/pricing), [nflreadr release notes (FTN participation is post-season)](https://cloud.r-project.org/web/packages/nflreadr/news/news.html), [ETR on the NFL prop market](https://establishtherun.com/understanding-the-current-ecosystem-of-nfl-player-props/).

_Analysis scripts are in the session scratchpad. Settled numbers recompute from `data/bet_results.json` once the point-in-time settlement runs._
