# Dropped plays audit (sharp-only picks removed from the bet record)

Question: the 96 plays taken out of the bet record when sharp money stopped being a bet signal. Is each one still stored with its raw graded result, and is anything deleted?

## Method

`node scripts/fetch-sharp-money.mjs --audit-dropped=<state.json>` loads a stored ledger state, copies the picks, runs the ledger migration (`migrateLedger`), and compares every pick before and after. A pick is "dropped" when none of its stored kinds is a bet signal (line, money, behind). The check is run on the live `sharp-data` branch `state.json` (written 2026-10-13, before the new ledger code has run in production, so it is the unmigrated history).

## Result

| Check | Count |
|---|---|
| Picks in the stored ledger before migration | 563 |
| Of those, graded (raw result stored) | 302 |
| Picks left in the bet ledger after migration | 470 |
| Dropped (sharp-only) and moved to the sharp-money context track | 93 |
| Dropped and graded | 87 (42 W, 44 L, 1 push) |
| Dropped and still pending | 6 |
| Dropped plays missing from the context track | 0 |
| Dropped plays whose stored result, side, market or line changed | 0 |
| Graded results stored after migration (bet ledger plus context track) | 302 (same as before) |

By sport (graded, W-L-P): CFB 18-15 of 35 plays, NBA 15-15 of 32, NFL 9-14-1 of 26. By market: spread 32 plays (30 graded), moneyline 37 (34), total 24 (23).

The migration moves a dropped pick into `sharpContext` with `dropped: true` and a copy of every field. It deletes nothing. Nothing needed restoring.

## About 96 versus 93

The earlier description counted 96 dropped plays from a 508-pick snapshot. The current snapshot has 563 picks and 93 sharp-only ones as stored picks. `--ledger` on the published `data.json` reports 94, because one more play is rebuilt from stored alerts. I could not reproduce 96 from any data in the repo or on `sharp-data` (that branch is force-pushed as one commit, so the older snapshot is gone). The audit proves the property for every sharp-only pick that exists in the data I can read. It cannot prove anything about plays that were absent from that data.

## Bug found and fixed

`gradePicks` only graded rows in `S.picks`. A sharp-only play that moved to the context track while its game was still pending would never get its result, so it would stay ungraded forever. 6 of the 93 were in that state. `gradePicks` now grades the context track as well, and the self-test covers a dropped pending play. On this snapshot none of the 6 games had finished, so the fix graded 0 today and would grade them when they end. 0 pending plays are currently stuck with a final score and no result.

## Not changed

Records. The 79-67-1 bet record (sharp removed) and the old 84-70 record are unchanged by this audit. Only the future grading of the 6 pending context plays can change the sharp-context record (currently 95-80-1 on 176 rows in the `data.json` ledger).
