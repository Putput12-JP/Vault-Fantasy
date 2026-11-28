# Game model: on/off player value, results

Generated 2026-11-19T18:08Z by `nba/scripts/test_onoff.py`. Rules, committed before this ran: [onoff-prereg.md](onoff-prereg.md). Box-score on/off, test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Chosen on the tune seasons: O = O|C=0.5|K0=1000; B = B|LAM=0.5|K0=1000. Tune margin MAE (all games, who actually sat): S: 10.5252, O|C=0.25|K0=200: 10.581, O|C=0.25|K0=500: 10.5835, O|C=0.25|K0=1000: 10.5898, O|C=0.5|K0=200: 10.5951, O|C=0.5|K0=500: 10.5808, O|C=0.5|K0=1000: 10.5741, O|C=0.75|K0=200: 10.6808, O|C=0.75|K0=500: 10.6285, O|C=0.75|K0=1000: 10.5931, O|C=1.0|K0=200: 10.8294, O|C=1.0|K0=500: 10.7247, O|C=1.0|K0=1000: 10.6465, O|C=1.5|K0=200: 11.3362, O|C=1.5|K0=500: 11.0621, O|C=1.5|K0=1000: 10.8462, B|LAM=0.5|K0=200: 10.5609, B|LAM=0.5|K0=500: 10.5493, B|LAM=0.5|K0=1000: 10.5399, B|LAM=1|K0=200: 10.6702, B|LAM=1|K0=500: 10.6296, B|LAM=1|K0=1000: 10.5927, B|LAM=2|K0=200: 11.0916, B|LAM=2|K0=500: 10.9289, B|LAM=2|K0=1000: 10.796, B|LAM=4|K0=200: 12.5731, B|LAM=4|K0=500: 12.0501, B|LAM=4|K0=1000: 11.5709.
Games where the shipped injury adjustment is active at tip: 1967 of the test games.

## O (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.952 | 0.04 | 0.04 | 1.0 |
| 2026 | 1322 | 11.288 | 11.322 | 0.034 | 0.043 | 0.78 |
| pooled | 2643 | 11.1 | 11.137 | 0.037 | 0.03 | 1.22 |
| exploratory: injury adjustment active | 1967 | 10.987 | 11.044 | 0.057 | 0.039 | 1.47 |

Against the close: {'variant': {'model': 11.138, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.065, 'g_model_gap': 0.092, 'g_se': 0.094, 't': 0.98}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## B (margin MAE, points)

| Window | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|
| 2025 | 1321 | 10.912 | 10.92 | 0.008 | 0.019 | 0.43 |
| 2026 | 1322 | 11.288 | 11.309 | 0.02 | 0.02 | 1.01 |
| pooled | 2643 | 11.1 | 11.115 | 0.014 | 0.014 | 1.0 |
| exploratory: injury adjustment active | 1967 | 10.987 | 11.005 | 0.018 | 0.018 | 1.01 |

Against the close: {'variant': {'model': 11.115, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.063, 'g_model_gap': 0.104, 'g_se': 0.092, 't': 1.14}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdicts, by the registered rules

| Variant | Rule 1 (pooled whole-season t) | Rule 2 (same sign both seasons) | Rule 3 (info t vs shipped) | Verdict |
|---|---|---|---|---|
| O, on/off replaces game score | +1.22 (worse) | both worse (+0.040, +0.034) | 0.98 vs 1.23 | **NO-GO** |
| B, on/off added to game score (LAM 0.5) | +1.00 (worse) | both worse (+0.008, +0.020) | 1.14 vs 1.23 | **NO-GO** |

## Reading it

- **On/off was worse than the shipped value on the tune seasons too.** Shipped 10.525; the best O cell was 10.574 and the best B cell 10.540. Every one of the 27 cells lost to the shipped model, and the more shrinkage (K0 1000, the grid edge) the closer it got to shipped. The tuner was effectively asking for less on/off, so the test-season result is not a surprise.
- **Direction is consistent, size is small.** B costs 0.014 points of margin MAE (SE 0.014); O costs 0.037 (SE 0.030). Neither is significant, and the information test against the close does not improve, so there is no hidden gain.
- **Why box-score on/off is a weak signal here.** A player's on/off swing mixes in who he plays with and against, and 82 games is a small sample for it (the best shrinkage was the largest on the grid). Stint-based RAPM corrects for teammates and opponents but needs stints, which are not on disk.
- **This does not test lineup data from NBA.com.** The box-score version uses the same games and the same information (plus-minus and minutes). Real lineup on/off or RAPM would add the teammate adjustment and was not tested.
- **Nothing ships.** `game_model.json`, the Slate and the Game Picks record are unchanged.

## If you want to pursue it

Build stints from the play-by-play (the existing `build_pbp_stints.py` plan in `docs/reverse-engineering-targets.md`), fit RAPM walk-forward by season, and register it as its own test. The bar is higher than here: it has to beat a game-score value that is already tuned.
