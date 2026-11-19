# CBB money vs bets, with the line moving their way: forward test (registration)

**Status: Registered.** Proposed on 2026-11-19 and approved by the user as written the same day, with every decision below taken as proposed. The commit that changes this line from PROPOSED is the registration: its hash and time are the proof that
the rule came first. Nothing below may change after the first counted game is graded. A change means a new registration with its own date.

Sharp money is context only (CLAUDE.md). This is a measurement. It is not a bet signal, not a size, and it never feeds Top Reads, SM_GATE or an
agree total.

## Why this exists

A public post (ClosingDime) and the Nov 19 West Virginia at Florida page (`cbb:309762`) show a pattern: most bets on one side, most money on the
other, and the number moves toward the money. On that game WVU had 40% of spread bets and 71% of the money, and the consensus spread went from
WVU +8.5 (open) to +7.5. Nothing is stored that can test this on history: the CBB line tape starts 2026-11-19, bets/money splits are not kept
per game anywhere, and there are no CBB closing lines or final scores in the repo. So this can only be tested forward. No past result is used.

## What is logged

`scripts/cbb_split_move.py log`, run from the Sharp Money workflow (`update-sharp-money.yml`, the tape step), freezes one row per CBB game at the
**first run 30 to 90 minutes before tip**. It stores the consensus spread and total, their opening lines, Pinnacle's lines, the Action Network
bets % and money % for both sides, and the cell the game falls in. A frozen row is never rewritten; only `result` is added after the game.
Games with no lock inside the window are not logged and are counted as missed in the report.

## Cells (spread, primary)

Side line = points the side receives (away = minus the home spread). "Toward" = the side's number at the lock is worse for backers than at the
open, in points (WVU +8.5 to +7.5 is 1.0 toward).

| Cell | Rule |
|---|---|
| **treat** | the side's money % minus its bets % is **20 or more**, it holds **45% or less** of bets, and the line moved **1.0 or more toward it** |
| **split_only** (control 1) | same split, line moved **less than 1.0** toward it (including moves against it) |
| **move_only** (control 2) | the line moved **1.0 or more toward** a side whose money minus bets gap is **under 10** |
| none / nosplit | everything else. `nosplit` = no bets/money split stored for the game. Both are counted, not graded |

A game falls in one cell. The finding is **treat against both controls**, not treat alone.

## Cell (total, secondary, one cell)

**rlm:** one side holds **70% or more of bets** and the total moved **1.0 or more toward the other side** since the open. The play is the
side the line moved toward (heavy over bets and the total drops: under). Reported by itself, with no controls.

## Result and measures

- **Bet:** the cell's side at the frozen consensus number and the stored consensus price, flat 1 unit. A push is 0. Graded on the final score
  from the same ESPN finals the Sharp Money page already stores.
- **ATS and ROI:** record, and units per bet.
- **Line CLV (points):** the side's Pinnacle number at the lock minus Pinnacle's last stored number at or before tip (the tape), same book both
  times. Positive means a follower had a better number than the close. Not available if the tape has no Pinnacle row before tip; those are
  counted. This is a line comparison only; no points-to-probability conversion is used.
- **Intervals:** 95% percentile bootstrap, 10,000 resamples, seed 20261119, resampling games.
- **Coverage (reported every time):** locked, counted, `nosplit`, `none` and missed games. On Nov 19, **59 of 84** CBB games had no split
  stored, so this test only sees the share of games the splits feed covers. That limit is stated in advance.

## Which games count

Locks at or after **2026-11-20 00:00 CT** (epoch 1795154400, `REGISTERED_FROM` in the script). Earlier locks are kept with `counts: false`
and are not in the record. Today's WVU/FLA and Oregon State/Oregon rows are examples, not evidence.

## Pass rule

Read once, at **300 graded treat games** or Selection Sunday (March 14, 2027), whichever is first. A pass needs all of:

1. treat ROI above 0 with its 95% interval's lower bound above 0, and
2. treat ROI above **both** controls' ROI by more than the 95% interval of the difference, and
3. treat mean line CLV above 0 with its interval's lower bound above 0.

Fewer than 300 at the end is "not proven". A pass would only allow a **context label** on the Sharp Money game page ("money and line agree,
untested"); it adds nothing to Top Reads or any agree total, and a label is a separate pull request.

## Reporting

Monthly, report-only, in `data/cbb_split_move_record.json` (`scripts/cbb_split_move.py report`). Any slice that looks better (a conference, a
spread size, a time of day) is flagged for close monitoring with its sample size and is **not** promoted on the same data. Thresholds (20, 45,
1.0, 10, 70, the 30 to 90 minute window) are not tuned to the output; if they fail, the next step is a new registration, not a new cut.

## Known limits, said in advance

- Money % is handle at US books (Action Network consensus). One large ticket can move it, and it says nothing about who bet.
- The lock is a single snapshot. A move that happens after the lock is not in the treatment (it shows up as CLV).
- Late-announced injuries can move a number for reasons unrelated to money. They are not filtered, in either direction.
- The finals feed keeps a game for about five days. A game whose final is missed is reported as ungraded, not estimated.
