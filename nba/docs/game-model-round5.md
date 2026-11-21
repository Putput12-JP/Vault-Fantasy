# Game model round 5: the line-taught model in full, every game out of sample

Written 2026-11-10, before the cross-fit below was run and before the totals variant was scored on anything.
Runner: `nba/scripts/test_game_model_round5.py`. Results land in `nba/docs/game-model-round5-results.md` only after this file is committed.

## Why, and what is different from round 3

Round 3 let the team ratings learn from each game's closing spread as well as its final. It was closer to the final margin in all three seasons and
missed its bar on the one season it was tested on (2025-26, t 2.21 against 2.5; this season's 154 games, t 2.11). That design could only test one
season, because closing lines exist for two and the other was used to fit.

This round asks the same question with all of the data, and one new one.

1. **Margin, second look.** The same option L, scored by cross-fit: each of the two lined seasons is predicted with W and KL chosen on the
   **other** season, so all 2,641 games are out of sample for the parameters. Because this is the second look at one idea, the bar goes **up**, from
   2.5 to **3.0**.
2. **Total, first look.** Option LT: the scoring ratings (offense, defense, league base) also learn from each game's closing total. The model's
   total is its weakest number (MAE 14.85 against the closing total's 14.32; it runs about 4 points low in the first weeks of a season). Never tested.

Honest accounting of what is already known: the fold "fit 2024-25, score 2025-26" is round 3 (t 2.21). The other fold is new. 2024-25 scored
3.35 with parameters fitted on itself, which is in sample and proves nothing; the new fold scores it with 2025-26's parameters.

No look-ahead in either: a game's closing spread and total are used only in the update that runs after that game.

## What this is, said before the numbers

A model taught by the market sits closer to the market. A pass is a **more accurate Vault line** (the margin, total and win % the Slate shows). It
is **not** an edge and is not expected to change the spread record: round 3 already showed the line-taught margin at 49.7% against the closing
spread, the same as the shipped model. Sharp money is not an input.

## The variants (fixed now)

**L (margin).** As round 3: after a game with a closing spread the miss that moves the two team ratings is
`W x (closing home margin - model margin) + (1 - W) x (final home margin - model margin)`, step KL.
Grid: W {0.25, 0.5, 0.75, 1.0}, KL {0.04, 0.08, 0.12, 0.16, 0.24, 0.32, 0.5}.

**LT (total).** After a game with a closing total, each side's points miss that moves offense, defense and the league base is
`WT x (market points - model points) + (1 - WT) x (actual points - model points)`, where the market's points for the home side are
(closing total + closing home margin) / 2 and for the away side (closing total - closing home margin) / 2, step KT.
Grid: WT {0.25, 0.5, 0.75, 1.0}, KT {0.03, 0.05, 0.08, 0.12, 0.16, 0.24}.

The margin and the total do not interact in this model (ratings and scoring update separately), so the two grids are run separately, each with
the other at its shipped value. Everything else keeps its shipped value. Nothing here writes `data/game_model.json`.

**Cross-fit.** For each grid point the model walks 2021-22 through 2025-26 once. Fold A: the point with the lowest 2024-25 MAE (injury report at
tip, games with a closing line) is scored on 2025-26. Fold B: the point with the lowest 2025-26 MAE is scored on 2024-25. The two out-of-sample
seasons are pooled. **Ship parameters** = the point with the lowest MAE over both seasons together; they are what this season is scored with.

## Metrics

- Margin MAE and total MAE against the finals, shipped against variant, per fold and pooled: `mean(|error S| - |error V|) / SE` over games.
- The information test against the closing spread (margin) and closing total (total), pooled out of sample, beside the shipped model's.
- The closing line's own MAE, the bar neither is expected to clear.
- This season (154 games through 2026-11-09), with the ship parameters, walked as the live state is (2024-25, 2025-26, this season), learning from
  each game's last DraftKings look before tip (`data/game_first_looks.json`). Margin: ratings-only margin plus the injury and rest adjustment the
  recorder applied, against the locked margin. Total: ratings-only total, against the shipped model's replayed total.

## Verdicts (fixed now)

- **Margin GO**: pooled out-of-sample t >= 3.0, closer in each fold, closer on this season, and the pooled information test's t not lower than the
  shipped model's by more than 1.
- **Total GO**: pooled out-of-sample t >= 2.5, closer in each fold, and closer on this season.
- A GO is a GO **for accuracy**. It says: ship these ratings as the Vault line. It does not say the picks win, and the results file repeats the
  spread record of the variant beside it so nobody reads it that way.
- Shipping is its own pull request: the daily state build has no closing lines today, and the change moves the Vault line the Slate, the win %, the
  Game Picks page and the totals paper bot (`scripts/paper_bot/signals/nba_total.py`) read. Locked picks are never re-priced.
