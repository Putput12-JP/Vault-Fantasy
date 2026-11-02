# Near-exact side pockets: forward test (frozen Nov 2, 2026)

Written before any game it scores. The code is `FORWARD` in `nba/scripts/near_record.py`; the Track Record page reads it under
Near-exact calls → Forward test.

## Where the pockets came from

Every scored prop from Oct 21 to Nov 1, 2026: 3,201 props with a side (the projection off the line, no push), each prop's last projection
before tip, players who played, roster-guard holds left out. "Side won" means the result landed on the side of the line our projection sat.
Return is 1 unit at the no-vig price stored with the prop (`psim` p_price), so it is before any book's cut.

| | Props | Side won | No-vig break-even | No-vig return |
|---|---|---|---|---|
| All props | 3,201 | 54.1% | 52.6% | +2.3% |
| Assist unders, sportsbook line | 280 | 59.6% | 53.7% | +11.2% |
| 3-pointer overs, sportsbook line | 326 | 56.1% | 52.1% | +9.4% |
| Rebounds, projection 1 to 2 off the line | 149 | 61.1% | 53.3% | +13.1% |
| Starter unders | 1,208 | 57.0% | 53.7% | +6.2% |

About 80 slices were looked at to find these four, so some of what they show is luck. Clustered by game (props in one game move together),
the 95% range on the no-vig return was +0.5% to +22.4% for assist unders and +0.2% to +12.7% for starter unders; the other two crossed zero.
None of them was clearly ahead after a typical book cut.

## The four pockets (frozen)

| id | Rule |
|---|---|
| `ast_u_books` | assists, projection under the line, the line from a sportsbook |
| `3pm_o_books` | 3-pointers, projection over the line, the line from a sportsbook |
| `reb_gap_1_2` | rebounds, projection 1 to under 2 off the line, either side, any source |
| `starter_u` | the player started (box score starters), projection under the line, any stat, any source |

`starter_u` reads the starters from the box score. Starting lineups post about 30 minutes before tip, so a bettor knows them; a late
scratch can make it differ from what was known at the last projection.

## Scoring

- Props that tip on or after **Nov 3, 2026** (Eastern day) only. Nothing from the discovery window counts.
- Same rules as the discovery: last projection before tip, played, not held, pushes and projection-on-the-line left out.
- **Read on Dec 1, 2026.** Before then the page shows the running count and says it is not read yet.

## What passes

A pocket passes when both hold on Dec 1:

1. No-vig return above **+4.5%**, about what -110 on both sides costs, so the pocket would still be ahead after a typical cut.
2. The lower end of the 90% range on its win rate (Wilson) is above its average no-vig break-even.

A pocket that passes is a candidate for a bet rule and its own backtest on prices actually offered; it is not a bet signal on its own.
One that fails is dropped. Changing a rule makes a new test with a new start date.
