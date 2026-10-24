# Game-model challenger: results

Generated 2026-10-24T13:16Z by `nba/scripts/test_ratings_challenger.py`. Rules, committed before this ran: `nba/docs/game-model-challenger.md`. Four variants, scored once.

Challenger parameters (tune seasons only): K 0.04, CARRY 0.45, KP 0.15; tune margin MAE 10.707 raw, 10.699 after the shrink (margin = 0.622 + 0.964 x raw). On a grid endpoint: KP.
Shipped parameters (not retuned): {'K': 0.04, 'CARRY': 0.5, 'C': 0.5, 'REP': 0.4, 'B2B': 2.0, 'ALPHA': 0.06}.

## 2025: 1,320 games with a closing spread

Market closing margin MAE: 10.636.

| Variant | Margin MAE | t vs shipped | Winner | Info test g (t) vs the close | ATS, any edge | ATS, edge 3+ |
|---|---|---|---|---|---|---|
| S: Shipped Vault line (injury report at tip) | 10.907 |  | 67.8% | 0.044 (t 0.32) | 52.0% on 1320 | 53.3% on 409 |
| A: Challenger, shrunk | 11.133 | -3.61 | 66.7% | 0.060 (t 0.51) | 49.7% on 1320 | 49.2% on 561 |
| B: Challenger + shipped injury adjustment | 10.953 | -1.17 | 67.3% | 0.103 (t 0.77) | 51.5% on 1320 | 51.0% on 469 |
| C: Mean of shipped and B | 10.913 | -0.31 | 68.3% | 0.079 (t 0.57) | 51.4% on 1320 | 51.7% on 418 |

## 2026: 1,321 games with a closing spread

Market closing margin MAE: 11.012.

| Variant | Margin MAE | t vs shipped | Winner | Info test g (t) vs the close | ATS, any edge | ATS, edge 3+ |
|---|---|---|---|---|---|---|
| S: Shipped Vault line (injury report at tip) | 11.294 |  | 68.2% | 0.186 (t 1.37) | 49.7% on 1321 | 49.6% on 411 |
| A: Challenger, shrunk | 11.428 | -1.91 | 68.7% | 0.070 (t 0.56) | 49.4% on 1321 | 50.2% on 560 |
| B: Challenger + shipped injury adjustment | 11.315 | -0.5 | 68.0% | 0.206 (t 1.62) | 49.6% on 1321 | 54.2% on 480 |
| C: Mean of shipped and B | 11.283 | 0.53 | 67.9% | 0.208 (t 1.55) | 49.4% on 1321 | 50.8% on 441 |

## Pooled: 2,641 games with a closing spread

Market closing margin MAE: 10.824.

| Variant | Margin MAE | t vs shipped | Winner | Info test g (t) vs the close | ATS, any edge | ATS, edge 3+ |
|---|---|---|---|---|---|---|
| S: Shipped Vault line (injury report at tip) | 11.101 |  | 68.0% | 0.118 (t 1.23) | 50.8% on 2641 | 51.5% on 820 |
| A: Challenger, shrunk | 11.28 | -3.83 | 67.7% | 0.066 (t 0.77) | 49.5% on 2641 | 49.7% on 1121 |
| B: Challenger + shipped injury adjustment | 11.134 | -1.17 | 67.7% | 0.159 (t 1.73) | 50.5% on 2641 | 52.6% on 949 |
| C: Mean of shipped and B | 11.098 | 0.18 | 68.1% | 0.148 (t 1.53) | 50.4% on 2641 | 51.2% on 859 |

## Verdicts, by the registered rules

| Variant | Matches the shipped model | Better than it | Pooled t | Season t | Info t (shipped) |
|---|---|---|---|---|---|
| A | no | no | -3.83 | [-3.61, -1.91] | 0.77 (1.23) |
| B | yes | no | -1.17 | [-1.17, -0.5] | 1.73 (1.23) |
| C | yes | no | 0.18 | [-0.31, 0.53] | 1.53 (1.23) |

Better needs: pooled t >= 2, positive in each season, and the information test t within 1 of the shipped model. A variant that is not Better changes nothing live.

## Reading it

- **Sam-style alone (A) is worse than the shipped model**: margin MAE 11.280 against 11.101, t -3.83 pooled and negative in both seasons. Its rating moves are the same family of idea (a moving average of how a team did against expectation), without who is playing.
- **Give it the shipped model's injury adjustment (B) and the gap closes** (t -1.17: statistically a tie, still not better). The difference between the two models is mostly the injury report.
- **Averaging them (C) ties the shipped model** (t +0.18). Its information test against the close is t 1.53 against 1.23, which is not significant for either.
- **No variant is Better, so nothing live changes.** `game_model.json`, the Slate and the Game Picks record stay as they are.
- **The bar neither clears is the market**: closing-line margin MAE 10.824 against 11.101 for the shipped model. Winner accuracy over the same 2,641 games: the market's favourite 68.6%, the shipped model 68.0%, the challenger 67.7%. None of the variants adds information beyond the closing line at t >= 2 (best: B at 1.73).

## Exploratory, not part of the registered verdict

Looked at after the registered run, so it is a hypothesis generator and carries no verdict. The question: does a fast-learning model help in the first 28 days of a season, where the shipped model is weakest?
Margin MAE, shipped (S), challenger (A), challenger with the injury adjustment (B), market:

| | Games | S | A | B | Market | A against S |
|---|---|---|---|---|---|---|
| 2025, first 28 days | 210 | 9.63 | 9.85 | 9.68 | 9.44 | t -1.59 |
| 2025, rest of season | 1,110 | 11.15 | 11.38 | 11.19 | 10.86 | t -3.26 |
| 2026, first 28 days | 206 | 10.67 | 10.75 | 10.70 | 10.30 | t -0.52 |
| 2026, rest of season | 1,115 | 11.41 | 11.55 | 11.43 | 11.14 | t -1.84 |

The challenger is not better early either, so there is no regime to chase. A round 2 would have to start from a different idea, be registered first, and clear t >= 2.5.

## Disclosure

The first run crashed with no records because the possession estimate was halved (the minutes total covers both teams, 480, not 240). That unit bug was fixed, and the registered text corrected to say 480, before any result was produced.
The registered rules, variants, grids and verdict criteria were not changed.
