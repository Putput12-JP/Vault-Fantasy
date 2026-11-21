# Game model round 3: ratings that also learn from the closing line

Written 2026-11-10, before the variant was scored on any season. Runner: `nba/scripts/test_game_model_round3.py`.
Results land in `nba/docs/game-model-round3-results.md` only after this file is committed.

## Why

Rounds 1 and 2 changed how the ratings learn from **results** (possession ratings, a bigger early step, a blowout cap) and none beat the shipped model.
The audit (`docs/game-picks-audit.md`) says the miss is not in how fast the model learns from results. It is that a final score is a very noisy
reading of how good a team is (finals scatter about 13 points around the line), while the closing line is a quiet one. The model sits 3 to 5 points
from the market on the same teams every night (LAC, CHA, MIL, SAC high; MIA, PHI, BOS low), the market has been closer on them, and the model never
hears it: it would take dozens of results to learn what one closing number already says.

**Question.** If each team's rating also moves toward what the closing line of its last game said, does the model predict the next margin better?

No look-ahead: a game's closing line is fixed at tip and is used only in the update that runs after that game, exactly when its final score is. A
prediction never sees its own game's line.

## What this is, said before the numbers

A model taught by the market sits closer to the market. If it passes it is a **better margin estimate** (the Vault line on the Slate, the win %),
not an edge: the gap to the line shrinks by construction, grade A spread picks become rare, and the winner pick agrees with the favourite more
often. What stays the model's own is the injury report, rest and home court it applies on top of the ratings. Sharp money is not an input.

## What is held fixed

Closing lines exist for 2024-25 and 2025-26 only (labels 2025, 2026), so the cut is: **fit on 2024-25, score on 2025-26**, then report this season.
Ratings arrive at 2024-25 from results alone (2021-22 to 2023-24, shipped parameters). Games with no closing spread update as the shipped model
does. Every other parameter keeps its shipped value. Nothing here writes `data/game_model.json`.

## The variant (fixed now; no other is scored this round)

**L, learn from the line.** After a game that had a closing spread, the miss that moves the two team ratings is

    W x (closing home margin - model margin) + (1 - W) x (final home margin - model margin)

with the model margin the one the update already uses (who actually played), and the rating step KL for both teams. Scoring (offense, defense), home
court and player values update as shipped.

**Choosing W and KL.** W from {0.25, 0.5, 0.75, 1.0}, KL from {0.04, 0.08, 0.12, 0.16, 0.24, 0.32, 0.5}, one pass over the grid, minimising 2024-25
margin MAE with the injury report at tip on games that have a closing spread. The shipped model (W = 0) is the reference row. A value on a grid
endpoint is reported.

## Metrics

On 2025-26 (the test), games with a closing spread, injury report at tip:

1. Margin MAE against the final margin, and for the first 4 weeks; the closing line's own MAE beside it.
2. The information test (`build_game_model.info_test`) and the record against the closing spread at a gap of 0+, 3+ and 5+.
3. How far the variant sits from the line (mean absolute gap, share of games at 3+ and 5+) next to the shipped model.

A difference is `mean(|error S| - |error L|) / SE` over games: positive means L is closer.

On this season (154 games through 2026-11-09): L walked the way the live state is built (2024-25, 2025-26, then this season), learning from each
game's closing spread (this season: the record's last look before tip, DraftKings). Its margin for a game is its ratings-only margin plus the
injury and rest adjustment the recorder applied, scored against the locked first-look line. Margin MAE, spread and winner records, picks that change
side.

## Verdict (fixed now)

- **Better**: on 2025-26 the margin-MAE t is 2.5 or more, the information test's t is not lower than the shipped model's by more than 1, and on this
  season's replay L's margin MAE is not worse than the shipped model's.
- A Better verdict is a recommendation, not a release. Shipping it means feeding closing lines to the daily state build (it has none today) and it
  changes the Vault line the Slate, the win % and the paper bot read, so it goes in its own pull request. Locked picks are never re-priced; the
  replayed record is shown beside the locked one and labelled a replay.
- This season's replay rows are flagged for monitoring with n = 154 whichever way they point.
