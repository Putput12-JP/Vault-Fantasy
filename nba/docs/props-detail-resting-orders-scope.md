# Resting-orders strip on the new Player Props detail page: scope

Written 2026-11-18 (Central). Scope only: this PR adds this document and changes nothing a player sees.

## The gap

PR 449 added a "Resting orders" strip to a prop's Novig card (`pvNovig` in `nba/ui/projections.template.html`, inside the old Sharp money
section of `pvDetail`). The Player Props page now draws its detail from `nba/ui/props_board.js` (`PBX.detail`, cards `pbx-card2`), which has no
Sharp money section and never calls `pvNovig`. Checked in the running page on 2026-11-18: Amen Thompson points (Novig depth $83 over, $2,104 under
at 15.5) shows no strip, and the old `#pv-detail` container is empty. The strip is live on Steam Chaser (PR 451) and nowhere on Player Props.

This is the same strip, the same data and the same wording. It is a market fact, not a signal.

## Proposed change (one PR after this one)

- **Where:** a new `pbx-card2` card, "Resting orders", in the right rail of `PBX.detail`, between the Prop signals card and the Line movement card.
  It is a card of its own so it is never read as one of the five signal checks, and it never counts toward "N of 5 agree".
- **What:** the existing logic, moved as is. From `PS.live.novig.props["<pid>|<stat>"]`, the rung nearest the prop's line that has per-side depth
  (`dp`); over and under dollars within 3 cents of each side's best bid; a two-tone neutral bar; "Over $X · Under $Y at <line>"; the heavier side
  in bold only when it clears the registered `p_dep` thresholds ($500 and 2x). Hidden when under $100 total, as today.
- **Wording:** the card keeps the "untested" badge and the line "Offers within 3 cents of each side's best bid on Novig, not trades. Untested as a
  signal: the test is registered and reads on or after Dec 7." Neutral colours only: no green or red, no arrow, no ranking.
- **Not in it:** no Kalshi depth (the board has top-of-book sizes in `r.kal`, but the Kalshi test has its own registration and is not read until it
  clears), no US-book gap, no new data file, no change to Top Reads, SM_GATE, Sharp Plays, an agree total, or any record.
- **Both sides of one prop:** the card shows the prop's depth once, not per Over/Under row, because the depth belongs to the market, not the side
  being viewed.

## Files

- `nba/ui/props_board.js`: the card and its CSS (this file inlines into the page through `render_app.py`).
- `nba/projections.html`: rebuilt by `render_app.py`, not edited by hand.
- Changelog: the NBA page has no changelog array (the `VAULT_CHANGELOG` rule in CLAUDE.md is for `index.html`), so none is added. To confirm
  at build time.

## Open PRs and branches to avoid colliding with

- **`nba-props-chips-unify` (pushed, no PR):** edits `nba/ui/props_board.js` and `nba/projections.html`. Build this after it lands, or stack on it.
- **PR 304** (`perf/nba-lazy-data2`) and **PR 305** (`perf/nba-motion`): both edit the generated `nba/projections.html`. Neither touches
  `props_board.js`, but the rebuilt page will conflict textually until they merge. CLAUDE.md says to avoid editing a file another open PR is
  changing, so the build waits for them or rebases onto them.

## Verification when built

Run the app (Putput) and look at it: desktop and phone width, light and dark, a prop with depth, a prop with none (card hidden), and a prop whose
Novig ladder has no `dp` (card hidden). Confirm the Steam Chaser strip is unchanged.

## Model/data and UI numbers for that PR

No model or data change. UI: one new card; no existing number changes.
