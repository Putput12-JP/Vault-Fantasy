# Practitioner Methods: How Winning NFL Prop and Side/Total Bettors Model (and What Is Verified)

Research date: 2026-09-28. Note on dates: several Unabated articles display a July 29-31, 2026 date; these look like republish/migration dates of evergreen content (the mean-vs-median thesis has circulated since at least 2021), so treat the date as "no later than." X/Twitter and Reddit were not directly retrievable; Reddit content below comes only via a secondary aggregator and is labeled as such.

## Q1. Who publishes NFL prop or game models and methodology, and what are their core techniques?

### Takeaway
The practitioners with the most transparent methodology (Unabated, Establish The Run, nfelo, Rufus Peabody) converge on: bottom-up usage projections (team plays x pass rate x target/route share x efficiency), converted to a full distribution and compared to the market at the MEDIAN, not the mean; for sides, blend your model with the market rather than replacing it. Only ETR publishes a multi-year prop W-L/ROI table; nfelo publishes an open-source backtest; nobody surfaced here publishes a prop CLV log.

### Cited Findings
- **Unabated (Captain Jack Andrews):** books set prop lines at the median ("the point where 50% of the time the result will be over and 50% ... under"), while DFS projections are means; player outcomes are positively skewed (floor of 0, big-game tail), so mean > median, and using DFS means as an answer key "result[s] in betting far too many overs, and is almost guaranteed to be unprofitable." Fix: simulate the projection to get the median. — [Unabated, The Biggest Mistake You're Making When Betting NFL Player Props](https://unabated.com/articles/the-biggest-mistake-youre-making-when-betting-nfl-player-props)
- **Unabated 3-step prop process:** (1) pick a "source of truth" projection set, (2) load it into a prop simulator (10,000 trials), (3) shop for the best price across books. Claims top-down (sharp-book-following) betting does not work for props because "player props typically don't have massive liquidity" and sharp books deprioritize them. Warns books "have a habit of not tolerating bettors who beat them on props," advises against aggressive Kelly on props, and says "feasting just on props is not a way to sustain your account." — [Unabated, Profitable Prop Betting In 3 Easy Steps](https://unabated.com/post/profitable-prop-betting-in-3-easy-steps)
- **Unabated projection-building series:** projections should adjust for QB and defense, and use a weighted mean AND a weighted standard deviation (variance is player-specific), then Monte Carlo 10,000 sims to produce a distribution. — [Unabated, How to Create NFL Player Projections For Player Props](https://unabated.com/post/creating-player-projections-for-nfl-player-props)
- **Establish The Run (ETR):** projects every player with "statistical models plus simulations" combined with player-usage and coaching-tendency analysis; first projections drop ~11pm ET Wednesday; ETR claims its projections move the prop market and "higher accuracy than market closing lines over the past 3 seasons" (self-reported, not independently verified). — [ETR In-Season NFL Props FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/) (as summarized in search index); [ETR NFL Full Stat Projections FAQ](https://establishtherun.com/nfl-full-stat-faq/)
- **ETR book-ecosystem piece (Jack Miller, Aug 25 2023):** Pinnacle and Betcris are NOT the sharpest prop books ("very limited prop sheet," "simply don't care as much about props"); Caesars (~$500 limits for sharp accounts "even on openers," moves aggressively on action) and FanDuel (originates its own numbers separate from DK/Caesars/MGM) stand out; DK, Caesars, MGM outsource origination from the same source; many offshores share tools and coordinate limits. — [ETR, Understanding the Current Ecosystem of NFL Player Props](https://establishtherun.com/understanding-the-current-ecosystem-of-nfl-player-props/)
- Secondary sources state Pinnacle hangs roughly $250 pre-gameday / $500+ gameday on NFL props and outsources prop lines to Swish Analytics (the ETR article itself did not name Swish; treat as unconfirmed). — [Unabated/search-index summary](https://unabated.com/articles/the-biggest-mistake-youre-making-when-betting-nfl-player-props); Circa described as the sharpest regulated US book that posts early and takes large bets — [valuebetfactory (aggregator)](https://valuebetfactory.com/betting-education/sharpest-sportsbooks)
- **nfelo (sides):** blends its spread with the market; optimal static weight was ~65% model / 35% market, and the blend beat both the model alone and the market alone on Brier score; raw nfelo slightly underperforms the market on Brier but grades positive ATS. It then uses "error-weighted" dynamic regression (trust market more when the model's recent error is higher). Code open on GitHub; picks tracked on PredictionTracker. Article dated Nov 8 2020. — [nfelo, Using Market Regression to Improve Prediction Accuracy](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/); [nfelo About](https://www.nfeloapp.com/about/)
- **Rufus Peabody (Massey-Peabody):** builds individual models for "hundreds and hundreds" of props and acts as an originator whose bets move lines; limits force him to route bets through a network of accounts (~$170k+ deployed on one Super Bowl per the 2022 profile). No performance numbers published in that piece. — [The Ringer, The King of Super Bowl Props (Sep 2022)](https://www.theringer.com/2022/9/21/23363621/gamblers-super-bowl-props-rufus-peabody-nfl). He also argues props are more profitable than sides/totals (podcast description) — [iHeart, The Volume / Straight Fire](https://www.iheart.com/podcast/1119-the-volume-78406522/episode/straight-fire-super-bowl-prop-148378416/); Massey-Peabody ratings vs market discussed weekly on the Unabated Podcast — [Apple Podcasts](https://podcasts.apple.com/us/podcast/nfl-week-16-massey-peabody-power-rankings/id1654826176?i=1000590840204)
- **Advanced Sports Analytics Substack (Aug 2021):** prop models should output cumulative distributions, not points; they used K-nearest-neighbors (historical comps weighted by inverse distance) and simulated outcomes across the neighbor set to get asymmetric distributions. Example: a player averaging 3 receptions but at 2-or-fewer in 57% of games would mislead a mean model into overs. No track record. — [Getting Ready for NFL: Props & Sports Modeling Approaches](https://advancedsportsanalytics.substack.com/p/getting-ready-for-nfl-props-and-sports)

### Inferences
- Vault's recency-weighted volume x efficiency with Normal/Poisson is structurally the same family as Unabated/ETR. The practitioner differentiators are (a) player-specific variance/skew (weighted SD, not a global sigma), (b) comparing at the median, and (c) a usage layer driven by coaching tendencies and news, not recency alone.
- nfelo's result (model only adds value when BLENDED with market, and only when recent error is low) matches Vault's finding that the team-rating model "only matches the market." The practitioner norm is market-as-prior, model-as-adjustment.

### Gaps
- Could not retrieve X/Twitter threads or original r/algobetting / r/sportsbook / r/NFLstatheads posts directly; no primary Reddit methodology posts are cited.
- No public, audited CLV log for any NFL prop modeler was found.

## Q2. Where are NFL edges today (props vs sides/totals; which prop markets are softest; timing; how long edges last)?

### Takeaway
Consensus: props > sides/totals for edge, because prop markets are thin, low-limit, and originated by a few shared vendors; edges are largest at openers (Wed-Fri) and get corrected fast once sharps/ETR projections hit. Unders have historically been the structural edge (mean/median skew plus public over bias), but practitioners report books have adjusted and under-only systems have cooled.

### Cited Findings
- Top-down betting fails in props because of thin liquidity; sharp books deprioritize props. — [Unabated, 3 Easy Steps](https://unabated.com/post/profitable-prop-betting-in-3-easy-steps)
- Props open early: TNF props Wednesday; Sunday/Monday props fill in late Thursday or Friday; "Waiting too long into the week ... will often result in only having sharp lines to bet"; bad lines each week get found by sharps quickly and corrected (e.g. Drake London receiving yards 60.5 -> 64.5). — [SportsBettingDime guide (media, not a verified bettor)](https://www.sportsbettingdime.com/guides/how-to/nfl-player-prop-bets/)
- ETR releases plays Wed-Sun, with early-week releases targeting "plays likely to move before weekend maturation." — [ETR In-Season NFL Props FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)
- Unders bias: extra juice sits on the over far more often than the under on rushing-yard boards, reflecting where recreational money goes; unders hit at a higher raw rate but "that alone does not make them profitable." — [BetSmart, NFL Rushing Props](https://www.betsmart.co/articles/nfl-rushing-props-guide)
- **Unverified individual record:** Stealing Lines (Dalton Kates) Substack reported 111-64 (63.7%) on 175 prop unders in a prior season, then 35-28 wks 1-6 and 12-24 wks 7-15 the next season; he says books "have adjusted over time" after being "too bullish on player projections," and that he drifted toward overs (58% of bets) after the losing stretch. Self-reported, not tracked on a third-party platform; season years not stated in the retrieved text. — [Stealing Lines, Finding a Flaw in the Process](https://stealinglines.substack.com/p/finding-a-flaw-in-the-process-best)
- Pick'em apps: edge comes from flat multipliers; a line on PrizePicks/Underdog below sportsbook consensus makes the over +EV; Underdog cuts payouts or posts "shifted" lines on heavily correlated same-game legs (QB + own WR) to protect itself; volume-driven props (dual-threat QB rush yards, target-share WR yards, receptions) are recommended over boom/bust props; 2-4 leg entries preferred for variance. — [SmartStake, How to Beat PrizePicks](https://www.smartstake.app/learn/how-to-beat-prizepicks); [OddsShopper, PrizePicks NFL Strategy](https://www.oddsshopper.com/articles/betting-101/prizepicks-nfl-strategy); [Stokastic, correlation in pick'em (NBA)](https://www.stokastic.com/nba/nba-dfs-correlation-for-pickem-entries-strategy-for-prizepicks-underdog-more-ac11/) (all tout/media sources; no verified records)
- Sustainability: books limit prop winners; Peabody needs a network of accounts to get money down. — [Unabated](https://unabated.com/post/profitable-prop-betting-in-3-easy-steps); [The Ringer](https://www.theringer.com/2022/9/21/23363621/gamblers-super-bowl-props-rufus-peabody-nfl)

### Inferences
- Vault's winning narrow subset (WR/TE receiving-yard unders) and "openers beat closers" both fit the practitioner picture exactly: receiving yards are the most right-skewed volume market, and edges live at open. The ETR 2023-24 near-zero ROI and Stealing Lines' decay suggest unders edges shrink as books adjust, so the gate should be re-validated each season rather than assumed permanent.
- Vault's "biggest disagreements are model errors" matches the practitioner reason prop edges get corrected fast: the market has news (role changes, injuries) the model lacks.

### Gaps
- No quantified public study of how quickly prop openers converge (hours-to-correction) was found.
- No source quantified which prop markets are softest by measured ROI across a large sample; "low-volume players / alt lines" softness is asserted in tout content but not measured.

## Q3. Simulation vs simpler projection + distribution: when is simulation worth it?

### Takeaway
Practitioners use "simulation" mostly to turn a mean projection into a skewed distribution and a median (Unabated's 10k-trial simulator, ETR's sims, KNN resampling). Full play-level game sims are marketed but not shown to beat simpler approaches; the demonstrated value of sims is (1) skew/median for single props and (2) correlation for same-game combinations.

### Cited Findings
- Unabated's simulator exists specifically to convert a mean to an effective median; "to convert a mean projection to an effective median you need simulation." — [Unabated, Biggest Mistake](https://unabated.com/post/the-biggest-mistake-youre-making-when-betting-nfl-player-props)
- KNN comp-based resampling produces asymmetric distributions without a parametric assumption. — [Advanced Sports Analytics](https://advancedsportsanalytics.substack.com/p/getting-ready-for-nfl-props-and-sports)
- Correlated legs (QB pass yds + his WR rec yds) move together; pick'em apps recognize this and cut payouts/shift lines on the most obvious pairs. — [SmartStake](https://www.smartstake.app/learn/how-to-beat-prizepicks)
- Drive-level simulation products exist (e.g., Predictium) but publish no verifiable edge. — [Predictium, About the NFL Model](https://www.predictium.ai/nfl/about)

### Inferences
- For single props, an empirical or skewed distribution with player-specific variance captures most of what simulation buys; Vault's Normal assumption on yardage is the specific weakness practitioners flag (symmetric Normal puts median = mean, overstating overs).
- Simulation with player correlation is worth building only for multi-leg products (SGP, pick'em slips), which matches Vault's own MC spike (game-market MC = closed form; player-level QB~WR1 correlation meaningful).

### Gaps
- No practitioner source with a head-to-head backtest of play-level sim vs projection+distribution for NFL props was found.

## Q4. How do they evaluate models, and what pitfalls do they warn about?

### Takeaway
CLV vs a no-vig sharp close is the standard for sides/totals, but leading prop practitioners explicitly say CLV is unreliable in props because the closing price is not a well-discovered fair value. For props, evaluate on results over large samples plus calibration; warn about overfitting, mean-vs-median, limits, and aggressive staking.

### Cited Findings
- CLV must be computed against the vig-free closing line; it works best in efficient, high-volume markets like NFL sides/totals; in props Captain Jack Andrews says "(CLV) doesn't mean anything in props" due to low limits and few market signals; "CLV is a comfort, not a crutch." — [Unabated, Getting Precise About Closing Line Value (Jason Scavone)](https://unabated.com/articles/getting-precise-about-closing-line-value)
- In low-limit prop markets sharp money moves the line "more than it should," so a positive prop CLV may be an informed guess rather than proof. — [Unabated CLV article](https://unabated.com/articles/getting-precise-about-closing-line-value); [Wizard of Odds, Player Props math](https://wizardofodds.com/article/player-props-understanding-the-math-behind-the-lines/)
- Aggregated Reddit algobetting lessons (secondary source): overfitting is "the number-one killer"; the goal is CLV, not picking winners; one AMA reported ~EUR 30,000 profit in 2022 from thin edges, volume, maintenance, and fighting account limits. Unverified. — [SportBotAI, Do Betting Models Actually Work? What Reddit Says (2026)](https://www.sportbotai.com/blog/sports-betting-model-reddit)
- nfelo benchmarks against the market on Brier score and ATS, with open code and PredictionTracker submission. — [nfelo](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/)
- Pitfalls named by practitioners: using DFS means (over bias); over-Kelly on props; relying on props alone as books limit winners — [Unabated](https://unabated.com/post/profitable-prop-betting-in-3-easy-steps); discipline drift after variance (switching away from unders during a cold streak) — [Stealing Lines](https://stealinglines.substack.com/p/finding-a-flaw-in-the-process-best); injuries and blowout game scripts driving under losses — same source.

### Inferences
- Vault's "openers beat closers" result should not be read as "we have no edge" in props; per Unabated, prop closes are noisy benchmarks. Better prop evaluation: ROI and calibration by market/side over large samples, plus CLV only against the few books that actually take prop limits (e.g., Caesars/FanDuel/Circa per ETR), not a consensus close.

### Gaps
- No practitioner specified a minimum prop sample size; no standard error figures were published.

## Q5. Which claims are verified vs unverified?

### Takeaway
Nothing found is third-party audited with CLV. The strongest are ETR's multi-year self-published ledger (mixed, decaying, ROI 0.5% to 22%) and nfelo's open-source backtest. Everything else is methodology or self-report.

### Cited Findings
- **ETR published NFL prop record (self-reported, graded by ETR, no CLV):** 2019 50-36 (+$963); 2020 55-34 (+$1,907); 2021 216-118 (+$8,572, 22.1% ROI); 2022-23 308-222 (+$5,860, 9.5%); 2023-24 253-225 (+$267, 0.48%); 2024-25 standard 228-158 (+$5,969, 14.09%); 2024-25 alt/longshot 38-222 (+$736, 17.62%); 2025-26 203-164 (+$2,405, 6.03%). Staking: $100 risk on dogs / to win $100 on favorites; books include FanDuel, DK, Caesars, BetMGM, ESPN Bet, BetRivers, Circa. — [ETR In-Season NFL Props FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)
- **nfelo:** open code on GitHub + PredictionTracker submissions; publishes weekly backtest back to 2009 (moderately verifiable). — [nfelo About](https://www.nfeloapp.com/about/)
- **Pikkit:** platform claims records are verified via sportsbook sync and shows ROI and CLV per user, filterable by sport/bet type; no specific NFL prop modeler record was located there. — [Pikkit, Follow Bettors](https://pikkit.com/follow-bettors); [Pikkit CLV](https://pikkit.com/closing-line-value)
- **Unverified:** Stealing Lines under record (self-reported) — [Stealing Lines](https://stealinglines.substack.com/p/finding-a-flaw-in-the-process-best); Reddit EUR 30k AMA (via aggregator) — [SportBotAI](https://www.sportbotai.com/blog/sports-betting-model-reddit); Rufus Peabody profitability (widely reported reputation, no numbers in the retrieved profile) — [The Ringer](https://www.theringer.com/2022/9/21/23363621/gamblers-super-bowl-props-rufus-peabody-nfl); ETR's "more accurate than closing lines" claim — [ETR](https://establishtherun.com/nfl-full-stat-faq/); media model records (SportsLine, CBS "Inside the Lines") are marketing — [CBS Sports example](https://www.cbssports.com/betting/news/inside-the-lines-rising-best-bets-up-9-2-units-heading-into-nfl-week-4-led-by-17-8-mark-on-passing-props).

### Inferences
- ETR's ledger is the best available real-world benchmark: even a market-moving, well-resourced projection shop ranges from ~0% to ~22% ROI on selective prop bets, with a near-breakeven year. A full-board prop model losing is expected; selective, early, shopped bets are how they win.

### Gaps
- No independently audited (e.g., Pikkit-synced) NFL prop modeler with a published CLV series was found.
- Could not verify ETR's ledger against timestamped bet slips.
