# Game model: market-anchored projection, results

Generated 2026-11-23 by `nba/scripts/test_game_model_anchored.py`. Rules: [game-model-anchored.md](game-model-anchored.md) (committed before this ran, `882b020a`).

**Verdict: NO-GO on every rule.** Neither part of the model's gap carries information against the close, and no anchored projection beats the line.

## Information test: result - line = a + g1 (ratings part) + g2 (news part)

History: ratings part = model at the 1pm report minus the closing line; news part = model at 30 minutes before tip minus model at 1pm. This season: ratings part = 4-hour margin
minus the lock line; news part = lock margin minus 4-hour margin (the 4-hour margin from the `--rule 4h` rebuild, as registered).

| Sample | Games | g1 ratings part (t) | g2 news part (t) |
|---|---|---|---|
| 2024-25 | 1,320 | -0.022 (-0.17) | -0.097 (-0.35) |
| 2025-26 | 1,321 | +0.110 (+0.89) | +0.143 (+0.51) |
| History pooled | 2,641 | +0.048 (+0.55) | +0.029 (+0.15) |
| This season, lineup lock | 248 | -0.609 (-1.92) | +0.338 (+0.29) |

A coefficient of 1 would mean the line ignores that part of the model; 0 means the line already holds it. Both are 0 within a standard error in history, and the pooled
news part is 0.03. The GO bar (g2 t >= 2.5, positive in each season) is missed by a wide margin. This season's ratings part is negative (t -1.92) on 248 games: a direction
check only, and it points the same way as the overall result in the Game Picks record (the model's gap from the line, if anything, is noise against the result).

## Anchored projections (fit on the other season, scored on this one)

| Test season | Projection | MSE | MAE | MSE minus the line's (paired t) |
|---|---|---|---|---|
| 2024-25 | the line | 188.57 | 10.636 | |
| | line + w (model - line), w = 0.116 | 188.74 | 10.634 | +0.18 (+0.66) |
| | line + k (news part), k = 0.058 | 188.59 | 10.635 | +0.03 (+0.42) |
| | raw model | 198.24 | 10.907 | +9.67 (+4.13) |
| 2025-26 | the line | 197.97 | 11.012 | |
| | line + w (model - line), w = -0.024 | 198.03 | 11.011 | +0.06 (+1.11) |
| | line + k (news part), k = -0.078 | 198.00 | 11.013 | +0.03 (+0.33) |
| | raw model | 205.65 | 11.294 | +7.68 (+3.31) |

The raw model is worse than the line by 4.1 and 3.3 standard errors. Anchoring removes that loss and then adds nothing: the fitted weight on the model is 0.12 in one fold and
-0.02 in the other, and the anchored MSE is never below the line's. The projection that is best supported is the line.

## Picks against the line (win-loss, break-even at -110 is 52.4%)

| Part and cut | 2024-25 | 2025-26 | This season |
|---|---|---|---|
| News 1+ | 170-167 (50.4%) | 159-160 (49.8%) | 19-23 (45.2%) |
| News 2+ | 78-75 (51.0%) | 77-71 (52.0%) | 5-6 |
| News 3+ | 43-36 (54.4%) | 38-35 (52.1%) | 2-0 |
| Ratings 1+ | 508-479 (51.5%) | 488-504 (49.2%) | 86-103 (45.5%) |
| Ratings 2+ | 360-356 (50.3%) | 340-361 (48.5%) | 54-71 (43.2%) |
| Ratings 3+ | 240-229 (51.2%) | 221-230 (49.0%) | 31-37 (45.6%) |

The registered cut (1+) is under 52.4% in every cell. The 3+ news cell in 2024-25 (54.4%) is 79 games, one cell of 18, and 52.1% the next season: not read.

## What this settles

- The late injury news the model processes is already in the closing line (news part 0.03 +/- 0.19). The model is not faster than the market on scratches.
- The model's ratings view adds nothing either (0.05 +/- 0.09). Rounds 2 to 5 reached the same place by changing the ratings; this reaches it without changing them.
- An anchored projection is therefore the line plus noise. There is no registered rule under which the model's number should be shown as a pick or a projection that differs from the line.
- No change to the record, the page or any pick. A pick shown against the line needs a source of information the line does not hold; nothing the model has scored here is one.

## Limits

- History's 1pm and 30-minute reports are the official reports as of those times; the close has no timestamp. News that landed after the close cannot be scored.
- This season's rows use the Game Simulation's one-decimal margin (about 0.1 to 0.4 points of noise), and only 42 games had a news part of 1 point or more.
- Not tested: a model whose inputs the line does not contain (for example player-tracking or lineup-combination data the market prices slowly). That would need its own registration.
