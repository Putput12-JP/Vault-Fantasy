# Overs cohorts: forward tracking, registered before any new game is scored

Written 2026-10-26. Nothing here changes a pick, a price or a page, and nothing here is a betting rule: these are **tracked cohorts**, read once, so that "overs look strong" is tested on games nobody has looked at.

## Why this exists

A review of the first four nights (2026-10-22 to 10-25, 24 games, 187 players, about 2,100 first-look leans) found the model leans under far more than the 2025-26 backtest did (31% overs against 54%) while its over leans did better live (55.2% against 50.0% for unders), and that the model under-projects rotation players' minutes by about 2 to 3 minutes. Every cut below came from reading that sample, so each is a **post-hoc hypothesis**, and those four nights are **excluded** from the test.
`docs/live-vs-backtest-parity.md` has the numbers.

## Cohorts (fixed now)

Rows: the lean log's **first look** (`clock = f`), not held, a graded W or L (pushes and voids out), **games on or after 2026-10-26**. gap = (mu - line) / max(|line|, 0.5). p_mkt is the market's no-vig over chance (only rows with a sportsbook price carry one).

| Cohort | Definition | Why it is on the list (evidence already seen, not part of the test) |
|---|---|---|
| **O1** | over leans with gap >= 0.25 | live 61.6% (n 258); 2025-26 backtest 57.1% (n 624, interval 52.7 to 61.4) |
| **O2** | over leans where p_mkt > 0.5 (the market also leans over) | backtest 53.7% (n 1,599) |
| **O3** (check) | over leans where p_mkt < 0.5 (against the market) | backtest 45.0% (n 1,163): expected to lose; it tests whether the market gate is what matters |
| **U1** (check) | under leans with gap <= -0.25 (the strongest unders) | backtest 66.2% (n 151) but live 45.4% (n 350): does the backtest or the live read hold? |
| **A_over**, **A_under** | all over leans, all under leans | the base the cohorts are measured against |

## Rule (fixed now)

Statistic: hit rate of the leaned side, plus, for rows with a stored sportsbook price, the units at that price (context). Interval: **game-clustered bootstrap**, 2,000 draws, seed 7, 95%. Break-even at -110 is **52.4%**.
- **WORKS:** the interval's lower end is above 52.4%, with at least **300 rows and 100 games** in the cohort.
- **FAILS:** the interval's upper end is below 52.4% with the same minimums.
- **Inconclusive** otherwise, reported with its numbers; the cohort keeps being tracked.
- **Read once, on or after 2026-11-23, and only when O1 has 300 rows and 100 games** (O2 and the rest are read at the same time under the same minimums; a cohort short of its minimum is "collecting"). The first read stands; later looks are labelled monitoring.
- Four cohorts are tested together against one bar each; none is chosen afterwards, and a WORKS is a claim about hit rate against break-even, not about profit (pick'em-only lines carry no price).
- **Context, no verdict:** the same cohorts split by sportsbook-priced against pick'em-only lines, by stat, by projected minutes (under 15, 15 to 25, 25 and over), and the early-stop-style monitor: calibration of P(over) by band for each side.

## What a WORKS or FAILS would and would not change

A WORKS earns a pre-registered proposal (its own test, its own rule) for using the cohort in the page's ranking; it does **not** move any pick. A FAILS retires the hypothesis. Neither touches the model. The model's side skew is addressed at its cause (minutes), which is tracked separately (`rotation-minutes-shadow.md`).

## Not in scope

Any change to leans or to how the model leans; a tilt toward overs; the bet ledger (which has its own accept rules in `experiment-log.md`); the pick'em apps' payout structure.
