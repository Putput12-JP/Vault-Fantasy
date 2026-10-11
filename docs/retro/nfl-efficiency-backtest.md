# NFL: does the college method find anything? (2026-10-11)

`scripts/nfl_efficiency_study.py`. The same method as the college model (opponent-adjusted EPA per play, ridge, last season's
ratings shrunk as the prior, ratings for each week built only from earlier games), on nflverse play-by-play and the nflverse
closing spread. Plays: pass and run, no kneels or spikes, win probability between 5% and 95%, EPA clipped to +-4. Tuning
seasons 2017-2021 (2016 seeds the prior), 16 settings tried, chosen on the lowest average miss on the tuning seasons only
(shrink 0.6, ridge 400, 55 points per EPA, 1.5 home field). 2022-2025 read once.

| Weeks 4+, model disagrees with the close by | Tuning 2017-21 | Test 2022-25 |
|---|---|---|
| 1.5+ points | 330-340 (49.3%) | 246-275 (47.2%) |
| 2.5+ points | 231-223 (50.9%) | 157-191 (45.1%) |
| 3.5+ points | 146-149 (49.5%) | 90-124 (42.1%) |
| 5+ points | 66-66 (50.0%) | 43-53 (44.8%) |

Average miss on the test seasons: model 10.12 points, market 9.43. Regressing the final margin on the market and on (model -
market) gives the model's disagreement a weight of -0.29, so a blend with any positive weight is worse than the market alone
(miss 9.45 at 5%, 9.47 at 10%, 9.51 at 20%, against 9.43).

**What this says:** no edge, and the market is clearly better than the model. The tempting reading, fading the model (about 55%
at 2.5+ and 58% at 3.5+ on the test), is not supported: the same model was 50.9% and 49.5% on the tuning seasons, so the
negative result is specific to four test seasons, and the 2.5+ miss is under two standard errors. That would be a new
hypothesis to test forward, not a finding. Nothing ships; the NFL gets no model page. The framework (walk-forward, closing-line
grading, a blend weight, a shadow tracker) is what carries over, not the model.

Why it is weaker than college: 17 games per team keeps ratings noisy all year, the market already uses the same public stats,
and quarterback changes and injuries move NFL lines more than team ratings do, and a team-level model cannot see them.
