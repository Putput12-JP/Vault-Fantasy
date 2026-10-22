# Wallet ranking: shrinkage and cross-sport pooling

Sharp Price V2, step 2. Code: `scripts/rank_pm_wallets.py`; tests: `tests/test_rank_pm_wallets.py`; output: `data/pm_wallet_rank.json`
(rebuilt weekly after the scorecards in `update-pm-wallets.yml`). It ranks accounts; it does not change who the shadow ledger
(`sharp-follow-prereg.md`) calls sharp, which stays frozen on the scorecard's hard t >= 3 label.

## Model

Each scorecard row gives a wallet's number of games, mean closing-line value per game and its spread. For wallet w in sport s:

- observed mean `y` has noise variance `sigma_w^2 / n` (the wallet's own spread, mixed with the sport's median spread as if it had 4 more games);
- true skill is drawn from `N(m_s, tau_s^2)` across wallets, with one correlation `rho` between a wallet's skill in different sports.

`m_s` and `tau_s` come from the wallets with 5+ games (below that the wallet's own spread is noise), by method of moments. `rho`
comes from wallets seen in two sports. The posterior skill in the target sport given everything seen on the wallet is a conditional
Gaussian: few NBA games lean on the league average and on the NFL / CFB record, in proportion to how noisy each is.

Tiers by `p`, the posterior chance skill is above zero: proven >= 0.95, probable >= 0.80, watching >= 0.60, dull <= 0.05.
The cut-offs are conventional, set before the hold-out was run, and were not tuned.

## Fitted values (2026-10-22 scorecards)

| | mean m | skill spread tau | median game spread |
|---|---|---|---|
| NFL | -0.44% | 0.74% | 2.4% |
| CFB | +0.25% | 0.68% | 2.9% |
| NBA | -0.42% | 1.18% | 2.6% |

`rho` = 0.64, but its 90% bootstrap interval is **0.00 to 0.95** on 117 wallet pairs: the data cannot yet say how much skill
travels between sports. The study's NFL-sharp-on-NBA result (+1.76%, 439 trades, t 3.0) says it is above zero, nothing more.

## What it changes for NBA (818 wallets with 3+ games)

proven 4, probable 13, watching 51, dull 20, unranked 730. The old hard label had 1 NBA sharp wallet (7 sharp wallets in all sports).
All 7 wallets the old rule called sharp are ranked (1 proven, 4 probable, 2 watching); 61 more wallets are proven, probable or
watching with no old label (see `old` on each row).
The old rule also called 13 wallets dull; the ranking keeps only 2 of them dull, because the sport's average wallet already
loses 0.4% and a handful of games cannot show a wallet is worse than that.

## Hold-out: does the NFL + CFB record rank NBA skill?

Wallets ranked for the NBA from NFL and CFB data only, then scored on the NBA games they actually have (208 wallets, 520 games,
mean -0.43%, SE 0.11%):

| Tier from other sports | Wallets | NBA games | NBA mean (SE) |
|---|---|---|---|
| probable or better | 2 | 5 | +2.9% (1.2%) |
| watching or better | 11 | 34 | -0.03% (0.45%) |
| dull | 1 | 9 | +0.14% (0.87%) |
| old rule (other-sport t >= 3) | 1 | 4 | +3.1% (1.3%) |

**This does not validate the pooling.** The groups are 1 to 11 wallets and under 35 games; "watching or better" is
indistinguishable from the average wallet. Sensitivity, not used: at `rho` 0.30 no wallet reaches probable from other-sport data; at 0.95 the dull group is 12 wallets
and 33 games at -0.84% (SE 0.45%) and proven is 2 wallets at +2.9%. The direction is right, but `rho` was not chosen by the hold-out.
The scorecards store sums,
not dated games, so a within-sport time split is impossible; the shadow ledger's cohort tags (sharp / other) are the real
out-of-sample test.

## Limits

- Group SEs assume wallets are independent; wallets in the same game share the same close.
- Scores are relative returns on dollar-weighted entries, so longshot buyers have large spreads; the median spread is used for shrinkage to keep them from setting everyone's.
- A wallet is one address; one person can run several.
- Every tier is for context. Sharp money is not a bet signal and does not count toward an agree total.
