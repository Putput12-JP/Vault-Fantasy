# CLV-ranked wallet tiers (Sharps audit, Step 1)

Code: `scripts/pm_clv_tiers.py`, wired into `scripts/build_side_cards.py` as an additive `rk` block. Tests: `tests/test_pm_clv_tiers.py`.
Why: `docs/sharps-audit-2026-11-18.md` found the "hot" label (win rate and dollar ROI from leaderboards) does not predict results, and that
closing-line value (CLV) is the skill that persisted. Sharp money is context only (CLAUDE.md): a tier is not a bet signal and does not count
toward an agree total, a lock or a size.

## What it measures

One observation per wallet x game x market type: the mean of (close - the wallet's average entry price) over its positions in that market.
Closes are stored prices only: Vault's T-15 keyframes (`pm_holders/<sport>/frozen`), else `data/pm_closes.json` (Pendulum Flow, the last
quote before kickoff). No close is estimated. Hedged and split rows and entries outside .02 to .98 are left out.

## Model and tiers

Per sport, the same shrinkage as `scripts/rank_pm_wallets.py`: observed mean y ~ N(mu_w, sigma_w^2 / n), mu_w ~ N(m, tau^2),
m and tau^2 by DerSimonian-Laird over wallets with 5+ games, sigma^2 the median wallet variance. p = P(mu_w > 0).

| Tier | Rule |
|---|---|
| sharp | 30+ games and p >= 0.95 |
| dull | 30+ games and p <= 0.05 |
| mid | 30+ games, neither |
| thin | under 30 games (listed, not tiered) |

The cut-offs are conventional and were set before the walk-forward below. No tier is given until 30 wallets have 5+ games.

## Point in time

A game counts only if it started before `asof`. A card's `asof` is its cut (game start minus 15 minutes), so a card never sees its own game
and the tier on a frozen card is the tier that existed at the lock. Win rate, dollar PnL and leaderboard rank are not inputs.

## Walk-forward (the test that matters)

Tier every wallet each week using earlier games only, then read the next 7 days of games by tier. Mean CLV per observation, SE in brackets.
Data: ledger positions with a stored close (NBA from Oct 20 2026, NFL from Sep 2026). Files: `data/pm_clv_tiers_backtest_nba.json`, `_nfl.json`.

| Tier at the start of the week | NBA next-week CLV | NFL next-week CLV |
|---|---|---|
| sharp | **+0.46%** (0.06), n 2,061 | **+0.76%** (0.08), n 1,343 |
| mid | -0.17% (0.04), n 7,877 | -0.00% (0.04), n 3,225 |
| dull | **-0.79%** (0.04), n 5,245 | **-0.78%** (0.04), n 2,715 |
| thin (under 30 games) | -0.45% (0.05), n 4,862 | -0.42% (0.04), n 3,646 |

Sharp wallets per weekly fold: NBA 15 to 22, NFL 12 to 15. Dull: NBA 23 to 84, NFL 19 to 71 (it grows as games accumulate).

Sharp wallets keep beating the close the next week and dull wallets keep losing to it, out of sample and without look-ahead. That is the
persistence the win-rate label did not have.

## Today's tiers (2026-11-18, from the ledger)

| Sport | sharp | dull | mid | thin |
|---|---|---|---|---|
| NBA | 22 | 83 | 105 | 572 |
| NFL | 17 | 77 | 67 | 616 |
| CFB | 3 | 15 | 11 | 155 |
| CBB | 4 | 1 | 14 | 85 |

## Limits, stated up front

- **This is skill at the entry price, not a copyable edge.** Entries are mostly before T-15; a follower at T-15 gets the T-15 price. The
  copy test (`docs/pm-accounts-copy-results.md`) found no edge 15 minutes later. Step 3 measures the price a follower can actually get.
- **Short window.** NBA closes start Oct 20 2026, NFL Sep 2026; about 3 to 4 weeks of weekly folds for NBA. The result is directional.
- **CFB and CBB are not validated.** Their closes are T-15 keyframes from Nov 11 only, so their tiers are computed and stored but the page
  shows the price-sharp line for NBA and NFL only.
- SEs treat observations as independent; wallets in one game share a close, so the real intervals are wider.
- CLV vs a T-15 close (keyframe days) and vs a pre-kickoff close (Pendulum days) are not identical; the mix is in both tiers and the test.
- Selection: the ledger universe came from leaderboards. Tiers rank wallets against that universe, so "sharp" means better than the
  other tracked wallets, and the sport mean m is negative (-0.4%) because everyone pays the spread.

## Registered next (Step 2, not part of this change)

Candidates A, B, C in the audit plan are tested on these tiers, forward only, per sport, with a new dated registration.

## On the page

NBA and NFL plays show "N price-sharp for, M against" in the card footer (`rk.sharp_n` on each side). The field is additive: cards built
before it have none and show nothing.
