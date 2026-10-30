# Steam Chaser NBA: Novig prop moves and agreement (shadow, context only)

Written 2026-10-30 (Central), before any `p_nov` alert has been graded. Follow-up to `steam-chaser-backtest.md`: Pinnacle-only prop moves are a NO-GO as a bet, so this adds a second reference and logs both, and the page (`sharp-money/steam-chaser/`) calls nothing a bet.

## What was added

- `p_nov` (sharp.py `nov_prop_signals`): the over side's mid at one Novig strike moved 5 points or more within an hour, same rule, 25-minute poll gap and 3-hour cooldown as the Pinnacle prop move `p_pin`. Mid needs bid and ask both present and no wider than 10 cents (`novig.TIGHT`). Source: `novigprops` (PR 310), rows carried forward between rotated reads, so a move is timed at the poll that read it.
- `steam_agree`: for each reference alert (`p_pin`, `p_nov`, `p_kal`, `p_acct`) the number of different reference venues that moved the same side within an hour. Written on each alert as `refs` and `agree`. Not an agree total, never added to one.
- `board.sharp.nov`: the `p_nov` alerts per prop, apart from `board.sharp.props`, because the Player Props page has no label for the type yet. They are saved and graded like every other `p_` alert (CLV against Pinnacle's close at the same line, result from the box score).

## What is NOT known

- The 5-point threshold is the Pinnacle one reused, not fitted. Novig prop history started 2026-10-30; nothing is backtested.
- CLV for `p_nov` compares Novig's mid at the alert with Pinnacle's close, a different venue, so it measures agreement with Pinnacle as much as drift.
- Props rotate across polls (80 requests), so a Novig read can be a few polls old.

## Rule, fixed before grading

Context only. First look at 100 graded `p_nov` alerts: mean CLV at the same line with its standard error, and the share positive. Until then no verdict. Agreement is judged only after 100 graded alerts with `agree` of 2 or more exist; the comparison is their CLV against alerts with `agree` of 1. A result is a hypothesis for a forward test, not a go.
