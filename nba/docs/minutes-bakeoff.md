# Minutes bake-off: GBM conditional minutes x P(plays), scaled to 240 expected

Written 2026-10-28, before any number below was computed. Script: `scripts/test_minutes_bakeoff.py`. Results go to `minutes-bakeoff-results.md`.
Motivation: [minutes-audit-2026-10-28.md](minutes-audit-2026-10-28.md) (priced minutes sum to 283 per team-game, 46 of them on players who did not play).

## Candidates (all scored once on 2025-26, the pool the rotation test uses: as-of candidates, Out players excluded)
- **A, v2**: the walk's `pm` (priced today; pool scaled to 251.6).
- **C3**: the frozen rotation model (`data/rotation_minutes_model.json`; fitted without 2025-26).
- **G**: LightGBM conditional minutes (`minutes_gbm.py` features, `build_minutes_spread.MEAN_KW`), refit on 2023-2025 only, with **no oracle absences**: a rotation player is Out when he is in the rotation and not in that game's pool. Players with no minutes history keep v2's number.
- **GP (the proposal)**: G's conditional minutes, C3's P(plays) and the C3 rescale, so the pool's expected minutes (P x minutes) sum to T = 239.67, conditional minutes capped at 48.

## Rule (fixed now). GP is promoted to pricing only if ALL hold
1. Players who played: GP minutes MAE below v2's with paired t >= 3 (game is the unit), and not above C3's.
2. Top 8 by `m`: mean(projected - actual) within 0.5 minutes in each pool-size bucket (12 or fewer, 13-14, 15 or more) that has 500+ player-games, or smaller in size than v2's in every bucket.
3. Props proxy (`mu_new = mu x new / pm`, single stat pts, reb, ast, 3pm): no stat's MAE worse than v2's.
4. Expected minutes (P x minutes, DNP counted as 0): MAE below v2's expected minutes (v2 minutes x C3 P(plays)) over all pool rows.
Otherwise the best candidate that passes is reported and nothing is promoted. Variants not listed here are context only.
