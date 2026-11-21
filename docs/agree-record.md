# Agree-count record (NBA Game Lines signal board)

Context only. It is not a bet signal and feeds nothing else.

The board's "4 of 5 signals point to POR" is a live read and was never stored. This record rebuilds it from the stored alert logs
(`snapshots/<day>/signals.json`, nba-data branch) with `nba/scripts/build_agree_record.py`, output `nba/data/agree_record.json`.

## Rule (written before the first read)

- Signals: Pinnacle = steam, Sharp accts = sharp, Kalshi big = whale (Kalshi venue only), Novig = novig, Money = split.
- Moneyline and spread alerts only, since they name a team. Totals are left out.
- A signal's direction at a moment is the team with more weight in its alerts so far (dollars when stored, else 1). A tie is no direction.
- An agree event at level k (3, 4, 5, nested) is the first moment at least k signals point to one team and none point to the other, before tip. One event per game per level.
- Graded on the final score against Pinnacle's closing no-vig moneyline for that team ("won vs close"), and on closing-line value: closing fair minus the team's fair at the event, taken from a moneyline alert no more than 2 hours old. Missing means left out, never guessed.

## Limits

- Alert thresholds, not the page's cumulative state at a 0.06 cut, so a game the page called 4 of 5 can be 3 here.
- Backfilled over every stored alert (2026-10-03 to 2026-11-19). The backfill is in-sample for a rule written after seeing the page, so only games after 2026-11-19 are a clean forward test.
- Samples are small. No pass rule is set, so nothing here is a verdict.
- Refresh is manual for now: `python3 nba/scripts/build_agree_record.py <nba-data root> nba/data/agree_record.json`.
