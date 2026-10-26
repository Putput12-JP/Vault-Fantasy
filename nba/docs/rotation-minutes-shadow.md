# Rotation-aware minutes (C3) as a never-priced shadow: build and forward read, registered before any row exists

Written 2026-10-26. Evidence: [rotation-minutes-round3-results.md](rotation-minutes-round3-results.md) (pool-size bias fixed on held-out 2024-25; formal FAIL on the fringe and props), [rotation-minutes-test.md](rotation-minutes-test.md), [rotation-minutes-round2-results.md](rotation-minutes-round2-results.md).
**Nothing here changes a price, a pick or a page.** The model's minutes are logged next to v2's, scored against the box score, and read once under the rule below.

## What is built

- **The model is round 3's C3, frozen.** Three game-state models (close under 10, middle 10 to 19, blowout 20 or more by final margin), each with P(plays), P(rotation | plays) and minutes given rotation, mixed by the pre-game blowout probability, rescaled so the pool's unconditional minutes sum to the fit seasons' mean team total. Features as registered (round 1 features plus the four pool-size features). Fitted **once** by `build_rotation_minutes_model.py` on the walk's 2022-23, 2023-24 and 2024-25 (P(plays) on 2024-25 only), weights in `data/rotation_minutes_model.json`. **2025-26 is not in the fit.** It is never refitted without a new registration.
- **Live inputs, and where they differ from the backtest (stated, not hidden):**
  1. The blowout probability comes from the **market spread** on the board (|spread|, Normal with sd 13.2); the backtest used the game model's walk-forward margin. The v2 minutes model has the same substitution live.
  2. The pool, `m`, starter rate, games, vacated minutes at the player's and other positions, rotation players out, back-to-back and home are exactly `pricing.game_minutes`'s (same candidates, same Out rule).
  3. Last-three-games minutes and team games since a player last played come from two new fields in the daily state (`live.last3`, `live.last_idx`), built by `build_model_state.py` with the backtest's rule (no appearance yet this season: 0 in a team's first three games, otherwise 10).
- **What is logged:** the Minutes record row gains three values after the blend: `rot` (C3's conditional minutes), `size` (the pool size), `tgn` (this game's number for the team), and `rank` (his rank in the pool by `m`). The daily `minutes_days` block gains `rot`: minutes MAE of v2 and of C3 on the same players, and the top-8 bias by pool-size bucket. Rows from before the merge have no `rot` and are not rebuilt.

## Forward read (fixed now)

Population: players who played, in games whose last pre-tip Minutes row carries `rot`. Game is the unit; bootstrap 2,000 draws, seed 7; t = mean / sd of the bootstrap means. **Read once, on or after 2026-12-15, when there are at least 150 games and 3,000 player-games**, using every qualifying game up to then. Not before.

1. **Overall:** minutes MAE of C3 below v2, gain > 0 with t >= 2.5.
2. **Pool size (the point):** for the top 8 by `m`, mean(projected minus actual) within **0.5 minutes** for C3 in each of pools of **15 or more** and **12 or fewer**, each bucket with at least 500 player-games (a bucket short of 500 is reported "collecting" and the read waits for it, up to 2027-02-01, then fails by default). v2's biases are reported beside them.
3. **First 15 team games:** gain > 0 with t >= 2.5 (`tgn` 15 or less).
4. **Props** (the blend test's approximation, applied to the lean log's first-look `mu` for single-stat pts, reb, ast, 3pm, `mu_new = mu x rot / pm`): pooled gain > 0 with t >= 2.5 and no stat's MAE worse.

**PASS** needs all four: C3 becomes a *candidate for a pricing proposal* (its own pull request and its own test). It is never priced by this result. **FAIL** is reported as it falls and the shadow is turned off by a pull request.
**Context, no verdict:** ranks 9 and 10 (the known weakness: about 0.8 minutes too low in every earlier round), the fringe cut, the cut with a rotation player out, bias by pool size for every bucket, and C3 against the early-season blend.

## Not in scope

Pricing, the Game Simulation (the frozen B3 model and its 2026-11-16 holdout are untouched), the page and any JS port, a hard rotation set, other cut-offs, refits.

## Order of work

1. Pure scoring module (`rotation_minutes.py`) with a test that it equals the registered test's functions on random inputs; fit script; run the fit once.
2. State export (`last3`, `last_idx`); `Pricer.game_minutes_rot`; Minutes record and daily block; tests.
3. Scorer `score_rotation_forward.py` implementing the rule above; scheduled read.
4. One pull request with a before-and-after (priced output identical).


## As built (2026-10-26)

- **Model file:** `data/rotation_minutes_model.json`: T 239.67, fit on 101,425 pool rows (walk seasons 2023 to 2025), P(plays) on 34,161 rows of 2024-25. 2025-26 not in the fit.
- **Proof that the saved weights and the live scoring module equal the registered round 3 model:** on the 2025-26 pools, minutes MAE 4.9218 (v2) to **4.7707**, and top-8 bias by pool size +0.52, +0.46, +0.34 (v2 +1.22, -0.39, -1.83), the numbers round 3 reported as context. `tests/test_rotation_minutes_shadow.py` also proves the features, state probabilities and the whole-pool score equal the registered test's functions.
- **What could not be proven offline, stated plainly:** that the live feature construction (`Pricer.game_minutes_rot`, from the daily state and the board) gives the same inputs the backtest had. A trial on an end-of-season state (stars long out, no injury statuses, tip after the playoffs) was off-distribution and showed the model well above v2 for the top players, so it proves nothing either way. The method logs nothing until the daily state carries `last3` and `last_idx`.
- **Launch check (operational, not a verdict), registered now:** after the first two settled nights, `minutes_days[...].rot` must show, over players who played, a mean (C3 minus v2) for the top 8 by `m` within **1.5 minutes**, and C3's MAE not above v2's by more than **0.3**. If either fails, the shadow is turned off by a pull request until the live inputs are understood. This check cannot keep or promote anything.
- **Logged:** Minutes record row values 6 to 9 (`rot`, `size`, `tgn`, `rank`); the daily block's `rot` (n, mae_v2, mae_rot, top-8 bias by pool size). Scorer `score_rotation_forward.py` with the rule above; read on or after 2026-12-15.
- Priced output is identical (`check_pricing_regression`: all four sections IDENTICAL). 25 related tests pass.
