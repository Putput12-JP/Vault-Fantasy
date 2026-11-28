# Game Picks A tier: results

Generated 2026-11-23 by `nba/scripts/test_game_model_a_tier.py`. Rules: [game-model-a-tier.md](game-model-a-tier.md) (committed before this ran, `67da5e79`; the pass bar was tightened in `5a72a0ae`, also before any score).

**Verdict: NO-GO. No subgroup of spread A passes, in either direction.** Nothing about the A tier, the record or any pick changes.

## Spread A (edge 5+ points against the line, -110, break-even 52.4%)

| Rule | 2024-25 (discovery) | 2025-26 (confirm) | Pooled z vs 52.4% | This season | Pass |
|---|---|---|---|---|---|
| S0 all A, followed | 61-74 (45.2%) | 71-73 (49.3%) | -1.70 | 11-11 | no |
| S1 all A, faded | 74-61 (54.8%) | 73-71 (50.7%) | +0.10 | 11-11 | no |
| S2 takes the underdog | 54-64 (45.8%) | 66-69 (48.9%) | -1.58 | 9-10 | no |
| S3 takes the favourite | 7-10 (41.2%) | 5-4 (55.6%) | -0.64 | 2-1 | no |
| S4 news part 1+ | 18-15 (54.5%) | 19-17 (52.8%) | +0.21 | 3-3 | no |
| S5 news part under 1 | 43-59 (42.2%) | 52-56 (48.1%) | -2.07 | 8-8 | no |
| S6 after day 28 | 51-67 (43.2%) | 53-59 (47.3%) | -2.18 | 0-1 | no |
| S7 first 28 days | 10-7 (58.8%) | 18-14 (56.2%) | +0.67 | 11-10 | no (n under 60) |
| S8 edge 7+ | 13-21 (38.2%) | 20-23 (46.5%) | -1.67 | 2-2 | no |
| S9 home picks | 34-41 (45.3%) | 34-24 (58.6%) | -0.29 | 7-6 | no |
| S10 away picks | 27-33 (45.0%) | 37-49 (43.0%) | -2.07 | 4-5 | no |

- **Followed, spread A is 132-147 (47.3%) over 2024-26,** about -9.7% ROI at -110, as `game-model.md` already said. **Faded it is 147-132 (52.7%), +0.6% ROI with a standard error near 6%**: break-even, not an edge.
- **Where A does worst is where it is largest:** edge 7+ is 33-44 (42.9%).
- **Where A looks best is the first 28 days of a season** (S7: 28-21 pooled, 57.1%; this season 11-10). The page flags those games "Early season" as less trusted, the opposite of what this
  shows. It failed the registered bar (n 17 and 32, under 60 each), was one of eleven cells, and it cannot be tested forward until the 2027-28 season starts. It is a lead, nothing more.

## Winner A (model chance 70%+), this season only, descriptive

| | Games | Record | Units at the stored moneyline | The same teams against the spread |
|---|---|---|---|---|
| All winner A | 80 | 66-14 | +0.63 (80 priced) | covered 33 of 80 (41%) |
| Model chance 3+ points over the spread-implied chance | 18 | 11-7 | -2.26 | covered 8 of 18 |

Winner A is a heavy-favourite list. Its +0.63 units on 80 picks is 0.8% ROI, inside any noise band (n is under the 100-pick reading rule). The price-aware cut, the natural way to lift it,
is worse (-2.26 on 18). Taking the same teams on the spread instead would have lost: they covered 41%, because a team the model likes by a lot is usually a team the line already laid a lot of points on.

## What this settles

- No rule on information the pick already has (side, size of the edge, home or away, news or ratings, early or late) separates winning A picks from losing ones in 2,643 games, in either direction.
- The A tier's problem is not a filter that is missing. Spread A is the tier where the model and the line disagree most, and the line has been right.
- Winner A is not losing, but its result is price, not skill: it wins 82.5% at prices that need 81.6% on average (the model's own average chance for these teams was 77.8%).

## Limits

- n per cell is 17 to 138; a win rate has a standard error of 4 to 12 points. A real 2-point effect cannot be found at these sizes, and this does not claim there is none.
- The closing spread has no timestamp; edge is measured against it, as `game-model.md` does. This season's rows use the lineup-lock line and the simulation's one-decimal margin.
- Winner A history has no stored moneyline; no price is inferred, so it is forward only.
