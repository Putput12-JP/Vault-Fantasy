# Sharp agreement on Vault's own game prices: pre-registered forward test (Step 4)

**Status: Registered.** Proposed on 2026-11-19 and approved by the user as written the same day, with every decision below taken as proposed.
The commit that changes this line from PROPOSED is the registration: its hash and time are the proof that the rule came first. Nothing below may change after the first row is graded. A change is a new registration with its own date.

Step 4 of `docs/sharps-audit-2026-11-18.md`. Steps 1 to 3 are `docs/pm-clv-tiers.md`, `docs/sharp-tier-prereg.md` and `docs/sharp-speed-prereg.md`.
Sharp money is context only (CLAUDE.md). This is a measurement. It never feeds Top Reads, SM_GATE, a Play or an agree total. A pass only lets the
user *consider* showing "sharps agree" or "sharps against" as context on a game Play; it changes nothing by itself.

## The question

Vault's V2 board calls a price a Play when it beats Pinnacle and the exchange. Does it matter whether CLV-ranked wallets (Step 1 tiers) are on the
same side? Two uses: a **boost** (agree means a better price) and a **veto** (against means a worse one).

## What cannot be tested, said first

- **Props are out.** The wallets hold full-game moneyline, spread and total markets. There is no stored link from a game position to a player
  prop, so the NBA fair-agreement rule (`docs/retro/nba-fair-agreement-rule.md`), which is props, cannot be boosted or vetoed by this data. Of
  the 392 V2 Plays logged to Nov 19, 353 are props and only 39 are game markets, so most of the record that earns its ROI is out of reach.
- **Plays alone cannot power the test.** NBA has about 25 game Plays in 4.5 weeks. The test therefore reads every V2 **game row** (Play, Watch
  and Passed alike, all stored at first sight with the same fields), and reports the Plays subset beside it with no verdict. Whether a
  price edge that fails the Play gates behaves like one that passes is itself an assumption, stated here.

## Data and scope

- **Rows:** every V2 game-market row (`kind` book or exch) in `v2_plays.json`, `v2_watch.json` and `v2_passed.json` for **NBA and NFL**. CFB and CBB
  have no validated tiers (Step 1) and are not in this test.
- **Which rows count:** `firstSeen` at or after **2026-11-20 00:00 CT** (epoch 1795154400). Earlier rows are not touched. On Nov 19 the three
  files hold NBA about 950 and NFL about 240 game rows; I counted them to plan sample size and computed no flag or result for any of them.
- **Unit:** one row, keyed as the ledger keys it (game, market, side, line). Rows of one game share a close, so intervals resample games.

## The flag, rebuilt as of first sight

For each row, the flag is rebuilt from stored data **as of `firstSeen`**, never later:

1. **Match the market.** Join the row's game to the Polymarket market by sport, teams and date. Moneyline matches the moneyline market. A spread or
   total row matches only a market with the **same line**. No match, or a line mismatch, is `no_read`.
2. **Holders as of first sight.** Replay the holders change log (`pm_holders/<sport>/log/`) to the row's `firstSeen`. The market needs an accepted
   holders read finished no more than **60 minutes before** `firstSeen`, else `no_read`. Holders are the card's: $250 or more on a side, a two-way
   wallet collapsed to its larger side, class `excluded` dropped.
3. **Tiers as of first sight.** Each wallet's tier is the Step 1 tier computed from games that started before `firstSeen` (`pm_clv_tiers.py`,
   MIN_N 30, sharp p >= 0.95, dull p <= 0.05). Only wallets with `first_seen` in the ledger at or before **2026-11-19 12:00 AM CT** can be sharp or
   dull (the Step 2 frozen universe).
4. **Cell**, with S = the side the row bets:

| Cell | Rule |
|---|---|
| `agree` | at least 1 sharp wallet on S and none on the other side |
| `against` | at least 1 sharp wallet on the other side and none on S |
| `mixed` | sharp wallets on both sides |
| `none` | holders read, no sharp wallet on either side |
| `no_read` | no market match, line mismatch or no read in the window. Counted, never graded |

Dull wallets are reported as a separate split inside `none` (`dull_with`: a dull wallet on S, `dull_against`: one on the other side) and carry no
verdict. They are Step 2's test.

## Measures

- **Primary: row CLV** as the ledger already stores it: the exchange's close fair of the side divided by the stored price, minus 1, close from the
  exchange tape, empty when the line moved or the quote was wider than 6 points. A row with no close is counted, not estimated.
- **Secondary: flat ROI** at the stored price, from the final score as the ledger settles it. Void is excluded.
- **Intervals:** percentile bootstrap, 10,000 resamples, seed 20261119, resampling **games**. Four tests are registered (2 sports x 2 contrasts),
  so the pass test uses the **98.75% interval** (0.05 / 4). The report also shows 95%.

## The contrasts and the pass rule

| Test | Contrast (mean row CLV) | Passes when |
|---|---|---|
| Boost | `agree` minus `none` | the interval's **lower** bound is above 0 |
| Veto | `against` minus `none` | the interval's **upper** bound is below 0 |

Each test is per sport (NBA, NFL), never pooled. A test is read only when both cells have **at least 150 rows with a close and 40 games**.
A pass is a reason to consider a context label. It is not promotion and does not touch a Play, a size or an agree total.

- **Kill:** at the same minimums, the contrast's interval lies wholly on the wrong side of 0 (boost wholly below 0, veto wholly above 0). A killed
  test stops being reported as a candidate.
- **Underpowered:** a cell below the minimum on the read date. Neither a pass nor a fail.
- **Every read reports:** rows, games, no-close and `no_read` counts by cell, CLV and ROI with both intervals, and the **Plays-only subset** with its
  n and no verdict. A slice that looks better (a market, a month, a wallet) is flagged for close monitoring with its n and never promoted on the
  same data.

## When it is read

| Sport | Final read |
|---|---|
| NFL | the Tuesday after Week 18 of the 2026 season (2027-01-12) |
| NBA | the first Monday after the last scheduled game of the 2026-27 regular season |

Interim reports monthly, report-only.

## Expected sample, said in advance

At the Nov 19 rates, NBA game rows come in at about 200 a week and NFL about 50. If a tenth of rows land in `agree` and a tenth in `against`
(unmeasured, an assumption), NBA reaches about 150 rows in each cell around February. NFL will very likely stay **underpowered** (about 450 rows
by Week 18, so cells near 45). That is expected and is said here in advance. Plays alone (NBA about 6 a week) will not reach any cell minimum.

## Build, and what it may not change

The flag is **derived** from append-only stored data (holders log, tier code, ledger), not logged live, so the script (`scripts/sharp_agree.py`)
can be written after this registration. It must be committed and tested on rows first seen after registration **before any row is graded**, and it
may not change a definition above. If the stored holders log cannot reproduce a flag as of `firstSeen` for more than 30% of NBA rows, the test
reports `no verdict, data` and the fix is a new registration, not a looser window.

## Known limits

- Wallet tiers measure skill at the wallet's own entry price. Whether a follower gains from knowing it is the question; Step 3 says what the
  order book charges and may show the edge is gone by detection.
- The tier universe came from leaderboards. "Sharp" means better than the other tracked wallets (`docs/pm-clv-tiers.md`).
- Polymarket game markets are thinner than US books, so a read can sit on a few wallets. The $250 floor is the card's, not tuned here.
- Row CLV is against exchange closes, which are the benchmark the Play gates already use, so a row that passes the gates may have a CLV biased
  upward. The contrast cancels that only if it affects all cells equally.
