# CFB week 7 retro (2026-10-18): the model was flat, JP+ had a strong week, and no change is proven yet

Scripts: `scripts/cfb_week7_base_rows.py`, `cfb_week7_fetch_opens.py`, `cfb_week7_study.py`, `cfb_week7_sr_study.py`. Live numbers: `data/cfb_scoreboard.json`. Everything is weeks 4+, FBS vs FBS, graded against ESPN's recorded open unless it says close.

## Scorecard

Week 7, 54 finished games on our board (52 of them have a JP+ number we recorded before kickoff):

| | all games vs open | 5+ from the open | avg miss |
|---|---|---|---|
| Our model | 25-25-3 (50.0%) | 7-11-1 (38.9%) | 12.32 |
| Previous model (v1 shadow) | 29-22-3 (56.9%) | 5-10-1 | 12.15 |
| JP+ (our grading) | 31-20-3 (60.8%) | 9-5-1 (64.3%) | 11.27 |
| Opening line | | | 11.83 |
| Closing line | | | 11.29 |
| Our official picks (log) | 6-10-2 (37.5%) | | |

JP+ reported for week 7: 32-27 (54.2%), 5+ 13-6 (68.4%), selection engine 17-8 (68.0%). Season: 230-158, 93-62, 62-37, average miss 11.91 against open 11.53 and close 11.29 on 384 games. Their numbers are graded to their own opening spread and cover more games than our 54, so they do not match ours game for game, but the direction agrees: JP+ won the week and we did not.

Season on our board (212 games, weeks 4-7): ours 119-87-5 (57.8%), 5+ 48-43-2 (52.7%), miss 13.07. JP+ 132-75-5 (63.8%), 5+ 43-23-3 (65.2%), miss 12.12. Open 12.42, close 11.88. Official picks 40-42-4. Weeks 4-6 of our record were restated with the current model, so only week 7 is a clean forward week.

Graded against the CLOSE instead, week 7: ours 23-27-2 (5+ 5-7-1), JP+ 28-24-2 (5+ 9-5-0). Everyone does worse against the close than the open, which is the point of the close: Oregon opened -21.5 and closed -6.5, Tennessee opened -1.5 and closed -7.5. Both models were credited with Oregon/Nebraska against the stale open.

## Did we succeed?

No. 7-11-1 on 5+ (z -1.15) and 6-10-2 official is a bad week, but it is one week and inside noise. It was not a bad month: weeks 5 and 6 were 14-8 and 14-7 on 5+, week 4 was 13-17.

Where the wins came from: fading favorites the model thought were overpriced. Temple (opened -23.5, we had them by 9.3, they lost to Charlotte), New Mexico (opened -15.5 over Hawaii, we had 4.7), Louisville (opened -10.5 at Syracuse, we had 3.7), and Oregon (opened -21.5, a stale number, see below), plus Middle Tennessee and UAB where the model liked the home side.

Where the losses came from: 13 of our 19 picks were ones JP+ did not make, and those went 5-7-1. JP+'s 9 picks we did not make went 6-2-1. The 6 games we both picked: 5 were on the same side, and on those 6 we went 2-4 and JP+ 3-3 (we were on opposite sides at USF). So the whole gap is the games where the two models disagreed on whether there was an edge at all. The misses were mostly us fading a favorite who then won big: USF (we had 12.7, JP+ 28.1, final 27), Army over FAU (32), Texas State over Colorado State (39), JMU over Georgia State (27), Ohio over Sac State (41).

## Why JP+ is ahead this season

- Our projections are too narrow. Standard deviation of the projected margin is 8.2 for ours against 10.2 for JP+ and 12.1 for the open. Over weeks 4-7 the final margin moves 1.45 points per point of our projection (JP+ 1.24, open 1.02). The v1 shadow was 10.9 wide with slope 1.07, so the v2 prior plus special teams promotion (PR #48) took width out of the model.
- Our disagreement with the market carries little information. Regressing the final margin minus the open on each method's edge, the weight is 0.24 for ours and 0.57 for JP+ (212 games). Jointly the weight on ours falls to about zero once JP+ is in the regression, so JP+ contains what we have and more.
- JP+ sits closer to the market and still wins; our 5+ edges are larger than JP+'s and worse.

## What we tested, on 2022-25 walk-forward, nothing tuned on pick record

Filters, fixed in advance from the week 7 slate (`cfb_week7_study.py`; test = 2024-25, read once). Records are 5+ from the close (the base row also shows the open after the comma):

| rule | tune 22-23 | TEST 24-25 | 2026 live (vs open) | verdict |
|---|---|---|---|---|
| base (live) | 247-224, 49-44 | 197-160, 205-157 | 48-43 | |
| cap at 10 points | 175-163 | 169-124 | 34-35 | -0.6 points on tune, +2.5 on test, inside noise |
| cap at 8 points | 127-115 | 123-92 | 25-24 | noise |
| 10+ only | 72-61 | 28-36 | 14-8 | not stable |
| exclude lines of 21+ | 186-166 | 145-115 | 38-37 | no gain |
| both teams Power 4 | 85-78 | 51-37 | not run | no gain on tune |
| weeks 6+ only | 176-174 | 154-117 | 21-18 | tune 50.3%, test 56.8%, no |
| old and new model averaged | 198-168 | 138-137 | not run | worse on test |
| pick is the favorite (model more bullish on the favorite) | 8-13 | 13-18 | 5-6 | watch only: 21-31 vs close, 16-20 vs open, 5-6 live, n about 50 |

Nothing clears two standard errors against the base rule on both the tuning and the test seasons. Differences of 2 to 4 points on 300 to 400 picks are inside the noise.

A real model change: JP+ rates on success rate and explosiveness, ours on EPA per play. `cfb_week7_sr_study.py` builds both ratings (success rate; EPA on successful plays) through the same weekly ridge, fits three coefficients on 2022-23 only, and reads 2024-25 once:

| | miss, tune | miss, test | 5+ vs close, test | 5+ vs open, test |
|---|---|---|---|---|
| current | 12.811 | 12.454 | 197-160 (55.2%) | 205-157 (56.6%) |
| + success rate + explosiveness | 12.391 | 12.331 | 140-132 (51.5%) | 134-119 (53.0%) |

Accuracy improves (0.12 on the untouched seasons, past the 0.05 bar) and the picks get worse, the same shape as the K 90 retune, team home field and turnover luck tests: anything that moves the model toward what the market already prices lowers the miss and shrinks the edge that made the picks. NO-GO for the pick rule. Success rate alone and explosiveness alone are both worse than the current model on their own (miss 12.87 and 15.45 on test).

## Second round: finding the cause and testing real fixes

The 2022-25 base rows now also replay the 2026 season to date week by week (`cfb_week7_base_rows.py`; the replay matches the live board, correlation 0.999, mean difference 0.11 points, and finds the same 59 week 7 games JP+ counts), so every candidate below has three reads: tune 2022-23, test 2024-25 read once, and 2026 weeks 4-7 as an extra out-of-sample season. Bar (from `cfb-retune.md`): average miss better by 0.05 and picks not worse on test and 2026. Picks are compared at the live rule's count (the largest |edge|) so a candidate cannot win by simply taking fewer picks.

### Where the gap is
- **It is an accuracy gap, and it is not new.** Weeks 4-7 miss minus the closing-line miss: 2022 +0.62, 2023 +0.64, 2024 +1.14, 2025 +1.25, 2026 +1.18. So 2026 is the model's usual self, not a collapse.
- **JP+ is at market accuracy and we are not.** 2026, 212 games: ours minus close +1.19 points (paired t 3.4), JP+ minus close +0.24 (t 0.85), ours minus JP+ +0.95 (t 3.1, p 0.002).
- **The pick-record gap is much weaker than the accuracy gap.** Games where exactly one of us picked the right side of the open: JP+ 38, ours 25 (p 0.13). Week 7's 7-11 against 9-5 is mostly the picks each model chose to make.
- **Our picks are prior-led.** Split each margin into the preseason prior and the in-season move (live minus prior-only). Of our 80 2026 picks of 5+ points, the average prior sat 10.6 points from the line while the in-season move pointed 2.1 the other way; 69 were led by the prior and went 35-34, the 11 led by the in-season move went 4-7. In 2026 the final margin follows the in-season move (weight +0.28) and not the prior (weight -0.02), but on 2022-25 prior-led and in-season-led picks are about equally good, so this is a 2026 read at n=80, not a rule.
- **The in-season update is too timid and the model is too narrow, but fixing either does not make better picks.** Final minus live regressed on the in-season move: +0.27 (2022-23), +0.38 (2024-25), +0.58 (2026).
- 2026 is a mild chalk year: favorites of 10+ cover 50.6% against 43-50% in 2022-25, slope of (final minus close) on the line +0.12, about 2 standard errors above 2022. A wider model like JP+ gets some credit for that, so part of JP+'s week 7 may be regime.

### Candidates tested (all pre-registered; chosen on 2022-23 by average miss only)

| candidate | miss tune | miss test | miss 2026 | 5+ vs close at matched count: tune / TEST / 2026 | verdict |
|---|---|---|---|---|---|
| live (v2 + special teams, K 70) | 12.811 | 12.454 | 12.822 | 247-224 (52.4%) / 197-160 (55.2%) / 41-39 (51.2%) | |
| + last season's SP+, FPI, Elo in the prior | 12.690 | 12.249 | 12.548 | 257-212 (54.8%) / 186-170 (52.2%) / 39-43 (47.6%) | accuracy up, test and 2026 picks worse |
| in-season move x1.2 and prior x1.2 (= K 84) | 12.733 | 12.316 | 12.593 | 256-215 (54.4%) / 189-165 (53.4%) / 41-39 (51.2%) | accuracy up, test picks worse |
| K 90 / K 110 at matched count | | | | K 90 250-221 / 181-174 (51.0%) / 43-38; K 110 238-229 / 189-167 / 43-38 | not consistent |
| z-scored edge rule | | | | 243-226 / 194-164 (54.2%) / 40-40 | no gain |
| v1 and v2+ST both 3+ and averaging 5+ | | | | 185-155 (n 349) / 117-115 (50.4%) / 25-24 | worse on test |
| offense ridge strength x0.5 (offense reacts faster) | 12.752 | 12.333 | 12.574 | 249-220 (53.1%) / 187-167 (52.8%) / 44-36 (55.0%) | accuracy up, test picks worse |
| defense ridge strength x2 or x4 | 12.867-13.009 | 12.651-12.932 | 12.821-12.871 | | worse on every read |
| winsorise team-game EPA at 2.5 and 97.5 percent | 12.845 | 12.519 | 12.837 | 251-220 / 194-163 / 41-39 | no change |
| shrink toward the prior (b fitted -0.275, i.e. extrapolate the move) | 12.794 | 12.318 | 12.600 | 235-209 (not matched) / 174-146 / 39-34 | accuracy up, test picks lower |
| market-anchored number (close + 0.2 x prior gap + 0.25 x move) | 12.111 | 11.868 | 11.650 | 250-222 / 191-164 (53.8%) / 41-39 | equals the close by construction, no pick gain |

Every candidate that improves accuracy past the 0.05 bar (SP+/FPI/Elo prior, wider K, faster offense, move scaling) moves the model toward the market and lowers the 2024-25 pick rate by 1 to 3 points. That is the same pattern as the K 90 retune, team home field, turnover luck and success-rate tests, now seen from five more directions. Net: several changes raise accuracy by 0.15 to 0.25 points, none closes the 1.2 point gap to the market, and none improves picks.

## What needs to change

1. **No projection or pick change ships on this evidence.** Everything above fails the bar on test or on 2026, or just reproduces the market. Shipping an accuracy-only change would fail the project's own rule that picks must not get worse.
2. **The accuracy gap to the market is 1.2 points in weeks 4-7 and has not moved since 2024.** It is not in the preseason prior, the ridge shape, K, the dispersion, or the success-rate and explosiveness ratings. An earlier draft of this note guessed that JP+ closes it with quarterback and injury information. The reverse engineering below rules that out: JP+'s published production data says its injury authority is switched off. Whatever JP+ does better on accuracy is not roster news.
3. **The single most promising next experiment is a market-implied prior.** Fit team ratings from the closing lines of games already played (ridge on the spreads, same home field), use them as the center of the in-season ridge in place of the regression prior, and test whether the EPA evidence on top of it carries weight (the anchored test above says the model adds about nothing to the market on average, so this is a test of whether a market prior makes the model's own disagreements more reliable).
4. **Measurement stays as shipped in this PR** (week by week, closing line, official picks, JP+ reported record). JP+ numbers recorded before kickoff now cover week 7 only (52 of 59 games), so a fair JP+ head-to-head needs four to six more weeks of the recording job.
5. **Watch, do not act:** picks where the model is on the favorite (21-31 vs the close, 16-20 vs the open on 2022-25, 5-6 live, n about 50); 2026 picks being prior-led (69 of 80, 35-34).

## Reverse engineering JP+'s picks page (REA, 2026-10-18)

REA's `capture_browser_scenario` loaded https://www.jpplusratings.com/picks/spreads/ in a controlled headless Chrome and kept every network response. The page is a Next.js app; it embeds its production pick records in the page data and pulls three public JSON files from a GitHub gist (`pick_records_2026.json`, `price_aware_clv_public_2026.json`, `spread_execution_runtime_2026_w8.json`). JP+'s model code is not shipped to the browser, so this recovers how picks are selected, sized, entered and graded, not how the margin is computed. The 99 settled selections rebuilt from the feeds are 62-37, identical to the number JP+ posts, so the data is complete.

**What it shows**
- **JP+ is not using a 5-point cutoff for the bets.** Its production selections are chosen on expected value at the best available price across books, after filters and vetoes. In weeks 6 to 8 the smallest edge among selections is 2.9 to 3.5 points, and every selection carries an `ev`, a `good_to_line` (the worst number still worth taking) and a `recommended_book`. The "5+ disagreements" record (93-62) is a separate, wider population from the selection engine (62-37).
- **Entry is the opening quote, shopped across books.** All 107 production selections have `production_reason: opening_quote_eligible`; they are added the moment lines post and frozen (the first week 1 picks were added on 2026-07-20). Books: FanDuel 61, DraftKings 23, Fanatics 11, BetMGM 10, Caesars 2. On the 99 selections with an ESPN open, JP+'s entry beats ESPN's DraftKings open by 0.56 points on average (better on 52%, same on 27%, worse on 21%), and the market then moves a further 0.90 points toward the pick on average by the ESPN close.
- **87% of selections are underdogs** (median entry +9.5), and the volume is bursty: 9, 5, 4, 26, 4, 26, 25, 8 picks in weeks 1 to 8.
- **Stakes come from flags, and the flags are success-rate based.** Stake is 0.5 in weeks 1 to 3 (preseason caution), 1.0 normally and 2.5 when a conviction flag fires: `AWAY_CONVICTION` (26 of the 2.5 stakes) or `DEF_SR_DOMINANT` (defensive success rate, 9). Settled, 2.5-unit picks are 23-10, 1-unit 29-19, 0.5-unit 10-8. The flags appear to be what separates the strong picks, which is a lead and not a proven edge at 33 picks.
- **Win rate does not rise with edge size** in their own selections: under 4 points 6-1, 4-5 6-7, 5-6 13-5, 6-8 15-15, 8+ 22-9.
- **Injuries are not used.** Every selection has `current_injury_integrity_state: null`, and the execution file says "Production injury authority is disabled by tracked repository policy." Chalk-trap and rivalry-week vetoes exist as fields and none of the 107 selections is vetoed, so vetoed games are removed upstream.
- **Grading differs from ours.** Their model record (230-158) and 5+ record are graded against a "canonical opening spread" and the selection record against the entry line; our scoreboard grades against ESPN's recorded open.

**What it changes in this retro**
- **Closing-line value is level.** JP+'s selections beat the close by 1.53 points on average (70% beat it, 17% tie; 99 picks). Our 5+ picks entered at the ESPN open beat the close by 1.43 points (66.7% beat it; 96 picks). On the measure that is least affected by luck, the two models are doing the same thing. The record gap (62-37 against 40-42-4) is therefore mostly outcome noise plus the 0.56 points JP+ gains by shopping the opening quote, plus their smaller, EV-filtered pick set.
- **Our all-games lean record is also close.** On weeks 4 to 7, JP+ is 140-91 (60.6%) on the full slate against the canonical open and ours is 119-87 (57.8%) against ESPN's open, a 2.8 point gap on about 230 games, inside the noise. The gap that is hard to explain by luck is the 5+ pick records, 55-32 for JP+ against 48-43 for ours on weeks 4 to 7, and the accuracy gap to the market.
- **Success rate is where JP+ puts its conviction.** The earlier success-rate and explosiveness test failed the pick bar, but it used success rate as a rating input to the margin. JP+ uses it as a flag on picks and for sizing. That is a different test (does a team's defensive success rate predict which edges cover) and it has not been run; the only evidence so far is JP+'s 6-3 on `DEF_SR_DOMINANT` and 18-8 on `AWAY_CONVICTION`.

**What was tried on our data**
- **Home or away side of the pick:** 5+ picks on the home team go 246-204 (54.7%) against the close and on the away team 239-219 (52.2%) over 2022-26; against the open 54.1% and 56.5%. No consistent side effect, so JP+'s away flag is not a simple away rule.

**What to do next**
1. Grade our picks at the best price across books at the open, the way JP+ grades its selections, so the two records are comparable. The line shopping is worth about half a point.
2. Pre-register and backtest a defensive-success-rate pick flag on 2022-25 (top-decile defensive success rate on the picked side), judged on the same tune, test and 2026 split. This is the only lead the reverse engineering produced that we can test.
3. Replace the raw 5-point rule with an EV rule at the opening price once the best-price grading in step 1 exists, then backtest it against the 5-point rule at matched pick counts.
4. Keep the JP+ recording job running; four to six more weeks gives a fair head-to-head.

## Round 4: JP+'s week 7 picks game by game, a defensive success rate flag, and the chalk-trap analog

**Week 7 side by side** (JP+'s 25 production selections from the picks page, 17-8, against our board at the ESPN open):
- On the 8 games where we also had a 5+ point pick, we agreed on the side in 6 and were on opposite sides in 2 (South Florida and Navy at UTSA, both won by JP+'s side). On the 6 shared sides we were 3-3 and so was JP+. On the 2 opposite games JP+ went 2-0 and we went 0-2.
- On 15 more games JP+ made a pick and we had no 5+ point edge, and JP+ went 12-3 there. That is where the week was won: Texas Tech over Arizona State (JP+ edge 11.7, ours 0.7 the other way), Air Force over UNLV (11.4, ours 3.6 on the other side), Oregon State, Auburn, Florida State, Ball State, North Carolina. Two more JP+ picks (UTEP, UMass) are not on our board and both lost.
- So the week-7 record gap is the accuracy gap again: JP+ was right in games where our projection sat close to the line, not in games where we both disagreed with the market.

**Defensive success rate flag (JP+'s `DEF_SR_DOMINANT`).** JP+ does not publish the definition, so this tested a guess fixed in advance: the side our model picks has a top-10% (or top-20%) defensive success rate in FBS that week, from the same weekly opponent-adjusted ridge. `scripts/cfb_week7_defsr_study.py`, 5+ point picks, weeks 4+:

| | flagged vs close | unflagged vs close | flagged vs open |
|---|---|---|---|
| top 10%, 2022-26 | 17-16 (51.5%, n=33) | 468-407 (53.5%) | 12-6 (n=19) |
| top 20%, 2022-26 | 35-36 (49.3%, n=71) | 450-387 (53.8%) | 24-14 (n=39) |
| top 20%, TEST 2024-25 | 14-13 | 183-147 | 16-9 |

No edge against the close, where the sample is large enough to read. The open numbers look better but the 2022-23 opens are mostly missing, the samples are 19 and 39, and the flag we built may not be JP+'s. NO-GO as defined; JP+'s 6-3 stays a lead.

**The chalk-trap analog.** JP+'s picks carry a `chalk_trap_vetoed` field (none of the 107 selections is vetoed, so vetoed games are removed upstream), and its selections on favorites are 11-2 against 51-35 on underdogs, so the veto is selective about which favorite picks survive. Our version is the simplest one: drop a 5+ point pick when the pick is the favorite. This is the watch item from round 1, now with 2026 added and a design reason behind it. `5+` picks on the favorite, weeks 4+:

| | picks on the favorite | rule: drop them | base |
|---|---|---|---|
| vs close, tune 22-23 | 8-13 (38.1%) | 239-211 (53.1%) | 247-224 (52.4%) |
| vs close, TEST 24-25 | 13-18 (41.9%) | 184-142 (56.4%) | 197-160 (55.2%) |
| vs close, 2026 | 0-3 | 41-36 (53.2%) | 41-39 (51.2%) |
| vs close, all 22-26 | 21-34 (38.2%, n=55) | 464-389 (54.4%) | 485-423 (53.4%) |
| vs open, TEST 24-25 | 14-14 (50.0%) | 191-143 (57.2%) | 205-157 (56.6%) |
| vs open, 2026 | 6-6 | 44-38 (53.7%) | 50-44 (53.2%) |

By season against the close the favorite picks were 3-1, 5-12, 5-5, 8-13 and 0-3. Over 2022-26 they cover 38.2% against the close (binomial p 0.04 against break-even, Fisher p 0.025 against the underdog picks, n=55). The hit rate improves on tune, test and 2026 against the close and the pick count falls by 6%. It is not strong evidence: it was one of about a dozen pre-registered variants, so the p value does not survive a correction for that, and against the open the favorite picks are 22-26 (p 0.39). The rule changes which games are official picks, so shipping it must restate the pick log and the records (project rule) and touch every place `is_pick` is set in `cfb_model.py`. Not shipped in this PR; it needs a decision.

