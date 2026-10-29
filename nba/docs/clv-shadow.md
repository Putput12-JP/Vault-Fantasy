# Closing-line shadow: does the market move toward the minutes model?

Written 2026-10-29, before any forward row exists. Nothing here prices a prop or places a bet.

## Why this test

Win/loss cannot grade the minutes model against the price. On 2,110 settled free props the model's log loss is 0.6984 against 0.6827 for
the price, a blend with the price fits at k near 0 to 0.25 and gains nothing walk-forward, a logistic stack on the price and the model
gap is worse than the raw price, and a 3-point weight fit on 2025-26 and frozen scored -0.0004 (se 0.0025) on 2026-27. An edge of
about half a point is far below the roughly 1.1-point standard error of 2,000 outcomes.

The price moving toward the model's side is a cleaner measurement. In the discovery window the price moved toward the model side at
the first look by +0.38 points (n 1,437 props, 50 games, game-clustered z 5.81), rising with the gap and present in all four stats.

## Rule (frozen)

For every prop in the psim record seen at two different times on the SAME line with a price at both looks:

- first look: the earliest psim row (p_exact = model, p_price = vig-free over chance)
- model side: over if p_exact(first) > p_price(first), else under
- cohort: gap |p_exact(first) - p_price(first)| >= 0.03
- CLV: how far p_price moved toward the model side by the last pre-tip row, in probability points

Free props only for the verdict; held props are reported apart. Standard error clustered by game.

## Samples

- DISCOVERY: first seen before 2026-10-30 (the window the rule was found in; looked at at gaps 0, 0.03 and 0.06, and by stat). Descriptive only.
- FORWARD: first seen on or after 2026-10-30. The only sample that counts.

## Verdict (read once, on or after the bar is met)

- WORKS: forward free cohort has n >= 500 props, >= 30 games, CLV > 0 and z >= 2.
- NOT SHOWN: the bar on size is met and CLV or z fails. Retire the line.
- COLLECTING until then. Do not quote a forward number under 500 props.

## What a pass does and does not mean

- It says the model sees something the early price lacks. It does not say a bet clears the fee: +0.4 points of probability is about 0.8% of value
  per bet before the vig. Whether the first price was bettable and what it nets after the Kalshi fee are separate questions.
- In discovery the first price came from sportsbooks on 1,216 of the 1,437 props and from pick'em apps on 221. The record splits by source.
- Not a bet signal, and it adds nothing to an agree total.

## Where it lives

`nba/scripts/clv_shadow.py` rebuilds `nba/data/clv_shadow.json` daily from the nba-data branch (`.github/workflows/nba-clv-shadow.yml`).
Stateless: re-running recomputes the whole file. No page reads it yet.
