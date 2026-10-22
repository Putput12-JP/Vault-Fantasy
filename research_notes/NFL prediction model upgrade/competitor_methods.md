# Competitor Methods and Track Records: NFL Prop and Game-Line Prediction Products (2023-2026)

Research date: 2026-09-28. About 22 search and fetch calls. Every record below is **self-reported by the vendor** unless it is explicitly marked otherwise. I found **no independently audited (third-party, timestamped, CLV-verified) record for any product covered.** That absence is the main finding.

## Q1. What core method does each product use?

### Takeaway
The products fall into three camps:
1. **"No-model" market tools.** OddsJam, Unabated, Outlier's +EV feed, and the pick'em optimizers. They de-vig sharp books (Pinnacle, Circa, Bookmaker) or a consensus into a "fair" price, then flag soft-book or DFS lines that beat it.
2. **Proprietary projections compared to the line.** Action PRO (Koerner), ETR, PFF Greenline, BettingPros, 4for4, Dimers, Warren Sharp, Rithmm, Leans.ai.
3. **Pure research dashboards with no model.** Props.Cash, and Outlier's hit-rate views.

Only camp 1 has a mechanism that works by construction, not by claim.

### Cited Findings

**OddsJam (market-based +EV)**
- The EV tool looks for large discrepancies between a sportsbook's odds and a sharp book such as Pinnacle, or a market consensus. It flags a bet as +EV when a book beats the fair value. — [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)
- OddsJam's filters require a bet to be +EV against the no-vig fair odds of "a variety of sharp bookmakers," with Pinnacle as the reference sharp book. — [OddsJam: how +EV filters work](https://oddsjam.com/betting-education/how-do-positive-ev-sports-betting-filters-work); [OddsJam Positive EV tool](https://oddsjam.com/betting-tools/positive-ev)
- OddsJam publishes guidance on using "market width" (vig size) as a quality filter on the fair line. — [OddsJam: market width](https://oddsjam.com/betting-education/market-width)
- OddsJam also runs a fantasy/pick'em optimizer for PrizePicks. — [OddsJam Fantasy Optimizer](https://fantasy.oddsjam.com/fantasy-odds/prizepicks)

**Unabated (market-based, weighted sharp consensus)**
- The "Unabated Line" is a vig-free blend of market-making books, "curated on a sport-by-sport basis."
  - Weights go to "books [that] reach the closing line the fastest."
  - The weights are proprietary.
  - Unabated makes no accuracy or CLV claim for the line itself.
  - [Unabated: What is the Unabated Line](https://unabated.com/post/what-is-the-unabated-line)
- The model adjusts weighting per sport and per market type, because the sharpest book on NFL spreads may not be the sharpest on props. The tracked books include Bookmaker, Circa, and Pinnacle. — [XCLSV Unabated review](https://xclsvmedia.com/unabated-review-2026-premium-sharp-bettor-tool-worth-it/); [Unabated Line tool page](https://unabated.com/tools/core/unabated-line)
- Unabated recommends a "Top Down" approach: treat a sharp line as the source of truth and pick off better prices elsewhere. — [Unabated Line tool page](https://unabated.com/tools/core/unabated-line)
- Unabated has a pick'em entry builder for PrizePicks and Underdog. It shows the per-pick edge, the hit probability, and the overall entry edge. — [Unabated DFS pick'em](https://unabated.com/nba/dfs)

**Outlier (hit rates plus a +EV feed)**
- Outlier pulls odds from sportsbook APIs. Its "traffic light" hit rates are green at 65%+, yellow at 45-65%, and red below 45%. The windows are the last 5 and 10 games, vs. the opponent, this season, and last season. — [XCLSV Outlier review](https://xclsvmedia.com/outlier-review/); [Outlier help: Prop Finder](https://help.outlier.bet/en/articles/6711738-research-player-propositions-with-outlier-s-prop-finder)
- The +EV feed (Premium+/Pro tiers) shows EV, vig, a Kelly stake, no-vig odds, and best odds. That makes it the same de-vig approach as OddsJam, layered on top of the hit-rate research. — [XCLSV Outlier review](https://xclsvmedia.com/outlier-review/)

**Props.Cash (research only)**
- Props.Cash is a research dashboard.
  - For each prop it shows a bar chart of the last 5, 10, and 20 games plus the season against that exact line, with the implied probability overlaid.
  - It compares the historical hit rate to that implied probability.
  - Reviewers say it has no +EV or arbitrage function, and "the strategy part is on you."
  - [Picks & Parlays review](https://picksandparlays.net/reviews/ai-picks/props-cash); [BetSmart review](https://www.betsmart.co/tool-reviews/props-cash)

**Action Network PRO (projections plus sharp-money signals)**
- The NFL prop projections come from Sean Koerner. An "Edge" column shows the projection's advantage over the book price. — [BetSmart Action PRO review](https://www.betsmart.co/tool-reviews/action-network-pro); [Action Network prop projections](https://www.actionnetwork.com/nfl/prop-projections)
- Koerner's credential is **projection/ranking accuracy, not betting ROI**. He ranked #1 on FantasyPros in 2015, 2016, 2017, and 2023, and won 4 FSTA awards for projection accuracy. — [Muck Rack / Action Network bio summary](https://muckrack.com/sean-koerner)
- The Sharp Report and PRO Report infer "sharp action" from the gap between bet % and money %, plus line movement. "PRO Systems" are angles mined from the Bet Labs historical database. — [Action Network PRO Report explainer](https://www.actionnetwork.com/nfl/nfl-pro-report-sharp-action-betting-systems-model-projections-expert-picks); [Action Network help: identifying public money](https://actionnetworkhq.zendesk.com/hc/en-us/articles/360022406891-Identifying-public-money)

**PFF Greenline (model on PFF grades and player data)**
- Greenline gives model projections for spread, moneyline, and total from "exclusive game and player data," and shows where the model finds value against the market. — [PFF Greenline NFL](https://www.pff.com/greenline/nfl); [PFF Greenline intro](https://www.pff.com/news/pro-pff-greenline-introduction)
- PFF also sells a player-prop tool under PFF+. — [PFF player props tool](https://www.pff.com/betting/player-props)

**Establish The Run (ETR; proprietary projections and simulation)**
- In ETR's words, the method is "statistical models plus simulations we've built in tandem with a unique understanding of player usage and coaching tendencies... part math, part football, and part gambling knowledge." It reuses their fantasy projection stack. — [ETR In-Season NFL Props FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)
- ETR admits "Lines typically move within a few seconds to 30 seconds after we release a play." They tell subscribers to fund FanDuel, DraftKings, Caesars, BetMGM, ESPNBet, BetRivers, Circa, and others. — [ETR FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)

**BettingPros / FantasyPros**
- Every prop gets a BettingPros projection, plus Cover Probability %, Expected Value, and a 1-5 Star Rating (the latter three are premium). The models use the same projections behind FantasyPros rankings. — [BettingPros help: Prop Bet Analyzer](https://support.bettingpros.com/hc/en-us/articles/7729846650011-What-is-the-Prop-Bet-Analyzer); [BetSmart BettingPros review](https://www.betsmart.co/tool-reviews/betting-pros)
- BettingPros launched PrizePicks and Underdog optimizers that "show the real odds behind every payout" and grade picks against the market. That is a market-based approach, separate from their projections. — [BettingPros optimizer launch](https://www.bettingpros.com/articles/bettingpros-launches-new-prizepicks-and-underdog-optimizers/)

**Dimers (simulation)**
- Dimers simulates each NFL game 10,000+ times with a proprietary ML model. Inputs: team performance, matchup history, coaching trends, injuries, weather, and pace. It outputs win, cover, and total probabilities. — [Dimers NFL picks](https://www.dimers.com/nfl/picks); [Dimers best props](https://www.dimers.com/best-props/nfl)

**Warren Sharp / Sharp Football Analysis**
- Sharp markets a "computer model" for NFL totals, "with a 20-year track record." No model mechanics are published. — [Sharp Football lifetime records](https://www.sharpfootballanalysis.com/lifetime-betting-records/)

**Rithmm (user-built ML models)**
- Rithmm is a custom model builder: users weight factors themselves. Reviewers call it "a modeling tool, not a verified track record service." — [Picks & Parlays Rithmm review](https://picksandparlays.net/reviews/ai-picks/rithmm); [PropsBot Rithmm review](https://propsbot.ai/rithmm-review/)

**Leans.ai ("Remi" AI picks)**
- Remi is a proprietary predictive model. The marketing claims a long-run 53-58% ATS. — [XCLSV AI handicappers review](https://xclsvmedia.com/ai-sports-handicappers-2026-leans-rithmm-sportbot-vs-human-cappers/); [Leans.ai](https://leans.ai/)

**4for4 and Fantasy Life+**
- 4for4 props are an analyst column (Connor Allen) built on projections. — [4for4 Week 8 2024 props](https://www.4for4.com/2024/w8/week-8-nfl-player-prop-bets-best-player-props-bet-connor-allen)
- Fantasy Life has an NFL Prop Bet Finder. I could not retrieve a methodology page for it. — [Fantasy Life Prop Bet Finder](https://www.fantasylife.com/tools/prop-bet-finder)

**Pick'em optimizers (Props Made Easy, Daily Fantasy Fuel, Upside, OddsJam Fantasy, Unabated, BettingPros)**
- All of them are market-based. They compare PrizePicks and Underdog fixed lines to consensus sportsbook odds (Props Made Easy says 100+ books) and flag picks whose implied probability clears the payout's break-even. — [Props Made Easy](https://www.propsmadeeasy.com/prizepicks-optimizer); [Daily Fantasy Fuel](https://www.dailyfantasyfuel.com/prizepicks-optimizer/); [Upside](https://upside.tools/tools/optimizer/prizepicks)
- Even the best pick'em payout structure needs about 54% per-pick accuracy to break even. — [OddsShopper PrizePicks cheat sheet](https://www.oddsshopper.com/articles/betting-101/prizepicks-cheat-sheet-today)

### Inferences
- The industry has split. Tools sold to "sharp" bettors (OddsJam, Unabated, the +EV tiers of Outlier, the pick'em optimizers) **do not predict football**. They assume the sharp closing market is the best estimate and profit only from other books being slow or flat-priced.
  - This matches Vault's own findings: the game model matches the market, and edge shows up only on a gated subset.
  - Competitors treat "matching the market" as the fair line, not as a failure.
- Among projection shops, only ETR, Action (Koerner), and PFF have strong football-usage data. Even they position props as "projection vs line," which works only where books are softest (props, alt lines, pick'em).
- "Simulated 10,000 times" (Dimers) is a presentation device. A simulation adds nothing unless the inputs and correlations beat the market.
  - This is consistent with Vault's MC game-sim spike, which found game-market MC equal to the closed form.

### Gaps
- No public methodology for numberFire/FanDuel Research, the Fantasy Life+ prop finder internals, or the PFF prop tool's model. Searches returned product pages only.
- Unabated and OddsJam do not publish the book weights or de-vig method (multiplicative, power, or Shin) per market.

## Q2. Which products publish tracked results, and what do the records show?

### Takeaway
The vendors that publish NFL records are ETR, Warren Sharp, Leans.ai, 4for4, and PFF (2022). **All of these records are self-reported on the vendor's own site.** None I found carries third-party timestamping, closing-line value (CLV), or an audit. The market-tool vendors (OddsJam, Unabated, Outlier) publish **no aggregate user results at all**.

### Cited Findings

**ETR NFL in-season props.** Self-reported. This is the longest and most granular record I found. [ETR FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)

| Season | Bets | Record | Profit | ROI |
|---|---|---|---|---|
| 2019 | | 50-36 | +$963 | |
| 2020 | | 55-34 | +$1,907 | |
| 2021 | | 216-118 | +$8,572 | 22.1% |
| 2022-23 | | 308-222 | +$5,860 | 9.5% |
| 2023-24 | | 253-225 | +$267 | 0.48% (roughly breakeven) |
| 2024-25 | Straight | 228-158 | +$5,969 | 14.09% |
| 2024-25 | Alt/longshot | 38-222 | +$736 | 17.62% |
| 2025-26 | | 203-164 | +$2,405 | 6.03% |

- The FAQ does not say whether results are graded at the price when posted or at a price subscribers could actually get. It reports no CLV.

**Warren Sharp.** Self-reported. [Sharp Football lifetime records](https://www.sharpfootballanalysis.com/lifetime-betting-records/)

| Season | Overall | Computer totals | Props |
|---|---|---|---|
| 2023 | 340-260 (57%) | 38-23 (62%) | 43-21 (67%) |
| 2024 | 54-45 (55%) | 26-11 (70%) | 104-65 (62%) |
| 2025 | 63-49 (56%) | 20-11 (65%) | |

- The page shows no verification, odds tracking, or CLV.
- The marketing also claims 62.6% on 1,100+ NFL totals lifetime, and "19 winning seasons over 20 years." — [Sharp Football](https://www.sharpfootballanalysis.com/)
- The "overall" samples swing from 600 picks (2023) to about 100 picks (2024), so the scopes are clearly not comparable year to year.

**Leans.ai / Remi.** Self-reported. [Leans.ai past performance](https://leans.ai/past-performance/)
- NFL: 123-100 (55.2%), "192.7 net units," $19,268 at $100 per unit.
- The "Executive Level" tier shows 234-191 (55.1%) and 89.9 units.
- The tracking start is September 1, 2022.
- The page calls these figures "ESTIMATIONS ONLY" and "self-reported."

**4for4 (Connor Allen props, 2024).** Self-reported, partial season.
- 51-32 (61.45%) for +15.61 units through Week 8.
- 65-40 and "over 20 units" through Week 9.
- [4for4 Week 8](https://www.4for4.com/2024/w8/week-8-nfl-player-prop-bets-best-player-props-bet-connor-allen); [4for4 Week 10](https://www.4for4.com/2024/w10/week-10-nfl-player-prop-bets-best-player-props-bet-connor-allen)
- I found no full-season or multi-season total.

**PFF Bet.** Self-reported, and old.
- 2022 first quarter of the season: 177 staff picks, including 115 player props, at a 10.52% ROI.
- An earlier season's model column went 49-37-5 (57.0%).
- [PFF Betting 2022 Q1 recap](https://www.pff.com/news/betting-2022-first-quarter-recap-reflections); [PFF Greenline intro](https://www.pff.com/news/pro-pff-greenline-introduction)
- I found no 2023-2026 Greenline record.

**Action Network.**
- Action PRO lets users track their own bets and ROI (BetSync/BetScan). — [BetSmart Action PRO review](https://www.betsmart.co/tool-reviews/action-network-pro)
- I found no published aggregate record for Koerner's prop projections or for the "Edge" column (searched specifically for 2024 units; nothing turned up). — [Action Network Koerner author page](https://www.actionnetwork.com/article/author/sean-koerner)

**Rithmm.** The sources conflict.
- One review says Rithmm "does not publish official accuracy rates or audited ROI figures." — [Picks & Parlays](https://picksandparlays.net/reviews/ai-picks/rithmm)
- Other copy claims a live board "with a verified track record... every pick logged publicly." — [search summary citing Rithmm review sites](https://oddsplays.com/reviews/rithmm/)
- App-store user reviews are mixed. Some report +24 units in NBA; others call the predictions "atrocious" across MLB, WNBA, NBA, and CFB, with negative ROI on custom models. — [App Store reviews](https://apps.apple.com/us/app/rithmm-ai-sports-betting/id1641010681?see-all=reviews&platform=iphone)

**Dimers.** I found no published historical ROI. Their pages describe the method only. — [Dimers NFL picks](https://www.dimers.com/nfl/picks)

**OddsJam, Unabated, Outlier, Props.Cash.** I found no aggregate performance record for any of them.
- Unabated explicitly makes no accuracy or CLV claim for its line. — [Unabated](https://unabated.com/post/what-is-the-unabated-line)
- Their "proof" is structural: +EV against a de-vigged sharp price.

**Pikkit.** Pikkit is the nearest thing to neutral tracking.
- It is a user bet tracker that syncs to sportsbook accounts and computes each user's CLV%.
- It frames positive CLV over hundreds of bets, or beating the close on 60-65%+ of 200+ bets, as evidence of real edge.
- It does not publish vendor-level audits.
- [Pikkit CLV](https://pikkit.com/closing-line-value); [Pikkit: How to Track CLV](https://pikkit.com/blog/how-to-track-closing-line-value-clv-in-sports-betting)

### Inferences
- **The Leans.ai numbers don't add up.**
  - 123-100 at standard -110 flat stakes comes to roughly +10 units, not 192.7.
  - The unit total therefore implies variable staking or odds not disclosed on the page.
  - Treat this as a marketing figure.
- **ETR's record is the most credible of the set,** because it is multi-year, includes a near-breakeven year (2023-24: +0.48%), and gives W-L and dollar totals.
  - It still carries a major execution caveat: lines move within 5-30 seconds of release (ETR's own statement).
  - So the posted ROI is an upper bound on what subscribers actually achieve.
  - The alt/longshot line (38-222, +17.6%) shows that high variance on a small sample can dominate a season.
- **Warren Sharp's props record is strong on paper** (104-65 in 2024), but it is self-graded with no odds or CLV disclosed.
- Across the board, **a win % (W-L) reported without the odds taken and without CLV is not a verifiable edge claim.** The ETR 2023-24 year shows that a 53% hit rate at typical prop prices is about breakeven.
- For Vault's own Track Record, the verifiable standard none of these competitors meets would be: timestamped pick, price at pick, closing price, CLV, and graded ROI. Publishing that would be a genuine differentiator.

### Gaps
- No third-party audit found for any product: no Action Network expert-tracker export, no SportsMonitor-style verification, no public Pikkit leaderboard for these vendors.
- No ETR CLV figures.
- No 2023-2026 PFF Greenline record.
- No full-season 4for4 total.
- No Koerner betting ROI.
- No Reddit threads on Leans.ai's record surfaced in search. The existing criticism is on Trustpilot, which I did not fetch. — [Trustpilot Leans.ai](https://www.trustpilot.com/review/leans.ai)

## Q3. Which methods appear to work for users, and which are projection-based picks?

### Takeaway
The only approach whose edge is structural rather than asserted is **market-based +EV**: de-vig sharp books into a fair price, then bet soft books and pick'em apps that deviate from it, with line shopping. Its limit is account restriction, not model accuracy. Projection-based picks show positive self-reported records mainly **in props and totals**, not sides, and even the best (ETR) has had a flat year.

### Cited Findings
- The standard +EV workflow: compare soft-book odds to the no-vig fair odds from sharp books, and bet when the soft price beats fair. — [OddsJam walkthrough](https://oddsjam.com/betting-education/positive-ev-betting-walking-through-an-example); [Unabated top-down](https://unabated.com/tools/core/unabated-line)
- Unabated weights books by how fast they reach the closing number. That builds the de-vig reference toward the close, which is what CLV measures. — [Unabated](https://unabated.com/post/what-is-the-unabated-line)
- Winning bettors, EV bettors included, face stake limits and restrictions at US books. The usual mitigation is spreading action across many books. — [XCLSV free +EV tools](https://xclsvmedia.com/best-free-ev-betting-tools-in-2026-find-value-bets-without-paying-199-month/)
- NBA player props can be capped around $1,000, while NFL spreads may allow $5k-$20k. That caps how much any prop edge can be worth. — [Bleacher Nation max bets](https://www.bleachernation.com/betting/2025/10/17/maximum-bet-size/)
- Pick'em apps price every leg at a flat payout, so optimizers target legs where sharp odds imply well above about 54%. — [OddsShopper](https://www.oddsshopper.com/articles/betting-101/prizepicks-cheat-sheet-today); [BettingPros optimizers](https://www.bettingpros.com/articles/bettingpros-launches-new-prizepicks-and-underdog-optimizers/)
- Projection shops' records, as they themselves report them:
  - ETR props are positive in 6 of 7 seasons, but ROI swings from 22% to 0.5%.
  - Warren Sharp's positive numbers are concentrated in totals and props.
  - These are consistent with, but do not prove, the idea that projection edges exist mainly where books are softest.
  - [ETR FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/); [Sharp Football records](https://www.sharpfootballanalysis.com/lifetime-betting-records/)
- Historical hit-rate research (Props.Cash, Outlier traffic lights) presents last-N hit rates against implied probability. No product publishes evidence that last-N hit rate beats the line. — [Picks & Parlays Props.Cash](https://picksandparlays.net/reviews/ai-picks/props-cash); [XCLSV Outlier](https://xclsvmedia.com/outlier-review/)

### Inferences (for Vault)
1. **Copy the market-based layer as the default "fair" line.** Weight sharp books by speed-to-close, as Unabated describes. Treat Vault's own model as a filter or tiebreaker on props, not as the source of truth for game lines.
   - Vault already de-vigs per book, applies exchange fees, and has a Kalshi anchor, so this is close.
   - Vault's game model "matching the market" is exactly how Unabated positions its product.
2. **Pick'em mispricing is the highest-leverage free-user use case.**
   - The apps price flat, every major optimizer is market-based, and Vault's QB-WR correlation finding (+22% mispricing on same-team overs) goes beyond what the reviewed optimizers advertise.
   - None of the optimizer pages I saw mentions correlation.
3. **Last-N hit-rate displays are engagement features, not edge.** Don't sell them as predictive.
4. **Publish a verifiable record.** Price at pick, closing price, CLV, graded units. No competitor does this, so it is a credibility moat.

### Gaps
- No published study of aggregate user ROI or CLV from OddsJam, Unabated, or Outlier +EV users.
- No quantified data on how quickly soft books limit +EV bettors.
- No evidence found for or against pick'em optimizer profitability at scale.

## Q4. What weaknesses, criticism, or failed records are documented?

### Takeaway
The documented weaknesses fall into four groups:
- **Execution decay.** Lines move seconds after picks are posted.
- **Unverifiable or incoherent self-reported records.** Leans.ai's units vs. its W-L.
- **Research tools with no edge mechanism.** Props.Cash.
- **Mixed user results for "AI picks" apps.** Rithmm.

No vendor's record has survived an independent audit, because none has been audited.

### Cited Findings
- ETR: "Lines typically move within a few seconds to 30 seconds after we release a play." — [ETR FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)
- ETR's own 2023-24 props season was roughly breakeven: 253-225, +0.48% ROI. — [ETR FAQ](https://establishtherun.com/etr-in-season-nfl-props-faq/)
- Leans.ai labels its own metrics "ESTIMATIONS ONLY," self-reported, with no third-party verification or CLV. — [Leans.ai past performance](https://leans.ai/past-performance/)
- Some users question whether Leans.ai's advertised record is a fair representation. — [Trustpilot via search summary](https://www.trustpilot.com/review/leans.ai)
- Rithmm users report custom models producing negative ROI regardless of adjustments. — [App Store reviews](https://apps.apple.com/us/app/rithmm-ai-sports-betting/id1641010681?see-all=reviews&platform=iphone)
- Props.Cash has no +EV function, and a recent redesign drew complaints about UI, missing features, and performance. — [BetSmart Props.Cash](https://www.betsmart.co/tool-reviews/props-cash); [Sportsbook Scout](https://www.sportsbookscout.com/sportsbook-reviews/props-cash-review)
- +EV bettors risk limits and restrictions at US books. — [XCLSV](https://xclsvmedia.com/best-free-ev-betting-tools-in-2026-find-value-bets-without-paying-199-month/)
- Warren Sharp's records page discloses no verification method, odds, or CLV. — [Sharp Football records](https://www.sharpfootballanalysis.com/lifetime-betting-records/)

### Inferences
- Treat any W-L record without prices, timestamps, and CLV as marketing.
- **Marketing claims** (unverified): Leans.ai's 53-58% ATS, Warren Sharp's 62.6% totals, Koerner's "most accurate" label (which is about fantasy projections, not betting), and Dimers' "10,000 simulations."
- **Self-reported but granular** (more credible, still unaudited): ETR's yearly table, and PFF's 2022 quarter.
- **Verifiable**: none found.

### Gaps
- Could not access Reddit threads directly. Reddit-sourced claims here come secondhand via review sites.
- No verified exposé or regulatory action against any of these vendors was found.
