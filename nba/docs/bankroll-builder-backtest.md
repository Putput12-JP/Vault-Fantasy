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
