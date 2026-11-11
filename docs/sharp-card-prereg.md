# Sharp side card: pre-registered forward test

Written on 2026-11-11, before any side card was frozen or graded. The commit that adds this file is the registration: its hash and
time are the proof that the rule came first. Nothing below may change after the first frozen card is graded. A change means a new
registration with its own date, and the old one is still read exactly as written.

Sharp money is context only (CLAUDE.md). This test decides only whether a pick label may be *proposed* for the side card. Passing it
does not add the card to any agree total. That needs a separate change to CLAUDE.md by the user.

## The lock

Each frozen side card (`scripts/build_side_cards.py` v1, built from the T-15 keyframe) carries `lock_shadow` per market group
(moneyline, spread, total). A **lock** is a side where SharpFlow's press-ladder gates (`pressLadderOverlay.js`) all hold, as of the
cut:

1. The money for the side is at least 60% of all money in the market group. This counts every wallet holding at least $250 on
   its largest single rung, except excluded wallets.
2. At least one wallet for the side, of any class, has a sport book of n >= 15 positions and holds at least 1.5x its usual stake.
3. No proven wallet is on the other side.
4. At least one proven wallet is for the side.

Proven, loser, excluded, position, the $250 floor and the hedge collapse are defined in the header of
`scripts/build_side_cards.py` and in `docs/side-cards.md`. Where Vault approximates a SharpFlow rule, that header says so.

## Variants

| Variant | Wallet books are built from | Role |
|---|---|---|
| **A: all rows** | every ledger row settled before the cut, for wallets already in the universe at the cut. This includes `backfill` rows, history from before Vault started tracking the wallet (SharpFlow's way). | **primary** |
| **B: forward rows** | only `forward` rows: games after the wallet was selected | secondary, read alongside A |

A wallet first selected after the cut is untracked on that card in both variants. If A passes while B has n >= 100 and a flat ROI
at or below 0, the result is reported as **"A passed; B does not support it"**, not as a clean pass.

## Which cards count

A frozen card counts toward the test only if its `test.counts` is true:

- **built before game start;**
- **built on a ledger run that finished before the cut;**
- **not a duplicate.** If a game has several frozen cards (a postponed game), the one with the earliest cut counts. The others are
  listed as duplicates.

Cards that do not count are listed with their reason and never enter n, ROI or CLV.

## Bet, price and result

- **Per sport, never pooled:** NBA, NFL and CFB are read separately.
- **One lock per counted card per market group.** The moneyline is the headline. Spread and total locks are reported, but they are
  not part of the pass test.
- **Price.** Polymarket's displayed price (Gamma `outcomePrices`) of the locked outcome at the cut, read from the keyframe
  (`lock_shadow.price`, `price_t` <= cut). It is a mid or last price, not the ask. A second ROI line at the stored ask is reported
  when one exists.
- **Unpriced.** A lock whose price is missing, or whose `price_t` is more than 30 minutes before the cut, is unpriced. It is listed
  but not in ROI. If unpriced locks exceed 10% of a sport's counted moneyline locks, that sport's read is a data-quality failure
  and gets no verdict.
- **Market.** The moneyline, or for spread and total the rung carrying the most proven money for the side (`lock_shadow.cid`).
- **Profit per lock, flat 1 unit.** A win pays 1 / price - 1, a loss pays -1, and a push or a 0.5 resolution pays 0. Flat ROI is
  the mean of those values.
- **Result.** The market's own Polymarket resolution. Every counted lock is graded; none is dropped.
- **Units.** The clean-ladder units (`units_clean_ladder`) are reported as a second line, never as the test.

## Closing-line value

**CLV = the locked outcome's close minus its price at the cut**, in probability points.

The close comes from `data/pm_closes.json`, the Pendulum Flow archive's last quote before kickoff, using its `p` field:

- **Matching.** A row matches on event slug, market type and line, plus an outcome list identical to the locked market's.
- **Side.** `p` is the price of `outcomes[0]`, so the locked side's close is `p` or `1 - p`.
- **No close stored.** The lock is left out of the CLV mean and counted. No close is ever estimated, and the step 2 holders log is
  never used, because it stops at the cut.

The archive covers NBA and NFL. **CFB has no stored close, so CFB is read on ROI only and its CLV is "not available".** That is said here in advance.

## Statistics

- **n.** The number of priced, counted moneyline locks in variant A for the sport.
- **Intervals.** Both the flat-ROI and CLV intervals are 95% percentile bootstraps: 10,000 resamples, seed 20261111, resampling
  locks.

## When it is read, and what passes

| Sport | Final read | Minimum n |
|---|---|---|
| NBA | the first Monday after the last scheduled game of the 2026-27 regular season | 300 |
| NFL | the Tuesday after Week 18 of the 2026 season | 300 |
| CFB | the Monday after the 2026 conference championship weekend | 300 |

- **Interim reports** may be published monthly and are report-only. Only the final read on the date above gives a verdict, and a
  verdict is never revisited on this registration.
- **Pass** (per sport, variant A, moneyline) needs all of:
  1. the flat ROI interval's lower bound is above 0;
  2. mean CLV is above 0 and its interval's lower bound is above 0 (NBA and NFL only; CFB is read on condition 1 alone);
  3. n is at least the minimum.
- **Fail:** n reaches the minimum and the pass conditions do not hold.
- **Underpowered:** n is below the minimum on the final read date. It is neither a pass nor a fail. NFL and CFB will very likely
  be underpowered this season; that is expected and is said here in advance.
- **What every read reports:** n, win-loss, flat ROI with its interval, CLV with its interval, the unpriced and no-close counts,
  the variant B line, the spread and total lines, and the count of non-counting cards by reason.
- **Better-looking slices** (a tier, a market, a month) are flagged for close monitoring with their n, per the house rule. They are
  never promoted on the same data.

## Known limits, stated before the data

- **The ledger lags.** It runs nightly, so a game settled the same day is not in a wallet's record until the next run.
- **The cut is Polymarket's start time.** `vault.start_gap_flag` marks a gap of more than 10 minutes to Vault's start.
- **Money is mark value**, shares times price at the cut, not what the wallet paid.
- **Holders below the $250 floor are not on the card.** Holders past the API's 1,000-row page limit would be missing, though the
  most seen on one token is 229.
