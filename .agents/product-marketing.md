# Product Marketing Context

**Document version:** v2
**Last updated:** 2026-08-20

> Drafted from the app (index.html, login.html, changelog), project docs, and internal
> strategy notes. Sections marked **[CONFIRM]** are my best inference and need your
> sign-off; sections marked **[NEEDS INPUT]** can't be sourced from the repo (real
> customer quotes, live metrics, testimonials) and need you to fill them.

## Product Overview
**One-liner:** Vault is a league-synced intelligence platform for fantasy football managers — your dynasty and redraft war room for drafting, trading, and setting lineups.

**What it does:** Vault connects to your real Sleeper leagues and turns them into a decision cockpit: a live draft assistant with per-pick grades and an adaptive game plan, an ADP explorer, trade engines (matchmaker, exploit finder, fair-value calculator), lineup/waiver optimization that can write back to Sleeper, a season simulator, and betting/props context. The numbers under the hood are fit from *real* Sleeper drafts and trades, not hand-picked constants.

**Product category:** Fantasy football tools — specifically a dynasty/redraft manager toolkit + draft assistant. The "shelf" customers search from: *fantasy football draft tool*, *dynasty trade calculator*, *Sleeper draft assistant*.

**Product type:** Web app (PWA, mobile + desktop), Sleeper-connected. Multi-platform reads expanding to ESPN and Yahoo.

**Business model (2026 GTM = free / love-first):** For the 2026 season Vault is **free — no pricing, no paywall.** The goal is to get managers in the door and falling in love with the product, build an engaged base, and earn word-of-mouth before charging. Monetization (Season Pass, capped Founder's Lifetime, small Dynasty recurring tier) is a *later* lever, kept out of public marketing for now. Sportsbook/DFS affiliate stays a garnish, walled off from advice — never metered into the live draft. **All public copy/graphics/SEO this season should market "free," not price.**

## Target Audience
**Target companies:** N/A — B2C. Individual fantasy football managers.

**Decision-makers:** The manager themselves (impulse/personal purchase). Secondary buyer: **fantasy content creators** who want to publish their own rankings board through Vault.

**Primary use case:** Make the highest-leverage roster decisions — who to draft, who to trade, who to start — with league-specific intelligence instead of generic rankings.

**Jobs to be done:**
- "Help me not blow my draft" — walk into a draft with a plan and get live, format-aware guidance and a grade.
- "Tell me if this trade is fair (and find me better ones)" — price players and picks off real market data across all my leagues.
- "Set my optimal lineup every week" — and actually push it to Sleeper without tab-switching.
- "Tell me if I'm actually good" — season sim, power rankings, playoff odds for my real league.

**Use cases:**
- Live dynasty or redraft draft (the crown-jewel moment).
- Off-season and in-season trade hunting across multiple leagues.
- Weekly lineup/waiver decisions.
- Rookie draft / ADP research.
- Creators publishing a named rankings profile for their audience.

## Personas
*(B2C — light personas rather than a buying committee.)*

| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| The dynasty grinder | Multi-league edge, trade value, long-term assets | Juggling many leagues, mispriced picks, generic calculators | One war room across every league, values from real trades |
| The redraft "just win" manager | Winning this season, not overthinking | Doesn't want a spreadsheet; wants a call | Adaptive draft plan + optimal lineup, in plain English |
| The creator | Publishing their board, serving an audience | No easy way to ship their rankings as a tool | Upload a rankings profile that drives every "Mine" surface |

## Problems & Pain Points
**Core problem:** Fantasy tools are either generic (rankings that don't know *your* league) or fragmented (a different site for ADP, trades, lineups, projections). Managers make big decisions on gut or on numbers that were made up.

**Why alternatives fall short:**
- Rankings/calculators use hand-picked or crowd-vote values, not what players and picks *actually* trade for.
- Nothing is synced to your real leagues — you retype rosters and settings everywhere.
- Draft tools give you a static cheat sheet, not live, adaptive coaching for the pick in front of you.
- Multi-league managers have no single cockpit.

**What it costs them:** A busted draft or a lopsided trade costs a whole season. Time lost tab-switching between five tools. The nagging feeling they left value on the board.

**Emotional tension:** Draft-day anxiety ("am I screwing this up in real time?"), FOMO on the league-winning move, and the sting of getting fleeced in a trade in front of friends.

## Competitive Landscape
**Direct:** DynastyLeagueFootball (DLF), Dynasty Nerds, KeepTradeCut, FantasyCalc, Statchasers, Flock Fantasy white-labels (Land Draft Guide, DFF) — dynasty/draft toolkits. Fall short: values are crowd-vote or editorial, tools are siloed, and most aren't deeply league-synced or fit from real transaction data. **[CONFIRM competitor list]**

**Secondary:** Sleeper's own native app tools + generic ranking sites (FantasyPros). Fall short: rankings aren't personalized to league context; no trade engine or season sim depth.

**Indirect:** A spreadsheet, a Discord full of takes, or "just wing it." Falls short: no data, no memory, no live coaching.

## Differentiation
**Key differentiators:**
- **Real-market pricing.** Trade and pick values are fit from real Sleeper trades and crawled Sleeper ADP — not a made-up table.
- **League-synced war room.** Pulls all your real Sleeper leagues (ESPN/Yahoo expanding) into one place; writes lineups back to Sleeper.
- **Adaptive live draft coaching** — a game plan that ticks through your picks, phase directives, and a live per-pick grade, not a static sheet.
- **Breadth in one product** — draft, ADP, trades, lineup/waiver, season sim, betting context — that competitors split across separate tools.
- **Creator rankings profiles** — publish your board and have it drive every surface.

**How we do it differently:** Instrument the real market (crawl drafts/trades, fit models) and bind everything to the user's actual leagues, rather than shipping generic content.

**Why that's better:** Decisions are grounded in what really happens in leagues like yours, in the moment you're deciding.

**Why customers choose us:** It's the only tool that's *theirs* — their leagues, their format, their board — with numbers they can trust.

## Objections
| Objection | Response |
|-----------|----------|
| "I already use [KTC/FantasyCalc/DLF] for free." | Those are crowd-vote values in a silo. Vault prices off real trades, syncs your actual leagues, and does draft + lineup + trades in one place. Base tier is free. |
| "Is this another paid subscription?" | Nope — Vault is free this season. No paywall, no credit card. Just connect a league. |
| "Will it actually work with my league?" | Live Sleeper sync by username; reads your real rosters, settings, and scoring. ESPN/Yahoo expanding. **[CONFIRM]** |

**Anti-persona:** The ultra-casual one-league player who sets a lineup twice a season and doesn't trade — the depth is wasted on them. Also non-Sleeper-primary users until ESPN/Yahoo writes land.

## Switching Dynamics
**Push:** Got fleeced in a trade / busted a draft; tired of five tabs; generic rankings that ignore their league.
**Pull:** A single synced war room, real-market values, live draft coaching, one-tap optimal lineup.
**Habit:** KTC/FantasyCalc muscle memory; Sleeper's native tools being "good enough"; their Discord's takes.
**Anxiety:** "Do I have to re-enter my leagues?" (no — sync), "Is my data safe?", "Will the paid tier actually be better than the free stuff I use?"

## Customer Language
**How they describe the problem:**
- **[NEEDS INPUT]** — pull verbatim from your Discord/DMs/Reddit. Likely candidates: "don't want to blow my draft," "did I win this trade?," "who do I start."
**How they describe us:**
- **[NEEDS INPUT]** — first real user quotes.
**Words to use:** war room, board, your leagues, real trades, on the clock, the call, fair value, movers, optimal.
**Words to avoid:** generic "AI-powered" hype; "algorithm" as a black box (competitors lean on it — we show the data); anything that sounds like a casino when near advice.
**Glossary:**
| Term | Meaning |
|------|---------|
| Vault / war room | The connected cockpit for a manager's leagues |
| Draft Vault | The live draft assistant surface |
| Grade Keys | 4-factor player grades (Upside/Floor/Risk/Situational) |
| ADP Explorer | Board/snake view of average draft position + movers |
| Trade Center | Matchmaker / exploit finder / fair-value engines |
| Command pages | Lineup / Waiver / Trade command surfaces |
| Season Sim | Simulated season outcomes / playoff odds |
| Rankings profile | A named board (yours or a creator's) that drives "Mine" surfaces |

## Brand Voice
**Tone:** Confident, sharp, a little insider — talks like a smart league-mate, not a corporate SaaS.
**Style:** Direct and plain-English; gives *the call*, not a hedge. Data-backed but never jargon-drunk.
**Personality:** Sharp, trustworthy, competitive, modern, no-nonsense. **[CONFIRM]**

## Proof Points
**Metrics (ownable, un-fakeable — lead with these):**
- Trade & pick values fit from **251,314 real Sleeper trades** across **26,282 leagues** (rolling ~430-day window).
- ADP built from **38,566 real Sleeper drafts** (**5.3M+ picks**).
- These refresh on a cron, so the numbers grow — round down when citing publicly (e.g. "250,000+ real trades," "38,000+ real drafts") to stay durable.
**Customers:** **[NEEDS INPUT]** — early users, notable leagues/creators.
**Testimonials:** **[NEEDS INPUT]**
> "[quote]" — [who]
**Value themes:**
| Theme | Proof |
|-------|-------|
| Real-market values | Fit from 251,314 real Sleeper trades / 26,282 leagues + ADP from 38,566 real drafts (`data/trade_market.json`, `data/sleeper_adp_stats.json`) |
| Your leagues, synced | Live Sleeper sync; lineup write-back |
| Live draft coaching | Adaptive plan + per-pick grade + phase directives |
| All-in-one | Draft, ADP, trades, lineup, waiver, season sim, betting context |

## Goals
**Business goal (2026):** Land-grab. Get as many managers as possible in the door and *falling in love* with Vault this season — free, no paywall. Optimize for activation, retention, and word-of-mouth, not revenue. Build the base and the testimonials/proof that make later monetization easy.
**Conversion action (this season):** Connect a Sleeper league (the activation moment) → come back for a draft / trade / lineup decision → tell a league-mate. The "north star" is a synced, returning manager.
**Current metrics:** **[NEEDS INPUT]** — current MAU / connected leagues / retention, if tracked.

## Changelog
*Newest first. One line per revision: what changed and why.*
- v2 (2026-08-20) — Repositioned 2026 GTM to free/love-first (no public pricing this season) per founder call; rewrote Business model, Goals, and pricing objection; added ownable proof metrics (251,314 real Sleeper trades / 26,282 leagues; ADP from 38,566 drafts / 5.3M picks).
- v1 (2026-08-20) — Initial context, auto-drafted from the app, changelog, monetization research, and competitor recon; open items flagged [CONFIRM]/[NEEDS INPUT].
