# Sharps V2: Move grade search 2, large-sample CFB open-to-close test (protocol, written before any outcome is read)

**Status: REGISTERED by the commit that adds this file. Research only.** Written 2026-11-23 (Central). Branch `sharps-v2-movegrade-search`.
Follows search 1 (`docs/sharps-v2-movegrade-search-results.md`, NO-GO), which proposed this test. Nothing from search 1's tape or its 205 graded
plays is used to choose anything here. Sharp money is context only (CLAUDE.md); a pass here is at most a reason for a forward test of the live grade.

## 0. What this can and cannot tell us about the live Move grade

The live Move grade (mg-1, and S3 in search 1) reads the move in the **24 hours ending 15 minutes before start**, at **Pinnacle** and the stored US
books, and the play is priced at the cut. This test reads a different thing: one book's **opening** number to its **closing** number (days, not
24 hours, ending at the close, not 15 minutes before it), college football only, spreads (and totals in one variant), graded against the **closing
number**. The structure is the same question in a bigger sample: does a letter built from how far the number moved toward a side predict the result
against the number that already contains the move? A pass says only that such a letter has worked on CFB open-to-close history, and would justify a
pre-registered forward test of the live grade; it cannot validate mg-1's cutoffs, its window, Pinnacle's price move (Flag A), or any other sport. A
NO-GO says a move-size letter does not beat the moved number in the largest sample this repo has.

## 1. Data, and what is missing (checked before this file; no outcome read)

| Input | Ref | Notes |
|---|---|---|
| CollegeFootballData lines with scores | `data/cfbd/lines_<year>.json` at `origin/cfbd-lines-probe` `6825116ec526` (written 2026-10-11 by the repo's own CFBD fetch with the repo secret; read here through git, no new fetch) | one row per game per provider: `sp`, `so` (closing and opening spread, home), `ou`, `ouo` (closing and opening total), `hs`, `as_` (scores), `wk`; regular season weeks 1 to 15 |

- **2021 is not stored** anywhere in the repo, and the CFBD key is not available locally (it is a repo secret used only by the workflows). Fetching
  2021 would need the `update-cfbd-lines` workflow run with a years input it does not have, and that workflow pushes to `main`. So 2021 is left out
  rather than fetched another way.
- **Provider.** Only DraftKings among the books this project may name stores an opener: spreads 2023 729 games, 2024 702, 2025 676; totals 2023 462,
  2024 143, 2025 72; **2022 has none**. Another provider stores openers in every year but is not one this project names, so it is not used.
- **No price is stored** (the rows hold numbers, not odds). **No ROI is computed.** Targets are win % and cover rate against the stored number only.

So the split forced by the data, replacing the brief's 2021-2023 / 2024 / 2025: **fit = 2023, validation = 2024, sealed = 2025** (DraftKings).

## 2. Unit, move, targets

- Unit: a side (home and away of the spread; over and under of the total) of one game with a DraftKings row carrying both the open and the close and
  both scores. Duplicate rows for the same game and provider: the first in the file is used. Intervals resample whole games.
- Move toward the side, points: home spread `s = so - sp`; away `s = sp - so`; over `s = ou - ouo`; under `s = ouo - ou`.
- **Primary target, win % vs the closing number**: the side's result at the close (home: `hs - as_ + sp`; away: the negative; over: `hs + as_ - ou`;
  under: the negative); win = above 0, loss = below 0; push left out; win % = wins / (wins + losses).
- **Secondary, cover rate** (report only): wins / all graded sides, pushes counted as not covered.
- Report only: win % vs the opening number (what a bettor at the open got; it overlaps the move by construction, so never a pass condition).

## 3. Letters and the search space (exactly 3 systems, every one counted)

Letter marks are the fit-year (2023) p50 / p80 / p95 of |s| on the home or over side, per market: **A** `s >= p95`, **B** `p80 <= s < p95`, **C**
`p50 <= s < p80` (each needs `s > 0`), **against** (marker, out of the slope) `s <= -p80` with `s < 0`, **D** otherwise.

| Id | System |
|---|---|
| M1 | DraftKings spread move (the S3 analogue), all weeks |
| M2 | M1 plus DraftKings totals, pooled with a market fixed effect |
| M3 | M1, weeks 4 and later only (early-season numbers move on thin information; the CFB model's own `min_week` convention) |

## 4. Statistics

- Slope of the target (win = 1, loss = 0) on the letter score (D=0, C=1, B=2, A=3) over lettered sides, market fixed effect (M2), 95% cluster
  bootstrap over games, 2,000 resamples, seed 20261111. Permutation: letters shuffled among lettered sides within market, 5,000 shuffles, one-sided.
- Per-letter cells: n, mean, standard error clustered by game; small sample under n = 30.
- Holm across the 3 systems on fit and on validation.

## 5. Selection

Screen: fit slope t above 0. Chosen: the screen-passing system with the largest validation t (ties: lower id); none passing, the largest validation
t of all 3, said so. The choice and its marks are committed before 2025's outcomes are computed; 2025 is read once.

## 6. Pass rule (2025, chosen system, primary target only)

**WORKS** only if all hold: (1) slope 95% interval above 0; (2) permutation p below 0.05; (3) at least 1.0 point of win % per letter step and A minus
D at least 3.0 points; (4) A >= D and B >= D; (5) the slope point estimate above 0 in both halves of 2025 (weeks 1 to 7 and 8 to 15), since one
sport and one book cannot give a cross-sport check. Otherwise **NO-GO**, or **INCONCLUSIVE** if 2025 has fewer than 30 A sides or fewer than 300
lettered sides. A pass is a candidate only: a PROPOSED forward test of the live grade, written separately, never a bet signal.

Also reported: the moved-against marker vs D (2025, 95% interval), and all 3 systems on 2025 after the frozen read (exploratory, Holm).

Scripts: `scripts/research/mgs2_cfbd.py`, `python3 -I`, stdlib only. Times Central. No em dashes.
