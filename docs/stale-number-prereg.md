# Stale number: a book hangs the old line after the market moves (registration)

Written on 2026-11-19, before any row was graded. The commit that adds this file is the registration. The rules below change only by a new
dated registration. Sharp money is context only (CLAUDE.md): this is a measurement, not a pick, a size or an agree total.

Origin: a public post (ClosingDime, Cornell +19.5 at Fanatics) where the whole market moved the number from +22 to about +19, Pinnacle's price
and limit rose, and one soft book still hung the old number. `scripts/steam_record.py` already tests a Pinnacle **price** move at a **fixed
line** and finds the soft price about 1.1 to 1.3 points worse than the close (NFL, CFB, NBA). It skips line changes and does not count how many
books moved. This tests the part it leaves out.

## Data and scope

Replay of `data/book_tape` for NFL, CFB and NBA, spread and total only. Moneyline is excluded (no line to compare). **CBB is not covered**: the
tape has no CBB, so it can only be tested forward once a CBB tape exists. Only games that have started are graded. No result is estimated.

## Signal (treatment)

Per game, market (spread or total) and direction, the **first** time all of these hold at a tape row of Pinnacle at time t, where t is at
least 10 minutes before kickoff:

1. **Pinnacle moved the number.** Its line differs from its earliest stored line in the previous 90 minutes by T points or more.
   T = 1, 2 and 3 are reported. **The primary cut is T = 2.**
2. **The market agrees.** At least 2 other books (not Pinnacle, not Consensus or Open, not the lagging book) have a latest stored line that
   moved the same direction by 1 point or more since their own earliest stored line in the same 90 minutes. A book's latest line counts only if
   it is no more than 30 minutes old at t.
3. **A soft book lags.** DraftKings, FanDuel, BetMGM, bet365 or BetRivers (latest line at most 30 minutes old) hangs a number at least 1 point
   better, for the side Pinnacle moved toward, than Pinnacle's new number. If several lag, the one with the largest gap is used.

The play is the lagging book's side at its stale number.

## Control (pack reversion)

Earlier work (`docs/retro/sharp-money-study.md`) found controls "led" as well, because lines revert toward the pack. So the same measure is
run where **Pinnacle did not move**: Pinnacle's line moved less than 0.5 points in the 90 minutes, and a soft book still hangs a number at
least 1 point better than Pinnacle's for one side. One row per game, market, book and direction, the first time it holds. Whatever the control
earns is what a stale number earns without a market move. **The finding is the treatment minus the control.**

## Measures

- **Edge at signal (points):** how much better the stale number is than Pinnacle's new number, in the side's favor.
- **Line CLV (points):** Pinnacle's closing line (its last quote at or before kickoff) against the stale number, in the side's favor. Positive
  means the closing number is worse for the side than the one a follower had. This is a **line** comparison: the soft book's price (juice) is
  not converted to a probability, because no stored conversion of points to win probability is used here. It is reported as a share too:
  `beat` is the share of plays with CLV above 0.
- **Cut by limit:** `limit_up` when two stored Pinnacle limits for that market, 3 or more hours apart, show the later one 50% or more higher.
  Limits are stored on few rows, so `limit_known` is reported.
- Standard errors are **clustered by game** (one game can fire several rows). 95% intervals are 1.96 x the clustered standard error.

## Pass rule

A pass needs, on the primary cut (T = 2), a treatment mean line CLV above the control's by more than the 95% interval of the difference, with at
least **100 games** in treatment, and the same sign in each sport with 20 or more games. Anything less is "not proven" and the card, if built,
stays "context only". A record that improves on a slice found after looking is flagged for monitoring with its sample size and is not a pass.

## What would change the verdict

Nothing found in this replay is tuned. If it fails, the next step is the forward CBB tape, not new thresholds on the same data.
