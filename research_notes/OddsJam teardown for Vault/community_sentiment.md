# OddsJam Community and User Sentiment (researched 2026-09-26)

Method note: Reddit could not be reached. WebSearch refuses reddit.com as a domain (the crawler is blocked) and WebFetch cannot fetch www.reddit.com, so **no Reddit threads were read directly**. Reddit and forum sentiment below comes only from secondary sources that summarize it, and is labeled that way. Trustpilot, the Apple App Store, review blogs, SEC/trade press and GitHub (through the `gh` CLI) were read directly. Google Play would not render.

## 1. Recurring praise and complaints (Reddit, forums, reviews)

### Takeaway
Sentiment splits into two camps: users who say they made $10K-$80K+, and users angry about billing after a free trial, refusals to refund, lines that were stale or wrong, and getting limited quickly. On review sites the complaints are about the business (billing, support, price), not the core math. The most requested thing is a cheap "lines only" tier.

### Cited Findings
- Trustpilot (read directly, Sep 2026): **2.7/5 from 95 reviews**, 40 of them in the last 12 months. The split is bimodal: 43% 5-star, 50% 1-star, only about 7% in between. The page showed no company replies and the profile looked unclaimed. — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com)
  - Conflict: a search-engine snippet reported "4.4/5 from 85+ reviews", probably an older snapshot or a regional aggregate. Treat 2.7 as current. — [Trustpilot search snippet](https://www.trustpilot.com/review/oddsjam.com)
- Recent Trustpilot complaints (2026), quoted:
  - "Cancelled subscription before free trial...still charged me" (Jul 16, 2026)
  - "OddsJam consistently displays inaccurate lines" (May 19, 2026)
  - "You get limited almost instantly when betting real money" (Apr 1, 2026)
  - "There is no phone support...only a chat box" (May 19, 2026)
  - "Every play that they give out is wrong" (Apr 29, 2026)
  — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com)
- 2025 Trustpilot page: a "Charged $199 after cancellation" review (Aug 2025), a complaint about "Non-real-time odds" (May 2025), "Signed up for year plan without consent" (May 2025), and a user asking for a "simple $10-14 membership for just lines/odds" (Jun 2025). Mixed in are 5-star reviews claiming $12K in a first month and $20K+ in 2.5 months. Several of those name individual support reps (e.g., "Randall and Billy C"), which suggests solicited reviews; this is inference, not a verified flag. — [Trustpilot UK p.3](https://uk.trustpilot.com/review/oddsjam.com?page=3)
- Praise: "I've personally profited more than $80K since starting in OCT 24" (Apr 2025); "tools and data are top in the industry." — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com)
- **bet365 was removed from the platform with no warning.** One user bought a roughly $3,000 annual plan on a discount offered about a week before the removal, and got no refund or credit; support cited the Terms of Service. — [Trustpilot (via search summary)](https://www.trustpilot.com/review/oddsjam.com)
- International users call it "extremely costly and unusable" outside the US, because the books and markets covered are US-centric. A European user reports a surprise charge of about 630 EUR months after a trial. — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com); [UK Trustpilot](https://uk.trustpilot.com/review/oddsjam.com?page=3)
- Review-blog summary of user complaints: "lots of people just need the lines & not the extra stuff"; "poor customer support and a lot to learn at the start"; "not great for non US users"; tiers are "complex and not well designed." — [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)
- Secondary sources on community (r/sportsbook-type) sentiment: limiting is described as "an eventual reality" for serious +EV bettors, and the tool pays for itself only at roughly $1,000+/week of handle. These are review-site characterizations, not quoted Reddit posts. — [XCLSV review](https://xclsvmedia.com/oddsjam-review-2026-is-this-ev-sports-betting-tool-worth-it/)
- Positioning against competitors (review sites):
  - Unabated is called "the gold standard" for fair lines among sharps, at about $199/mo.
  - Outlier costs about $99/mo against OddsJam's $199 Gold. Its advice: use OddsJam only at 30+ bets a week across 4+ books, and everyone else should start with Outlier.
  — [XCLSV Unabated](https://xclsvmedia.com/unabated-review-2026-premium-sharp-bettor-tool-worth-it/); [OddsPlays OddsJam vs Outlier](https://oddsplays.com/us/betting-tools/oddsjam-vs-outlier/); [BetSmart](https://www.betsmart.co/comparison-tool/outlier-vs-oddsjam)
- Free alternative: Crazy Ninja Odds runs a free Positive EV / de-vig tool. — [CrazyNinjaOdds](https://crazyninjaodds.com/site/tools/positive-ev.aspx)
- A competitor's "alternatives" roundup (written by a ValueBetFactory co-founder, so biased) calls OddsJam "the tool most bettors benchmark others against." It lists RebelBetting, Trademate, BetBurger and Surebet as alternatives, and says free scanners lack "speed, customisation, and reliability." — [ValueBetFactory](https://valuebetfactory.com/betting-education/oddsjam-alternatives)

### Inferences
- The recurring anger is about **billing and trust**: charges after a trial, surprise annual plans, no refunds, a book removed mid-subscription. Being transparent (one-click cancel, prorated refunds, a notice when coverage changes) is cheap differentiation.
- The repeated wish for a **cheap lines-only / screen tier** points to an under-served price point well below $99. Vault already has a free-first stance and its own line consensus, and could take it.
- "Plays decrease in value after you take it" and "inaccurate lines" are the stale-line / false-positive complaint. Vault's own single-book guard and the checks it runs before a line gets a grade (priced-line pairing, real-book requirement) answer this directly and can be marketed.

### Gaps
- No direct Reddit quotes or thread links: reddit.com is blocked for this toolset. A follow-up with a browser session should pull r/sportsbook, r/sportsbetting, r/algobetting and r/PrizePicks threads.
- Could not confirm whether the Trustpilot profile is officially unclaimed, beyond what the page showed.
- No Covers or SBR forum threads surfaced in search.

## 2. App store ratings and YouTube

### Takeaway
The iOS app rates much higher (4.7 from about 2.3K ratings) than Trustpilot (2.7). App ratings skew toward engaged, paying users. The complaints on the App Store are the same ones as on Trustpilot.

### Cited Findings
- Apple App Store "OddsJam: Sharp Sports Betting": **4.7/5, about 2.3K ratings**. Praise covers fast odds updates and real-time comparison; some users report $40K-$80K in profit. — [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108?see-all=reviews&platform=iphone)
- App Store complaints, quoted:
  - "charge you after you've canceled"
  - the Platinum price is "just outlandish"
  - plays "decrease in value after you take it"
  - limits arrive after 1-2 months of use
  — [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108?see-all=reviews&platform=iphone)
- The listing claims 100,000+ users; the app is free with in-app purchases. — [App Store listing](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- OddsJam hosts its own "Customer Reviews" playlist on YouTube, which is company-curated testimonial content. — [YouTube playlist](https://www.youtube.com/playlist?list=PLHJ-_Cm9SrApfTESXuRMfaNAOgk_KVhcW)

### Inferences
- The gap between the App Store and Trustpilot fits a pattern: in-app rating prompts reach happy active users, while churned or billed-after-cancel users go to Trustpilot.

### Gaps
- Google Play rating and review count could not be fetched (the page did not render). — [Google Play](https://play.google.com/store/apps/details?id=com.oddsjam.app&hl=en_US)
- No independent (non-OddsJam) YouTube review summaries were collected.

## 3. GitHub and open-source ecosystem (how commoditized is the core math?)

### Takeaway
The core math (de-vig, EV against a sharp book like Pinnacle, arbitrage) is thoroughly commoditized. There are dozens of small hobby repos, most built on The Odds API or scraping. None has broad adoption: the top project is about 300 stars. The moat is data (coverage, speed, number of books), not algorithms.

### Cited Findings (stars via `gh search repos`, 2026-09-26)
- **personal-coding/Live-Sports-Arbitrage-Bet-Finder**: 294 stars, updated Sep 2026. Live arb bot across FanDuel, DraftKings and others. The largest found. — [GitHub](https://github.com/personal-coding/Live-Sports-Arbitrage-Bet-Finder)
- **dos-2/oddshub**: 125 stars. Terminal UI for betting odds. — [GitHub](https://github.com/dos-2/oddshub)
- **dashee87/betScrapeR**: 67 stars. R odds scraper. — [GitHub](https://github.com/dashee87/betScrapeR)
- **kippfreud/Free_Arbitrage_Finder**: 38 stars. **LeartS/betbot**: 35 stars. **ratsam3474/autoarbitrage**: 35 stars, auto-places bets. — [GitHub](https://github.com/kippfreud/Free_Arbitrage_Finder); [GitHub](https://github.com/LeartS/betbot); [GitHub](https://github.com/ratsam3474/autoarbitrage)
- **odds-api/odds-api**: 30 stars. Vendor SDK advertising built-in arbitrage and "positive EV" examples, plus an MCP server for coding agents; the vendor also ships an arbitrage scanner bot repo. So data vendors now hand out the scanner as sample code. — [GitHub](https://github.com/odds-api/odds-api); [GitHub](https://github.com/odds-api/arbitrage-betting-scanner-bot)
- **roman-smith/oddsapi_ev**: 20 stars. **jrey999/mlb-positive-ev**: 12 stars. Both compute EV from The Odds API. Also **edge-scanner**, which finds EV against Pinnacle as the sharp reference. — [GitHub](https://github.com/roman-smith/oddsapi_ev); [GitHub](https://github.com/jrey999/mlb-positive-ev); [GitHub](https://github.com/DeliciousPipe1326/edge-scanner)
- Prediction-market arbitrage is an emerging niche: polymarket-sports-arbitrage (16 stars) and polymarket-sportsbook-arbitrage-agent (16 stars). — [GitHub](https://github.com/Dylanwu2025/polymarket-sports-arbitrage); [GitHub](https://github.com/arcofs/polymarket-sportsbook-arbitrage-agent)
- **OddsJam API wrappers** are tiny:
  - cooperbrandon1/oddsjam-api: 15 stars
  - the official oddsjam/api-python: 4 stars
  - scrapers and bots: joshniemela/oddsBot (8 stars), Sanju311/plusEV-odds-finder (5 stars), jakeflynn39/oddsjam-api-plus-ev-calculator (3 stars)
  The OddsJam B2B API has a small developer following. — [GitHub](https://github.com/cooperbrandon1/oddsjam-api); [GitHub](https://github.com/oddsjam/api-python); [GitHub](https://github.com/joshniemela/oddsBot)
- The `the-odds-api` GitHub topic has only 13 repos; the biggest relevant one is BetTrack (15 stars, an MCP server for Claude Desktop). ParlayAPI SDKs appear too. — [GitHub topic](https://github.com/topics/the-odds-api)

### Inferences
- A competitor gains nothing from copying the algorithm, since it is public and trivial. What cannot be copied is **line coverage, freshness, and the filtering that removes false positives**, plus trust and the user experience.
- The main input cost is odds-data licensing or scraping (see the legal risk in section 4). Vault's cost-bounded ParlayAPI budget is the real constraint, not the math.

### Gaps
- Commit activity and contributor counts were not examined; star counts only.

## 4. Controversies (limiting, legal, refunds, marketing)

### Takeaway
There are four: a $100M+ data-scraping lawsuit, ownership by an affiliate-marketing company (Gambling.com Group, whose revenue comes from referring bettors to sportsbooks), marketing through influencers paid per sale, and a pattern of disputes over trial billing.

### Cited Findings
- **Swish Analytics v. OddsJam and OpticOdds**, San Francisco Superior Court, reported around Dec 30, 2024 to Jan 2, 2025. Swish alleges web scraping and unauthorized API access to take odds data from sportsbook sites such as FanDuel and bet365, and claims over $100M in damages. No defendant response was published. — [GamblingNews](https://www.gamblingnews.com/news/swish-analytics-sues-odds-providers-oddsjam-and-opticsodds-over-alleged-misappropriation/); [SBC Americas](https://sbcamericas.com/2025/01/02/swish-oddsjam-lawsuit/); [Casino Reports](https://www.casinoreports.com/swish-analytics-sues-rival-odds-providers/)
- **Acquisition:** Gambling.com Group agreed on Dec 12, 2024 to buy Odds Holdings (OddsJam's parent) for $80M up front ($70M cash plus $10M stock), with up to $80M more tied to performance through 2026. It closed Jan 1, 2025. — [SEC 6-K](https://www.sec.gov/Archives/edgar/data/1839799/000183979924000084/exhibit991-pressreleasexde.htm); [iGaming Business](https://igamingbusiness.com/strategy/ma/gambling-com-group-acquire-oddsjam/)
- **Influencer and affiliate marketing:** OddsJam recruits creators in gambling, sports betting and "financial independence" niches, paid per sale. — [OddsJam Affiliate](https://oddsjam.com/affiliate); [influence.co](https://influence.co/oddsjam/campaign/oddsjam-inc-marketing-oddsjam-dot-com)
- Trustpilot users allege that paid YouTube and Discord influencers claim big wins while "every play" loses. — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com)
- A broader critique argues that affiliates posing as neutral advice exist "to funnel customers to sportsbooks." — [Closing Line Substack](https://closingline.substack.com/p/shams-the-nba-draft-and-us-sportsbooks)
- **Limiting:** OddsJam's own material and third-party reviews acknowledge that +EV success leads to limits. Users report being limited "almost instantly" or within 1-2 months. — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com); [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108?see-all=reviews&platform=iphone); [XCLSV](https://xclsvmedia.com/oddsjam-review-2026-is-this-ev-betting-tool-worth-it/)
- **Refunds and billing:** a repeated pattern of charges after cancelling a trial, support citing the Terms of Service, and store credit offered instead of refunds. — [Trustpilot](https://www.trustpilot.com/review/oddsjam.com); [UK Trustpilot](https://uk.trustpilot.com/review/oddsjam.com?page=3)

### Inferences
- An "anti-sportsbook" +EV tool is now owned by an affiliate whose revenue comes from sending bettors to sportsbooks. That is a positioning opening for an independent competitor with no affiliate links.
- The Swish suit shows that scraped odds carry legal exposure. Using licensed feeds and exchanges (Kalshi, ParlayAPI) is safer.

### Gaps
- Outcome or status of the Swish lawsuit not found.
- No regulatory actions against OddsJam were found.

## 5. Pricing, and what users see as real value versus hype

### Takeaway
Users value speed, breadth of books, the arb/EV/middles screens and bet tracking. They see the income claims, the Platinum price and the tier maze as overhyped. Education and coaching exist but are bundled into expensive tiers.

### Cited Findings
- Tiers (review site, Sep 2026):
  | Tier | Price | What it includes |
  |---|---|---|
  | Sharp Money | $162-$198/mo | 40+ books, tracker, parlay builder |
  | Platinum | $408-$498/mo | 100+ books, Arbitrage, EV+, Middles, line history, promo conversion, 1:1 coaching |
  | Screen plans | $99.99-$299.99/mo | line shopping only |
  | Fantasy Optimizer | $59.99-$490.99/yr | DFS / pick'em |

  There is a 7-day free trial. — [OddsPlays](https://oddsplays.com/reviews/oddsjam/)
- Other sources cite $199.99/mo "Gold" as the headline plan. — [OddsPlays vs Outlier](https://oddsplays.com/us/betting-tools/oddsjam-vs-outlier/)
- Valued: fast odds updates and comparing books quickly; "top in the industry" data; a free bet tracker (one user credits it with $5K in a month). — [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108?see-all=reviews&platform=iphone); [UK Trustpilot](https://uk.trustpilot.com/review/oddsjam.com?page=3)
- Seen as overhyped: influencer income claims, a Platinum price called "outlandish", and tier complexity. — [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108?see-all=reviews&platform=iphone); [OddsPlays](https://oddsplays.com/reviews/oddsjam/)

### Inferences
- What is worth copying: a free bet tracker with CLV, fast line screens, and education content. What to exploit: price, lines-only access, transparent billing, no affiliate conflict, DFS/pick'em coverage at a low price, and a visible false-positive guard.

### Gaps
- No verified data on what share of users actually profit. The profit claims are self-reported testimonials.
- Could not see Discord community sentiment directly.
