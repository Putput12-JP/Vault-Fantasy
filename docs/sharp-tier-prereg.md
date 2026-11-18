# CLV-tier shadows: pre-registered forward test

Written on 2026-11-18, before any tier play was built or graded (the first possible card is cut at 2026-11-19 12:00 AM Central, epoch
1795068000). The commit that adds this file is the registration: its hash and time are the proof that the rules came first. Nothing below
may change after the first tier play is graded. A change is a new registration with its own date, and this one is still read as written.

Step 2 of `docs/sharps-audit-2026-11-18.md`. The tiers are `scripts/pm_clv_tiers.py` (`docs/pm-clv-tiers.md`); the plays are
`scripts/sf_tiers.py`. Sharp money is context only (CLAUDE.md): these are **shadows**. They are never shown as a pick, never set a size, and
never feed Top Reads, SM_GATE or an agree total. Passing this test only lets the user *consider* a change to the card (a separate decision
in CLAUDE.md). It does not make one.

## What was learned before this registration (so it is not counted as evidence)

Walk-forward on NBA and NFL ledger positions since Sep 2026 (`docs/pm-clv-tiers.md`): sharp-tier wallets kept beating the close the next week
(+0.46% NBA, +0.76% NFL), dull-tier wallets kept losing to it (-0.8%). That is skill at the wallet's *entry price*. Whether a follower at the T-15
price gets any of it is exactly what this test measures. The three rules below were not fitted to outcomes of any play: no tier play has ever
been graded. I did count how often each rule fires on already-frozen cards (to plan sample size, below) and did not look at their results.

## The universe, frozen

A wallet can appear in a tier play only if its `first_seen` in the ledger (`pm_ledger/first_seen.json`) is **at or before 2026-11-19 12:00 AM
Central**. Wallets the ledger adds later (leaderboard scans, fat-ticket discovery, SharpFlow's boards) still appear on cards but can never be
the sharp or dull wallet in a tier play. This is the guard against the hindsight selection that sank the "hot" label. As of today the ledger
has 3,205 wallets, all first seen Nov 11 to Nov 18.

Also frozen, in code at the registering commit:

| Item | Value |
|---|---|
| Tier model | `pm_clv_tiers.py`: per-sport shrinkage, MIN_N 30 games, sharp p >= 0.95, dull p <= 0.05, entries priced .02 to .98, hedged and split rows out |
| Tier clock | as of the card's cut (game start minus 15 minutes); only games that started before it |
| Holders | the card's own: $250 or more on a side, a two-way wallet collapsed to its larger side, wallets of class `excluded` dropped |
| Sports | NBA and NFL. CFB and CBB tiers exist but have no registered test (their closes are T-15 keyframes from Nov 11 only) |
| Cards that count | a frozen card with `test.counts` true (built before game start, on a ledger run before the cut, not a duplicate) and cut at or after the registration time. No tier play exists for an earlier card, so there is nothing in-sample |

## The rules

Per frozen card and market group (moneyline, spread, total), at most one play per rule:

| Rule | Name | Plays side X when |
|---|---|---|
| `tA` | Follow price-sharps | at least one price-sharp wallet is on X and no price-sharp wallet is on the other side |
| `tB` | Fade price-dull | at least one price-dull wallet is on the other side and none is on X (the play is X, the opposite of the dull money; no sharp needed) |
| `tC` | Both | `tA` and `tB` both fire on X |

Overlaps are expected (`tC` is inside `tA` and `tB`) and each rule is read on its own. This changes the audit plan's wording of A, which
excluded a dull wallet on the other side: that made `tC` impossible, so `tA` now ignores dull wallets and `tC` carries that evidence.

- **Market:** the rung carrying the most supporting money (the sharps' money for `tA` and `tC`, the dull wallets' for `tB`).
- **Price:** the market's stored displayed price for X at the cut (Gamma / keyframe `px`, a mid or last price). **No ask is stored, so none
  is used.** Both CLV and ROI are therefore before the spread; the final read reports the mean bid-ask spread at the close from
  `pm_closes.json` beside them. A positive CLV smaller than about half that spread is not a copyable edge, and the read says so.
- **Stake:** flat 1 unit. A win pays 1 / price - 1, a loss -1, a push or 0.5 resolution 0. The result is the market's own Polymarket resolution.
- **Unpriced:** a price missing or older than 30 minutes before the cut (confirmed-unchanged re-reads allowed, as in the lock test) is listed,
  not in ROI or CLV. If unpriced plays exceed 10% of a sport's counted plays for a rule, that sport and rule get no verdict.
- **CLV:** close minus the price at the cut, close from `data/pm_closes.json`, matched on event, market type, line and outcome list. A play with
  no stored close is left out of the CLV mean and counted. No close is ever estimated.

## Statistics

- **n:** priced, counted plays with a stored close, per rule and sport, the three market groups pooled for the pass test and each group reported.
- **Intervals:** percentile bootstrap, 10,000 resamples, seed 20261111, resampling plays. Six tests are registered (3 rules x 2 sports), so the
  pass test uses the **99.17% interval** (0.05 / 6). The cards record also shows the 95% interval.

## When it is read and what passes

| Sport | Final read | Minimum n (CLV) |
|---|---|---|
| NFL | the Tuesday after Week 18 of the 2026 season (2027-01-12) | 300 |
| NBA | the first Monday after the last scheduled game of the 2026-27 regular season | 300 |

- **Interim reports** monthly, report-only.
- **Pass** (per rule and sport): mean CLV above 0, the 99.17% CLV interval's lower bound above 0, and n at least 300. A pass is a reason to
  consider the rule for the card. It is not promotion.
- **Kill:** the CLV interval lies wholly below 0 at n >= 300, or the flat ROI interval lies wholly below 0 at n >= 1,000. A killed rule stops being
  built.
- **Underpowered:** n below the minimum on the read date. Neither a pass nor a fail.
- **Every read reports:** n, W-L, flat ROI with both intervals, CLV with both intervals, the unpriced and no-close counts, the mean closing
  spread, and each market group on its own.
- **Better-looking slices** (a group, a month, a wallet) are flagged for close monitoring with their n. They are never promoted on the same data.

## Expected sample, said in advance

Firing rates on the Nov 13 to 18 frozen cards (counts only, no results): `tA` about 9 plays a day across NBA's three groups, `tB` about 1 a day
and `tC` about one every five days; NFL `tA` about 11 a week, `tB` and `tC` a few a week. At those rates:

- **NBA `tA`** should reach 300 around the new year and is the one test with real power.
- **NBA `tB` and `tC`, and all three NFL rules, will very likely be underpowered** (NFL `tA` about 100 by Week 18, NBA `tB` about 150 by April).
  That is expected and is said here in advance. The interim reports will show direction, and the kill rule still applies if an interval is wholly
  below 0 early.

## Known limits, stated before the data

- Tier plays inherit the card's holder floor ($250), so a sharp wallet under it is invisible.
- Wallets in one game share a close and a result, so plays are correlated; the bootstrap resamples plays and its intervals are a little narrow.
- The ledger runs nightly; a wallet's game that settled the same day is not in its CLV until the next run.
- The tier uses closes from Vault's T-15 keyframes (from Nov 11) and `pm_closes.json` before that; the two are not identical quotes.
- A sharp tier is better entry prices than the other tracked wallets, not proof of winning picks.
