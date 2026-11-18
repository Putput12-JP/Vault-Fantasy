# Vault NBA usability and usage audit, Nov 18 2026

Scope: all 18 pages in the left nav, desktop (1400 wide) and phone (390 wide). Screenshots are in `shots/<page>-desktop.png` and `shots/<page>-mobile.png`. Capture script: `shoot.mjs`. Raw text metrics: `metrics.json`.

Limit of this audit: the NBA app has no usage tracking (no `vfTrack`/GA events in `nba/projections.html`), so there is no page-view or click data. "Usage" below is judged from what each page asks a person to do, not from counts. Fixing that is item 1 of the plan.

## Answer to "keep Pick'em of the Night?"

Recommendation: take it out of the sidebar. Keep the forward test running in the background.

The page's own verdict card says it: no profitable slip found, every slip is a Pass, best rule 56.1% early and 53.8% late against a 54.2% to 59.1% pay-table need, and the old chance numbers ran 20 points too high. A page whose first screen explains why you should not use it, and then shows slips labelled PASS, is a research note, not a tool. Move the Record tab under Track Record, and bring the page back only if the Oct 27 rule clears its holdout.
Shot: `shots/pairs-desktop.png`

## Findings, worst first

### A. Text blocks nobody reads (the pattern you spotted)
| Page | What | Fix |
|---|---|---|
| Pick'em of the Night | Two stacked paragraph cards (about 285 and 150 words) push the actual slip below the fold on desktop, and on a phone the slip is more than one screen away. `pairs-desktop.png`, `pairs-mobile.png` | One line verdict plus a "Method" link. Slip first. |
| Track Record | The explainer line under every tab and a 400 character rule paragraph on the What Works tab. `track-desktop.png` | Cut to one line each, move detail behind the info icon that already exists. |
| Backtest Lab | Seven long captions (up to 231 chars) between charts. `btlab-desktop.png` | Chart title plus one short sentence. |
| Props Simulation | Confidence-level paragraph inside the player card ("Level 2 points props this season..."). `propsim-desktop.png` | Show the one number, link the rest. |
| Header subtitle strip | Every page has an all-caps mono line under the title ("EVERY LINE · EVERY VENUE · ONE TABLE"). It repeats the nav, is hard to read, and on Sharps carries a rule disclaimer. | Remove, or limit to freshness. |

### B. Dead ends and empty pages
| Page | Problem |
|---|---|
| Bankroll Builder | The Record panel says "private, sign in with the owner's Google account". For every visitor but one this page is two collapsed cards and a locked panel. `bankroll-desktop.png` |
| My Bets | Empty by default and says to go to Player Props. Fine as an empty state, but it is a full nav slot for a feature with a hidden start (Log bet inside a prop). `mybets-desktop.png` |
| Sharps | Rendered blank in this local run: a header, six tabs and nothing under them. Console shows 404s and a CORS block on the refresh worker, so this is probably the local data routing, not production. UNVERIFIED on the live site; check there before acting. `sharps-desktop.png` |
| Summary "Top sharp play" | Says "None open / Loading the Sharp Money ledger". `summary-mobile.png` |

### C. Numbers that confuse
| Page | Problem |
|---|---|
| Track Record | Headline "43123-41499-284, -5.5% across 84,906 settled bets" next to "0 distinct picks settled" and "Picks are counted from the latest 600 of 92,570 bets". Three different counts on one card, and the big number is a record of bets nobody was told to place ("Not a tip sheet"). `track-desktop.png` |
| Track Record | Counts disagree between desktop (92,570 bets) and phone (92,576) in the same minute. Likely just a refresh, but it reads as unstable. |
| Game Picks | Headline 95-114 against the spread, -27.65u, in the biggest type on the page. Honest, but it is the first thing every visitor sees on a page called "Picks". `games-desktop.png` |

### D. Layout and phone
| Page | Problem |
|---|---|
| Pick'em (phone) | Title truncates ("Pick'em of the Nigh") under the refresh button. `pairs-mobile.png` |
| Player Props (phone) | Good. Cards are readable, filters scroll. One note: 3,504 props with no default cap. |
| Slate | 11,452 px tall on desktop, 4,629 words. Longest page, no jump links. `slate-desktop.png` |
| Backtest Lab | 10,786 px, 4,525 words. Internal research on a public nav. `btlab-desktop.png` |
| Minutes Lab | Shows "274.4 of 240 minutes, 34.4 over 240" in red as the first thing on load, which looks like an error. `lab-desktop.png` |

### E. Overlap between pages (same job, several places)
- Game Lines, Game Picks, Game Simulation and Summary all show the same game with a line and a pick.
- Props Simulation, Player Props and Pick'em all price the same prop.
- Sharp Price (nav), Sharps, Follow Board, Wallets, Prop Tells, Steam Chaser: six sharp-money surfaces. The Sharps sub-tabs alone are six.
- Data Health and Backtest Lab are builder pages in a visitor's nav.

### F. What works
Player Props table with the Edge column and L5/L10 chips, Game Lines (each number labelled, "context, not a bet"), Slate expected-five cards, and Data Health. These are scannable and the first screen is content.

## Proposed order of work
1. Add usage tracking (page view, tab, Log bet, Share) so the next audit has data. Needs your OK because it is a user-facing privacy change.
2. Cut header subtitle strip and the long intro cards (A). Cheapest, biggest effect.
3. Demote Pick'em; fold Record into Track Record (needs your yes).
4. Make Bankroll Builder honest for visitors: hide or show a public record.
5. Fix the Track Record headline so one count and one verdict lead.
6. Group builder pages (Backtest Lab, Data Health) under one "Model" entry that is collapsed by default.
7. Check Sharps on the live site.

Nothing in the app was changed. Per CLAUDE.md, any change that affects tracking must also fix history; none of the above touches tracking except item 3, which only moves a tab.
