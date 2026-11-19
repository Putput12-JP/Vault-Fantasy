# Game model: garbage-time RAPM on five seasons, pre-registration

Written 2026-11-19, before `nba/scripts/test_rapm_history_g.py` was run. Completes the grid left open by PR 512 (garbage time, three seasons) and PR 516 (five seasons, all stints). Stacked on PR 516. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Definition

Identical to `rapm-history-prereg.md` in every respect (stints from 2021-22 to 2025-26, the tuned yearly decay D in {0.5, 0.7, 0.85, 1.0}, ridge lambda in {3000, 10000}, C in {0.5, 0.75, 1.0} for replace, LAM in {0.5, 1, 2} for add, tuning on 2022-23 and 2023-24 from 28 days into each season, the same test seasons, scoring and verdict rules), with one change: **garbage stints are removed** (the `rapm-prereg.md` ladder: a 4th-quarter lead of at least 25 with 9:00 or less left, 20 with 6:00, or 15 with 3:00; stints starting at or after it are dropped; overtime games have none).

Variants: **GLO** (replace) and **GLB** (add). The A-versus-G comparison against PR 516's results is exploratory and carries no verdict.

## Verdict rules

As before: Better only if pooled whole-season t of at least 2 against S, the same sign in each test season, and the information test against the close within 1 t of S. A pass leads to a frozen forward test, never to shipping.
