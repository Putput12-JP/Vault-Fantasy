# Live against backtest: why the live leans sit under, 2026-10-22 to 2026-10-25

Written 2026-10-26. Descriptive, from four nights (24 games, 187 players, 2,127 first-look leans, 298 prop-bearing single-stat player-games). Every figure is a post-hoc read of that sample; nothing here is a test or a model change.
Data: the lean log and results on `nba-data`, the 2025-26 backtest lines (`data/lean_rows_nba.json`, 5,250 lines, 76% of them playoff lines).

## The question

Live, 31% of leans are overs (backtest 54%) and 60% of ledger bets are unders. Is the live pipeline different from the backtest's, or is the sample different?

## What the code says

The projection functions are the same: live `pricing.py` runs the backtest's walk (`build_prop_model_v2`), and every change this month was checked for identical priced output (`check_pricing_regression`). `check_minutes_parity.py` (backtest equals live) needs the price archive and was **not re-run here**. So the difference is in the inputs and the population, not the arithmetic.

## What the numbers say

**1. The miss is minutes, not rate.** First-look single-stat leans (points, rebounds, assists, 3-pointers):

| Stat | Actual / projected stat | Actual / projected minutes | Actual / projected per-minute rate |
|---|---|---|---|
| Points (283) | 1.079 | 1.112 | 0.970 |
| Rebounds (288) | 1.138 | 1.114 | 1.022 |
| Assists (233) | 1.092 | 1.107 | 0.987 |
| 3-pointers (278) | 1.106 | 1.118 | 0.989 |

The per-minute rates are accurate (0.97 to 1.02). The stat miss comes from the minutes.

**2. Prop-bearing players are under-projected, other players are not.** Over all 634 players who played in these games, projected minus actual is -0.27 minutes. Over the 298 prop-bearing player-games, actual minus projected is **+2.70 minutes at first look (11.2%) and +2.06 at the last look before tip (8.3%)**; late news fixes about a quarter of it.
By projected-minutes band at first look: 15 to 22 minutes +4.05 (n 97), 22 to 28 +2.17 (98), 28 to 34 +2.04 (56), 34 and over -2.80 (25). That is the pattern of minutes leaking to bench and non-playing players (`rotation-minutes-round3-results.md`: the old model was 2.5 minutes short for the top 8 in padded pools of 15 or more), plus the usual pull of the heaviest minutes back toward the middle.
For comparison, the backtest's top 8 (2025-26) were only -0.15 minutes off for the old model. The live gap is **an order of magnitude larger** in this sample.

**3. First look against the closing line does not explain the skew.** Over 2,126 props with both clocks: lines moved up 2.5% on average (24.8% of them up, 20.4% down) and projections moved up 2.7% with them; the over-lean share is 31.0% at first look and 32.0% at the close.

**4. The population differs from the backtest's.** 84% of live leans are on lines with no sportsbook price (pick'em apps only): median line 9.5 against 6.5, median projected minutes 23.9 against 28.4, share of leans with the projection above the line 37.9%, median gap -7.3%. Sportsbook-priced live leans: 45.5% above the line, median gap -2.8% (n 345, about ten games). The backtest: 53.9% above the line, median gap +1.5% (n 5,250). Even like with like, live sits lower, and the minutes miss is the likely reason: a projection that is low by 2 to 3 minutes is a projection that lands under the line.

## Conclusion

The under skew is mostly **a minutes under-projection for rotation players** layered on a population that is dominated by pick'em-only lines. It is not a side bias in the model. The rotation-minutes shadow (`rotation-minutes-shadow.md`) is aimed at exactly this, and its first nights will say whether it closes the gap. Until then the model's strongest unders are the least trustworthy leans (the strongest, gap 25% or more, hit 45.4% live against 66.2% in the backtest).

## What was not done

A replay of the four nights through the backtest's walk, which needs the 2026-27 box-score files (the daily job fetches them in CI; they are not in this checkout). It would separate "different inputs" from "different arithmetic" exactly. It is the next step if the rotation shadow does not close the minutes gap.

## Correction made alongside this write-up

The rotation shadow's launch check (due 2026-10-29) was registered with "mean C3 minus v2 within 1.5 minutes". The numbers above show the live v2 minutes are 2 to 3 minutes low for rotation players, so a correct model may differ from v2 by more than that, and the check would have switched a better model off. Changed **before any shadow row was settled**: the check now compares each model with the actual minutes (see `rotation-minutes-shadow.md`, "As built").
