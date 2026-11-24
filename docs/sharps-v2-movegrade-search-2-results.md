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
