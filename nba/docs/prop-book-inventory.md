# NBA prop book inventory (for a multi-book Steam Chaser test)

Researched 2026-10-30. Docs only: no recorder, page or data change. Reopens the question left by the Pinnacle-only Steam Chaser
backtest (PR 308, `nba/docs/steam-chaser-backtest.md`, NO-GO): the test needs several sharp references so an agreement count can be built.

**Method.** Small read-only requests from one laptop IP, plus vendor docs. Each row says whether it is *confirmed* (we got an answer
or a machine-readable list from the source itself) or *vendor claim* (a marketing or docs page, not tested). No credentials of
anyone else were used and nothing behind a login was fetched. **Cloud-IP blocking was not tested from here.** The recorder already
runs from GitHub Actions against Pinnacle, Kalshi, Polymarket, Novig, PrizePicks, Underdog and Sleeper, so those are known to work from a cloud IP;
everything else is unknown. No prices, limits or fees below are our own numbers; each is copied from the source named.

## Bottom line

1. **Upside's reference set (Circa, FanDuel, 4Cx, Bet105, Pinnacle, PropBuilder) cannot be rebuilt as is.** Only Pinnacle (already stored) and
   FanDuel are reachable with NBA props. Circa has no prop tree on any feed we found; Bet105, 4Cx and PropBuilder have no legitimate
   feed we could find. A test must pre-register a *different* reference set rather than imply it matches Upside's.
2. **The cheapest path to 3+ references is ParlayAPI Starter ($5/month)**, which lists Pinnacle, FanDuel, DraftKings, BetMGM, Caesars, Fanatics,
   Hard Rock, bet365, Novig and others on its props endpoint, plus fixing the Novig prop gap we already created ourselves (below).
3. Sharp money stays context only (CLAUDE.md): none of this feeds an agree total until a frozen forward test says so.

## Ranked: cheapest additions that give 3+ references

Pinnacle is already stored, so each step adds to it.

| # | Addition | Cost | New references | Why it is cheap | Open question |
|---|---|---|---|---|---|
| 1 | **Store the Novig props we already read** | $0, code change in `snapshot.py`/`novig.py` | Novig (exchange, both sides via bid/ask) | `novig.py` already polls props (`PROP_BUDGET` 80/poll, stats pts reb ast 3pm pra pr pa ra stl blk). `quotes()` only returns game lines, so props are in `board['novig']['props']` but never written to the day tape. | Rotation means a prop is seen every few polls, not every poll; a steam test needs the refresh age per prop. |
| 2 | **ParlayAPI Starter, props endpoint** | $5/month, 20,000 credits | FanDuel, Hard Rock, Caesars, BetMGM, Fanatics, bet365, DraftKings (plus Pinnacle, Novig as cross-checks) | `GET /v1/sports/basketball_nba/props` costs 3 credits (confirmed, `/v1/meta/credit-costs`). 20,000 credits is about 6,600 calls a month, about 220 a day, one every 6.5 minutes around the clock. Free tier (1,000 credits) is about 333 calls a month, already budgeted for the lineup feed. | Unconfirmed: whether one props call returns every book's NBA player props or one book per call, and how deep each book's NBA prop tree is. Needs one authenticated call with the existing key. |
| 3 | **Kalshi and Polymarket NBA props** (already stored) | $0 | Two exchanges as context | Already in the recorder. | Thin and one-sided in places; useful as a price check, not as a reference. |
| 4 | ParlayAPI Pro | $20/month, 100,000 credits | same books, one call every 1.3 minutes | Only if Starter cadence is too slow for steam. | Tests Starter first. |

Smallest viable reference set to pre-register: **Pinnacle + FanDuel + Novig** (3 references, steps 1 and 2), with Hard Rock and bet365 as
extras if the props call returns them. That is a sharp book, a sharp-ish recreational book, and an exchange. It is not Upside's set.

## Per book

Format: how read / cost / limits and cloud IP / NBA prop markets / both sides and limits / price format / status.

### Sharp references in Upside's set

| Book | How read | NBA props | Verdict |
|---|---|---|---|
| **Pinnacle** | *Confirmed, already stored.* Guest API `guest.api.arcadia.pinnacle.com/0.1/leagues/487/matchups` answered 200 (1.3 MB). Uses Pinnacle's public web-client key, which the recorder already sends; recorder notes it sometimes 403s a cloud IP for seconds. Also on ParlayAPI (`pinnacle`, props endpoint listed). | Stored as type total with the player in the description. Prop tree is thin and mostly pts/reb/ast (OddsPapi article, vendor claim). Both sides and `maxRiskStake` limit are stored. | In hand. |
| **FanDuel** | Two routes. (a) ParlayAPI `fanduel`, props + historical endpoints listed (*confirmed list*). (b) FanDuel's own `sbapi.nj.sportsbook.fanduel.com` content-managed-page answered 200 (2.8 MB) with the site's embedded `_ak` key from this IP. That is an unofficial site API, not a documented one, and likely against FanDuel's terms; **not recommended**, listed only because it answers. | Strong, including alt and milestone lines (OddsPapi article, vendor claim). | Use via ParlayAPI. |
| **Circa** | No official API (OddsPapi, SharpAPI, SportsGameOdds all say so). OddsPapi aggregates it as `circasports` but its own article says **no NBA player props**, only spreads, totals, moneylines, futures. SportsGameOdds lists it on Pro and above, props not confirmed. ParlayAPI does not list Circa. Site fetch from this IP: 200, HTML only. | None confirmed. | **Blocked for props.** |
| **Bet105** | No public API. SharpAPI's page says "Bet105 coverage has not launched yet" on any plan. Not on ParlayAPI, OddsPapi or SportsGameOdds lists we saw. Site fetch from this IP: 403. | None found. | **Blocked.** Scraping a 403 site is out. |
| **4Cx** | Not mentioned by ParlayAPI, SharpAPI, SportsGameOdds or OddsPapi pages. Search found nothing. | None found. | **Blocked: no source.** |
| **PropBuilder** | Same. A web search for it returns film-prop results, nothing betting. | None found. | **Blocked: no source.** |

### Sportsbooks and exchanges

| Book | How read / cost | NBA props | Verdict |
|---|---|---|---|
| **DraftKings** | Already stored via ESPN odds (prop lines). Direct `sportsbook-nash.draftkings.com` returned **403 Access Denied** (Akamai) from this IP. ParlayAPI lists `draftkings` with props. | Pts/reb/ast/3pm etc. through ESPN today. | Keep ESPN; ParlayAPI as second source. |
| **BetMGM** | ParlayAPI `betmgm` props + historical (*confirmed list*). The Odds API US region (vendor claim). | Not measured. | Via ParlayAPI. |
| **Caesars** | ParlayAPI `caesars` props. The Odds API says **paid subscriptions only** for Caesars (vendor claim). | Moderate, varies by game (OddsPapi, vendor claim). | Via ParlayAPI. |
| **Fanatics** | ParlayAPI `fanatics` props; The Odds API paid only (vendor claim). | Not measured. | Via ParlayAPI. |
| **Hard Rock** | ParlayAPI `hardrock` game lines, live, props. | "Deepest prop coverage in testing" incl. pts, reb, ast, PRA, 3pm, steals, blocks, combos (OddsPapi, vendor claim). | Best depth. Via ParlayAPI. |
| **bet365** | ParlayAPI `bet365` props (*confirmed list*). | Not measured. | Via ParlayAPI. |
| **BetOnline** | Sharp-leaning offshore book. In ParlayAPI's source-quality list as latest-state only, **not in its bookmaker registry**; no props endpoint listed. Also on The Odds API and SportsGameOdds (vendor claims). Direct site fetch: 403. | Unknown. | Uncertain; ask ParlayAPI support or check The Odds API `bookmakers=betonlineag`. |
| **Thunderpick** | Crypto book. No feed found on ParlayAPI, The Odds API, SharpAPI or SportsGameOdds. Direct site: 403. | None found. | **Blocked: no source.** |

### Exchanges and prediction markets

| Book | How read / cost / limits | NBA prop markets | Both sides, limits | Price format | Verdict |
|---|---|---|---|---|---|
| **Novig** | *Confirmed keyless.* Public REST `api.novig.com/v3/public/catalog/events?league=NBA&status=OPEN_PREGAME` returned 200 with no credentials; the recorder already paces 0.35 s/request and honours `Retry-After`. Works from Actions. Also on ParlayAPI with `props`. | pts reb ast 3pm pra pr pa ra stl blk (stat map in `novig.py`). | Order book: bid, ask, depth near the top, trade tape. | Probability in dollars; stored as bid/ask. | **Props are read but never stored.** Step 1 above. |
| **ProphetX** | Exchange. ParlayAPI lists `prophetx` but with **no endpoint list** (no props, no game lines) and warns some asks are no-volume "shill" orders. The Odds API lists it (vendor claim). `www.prophetx.co` loads as a web app (200, 1.3 MB of HTML); no public REST path found (`/api/v1/sports` 404, `api.prophetx.co` no answer). | Unknown. | n/a | n/a | **Blocked: no confirmed feed.** |
| **Kalshi** | *Confirmed, already stored.* Public `api.elections.kalshi.com/trade-api/v2`; series exist for `KXNBAPTS`, `KXNBAREB`, `KXNBAAST`, `KXNBA3PT`, `KXNBAPRA`, `KXNBAPA`, `KXNBAPR`, `KXNBARA`, `KXNBASTL`, `KXNBABLK`. | all of those. | Yes/no contracts, depth. | Cents (probability). | In hand. Exchange, context only. |
| **Polymarket** | *Confirmed, already stored.* Gamma `events?series_id=10345&closed=false` answered 200. Of 100 events: points 685 markets, rebounds 674, threes 561, assists 419, steals 207, blocks 74. **No PRA or combos.** Recorder note: price-history is moving to v2 before the Oct 30 shutdown (PR 270). | pts reb ast 3pm stl blk. | Yes/no, order books. | Probability. | In hand. Context only. |

### Pick'em and DFS apps

| Book | How read | Markets | Verdict |
|---|---|---|---|
| **PrizePicks** | *Already stored.* `partner-api.prizepicks.com/projections` (keyless, leagues 7 and 237). ParlayAPI `prizepicks` props. | Single-line projections, no price (fixed payout), so it has no sides or juice. | In hand. These are the **slow** side of a steam test, not references. |
| **Underdog** | *Already stored.* `api.underdogfantasy.com/v1/over_under_lines`. Also ParlayAPI. | Over/under with its own prices. | In hand, slow side. |
| **Sleeper** | *Already stored.* `api.sleeper.com/lines/available`. Also ParlayAPI. | Same. | In hand, slow side. |
| **Pick6 (DraftKings)** | ParlayAPI `pick6` props; The Odds API lists it (vendor claim). Not stored by us. | Not measured. | Available via ParlayAPI if wanted; project notes say hold new pick'em books until the frozen forward test (from 10/27) reads. |
| **Dabble** | The Odds API (US key, vendor claim). Not on ParlayAPI's registry. | Not measured. | Hold. |
| **Betr** | ParlayAPI `betr` props (US). The Odds API lists only an AU Betr. | Not measured. | Hold. |

## Aggregators

| Service | Books we care about | NBA props | Cost | Limits | Notes |
|---|---|---|---|---|---|
| **ParlayAPI** (already used) | *Confirmed* from `/v1/bookmakers`: Pinnacle, FanDuel, DraftKings, BetMGM, Caesars, Fanatics, bet365, BetRivers, Bovada, Hard Rock, Parx, Novig, PrizePicks, Underdog, Sleeper, Pick6, Betr, Fliff, ParlayPlay. **Not** Circa, Bet105, 4Cx, PropBuilder, Thunderpick. | Props endpoint 3 credits per sport. | Free 1,000 credits; Starter **$5** 20,000; Pro $20 100,000; Business $40 1M; Enterprise $100 5M; Scale $200 50M (`/pricing`). | Free 60 req/s; paid 10,000 req/s; WebSocket/SSE on Business and up. History lookback 48 h free, 168 h Starter, 720 h Pro. | `/v1/meta/parser-coverage` (per-book per-sport market counts) was returning 503 stale when tried; retry before relying on it. Which tier includes which books is not stated on the pricing page. |
| **The Odds API** | Per its bookmaker page: Pinnacle (EU, "public website, may be delayed"), FanDuel, DraftKings, BetOnline, Bovada, BetMGM, Caesars (paid), Fanatics (paid), Hard Rock, Novig, ProphetX, Underdog, PrizePicks, Pick6, Dabble. Circa not listed. | "Selected US sports and bookmakers" (page does not say NBA). | Free 500 credits; $30 20K; $59 100K; $119 5M; $249 15M. | Credit formula for several regions/markets is not on the page. | Only mainstream aggregator that lists ProphetX and BetOnline. Worth a free-key check of which bookmakers return NBA props. |
| **OddsPapi** | Circa (`circasports`, no props), Hard Rock, FanDuel, theScore, BetRivers, Caesars, Pinnacle, DraftKings, "350+ bookmakers" (vendor claim). | Hard Rock deepest; Pinnacle and DK thin. | Free tier exists, limits not stated. | Not stated. | Decimal prices. Requires a key (API answered 401). |
| **SharpAPI** | DraftKings, FanDuel, BetMGM, Caesars, Pinnacle, bet365, Betway, BetOnline, Circa (page exists). Bet105 "not launched". | Yes; for Pinnacle it estimates props from game lines (its own statement), so that is **not** a Pinnacle prop price. | Free: 2 books, 12 req/min, 60 s delay. Pro **$229**/month. | Free 12 req/min. | Too expensive for what ParlayAPI Starter gives. |
| **SportsGameOdds** | Circa (Pro and up), BetOnline, Pinnacle. Not Bet105, 4Cx, PropBuilder, Novig, ProphetX. | Circa props not confirmed. | Prices not on the page we fetched. | Not stated. | Key required (API answered 401). Check `/markets` for Circa before paying. |
| **Action Network** | Already stored for game lines (`api.actionnetwork.com/web/v2/scoreboard/nba`, books 15,30,68,69,75,71,79). | Not tested for props. | Free (unofficial web API). | Not stated. | Props endpoint not probed here; follow-up. |
| **Unabated, OddsJam, OpticOdds, Sportradar** | Not probed. Unabated and OddsJam are consumer products with paid tiers and no documented public feed found. Sportradar Odds Comparison Player Props v2 exists (NBA, vendor claim), enterprise priced. | n/a | n/a | n/a | Left out: no free or cheap legitimate API found in this pass. |

## Blocked, with the reason

| Book | Why |
|---|---|
| Circa | No public API; the aggregators that carry it show no NBA prop tree. |
| Bet105 | No API anywhere; SharpAPI says coverage has not launched; site 403s us. |
| 4Cx, PropBuilder | No feed found on any vendor or search result. |
| Thunderpick | No feed found; site 403. |
| ProphetX | Listed by ParlayAPI with no endpoints and shill-order warning; no public REST path found. |
| BetOnline | No props endpoint on ParlayAPI; only in third-party aggregators' lists. |
| DraftKings direct | 403 Akamai from this IP; already covered by ESPN. |
| FanDuel direct site API | Answers, but it is an undocumented site API using an embedded key; ToS risk. Use ParlayAPI instead. |

## Next steps (not done here)

1. One authenticated ParlayAPI NBA props call with the existing key (3 credits) to record, per book, the markets returned, both sides, and whether prices and lines come back in one payload. That settles step 2's open question.
2. Free-key check of The Odds API props for `betonlineag`, `prophetx`, `novig`, `hardrockbet`.
3. Write the Novig prop quotes into the day tape (small, separate PR; touches `snapshot.py`, so check open PRs first).
4. Pre-register the reference set and the agreement rule before any data is read, then rerun the PR 308 backtest.

## Sources

- ParlayAPI: `/v1/bookmakers`, `/v1/meta/credit-costs`, `/v1/meta/source-quality`, `/pricing` (fetched 2026-10-30)
- Novig, Kalshi, Polymarket, Pinnacle, DraftKings, FanDuel: direct requests from this machine, 2026-10-30
- [The Odds API bookmakers](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html) and [pricing](https://the-odds-api.com/#get-access)
- [OddsPapi: Circa](https://oddspapi.io/blog/?p=3108), [OddsPapi: NBA props](https://oddspapi.io/blog/?p=2877)
- [SharpAPI: Bet105](https://sharpapi.io/sportsbooks/bet105-odds-api), [SharpAPI: NBA](https://sharpapi.io/odds/nba)
- [SportsGameOdds: Circa](https://sportsgameodds.com/circa-odds-api/)
