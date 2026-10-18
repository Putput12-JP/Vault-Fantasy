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
2. **The real problem is a 1.2 point accuracy gap to the market in weeks 4-7 that has not moved since 2024 and is not in the preseason prior, the ridge shape, K, the dispersion, or the success-rate and explosiveness ratings.** JP+ is at market accuracy with the same public data, so something JP+ uses that we do not (the likely candidates are position-level preseason inputs such as quarterback, injuries and transfers, and in-season roster news) is worth about one point of margin. We have no data on those in the build environment, so this is where to look.
3. **The single most promising next experiment is a market-implied prior.** Fit team ratings from the closing lines of games already played (ridge on the spreads, same home field), use them as the center of the in-season ridge in place of the regression prior, and test whether the EPA evidence on top of it carries weight (the anchored test above says the model adds about nothing to the market on average, so this is a test of whether a market prior makes the model's own disagreements more reliable).
4. **Measurement stays as shipped in this PR** (week by week, closing line, official picks, JP+ reported record). JP+ numbers recorded before kickoff now cover week 7 only (52 of 59 games), so a fair JP+ head-to-head needs four to six more weeks of the recording job.
5. **Watch, do not act:** picks where the model is on the favorite (21-31 vs the close, 16-20 vs the open on 2022-25, 5-6 live, n about 50); 2026 picks being prior-led (69 of 80, 35-34).
