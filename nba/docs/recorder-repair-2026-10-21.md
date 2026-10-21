# Recorder repair, 2026-10-21: opening night has no shadow bets, and why

Written after the Track Record said "612 shadow bets, 0 settled" with three games final. Three separate things were going on. This page says which is which, with the numbers, so none of it is guessed later.

## 1. The shadow ledger poll was dying (fixed)

From 2026-10-19 19:01Z to 2026-10-20 21:44Z, 184 consecutive polls (56 in the Oct 19 folder, 128 in the Oct 20 folder) raised `'NoneType' object is not subscriptable`. One player in `model_state.json` had a null `ms` (minutes record). The error was in `ledger.minutes_log`, which runs after `ledger.log` and before the simulation records and `settle()`. Commit 3c56a2996 fixed that one expression. This change fixes the class:

- `Pricer` drops null player records and null fields on load (a null means "not known", the same as absent).
- `price_board`, `minutes_log`, `sim_record.log` and `prop_sim_record.log` skip one bad row and count it (`pricing.row_error`) instead of raising.
- `snapshot.shadow()` runs each stage on its own (log, minutes, simulation, props simulation, Novig paper, settle). A stage that raises is named in the poll record (`ok:false`, `err`) and the rest still run, so settlement no longer stops with it.
- `check_ledger_robust.py` checks all of that without a network.

Pricing is unchanged: `check_pricing_regression.py` on this branch against its parent is IDENTICAL on the example board (640 candidates), v2 minutes, v3 minutes and v3 with starters.

What the failure cost: no Minutes Lab, Game Simulation or Props Simulation rows for BOS @ DET (it tipped in the window), and no `settle()` for 184 polls. What it did NOT cost: bets. `ledger.log` ran and wrote before the line that raised (the failed polls say `n:0`), so the ledger rows were real.

## 2. Why PHI @ NY, OKC @ SA and BOS @ DET have no shadow bets (by design, not a bug)

`pricing.roster_hold` holds a team when the minutes model projects fewer than 8 of its players, or anyone at 44+ minutes, or the rescale to team minutes stretched everyone by 1.10 or more. A held prop is priced and shown, never a Bet, Lean, edge or shadow bet (`ledger.log` skips it). On opening night, after a summer of roster turnover, the guard held every team in these games (the model state on hand, which the recorder also had for the last 2 hours before each tip):

| Team | Players known | Top minutes | Stretch | Held because |
|---|---|---|---|---|
| BOS | 11 | 46.8 | 1.35 | top 44+ and stretch |
| DET | 11 | 48.0 | 1.45 | top 44+ and stretch |
| PHI | 6 | 37.2 | 1.00 | fewer than 8 players |
| NY | 13 | 42.7 | 1.15 | stretch |
| OKC | 11 | 38.3 | 1.10 | stretch (exactly at the line) |
| SA | 12 | 42.4 | 1.14 | stretch |

Replaying every stored poll of each game's 24-hour window through the same `ledger.log` (`replay_polls.py --check-ledger`): BOS @ DET 159 polls, PHI @ NY 173, OKC @ SA 188. In each, every candidate that reached the 3% edge was held (20,663 of 20,663; 17,237 of 17,237; 25,992 of 25,992 candidate-polls) and 0 rows were logged. That matches the live recorder's `n:0`. So the Track Record is right that these games have no shadow bets: there was no honest bet to settle. **Nothing was backfilled for bets and nothing should be.** Relaxing the guard to get a record would be inventing one; the guard's thresholds are measured (docs/moved-players-results.md).

From now on the Data Health page says this out loud ("N edges of 3% or more, all held by the roster guard") so an empty Track Record is not read as a broken recorder.

## 3. BOS @ DET was missing from Game Simulation (replayed)

`replay_polls.py` rebuilds each stored poll's board from `snapshots/<day>/*.jsonl` (cut off at the next poll's start) and calls the same `ledger.minutes_log`, `sim_record.log`, `prop_sim_record.log` the recorder calls. Every row written carries meta `"replay":1`; `snapshots/<day>/replay.json` records what was replayed and at which commit; settling copies the flag to the Game Simulation entry, the Props Simulation entry, the Biggest gap pick, the Minutes Lab day (`replay` = players) and any bet (none exist).

It is only as faithful as the stored prices allow:

- **Model state is the one on hand, not point in time.** The last daily refresh of `model_state.json` and `player_projections.json` before the replayed polls was 2026-10-20 16:44Z. The rows a game is scored on are its last pre-tip rows (after 16:44Z), but earlier replayed rows used a newer state than the recorder had.
- **Not stored, so not replayed:** Kalshi book sizes and Polymarket depth (priced rows do not read them) and the Novig order books (Novig paper trading is not replayed; BOS @ DET has no Novig paper rows).
- **Checked against live rows.** Replaying PHI @ NY (which has live rows from 21:47Z) and comparing: minutes 85 of 85 identical at the same poll, Game Simulation 1,856 of 1,856, Props Simulation final pre-tip rows 55 of 55. Not identical: the intermediate Props Simulation `p_price` (the market price anchor) in 154 of 346 comparable rows, almost all on props with a Polymarket quote. Final rows, the ones scored, matched. The Biggest gap pick for BOS @ DET is chosen from last-row p_price, so treat it as replayed.

What it wrote for BOS @ DET (2026-10-19 and 2026-10-20 folders): minutes 29 players (150 change rows), Game Simulation 3 environments (694 rows), Props Simulation 57 props (869 rows; held, tagged `held:team`, not scored in the log-loss sums, only used for the Biggest gap pick).

Running it: `.github/workflows/nba-repair.yml` (manual, after this merges), or locally `python3 nba/scripts/replay_polls.py --dir=<nba-data checkout> --games=401909088 --write`. It refuses today's ET folder (the recorder appends to it), only adds a source for a game that has none in that folder, and merges rows in time order, so running it twice writes nothing the second time. The recorder's next poll settles the replayed rows into `track.json` (`settle()` re-reads the last 3 days, so run it within 3 days of the game).

## 4. One DraftKings

ESPN's odds feed names its provider 100 "DraftKings" on some polls and "Draft Kings" on others. A recorder row's meta keeps whichever name it saw first, and the board labels a game's props by the last name it read, so one quote flipped between two ledger keys and was logged as two bets. 79 of 90 DraftKings quotes in the record were double counted (169 bets, 90 quotes).

`nba_common.book_name` is the one spelling. It is applied where the recorder writes (`snapshot.src_espn`), where the board reads (`prop_board`), where the ledger logs (`ledger.log`, and tracked keys are matched canonically so no tracked candidate is dropped), and where history is read (`ledger.load_ledger` merges the two spellings into one series; `settle()` collapses stored bets, the recent list and the cube). The raw `ledger.jsonl` and `meta.jsonl` files on the data branch are left as recorded; readers normalise.

## 5. Data Health flags

`snapshot.write_flags` writes `flags` into `status.json` every poll; the Data Health page shows them above the KPIs:

- **Needs attention:** the shadow ledger failed 3 polls in a row (`LEDGER_FAIL_N`; the GitHub watchdog waits for 6); a game inside the 24-hour window has no Minutes Lab rows; a game inside 4 hours has no Game Simulation rows.
- **Check:** a poll skipped bad rows (with the count and the first two).
- **Note:** a game has 3% edges and all are held by the roster guard.

The ledger line in the Sources table says the same ("N edges of 3%+ within 24 hours of tip, all held by the roster guard").

## 6. Held props get a record of their own (added the same day)

The box scores of a held game settle hundreds of priced props, but a held prop is never a shadow bet and `score()` leaves it out of the log-loss sums, so the Track Record showed W/L for 3 of them (the Biggest gap picks). `prop_sim_record.record_held` settles every held prop the props simulation recorded (the last pre-tip psim row: points, rebounds, assists and 3-pointers on the main line) into `track.json` `held_days`, and Track Record shows it as "Held by the roster guard, not bets".

- Model's side = the side the model gives 50% or more (the same rule as the Biggest gap pick). Price chance = the price's chance for that side, vig removed (blank for a flat pick'em line). Result W / L, P (landed on the line), D (did not play).
- Not a bet record: no stake or payout is stored, so no profit number. It is judged on hit rate against what the price expected and against what the model expected, with a z score once 100 priced props are in.
- Nothing reads `held_days` except that card: not the cube (season record), not the GO / WATCH verdicts, not a signal's 50-bet promotion count. Preseason goes to `preseason.held_days`.
- Fills itself: psim already records held props (the Oct 20 change), and `settle()` rebuilds the last 3 days every poll. Prop rows are kept 14 days; older days keep their sums.
- Not covered: other markets (combos, steals, blocks and so on) are not recorded per game, and a prop the recorder never got a main line for.

## 7. The GO and WATCH plays a hold kept out (added Oct 21, after "there were GO and WATCH plays last night")

There were. At every poll in each game's window the roster guard held the team, and the held Kalshi candidates carried the gate: 3PM NO (GO) and PTS / REB / AST YES (WATCH). The page and the recorder agree on the hold (same numbers, six teams, final pre-tip poll: BOS 11 players known, top 46.8 min, stretch 1.35; DET 11, 48.0, 1.45; PHI 6, 37.2, 1.00; NY 13, 42.7, 1.15; OKC 11, 38.3, 1.10; SA 12, 42.4, 1.14; run through `pricing.roster_hold` and the page's `rosterHold` on the same board), and the Props page, Edges and Pick'em of the Night all drop held props ("No call: roster guard"). So nothing disagreed. What was missing is that a held candidate left no trace in the Track Record at all, whatever its gate.

- `ledger.log` now also writes the held candidates that carry a GO or WATCH gate (the better of the model's gate and the consensus gap's, when that edge reached 3%) to their own source, `heldbets` (key and value like the ledger's, meta `hold` = why). They are never bets: not in `ledger.jsonl`, the cube, the season record, the GO / WATCH verdicts or a signal's 50-bet promotion count.
- `ledger.held_bets_record` enters each at the first poll its edge reached 3%, closes it at the last poll before tip and settles it from the box score exactly like a bet (`bet_from`, `grade`): `track.json` `held_bets_days`, rows kept 14 days, one unit each at the stored entry price with the Kalshi fee. Only GO and WATCH gates; a hold keeps sportsbook and pick'em candidates out of it, as before.
- Opening night was filled in by `replay_polls.py` (source `heldbets`, flagged replay): the same `ledger.log` on every stored poll in each game's window, with the model files on hand rather than the recorder's files at the time.
- A Kalshi ladder gives several rungs of one pick, so bets are rungs and the card also counts picks (player, stat, side).
