# Rotation-aware minutes, round 2: stop padded pools taking the rotation's minutes

Written 2026-10-25, before round 2 was fitted or scored. Round 1 (`rotation-minutes-test.md`, `rotation-minutes-results.md`) failed its bar: minutes got better overall but not at the fringe, and props barely moved.
This round is about the specific harm: **players who will not see the court are given minutes, and the team total then takes them from the players who will.**

## What the diagnostics showed (all before this round was designed, descriptive)

The old model (A) rescales every pool to 264.9 minutes whatever its size. For the **top 8 players by recent minutes in the pool** (a pre-tip definition), bias = projected minus actual minutes:

| Pool size (candidates) | 2022-23 | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|---|
| 12 or fewer | +1.16 | +1.11 | +1.10 | +1.22 |
| 13 to 14 | -0.07 | -0.11 | -0.25 | -0.39 |
| 15 or more | -0.58 | -0.38 | -2.02 | -1.83 |

It holds in all four seasons. Padded pools (15 or more, typically long injury lists and two-way call-ups) take up to 2 minutes from each rotation player; short pools hand them 1.1 too many. A also gives about 26 minutes per team-game to players who do not dress (round 1's model: 15).
Round 1's candidate C cut the pool-size spread (bias +0.89 / +0.29 / -0.12 in 2025-26) but over-projects the top 8 overall (+0.44) and under-projects ranks 9 and 10 (-0.79).
A figure I quoted earlier, "rotation players 1.1 min short", selected players on having played 12 or more minutes and was biased; it is withdrawn. The ex-ante top-8 definition above is the one used from here.

**Disclosure.** Round 1's 2025-26 predictions were read for these diagnostics, so 2025-26 is no longer an untouched test season. Round 2's calibration is fitted on 2024-25 only and never on 2025-26, but the *choice* of what to fix was informed by 2025-26. Any adoption therefore needs the forward 2026-27 shadow read, whatever this round shows.

## Candidate C2 (the only one)

C2 = round 1's candidate C (same features, same three state models, same mixture, same rescale) **plus a bias calibration by ex-ante rank group**: `C2 = C + delta_g`, g in {ranks 1 to 8, ranks 9 and 10, ranks 11 and below}, delta_g = mean(actual - C) over players who played in the calibration set.
**Calibration set:** the last 40% of 2024-25 games (by game id), predicted by models fitted **without** them (fit on 2022-23, 2023-24 and the first 60% of 2024-25; P(plays) on that first 60% only). delta_g is then frozen and applied to the 2025-26 predictions of the round 1 models (fitted on all three fit seasons). The team total is not re-forced after the shift; its drift is reported.

## Tests on 2025-26 (players who played, as before; game as the unit, bootstrap 2,000 draws, seed 7)

1. **Pool-size robustness (the point of the round).** For the ex-ante top 8, |bias| of C2 at most **0.5 minutes** in each of the three pool-size buckets (12 or fewer, 13 to 14, 15 or more), each bucket with 1,000 or more player-games. A's biases are shown beside it.
2. **Overall minutes MAE**, C2 against A: lower, t >= 2.5.
3. **Fringe**: the rank 9 to 12 cut, C2 against A, gain >= 0 (round 1 failed this at -0.035).
4. **Cuts (a) a rotation player is Out and (e) each team's first 15 games**: gain positive with t >= 2.5.
5. **Props** (the blend test's approximation, pts / reb / ast / 3pm): pooled gain > 0 with t >= 2.5, and no stat's MAE worse.
6. **Top-8 bias overall** within 0.3 minutes, and rank 9 to 10 within 0.5.

**PASS** needs all six. Anything else is FAIL, reported as it falls, including a minutes gain with no prop gain.
**Context, no verdict:** minutes per team-game given to players who do not dress (A, C, C2); team-total drift of C2; ranking quality of P(rotation) among ranks 9 to 12 (AUC; round 1 diagnostic: model 0.819, A's projection 0.786, recent minutes alone 0.737).

## Not scored

Any other group split for the calibration, a multiplicative calibration, a hard rotation set with a fixed minimum for the rest, other rotation cut-offs, refitting the models, and C versus single model B.

## If it passes

Shadow-field it next to v2 and the early-season blend (Minutes record, never priced), with its own pre-registered forward read. The daily state job would need to export rank, last-3 minutes and team games since a player last played, which is the build step.
