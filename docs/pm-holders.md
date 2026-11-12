# Polymarket holders scan

`scripts/scan_pm_holders.py` is run by `.github/workflows/pm-holders.yml`. It records who holds which side of every upcoming
full-game NBA, NFL and CFB market on Polymarket (moneyline, every spread rung, every total rung), and freezes that picture 15 minutes
before each game. It is step 2 of the proven-sharps side card:

- **Step 1** (`docs/pm-ledger.md`) grades each wallet's past bets.
- **Step 3** joins the frozen picture with those grades to split each side's money into sharp, unproven and losers.

Sharp money stays context only (CLAUDE.md).

## Where it lives

Output goes to the `pm-holders-data` branch. That branch is ordinary history and is never force-pushed, under `pm_holders/<sport>/`:

| Path | What |
|---|---|
| `log/<YYYY-MM-DD>/<HHMMSS>.jsonl.gz` | one immutable change log per cycle (UTC) |
| `frozen/<YYYY-MM-DD>/<slug>@<game start>.json` | the T-15 keyframe of one game, written once, never rewritten |
| `status.json` | last good cycle, last error, consecutive failures |

There is no state file. Each run rebuilds its state by replaying the last 8 days of logs, so a run that dies loses nothing. It also
keeps git from carrying a rewritten state blob every five minutes.

The repo is public, so this branch publishes wallet addresses and positions. Those are already public on Polymarket, and
`sharp-history` already carries the same kind of data.

## Cadence

Each market is read on a schedule set by how far away its game is.

| Time to game start | Read every |
|---|---|
| more than 24 h | 6 h |
| 45 min to 24 h | 15 min |
| under 45 min | 5 min |

Until 2026-11-12 the 3 to 24 h tier read hourly. It reads every 15 minutes now, so a game-day card is never more than about
15 minutes behind (the live cards rebuild every 10 minutes and the page reloads them every 2).

- **Freeze read.** One read must land between 20 and 15 minutes before the start; the loop wakes at T-18 to take it.
- **Nothing after the cut.** A read that finishes after the cut (game start minus 15 minutes) is thrown away.
- **Horizon.** NBA 72 h, NFL 7 days, CFB 5 days.
- **Two jobs.** NBA and football run in separate jobs with separate concurrency groups. Each loops while one of its games starts
  within 24 h. Otherwise it runs one cycle and the hourly cron (:41) takes over.

## Log rows

| `k` | Row |
|---|---|
| `cyc` | the cycle: start and end time, requests, markets due and read, misses, limit hits, late reads, HTTP stats |
| `m` | market facts on first sight or change: event slug, type, line, outcomes, token ids, game start |
| `p` | Gamma outcome prices, on change |
| `r` | every successful holders read of a market, with its completion time `rt`, holder count per outcome, and limit flags. This is the proof a market was read, so "no sharp holders" and "not read" are never confused. |
| `h` | a holding that changed: wallet, outcome, shares. `a:0` means the wallet left. |
| `n` | a wallet's display name, on change |

## Point-in-time rules

- **A wallet missing from a successful read has left.** The API serves every holder down to 0 shares, and drops a token's group
  when it has no holders. The exception is a token whose read hit the 1,000-row page limit: there, absent wallets are not marked as
  exits and keep their older `conf` (the last read that returned them).
- **`fs` is the first read that returned a wallet on that outcome; `fs_prev` is the read before it.** The entry happened between
  the two. A re-entry keeps the first `fs`.
- **`cens` means the wallet already held at our first read of that market.** Its true entry is earlier, so it is never a fresh
  position.
- **A keyframe uses only reads finished at or before the cut.** `frz_lag` is how long before the cut the last read was taken.
- **A postponed game gets a new keyframe.** Keyframes are keyed by slug and game start, so the old one is never edited.
- **The cut uses Polymarket's game start.** The side-card step compares it with Vault's own start time and flags a mismatch.
- **`usd_at_mark` is shares times the current price**, not what the wallet paid. Entry prices come from the step 1 ledger.

## Keyframe

```
{v, ev, gst, cut, written,
 mk:   {cid: {mt, line, outs, tok, px, read_rt, frz_lag}},
 miss: [cid not read before the cut],
 both: [wallets on both outcomes of one market],
 cols: [cid, oi, wallet, shares, usd_at_mark, fs, fs_prev, cens, conf],
 h:    [...rows...],
 names}
```

## Failure handling

- **A failed Gamma event listing** fails the cycle. Nothing is written for that sport, and the next cycle retries.
- **A failed Gamma price fetch** is logged as `price_err`, and holders are still read.
- **A failed holders batch** is split in half until the bad market is isolated. That market goes to `miss` and stays due.
- **The per-cycle request cap** (`--max-req`, default 400) ends a cycle cleanly. Unread markets stay due.
- **Push.** The two jobs write disjoint folders. A rejected push fetches and rebases, then retries.
- **Exit codes.** A job with unpushed commits at exit fails red. Six failed cycles in a row also turn the job red.

## First live read (2026-11-11, about 10 AM Central)

| Sport | Markets | Requests | Time | Log size (gz) | Misses | Tokens at limit |
|---|---|---|---|---|---|---|
| NBA | 662 | 49 | 15 s | 320 KB | 0 | 0 |
| NFL | 784 | | 2 min for NFL and CFB together | 223 KB | 0 | 0 |
| CFB | 4,800 | | | 1.0 MB | 0 | 0 |

The most holders on one NBA token was 229. Later cycles write only changes.
