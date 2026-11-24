# Sharps V2: Move grade search 2 (results), CFB open-to-close, DraftKings, 2023 to 2025

Protocol: `docs/sharps-v2-movegrade-search-2.md`, registered at `f3aa99ca` (2026-11-23 10:32 PM CT) before any outcome was read; script
`scripts/research/mgs2_cfbd.py` at `3519a838` (10:33 PM CT), also before any outcome. Data: `data/cfbd/lines_<year>.json` at `origin/cfbd-lines-probe`
`6825116ec526`, DraftKings rows only. No price is stored, so there is no ROI anywhere in this file; targets are win % and cover rate at the stored number.

## Part 1. Selection (2023 fit, 2024 validation; 2025 not yet read)

Games with a DraftKings open and close and both scores: spreads 2023 729, 2024 702, 2025 676; totals 2023 462, 2024 143, 2025 72.
Marks from 2023 moves (home or over side, |move|, points): spread C 0.5 / B 1.5 / A 4.5; total C 0.5 / B 2.0 / A 4.0.

Slope of win % at the closing number per letter step (D=0 .. A=3), 95% cluster bootstrap over games, one-sided permutation p (5,000), Holm over 3:

| Id | System | 2023 fit | 2024 validation |
|---|---|---|---|
| M1 | spread move, all weeks | -1.76 pts [-5.19, +1.50], t -1.03, p 0.850 (Holm 1.000), n=1,241 | +0.18 [-2.52, +2.81], t 0.13, p 0.470 (Holm 1.000), n=1,000 |
| M2 | spread and total | -1.01 [-3.53, +1.61], t -0.77, p 0.783 (Holm 1.000), n=2,046 | -0.35 [-2.88, +2.12], t -0.27, p 0.601 (Holm 1.000), n=1,254 |
| M3 | spread move, weeks 4 and later | -1.50 [-5.31, +2.10], t -0.80, p 0.793 (Holm 1.000), n=1,014 | +0.22 [-2.61, +3.22], t 0.15, p 0.468 (Holm 1.000), n=749 |

Win % at the close by letter (M1): 2023 A 47.5 (se 8.0) n=40, B 49.7 (4.2) n=145, C 44.3 (3.5) n=201, D 51.3 (0.8) n=855, against 50.8 (3.7) n=185;
2024 A 47.2 (5.3) n=89, B 55.4 (2.9) n=287, C 46.0 (3.5) n=202, D 51.9 (1.7) n=422, against 46.5 (2.6) n=376.

For contrast (report only; overlaps the move by construction): win % at the **opening** number, M1 A 72.5% (2023) and 60.9% (2024), against 41.1% and
37.9%. The moves are real (the side the number moved to did win more often against the old number), but the closing number has already absorbed them.

Letter shares moved between years: in 2024 far fewer sides are D (426 of 1,404 spread sides vs 873 of 1,458 in 2023) and far more are B or against,
so DraftKings' 2024 openers moved more. Marks are kept from 2023 as registered.

### The choice, frozen before 2025 is read

**No system passes the screen** (every 2023 slope is negative). As registered, the chosen system is the largest 2024 t of all three: **M3**
(spread move, weeks 4 and later, t 0.15), with the marks above. 2025 is read once with `mgs2_cfbd.py --phase sealed --system M3`.

## Part 2. 2025, read once (2026-11-23, about 10:35 PM CT, after the choice was committed at `bda9b881`)

### Verdict: **NO-GO**

The frozen system M3 has a **negative** slope on 2025: the bigger the move toward a side, the slightly worse that side did at the closing number.
2025 is not too small to read (71 A sides, 1,214 lettered sides with or without a result), so this is NO-GO, not INCONCLUSIVE.

| Pass condition (2025, M3, win % at the closing number) | Value | Met? |
|---|---|---|
| 1. slope 95% interval above 0 | -2.49 pts per step [-5.30, +0.38], n=843 sides | no |
| 2. permutation p below 0.05 | 0.937 | no |
| 3. at least +1.0 pt per step and A minus D at least +3.0 | -2.49; A minus D = 44.9 - 52.4 = -7.5 | no |
| 4. A >= D and B >= D | A 44.9, B 47.1, D 52.4 | no |
| 5. slope above 0 in both halves | weeks 4 to 7: -2.81 [-7.52, +2.20], n=287; weeks 8 to 15: -2.32 [-5.67, +1.32], n=556 | no |

### 2025 by letter, M3 (DraftKings spreads, weeks 4 and later; mean (standard error clustered by game), n)

| Letter | Win % at the close (pushes out) | Cover rate (pushes count as not covered) | Win % at the open (report only, overlaps the move) |
|---|---|---|---|
| A | 44.9 (se 6.0), n=69 | 43.7 (se 5.9), n=71 | 63.8 (se 5.8), n=69 |
| B | 47.1 (se 3.0), n=278 | 46.3 (se 3.0), n=283 | 53.7 (se 3.0), n=283 |
| C | 45.1 (se 3.9), n=162 | 44.2 (se 3.9), n=165 | 46.1 (se 3.9), n=165 |
| D | 52.4 (se 1.9), n=334 | 51.3 (se 1.9), n=341 | 51.9 (se 1.9), n=337 |
| Moved against | 53.3 (se 2.7), n=347 | 52.3 (se 2.7), n=354 | 44.3 (se 2.7), n=352 |

Cover-rate slope: -2.45 [-5.25, +0.26]. Win-at-open slope (report only): +2.37 [-0.36, +5.12].

Permutation p (win % at the close, one-sided): M3 2023 0.793, 2024 0.468, **2025 0.937**.

Moved against minus D (2025, win % at the close): +0.9 pts [-5.5, +7.4]: no support for a "caution" reading.

Exploratory, after the frozen read, all three systems on 2025 (Holm over 3): M1 -2.13 [-4.93, +0.56] p 0.919 (Holm 1.000) n=971; M2 -1.56
[-4.16, +0.96] p 0.855 (Holm 1.000) n=1,104; M3 -2.49 [-5.30, +0.38] p 0.937 (Holm 1.000) n=843. All three are negative in all of 2023 and 2025.

Flagged for close monitoring (cells that improve, here: win % at the close above 50, report only, none promoted): 2025 M3 D 52.4% n=334, moved against
53.3% n=347; 2024 M1 B 55.4% n=287, D 51.9% n=422; 2023 M1 D 51.3% n=855, against 50.8% n=185. With no stored price none of these is a return.

## Part 3. What this means

- **Tried: 3 systems** (M1, M2, M3), 2 periods each before the sealed year (6 tests), 1 frozen system on 2025, then 3 exploratory 2025 tests.
  Nothing else was tried.
- **Across 2,100 games of DraftKings CFB history, a letter for how far the number moved toward a side does not predict the result against the
  moved (closing) number.** The slope is negative in 2023 and 2025 and about 0 in 2024. Against the **opening** number the same sides did win more
  (A 64 to 73%), which is the market moving correctly; by the close the move is priced. That is the market-efficiency answer search 1 expected.
- **What it says about the live Move grade:** this was a different window (open to close, not the 24 hours before a 15-minute cut), one book
  (DraftKings, not Pinnacle's price), one sport, and graded at the close rather than at a stored price, so it cannot test mg-1 directly. But it was the
  largest honest sample available, and it gives no reason to expect a move-size letter to order results in the live grade. It does not justify a
  forward test of a results claim. The live grade stays what mg-1 already says: a description of the market, not a bet signal.
- **What is missing and what it would take to go further:** 2021 lines are not stored (needs a CFBD fetch with the repo secret through a workflow
  that takes a years input and does not push to `main`); 2022 has no DraftKings openers; no CFBD row stores a price, so no ROI can be computed
  from this source at all. A stored-price test would need a historical odds source with prices at open and close, which this repo does not have.

Outputs: `docs/sharps-v2-movegrade-search-2/select.json`, `sealed.json`. Reproduce: extract the four files with
`git show 6825116ec526:data/cfbd/lines_<year>.json > scratch/cfbd/lines_<year>.json`, then `python3 -I scripts/research/mgs2_cfbd.py --phase select
--out scratch/mgs2_select.json` and `--phase sealed --system M3 --out scratch/mgs2_sealed.json`.
