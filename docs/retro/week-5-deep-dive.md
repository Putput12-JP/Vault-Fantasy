# Week 5 retro: NFL props and game markets

_Run Monday 2026-10-12 from `data/bet_results.json`, `best_bets_record.json`, `model_scoreboard.json` and the Vault Ledger database. 642 props and 14 games were settled; the Monday night game(s) and 2 other game slots were not on the tape yet. Prop units are at each side's own price, spreads and totals at -110, moneylines at the opening price. A/B grades are the point-in-time grades (model version live at first sighting)._

## The short version

1. **A quiet, near-flat week.** A/B props went 56-52, **-1.7u at the close** (+3.9u at the open). The full prop board lost 15.5u. Games went 20-19 for +2.2u. Nothing blew up, and nothing proved an edge.
2. **Week 4's fixes held.** Zero QB volume props (attempts, completions, passing yards) reached A/B this week, so the biggest Week 4 leak (-35u on QB props) did not recur. Real-book coverage at the open more than doubled, from 17% to 38%.
3. **Still no measurable skill over the market.** Prop log-loss skill against the no-vig close was -0.020 (z -1.7) for the week and -0.020 (z -3.2) for the season. Week 1-5 skill by week: -0.036, -0.014, -0.013, -0.019, -0.020. That is five straight weeks of being slightly worse than the market.
4. **Games again had no closing-line value.** Only 3 of 14 totals and 3 of 13 spreads moved toward Vault. The record is positive because the week was high scoring, not because Vault led the market.
5. **The Vault's Plays card was empty.** Every play-type bucket is switched off by the self-adjusting rules, so no Week 5 card was posted (last card update Oct 4). The ledger placed one bet and lost it.

## Surfaces

| Surface | Week 5 | Season |
|---|---|---|
| Vault Ledger ($1,000 paper) | 0-1, **-$20** (CIN @ MIA under 43.5, final total 55) | about -$20 on the season after Week 4's flat result |
| Vault's Plays (locked card) | no picks posted | 20-14, +5.6u (Weeks 1-4) |
| Strict tier (shadow) | 11-12, 5 voids, -2.4u | same, first week tracked |
| Held-back plays (shadow) | 5-5, -0.3u | 5-8, -3.3u |
| Withheld shadow picks | 9-9, 6 voids, +1.2u | n/a |
| **A/B props** | **56-52, -1.7u close / +3.9u open** | 387-356, **+11.2u close** |
| A/B excluding QB volume | 56-52 (no QB volume reached A/B) | 367-327, +21.7u close |
| C/D/F leans | 236-204, -6.6u | -106.3u |
| All leans | 338-304, -15.5u | n/a |
| Games, all | 20-19, +2.2u (spreads +0.4, totals +1.3, ML +0.6) | 4 of 5 weeks positive after a -11.0u Week 1 |

Caveat on the open column: my recomputed season open-price total for A/B (+58.6u) does not match last week's report (+29.9u through Week 4). Close-price numbers do match exactly (Weeks 1-3 +11.8u). I have not reconciled the open-price method, so lean on the close numbers.

## Props

**A vs B vs the rest.** A grades 31-27, +0.4u. B grades 25-25, -2.2u. D grades went 63-42, +11.3u, while C went 43-53, -15.0u. The grade ladder is non-monotonic for the second week running, so the letter is not separating winners from losers.

**By market (A/B).** Rush yards 16-11, +2.2u. Receiving yards 15-14, -0.7u. Receptions 13-15, -2.0u. Rush attempts 11-10, flat. Pass TD only 2 plays.
**All leans by market:** receptions +8.7u (88-65) and pass TD +5.1u (19-8) were the winners. Rush attempts -11.9u (30-39), pass completions -7.5u (8-15), passing + rushing yards -5.9u (9-14) lost. The model under-projects pass completions by 1.5 on average.

**Over vs under.** A/B overs 25-17, +5.5u. A/B unders 31-35, -7.3u. Season A/B overs are +11.3u and unders -0.1u, so the edge, such as it is, lives in overs. Heavy rushing unders lost: Gibbs under 90.5 (151), Braelon Allen under 71.5 (116), Croskey-Merritt under 55.5 (82), Gibbs under 19.5 attempts (25).
The all-lean picture is the reverse in sign: overs 194-177 and unders 144-127 both lost, because the C/D/F pile bleeds.

**Position.** RB A/B 26-20, +3.3u. QB 12-8, +2.4u. WR 14-18, -5.3u. TE 4-6, -2.1u.

**Calibration.** Model probabilities of 0.60 to 0.65 hit 51% (86 props) and 0.70 to 0.80 hit 55% (22 props). Same overconfidence found in Week 4. Lower buckets are fine.

**CLV.** A/B beat the close 52.8% of the time (49% in Week 4, 60% in Week 3). WR props beat the close 63% while losing money, which reads as variance rather than a leak.

**Data quality improved but is still thin.** Of the 108 A/B props, 61 had no real sportsbook at the open (29-32, -6.5u at the close), 42 had one or two books (24-18, +3.8u), and only 5 had three or more. The no-real-book bucket is where the damage sits, which supports the Week 4 call that a paid odds feed is the highest-value fix.

**Anchored shadow.** Grades anchored to the market (shrunk toward the no-vig price) went 12-8, +2.3u this week, and 45-35, +10.1u since Week 3 on a much smaller set of picks (80 vs about 450 for the live grades, which are -2.1u over the same weeks). Promising, small, and exactly the "decide after 2 more settled weeks" question from last week. Two more weeks are now in, so this is the decision point.

## Games

| | Week 5 | Weeks 1-5 |
|---|---|---|
| Spreads | 7-6 (1 push), +0.4u | 34-40, -9.0u |
| Totals | 8-6, +1.3u | 40-38, -1.5u |
| Moneylines | 5-7 (1 push), +0.6u | 30-29, +8.5u by my tally |

- **Scoring ran 2.9 points above the closing total** (46.8 actual vs 43.9). Seven of 14 games finished 8 or more over their number. Vault's total (45.1) was between the two, which is why overs 5-4 and unders 3-2 both made a little.
- **Closing-line value was poor again.** Totals: 3 toward, 8 away, 3 unchanged. Spreads: 3 toward, 3 away, 8 unchanged. The tape's CLV beat-rate is 25.6%.
- **Model accuracy:** spread error 1.8 points high, total error 1.7 points low. Scoreboard game skill this week +0.014 (z 0.4), season -0.017 (z -1.0): level with the market.
- **Biggest gaps (the "differs most" strip):** IND @ PIT over (+4.6) won, BAL @ ATL spread (+3.7) won, NYG @ WAS over (+3.7) won, LV @ NE spread (+3.5) won, CIN @ MIA over (+3.1) won, HOU @ TEN over (+2.9) lost, DET @ ARI spread (+2.3) lost. The big-gap plays went 5-2 this week after going 3-9 through Week 3, which is a reminder that 18 plays do not make a rule. Do not read this as the gap cap being wrong or right yet.
- **The Ledger's one game bet** (CIN @ MIA under 43.5 at +108) lost to a 55-point game. It also fought Vault's own number (Vault total 47.6 on the tape, the ledger note quoted 43.7).

## What to do next

1. **Decide the anchored grade switch.** Two more weeks have settled. It is the only structural change currently positive, but on a small sample. Suggest flipping it on for display with the live grade kept as a shadow, rather than switching the record.
2. **Rushing attempts and under-heavy rush yards.** Rush-attempt leans lost 11.9u across all grades; consider adding rush attempts to the weak-market cap list the way pass attempts was.
3. **Stop quoting the C/D/F pile in headlines.** D grades beating C is noise.
4. **Paid odds feed.** The no-real-book bucket is still the bad one. Still the user's call.
5. **Vault's Plays is idle by design.** The next time a bucket clears 15 plays at 5%+ return it comes back on; nothing to fix.
