# Rotation-aware minutes, round 2: results

Rules: [rotation-minutes-round2.md](rotation-minutes-round2.md), committed before the round 2 runner (`2335fea0a`). Numbers: `nba/data/rotation_minutes_round2.json`. Run once on 2026-10-25. Nothing here changes what the page prices or bets.

## Verdict: **FAIL** (2 of 6 conditions met)

C2 = round 1's candidate C plus a bias shift by rank group (ranks 1 to 8, 9 to 10, 11 and below), fitted on the last 40% of 2024-25 from models that had not seen it: shifts **+0.209, +0.834, -0.253** minutes.

| Condition | Needed | Got | Met |
|---|---|---|---|
| Top-8 bias within 0.5 min in every pool-size bucket | all three, n >= 1,000 | 12 or fewer **+1.10**, 13 to 14 **+0.59**, 15 or more +0.09 | **no** |
| Overall minutes MAE, C2 against A | t >= 2.5 | 4.922 to 4.794, gain 0.128, t 9.06 | yes |
| Fringe (ranks 9 to 12) gain | >= 0 | -0.015 (t -0.77) | **no** |
| Cuts: rotation player Out, first 15 team games | t >= 2.5 | +0.111 (7.08), +0.189 (6.29) | yes |
| Props pooled gain, no stat worse | t >= 2.5 | -0.09% (t -1.32); rebounds, assists, 3PM worse | **no** |
| Top-8 bias within 0.3; ranks 9 to 10 within 0.5 | both | +0.65; +0.05 | **no** |

## Read

- **The calibration made the main target worse.** The 2024-25 shift moved the top 8 up (+0.21), but in 2025-26 the unshifted C was already over-projecting the top 8 (+0.44), so C2 ends at +0.65. A shift fitted on one season did not transfer to the next. It also left rebounds, assists and 3-pointers slightly worse.
- **What it did fix:** padded pools. For pools of 15 or more, top-8 bias went from the old model's -1.83 to +0.09. Minutes given to players who do not dress fell from 26.3 to 15.0 per team-game. The rotation's minutes are no longer being taken in padded pools.
- **What it did not fix:** short pools. With 12 or fewer candidates, the top 8 are still +1.1 minutes too high (the old model: +1.2), and it is the same in all four seasons.

## A hypothesis that did not hold

I suspected short pools were short because actual rotation players were missing from them (call-ups, returners), so the remaining players were handed minutes that belonged to someone else. That predicts that short pools cover fewer than 240 actual minutes. They do not: pools of 11 or fewer cover 236 to 239, pools of 15 or more cover 240 to 242, in every season. The total is right; the *split inside a short pool* is wrong.

The likelier cause is that neither the old model nor round 1 knows the pool size. With fewer players, the deep bench plays more than its recent minutes imply (there is no 13th to 15th man to share garbage time), so a proportional split gives the top 8 too much. Pool size was not a feature. This is a hypothesis, not a result.

## Where this leaves it

- Round 1 and 2 both improve minutes (about 0.12 to 0.13 per player, 0.19 to 0.20 in the first 15 games) but neither moves props, and neither passes the registered bar.
- A third round would add pool size (and its interaction with rank) to the models and drop the calibration shift. Pool-size bias replicates in 2022-23, 2023-24 and 2024-25, so the model can be fitted and validated **without 2025-26**. 2025-26 has now been read twice and should not be used to select anything again; the confirmation should be the 2026-27 forward shadow.
