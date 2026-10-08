# Pick'em entries built from independent picks: rules written before the run

Written 2026-10-08, before the script (`scripts/build_pickem_entries.py`) was run. Follows the different-teams finding
(docs/pickem-different-teams.md): picks on different teams, or in different games, are independent, so an entry's chance is the
product of its picks' chances and the only lever is the picks themselves and the entry size.

## What is being asked
An entry can mix players from different games. Given independence, (1) which entry size has the lowest per-pick bar, (2) how good
would the picks have to be, and (3) did a rule for choosing the picks (by the model, or by where the model and the market disagree)
beat that bar on games it was not tuned on?

## Payout assumption (stated, editable)
Power entries pay 2 picks 3x, 3 picks 5x, 4 picks 10x, 5 picks 20x, 6 picks 37.5x (PrizePicks-style; apps change these, so the
page lets you set your own). A pick must hit; a tie voids the pick and the entry is re-priced at one fewer pick (the standard rule).
Break-even per pick = payout^(-1/k): 57.7%, 58.5%, 56.2%, 54.9%, 54.5% for k = 2 to 6.

## Data
`raw/tables/props_espn.csv`, kind = main, played games, the same filters as the model backtest (two-way price, 2-15% hold, both
sides between 12% and 88%, no ties). Stats: points, rebounds, assists, 3-pointers, and the four combos. The line stands in for a
pick'em line (apps sit within about half a point of the books). Pre-registered limit: no historical pick'em lines exist, so this
tests what the picks would have done at the book's line, not at an app's.
- Fit: 2024-25, open price and the model's raw probability. Test: 2025-26, pre-tip close and the model's calibrated probability
  (calibration fit on 2024-25), injury report 30 minutes before tip. Same walk-forward model as build_prop_model.py.

## Entries
Each day, build entries from that day's legs, **one pick per player, one pick per game within an entry**, greedily by rank:
up to 3 entries per size per day. Three ways to rank a pick (side = the side the ranking prefers):
- S1: the model's chance for the side (calibrated on the test season).
- S2: the model's chance minus the market's no-vig chance for that side (where they disagree most).
- S3 (baseline): the market's no-vig chance for the side (the favourite side of every line).
Sizes k = 2, 3, 4, 5, 6.

## Rule, frozen now
- **Selection on the fit season:** the one (strategy, size) cell with the highest ROI per entry, among cells with at least 100
  entries. S3 is a baseline: it can be selected only to show the model adds nothing, and then the verdict is NO-GO.
- **Test:** that one cell on 2025-26. The day is the unit (an entry's days are averaged first, z across days).
  **GO** if ROI per entry > 0 at z >= 2.4, at least 100 entries over at least 40 days, and ROI > 0 in both halves of the season.
  **WATCH** at z >= 1.65 with the same sample. Otherwise NO-GO.
- Every other cell is reported in both seasons and is descriptive only. The per-pick hit rate of each strategy is reported against
  the break-even for its size, which is the number that says how far from profitable it is.
- Also reported, not decided on: how many points of line shading (the app's line off the sharp line, in stat units, by stat) a pick
  needs to reach each size's break-even, from the fitted variance at a typical player's mean.

---

## Run 1 result and amendment (2026-10-08, written before run 2)

**Run 1 (rules above, frozen) was NO-GO.** The fit season selected S3 at size 6 (the market-favourite baseline), which the rule
says can only mean NO-GO. Run 1 also exposed a flaw in the rule as written: it allowed legs at any price between 12% and 88%, so
the "favourite side" strategy picked legs priced at 80% and above. A pick'em app does not offer those: it posts a line near the
median, so every pick is close to a coin flip before any edge. Those legs hit far above anything achievable (73-79% on 2024-25 opening
prices, which are also the least reliable rows) and cannot be played. The run-1 table is kept as the record and is not used.

**Amendment, run 2:** legs are restricted to lines a pick'em app could post: the book's no-vig chance of the over between **45% and 55%**.
Everything else is unchanged: the fit and test seasons, the three rankings, sizes 2 to 6, up to 3 entries per size per day,
selection on 2024-25, the verdict thresholds, and S3 can still only produce NO-GO. S3 is now "the side the market likes a little
more" and works as a baseline. One run, no further changes.
