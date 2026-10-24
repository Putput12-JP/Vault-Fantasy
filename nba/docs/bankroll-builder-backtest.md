# Bankroll Builder: backtests on the first nights (run 2026-10-22)

Rules: `nba/docs/experiment-log.md` section 12. Code: `python3 scripts/bankroll_builder.py --backtest`.

**What the backtest is.** The recorded SmartStake tape (10/19 to 10/22, 556 polls) replayed poll by poll through the same code the live tracker uses. For each poll the board is
rebuilt from the recorder's stored snapshots (nba-data branch, rows cut off at the poll), and the model's chance comes from the model files as they stood in git at that moment
(none from after the poll). Picks are logged at the first poll they qualify, followed to tip, settled from the ESPN box score, graded flat 1 unit at entry. 472 boards rebuilt.

**Limits.** Two regular-season nights settled (10/20, 10/21; 13 games). The prop model's fitted parameters were last refit 2026-10-09, before any regular-season game. The tape has gaps.
Picks inside one game are correlated, so the effective sample is smaller than the pick count.

## Step 1: is the price band itself profitable? No.

Every sportsbook leg priced -110 to -220 at the last pre-tip snapshot of each game, settled from the box score, no gates (13 games):

| Slice | legs | won | implied | ROI |
|---|---:|---:|---:|---:|
| All legs, best price per player-line-side | 5,376 | 52.9% | 57.1% | **-7.3%** |
| Overs | 3,236 | 49.5% | 58.1% | -14.9% |
| Unders | 2,140 | 58.0% | 55.6% | +4.3% (se 5.4%) |
| Cost 52-57% (-110 to -133) | 3,331 | 50.3% | 53.7% | -6.3% |
| Cost 62-69% (-163 to -220) | 1,101 | 57.2% | 65.1% | **-12.1%** |

Heavier favorites are overpriced, not underpriced. Buying the band is a vig tax. Legs priced against the other books' no-vig price (one pick per player-game, 3+ venues):

| Price vs the market's fair | picks | won | ROI | se |
|---|---:|---:|---:|---:|
| 4%+ better (v1's gate) | 16 | 50.0% | -6.8% | 19.8% |
| 2%+ better | 43 | 62.8% | +14.9% | 18.8% |
| At or better (0%+) | 93 | 60.2% | +9.4% | 9.2% |
| 1% worse or better | 126 | 61.1% | +11.0% | 8.4% |

Nothing in this table is statistically significant. It is why v2 moved the gate from 4% to 0%: the strict gate threw away most of the volume and the extra edge did not show up.

## Step 2: v1 (4% edge AND model gate), replaced

8 picks (7 settled), 3 won, -1.74u, CLV +10.1% (n=7). Shadow: legs the model liked but the market did not, 33 settled, won 48% while the model said 65%. Too small to say anything.

## Step 3: v2 (price at or better than the market's fair; model recorded, not a gate), IN-SAMPLE

Chosen after looking at Step 1, so this is not out-of-sample. 42 picks, 32 settled (10/22 and 10/23 picks are still open); 77 more qualifying picks were held back by the 20-per-slate cap
and 41 by the 2-per-team-game cap.

| | picks | settled | won | units | ROI | CLV |
|---|---:|---:|---:|---:|---:|---:|
| All | 42 | 32 | 21 | **+6.24** | +19.5% (z 1.27) | **+5.1%** (n 32, 2 SE = 2.3 pts) |
| Core (4%+) | 9 | 6 | 5 | +3.29 | +54.8% | +8.4% |
| Standard (0-4%) | 33 | 26 | 16 | +2.95 | +11.4% | +4.3% |
| Overs | 21 | 16 | 9 | +0.22 | +1.4% | +5.5% |
| Unders | 21 | 16 | 12 | +6.02 | +37.7% | +4.6% |
| Model agrees (clears price by 2+) | 13 | 10 | 6 | +1.08 | +10.8% | +4.1% |
| Model disagrees | 29 | 22 | 15 | +5.16 | +23.5% | +5.5% |

**Flags, all improve and all small:** the +6.24u (**n=32 settled**, z 1.27, not significant); CLV +5.1% (n=32), the steadier number because it does not depend on outcomes; Core +3.29u (**n=6**);
unders +6.02u (**n=16**, the side split is the part most likely to be noise).

**The model does not help here:** picks it disagreed with did better than ones it liked (n=22 vs n=10, both small). Do not put weight on either; it means the model is not earning a gate.

Shadow (not bets): legs the model liked while the market priced them worse than fair: 96 logged, 53 settled, 34 won (64%, the model said 64%), +8.95u. That conflicts with v1's 33-leg result
(48% won) because v2 no longer excludes roster-held legs. Both are small, correlated and unresolved; it is only a reason to keep logging the shadow.

## Where the replayed picks live now

The step-3 picks are merged into the live record on the page, tagged `replayed`, and the page has a Live only switch (see `nba/docs/experiment-log.md` section 12). The open ones from tonight's slate are
followed and settled by the live tracker.

## What to expect

About 20 picks per slate hit the cap, ranked first come. The live record starts at zero and counts only picks made from now on.


## Audit, 2026-10-24: settlement, the 75% question, and v3

**Settlement is correct and current.** All 179 settled legs on file (85 picks plus the shadow logs) were re-graded from freshly fetched ESPN box scores, ignoring the cache: 0 mismatches,
0 voids, 0 unfinished games. The 5-minute job runs a copy of the scripts; all six copies were byte-identical to main, and it last wrote at 07:07 ET on 10/24. Nothing was stale.

**The record at the time of the audit (v2, live + replayed):** 85 picks, 65 settled, 33 won (**50.8%**), -4.98u (-7.7%), CLV +5.3% (n 65). Live only: 23 settled, 10 won (43.5%), -4.91u. Overs 13-20 (39.4%, -9.50u),
unders 20-12 (62.5%, +4.51u).

**Why it is not hitting 75%: the hit rate is the price.** Whole tape (10/19 to 10/24, 722 polls, 26 settled games), every sportsbook leg at its best price, one row per player-stat-side-line, settled from box scores:

| Price band (implied) | legs | hit | implied | ROI |
|---|---:|---:|---:|---:|
| -110 to -140 (50-58%), 3+ venues | 2,625 | 52.9% | 53.2% | -0.6% |
| -140 to -170 (58-64%) | 251 | 59.8% | 60.2% | -0.9% |
| -300 to -400 (75-80%), no fair gate | 4,012 | 61-65% | 77% | -15% to -22% |
| -400 to -525 (80-84%), no fair gate | 2,567 | 72-80% | 82% | -2% (unders) to -11% (overs) |
| -525 to -900 (84-90%), no fair gate | 3,404 | 79-88% | 86% | +2% (unders) to -9% (overs) |

In every band the hit rate lands on the price, and the market's fair chance (margin removed) is well calibrated. The picks average -124, which implies 55.6%; they hit 50.8% (v2) and 57.6% (v3). A 75% hit rate means buying about -300, and
at -300 the books charge more than the extra wins are worth. Legs that clear the fair-price gate at -220 or heavier are almost nonexistent (other venues rarely quote both sides), so the edge there cannot be checked.
No rule can be tuned to 75% without picking the price band that loses the most.

**What did separate winners from losers: the side.** In the -110 to -140 band (3+ venues, best price, one row per leg): overs **-13.3%** ROI (n 1,234, se 2.7), unders **+10.6%** (n 1,391, se 2.5). Across the whole -110 to -220 band, unders beat overs in **21 of 26 games**, on all four nights (10/20 to 10/23), and in all eight stat types. The closing line does not show it (CLV is +2% to +4% on both sides), so it is a pattern in
how these first games finished, not a price the market later agreed with. **In-sample, six nights, 26 games, correlated within a game.** The one explanation worth testing is that early-season lines are set on last season; if lines
adjust, it fades.

### v3 (2026-10-24): v2 plus unders only

Same gates as v2; an over that passes them goes to the `over_watch` shadow (never counted). Both rebuilt on the identical tape and code (`--backtest`, `PICK_OVERS=1` for v2):

| | picks | settled | won | hit | units | ROI | CLV |
|---|---:|---:|---:|---:|---:|---:|---:|
| v2 rebuilt on the same tape | 80 | 60 | 31 | 51.7% | -3.40 | -5.7% | +6.0% |
| **v3 unders only** | 80 | 59 (1 void) | 34 | **57.6%** | **+2.81** | **+4.8%** (z 0.41) | +5.0% (n 59) |
| v3 Core (4%+) | 17 | 12 | 9 | 75.0% | +4.32 | +36.0% | +8.0% |
| v3 Standard | 63 | 47 | 25 | 53.2% | -1.51 | -3.2% | +4.2% |
| Shadow `over_watch` | 131 | 101 | 48 | 47.5% | -13.87 | -13.7% | +4.8% |

**Flags, all improve and all small:** the +2.81u (**n=59**, z 0.41, not significant); Core's 75.0% (**n=12**, chosen after looking, the v2 record's Core was 7 of 12); the unders-over split (**26 games**). v3 hits what its prices imply, not more.
v3 has **zero live picks**; the rule was picked after seeing these nights, so none of this is evidence until live picks settle (100 picks and CLV +2 SE, as in the log).

### Chalk (-300 and heavier), tracked, not bets

Added at the owner's request to show the high-hit plays. Unders at -300 or heavier, same minutes and injury gates, one per player per game, no fair-price gate (most cannot be checked). Replayed on the same six nights, first version:
-300 to -400: 46 settled, 33 won (71.7%), -2.94u (-6.4%); -400 or heavier: 66 settled, 54 won (81.8%), -1.94u (-2.9%).

**ProphetX excluded (2026-10-24).** Its chalk prices are not real: in 22 of 25 entries the decimal price had moved 25% or more by tip (median +42%), where bet365 (89) and ParlayPlay (30) closed at their entry price. 25 ProphetX
chalk entries (14 of 23 settled won, -4.96u) were removed from the stored history; the slots they held were not refilled. Chosen on quote integrity, but made after seeing the results, and it improves the record, so read it as in-sample:

| | picks | settled | won | hit | units | ROI |
|---|---:|---:|---:|---:|---:|---:|
| -300 to -400 | 30 | 28 | 22 | **78.6%** | +0.73 | +2.6% |
| -400 or heavier | 89 | 61 | 51 | **83.6%** | -0.65 | -1.1% |

**Flag:** these are the highest-hit-rate plays on the page and they sit at break-even on **n = 28 and 61** settled; CLV is about zero (the entry price holds). Not enough to call them an edge. Shown in the Favorite props table, tagged CHALK, never in the record.
