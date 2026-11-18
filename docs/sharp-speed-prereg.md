# Sharp tape: what a follower can actually get (Step 3 registration)

Written on 2026-11-18, before any row was graded. The commit that adds this file is the registration; the rules below change only by a new dated
registration, and this one is still read as written. Step 3 of `docs/sharps-audit-2026-11-18.md`.

Step 1 showed CLV-sharp wallets beat the close at **their own** entry price. Step 2 tests the T-15 follow. The earlier copy test
(`docs/pm-accounts-copy-results.md`) found nothing 15 minutes after a trade. This asks the sharper question in between: **when a tiered
wallet's buy first appears in the trade feed, what does the order book charge a follower, and is the closing line still above it?**
Sharp money is context only (CLAUDE.md). This is a measurement; nothing here is a pick, a size or an agree total.

## What is built

- `scripts/pm_sharp_tape.py`: watches wallets and, for each pre-game BUY of a full-game NBA or NFL moneyline, spread or total, reads the order
  book of both outcomes at the moment of detection (best ask, its size, best bid, the average price for $100) and again 1, 5 and 15 minutes
  later. Rows go to `pm_tape/<sport>/<date>.jsonl` on `pm-holders-data`, append-only.
- `scripts/grade_sharp_tape.py`: grades what has a stored close into `pm_tape/tape_record.json`.
- `.github/workflows/pm-tape.yml`: a ~170 minute loop started every 3 hours; run markers (`k: r`) make any gap countable.

## Who is watched (frozen per run, point in time)

Sharp and dull wallets of the CLV tier file computed at the start of the run (`pm_clv_tiers.py`, only games already started), plus the 40 most
active `mid` wallets per sport as the **control**. Only wallets with `first_seen` at or before 2026-11-19 12:00 AM Central (the Step 2 frozen
universe) are watched. A wallet's tier is fixed for the run that detects its trade, so a later change in tier never rewrites a row.

## Measures

| Play | Who | Buy | CLV |
|---|---|---|---|
| `follow` | sharp (control: mid) | the wallet's outcome at the best ask at detection | close - ask |
| `fade` | dull (control: mid) | the **other** outcome at its best ask at detection | (1 - close) - that ask |

- **Close:** the last quote before kickoff in `data/pm_closes.json`, matched on event, market type, line and outcome list. A row with no stored
  close is counted and left out. No close is estimated.
- **On time:** `late` is false, i.e. the trade was first read within **300 seconds** of its own timestamp. The trade feed itself shows a buy 2 to
  4 minutes after it happened (smoke run below), so 300 s is the realistic floor for any follower using it, not a tuned value. Late rows are
  kept and counted. Latency buckets (0 to 120, 120 to 240, 240 to 300 s) are reported.
- **Observation:** one per wallet x game x market type x line x play, the mean over its rungs, so a ladder of twenty fills counts once.
- **Standard errors** are clustered by game (wallets in one game share a close).
- **Context lines, not tests:** the wallet's own CLV (close - their price), the **slip** (ask - their price: what the delay cost a follower),
  and markouts (the bid 1, 5 and 15 minutes after detection minus the ask paid).

## When a test is cleared

Four tests (sharp `follow` and dull `fade`, NBA and NFL). One is **cleared** when all hold:

1. n >= 100 observations;
2. mean CLV at the ask minus 2 standard errors is above 0;
3. the same sign in the first and second half of the sample by game date (`halves`);
4. the matching control (`mid`, same play, same sport) is **not** itself cleared (otherwise the effect is any wallet's buy, or drift, and not
   skill).

A cleared test lets the user *consider* a real-time context alert for that sport. It does not make one, and sizing or picks stay out
(CLAUDE.md). Four tests at 2 standard errors is not a Bonferroni bar: about 0.1 false clears are expected, which is why condition 3 and 4 exist
and why a clear is read again on the next 100 observations before anything ships.

**Kill:** mean CLV minus 2 standard errors below 0 at n >= 100 for a play stops that play being built. **Too few:** under 100 observations.
Interim reads are report-only until n >= 100.

## Smoke run, before registration (plumbing, not evidence)

A 2.5 minute live run on 2026-11-18 (207 wallets: 29 sharp, 125 dull, 53 mid) wrote 21 trade rows on one game's totals: latency 75 to 239
seconds, the ask averaged 1.8 points above the wallet's own price, the bid-ask spread averaged 2.05 points. No row had a close, so nothing was
graded. That is why the late threshold is 300 seconds and why a 2-point spread is the bar a follower starts under.

## Known limits, said in advance

- **The feed lags the trade by minutes.** A follower using it cannot act inside a minute. If every on-time row's CLV is eaten by the slip, the answer
  to "can a user follow" is no from this feed. Faster wallet attribution (on-chain OrderFilled logs) is a separate build, not part of this test.
- BUYs only; a sharp exit is not a follow. Wallets that quote both sides (market makers) are in the tiers like any wallet; the control and the
  dull fade show whether that matters.
- Runs start every 3 hours with a gap of minutes; trades in a gap are never detected (not back-filled), so coverage is counted from the run markers.
- Wallets laying a ladder on one game make correlated observations; the clustered SE handles the game, not the wallet's style.
- The tape reads displayed best ask and depth; a $100 walk price is stored, larger sizes are not read.
- CLV is price movement against the close, not a win rate. ROI is not graded here.
