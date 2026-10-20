# Data Sources and Market-Based Methods for Sharper NFL Prop and Game-Line Prediction

Scope: free/cheap usage data usable from stdlib Python/Node on GitHub Actions, de-vig and sharp-book weighting, market-implied distributions, line-movement signals, CLV evaluation, and market timing. Research date 2026-09-28. Style note: this file avoids em dashes by project rule; citations follow each claim in brackets.

## Q1. Which free/cheap sources provide route participation, target share, snap counts, and how timely are they?

### Takeaway
nflverse already exposes most of what a role-change detector needs for free: PFR snap counts (refreshed 4x daily in season), FTN manual charting (2022+, charted within 48h of each game, CC-BY-SA 4.0 with attribution), Next Gen Stats weekly (nightly), daily depth charts with ISO8601 timestamps, and daily injury data. The one big gap is weekly per-player route participation: nflverse's play-level participation (who was on the field) for 2023+ comes from FTN and is only published after the postseason, so in-season route counts require a paid source (FantasyPoints Data, PFF Pro, etc.) or a proxy.

### Cited Findings
- FTN charting fields include qb_location, n_offense_backfield, n_defense_box, is_motion, is_play_action, is_screen_pass, is_rpo, read_thrown (primary/secondary/tertiary/checkdown/designed/scramble drill, i.e. a first-read signal), is_catchable_ball, is_contested_ball, is_created_reception, is_drop, n_blitzers, n_pass_rushers, is_qb_fault_sack; seasons 2022 onward. [nflreadr FTN dictionary](https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html)
- FTN charting is "charted within 48 hours following each game", licensed CC-BY-SA 4.0, attribution required to "FTN Data via nflverse". [nflreadr load_ftn_charting](https://rdrr.io/cran/nflreadr/man/load_ftn_charting.html)
- nflverse update schedule: pbp and player stats nightly after games (raw pbp ~15 min after game end; "Thursday's load_pbp() is the cleanest" due to stat corrections); FTN charting and PFR snap counts and PFR advanced stats every day at 0/6/12/18 UTC in season; NGS player weekly nightly 3-5 AM ET; rosters daily 7AM UTC; depth charts daily 7AM UTC year-round, now with ISO8601 timestamps rather than weekly assignments; injuries daily 7AM UTC; schedules every 5 minutes. [nflverse data schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
- Participation data: 2022 and earlier from NFL NGS (discontinued mid-2023); 2023 onward from FTN and updated only "after all post-season games are completed". [nflverse data schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html); [nflreadr NEWS / search snippet](https://cran.r-project.org/web/packages/nflreadr/news/news.html)
- Participation fields: offense_players (gsis_id list of every offensive player on the field), route (route of the primary receiver: CORNER, GO, SLANT, etc.), was_pressure, time_to_throw, defense_coverage_type (COVER_0..COVER_9, COMBO, BLOWN). ngs_air_yards is legacy through 2023; use pbp air_yards from 2024. [nflreadr participation dictionary](https://nflreadr.nflverse.com/articles/dictionary_participation.html)
- FTN charting and all-22 participation data (player participation and route data, coverages, pressure) exist back to 2019 as a commercial product. [FTN Data](https://ftnfantasy.com/stats/sports-data)
- PFR snap counts in nflverse start in 2012, game level. [load_snap_counts](https://nflreadr.nflverse.com/reference/load_snap_counts.html)
- FantasyPoints Data (Data Suite 2.0, paid) offers snap counts, route participation, and team-share denominators based on games the player was actually on the field for. [FantasyPoints Data](https://fantasypointsdata.com/)
- PFF Pro ($199.99) includes an API and CLI; PFF+ does not include API access; B2B via b2b.pff.com; CSV downloads available in Premium Stats. [PFF developer](https://developer.pff.com/); [PFF support](https://profootballfocussupport.zendesk.com/hc/en-us/articles/32094827302163-Does-API-access-come-with-a-subscription); [PFF pricing](https://www.pff.com/subscribe)
- FantasyPros API is free for personal/non-commercial use (HOF members get production keys) with rankings, projections, news, injury data. [FantasyPros API](https://www.fantasypros.com/api-data/)
- RotoWire publishes TE route data pages (paid site). [RotoWire](https://www.rotowire.com/football/te-route-data.php)

### Inferences
- For in-season role detection with zero cost: snap share (PFR via nflverse) + target share and air yards share (pbp) + depth-chart timestamp changes + injury status are all available within roughly 12-24h of the game. A route-participation proxy can be built as (team dropbacks while on field) only if participation is available, which it is not in-season; so use snap share x team pass rate as a cheap proxy and treat route data as a paid upgrade.
- FTN read_thrown (first-read targets) lands within 48h and is free, making "first-read target share" a realistic free in-season feature from 2022+.
- The depth-chart ISO8601 timestamps allow detecting when a role change was published, which matters for aligning features to line timestamps (avoiding lookahead).
- Licensing: FTN via nflverse is CC-BY-SA 4.0; share-alike could apply to derived data published publicly on the app. Paid sources (PFF, FantasyPoints) likely prohibit redistribution; not verified.

### Gaps
- Could not confirm nflverse licensing for PFR snap counts or NGS (scraped sources, terms unclear).
- No verified pricing found for FantasyPoints Data, Sports Info Solutions, or FTN's commercial API.
- No quantitative study found measuring how much route participation improves prop prediction over snap share.

## Q2. Which de-vig method is most accurate for NFL props and sides, and how much does sharp-book weighting help?

### Takeaway
The best peer-reviewed comparison (Clarke, Kovalchik & Ingram 2017) finds the power method universally beats multiplicative and matches or beats Shin; practitioner sources agree multiplicative is fine for near-symmetric two-way markets and that Shin/power matter more for lopsided prices. No NFL-props-specific de-vig accuracy study was found. The bigger lever is source choice: sharp-book (Pinnacle-type) closing prices track realized outcomes ~1:1, and consensus of many books can itself beat individual books.

### Cited Findings
- Clarke, Kovalchik & Ingram (Am. J. Sports Science 2017) compared additive, normalization (multiplicative), Shin, and power across three large datasets in different sports: "the power method universally outperforms the multiplicative method and outperforms or is comparable to the Shin method." Additive can produce negative probabilities; multiplicative ignores favorite-longshot bias. [Semantic Scholar](https://www.semanticscholar.org/paper/Adjusting-Bookmaker%E2%80%99s-Odds-to-Allow-for-Overround-Clarke-Kovalchik/713d3cb2e10dec3183ea5feced45bb11097fe702); [PDF via Outlier](https://outlier.bet/wp-content/uploads/2023/08/2017-clarke-adjusting_bookmakers_odds.pdf)
- Practitioner guidance: multiplicative sufficient for most two-way markets; Shin or power more accurate for multi-way markets with longshots; power sits between multiplicative and Shin in FLB correction. [Bet Hero](https://betherosports.com/blog/devigging-methods-explained); [Outlier devig comparison](https://help.outlier.bet/en/articles/8208129-how-to-devig-odds-comparing-the-methods); [Pinnacle Odds Dropper 4 methods](https://www.pinnacleoddsdropper.com/guides/how-to-devig-pinnacle-s-odds-for-betting-on-soft-books)
- Data Golf (golf, 106,204 matchups, 11 books, 2019-2020): Pinnacle shows a "roughly 1 to 1" relationship between expected and realized ROI; Betcris openers add value; DraftKings and Bet365 modest; 5Dimes/Bovada mostly copy. Optimal blend of their model and books was about 45/55, shifting to 60-65% model in 2020. When Pinnacle and Betcris differed by 5%+, Pinnacle closing moved 54.7% toward Betcris's opener vs 15.6% the other way. [Data Golf](https://datagolf.com/how-sharp-are-bookmakers)
- Buchdahl recommends Pinnacle as the closing-line reference ("the most accurate sportsbook"). [Pinnacle Odds Dropper / Buchdahl](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- Kaunitz, Zhong & Kreiner: consensus of many bookmakers' odds identifies mispriced books; profitable in 10-year closing-odds simulation, 6-month minute-level simulation, and 5 months of real money; ROI 3.5% to 9.9%; winning accounts were restricted. [arXiv 1710.02824](https://arxiv.org/abs/1710.02824)
- For props there is "no single sharp book" comparable to sides/totals; Caesars and FanDuel described as the most efficient US prop books; FanDuel originates independent prop lines and runs price discovery at modest opening limits; Caesars took $500+ on openers and moves aggressively on action. [Establish The Run](https://establishtherun.com/understanding-the-current-ecosystem-of-nfl-player-props/)
- Exchanges: Novig and ProphetX are available via aggregators (The Odds API added Novig and ProphetX as "us_ex" region; OpticOdds, SportsGameOdds, OddsPapi, SharpAPI, Betstamp also carry them). ProphetX has a closed API with no public developer portal; Novig has limited account-holder API only. [The Odds API on X](https://x.com/The_Odds_API/status/1869163198844428652); [OddsPapi ProphetX](https://oddspapi.io/blog/prophet-exchange-api-us-regulated/); [SportsGameOdds Novig](https://sportsgameodds.com/bookmakers/novig-odds-api)
- Kalshi API rate limits: Basic tier 200 read / 100 write tokens per second (higher tiers up to 12,000 read). [Kalshi docs](https://docs.kalshi.com/getting_started/rate_limits)
- Kalshi lists NFL player markets (passing/rushing/receiving yards, receptions, passing and anytime TDs) as binary contracts, mostly for star players. [SI](https://www.si.com/prediction-markets/reviews/kalshi-nfl)

### Inferences
- For NFL sides/totals at roughly -110/-110 the choice of de-vig method changes fair probability by well under 1 point; it matters on skewed prop prices (e.g. -150/+120) and anytime-TD longshots, where power (or Shin) should be default. Implementing power in stdlib is a 1-D root find (bisection on k such that sum p_i^k = 1).
- Sharp weighting > method choice. A reasonable weighting order for NFL sides: Pinnacle/Circa/BookMaker and exchanges (Kalshi/Novig/ProphetX when liquid) above FanDuel/Caesars above copy-books; for props, weight FanDuel/Caesars/exchange and down-weight DFS pick'em apps (flat-priced). Weights should be fitted (e.g. minimize log-loss vs outcomes, or vs Pinnacle close) rather than guessed, mirroring Data Golf's approach.
- Kalshi prices are fee-bearing and thin on props; treat mid-price with a liquidity gate.

### Gaps
- No NFL-specific (sides or props) empirical comparison of de-vig methods found.
- No quantitative estimate found of the fair-price improvement from sharp weighting in NFL props specifically (Data Golf evidence is golf).
- Pinnacle and Circa API access for a free app not researched here; Pinnacle closed its public API to most users (not verified in this session).

## Q3. Market-implied vs model-based prop distributions; is "market fair value + small model adjustment" dominant?

### Takeaway
Yes in practice: the leading public tools (Unabated) and sharp analysts treat the book's line as a median, build a full distribution (Poisson for counts, simulation for yards), and price alt lines off it; Data Golf's published blend weights books at ~55% vs model ~45%. The main documented model error is using means where books post medians, which biases toward overs on right-skewed stats.

### Cited Findings
- Sportsbooks set prop lines at the median; NFL stats are right-skewed so mean > median; using DFS mean projections systematically overbets overs; Unabated converts means to medians via 10,000-run simulation. [Unabated](https://unabated.com/post/the-biggest-mistake-youre-making-when-betting-nfl-player-props)
- Unabated Props Simulator runs 10,000 Monte Carlo sims to produce fair prices at every half-point for main and alt lines; receptions priced via Poisson. [Unabated Props Simulator](https://unabated.com/post/learn-about-the-props-simulator); [Unabated tool page](https://unabated.com/tools/core/props-simulator)
- Unabated offers an Alt Lines Calculator for pricing alternates from a main line. [Unabated](https://unabated.com/tools/calculators/alt-lines-calculator)
- Optimal model/book blend ~45/55 (golf). [Data Golf](https://datagolf.com/how-sharp-are-bookmakers)

### Inferences
- Recipe for Vault: (1) de-vig main line with power to get P(over); (2) fit a 1-2 parameter distribution (Poisson for receptions/TDs; normal or gamma/lognormal for yards) whose median and P(over at line) match; when alt-line ladders are available, fit the shape to multiple (line, prob) points by least squares; (3) apply the model only as a shift (e.g. role-change multiplier on the volume component) and shrink toward market with a fitted weight. This fixes the "role change misread" by letting the market carry baseline and the model carry only fresh usage info.
- Alt-line ladders carry heavier hold at the tails; de-vig each rung or anchor to the main line.

### Gaps
- No published head-to-head accuracy comparison of market-implied vs model distributions for NFL props was found.

## Q4. Documented signals that predict line movement

### Takeaway
Evidence is strongest for (a) sharp-book openers disagreeing with the market (the sharper book moves toward the independent originator far more than vice versa), (b) consensus disagreement (an outlier book vs consensus), and (c) early-week softness in props that sharpen by Thursday/Friday. Injury and weather are widely cited but I found no rigorous public quantification for NFL props.

### Cited Findings
- When two independent books differ by 5%+, the market-leading book's close moves 54.7% toward the other's opener (70.2% at 15%+ gaps). [Data Golf](https://datagolf.com/how-sharp-are-bookmakers)
- Outlier odds vs a many-book consensus predict value (and by implication movement toward consensus). [Kaunitz et al.](https://arxiv.org/abs/1710.02824)
- Caesars moves aggressively on incoming prop action, making it a useful movement detector. [Establish The Run](https://establishtherun.com/understanding-the-current-ecosystem-of-nfl-player-props/)
- Academic NFL work exists on intra-week efficiency of spreads (Miller & Rapach 2013) and holdover bias (Fodor et al. 2013). [search result listing, UNI thesis](https://scholarworks.uni.edu/cgi/viewcontent.cgi?article=1538&context=hpt)
- Recreational bettors lean overs on props; unders on rushing yards hit at a higher raw rate (not necessarily profitable). [OddsIndex](https://oddsindex.com/guides/nfl-player-props-guide) (practitioner, lower quality)

### Inferences
- Cheap signals to log per prop snapshot: distance of each book from power-devigged consensus; whether FanDuel/Caesars moved first; exchange (Kalshi/Novig) mid vs sportsbook consensus; depth-chart/injury timestamp changes preceding moves.

### Gaps
- No quantified NFL studies found on injury-news or weather effects on line movement magnitude/timing.

## Q5. CLV evaluation methodology and sample size

### Takeaway
CLV has about one tenth the per-bet standard deviation of win/loss results (approx 0.1 vs 1.0 at even money), so a consistent CLV edge can be shown in tens to low hundreds of bets, while proving profit from results takes thousands. Beating the close by X% implies roughly X% expected value if the close is efficient; that assumption is weaker for props, which lack a sharp reference book.

### Cited Findings
- Per-bet SD of even-money P/L ~1.00 vs CLV ~0.1; a consistent 5% CLV might need only ~50 bets for significance vs several thousand for P/L. Example: 952 bets, 756 shortened, mean 3.94%; ~65 bets would have sufficed. Beating the close by 5% implies ~5% expected value. [Buchdahl via Pinnacle Odds Dropper](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- Use Pinnacle's close as the reference. [same](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)

### Inferences
- Rough rule (t = 2): n ~ (2 x SD / mean CLV)^2. With SD 0.1: 5% CLV needs ~16 bets, 3% ~44, 2% ~100, 1% ~400. Real prop CLV SD is likely larger (bigger moves), so measure it empirically from Vault's own settled picks.
- Measure CLV in probability space against the power-devigged consensus close (or sharpest available book), not against the same book's close, and report Brier/log-loss of Vault probabilities alongside the de-vigged close's Brier/log-loss on the same bets; the model is only "sharper" if it beats the close on log-loss, not just on hit rate.

### Gaps
- No source found giving CLV variance specifically for NFL props, or validating CLV-to-ROI for props.

## Q6. Timing: prop openers, sharpening, injury windows

### Takeaway
Headline NFL props post early in the week with game lines; full menus fill by Thursday/Friday after injury reports; early-week lines are softest and late-week numbers sharpest. Limits start low and rise toward kickoff.

### Cited Findings
- Headline props post early week; deeper menus by Thursday/Friday once injury reports firm up; late-week numbers are sharpest; many profitable bettors do most volume in the first 48h after open. [ParlaySavant](https://www.parlaysavant.com/insights/how-to-research-nfl-player-props); [DawBets](https://dawbets.com/sports/nfl) (practitioner sources, moderate reliability)
- FanDuel opens props at modest limits that improve closer to game time. [Establish The Run](https://establishtherun.com/understanding-the-current-ecosystem-of-nfl-player-props/)

### Inferences
- Snapshot cadence should be denser at open (Tue/Wed), around injury-report releases (Wed-Fri afternoons), and in the 90-minute pre-kickoff inactive window; nflverse injury data refreshes only at 7AM UTC daily, too slow for the final windows, so the Sleeper injury feed remains the fast signal.

### Gaps
- No primary source fetched for official NFL injury report times (practice reports Wed-Fri, final game-status designations, inactives ~90 min before kickoff); these are standard NFL policy but unverified here.
- No quantitative measure found of how fast prop lines converge (e.g. % of open-to-close move completed by day).
