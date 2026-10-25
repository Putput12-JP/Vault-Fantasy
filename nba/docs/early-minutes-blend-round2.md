# Early-season minutes blend, round 2: two held-out seasons

Written 2026-10-25, before round 2 was scored. Round 1 (`early-minutes-blend-test.md`, `early-minutes-blend-results.md`) passed on 2025-26 with w = 0.394 fitted on 2024-25.
Round 2 asks whether that was one season's luck. Rules are the verdict; every result is reported.

## What is fixed

- **w = 0.3939, frozen from round 1.** Not refitted, not re-tuned, no other weight scored.
- Same definitions as round 1: team games 4 to 10, the player's average over his team's games 1 to 3 (he needs 2 of the 3, with that team), `pm_new = pm + w (f - pm)`, `mu_new = mu x pm_new / pm`, players who played, pts / reb / ast / 3pm, game as the unit, 2,000-draw bootstrap, seed 7, same walk records (`build_prop_model_v2.walk`).
- **Seasons scored: walk seasons 2023 (2022-23) and 2024 (2023-24)**, each on its own. Season 2022 is the walk's warm-up and is not scored.

## Honest limit

The minutes model's weights were fitted on 2022-23 and 2023-24 (`docs/minutes-model.md`), so these two seasons are **in-sample for the minutes model, not for the blend**. The blend has one parameter and was never fitted on them, but a model tuned on a season is usually a little better there than it will be live. This round can say "the effect is not a 2025-26 fluke". It cannot say how big the live effect is; round 1 and the forward shadow are the size estimates.

## Verdict, per season

A season **PASSES** if all hold (the round 1 conditions, same bar):
1. Minutes MAE lower under the blend, game-clustered t >= 2.5.
2. Props pooled gain > 0, t >= 2.5.
3. None of the four stats' MAE worse.
4. The minutes gain positive in both halves of the window (team games 4 to 7 and 8 to 10).

**Round 2 holds** only if **both seasons pass**. One pass and one fail is reported as "mixed" and the round 1 result stays a single-season finding. The w-strictly-inside condition is dropped: w is not fitted here.

Context, no verdict: the gain by team-game bucket in each season, to check the "slow start, gone by about game 20" shape from round 1 (`early-minutes-blend-results.md`).

## Not scored

Refitting w on these seasons, a pooled three-season fit, two games instead of three, other windows or weights, 2021-22.

## Runner

`nba/scripts/test_early_minutes_blend.py --round2` (uses the same walk records; the walk is cached). Written after this file is committed.
