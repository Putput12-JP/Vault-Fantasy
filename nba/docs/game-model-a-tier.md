# Game Picks A tier: can a rule lift its ROI? Pre-registered

Written 2026-11-23, before any A-tier subgroup below was scored. Runner: `nba/scripts/test_game_model_a_tier.py`.
Results land in `nba/docs/game-model-a-tier-results.md` only after this file is committed.

## Why

The A tier is the record the page leads with. What is already known: spread A (edge 5+ points) is 11-11 (-0.92u, n = 22) on the lineup-lock record and 47.3% (279 bets) against the close
over 2024-26 in `game-model.md`; winner A (70%+) is 66-14 (+0.63u, n = 80), where the market already gave the same teams about 79%. The previous round (`game-model-anchored.md`) found
neither the model's ratings nor its late-news view carries information the close lacks. This round asks the narrower question the user asked: **is there a subgroup of A picks
that clears break-even, found on one sample and confirmed on another?** It is not a search for a story that fits what already happened.

## Samples

- **Discovery: 2024-25** (1,321 games). **Confirm: 2025-26** (1,322 games). Walk-forward backtest, parameters frozen (`data/game_model.json`), model at the 30-minute report, the closing spread.
- **Forward: this season**, the 248 games of `data/game_picks.json` (lineup lock). Direction check only.

## The tier and the hypotheses (all fixed now; every one is reported, pass or fail)

**Spread A** = |model margin - line| >= 5 (edge in points), bet at the line at -110 (break-even 52.4%). Subgroups, each tested on the A picks only:

| | Subgroup |
|---|---|
| S0 | all spread A, followed |
| S1 | all spread A, FADED (the other side) |
| S2 | A where the pick takes the underdog |
| S3 | A where the pick takes the favourite |
| S4 | A where the late news part (|model at report - model at 1pm|) is 1 point or more |
| S5 | A where it is under 1 point (a ratings gap) |
| S6 | A after the first 28 days of the season |
| S7 | A in the first 28 days |
| S8 | A with an edge of 7 or more |
| S9 | A on home picks; S10 on away picks |

A rule PASSES when the win rate is >= 52.4% with n >= 60 in discovery AND in confirm, AND the two seasons pooled clear break-even by a multiple-comparison bar: a one-sided z of
2.6 or more against 52.4% (p about 0.005, which is 0.05 divided by the eleven rules). Followed and faded are separate rules (S1 is the opposite side of S0, S2 and S3 are tested followed
only). *Amended before any score:* the first draft said "52.4% in both folds", which a no-effect rule passes about 12% of the time at these n (a standard error of about 6 points per
fold), so eleven rules would put one false pass in play. The pooled bar makes a false pass about 5% across all eleven. Forward (n small) must point the same way (>= 50%) for a pass to be WATCH.

**Winner A** = the model's chance for its team >= 70%, straight up at the stored moneyline. Forward only (the stored moneyline exists only this season; no price is inferred for history):
the record and units on the 80 games, the same teams on the spread at -110 instead, and the teams whose model chance exceeds the market's no-vig chance by 3 points or more (the price-aware
cut). **Descriptive, no verdict**: n is far under the 100-pick reading rule.

## Verdict (fixed now)

- **GO** only for a spread rule that PASSES and is >= 50% forward. A GO becomes a shadow row beside the record, labelled untested rule, flagged for close monitoring with its sample size.
  It never feeds Top Reads or an agree total, and no existing pick is re-priced.
- **NO-GO** otherwise: nothing changes, and the A tier stays what the record says it is.

## Limits, stated before the numbers

- A spread of 5 or more points between the model and the line is a rare event: about 140 a season. A subgroup of 60 is about 43% of a season's A picks, so a win rate has a standard error of about 6 points
  per fold. Only a large, consistent effect can pass the pooled bar; a real effect of 2 points cannot be found at these n, and the result will say so rather than claim it.
- "Underdog / favourite", "home / away" and "early" are properties known at the bet; the news part uses the 1pm and 30-minute reports as of those times.
- The closing spread has no timestamp; the pick's edge is measured against it, as `game-model.md` does.
