# Rookie early-season minutes from preseason: pre-registered test

Written 2026-10-20 before any result below was computed. Only sample counts were looked at (about 118 drafted rookies
with 40+ preseason minutes over three classes). Amendments, dated, go at the end.

## Why

`minutes-lab-preseason.md` ships preseason first-half minutes for veterans only. Rookies are the biggest miss: the Lab
gives every rookie the mean early-season minutes of his draft-pick bucket (`PICK_BUCKETS` in
`build_player_projections.py`; #1-3 is 25.8, #4-10 17.8, ..., #46-60 9.8), so Darius Acuff Jr. (18.5 first-half
minutes, most of any rookie in four preseasons) and a second-rounder who never leaves the bench get the same number
inside a bucket. The question: does a rookie's preseason first-half minutes predict his early-season minutes beyond his
draft slot?

## Sample (fixed)

Drafted rookies of the 2023, 2024 and 2025 classes (seasons 2024, 2025, 2026), joined to the draft file by ESPN
athlete id. Needs: 40+ preseason box minutes, and 5+ regular-season games in his first 15 team games (rookies sit more
than veterans, so the veteran rule of 10 is relaxed; the rule selects on an outcome, so a rookie who never plays in
the first 15 is not scored; reported as a limitation, and the count excluded is reported). Undrafted rookies are not
tested (no pick to anchor, and a pre-2022 veteran cannot be told from a rookie in hoopR). Team-game exclusion as in
`preseason-signals-test.md` amendment 9.

Target: minutes per game played over the first 15 team games.

## Models (leave-one-class-out: fit on two classes, predict the third)

- **R0, today's Lab:** mean early mpg of his draft-pick bucket, from the training classes.
- **R1, candidate:** `early = a + b0 x bucket mean + b1 x 1H preseason mpg`.
- **R2:** `a + b x 1H preseason mpg` (no draft slot).
- **R3, the thread's benchmark:** `a + b0 x bucket mean + b1 x total preseason mpg`.

## Pass rule (fixed)

**PASS** if R1 beats R0 by **0.5 minutes MAE or more with a player-cluster bootstrap z >= 2** (2,000 resamples), **and**
R1 beats R3 by 2+ SE. Rookie minutes are noisier than veterans' (the bucket model's MAE is expected near 6) and the
sample is about 100, so the bar is larger than the veteran one. If R1 beats R0 under the bar, the result is "keep as
context, do not ship".

## Decay (only if the pass rule passes)

Same machinery as `build_preseason_decay.py`, rookies only: replay each rookie's season game by game, `pred = (n x EWMA
+ K x start) / (n + K)` with the Lab's EWMA (alpha 0.25). Standard = R0 start with K = 4 (today). Candidate = R1 start
with K in {2, 4, 8, 12}. Paired MAE gain by games played so far (0, 1-2, 3-5, 6-10, 11-15, 16-25, 26-40, 41+). Retire
rule as for veterans: the preseason term is active through the last bin with gain >= 0.05 min at z >= 2, zero after,
with a linear fade over its last five games.

## What ships on a pass

Rookie eligibility: drafted (draft pick on the depth chart), 40+ preseason minutes, on his preseason team, not Out, no
5+ game absence. They get `min0_pre` like veterans, with the rookie model and its own K and retire game, behind the same
toggle. `min0` is unchanged. On a fail nothing ships.

## Live read (descriptive, not tested)

The 2026-27 class (about 40 rookies with 40+ preseason minutes): current Lab number, preseason-informed number, first-half
minutes and games. Sample sizes beside every row.

## Amendments

2026-10-20, after the pass rule and the decay replay ran:

1. **The retire rule degenerates for rookies.** Applied as written (last bin with gain >= 0.05 min at z >= 2), it returns
   "never retire": the 41+ games bin shows +0.063 min (z 5.1) on 1,716 rows, because even a 4% start weight is worth a
   few hundredths of a minute over that many rows. That is not a useful schedule. Amended: for rookies the materiality bar
   is **0.10 minutes** (the veteran 0.05 was set for a model whose gains were smaller and rows more plentiful), which gives
   a retire game of 26. The same linear fade over the five games before it (weight 1 through game 20, zero from game 26).
   The literal-rule result is reported next to the amended one. The amendment was made after seeing the table, so the
   schedule is a candidate for the 2026-27 holdout like everything else here.
2. **K = 2 sits on the edge of the grid** (2, 4, 8, 12 all tested; smaller was not tried). Same as veterans.

## Results

Run 2026-10-20. Sample: 91 drafted rookies (2024: 27, 2025: 34, 2026: 30) of 106 with 40+ preseason minutes; 15 were
excluded for fewer than 5 games in their first 15 team games.

**The rule passes.** Leave-one-class-out MAE on early-season mpg:

| Model | MAE (min) | Gain vs today's Lab (paired, player-clustered) |
|---|---|---|
| R0, draft-bucket mean (today) | 6.77 | n/a |
| R3, bucket + total preseason mpg | 6.26 | 0.51 (z 1.8) |
| **R1, bucket + 1H preseason mpg** | **5.27** | **1.49 (SE 0.39, z 3.8)** |
| R2, 1H preseason mpg alone | 5.18 | 1.59 (z 3.4) |

R1 beats R3 (the thread's "total minutes") by 0.99 (z 3.6), so the first-half claim holds for rookies too. Correlation
with early mpg: first-half 0.67, total 0.48, draft bucket 0.43. R1 wins in each held-out class (MAE 2024: 6.13 -> 4.38,
2025: 6.70 -> 5.22, 2026: 7.41 -> 6.13).

Checks that it is not a few players: without the five highest first-half rookies (Thompson, Henderson, Wembanyama,
Sarr, Flagg) the gain is 1.44 min (z 3.7). For the 10 rookies who started 3+ preseason games the miss falls from 7.25 to
3.87; for the other 81 from 6.71 to 5.45. Calibration by first-half bin (predicted / actual early mpg): up to 3 min 7.4 /
8.2, 3 to 8 12.6 / 12.2, 8 to 12 17.6 / 17.1, over 12 24.9 / 26.1 (slightly low at the top).

**One finding that changes how to think about rookies: once you know his first-half preseason minutes, the draft slot
adds nothing.** R1 vs R2 is a tie (R2 better by 0.09, z 0.5). We keep the pre-registered R1 (the slot is a reasonable prior
when the preseason sample is tiny, such as a lottery pick with 16 first-half minutes) but the evidence says the preseason
role carries the signal.

Fit (all three classes): `early = 2.31 + 0.31 x bucket mean + 1.17 x 1H preseason mpg`. Bucket means from the same
classes: #1-3 26.0, #4-10 17.6, #11-20 16.5, #21-30 11.2, #31-45 8.8, #46-60 8.9.

### Decay (rookies)

Standard = today's Lab (bucket start, K = 4). Candidate = R1 start, K = 2 (best of 2, 4, 8, 12; MAE games 0 to 30:
5.35, 5.47, 5.70, 5.88).

| Games played so far | Rows | MAE standard | MAE preseason | Gain (min) | z |
|---|---|---|---|---|---|
| 0 | 91 | 7.28 | 5.88 | +1.40 | 3.4 |
| 1-2 | 182 | 6.63 | 5.71 | +0.92 | 3.2 |
| 3-5 | 273 | 6.44 | 5.57 | +0.87 | 5.0 |
| 6-10 | 455 | 5.86 | 5.38 | +0.48 | 4.4 |
| 11-15 | 455 | 5.34 | 5.14 | +0.21 | 3.2 |
| 16-25 | 876 | 5.42 | 5.28 | +0.15 | 3.5 |
| 26-40 | 1,211 | 5.30 | 5.28 | +0.03 | 1.3 |
| 41+ | 1,716 | 5.28 | 5.22 | +0.06 | 5.1 |

Rookies keep the preseason signal about three times longer than veterans (veteran gain at games 6-10: 0.14; rookies
0.48; veterans had nothing after game 10, rookies are still at 0.15 in games 16-25). The literal rule gives "never
retire" (amendment 1); the amended schedule is **active through game 25, fades from game 21, zero from game 26**.

### The live class (2026-27), descriptive

39 rookies with 40+ preseason minutes. Today's Lab number vs with-preseason:

| Rookie | Pick | Preseason 1H mpg (games) | Lab today | With preseason |
|---|---|---|---|---|
| Darius Acuff Jr. | 6 | 18.5 (4, all started) | 17.6 | 29.4 |
| Caleb Wilson | 4 | 16.2 (5, all started) | 17.6 | 26.7 |
| Aday Mara | 10 | 15.4 (5, 3 starts) | 17.6 | 25.8 |
| Yaxel Lendeborg | 12 | 15.2 (5, all started) | 16.4 | 25.2 |
| Keaton Wagler | 5 | 12.7 (3) | 17.6 | 22.5 |
| Kingston Flemings | 8 | 12.1 (5) | 17.6 | 21.9 |
| Hannes Steinbach | 13 | 4.0 (4) | 16.4 | 12.1 |
| Ebuka Okorie | 24 | 1.2 (4) | 11.2 | 7.2 |

Acuff's 18.5 is above anything in the training classes (the previous high is Thompson at 17.1, who played 30.5 early mpg),
so his 29.4 is an extrapolation of a line that was calibrated up to 17. Treat the top of this list as "role, not a
number". Sample sizes are 3 to 5 games and 38 to 81 first-half minutes.

## Verdict

**PASS. Ship-eligible**, same toggle and rules as the veteran term, with the rookie fit and schedule above. Built into the
Minutes Lab toggle in the follow-up PR (`build_preseason_minutes.py` reads `data/rookie_minutes.json`, asserts the pass flag,
and `build_player_projections.py` applies it; schedule: weight 1 through game 20, fade 21-25, zero from 26). Limits: 91
rookies over three classes; 15 who barely played are excluded; the retire game of 26 is an amendment made after seeing
the table; Acuff-level first-half minutes are outside the training range.
