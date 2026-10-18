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

## What needs to change

1. Nothing in the projection goes live on this evidence. Every candidate above either does not clear noise or buys accuracy at the cost of picks, and the earlier blend, K, home field and turnover studies say the same. A change with no backtest does not ship.
2. The scoreboard now shows what this retro needed and could not see: week by week records, the closing line next to the opening line, our official picks next to JP+'s selection engine, and JP+'s own reported record. This ships in this PR.
3. The model's real exposure is width. The honest next test is a pick rule that is invariant to how wide the model is (rank or z-score of the edge instead of 5 raw points), tested the same way. It was not run here because it needs a pre-registered design and the first rule would be tuned on the picks it is judged on.
4. We cannot backtest JP+'s method on history: their pre-kickoff numbers only exist from the day our job started recording them (57 games, 52 in week 7). Four more weeks of recorded numbers is the earliest a fair head-to-head with a real sample is possible, so keep the job running.
5. Watch, do not act: model picks on the favorite (n about 50 across all samples).
