# Matchup volume test: does the shot-diet matchup predict the miss in a player's attempts and assists?

Written 2026-10-25, before any index was built or scored. The rules are the verdict; every result is reported, pass or fail.
Nothing here changes what the page prices or bets. A pass earns a Stage 2 price test and a shadow field, never a direct pricing change.

## Why the earlier test says little

`docs/diet-test.md` (NO-GO, display-only) added one column, projected mean x a zone score, to every stat, and judged it by Kalshi and sportsbook ROI.
Its fit season (2024-25) had no prior-season shot data, so the feature was degraded when the coefficient was learned; the one column moved every stat (points bias +0.48) rather than the stat it relates to;
and the bar was a profitable bet against prices that already include matchups. It also used only shot zones, not shot type or assist locations. A NO-GO on that design is weak evidence that matchups carry nothing.

What the data measures, and does not: shots allowed per 48 by zone, and assists allowed per 48 by assist location (build_diet_defense.py). That is **volume**. It says nothing about how often shots go in, so it can sharpen
attempts and assists, not shooting percentage. Stage 1 therefore tests exactly two stats.

## Stage 1: accuracy, the volume the model misses (this document)

**Data.** `raw/hoopr/pbp_2024.csv`, `pbp_2025.csv`, `pbp_2026.csv` (regular season, shots with a coordinate), and the v2 walk records (`build_prop_model_v2.walk`) for 2024-25 (fit) and 2025-26 (test).
2023-24 play-by-play has coordinates for only 7 games, so 2024-25 has **no prior season**: its defenses count only after 15 games (before that the index is 0, the row is not scored), and a player needs 50 effective shots.

**Point-in-time rules (the Matchups page's own).** Everything uses shots from days before the game. A defense's rate = `w x current + (1 - w) x prior season`, w = games / 15 capped at 1 (2024-25: current only, from game 15). The league mean is the
mean over defenses. `vs = rate / mean - 1`. A player's shares blend his prior season at weight `max(0, 1 - his current attempts / 200)` (assists: `/ 80`), none in 2024-25.

**The two indices (fixed now).**
- **3PM, attempts.** `m3 = (share_c3 x vs_c3 + share_ab3 x vs_ab3) / (share_c3 + share_ab3)`, the player's own 3-point mix against the opponent's allowance. Target: the miss in 3-point attempts, `y3pa - pm x r3` (projected attempts = projected minutes x his 3PA per minute, the walk's own numbers).
- **AST.** `ma = sum over the five assist locations of (his share of assists from that location x vs of the opponent's assists allowed there)`. Target: `y_ast - mu_ast` (the walk's projection).
- **Control** for each: the same index with a random other defense (seed 7). Any gain there is an artifact.
- The effect on the projection is `projected x (1 + beta x index)`, beta a single slope per stat, clipped to a multiplier of 0.7 to 1.3.

**Fit and test.** beta is fitted once by least squares through the origin on 2024-25 rows with an index (residual on `projected x index`) and **frozen**. Test: 2025-26, players who played, game as the unit, bootstrap 2,000 draws, seed 7.

**Per-stat PASS** (3PM and AST each judged alone) needs all of:
1. beta fitted on 2024-25 is positive (a higher index means more attempts or assists than the model projected).
2. Applying the frozen beta to 2025-26 lowers the **volume MAE** (3PA for 3PM; assists for AST) against the walk's projection, t >= 2.5.
3. The same beta on the **control** index does not (t < 2.5); and beta re-estimated on 2025-26 alone is positive with t >= 2.5.
4. The gain is positive in both halves of 2025-26 (by game id).
5. The effect carries to the stat: the **stat MAE** (3PM, assists) with the multiplier applied to the projection is not worse than the walk's.

Anything else is FAIL, reported as it falls. Coverage (rows with an index of 0 because of thin data) is reported.

**Context, no verdict:** the gain by index quintile (does the top quintile get the volume the page says), the same test with the opponent-only team index (3PA allowed vs league, assists allowed vs league, no player mix), and the share of rows scored.

## Not scored

Points and rebounds (no volume index is registered for them), shot-type and transition indices, per-zone betas, a different prior weight or shrink, refitting on 2025-26, and any price or ROI measure.

## Stage 2 (only for a stat that passes Stage 1)

Registered separately before it is read: the multiplier applied inside the pricer for that stat, scored on Kalshi and sportsbook prices (log loss and ROI) with the control, and the forward 2026-27 shadow as the confirmation.
2025-26 has been read many times, so no adoption rests on this test alone.

## Clarifications made before any index was built (2026-10-25)

- A 3PM index needs the player's 3-point shots (corner plus above the break) to be at least 5% of his effective attempts; below that the index is undefined and the row is not scored.
- An AST index needs at least 30 effective assists (current plus prior-season weight); below that the row is not scored.
- Rows with a missing 3PA-per-minute (a player with fewer than 3 games of shooting history) are not scored for 3PM.
- The opponent-only context index is: 3PA allowed (corner plus above the break) against the league mean for 3PM, and total assists allowed against the league mean for AST.
