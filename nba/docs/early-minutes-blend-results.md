# Early-season minutes blend: results

Rules: [early-minutes-blend-test.md](early-minutes-blend-test.md), committed before the runner (`8c34dc71a`), runner `test_early_minutes_blend.py` committed before it was run.
Numbers: `nba/data/early_minutes_blend.json`. Run once on 2026-10-25. Nothing here changes what the page prices or bets.

## Verdict: **PASS** on every condition (shadow-track candidate, not a change)

w, fitted once on the 2024-25 window (team games 4 to 10, 1,797 blended rows) and frozen: **0.394**. Meaning: lean about 39% on the player's average over his team's first three games, 61% on the projection the model already made.

Scored on 2025-26, team games 4 to 10: 2,208 player-games who played, 1,886 blended (85%; the rest played fewer than 2 of the first 3 games and were left alone), 132 games.

| | Old (as first graded) | Blended | Gain | t |
|---|---|---|---|---|
| Minutes MAE | 5.119 | 4.622 | 0.497 min (95% interval 0.370 to 0.630) | **7.25** |
| Points MAE | 4.888 | 4.763 | 0.125 | |
| Rebounds MAE | 1.915 | 1.874 | 0.042 | |
| Assists MAE | 1.392 | 1.372 | 0.020 | |
| 3PM MAE | 0.941 | 0.927 | 0.014 | |
| Props pooled gain (each stat's error as a share of its own MAE) | | | 0.0190 (1.9%) | **5.97** |

| Condition | Needed | Got |
|---|---|---|
| Minutes t | >= 2.5 | 7.25 |
| Props t | >= 2.5 | 5.97 |
| No stat worse | all four better | all four better |
| Both halves positive (team games 4 to 7, 8 to 10) | yes | +0.519 and +0.469 min |
| w strictly inside 0 and 1 | yes | 0.394 |

**Flagged for close monitoring (improves, sample size):** minutes MAE 5.12 to 4.62 on 1,886 player-games from 132 games; props 1.9% lower error on 7,544 stat-rows.

## Context (no verdict)

- Same w, 2025-26 team games 11 to 20: minutes 4.581 to 4.462 (gain 0.119, t 3.00, 2,770 rows); props pooled gain 0.0096 (t 4.17), all four stats better. **The gain shrinks to about a quarter but does not vanish**, so the minutes model also under-weights recent games after the first ten, not only early. This round does not test whether that holds all year.
- In-sample on 2024-25 window: 4.961 to 4.589 (as expected, a bit smaller than the held-out season, so this is not an overfit of w).

## What this does and does not say

- It says the minutes the walk projected for games 4 to 10 were too anchored on last season, and a one-parameter blend with the first three games fixes about 10% of the minutes error and about 2 to 3% of the points error. The size is plausible: after three games the model's smoothing still gives last season roughly half the weight.
- It does **not** say the props beat the market. The market sees the same three games, so a better projection is only an edge where it differs from the line, and the 2025-26 priced lines in this window number only a few hundred (too few for a price-level test). The honest next test is price-level and forward.
- **Props are approximated:** `mu_new = mu x pm_new / pm`. The per-minute rate and the usage cascade are not re-run, so the true gain through the full pricer could be a little different in either direction.
- Not run this round: two games instead of three, other weights or windows, per-position weights. The 2025-26 walk has been used many times (`experiment-log.md` section 1); w was fitted on a different season, and the t-values clear 2.5 by a wide margin, which limits the multiplicity worry but does not remove it.
