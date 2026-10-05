# Dampened DvP: keep it for QBs, damp it for everyone else

**Date:** 2026-10-05 · **Scripts:** `scripts/backtest_dvp_damp.py` (holdout + market check),
`scripts/backtest_dvp_damp_market.py` (permutation / cluster diagnostics)

Follow-up to `docs/target-funnel-backtest.md`, which found the shipped opponent term hurts
receiving projections on a holdout.

## What ships

`oppMult = clamp(PPR pts allowed to pos per game / league avg, .88, 1.15)`
(`build_best_bets.mjs` `matchupAdjFor`, fed by `build-lineup-feed.mjs` `buildDvP`). It uses raw
current-season weeks once 2+ are complete (else last season shrunk by `dvp_shrink.json`) and
multiplies every prop market.

## Dampened candidate

`est = (n·cur + k·prior)/(n + k)`, `prior = 1 + a·(last season − 1)`, `mult = clamp(est^w, .88, 1.15)`.
One global fit on 2016-2021. Fit over all positions it comes out at k=8, a=0.5, w=0.2. Fit over the
RB/WR/TE cells it is applied to (what ships) it comes out at **k=16, a=0.25, w=0.5**: +0.12% mean
holdout RMSE, 7 of 8 cells better (RB rec −0.04%, flat). Per-cell fits add nothing over the global fit.

## 1. Holdout accuracy, 2022-2025 (154k market × player-games)

| | shipped | damped (global) |
|---|---|---|
| mean RMSE change vs no term | **−0.70%** | **+0.15%** |
| cells better than no term | 2 / 14 | **14 / 14** |
| worst cell | pass_att QB −2.30% | rec RB +0.01% |

On raw accuracy the shipped term is too strong everywhere, and the damped one wins every cell.

## 2. Against 2026 closing lines (2,454 settled props, Wk 1-4)

"Flips" are props where the term changes the model's side vs the closing line. The core projection
leans over, so **random flips also win ~54%**. The null is a shuffle of the same multipliers within
position.

| pos | shipped flips | flipped side wins | shuffled null | p |
|---|---|---|---|---|
| **QB** | 103 | **74.8%** | 54.4% | **<0.001** |
| RB | 70 | 54.3% | 54.3% | 0.50 |
| TE | 46 | 54.3% | 51.5% | 0.34 |
| WR | 58 | 48.3% | 56.3% | 0.94 |

The QB result is robust:
- **By market:** pass_yd 82% (28), pass_cmp 77% (22), pass_rush_yd 75% (16).
- **By week:** all four weeks are positive.
- **Clustering:** defense-week cluster bootstrap 95% CI 65-84% over 50 defense-weeks.
- **Leave-one-defense-out:** 73-77%.

## Verdict

- **RB / WR / TE:** the shipped term hurts accuracy and has no value against the market. Replace it
  with the damped version, which is close to off.
- **QB:** the holdout says the shipped magnitude is too big for accuracy. The market says its
  direction is valuable and not priced. Keep the shipped QB term as-is and watch it, since this is
  4 weeks of evidence. Re-run `backtest_dvp_damp_market.py` weekly.
- Implementation note: the damped term needs per-team games played and last season's ratio. The
  lineup feed's `dvp` table currently ships only `fpa` and `rank`.

## Shipped (2026-10-05)

- `python3 scripts/backtest_dvp_damp.py --write` publishes the RB/WR/TE fit to `data/dvp_damp.json`.
- `build-lineup-feed.mjs` `buildDvP` writes `dvp[team][pos].mult` for those positions. Last season's
  ratio comes from `data/nflverse_stats_{season-1}.json` in-season, or from the raw last-season table
  in the preseason. `dvp_meta.damp` records the parameters.
- `build_best_bets.mjs` `matchupAdjFor` and `index.html` `matchupAdj` prefer `mult` and fall back to the
  raw ratio, so QB, and everything when the file is missing, keeps the old term.
- Verified on the live props board (169 props): QB 29/29 unchanged; RB/WR/TE max swing 15% to ≤5%.
- The term also multiplies TD markets (it always did). Only yardage/count markets were backtested.
