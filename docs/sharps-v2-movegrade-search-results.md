# Sharps V2: Move grade search (results)

Protocol: `docs/sharps-v2-movegrade-search.md`, registered at `ab68d052` (2026-11-23 7:13 PM CT), before any outcome was read. Scripts:
`scripts/research/mgs_population.py`, `mgs_results.py`, `mgs_analyze.py` (committed at `01e8939f`, 7:17 PM CT, also before any outcome was read).
Research only: nothing here changes live code, `flags_v2.py`, the registered prereg, or `mg-1`. Sharp money is context only.

## Part 1. Selection (fit and validation only; the sealed set not yet read)

### Data used

| What | Source | Coverage |
|---|---|---|
| Population | book tape at `origin/main` `887be78439e7` (newest row 2026-11-23 7:08 PM CT), started games with a Pinnacle row at or before the cut | 5,382 sides, 897 games: NBA 255, NFL 114, CFB 340, CBB 188 |
| NBA scores | `nba/data/game_picks.json` | 248 of 255 games (the 7 without are mostly the Nov 23 slate, not final at the ref) |
| NFL scores | `data/bet_results.json` | 114 of 114 |
| CFB scores | `data/cfbd/lines_2026.json` with the line check | 339 of 340 (0 rejected by the line check) |
| CBB scores | none stored | target (a) report only |

`mg-1` is reproduced on this tape within the newer tape's growth (NFL A 23, B 73, C 132, D 360, against 96, the same as the spec's table 2.4).

### Deviations from the protocol (all fixed before any outcome was read, committed in `01e8939f`)

1. A letter above D needs a move toward the side (s > 0) and the against marker a move away (s < 0). Without it, a stratum whose p50 mark is 0
   (NFL spread and total lines, where most games never move) would have given every no-move side a C, and both sides of a flat market a letter.
2. NFL scores join on the ordered (away, home) pair, unique within the season, instead of the week from `data/game_line_history.json`, whose
   `week` field is 1 on every row and cannot be used.

### Split (per sport, by cut time, Central)

| Set | NBA | NFL | CFB | CBB |
|---|---|---|---|---|
| Fit (60%) | 153 games, Oct 20 to Nov 9 | 68, Oct 1 to Nov 1 | 205, Oct 17 to Nov 7 | 118, Nov 19 to Nov 21 |
| Validation (20%) | 51, Nov 9 to Nov 16 | 29, Nov 1 to Nov 15 | 67, Nov 7 to Nov 15 | 33, Nov 21 to Nov 22 |
| Sealed (20%) | 51, Nov 16 to Nov 23 | 17, Nov 15 to Nov 22 | 68, Nov 17 to Nov 21 | 37, Nov 22 to Nov 23 |

### All 10 systems on fit and validation (pooled NBA+NFL+CFB, sport-and-market fixed effects)

Slope per letter step (D=0 .. A=3), 95% cluster bootstrap over games, one-sided permutation p (5,000 shuffles within sport x market), Holm across
the 20 tests of each set. (a) in points of Pinnacle no-vig fair; (c) in points of flat ROI at Pinnacle's price at the cut. Population: tape.

| Id | System | Fit (a) | Fit (c) ROI | Validation (a) | Validation (c) ROI | Screen (fit t sum) | V |
|---|---|---|---|---|---|---|---|
| S1 | mg-1 as specified | -0.006 [-0.029, +0.018] p 0.668 (Holm 1.000) | +0.49 [-4.61, +5.50] p 0.425 (Holm 1.000) | +0.057 [+0.012, +0.105] p 0.015 (Holm 0.228) | +3.58 [-5.36, +12.90] p 0.188 (Holm 1.000) | -0.27 | +1.59 |
| S2 | Flag A magnitude | -0.046 [-0.076, -0.017] p 1.000 (Holm 1.000) | +2.63 [-2.48, +7.97] p 0.181 (Holm 1.000) | +0.006 [-0.044, +0.055] p 0.436 (Holm 1.000) | +7.62 [-1.65, +16.83] p 0.050 (Holm 0.700) | -2.06 | +0.92 |
| S3 | Flag C magnitude | +0.027 [+0.003, +0.051] p 0.012 (Holm 0.232) | -0.89 [-5.89, +3.88] p 0.645 (Holm 1.000) | +0.088 [+0.043, +0.141] p 0.001 (Holm 0.012) | +0.27 [-9.08, +9.54] p 0.466 (Holm 1.000) | +1.82 | +1.78 |
| S4 | larger of A and C | -0.005 [-0.032, +0.022] p 0.647 (Holm 1.000) | -0.59 [-5.94, +4.70] p 0.589 (Holm 1.000) | +0.075 [+0.022, +0.136] p 0.006 (Holm 0.102) | -0.23 [-10.71, +10.15] p 0.526 (Holm 1.000) | -0.55 | +1.27 |
| S5 | agreement (mean percentile) | -0.011 [-0.037, +0.015] p 0.776 (Holm 1.000) | +2.91 [-2.49, +8.53] p 0.160 (Holm 1.000) | +0.051 [-0.002, +0.109] p 0.060 (Holm 0.780) | +3.09 [-7.69, +13.30] p 0.271 (Holm 1.000) | +0.23 | +1.18 |
| S6 | US books agreeing | +0.017 [-0.001, +0.036] p 0.052 (Holm 0.995) | +1.15 [-2.84, +5.29] p 0.290 (Holm 1.000) | +0.059 [+0.024, +0.097] p 0.005 (Holm 0.085) | -2.25 [-8.92, +5.08] p 0.746 (Holm 1.000) | +2.41 | +1.28 |
| S7 | S4, spreads and totals | +0.002 [-0.033, +0.039] p 0.450 (Holm 1.000) | -2.02 [-7.57, +3.19] p 0.750 (Holm 1.000) | +0.036 [-0.024, +0.100] p 0.147 (Holm 1.000) | -0.69 [-11.29, +9.23] p 0.562 (Holm 1.000) | -0.60 | +0.50 |
| S8 | S4, moneylines | -0.018 [-0.056, +0.014] p 0.820 (Holm 1.000) | +2.53 [-6.59, +12.16] p 0.332 (Holm 1.000) | +0.148 [+0.047, +0.265] p 0.003 (Holm 0.054) | +0.74 [-17.47, +18.08] p 0.458 (Holm 1.000) | -0.52 | +1.40 |
| S9 | S4 pooled over sports | -0.003 [-0.031, +0.026] p 0.573 (Holm 1.000) | +0.98 [-4.90, +6.90] p 0.361 (Holm 1.000) | +0.086 [+0.029, +0.153] p 0.002 (Holm 0.038) | -3.14 [-15.28, +8.78] p 0.715 (Holm 1.000) | +0.14 | +1.08 |
| S10 | S2 pooled over sports | -0.051 [-0.084, -0.021] p 1.000 (Holm 1.000) | +3.09 [-2.16, +8.54] p 0.139 (Holm 1.000) | +0.027 [-0.022, +0.079] p 0.191 (Holm 1.000) | +3.82 [-6.22, +13.54] p 0.235 (Holm 1.000) | -2.03 | +0.90 |

Read before the sealed set: no system orders results (target (c)) on either set; every (c) interval spans 0 and no (c) p survives Holm. On the
after-cut move (a), several systems show a positive slope on validation, but only S3 is positive on both fit and validation.

### The choice, frozen (2026-11-23, before the sealed set is read)

Screen-passing systems (fit t sum above 0): S3, S5, S6, S9. Largest V among them: **S3, Flag C magnitude (V +1.78)**.

S3: score `s` = `c` = spreads and totals, Pinnacle's main-line move toward the side over the 24 hours ending at the cut (`v2f-2` Flag C's
`pin.from` to `pin.to`, side orientation); moneylines, the median of the readable US books' no-vig move toward the side (points x 100). Null when
`flag_line` is null. Marks = fit-set p50 / p80 / p95 of |s| on the home or over side (C / B / A; against at s <= -p80, s < 0):

| Sport | Moneyline (no-vig points) | Spread (line points) | Total (line points) |
|---|---|---|---|
| NBA | 2.1668 / 4.7359 / 10.4575 | 0.5 / 1.5 / 3.5 | 1.5 / 3.0 / 4.5 |
| NFL | 0.3766 / 1.3441 / 2.5922 | 0.0 / 0.5 / 1.0 | 0.0 / 1.0 / 1.0 |
| CFB | 0.7127 / 2.0845 / 4.1564 | 0.5 / 1.0 / 2.5 | 0.5 / 1.0 / 2.0 |
| CBB | 1.3587 / 3.2917 / 4.6236 | 0.5 / 1.0 / 2.0 | 1.0 / 2.0 / 3.5 |

(NFL total: B and A marks are both 1.0, so an NFL total that moved 1 point toward is an A and the NFL total has no B. Said as is; not changed.)

The sealed set will be read once with `mgs_analyze.py --phase sealed --system S3`, 97.5% intervals, pass threshold p < 0.025, per the protocol.

## Part 2. The sealed set, read once (2026-11-23, about 7:25 PM CT, after the choice above was committed at `f124446b`)

### Verdict: **NO-GO**

S3 (Flag C magnitude) fails every pass condition on the sealed set. The sealed set is not "too small to read" under the protocol (A has 30 sides
with a result pooled; NBA and CFB each have more than 100 lettered sides), so the verdict is NO-GO, not INCONCLUSIVE. Honest caveat: the sealed
set is small (629 lettered NBA+NFL+CFB sides with a result), and its (c) interval is about plus or minus 10.7 points of ROI per letter step, so it can
only rule out large effects. But no system showed a (c) slope on the 80% of the data before it either (every (c) interval spans 0, smallest Holm p 0.70).

| Pass condition (sealed, chosen system S3) | Target (a) after-cut move | Target (c) flat ROI | Met? |
|---|---|---|---|
| 1. pooled slope, 97.5% interval above 0 | +0.018 pts per step [-0.030, +0.072], n=639 sides | -1.05 pts ROI per step [-11.50, +9.91], n=629 | no, no |
| 2. permutation p below 0.025 | 0.227 | 0.579 | no, no |
| 3. slope above 0 in 2 of NBA, NFL, CFB | NBA +0.082, NFL -0.021, CFB -0.005 (1 of 3) | NBA +4.74, NFL +12.16, CFB -7.82 (2 of 3) | no, yes |
| 4. practically meaningful | +0.018 below 0.05 | -1.05 below +1.0; A minus D = -12.2 pts | no, no |
| 5. ordered (A >= D, B >= D) | A +0.02 >= D +0.00, B +0.07 >= D | A -15.0% below D -2.8% | yes, no |

### Sealed set by letter, S3 (pooled NBA+NFL+CFB; tape population; mean (standard error clustered by game), n)

(a) points of Pinnacle no-vig fair, cut to close, same line. (b) points: Pinnacle close fair minus the best US-book implied price at the cut (overlaps
the inputs; report only). (c) flat 1u at Pinnacle's price at the cut, points of ROI. Win % excludes pushes. "small" = n under 30.

| Letter | (a) after-cut | (b) CLV vs best US price | (c) ROI | Win % |
|---|---|---|---|---|
| A | +0.02 (se 0.08), n=29, small | -1.47 (se 0.24), n=18, small | -15.0 (se 15.5), n=30 | 46.4 (se 8.9), n=28, small |
| B | +0.07 (se 0.05), n=106 | -1.44 (se 0.14), n=79 | -2.6 (se 11.3), n=103 | 50.5 (se 5.5), n=103 |
| C | -0.01 (se 0.07), n=102 | -1.93 (se 0.10), n=76 | -0.0 (se 10.3), n=98 | 55.7 (se 5.2), n=97 |
| D | +0.00 (se 0.02), n=402 | -1.66 (se 0.04), n=316 | -2.8 (se 4.8), n=398 | 48.6 (se 1.3), n=391 |
| Moved against | -0.06 (se 0.04), n=135 | -1.87 (se 0.12), n=97 | +1.8 (se 11.7), n=133 | 50.4 (se 4.8), n=131 |

By sport (sealed, S3; (c) ROI points and win %):

| Letter | NBA (c) | NBA win % | NFL (c) | NFL win % | CFB (c) | CFB win % |
|---|---|---|---|---|---|---|
| A | -50.2 (se 57.0), n=4, small | 25.0, n=4 | +43.9 (se 18.4), n=10, small | 77.8, n=9 | -43.0 (se 19.0), n=16, small | 33.3, n=15 |
| B | -0.2 (se 19.5), n=34 | 52.9, n=34 | -15.7 (se 49.2), n=4, small | 50.0, n=4 | -3.0 (se 14.7), n=65 | 49.2, n=65 |
| C | +26.2 (se 15.7), n=48 | 64.6, n=48 | -14.5 (se 37.3), n=5, small | 60.0, n=5 | -26.4 (se 13.0), n=45 | 45.5, n=44 |
| D | -6.1 (se 7.9), n=140 | 44.9, n=138 | -4.9 (se 4.9), n=69 | 49.3, n=67 | +0.4 (se 8.1), n=189 | 51.1, n=186 |
| Moved against | -6.7 (se 17.7), n=38 | 50.0, n=38 | -45.5 (se 20.1), n=14, small | 30.8, n=13 | +14.0 (se 16.8), n=81 | 53.8, n=80 |

(a) by sport, sealed: NBA slope +0.082 [-0.007, +0.199]; NFL -0.021 [-0.069, +0.000]; CFB -0.005 [-0.078, +0.071]; CBB (report only) +0.022
[-0.000, +0.050], CBB letters A +0.05 n=20, B +0.05 n=24, C +0.02 n=28, D -0.01 n=88, against -0.05 n=44 (no CBB scores are stored).

### Permutation p-values (one-sided, 5,000 shuffles within sport x market, seed 20261111)

| Set | S3 (a) | S3 (c) |
|---|---|---|
| Fit | 0.012 (Holm over 20: 0.232) | 0.645 (Holm 1.000) |
| Validation | 0.001 (Holm 0.012) | 0.466 (Holm 1.000) |
| Sealed (the test) | **0.227** | **0.579** |

The one Holm-surviving result of the search (S3 on the after-cut move in validation, Nov 1 to Nov 16) did not hold in the sealed weeks. The after-cut
window is 15 minutes; most sides do not move in it, so that target has a low spread and a few late moves can carry a period.

### Exploratory, after the frozen read (cannot change the verdict): all 10 systems on the sealed set, 95%, Holm over 20

| Id | (a) slope | (c) ROI slope, pts |
|---|---|---|
| S1 mg-1 | +0.004 [-0.040, +0.050] p 0.420 (Holm 1.000) | +1.31 [-7.98, +10.59] p 0.374 (Holm 1.000) |
| S2 | +0.000 [-0.061, +0.057] p 0.498 (Holm 1.000) | +3.89 [-5.98, +13.57] p 0.242 (Holm 1.000) |
| S3 | +0.018 [-0.025, +0.064] p 0.227 (Holm 1.000) | -1.05 [-10.08, +8.32] p 0.579 (Holm 1.000) |
| S4 | +0.004 [-0.048, +0.056] p 0.447 (Holm 1.000) | +3.40 [-7.39, +14.12] p 0.275 (Holm 1.000) |
| S5 | -0.003 [-0.069, +0.055] p 0.557 (Holm 1.000) | +2.93 [-7.63, +13.17] p 0.313 (Holm 1.000) |
| S6 | +0.017 [-0.006, +0.048] p 0.165 (Holm 1.000) | -1.56 [-8.20, +5.23] p 0.646 (Holm 1.000) |
| S7 | -0.026 [-0.080, +0.023] p 0.783 (Holm 1.000) | +6.95 [-3.02, +17.02] p 0.102 (Holm 1.000) |
| S8 | +0.063 [-0.037, +0.183] p 0.063 (Holm 1.000) | -4.24 [-27.22, +15.81] p 0.600 (Holm 1.000) |
| S9 | -0.002 [-0.051, +0.045] p 0.541 (Holm 1.000) | +2.73 [-8.25, +14.37] p 0.307 (Holm 1.000) |
| S10 | -0.013 [-0.078, +0.043] p 0.674 (Holm 1.000) | +6.71 [-2.73, +16.51] p 0.127 (Holm 1.000) |

No system has a sealed interval above 0 on either target; every Holm p is 1.000. S7 and S10 have the largest (c) point estimates on the sealed set;
neither had a positive fit-plus-validation (c) record that would have chosen it (S7 fit -2.02, validation -0.69), so that is noise to watch, not a
finding. Nothing here is promoted.

### The 205 graded plays (report only; never used to choose; `pm-holders-data` `3e17a148dc2f`, flat 1u at the stored price at the cut)

`mg-1` re-derived here reproduces the spec's tables exactly (section 2.5 shares and 3.1 records), which checks the feature code. S3 letters, read at
each play's own cut (46 CBB plays cut before the CBB tape existed and 9 CFB plus 8 other plays whose side did not map stay "no grade"):

| S3 letter | Headline NBA+NFL+CBB | All four (CFB no size shown) |
|---|---|---|
| A | 4-2, +1.26u, +21.0% (se 38.8), n=6, small | 5-4, -0.43u, -4.8% (se 30.9), n=9, small |
| B | 3-1, +0.63u, +15.7% (se 40.3), n=4, small | 7-5, -0.49u, -4.1% (se 24.9), n=12, small |
| C | 12-6, +2.62u, +14.6% (se 21.1), n=18, small | 15-12, -1.15u, -4.2% (se 17.5), n=27, small |
| D | 33-26, -0.24u, -0.4% (se 12.2), n=59 | 44-31, +3.86u, +5.1% (se 10.7), n=75 |
| Moved against | 8-3, +4.39u, +39.9% (se 29.8), n=11, small | 10-11, -1.84u, -8.7% (se 22.3), n=21, small |
| No grade | 25-21, +3.32u, +7.2% (se 14.9), n=46 | 33-28, +2.71u, +4.4% (se 12.6), n=61 |

Old (no letter): headline 85-59, +11.98u, +8.3%, n=144; all four 114-91, +2.66u, +1.3%, n=205 (unchanged; each column sums to it). On the headline
the S3 letters look ordered A > B > C > D, but the "moved against" plays did best of all and every cell but D and no grade is under n=30; across all
four sports the order disappears. In-sample, not evidence. After-cut move on these plays: S3 A +0.00 n=6, C +0.14 n=18, D -0.01 n=58, moved against
-0.73 n=11 (headline).

Flagged for close monitoring (CLAUDE.md: every cell that improves, with its n; none promoted, none a signal): sealed population S3 NBA C +26.2% n=48;
NFL A +43.9% n=10 (small); CFB D +0.4% n=189; CFB moved against +14.0% n=81; pooled moved against +1.8% n=133; graded headline S3 A +1.26u n=6
(small), B +0.63u n=4 (small), C +2.62u n=18 (small), moved against +4.39u n=11 (small), no grade +3.32u n=46; graded all four S3 D +3.86u n=75,
no grade +2.71u n=61.

## Part 3. What was tried, and what is still legitimate

**Tried, all counted: 10 systems** (S1 to S10 above), 2 targets each on fit and validation (40 tests), one frozen system on the sealed set (2 tests),
then 20 exploratory sealed tests. Nothing else was tried. The best candidate was S3 (Flag C magnitude: how far Pinnacle's main line, or the US books'
moneyline price, moved toward the side in the 24 hours to the cut). It is not distinguishable from noise: its one strong read (after-cut move,
validation, Holm p 0.012) did not repeat on the sealed weeks (p 0.227), and on results it never had a slope (fit -0.89, validation +0.27, sealed -1.05
points of ROI per step, every interval spanning 0, its sealed A letter -15.0% ROI n=30).

Why this is the expected answer: the price at the cut already contains the move. A letter built from the move before the cut can only beat that
price if the market under-reacts, and on this tape it does not, in results or in the next 15 minutes. That matches every earlier test of the kind in
this project (steam chaser, EPA, spot score, line-taught ratings) and the `mg-1` in-sample read.

**Alternative framings.**

1. *A descriptive label of the move that already happened* ("how far the market moved toward this side by the lock") is legitimate, because it claims
   nothing about results; `mg-1` is exactly that. Its letter shares are stable across the three periods (S1, all four sports: A 4.0% / 4.7% / 5.6%
   of sides; against 15.6% / 18.0% / 19.5% in fit / validation / sealed; A and against drift up a little as the season goes on), so a reader gets a consistent description. It must keep the `mg-1` wording
   ("describes the market, not a bet signal"), and the page should not sort or filter by it. Whether it is useful is a product call; the data says it
   carries no information about the result beyond the price.
2. *A "moved against" caution marker* has no support. Sealed population, against minus D: S3 (c) +4.6 points ROI [-20.2, +29.4], win % +1.8
   [-8.0, +11.6], (a) -0.06 [-0.15, +0.03]; mg-1 (c) -1.6 [-25.4, +22.2], (a) +0.00 [-0.10, +0.10]. On the graded plays the against group did better
   than D on the headline (S3 8-3, mg-1 11-8). A caution would be telling people something the data does not show. The marker is fine as a
   description (the market moved the other way), never as "caution".

**The one most promising honest next test (not run).** The binding limit is sample size: the tape has 3 to 8 weeks per sport, and a 1-point ROI
per letter step needs thousands of graded sides. The cheapest large sample is historical college football lines from CollegeFootballData
(the source already behind `data/cfbd/lines_2026.json` and the `fetch-cfbd` workflow), which stores an opening and a closing spread and total per
game for 2021 to 2025, about 3,500 FBS games a season. Pre-register one rule (the S3 analogue: the open-to-close line move toward a side, letters
from the move's own distribution in 2021 to 2023), grade each side against the **closing** line at a flat -110 only if a stored closing price
exists (else report win % at the closing number only, never an invented price), and read 2024 to 2025 once. That tests "does a line move predict the
result against the moved number" with about 7,000 holdout sides, enough to see a 2-point win % gap. It is a different window (open to close, not 24
hours to the cut), so a pass there would justify a forward test here, nothing more. Otherwise, the registered `mg-1` forward shadow (prereg section
6 of the spec, if the user registers it) keeps accumulating, with its own minimums (about 550 lettered plays per sport before A reaches 30).

### Files

| File | What |
|---|---|
| `docs/sharps-v2-movegrade-search.md` | the protocol (`ab68d052`) |
| `scripts/research/mgs_population.py` | the tape population, features at the cut, targets (a) and (b), mg-1 letter |
| `scripts/research/mgs_results.py` | final scores for NBA, NFL, CFB |
| `scripts/research/mgs_analyze.py` | split, the 10 systems, slopes, bootstrap, permutation, Holm; `--phase select` and `--phase sealed` |
| `scripts/research/mgs_graded.py` | the 205 graded plays by S3 and mg-1 letter |
| `scripts/research/mgs_report.py` | prints the tables above from the JSON outputs |
| `docs/sharps-v2-movegrade-search/*.json` | `select.json`, `sealed.json`, `graded.json` (the outputs these tables were printed from) |

Reproduce (from the repo root, tape at `887be78439e7`): `python3 -I scripts/research/mgs_population.py --now 1795482496 --out scratch/mgs_pop.json`,
then `mgs_results.py --pop scratch/mgs_pop.json --out scratch/mgs_scores.json`, `mgs_analyze.py --phase select --out scratch/mgs_select.json`,
`mgs_analyze.py --phase sealed --system S3 --out scratch/mgs_sealed.json`, `mgs_graded.py --ref 3e17a148dc2f --select scratch/mgs_select.json
--out scratch/mgs_graded.json`.
