# Polymarket wallet ledger

`scripts/build_pm_ledger.py`, run daily by `.github/workflows/pm-ledger.yml` at 3:20 AM Central, writes `pm_ledger/` on the
`sharp-history` branch. It is step 1 of the "proven sharps" side card (the SharpFlow-style card: combined proven-sharp record, L30 ROI,
lifetime $, last 20, sharp / unproven / losers money). It only records and grades wallet bets. Deciding who is proven happens later,
point in time, from these rows. Sharp money stays context only (CLAUDE.md).

## What a row is

One wallet's net holding of one outcome of one full-game NBA, NFL or CFB market (moneyline, spread, total) at the **cutoff**, which is
game start minus 15 minutes (SharpFlow's T-15 freeze). It is graded against the market's own resolution on Polymarket.

| Field | Meaning |
|---|---|
| `w`, `cid`, `oi` | wallet, condition id, outcome index (the key) |
| `sport`, `mt` | nba / nfl / cfb; moneyline / spreads / totals |
| `gst`, `settled_at` | game start and the market's close time from Gamma (epoch seconds). Cutoff is `gst - 900`. |
| `sh`, `stake`, `avg` | shares held at the cutoff, their average-cost basis in USDC, and the average price |
| `res`, `pnl` | win / loss / push, and `sh x resolved price - stake` |
| `first`, `last` | first and last pre-cutoff buy |
| `exited`, `post` | shares sold before the cutoff; shares traded after it (in-play, ignored) |
| `hedged` | the wallet held both outcomes at the cutoff (both legs are written) |
| `split` | a SPLIT or MERGE touched the holding; its stake is a booked 0.5, not cash, so keep it out of dollar ROI |
| `src` | `forward` if the wallet was selected before the cutoff, else `backfill` |

Slug, outcome name and line live in `markets/<sport>.json`, looked up by `cid`.

No row is written when the wallet sold out before the cutoff, only bought in-play, or used a negRisk conversion before the cutoff.
Each case is counted in `summary.json` under `conditions`.

## Look-ahead rules

- **Settle time is the market's close, never the wallet's last trade.** Polymarket's `last_event_at` is often a pre-game trade.
- **A row is written only after the market resolves.** Until then its fills wait in `pending.json`.
- **Fills are read once the cutoff is 30 minutes old**, so the activity index has every pre-cutoff fill. If Gamma later moves the
  game start, the fills are read again for the new cutoff.
- **`first_seen.json` holds the epoch second a wallet was first selected**, from the real clock. A game whose cutoff is before
  that is `backfill`: the wallet was picked with hindsight. Anything built on `backfill` rows must say so and keep them apart.
- **Once selected, a wallet is read on every run**, whether it is still on a leaderboard or not. A forward record never depends on
  the wallet having kept winning.
- **`user_stats/<date>.jsonl` snapshots the market-maker features** (maker rebate, trade count, volume) per day, so an exclusion can
  be applied as of a date.

## Who is tracked

`universe/<date>.json` records why each wallet was polled:

- Polymarket's all-time sports PnL board, top 1,500 with positive PnL (SharpFlow's `LB_DEPTH`).
- The monthly sports board, top 1,000 with PnL of at least $20K (SharpFlow's `MIN_MONTHLY_PNL`).
- Vault's own classified wallets: the `sharp` and `dull` lists in `data/pm_wallets*.json`, and every tiered wallet in
  `data/pm_wallet_rank.json`.
- **Fat-ticket discovery** (SharpFlow's `discoverScanSupplement`). This runs on every full run and on three discovery-only runs at
  12:20, 4:20 and 8:20 PM Central. It reads the holders of every full-game market starting in the next 36 hours. A new wallet is
  added when it holds at least $2,000 on one market (valued at the current price) and its all-time and this-month sports PnL are
  both positive.

Once a wallet is added it stays tracked, so the universe grows day by day, the same way SharpFlow's list grew to 1,646. Market-maker
and trader exclusion is NOT applied at this stage. It is decided point in time from `user_stats/` and the rows, in the side-card step.

## Safety

- **Append-only.** A key already in the ledger is never rewritten. If a new grading disagrees with a stored row, the stored row stays
  and the disagreement goes to `conflicts.jsonl` for a person to read.
- **Bounded runs.** `--max-req` and `--max-secs` stop the run cleanly, and everything read so far is saved. Position reads go
  oldest-first from a per-wallet high-water mark that moves page by page, so a capped run resumes where it stopped.
- **Never a partial fill list.** If the activity feed for a batch of markets hits the page cap, the batch is split and re-read. A
  single market that still does not fit is dropped and counted as `too_many_fills`, with no row built.
- **A Gamma failure is not "unknown market".** The run records the failure and retries next run. A market Gamma does not know on 3
  separate runs is dropped and counted as `gamma_missing`.
- **Polite.** Requests are paced globally and honour `Retry-After` on 429 and 503.

## Dry run (2026-11-11)

See the PR description for the measured request counts, rate-limit probe, sizes and backfill estimate.
