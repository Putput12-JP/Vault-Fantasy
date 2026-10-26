# Rotation-aware minutes, round 3: tell the model how big the pool is

Written 2026-10-25, before round 3 was fitted or scored. Rounds 1 and 2 (`rotation-minutes-results.md`, `rotation-minutes-round2-results.md`) both failed their bars. What they left open:
padded pools (15 or more candidates) were fixed, but with **12 or fewer candidates the top 8 are still about 1.1 minutes too high** in the old model and in C, in all four seasons. Round 2's hypothesis that short pools miss real rotation players was tested and rejected
(short pools cover 236 to 239 actual minutes). The remaining suspect is that the models do not know the pool size: with fewer players the deep bench plays more than recent minutes imply, so a proportional split gives the top 8 too much.

## Discipline

2025-26 has been read twice and **is not used to fit or select anything in this round.** The verdict is on a validation slice of 2024-25 that no model in this round has seen; 2025-26 is reported afterwards as context with no verdict.
The pool-size bias of the *old* model (A, no fitting) was read in all four seasons before this round was written; no round 3 model has been run.

## Candidate C3 (the only one)

Round 1's candidate C (three game-state models mixed by the pre-game blowout probability, same features, same rescale), **with four added features in every model** (P(plays), P(rotation | plays), minutes given rotation):
`size / 15`, `1 if size >= 15`, `1 if size <= 12`, `(size - 13) / 5 x rank / 10`, where size is the number of candidates in the team's pool that game and rank is the player's rank in it by recent minutes. No calibration shift.

## Split

- **Fit:** 2022-23, 2023-24 and the first 60% of 2024-25 (by game id); P(plays) on that 60% of 2024-25 only (the report-era rows). Ridge, iterations and thresholds as in round 1.
- **Validation (verdict):** the last 40% of 2024-25 games (about 1,000 team-games), which no model in this round has seen.
- **Context, no verdict:** C3 fitted on all of 2022-23 to 2024-25, scored on 2025-26; and round 1's C refitted on the same fit slice, scored on the validation slice, to show what pool size adds.

## Verdict, on the validation slice (players who played; game as the unit; bootstrap 2,000 draws, seed 7)

1. **Pool-size robustness.** Ex-ante top 8 (rank 1 to 8 by recent minutes): |bias| of C3 at most **0.5 minutes** in each of the three pool-size buckets (12 or fewer, 13 to 14, 15 or more), each with 1,000 or more player-games.
2. **Overall minutes MAE**, C3 against A: lower, t >= 2.5.
3. **Fringe** (ranks 9 to 12): C3 against A, gain >= 0.
4. **Rotation player Out** cut: gain positive with t >= 2.5. (The first-15-games cut is not available: the validation slice is the end of the season.)
5. **Props** (blend test approximation, pts / reb / ast / 3pm): pooled gain > 0 with t >= 2.5, no stat's MAE worse.
6. **Top-8 bias overall** within 0.3 minutes; ranks 9 to 10 within 0.5.

**PASS** needs all six. Anything else is FAIL, reported as it falls. A PASS earns a shadow field and a forward read on 2026-27, never pricing directly.

## Not scored

Any other feature, a calibration shift, a different pool-size definition, a hard rotation set, refitting on 2025-26, and the single-state control B.

## Forward step

If it passes, shadow-field it (Minutes record, never priced) with its own pre-registered read on 2026-27. The daily state job would export rank, last-3 minutes, team games since a player last played, and the pool size.
