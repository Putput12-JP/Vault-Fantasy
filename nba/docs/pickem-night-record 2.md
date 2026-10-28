# Pick'em of the Night record (rules written before any result, 2026-10-21)

Every night the page builds the best slip of each size (2 to 6 picks) on each pick'em app. This records those slips and settles them from the box score, so the page has a record. Code: `scripts/pickem_record.py`; check: `scripts/check_pickem_record.py`; shown on the Pick'em of the Night page and on Track Record (`track.json` `pkn_days`; preseason apart in `preseason.pkn_days`).

- **Legs and slips are the page's rules ported line for line** (`ppLegs`, `ppBuild`). Checked on the live board of 2026-10-21: 216 legs and the same joint chance for every size and app as the page (with the board's 24-hour window lifted, which the page does not have).
- **Lock:** the night's slate locks at the first tip of the tip day. Each leg is its last record before that moment; a leg withdrawn before it is out. Slips are per tip day: the page can mix two days when both are on the board, the record never does.
- **Settle:** when every leg's game is final. A lost leg loses the slip; else a leg on its line makes a push; else won. A player who did not play voids it. Per $1: won pays - 1, lost -1, push and void 0.
- **Pays** are the standard multiples (3, 5, 10, 20, 37.5). Underdog and Sleeper entries can carry their own multiples; the record does not know them.
- **Pass slips are tracked too** (the page shows them); "Lean only" is reported beside the total. **Best app** is not stored: the highest average per $1 that night for that size.
- **Descriptive, no verdict** until 100 slips of a size. It never feeds a bet, a Lean or a price.
- **History:** none existed before this change. A closed day can be filled from stored prices with `replay_polls.py` (the `pkn` stage was added); nothing is estimated by hand.
