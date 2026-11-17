# Exchange depth against a side (pre-registered, shadow, context only)

Written 2026-11-16 (Central), before any `p_dep` alert exists, let alone is graded. Origin: a teardown of BetSniper's Smart Money
page, which lists NBA props where exchange resting orders are stacked on one side and calls that "sharp money". Its own text
says it is not an EV figure and shows no record, so nothing there is evidence. This test asks the question with our data and a
rule written down first.

## What was added

- `novig.read_book` now also returns `dp`: the top-of-book dollars per outcome (within 3 cents of that side's best bid). `depth`
  is still their sum and is unchanged.
- New day file `snapshots/<day>/novigdepth.jsonl` (`novig.depth_quotes`, recorded by `snapshot.py` beside `novigprops`): per prop
  strike, the over side's `[bid, ask, over depth, under depth]`, depth rounded to $100. Same carry-forward as `novigprops`.
- `p_dep` alert (`sharp.py` `dep_prop_signals`): a strike with a tight two-sided quote (spread no wider than 10 cents,
  `novig.TIGHT`), pre-tip, where one side has **$500 or more** at the top of its book **and at least 2x** the other side's.
  The alert is the heavier side. One alert per game, player, stat, strike and side; the first sighting keeps its time and price.
- `fair` on the alert is that side's Novig mid at first sighting. The existing grader (`grade_prop`) sets `clv` = Pinnacle's
  no-vig close at the same line minus `fair`, and `result` from the box score. No grader change.

Frozen now: the $500 floor, the 2x ratio, the 10 cent spread cap, the $100 rounding, one alert per strike and side. Chosen by hand,
not fitted. The floor sits near the middle of the $254 to $2,042 liquidity range seen on BetSniper's board on 2026-11-16; that is
the only thing it was set from.

## What is NOT known

- Per-side depth was never stored before 2026-11-16 (`novigprops` keeps only the both-sides total to the nearest $250). **There is
  no history to backfill and no backtest.** The first alert is the first data point.
- Whether resting orders say anything about sharpness. They are offers, not fills, and Novig accounts are anonymous.
- BetSniper's Pinnacle limit and xLimit columns are not reproduced.

## What is graded

- **Closing-line value** against Pinnacle's close at the same line (`pinclose.json`). Because the two sides' mids sum to one, the
  other side's CLV is the exact negative, so picking the side at random averages zero by construction. A positive mean means the
  heavier side is the side the close moved toward.
- **Result** (win, loss, push) for context only. It is not the pass rule.
- Descriptive only, no pass rule: CLV split by depth bucket ($500 to $999, $1,000 and up) and by stat.

## The rule

At the **first look**, once **100 graded `p_dep` alerts** exist and not before **2026-12-07**, the signal passes only if:

1. Mean CLV is above zero with **t >= 2**, standard error **clustered by game** (props in one game share news and are not
   independent).
2. Mean CLV is positive in **both halves** (the first 50 and the last 50 alerts, by alert time).

Anything else is a NO-GO: the field stays an explainer on Sharp Money, with the result written to the decision log. No threshold,
bucket or market is changed after the first look; a new version is a new pre-registration.

## Known limits

- CLV here compares a Novig quote with Pinnacle's close, a different venue, so it measures agreement with Pinnacle as much as
  drift. A pass means "heavier side agrees with where Pinnacle ends up", not "beats a soft book". A price edge against the books
  is a separate test and would need its own registration.
- Novig lists props close to tip and rotates its reads across polls, so an alert can be timed a few polls after the depth appeared.
- Context only. `p_dep` feeds no Top Reads, no SM_GATE and no agree total, and no page shows it yet.
