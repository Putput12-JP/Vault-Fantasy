# Prop calibration tests: results

Rules: [prop-calibration-tests.md](prop-calibration-tests.md), committed before the runner existed (`8064371ff`, clarified in `e0d006335`, runner `144c64ec0`).
Runner: `nba/scripts/test_prop_calibration.py`. Numbers: `nba/data/prop_calibration_tests.json`. Run on 2026-10-25.
Nothing here changes what the page prices or bets.

## Test 1. Cap the model's tail: **REJECT** (look 27 on the 2025-26 lines)

Candidate: the gap term in the lean-search stack clipped at c = 0.2889 (the 90th percentile of |gap| over the first 40% of rows, frozen before scoring). 12.0% of scored lines sit beyond c.
Scored on the harness's three expanding folds: 3,150 lines from only 56 games (the file is mostly playoff lines, and the early rows are fit-only).

| Fold | Incumbent log-loss | Capped log-loss | Gain |
|---|---|---|---|
| 1 (1,050 lines) | 0.68376 | 0.68317 | +0.00059 |
| 2 (1,050 lines) | 0.68744 | 0.68703 | +0.00041 |
| 3 (1,050 lines) | 0.68169 | 0.68141 | +0.00029 |
| **Pooled** | | | **+0.00043** (95% interval -0.00046 to +0.00137) |

| Condition | Needed | Got | Pass |
|---|---|---|---|
| Better in all three folds | yes | yes | yes |
| Interval lower end above 0 | > 0 | -0.00046 | **no** |
| Gain over the harness bar (27 looks) | > 0.00100 | 0.00043 | **no** |
| Game-clustered t | >= 2.5 | 0.92 | **no** |

**Read:** the cap helps a little in every fold and by an amount indistinguishable from nothing (t 0.92, one third of the bar). The one weight the stack already learns is not visibly over-trusting the big gaps on these lines. Hit rate did not move in a consistent direction (fold 2 fell from 54.7% to 53.4%, folds 1 and 3 rose).

**Flagged for close monitoring (improves, sample size):** capped gap better in 3 of 3 folds, +0.0004 log-loss, 3,150 lines, 56 games. This is a direction, not a result, and the pre-registered bar says it does not move anything.

**Companion, reliability of the incumbent on the scored lines** (predicted chance for the side it prefers, against how often that side won). Bands under 100 lines show the count only, per the reading rule.

| Predicted | Lines | Predicted | Won |
|---|---|---|---|
| 50 to 55% | 2,120 | 52.3% | 53.7% |
| 55 to 60% | 697 | 57.1% | 57.7% |
| 60 to 65% | 260 | 61.9% | 65.8% |
| 65% and over | 73 (66 in 65 to 70, 7 above) | not quoted | not quoted |

Inside 50 to 65% the stack is calibrated, if anything slightly modest. The tail the Edge Engine comparison pointed at is **the 65% and over band, and it holds only 73 of 3,150 lines (2.3%)**, too few to say whether it is overconfident. The forward lean log's "verified" label (within 4 points over 100 or more leans) is where that gets answered.

**Limits.** The harness incumbent is a research stand-in, not the shipped `Pricer.cal` then `blend`. The file has been used 26 times already. 56 scored games is a small test of a tail effect. A REJECT here does not say tails are fine; it says this cap, on this file, shows nothing.

## Test 2. Last-look gate: **not read**

Forward only. Qualifying settled bets since 2026-10-26: **0** (kept 0, dropped 0, 0 games, 0 nights). Needs 20 nights, 100 games and 300 dropped bets; earliest read about 2026-11-15.

## Test 3. Lower early-season model weight: **not read**

Forward only, one read on or after 2026-11-18. Qualifying first-look leans from 2026-10-26: **0** (0 games, 0 nights). Needs 100 games and 3,000 rows.

The runner's `counts` command prints those counts and nothing else; `test2` and `test3` refuse to score until their sample rules are met, and a verdict, once written, is not overwritten.
