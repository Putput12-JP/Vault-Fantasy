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
