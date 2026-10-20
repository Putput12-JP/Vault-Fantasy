# OddsJam: Product Lineup, Features and Pricing (as of Sept 2026)

Research method note: oddsjam.com blocks server-side fetch (HTTP 403), so primary OddsJam pages were read in a real browser session on 2026-09-26 (subscribe page, betting-tools hub, positive-ev, sharp-money, odds-api), plus Wayback Machine captures of the subscribe page (2023-12-26, 2024-12-18). Several oddsjam.com/betting-education/* articles that search engines still index now return "This page does not exist" (e.g. /uncovering-true-outcome-probabilities, /positive-ev-tool-tips-tricks-hacks, /how-to-sync-sportsbooks-with-oddsjam-bet-tracker), so methodology detail leans on secondary sources and OddsJam staff posts on X. Third-party review sites disagree with each other on prices; conflicts are flagged inline.

## 1. What are all the tools/offerings, and how does each work (method + UI/UX)?

### Takeaway
OddsJam is a suite of scanners on one real-time odds feed (100+ books): Positive EV, Arbitrage, Middles, Low Hold, Promo/Bonus Converter, Parlay Builder, Sportsbook Screen, Sharp Money (exchange-liquidity "crossed market" signals), Fantasy Optimizer (DFS pick'em), Trends, a free Bet Tracker with CLV, Prediction Traders/Insiders (Kalshi/Polymarket copy-trading signals), plus an enterprise Odds API/Screen. The UX pattern is the same everywhere: a sorted feed of opportunities, heavy filters, a recommended stake, and "1-click bet" deep links into the sportsbook.

### Cited Findings

**Positioning / scale claims (OddsJam's own pages)**
- "Profits average 3% every day"; "Developed by Stanford engineers"; processes "over 1 million odds per second"; identifies "over 10K arbitrage bets per month"; covers "mainline markets, alternative spread markets, player props, futures and more" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- "Trusted by 100k+ bettors worldwide" - [OddsJam Subscribe](https://oddsjam.com/subscribe); App Store says "over 100,000 users" and "150+ sportsbooks" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Founded 2021 by Stanford grads Alexander Monahan and Ankit Goyal - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)

**Positive EV tool**
- Marketed as "We scan millions of odds every second to find the rare bets that actually have an edge"; "We tell you the exact sportsbook, game, market, players, even amount to bet"; page states Positive EV, Arbitrage, Parlay Builder and Promo Converter are "INCLUDED IN ALL PLANS" (note: this contradicts the subscribe page, where those tools are only listed under the top tier) - [OddsJam Positive EV](https://oddsjam.com/betting-tools/positive-ev)
- EV formula stated as probability of win x amount won minus probability of loss x amount lost, with opportunities "sorted by expected profit margin" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- Users can choose their devig "source of truth" book (added ~Oct 2024, per a power-user post: "@OddsJam now allows you to choose your 'source of truth' for devigging") - [TheArbFather on X](https://x.com/TheArbFather/status/1848766801360130304)
- Devig methods offered (per third-party explainers describing OddsJam-style tooling): Multiplicative, Additive, Power, and "Worst Case" (the most conservative EV% across methods); users commonly pick Pinnacle as devig book with Worst Case - [search summary citing OddsJam education + Outlier help](https://help.outlier.bet/en/articles/8208129-how-to-devig-odds-comparing-the-methods); OddsJam also publishes a "Market Width" article on using market width as an EV filter - [OddsJam Market Width](https://oddsjam.com/betting-education/market-width)
- Secondary claim that OddsJam "primarily uses Pinnacle as its sharp reference line with power devigging" - [Sharp Lines comparison](https://sharplines.io/compare/oddsjam-alternative) (competitor source; treat cautiously)
- Another review says de-vig is done via "market averages" - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/). Likely both exist: default consensus/market-average fair line vs user-selected sharp book.
- OddsJam co-founder Alex Monahan publicly treats betting exchanges (Novig, ProphetX) as "VERY sharp", especially at high liquidity (example cites $25k liquidity on a prop) - [Alex Monahan on X](https://x.com/AlexMonahan100/status/1974164718538363018)
- 2023 Platinum plan explicitly listed "Circa Vegas Odds" as a feature (Circa as a sharp reference) - [Wayback 2023-12-26 subscribe](https://web.archive.org/web/20231226205121/https://oddsjam.com/subscribe)
- Reviewers report users keep CLV "beat rates at or above 70%"; filters by sportsbook, profit %, sport, league, odds range, time windows, saved filters, duplicate-bet warnings, customizable columns, "dual tab setup" - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)

**Arbitrage**
- "See arbitrage bets sorted by guaranteed profit percentage"; real-time from 100+ books - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- Pre-calculated ROI and stake sizing; live arbs average "2x higher ROI" - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/); built-in arbitrage calculator, sorting by ROI - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)

**Middles**
- "if the exact right outcome occurs you can win both bets"; OddsJam claims "the only offering with sports betting middles"; "process over 1M odds per minute" (note: inconsistent with "per second" elsewhere on the same page); live middles require the live plan - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)

**Low Hold**
- Finds markets with small or zero hold across books to reduce juice and clear deposit-bonus rollover - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)

**Promo / Bonus Bet Converter (and Promo Finder)**
- Bonus-bet conversion opportunities "sorted by the conversion percentage ... typically 80 cents on the dollar or better" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- Reviewer claims "95–98% efficiency" for promo conversion (likely for profit boosts/no-sweat, not bonus bets) - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)
- Separate "Promo Finder" nav item existed on the site in Dec 2024 alongside "Promo Converter" - [Wayback 2024-12-18 subscribe](https://web.archive.org/web/20241218213845/https://oddsjam.com/subscribe)
- "Deposit Optimizer" is listed as part of the Sharp Money plan - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)

**Parlay Builder**
- Generates "positive EV combinations" per user criteria - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/); app advertises "Auto-generated parlays from algorithms" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)

**Sharp Money (and Sharp Money Pro)**
- Features: "Real-time detection of unusually large bets from sharp bettors"; "We tell you exactly where to bet, across 40+ domestic books and Fantasy platforms"; "See available liquidity on every exchange line"; "Compare odds across every book" - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money)
- Method ("crossed market" strategy): if high liquidity sits on Under +121 at an exchange like Novig, sharps actually want Over -121 or better; OddsJam then scans for the same bet at a better price (example: Over -115 at DraftKings) and "1-click bet" takes you there - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money)
- Sharp Money Pro adds 100+ global books, auto refresh, "Line History shows which books are trailing the Sharp Money overtime", 1:1 coaching - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money)
- Support channels listed: 24/7 Live Chat, Discord Community, X Threads - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money)

**Sportsbook Screen / Odds Screen**
- Platinum: "Scan every league, market, and book with the Sportsbook Screen" - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- Enterprise Screen: real-time odds for main, alt and props from 100+ books; "custom weighted consensus lines" with notifications when they move; Slack and Microsoft Teams integrations; injuries, scores, play-by-play, location, weather; notifications for market posting, injuries, settlement, time changes - [OddsJam Odds API page](https://oddsjam.com/odds-api)
- Reviewer lists screen tiers: Starter Screen $99.99/mo (20+ US books), Pro Screen $299.99/mo (100+ global) - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/) (not visible on current subscribe page)

**Line movement / odds history**
- "Line Movement History for every bet" is a top-tier feature - [OddsJam Subscribe](https://oddsjam.com/subscribe); line movement charts noted - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)

**Alerts / notifications / auto-refresh**
- App: "Real-time value alerts for odds and stat shifts" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108); Gold plan included push notifications; Platinum adds Auto-Refresh - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review); 2023 Platinum listed "Real Time Push Notifications" and "Auto Refresh" - [Wayback 2023](https://web.archive.org/web/20231226205121/https://oddsjam.com/subscribe)

**Live odds**
- "Live odds (in-game) move up to 50x faster"; OddsJam claims "the only betting platform that refreshes live odds every second"; live +EV/arb/middles gated to Platinum; live bets "up to 2x more profitable" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools); [OddsJam Subscribe](https://oddsjam.com/subscribe)

**Fantasy (DFS pick'em) tools**
- Fantasy Optimizer plan: "Get profitable slips for every Fantasy App and DFS Platform"; includes Fantasy Optimizer, Fantasy Parlay Builder, Unlimited Line Shopping - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- Covers PrizePicks and Underdog; also "Fantasy Scores" (fantasy point projection discrepancies across platforms) and "Fantasy Middles" - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review); DFS profit tracking, CLV %, lineup builders - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)
- App: "Fantasy optimizer with hit-rate projections" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)

**Trends**
- App plan "Trends" ($19.99/mo); "Performance trend analysis (5, 10, or 20-game windows)" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)

**Bet Tracker** (see Q4)

**Prediction markets: Prediction Traders / Prediction Insiders**
- App IAP "Prediction Traders Monthly" $449.99/mo - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Described as unlimited picks from algorithmically selected traders on Kalshi, Polymarket, ProphetX, Novig and more - [search summary of App Store listing](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Prediction Insiders: filters traders with at least 500 bets, ranks on six risk-adjusted metrics (profit, Sharpe, capital efficiency, profit factor, max drawdown, consistency), ML classifies into nine strategy categories; delivers real-time signals with confidence scores and direct trade links; Polymarket on-chain wallet insights, Kalshi "whale" tracking; reviewer's 30-day trial claimed +473% / 63.01% win rate on $5k (self-reported, unverified) - [BettorEdge review](https://www.bettoredge.com/post/oddsjam-prediction-insiders-review) (review references March 2026)
- OddsPlays still labels Prediction Insiders "Coming Soon" - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/) (conflicts with App Store IAP and BettorEdge; likely stale)

**Mobile app**
- iOS "OddsJam: Sharp Sports Betting", 4.7/5 on 2.3K ratings, 18+, version 27.0.51; latest release notes: "New Games Tab: See upcoming games and find profitable plays from our Plus EV, Sharp Money, and Arbitrage algorithms!"; features: value alerts, trends, fantasy optimizer, +EV/arb/middles, bet tracker, "Follow the money", auto-generated parlays, Games tab - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Android app exists (com.oddsjam.app, "OddsJam: Win At Sports Betting") - [Google Play](https://play.google.com/store/apps/details?id=com.oddsjam.app&hl=en_US)

**Calculators and education (free SEO surface)**
- Free calculators: Arbitrage, EV, Bonus Bet Conversion, Half Point, Hold, Kelly, No-Vig Fair Odds, Odds Converter, Parlay, Point Spread, Poisson, Round Robin, Vig - [OddsJam Subscribe footer](https://oddsjam.com/subscribe)
- Odds pages per league (NFL, NBA, CFB, MLB, CBB, NHL, Soccer, Golf), Betting Education, promo codes, Getting Started Guide - [OddsJam Subscribe footer](https://oddsjam.com/subscribe)
- 1:1 "profit coaches" ($100k+ profit) on Platinum / Sharp Money Pro; positive-ev page advertises "FREE 1-1 Coaching Sessions" - [OddsJam Subscribe](https://oddsjam.com/subscribe); [OddsJam Positive EV](https://oddsjam.com/betting-tools/positive-ev)

**Enterprise: Odds API / data feed**
- "The fastest sports betting API in the world"; 100+ books; player props, alternates, futures, injury data, schedules/rosters, scores/results, deep links ("Maximize affiliate revenue"), push feeds, bet auto-grader endpoint; JSON or XML; push stream; "hundreds of servers"; full historical odds database (opening, closing, live line changes); targeted at market makers, traders, syndicates, operators; pricing via contact form only - [OddsJam Odds API page](https://oddsjam.com/odds-api)
- No public price; SSE streaming tier-gated; docs gated - [OddsPapi blog, Apr 2026](https://oddspapi.io/blog/oddsjam-api-alternative/); estimated "$500 - $1,000+ per month" starting (third-party estimate) - [search summary citing SportsAPI.com](https://sportsapi.com/api-directory/oddsjam/)

**Corporate**
- Gambling.com Group agreed Dec 2024 to buy Odds Holdings (OddsJam parent) for up to $160M (€80M initial + up to $80M earn-out through end of 2026); Odds Holdings also sells "low latency odds data to enterprise clients" - [iGaming Business](https://igamingbusiness.com/strategy/ma/gambling-com-group-acquire-oddsjam/); completed Jan 1, 2025 - [Gambling.com IR](https://www.gambling.com/corporate/investors/news/gambling-com-group-completes-acquisition-of-odds-holdings-inc-parent-company-of-oddsjam/7b002b9d-2af3-4ec2-966b-36145b46262f); [BusinessWire](https://www.businesswire.com/news/home/20250102618058/en/Gambling.com-Group-Completes-Acquisition-of-Odds-Holdings-Inc.-Parent-Company-of-OddsJam)

### Inferences
- The core product is one odds feed repackaged into many scanners; the moat is breadth (props/alts at 100+ books) and speed, not models. OddsJam does not appear to sell its own projection model; "fair odds" come from devigging sharp books/exchanges/consensus.
- Sharp Money is essentially exchange-liquidity reading (Novig/ProphetX/Kalshi) repackaged as "follow the pros", a cheaper tier than full +EV, and a pivot toward exchanges as the sharp reference.
- The product has shifted from pure +EV/arb (2023) toward retail-friendlier entry points (Trends $19.99, Fantasy ~$59.99, Sharp Money $199.99, Games tab) and prediction-market copy trading.
- OddsShopper (oddsshopper.com) appears as a separate content brand publishing prediction-market articles; I did not confirm its ownership relationship to OddsJam in this pass.

### Gaps
- Exact current devig defaults (which book is default fair source; default method; whether Kelly fraction is configurable) could not be read from OddsJam directly because the education/help articles 404 or 403.
- Kelly sizing: OddsJam offers a Kelly calculator and "even amount to bet" recommendations, but I found no primary source stating the default Kelly fraction used in tools.
- Chrome extension / "Bet Sync": no primary source found in this pass; sync described only as account syncing in the tracker (Q4).
- Discord details (paid vs free, size) not found beyond "Discord Community" being listed as a support channel.
- Correlated/SGP parlay pricing method not documented.

## 2. Pricing tiers and plans (current vs historical), trial/refund, API pricing

### Takeaway
As of Sept 2026 the web subscribe page shows three cards: Fantasy Optimizer (~$1.90/day), Sharp Money ($6.60/day, about $199.99/mo), and an unnamed top tier (Platinum, "106+ sportsbooks", live, all scanners) listed at a 50%-off first month of $8.30/day (implying about $16.60/day, $499.99/mo), with 15% off yearly and a 7-day free trial. App IAPs confirm $19.99 Trends, $59.99 Fantasy, $199.99 Sharp Money/Gold, $449.99 Prediction Traders, $499.99 Positive EV / Platinum. Platinum was $999/mo in Dec 2023, so the top tier has roughly halved.

### Cited Findings

**Current (web, captured 2026-09-26)**
- Headline "Get 7 days on us"; Monthly/Yearly toggle "Save 15%" - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- FANTASY OPTIMIZER: "$1.90" (strikethrough "$2") per day, billed monthly - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- SHARP MONEY: "$6.60" (strikethrough "$8") per day, billed monthly - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- Top tier: "50% OFF FIRST MONTH $8.30 ... $20 per day, for the first month"; includes Arbitrage, Positive EV, Middles, Low Holds, Promo Converter, live bets, Auto Refresh, "pre-match bet recommendations for 106+ Sportsbooks", Line Movement History, 1:1 coaching, Sportsbook Screen - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- Cancellation FAQ: "you can easily cancel your trial if you are not satisfied" (no money-back guarantee stated) - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- Sharp Money Pro plan exists (price rendered $0.00 on the page before login/geo; reviewer puts it ~$300/mo) - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money); [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)

**Current (App Store IAPs)**
- Trends $19.99; Fantasy $59.99; Sharp Money $199.99; Gold $199.99; Positive EV Monthly $499.99; Platinum Monthly $499.99; Prediction Traders Monthly $449.99; all with 7-day free trial - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)

**Reviewer-reported (conflicting)**
- Sharp Money ~$198/mo ($6.60/day) or $162/mo annual ($5.40/day); Platinum ~$498/mo ($16.60/day) or ~$408/mo annual ($13.60/day); Fantasy $59.99/mo or $490.99/yr; Starter Screen $99.99; Pro Screen $299.99 - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)
- Fantasy $1.97/day monthly, $1.32/day annual; Gold $6.60/day, $5.40/day annual - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)
- Platinum $499 monthly, ~$400/mo annual; "Positive EV Global" ~$499 - [ArbBets, Jul 2026](https://getarbitragebets.com/blog/oddsjam-pricing)
- "Global plan at $399.99/month" and Gold $199.99 - [XCLSV review](https://xclsvmedia.com/oddsjam-review-2026-is-this-ev-betting-tool-worth-it/); "Positive EV Global $399.99", "Platinum up to $999/month" - [BettorEdge](https://www.bettoredge.com/post/oddsjam-prediction-insiders-review); Platinum ~$999 figure also in [OddsPapi](https://oddspapi.io/blog/oddsjam-api-alternative/) (likely stale, carried from 2023)
- May 2025 promo on X: Platinum made free to all OddsJam users for a limited period - [OddsJam on X](https://x.com/OddsJam/status/1921706721665315161)

**Historical**
- Dec 26, 2023 (New Jersey geo): PROMO OPTIMIZER $39/mo (Free Bet Converter, Low-Hold, Middles, mobile app tools, unlimited line shopping); POSITIVE EV $199/mo "MOST POPULAR" (adds +EV, Arbitrage, Parlay Builder); PLATINUM $999/mo "Contact Us" (adds Live odds, Global books, real-time push, Auto Refresh, Line Movement History, Circa Vegas Odds); annual billing "SAVE 20%"; nav included Bet Tracker, Fantasy, +EV Tool, Arbitrage, Screen; plans were region-specific ("Are you in a different region?") - [Wayback 2023-12-26](https://web.archive.org/web/20231226205121/https://oddsjam.com/subscribe)
- Dec 18, 2024: nav was +EV, Arbitrage, Tracker, Promo Finder, Promo Converter, Pricing, Enterprise (plan cards did not render in the capture) - [Wayback 2024-12-18](https://web.archive.org/web/20241218213845/https://oddsjam.com/subscribe)

**API pricing**
- Not published; "Contact us now to get premium access and pricing" - [OddsJam Odds API page](https://oddsjam.com/odds-api); no free API tier - [OddsPapi](https://oddspapi.io/blog/oddsjam-api-alternative/)

### Inferences
- Price history: Platinum $999/mo (2023) to $499.99/mo (2026, plus 50%-off first month), a roughly 50% cut; entry tier went from $39 Promo Optimizer (2023) to $19.99 Trends / ~$59.99 Fantasy; the "+EV" mid tier ($199) was effectively rebranded to Sharp Money ($199.99), with +EV/arb moved up to the top tier on the web page. Annual discount fell from 20% (2023) to 15% (2026).
- Per-day price framing, strikethrough anchors and a first-month 50% discount are deliberate conversion tactics.
- Pricing is geo-dependent (2023 page was NJ-specific; Sharp Money Pro rendered $0.00 in my session), which explains conflicting reviewer figures.

### Gaps
- Exact current annual prices per tier on the web (toggle did not switch in automation).
- Current "Gold" and "Positive EV Global" plan existence on the web page (both exist as app IAPs; not shown as web cards).
- Refund policy beyond trial cancellation; Terms page not read.

## 3. Sportsbook/market coverage, latency claims, jurisdictions

### Takeaway
Claims range from "100+" to "106+" (web) to "150+" (App Store) sportsbooks across the US, Canada, Europe and Australia; mid tier limited to "40+ domestic books and Fantasy platforms". Latency claims are marketing superlatives ("fastest", "1 million odds per second", live odds refreshed "every second") with no published millisecond figures.

### Cited Findings
- "more than 100 sportsbooks from the United States, Canada, Europe, and Australia" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- Top tier: "106+ Sportsbooks"; Sharp Money: "40+ domestic books and Fantasy platforms" - [OddsJam Subscribe](https://oddsjam.com/subscribe)
- "150+ sportsbooks" - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108); reviewer: Platinum "91+ sportsbooks worldwide" (older figure) - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)
- Books named: FanDuel, DraftKings, BetMGM, bet365, Caesars, Fanatics, BetRivers, ESPN BET - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review); exchanges Novig, ProphetX; prediction markets Kalshi, Polymarket - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money); [App Store summary](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Sports: NFL, NBA, MLB, Premier League, MLS, NHL, Golf, Tennis, UFC, esports, Cricket, table tennis - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/)
- "over 1 million odds per second"; live odds refreshed "every second"; live odds "move up to 50x faster than pre-match" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools); "hundreds of servers" - [OddsJam Odds API page](https://oddsjam.com/odds-api)
- API latency not disclosed - [OddsPapi](https://oddspapi.io/blog/oddsjam-api-alternative/)

### Inferences
- Book-count inflation across surfaces (91 to 106 to 150) suggests counting regional skins/international books; a competitor should publish a precise, verifiable list.

### Gaps
- State-by-state availability list and sweepstakes book coverage (e.g. Fliff) not confirmed from primary sources.
- No independent latency benchmark found.

## 4. Bet tracker / syncing: import, CLV, ROI

### Takeaway
The Bet Tracker is free, auto-grades bets, tracks CLV against "the sharpest book in the world", supports one-click adds from any tool, and syncs sportsbook accounts (DraftKings, FanDuel, BetMGM, Caesars, PrizePicks and others); there is also a Deposits/Withdrawals tracker.

### Cited Findings
- "Free Bet Tracker ... tracks your bets across any sportsbook"; "Add bets with one click"; "automatically tracks the outcome of your bets (win, loss, refund, etc.)"; "automatically tracks CLV (closing line values) from the sharpest book in the world" - [OddsJam Betting Tools hub](https://oddsjam.com/betting-tools)
- Sync supported for DraftKings, FanDuel, BetMGM, Barstool, Caesars, PointsBet, WynnBET, PrizePicks (list partly stale: Barstool, PointsBet, WynnBET have since exited/rebranded); stats: bankroll, win/loss, "CLV beating %", profit margin per wager, breakdowns by bet type, time, sportsbook - [search summary of OddsJam sync article + App Store](https://oddsjam.com/betting-education/how-to-sync-sportsbooks-with-oddsjam-bet-tracker) (article now 404s)
- Bet tracker page and a separate "Deposits/Withdrawals Tracker" exist - [OddsJam Bet Tracker (dev mirror)](https://dev.oddsjam.com/bet-tracker); [Payment Tracker](https://dev.oddsjam.com/payment-tracker)
- Tracker tracks EV, CLV, profit and supports social sharing - [OddsPlays review](https://oddsplays.com/reviews/oddsjam/); CLV tracking and ROI metrics - [RotoWire review](https://www.rotowire.com/betting/oddsjam-review)

### Inferences
- The tracker is the free retention/acquisition hook feeding paid tiers; "CLV beat %" is the key trust metric OddsJam uses to prove its tools work.

### Gaps
- Sync mechanism (credential login, screen scraping, email parsing, or browser extension) not confirmed; no primary source for a Chrome extension/"Bet Sync".
- CSV import/export support not confirmed.

## 5. Newer 2025-2026 launches

### Takeaway
2025-2026 additions: Gambling.com Group ownership (Jan 2025), Sharp Money / Sharp Money Pro (exchange-liquidity signals), Prediction Traders / Prediction Insiders for Kalshi, Polymarket, ProphetX, Novig ($449.99/mo), Trends ($19.99), a mobile "Games Tab" (Sept 2026), and a lowered, discounted Platinum. No explicit "AI" branding found beyond ML trader classification.

### Cited Findings
- Acquisition completed Jan 1, 2025 - [BusinessWire](https://www.businesswire.com/news/home/20250102618058/en/Gambling.com-Group-Completes-Acquisition-of-Odds-Holdings-Inc.-Parent-Company-of-OddsJam)
- Choose-your-devig-book feature, ~Oct 2024 - [TheArbFather on X](https://x.com/TheArbFather/status/1848766801360130304)
- Sharp Money crossed-market tool using exchange liquidity (Novig) - [OddsJam Sharp Money](https://oddsjam.com/betting-tools/sharp-money); exchanges called "VERY sharp" by co-founder, ~Oct 2025 - [Alex Monahan on X](https://x.com/AlexMonahan100/status/1974164718538363018)
- Prediction Traders IAP $449.99 and Games Tab release - [App Store](https://apps.apple.com/us/app/oddsjam-sharp-sports-betting/id6448072108)
- Prediction Insiders ML strategy classification (nine categories), Polymarket wallet insights, Kalshi whale tracking - [BettorEdge](https://www.bettoredge.com/post/oddsjam-prediction-insiders-review)
- Platinum free-for-all promo, May 2025 - [OddsJam on X](https://x.com/OddsJam/status/1921706721665315161)

### Inferences
- OddsJam is moving its "sharp" anchor toward exchanges and prediction markets and monetising them both as a signal source (Sharp Money) and as a destination (Prediction Traders).

### Gaps
- Exact launch dates for Sharp Money, Trends, Fantasy Optimizer rebrand, and Prediction Traders.
- Sweepstakes book coverage and any AI-assistant/chat features: no reliable source found.
