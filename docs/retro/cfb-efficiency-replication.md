# College football: can a market-blind efficiency model beat the line? (JP+ replication)

_Run 2026-10-10. Script: `scripts/cfb_efficiency_study.py` (reproduces every number in section 1). Grader for section 2: `scripts/grade_jpplus_picks.py`._

JP+ (jpplusratings.com) publishes college football spread picks and reports **61.6% ATS** on a blind holdout and a live 2026 record of 42-26. It describes its method: opponent-adjusted play-by-play efficiency (ridge regression on success rate and explosiveness), preseason priors with mean reversion, special teams, and picks only where it differs from the line by 5+ points. The goal here was to rebuild that kind of model for Sharp Money and see whether the results hold up.

## 1. Rebuilding the method: no edge

**Data:** ESPN play-by-play with EPA (sportsdataverse-data releases), 2021-2025, plus the ESPN spread for every game. **Model:** per-team offense and defense EPA per play (garbage time dropped, EPA capped at ±3), ridge-adjusted for opponent and home field, refit each week using only earlier games; prior = last season's ratings x 0.85; predicted margin = 70 x rating gap + 2.5 home field. Hyperparameters were tuned on 2022-2023 only. 2024-2025 was the untouched test.

| | Model misses by | Market misses by | 5+ pt disagreements, ATS (break-even 52.4%) |
|---|---|---|---|
| 2022-23 tuning, all weeks | 13.1 | 12.0 | 257-281 (47.8%) |
| 2022-23 tuning, weeks 4+ | 12.6 | 12.1 | 185-179 (50.8%) |
| **2024-25 test, all weeks** | 13.0 | 12.0 | 241-265 (47.6%) |
| **2024-25 test, weeks 4+** | 12.5 | 11.9 | 164-181 (47.5%) |

Season by season (weeks 4+, 5+ pt edges): 2022 101-90, 2023 84-89, 2024 85-88, 2025 79-93.

- The model's error (12.5-13) is close to JP+'s own published 12.77, so it is a faithful rebuild of that kind of rating.
- Its picks do not cover. In weeks 4+ it explains a sliver of the gap between the market and results (regression of margin-minus-line on model-minus-line: slope 0.08-0.13, t about 1-1.8), worth well under half a point on a 5-point disagreement.
- Things tried on 2022-23 that did not help: success rate and explosiveness ratings, a points-scored rating (made it worse), per-week-bucket stage-2 weights, a market blend (no gain over the market alone).
- **Caveats:** ESPN's spread is a closing line, harder to beat than the opening lines JP+ grades against. As of this run we did not have recruiting, transfer-portal or returning-production priors (they matter most in weeks 1-3); the v2 prior below adds them. We do not have JP+'s sigma filter, its three vetoes, or its flags (none are published). The historical opening lines are not in these files.

## 2. Grading JP+'s live 2026 picks independently: the record and the closing-line value are real

74 picks were copied from their CLV page into `data/jpplus_picks.json`. `scripts/grade_jpplus_picks.py` regrades them from ESPN final scores and ESPN's closing spread (68 are final).

- **Record:** 42-26, identical to JP+'s page. 0 of 68 results differ.
- **Closing line:** ESPN's close is within 0.28 pts of the close JP+ lists.
- **Closing-line value (entry minus close):** +1.54 pts on average over 72 picks; 69% beat the close, 14% did not. Underdogs are about 9 in 10 picks.
- **Record vs luck:** 42-26 is 62%, 1.55 standard errors above break-even. The record alone is not conclusive over 68 picks; the closing-line value is (about 6-7 standard errors).
- **One week carries it:** weeks 1-5 are 27-21; week 6 is 15-5.

## 3. Their 2022-2025 log (660 picks, copied from the CLV page)

405-249-6 (61.9%) in my transcription (page: 407-249-6). By season 55.9%, 60.5%, 70.1%, 60.5%. Average closing-line value was only +0.17, +0.34, +0.64, +0.67 pts a pick, with 18-42% of picks in some seasons having a close equal to the open (2023: 42%, concentrated in weeks 11-13: 37 of 51), which looks like missing closes filled with the open. Underdogs and favorites win about equally, and the win rate does not rise with the size of the edge (60%, 65%, 62%, 57%, 65% across the five edge bands). Their reported +133.1u over the log implies about -106 pricing; at -110 it is about +119u.

## Conclusions

1. A straightforward market-blind efficiency model built from public data does **not** beat the closing line. It reaches market-level accuracy only late in the season and not at all in the first month.
2. JP+'s 2026 picks do beat the closing line by about 1.5 pts, which is more than its history (about 0.5). Whatever it does beyond the published method (priors, filters, vetoes, timing of the entry line), it is not reproduced by the method alone.
3. The edge, if it exists, is in the **opening number**. Those lines are small-limit and move quickly toward the picks, and the picks are mostly underdogs in small games, where followers can move the line themselves.
4. So Sharp Money does not publish its own college spread picks. It tracks JP+'s picks against real scores and closes (the "JP+ spread picks (outside model)" card) and judges them by the same bar as every other signal: 50+ picks and 2 standard errors above the break-even price before it says Trust it.

## What would change this

- Preseason priors from CollegeFootballData (team talent composite, returning production, transfer portal, SP+ as a benchmark) to fix weeks 1-3. (Done: see "v2 step 2" and "Promotion" below. Miss unchanged, 12.50 vs 12.52.)
- Opening-line history, to grade against the number JP+ uses rather than the close.
- JP+'s shadow record for vetoed games and a calibration table for its cover probabilities.

## Second round (2026-10-11): everything reasonable we could add from the same data

Passing and rushing efficiency separately, success rate, explosiveness, pace, a two-season prior, recency weighting, and week-bucketed stage-2 weights: 16 combinations, each tuned on 2022-23 and then read once on 2024-25 (weeks 4+).

- Slope of (margin minus line) on (model minus line): 0.01 to 0.10, never above t = 1.3.
- 5+ point disagreements on the untouched 2024-25 test: 47.4% to 50.1% ATS in every variant (break-even 52.4%).
- Best 2022-23 variants (52-54% at 5+ and 7+ points) fell back to 47-51% on 2024-25: the usual sign of fitting noise.

No variant is shipped. Stopped here on purpose: more variants would be fishing. What is still missing is the information the market has before kickoff that play-by-play does not carry: preseason talent and returning production, transfer movement, and opening-line history. Those come from CollegeFootballData (its API host was blocked in the build environment on 2026-10-11; the talent, returning-production and portal inputs were added later that day, see "v2 step 2").

## Where it lives in the app

The method is shown, unflattered, on the Sharp Money **CFB Model** tab: power ratings, the projected slate against the market line, the backtest by season, and a pick log (`data/cfb_model.json`, refreshed by `.github/workflows/update-cfb-model.yml` from `scripts/cfb_model.py`). Every pick 5+ points from the market in week 4 or later is logged once, before kickoff, and graded against real scores and ESPN's close. The tab is labeled Ignore it until it clears 50 graded picks and 2 standard errors above break-even, the same bar as every other signal. The frozen preseason ratings (`data/cfb_model_priors.json`) are rebuilt once a year with `python3 scripts/cfb_model.py priors`, and `FBS_ADDITIONS` in the script is updated for teams that move up.

## v2 step 1: blending with the market (2026-10-11)

Regressing the final margin on the ESPN closing spread and on (model - spread), weeks 4+, 2022-2025: the model's disagreement
gets a weight of 0.07 on the tuning seasons (2022-23) and 0.13 on the test seasons (2024-25). Using w = 0.10 the blended line's
mean miss was 11.89 vs the market's 11.88 on 2024-25 (12.10 vs 12.11 on 2022-23): no measurable gain. So the blended line is
the market, and the model alone is not an edge. The page shows the blended line anyway so nobody mistakes the model line for
a price, and adds a pre-game "market check" from Sharp Money (line move toward our side, money share above ticket share,
sharp-account flow). That check has no history, so it is tracked forward only and read after the sample builds. Games already
in progress get no check, because their lines and money are live.

## v2 step 2: a regression-built preseason prior (2026-10-11)

`scripts/cfb_v2_prior_study.py`. Inputs, all known before kickoff of the season they predict, from CollegeFootballData
(`data/cfbd/`, pulled by the Fetch CFBD data workflow): 247 team talent, returning production (% of PPA, % of passing PPA),
four classes of recruiting points, net transfer-portal movement (stars in minus stars out), plus last season's final offense
and defense ratings. A ridge regression predicts each team's end-of-season offense and defense rating from them; each
season's prior is fit only on EARLIER seasons (2022 opens flat). Everything else is v1. Feature set fixed before the run;
2024-2025 read once.

| 5+ pt disagreements, weeks 4+ | v1 (last season x 0.85) | v2 (regression prior) |
|---|---|---|
| 2023 (tune, one season to learn from) | 84-89 | 108-108 |
| 2024 | 85-88 | 92-81 |
| 2025 | 79-93 | 97-89 |
| Test 2024-25 | 164-181 (47.5%) | 189-170 (52.6%) |

Reading it honestly: 52.6% is 0.2 points above the 52.4% break-even, and 189 wins is about 1 win above what break-even
predicts on 359 picks (a tenth of a standard error). The model's average miss did not move (12.50 vs 12.52 points, market 11.88),
and the weight the model's disagreement gets when predicting the final margin FELL from 0.13 to 0.07. The prior is better
than v1's on the pick count and no better where it matters, the miss. It is not an edge, so nothing ships as a pick, and the
CFB Model page keeps its Ignore it label and its v1 ratings. Talent is the one input that carries weight in the defense fit
(0.06-0.09), returning production and portal movement are close to zero.

## Opening lines (2026-10-11): the edge is in the early number

CollegeFootballData's `/lines` endpoint carries `spreadOpen` per book (DraftKings, Bovada; older years also Caesars, William Hill, ESPN Bet), and coverage is
good from 2024 (about 80% of games have an open that differs from the close). `scripts/fetch_cfbd_lines.py` stores it in `data/cfbd/lines_<year>.json`.
Re-running the walk-forward model (same ratings, same tuning on 2022-23 only) and grading its 5+ point disagreements against the OPEN instead of the close,
on the 2,937 of 3,653 games that have both (weeks 4+):

| | vs open | vs close |
|---|---|---|
| 2022-23 (tune) | 224-165 (57.6%) | 190-168 (53.1%) |
| 2024-25 (test) | 211-156 (57.5%) | 178-178 (50.0%) |
| All | 435-321 (57.5%), 2.8 SE above break-even | 368-346 (51.5%) |

Every season was above 54% against the open. Edge 7+: 59.8% vs open, 54.0% vs close. The model's average miss is still worse than the market's
(12.5 vs 12.28 open, 11.95 close), so the model is not more accurate than the market; it is early. That fits JP+'s 2026 picks beating the close by about 1.5
points: the edge is in the number posted before the market corrects it. Open lines carry small limits and move fast, so this is a record, not a price we know we could
bet. Caveats: only games that had an open on file; the open's posting time is unknown.

Forward check: `open_check()` in `scripts/cfb_model.py` re-projects every 2026 FBS game from week 4 on and grades it against the open (nothing tuned; the same 5-point
threshold), and the CFB Model tab shows the record. The first 57 picks (weeks 4-6) went 30-26 (53.6%), +1.3 points of closing-line value: too small to say anything.
`.github/workflows/update-cfbd-lines.yml` refreshes the lines once a day and never loses a stored open.

### Is the opening-line edge real? Four checks (2026-10-11, no tuning)

Same 2,368 games (weeks 4+, 2022-2025). Nothing here was tuned; these are readings of the one fixed model.

- **It predicts where the line goes.** Regressing the move from open to close on (model minus open): slope 0.135, t = 13.9 (0.06 on 2022-23, 0.21 on 2024-25). On 5+ point
  picks the line moved toward our side 54% of the time, away 28%, flat 17%, by 1.1 points on average. A model that only fit noise would not lead the market like this.
- **It is not one corner.** Over the open, 5+ point picks: home side 56.9%, away side 58.1%; picked side an underdog 58.3%, a favorite 54.8%; weeks 4-6 57.2%,
  7-9 55.4%, 10+ 59.2%; every season above 54%.
- **Bigger gaps do better.** 54.3% at 5-6 points, 54.7% at 6-8, 58.8% at 8-10, 65.2% at 10+. (A reading, not a new threshold: the pick line stays at 5.)
- **It decays but does not vanish.** The weight on (model minus line) in predicting the margin is 0.35 against the open (t = 5.3) and 0.20 against the close (t = 2.9).
  When the line moved toward us the pick won 62.1% against the open; when it moved away, 50.5%.

What this means: the model carries real information the market only absorbs over the week, so it is an early-line model. It is worth something while the number has not moved.
The CFB Model tab now lists next week's games the model is 5+ points off the open on, with where the line is now and how far it has already moved toward the model.
Still unproven in 2026 (30-26 on the first 56 graded) and still not bettable by assumption: we do not know when each open posted or what limit it carried.


## Promotion (2026-10-13): v2 prior + a special teams rating

`scripts/cfb_v2_st_study.py`. Special teams = net EPA on punts, kickoffs and field goals (play-by-play EPA_punt / EPA_kickoff / EPA_fg), one number per game
from the home side, ridge-rated and centred on last season's final x 0.6, added to the margin at weight 1.0. lambda 5 / carry 0.6 / weight 1.0 were chosen on
2022-23 by the average miss only; 2024-25 was read once. Grading against ESPN's recorded DraftKings open (2024-25 coverage 98%; 2022 none, 2023 about 40%) and the close.

Untouched test, weeks 4+, 5+ point disagreements:

| | miss | vs close | vs open |
|---|---|---|---|
| v1 (last season x 0.85) | 12.50 | 164-181 (47.5%) | 172-173 (49.9%) |
| v2 prior | 12.52 | 189-170 (52.6%) | 193-163 (54.2%) |
| v2 + special teams | 12.45 | 197-160 (55.2%) | 205-157 (56.6%) |

The market misses by 11.88 (close) and 11.99 (open). 197-160 is about 1 standard error above break-even, short of the 2 the project asks for, and the v2 prior does not
improve accuracy (the weight on the model's disagreement is 0.07 against v1's 0.13). Promoted anyway at the owner's request, with v1 kept as a graded shadow on every row.
The ESPN open is a later number than CollegeFootballData's first-posted spread: v1 is 57.5% against that one (above) and 49.9% against this one.

2026, weeks 4+ (170 games with an open): v1 31-26 (54.4%), v2 41-33, v2 + special teams 45-34 (57.0%) against the open; miss 12.94, 13.34, 13.22 against the open's 12.47.

## Team home field and a head-coach flag (2026-10-13): NO-GO, coach test blocked

`scripts/cfb_hfa_study.py`. Against the current model (v2 prior + special teams), walk-forward 2022-25, weeks 4+. Ridge penalties chosen on 2022-23 by average miss only; 2024-25 read once.

| | miss, tune | miss, test | 5+ vs close, test | 5+ vs open, test |
|---|---|---|---|---|
| current | 12.811 | 12.454 | 197-160 (55.2%) | 205-157 (56.6%) |
| + league mean home field | 12.825 | 12.446 | 198-164 | 200-162 (55.2%) |
| + conference home field | 12.800 | 12.474 | 195-171 | 191-171 (52.8%) |
| + team home field (home games only) | 12.684 | 12.413 | 217-185 (54.0%) | 200-179 (52.8%) |
| + team strength bias, no venue | 12.668 | 12.366 | 158-150 (51.3%) | 146-139 (51.2%) |
| + strength bias + venue | 12.624 | 12.358 | 169-154 (52.3%) | 156-146 (51.7%) |

- The team home-field gain is not home field. The home-games-only effects reach +/-9 points (Alabama +8.9, UMass -10.5), which is team-rating error, not venue. A strength bias applied at home and away (no venue term) does better (12.366), and adding a venue term on top moves the miss by only 0.008. Real venue advantage is close to nothing here.
- Accuracy improves by 0.04 to 0.10 points of miss, but the pick records get worse (vs the open 56.6% -> 51 to 53%). The market already prices team strength, so correcting the model toward it shrinks the disagreements that were the edge. Not shipped.
- Conference home field (the JP+ style grouping) does not help.
- The league-wide residual is +1.09 points of home margin, but recalibrating to it changes the miss by 0.01.
- Head coach: untested. ESPN's free coaches endpoint returns the current head coach for every season (Alabama 2023 comes back as DeBoer), so a new-coach flag built from it would be always zero. The test needs the CollegeFootballData /coaches feed through the Fetch CFBD data workflow.
