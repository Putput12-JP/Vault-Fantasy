# Open-source code and academic work on NFL prop and game-line prediction

Research date: 2026-09-28. Scope: open repos + published methods that claim to match or beat closing lines; evidence quality flagged throughout. "OOS" = out-of-sample. Many findings come from repo READMEs (self-reported, unaudited).

## 1. Play-by-play / drive-level NFL simulators: do any publish results vs Vegas or closing lines?

### Takeaway
Open PBP/drive simulators exist, but they are built for strategy questions (4th down, run/pass mix) or season/futures sims. None I found publish a record against closing spreads/totals. The one hobby repo that sims props + spreads + totals from nflverse PBP shows no market backtest. This fits the client's own result that a Monte Carlo sim built on team ratings only reproduces the closed form.

### Cited Findings
- **NFLSimulatoR** (R, CRAN): simulates plays and drives from nflscrapR/nflfastR data to evaluate strategies. Built-in examples are 4th-down go-for-it and varying the pass/rush mix. It is a strategy tool, not a line predictor, and has no betting results. [GitHub](https://github.com/rtelmore/NFLSimulatoR); [CRAN README](https://cran.r-project.org/web/packages/NFLSimulatoR/readme/README.html)
- **dlm1223/nfl-simulation**: drive simulations that test play-calling strategies, e.g. whether high-EPA/YPA plays are best. No market comparison. [GitHub](https://github.com/dlm1223/nfl-simulation)
- **nflverse/nflseedR** (R): Monte Carlo season simulator that takes the user's own game model. The authors note it can help with futures and win-total betting. The game model is left to the user and there is no line backtest. [GitHub](https://github.com/nflverse/nflseedR)
- **hadantes-lab/ff-model**: pulls live PBP (nflverse) plus The Odds API, builds per-player stat distributions, and runs Monte Carlo sims to price props, spreads and totals. No published results were found in the search summary. [GitHub](https://github.com/hadantes-lab/ff-model)
- **dgrifka/nfl_simulator**: another nflverse-based simulator. I did not inspect it and saw no market results. [GitHub](https://github.com/dgrifka/nfl_simulator)
- **Nicowirz/nfl-props** also fits game margin and total distributions. Walk-forward 2025: margin NLL 4.0209 vs 4.0980 baseline (about 1.9% better), total NLL 4.0093 vs 4.0582 (about 1.2%). The baseline is a naive reference, **not the market**, so this says nothing about beating Vegas. [GitHub](https://github.com/Nicowirz/nfl-props)

### Inferences
- There is no open evidence that PBP/drive simulation beats closing game lines. Its real value for Vault is **correlated player outcomes inside a game** (QB/WR stacks, same-game legs). It does not produce a better spread. This matches the client's earlier finding: game-level MC = closed form, but player-level correlation matters.
- For porting, NFLSimulatoR's logic is empirical resampling of plays by down/distance/field-position state. That is portable to stdlib Python (bucketed resampling) but data-heavy: full nflverse PBP runs to tens of MB per season.

### Gaps
- I found no public PBP simulator with a published ATS/CLV or Brier-vs-close record. The absence is itself a signal, though my search was not exhaustive (GitHub topic pages were not fully crawled).
- Licenses for NFLSimulatoR, ff-model and nfl_simulator were not verified.

## 2. Player-prop / player-stat-distribution models with calibration or betting results

### Takeaway
The best open prop repos use per-player ability plus opponent-defense ratings on a transformed scale, with recency decay and ridge shrinkage (log-normal yards), Poisson for TDs/receptions, and calibration audits. **None report ROI or CLV against real historical prop lines**, because free historical prop-line archives do not exist. Their "edges" are measured against naive baselines or proxy lines. The documented modeling lessons are directly usable: zero-inflation, mean vs median, and availability conditioning.

### Cited Findings
- **Nicowirz/nfl-props** (Python, no license stated):
  - Method: weighted ridge regression on `log(yards + 10)`, fitting player "ability" and opponent "defense allowed" ratings. This gives a log-normal distribution per player-game.
  - Settings: recency weight `0.5^(days_ago/halflife)` with a 180-day default half-life, L2 strength 5.0, and position-group residual SD.
  - Extra features: usage-share covariate (trailing target/carry share), wider variance for QBs with fewer than 4 games, and a filter that drops legs where model and book disagree by more than 30 pp.
  - Walk-forward 2025 NLL vs baseline: pass yds 0.4980 vs 0.5875 (about 15% better), rush yds 0.7642 vs 0.8443, rec yds 0.9152 vs 1.0096. Calibration deciles are near uniform.
  - Poisson rate models for receptions and TDs beat baselines by 2-6%.
  - Self-declared gaps: no injury, inactive or depth-chart awareness, and no same-game correlation. Kalshi prices are live only, with no history.
  - [GitHub](https://github.com/Nicowirz/nfl-props)
- **Search-summary claims from prop repos** (I did not open them, so which repo each belongs to is unconfirmed):
  - Receiving-yard calibration buckets ran 8.1%-12.9% per decile against a 10% target, with a mild excess in the bottom decile.
  - About 8% of graded props were players who played but recorded nothing. A smooth continuous distribution under-weights this spike at zero, and zero-inflation was proposed as the fix.
  - Right skew means a line below the projected mean can still sit above the median.
  - One repo let the median factor rise with the projected mean, which improved receiving-yard Poisson log loss from 19.28 to 19.17 and from 18.25 to 18.16.
  - Candidate sources: [MattFos18/nfl-model PR #171](https://github.com/MattFos18/nfl-model/pull/171), [ctrax68-hash/NFL-Prop-Model](https://github.com/ctrax68-hash/NFL-Prop-Model), [SaintYuki/NFL-TD-Model](https://github.com/SaintYuki/NFL-TD-Model)
- **Barrett879/gridironvalue** (Python/Streamlit, nflverse/FTN data):
  - Projects `E[Y | appeared]`, i.e. conditional on the player playing, which matches how props void. Availability is a separate `p_play`.
  - Median-based distributions.
  - OOS test (trained through 2022, tested on 2024) "edge" in pp: pass attempts +11.5, pass yds +8.4, targets +6.0, rec yds +2.9, rush yds +2.4.
  - **Caveat, stated by the author:** these edges are measured against season-to-date player means used as *proxy lines*, "as historical line archives don't exist". The author says to read them "as a ranking, not as a promise about a real board".
  - [GitHub](https://github.com/Barrett879/gridironvalue)
- **Hierarchical Bayesian prop models:** I found no peer-reviewed NFL paper on receiving yards or targets. The closest items are a student RPubs note on RB rushing yards with hierarchical Bayesian regression and a blog on Bayesian hierarchical fantasy projections. Neither reports betting results. [RPubs](https://rpubs.com/JamesRAngus/BayesianStatsAss3); [srome blog](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/)
- **Industry/practitioner claims (unverified, not academic):**
  - Books price props to the median, while DFS projections are means. Betting means against medians produces too many overs. [Unabated](https://unabated.com/post/the-biggest-mistake-youre-making-when-betting-nfl-player-props)
  - Anecdotal under records of 25-11 and 111-64 over a season. These are single-bettor self-reports. [Stealing Lines](https://stealinglines.substack.com/p/finding-a-flaw-in-the-process-best)

### Inferences
- Vault's current prop design (volume × efficiency, Normal/Poisson, isotonic, shrink to market) is already at or above the open-source frontier. No open repo demonstrates real-line profitability.
- Concrete upgrades supported by these repos:
  - An opponent-defense term fit jointly with player ability (ridge on log scale).
  - A zero-inflated / hurdle component for receiving stats.
  - Explicit `E[Y | plays]` × `p_play` separation.
  - Log-normal instead of Normal for yardage.
- The documented over-bias from mean-vs-median is consistent with Vault's finding that only receiving-yard *unders* won. It suggests the edge may be structural (skew / books' medians vs public means), not model skill.
- A ridge regression on the log scale is easy to port to stdlib Python: closed-form normal equations or a few hundred coordinate-descent iterations.

### Gaps
- No academic paper found that tests NFL player-prop market efficiency with real historical prop lines. This is the biggest literature gap. Searches returned only NBER/Massey-Thaler (draft picks, not props) and spread/total studies.
- There is no free historical NFL prop-line archive, so every open prop "backtest" is against proxies. Vault's own captured line history (prop line snapshots) is likely rarer than anything public.

## 3. Academic evidence on NFL betting-market efficiency and documented inefficiencies

### Takeaway
Spreads and totals are close to efficient at close. Documented inefficiencies are small, often from older data, and tend to decay:
- totals underpricing adverse weather, strongest at open and in pre-2005 data
- open-to-close momentum overreaction, reversed at game outcome
- underpricing of home underdogs
- a reverse favorite-longshot bias in moneylines
- more line movement in low-attention games

Recent closing-total weather edges look real in raw hit rates but are mostly priced by close.

### Cited Findings
- **Borghesi (2008), Applied Financial Economics, "Weather Biases in the NFL Totals Market":**
  - 1984-2004 data. Heat, wind and rain reduce scoring, and the totals market under-incorporates adverse conditions.
  - Humidity and wind strategies reject efficiency, with win rates near 57% in both spread and totals markets.
  - Pre-2005 data, so likely decayed.
  - [ResearchGate](https://www.researchgate.net/publication/24071150_Weather_Biases_in_the_NFL_Totals_Market); [T&F](https://www.tandfonline.com/doi/full/10.1080/09603100701335432)
- **Jeff's Edge (Substack, 2025), about 7,000 regular-season games 1999-2025 vs *closing* totals:**
  - Under hit rate by wind: 49% under 10 mph, 55% at 10-14 mph, 56% at 15+ mph, 59% at 18+ mph (breakeven 52.4%).
  - Temperature does little: games at 32°F or below go under 47% of the time. Domes 49%.
  - Wind lowers scoring but not variance (SD stays 13-14 across conditions).
  - Author's caveat: books price forecast weather into closing lines, so bettors rarely capture it.
  - Non-peer-reviewed. Sample sizes per bucket not given in my extract.
  - [Substack](https://jeffsedge.substack.com/p/i-evaluated-7000-nfl-games-to-see)
- **Pinnacle** also reports under rates of about 54.5% or better at 15+ mph wind, 55.6% at 17 mph and 60% at 25 mph. The page is undated and the sample is not given in the snippet. [Pinnacle](https://www.pinnacle.com/betting-resources/en/football/nfl-points-totals-and-the-effect-of-the-weather/5zn2av8e4w2g9sf9)
- **Moskowitz (2021), Journal of Finance, "Asset Pricing and Sports Betting":**
  - More than 100k contracts across NFL/NBA/MLB/NHL over almost three decades.
  - Strong momentum and weaker value effects move prices from open to close, then are **fully reversed by the outcome**. This means closing lines slightly *overreact* relative to the open.
  - Strategy returns: 13.07% per year, t = 3.66, Sharpe 0.47. Whether these survive vig was not confirmed in the abstract I read.
  - [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2635517); [JF](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13082)
- **Shank (2018/2019), Journal of Economics and Finance, "Is the NFL betting market still inefficient?":**
  - Finds both spread and totals markets statistically inefficient.
  - Books underestimate home teams, especially when they are substantial underdogs (home dogs cover more).
  - Companion SSRN papers cover divisional rivals and the "wisdom of the crowd".
  - [Springer](https://link.springer.com/article/10.1007/s12197-018-9431-4); [SSRN 3022567](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3022567); [SSRN 3385529](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3385529); [SSRN 3289715](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3289715)
- **NFL moneyline study, 2007-2016:** inefficiencies in both opening and closing moneylines, consistent with a *reverse* favorite-longshot bias (favorites overbet). [Journal of Economic Insight](https://journalofeconomicinsight.com/index.php/joei/article/view/1335)
- **"Examining the impact of visibility on market efficiency" (2023), Journal of Economics and Finance:** NFL lines 2007-2021 show more frequent and larger line movements in games with less widespread attention (lower-visibility games). [Springer](https://link.springer.com/article/10.1007/s12197-023-09656-5)
- **Kuper (2012), UC Berkeley thesis:** closing moneylines were found inefficient, with exploitable strategies. Older data, student work. [PDF](https://econ.berkeley.edu/sites/default/files/Kuper.pdf)
- **Dmochowski (arXiv, Sept 2026), "profit-bias identity":**
  - MLB only, 1,139 games.
  - Heavy public lean toward favorites, but books did not shade prices to match it. Realized margin was indistinguishable from hold alone.
  - Warns that pooled bet-share/outcome correlations are a Simpson's paradox.
  - Relevant as a caution against "fade the public" features.
  - [arXiv](https://arxiv.org/abs/2609.06739)
- **Practitioner claim (not academic):** props are "the softest numbers", especially defensive props, because of lower liquidity and less analyst attention. [Squawka](https://www.squawka.com/us/nfl/props/)
- **USPTO patent on correlated prop analysis:** it states that sportsbooks under-resource prop line-making and are uncomfortable taking correlated parlayed props. This is an industry-insider framing, not an empirical test. [USPTO 11250671](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11250671)

### Inferences
- The most defensible documented edges for Vault's architecture:
  - wind effects on totals and pass props, taken **early in the week before the close prices them**
  - low-attention games, where lines move more (the opener is less informed)
  - home underdogs, a small and debated effect
- All of these suggest timing matters more than model sophistication. The measurable target should be CLV against the close, not ATS.
- Vault's pushed windMult (knot 10 mph, floor .85) is consistent with the 10-14 mph jump in under rate. But the raw closing-total under rates above 52.4% conflict with the "priced at close" caveat, likely because of small buckets. They must be tested against Vault's own line history before being treated as edge.

### Gaps
- No peer-reviewed study of NFL **player-prop** efficiency using real lines was found (see Q2).
- The Shank paper's exact effect sizes and after-vig profitability could not be read: the Springer page was paywalled and redirected.
- Evidence on early-week vs closing line inefficiency is only indirect (Moskowitz momentum, 2023 visibility paper). I found no NFL-specific estimate of how much opener CLV a public model can capture.

## 4. Open game-line models with honest OOS results: does anything beat the close?

### Takeaway
No public model has a verified, OOS record of beating NFL closing lines on Brier/log-loss.
- Every audited comparison (538 in 2018, walk-forward Elo in nfl-data-stack 2021-2025) loses to the close.
- nfelo advertises about 55% ATS vs the close for 2009-2026. Its spread is itself market-regressed, and whether that record is out-of-sample or backfit is **undisclosed**.
- Treat ~55% claims as unverified. Vault's ~48% ATS with market-hugging behavior is typical, not an outlier.

### Cited Findings
- **nfelo (Robby Greer), nfeloapp.com:**
  - Straight-up accuracy 66.74%, MAE 10.1 points.
  - ATS 55.97% vs the open and 55.38% vs the close, 2009-2026.
  - 137.6 cumulative units vs 107.5 expected; average CLV 5.75% per play.
  - "vs closing line" −0.04%, i.e. roughly zero improvement over the closing line's accuracy.
  - (An earlier search snapshot showed 55.24% ATS and 132.6 units, so the numbers update weekly.)
  - [Performance page](https://www.nfeloapp.com/games/nfl-model-performance/)
- **nfelo inputs and validation:** 538-style Elo, QB-specific adjustments, weighted EPA, and market analysis. The about page does not say whether performance is OOS or backfit. [About](https://www.nfeloapp.com/about/)
- **nfelo market regression (Nov 2020):**
  - Final line = weighted average of model spread and market spread. A 65% weighting was optimal (the extract does not confirm whether the 65% sits on the model or the market).
  - The blended line beat the market's Brier score.
  - Adds dynamic regression: less shrink to market when the model's trailing error on those teams is lower, bounded 0-1.
  - Author's note: a model with a Brier score *below* the market (i.e. better, as reported) can still grade positive ATS. The logic is unclear, so treat it cautiously.
  - This is an in-sample weight search, so selection bias is likely.
  - [nfelo analysis](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/)
- **Manifold Markets** ran "Will nfelo predictions beat Vegas in 2024/25?". The resolution was not retrieved, but the market shows public doubt. [Manifold](https://manifold.markets/bence/will-nfelo-predictions-beat-vegas-i)
- **michellepellon/nfl-data-stack, issue #30 (walk-forward harness gated in CI, close as benchmark):**
  - 1,424 games from 2021-2025 including playoffs. Closing market: Brier 0.2110, log loss 0.6108, spread MAE 9.76. Plain Elo: Brier 0.2236, MAE 10.20.
  - 2025 alone (224 games): market 0.2092 vs base Elo 0.2119 vs feature-adjusted Elo 0.2136. Adding features made it *worse*.
  - Issue #20 in the same repo proposes a starting-QB Elo adjustment.
  - [Issue #30](https://github.com/michellepellon/nfl-data-stack/issues/30); [Issue #20](https://github.com/michellepellon/nfl-data-stack/issues/20)
- **FiveThirtyEight QB-adjusted Elo:**
  - Brier 0.219 vs old Elo 0.224 by end of 2019 (search summary). The 538 page now redirects to ABC, so it could not be verified directly.
  - Code and data: [fivethirtyeight/nfl-elo-game](https://github.com/fivethirtyeight/nfl-elo-game). A walk-forward pure-Elo Brier of about 0.222 vs a closing benchmark of about 0.20-0.21 appeared in the same summary.
- **trevorData/538NFL, 2018 season, 256 games:**
  - RMSE: 538 at 13.57 vs Vegas at 13.10 (predicting a tie every game gives 14.50).
  - Winners picked: Vegas 171, 538 158.5.
  - Betting 538 against Vegas spreads went 122.5 of 256, under 50%.
  - 538 over-rated home teams by 0.39 points and favorites by 0.93 points.
  - [GitHub](https://github.com/trevorData/538NFL)
- **Hobby repos with walk-forward tests:**
  - Leave-one-out CV at multiple checkpoints chose 100% Vegas over Elo blends.
  - "Vegas beats everything at every checkpoint."
  - A Gaussian process model had margin error only 2% worse than Vegas and picked 64.36% of winners, but was just under 51% ATS.
  - These are search-summary extracts. The exact repo attribution is uncertain; one of them is likely [nemethb3/nfl-prediction-model](https://github.com/nemethb3/nfl-prediction-model).
- **Schlicht (2017, arXiv 1710.06551), "Exploiting oddsmaker bias":** claims methods that exploit oddsmaker biases perform best. The abstract gives no ATS/profit numbers, and the paper is unreviewed. [arXiv](https://arxiv.org/abs/1710.06551)
- **ESPN FPI:** there is an ECU/Decision Sciences Institute paper, "Is FPI a Good Bet?" (not read; a gap). [PDF](https://myweb.ecu.edu/robbinst/PDFs/Betting%20on%20FPI%20-%20DSI.pdf)
- **Older baseline:** "The Performance of Betting Lines for Predicting the Outcome of NFL Games" (arXiv 1211.4000). The lines are well-calibrated predictors; I did not re-read it. [arXiv](https://arxiv.org/pdf/1211.4000)

### Inferences
- The realistic ceiling for an independent public team-rating model is roughly **Brier 0.002-0.013 worse than the close**. A blended model can at best tie the close.
- nfelo's ~55% ATS vs the close contradicts every other audited source. Without OOS disclosure it should be treated as unverified. Possible explanations: selective play thresholds, a backfit blend weight, or CLV measured against openers.
- Gains in these models come from QB adjustments, market regression, and adaptive shrink. That is the same menu Vault already has, so a ratings upgrade alone will not flip 48% ATS.

### Gaps
- Massey-Peabody, PFF ELO and Ben Baldwin models: I found no published OOS-vs-close records in this pass. Not verified.
- Resolution of the Manifold nfelo market and nfelo's per-season OOS status: not found.

## 5. Role of market-based priors (de-vigged close as baseline, model only the adjustment)

### Takeaway
Both the academic and the practitioner evidence favor using the market as the baseline and modeling residuals or deviations:
- Hubáček et al. (2019) show that *decorrelating* from the book beats maximizing accuracy for profit.
- nfelo's blend beats both of its inputs on Brier.
- Walk-forward CV in hobby repos converges to 100% market weight for sides.

The implication is that Vault should target information the close does not yet have (timing, injuries, weather at open, prop-specific soft spots). Re-predicting the game from scratch is the wrong target.

### Cited Findings
- **Hubáček, Šourek & Železný (2019), International Journal of Forecasting 35(2):783-796, "Exploiting sports-betting market using machine learning":**
  - Adds a loss term that penalizes correlation with the bookmaker's implied probabilities. Trained this way, the models produced greater profit than accuracy-optimized models.
  - Key line: "a highly accurate predictive model is useless as long as it coincides with the bookmaker's model".
  - The paper is on NBA, not NFL.
  - [PDF](http://ida.felk.cvut.cz/zelezny/pubs/ijf.2019.pdf); [EconPapers](https://econpapers.repec.org/article/eeeintfor/v_3a35_3ay_3a2019_3ai_3a2_3ap_3a783-796.htm)
- **nfelo market regression:** a weighted model/market blend (65% weight) with dynamic, error-dependent shrink beat the market's own Brier score (in-sample, 2020). [nfelo](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/)
- **Walk-forward LOO CV in open repos chose 100% Vegas over Elo blends for sides.** Attribution uncertain; see Q4. [nemethb3/nfl-prediction-model](https://github.com/nemethb3/nfl-prediction-model)
- **"Machine learning for sports betting: Should model selection be based on accuracy or calibration?" (2024):** argues for selecting on calibration rather than accuracy. The page returned 403, so its ROI figures are not verified here. [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S266682702400015X)
- **Nicowirz/nfl-props:** drops legs whose model probability differs from the book by more than 30 pp. This is a practical "large disagreement = model error, not edge" guard, similar in spirit to Vault's MAX_PROJ_GAP. [GitHub](https://github.com/Nicowirz/nfl-props)
- **Moskowitz (2021):** closing prices overreact to momentum relative to the open. A market prior is therefore best anchored on the close for accuracy, but *betting* value sits in predicting open-to-close movement. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2635517)

### Inferences
- Recommended framing for Vault:
  - prior = de-vigged sharp consensus (or Kalshi mid)
  - model = residual on features the market under-weights (wind at open, low-visibility games, zero-inflation/median skew in props, injuries after open)
  - validation metric = CLV vs close plus Brier-vs-close
- A decorrelation penalty à la Hubáček is portable to stdlib Python: add λ·corr(model_p, book_p) to a logistic loss optimized by simple gradient descent.
- Given the literature, props (thin, under-resourced, median-priced, no public history) are more promising than sides/totals for an independent edge. Vault's own settled line history is a data asset no open repo has.

### Gaps
- No NFL-specific paper was found applying the decorrelation loss or residual-on-market modeling with OOS results.
- I found no quantified estimate of how much of Vault's measured edge would survive once benchmarked against Pinnacle/sharp close rather than DFS/soft-book lines.
