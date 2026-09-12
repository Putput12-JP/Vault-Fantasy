# Finding: the `rec` UNDER-lean is a market-disagreement / cold-start artifact, not a low projection bias

Investigation prompted by every grade-A best bet landing on a receptions UNDER
(Jefferson, Warren, Higgins, Loveland), each disagreeing with the market on the
same side. Question: is Vault's `rec` / `rec_yd` point projection systematically
biased low, producing an over-confident UNDER lean?

## Bottom line

There is a **real, `rec`-specific UNDER-lean vs the market** (about **-5.5pt of
P(over)** board-wide, up to **-20pt** on the flagged stars), but it is **not** a
low bias in the point projection. Out-of-sample the `rec` projection is
unbiased-to-slightly-high (mean signed error **+0.14 receptions**). The fix is
**not** to raise projections. The gap is a backward-looking model betting unders
into book lines that price a current-season role the 2025-only tape cannot see,
amplified by a shrink term and a correct-but-punishing count distribution.

Caveat on method: the Kalshi sharp anchor referenced in the original brief did
**not exist in the worktree the audit ran in** (no `data/kalshi_props.json`, no
`scripts/fetch-kalshi-props.mjs`, no `sharpFair` / `sharpGap` / `sharpOi` on the
props). That work shipped to `main` in parallel; the sharp-specific numbers
should be re-derived against the real Kalshi fairs before acting on a model
change. This finding rests on the two references present in the worktree: the
**de-vigged book lines** in `data/lineup-feed.json` and the **season-holdout
backtest** (`scripts/backtest_prop_model.py`), the honest out-of-sample test the
model docs require.

## 1. The bias is real and `rec`-specific, but centered on the line, not below it

Using the exact `fairProbOver` from `scripts/build_best_bets.mjs` (validated: it
reproduces the four production props exactly, e.g. Jefferson P(under) 0.706), Vault
P(over) was compared to the de-vigged real-book median at the modal line for every
scored prop:

| market | n | mean ΔP(over) | median ΔP(over) | mean(proj-line) | Vault < book |
|---|---|---|---|---|---|
| **rec** | 87 | **-5.5pt** | **-5.5pt** | +0.03 | **60/87 (69%)** |
| rec_yd | 77 | -3.0pt | -0.6pt | +3.37 | 42/77 (55%) |
| anytime_td | 42 | +6.4pt | +6.3pt | n/a | 7/42 |

`rush_yd`, `pass_yd`, `pass_att`, `pass_cmp` had **zero two-way real-book prices
in this feed** (quoted DFS pickem-style with null prices), so the book comparison
could not run there. That is itself part of why all four best bets are `rec`: it is
one of the only volume markets with a bettable two-way book market on this slate.

The tell: `rec` mean(proj-line) is about **0.03**. Vault's projections sit
essentially *on* the lines, yet P(over) is 5.5pt under. That is not a projection
sitting below the line, it is the **count distribution mapping a mean projection to
a sub-50% P(over)**.

## 2. Why the point projection is NOT the problem (season-holdout)

Season-holdout (fit on seasons < T, predict T, since 2016, test from 2021):

- **`rec` reliability, at lines near the projection:** `[0.50,0.60) pred 0.544 ->
  realized 0.502`. A line set at the model's own projection goes over about 50% of
  the time out-of-sample. The projection is honest.
- **`rec` mean signed projection error = +0.141 receptions** (n=22,378). If
  anything the projection runs slightly *high* vs what players actually do.
- The **cold-start** slice (game 1, projected off the prior season only, the exact
  regime of the current week-1 slate) has mean error **+0.37**, still not low.
- **A-grade `rec` picks win 66.0% out-of-sample** (n=13,192) against self-generated
  lines; grades are monotonic A >= B >= C >= D >= F.

Raising `rec` projections would therefore *degrade* accuracy. The suspected
"systematic low projection" is disproven.

P(over) is under 0.5 at the projection because receptions are right-skewed, so
**mean > median**. The realized over-rate at `line == proj` is **0.381**. The
nbinom in the model reproduces this (P(over) about 0.42 at proj==line). That is
correct, not a bug.

## 3. The actual cause, decomposed

For the flagged players the book line sits **above the player's own 2025 per-game
mean**, and the shrink term pulls the projection **below** even that mean:

| player | 2025 mean | recency-wtd | shrunk (proj) | book line | book vs 2025 mean | shrink cost |
|---|---|---|---|---|---|---|
| Justin Jefferson | 4.94 | 4.82 | 4.44 | 5.5 | **+0.56** | -0.38 |
| Nico Collins | 4.73 | 4.61 | 4.24 | 5.5 | +0.77 | -0.36 |
| DeVonta Smith | 4.53 | 4.27 | 3.99 | 5.5 | +0.97 | -0.29 |
| Colston Loveland | 3.62 | 4.20 | 3.92 | 4.5 | +0.88 | -0.28 |
| Tee Higgins | 3.93 | 4.19 | 3.90 | 4.5 | +0.57 | -0.29 |

Jefferson's roughly 1.5-reception gap from the model (4.44) to the book-implied
mean (about 6, needed for P(over 5.5) = 0.56) breaks down as:

1. **Book prices the role above the 2025 tape (about +1.0 rec, the dominant
   term).** The market expects more 2026 receptions than these players actually
   averaged in 2025. The model has essentially no 2026 games
   (`SEASONS = [cur-1, cur]`, week 1), so it cannot see this. This is the
   early-season / cross-season blind spot, confirmed, but it lives in the *market*,
   not in a projection error.
2. **Shrink toward the 2.57 league prior costs about 0.3 rec** (`k_vol = 2` in
   `data/prop_model.json`). For a stable, high-volume receiver, pulling toward an
   all-players 2.57 prior is unwarranted downward pressure. This is the one
   genuinely tunable contributor.
3. **The count distribution's mean>median skew** turns that projection deficit into
   a roughly 27pt P(over) gap. Correct behavior, but it magnifies (1) and (2).

`rec_yd` avoids the wall of unders because its projections run high (mean
proj-line +3.37), which offsets its own lognormal right-skew and nets near-neutral
vs books. `rec`, sitting on the line, does not get that offset.

## 4. Recommendation (measured, nothing shipped without walk-forward)

Because the projection is out-of-sample-unbiased, the honest response is
discipline, not a projection boost:

1. **Keep the agreement gate.** It correctly demoted 21 of these and is the right
   safety net for this cold-start regime.
2. **Treat `rec` count-market best-bets as held in the early season** (roughly
   weeks 1-3), while the projection is built almost entirely on the prior season.
   Same "labeled signal until validated" posture as
   [`docs/prop-td-redzone-plan.md`](prop-td-redzone-plan.md). A gate, not a model
   change, so it needs no walk-forward. Shipped behind the `EARLY_REC_HOLD_WEEKS`
   flag in `build_best_bets.mjs` (default 3; `--rechold=0` disables for the A/B).
3. **Candidate model tweak, only if it clears the season-holdout: lighten the
   `rec` volume shrink for high-volume players.** The flat `k_vol=2` toward a 2.57
   prior costs stable receivers about 0.3 rec. A usage-scaled or
   empirical-Bayes-by-volume shrink could recover it. But the aggregate signed
   error is already +0.14, so a *global* shrink reduction would likely hurt. Any
   change must be validated targeted, not global.

The season-holdout structurally **cannot** test the market-disagreement regime (it
sets lines off the model's own projection), so the only valid arbiter for a change
here is the **go-forward CLV harness on real closing lines**. That live data so far
is not alarming: `rec` picks show clv-beat 0.593 / win 0.556 (n=27), `rec_yd`
0.654 / 0.462 (n=26). Small samples, roughly break-even, no sign of a broken
under-machine, consistent with "the model is honest, the disagreement is a
role-information gap."

## What NOT to do

Do not globally lift `rec` projections or reshape the count distribution. Both are
validated as honest out-of-sample; changing them to chase agreement with the book
trades a measured model for the market's own number, the opposite of the point of
this model.
