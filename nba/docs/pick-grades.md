# Ranking and grading the game picks: what the record would look like

Written 2026-10-24. Descriptive, not a test and not a model change. Runner: `nba/scripts/analyze_pick_grades.py` (writes `nba/data/pick_grades.json`).
Question: if the picks were ranked by confidence, or given letter grades, what would "top 3" or "A" have done?

## Definitions (fixed before the numbers were read)

- **Spread confidence** = the edge in points, |model margin + home spread|. **A** = 5 or more, **B** = 3 to 5, **C** = under 3 (the buckets Track Record already shows; nothing tuned). **Top N** = the N biggest edges of each day.
- **Winner confidence** = the model's chance for the side it picks. **A** = 70% or more, **B** = 60 to 70%, **C** = under 60%. **Top N** = the N most confident picks of each day.
- **Market chance** for the same side = the closing spread through the same normal curve the model's win % uses (sd 13.19). It is what the market implied; a bet at a fair price breaks even when the side wins that often.
- Scored on the two test seasons (2024-25 and 2025-26, 2,641 games) with the shipped model's walk-forward records and the injury report at tip. Spread picks are scored against the **closing** spread, the conservative
  number (our live picks lock 4 hours before tip, far closer to the close than to the ESPN open, which has no timestamp), and against the **opening** spread as an optimistic bound. Break-even at -110 is 52.4%. No units: closing prices are not stored for every game and a price is never inferred.

## Spread picks: confidence does not rank them

| Ranking (2,641 games) | Against the close | Against the open (stale, untimestamped) |
|---|---|---|
| All picks | 50.8% (1,342-1,299) | 52.6% |
| **A**: edge 5+ | **47.3%** (132-147, n 279, CI 41.5 to 53.2%) | 60.5% (217-142, n 359) |
| B: edge 3 to 5 | 53.6% (290-251, n 541) | 53.3% |
| C: edge under 3 | 50.5% (920-901, n 1,821) | 50.7% |
| **Top 1 per day** | 49.1% (209-217, n 426) | 55.9% |
| **Top 3 per day** | **49.3%** (492-507, n 999, CI 46.2 to 52.4%) | 55.4% |

- Against the line you could actually bet, the biggest gaps do **worse**, not better: A is 47.3% and top 3 per day is 49.3%, both under break-even. Season by season it is the same story (A: 45.2% in 2024-25, 49.3% in 2025-26).
- Against the opening line A looks like 60.5%. That is the trap: the model uses the injury report, the open was posted before it, so the model "beats" a line that had not yet heard the news. It is not an edge, and it is why the picks are graded against a line stored at lock time.
- The one tier above break-even, B at 53.6%, has a range (49.4 to 57.8%) that includes 50%, and it was 57.3% in one season and 49.8% in the other. Treat it as noise.

## Winner picks: confidence is real, and the market already knows it

| Tier (2,641 games) | Won | Model said | Market said (closing spread) | Won minus market |
|---|---|---|---|---|
| All | 68.0% | 66.6% | 67.3% | +0.7 pts |
| **A**: 70% or more (n 941) | **80.5%** | 79.1% | 79.2% | +1.4 |
| B: 60 to 70% (n 795) | 67.5% | 64.9% | 66.1% | +1.5 |
| C: under 60% (n 905) | 55.4% | 55.0% | 56.0% | -0.6 |
| Top 1 per day (n 426) | 77.9% | 78.8% | 78.4% | -0.5 |
| **Top 3 per day** (n 999) | **76.1%** | 75.9% | 76.1% | 0.0 |
| Top 3 per day by value (model chance minus market chance) | 62.2% | 66.9% | 61.2% | +0.9 |
| The market's favourite, same games | 68.6% | | | |
| Model agrees with the market's favourite (n 2,340) | 70.7% | | | |
| Model disagrees with it (n 301) | 47.2% | | | |

- The model's confidence tiers are **well calibrated**: A says 79% and wins 80.5%, C says 55% and wins 55.4%. A real ranking.
- But every tier wins only about as often as the **market** already said it would (all within 1.5 points; one standard error is about 1.3). Confidence here mostly means "a heavy favourite", which the market prices at the same number. An A-grade winner pick at 80% pays about nothing at a fair price.
- Where the model **disagrees** with the market's favourite, it wins 47.2% (n 301): the market's side was right more often. Ranking by *value* (how far the model is above the market) is worse: the model says 66.9% and the picks win 62.2%, tracking the market's 61.2%, not the model's.

## What our 28 live games show (rebuilt, n far too small)

| Cut | Record | Units |
|---|---|---|
| Spread, A (edge 5+) | 4-2 (6 picks) | +1.65 |
| Spread, B / C | 2-4 / 6-10 | -2.18 / -4.64 |
| Spread, top 3 per day (days with 3+ games) | 5-4 (9 picks) | +0.56 |
| Winner, A (70%+) | 4-1 (5 picks) | +0.89 |
| Winner, top 3 per day | 6-3 (9 picks) | +0.13 |

**Flagged for close monitoring, with sample sizes** (CLAUDE.md): spread A 4-2 (n 6), spread top 3 per day 5-4 (n 9), winner A 4-1 (n 5), winner top 3 per day 6-3 (n 9). All are under the 100-pick reading rule, and the 2,641-game history above says the spread ones should not hold up (A has been under 50% against the close). They are listed because they look good, not because they are.

## What this means for the product

- **Do not label spread picks with letter grades.** An "A" on edge would be the model's worst-performing tier against the close, and 60% against the open if anyone showed that number.
- **A confidence ordering for winners is honest** (it is calibrated), as long as the page says what it is: how sure the model is, which tracks the favourite, not extra value over the market.
- The record can carry **rank cuts as measured rows** (top 1 and top 3 of each day, by edge for the spread and by chance for the winner), each with its sample size and the market's own number beside it, so the forward record answers this question instead of this table. Nothing is a bet signal.
