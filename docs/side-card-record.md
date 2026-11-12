# Proven-sharps record (step 4)

`.github/workflows/pm-record.yml` runs every 2 hours and keeps two records on `pm-holders-data` under `pm_record/`. Rows are
append-only and the branch is never force-pushed. Sharp money is context only (CLAUDE.md): these are records, not a pick feed.

## 1. Vault's cards (`scripts/grade_side_cards.py`)

Every frozen card (`pm_cards/<sport>/frozen/...`) is graded once its markets resolve. Per market group (ml, spread, total) and
variant (`all`, `fwd`), two plays are graded when the card has them:

| Play | What it is | Units line |
|---|---|---|
| `lock` | the pre-registered lock (`lock_shadow`, `docs/sharp-card-prereg.md`) | the clean-ladder units, a second line only |
| `sf` | the size the card shows (SharpFlow's staking rules, labelled "untested rule") | the shown units |

The rules are the pre-registration's:
- **Result:** the market's own Polymarket resolution. Every play is graded, and none is dropped.
- **Payout, flat 1 unit:** a win pays 1 / price - 1, a loss pays -1, and a push or 0.5 resolution pays 0.
- **Price:** the one stored on the card at the cut.
  - A missing price, or one older than 30 minutes before the cut, is **unpriced**. It is listed but never enters ROI.
  - A sport whose unpriced share of counted moneyline locks is over 10% gets no verdict.
- **CLV:** the close from `data/pm_closes.json` minus the price at the cut. A close counts only when the event slug, market type,
  line and outcome list all match.
  - The result row is written as soon as the market resolves. The close is its own append-only row (`<key>|close`), written
    whenever the close shows up, however late. A play with no close row counts as "no close stored", and no close is estimated.
  - CFB has no stored closes, so it never gets a close row.
  - **Known gap:** `data/pm_closes.json` has no game after 2026-10-30, so no NBA or NFL play can get a CLV until that feed is
    fixed. The close rows will fill in once it is.
- **Data quality:** `data_quality` per sport gives the unpriced share of counted moneyline locks (variant A). Over 10% sets `fail`,
  which by the pre-registration means that sport gets no verdict.
- **Which cards count:** every row carries the card's `test.counts`. `cards_record.json` reads counted cards for the test, gives an
  `all_cards` line beside it, and lists the non-counting cards by reason.
- **Statistics:** bootstrap intervals, 10,000 resamples, seed 20261111. The file is `report_only` until the final read date.

**Files:**
- `pm_record/cards/<sport>/<YYYY-MM>.jsonl`: rows keyed `card|group|variant|play`.
- `pm_record/cards_record.json`: the read.
- `pm_record/markets.json`: resolved Gamma facts. A final result never changes, so only resolved markets are cached.

## 2. SharpFlow head-to-head (`scripts/benchmark_h2h.py`)

SharpFlow rewrites its public files about every 10 minutes, so its site never shows what it said at a given time. Its repo's commit
history does, so the archive is built from that.

| File | When | What |
|---|---|---|
| `benchmark/<sport>/<date>/<slug>@<gst>.json` | once the cut has passed | that game's entry in SharpFlow's three position files and its picks, from the last commit at or before our cut (no older than 2 hours) |
| `...@<gst>.final.json` | 12 hours after the start, or at 3 days if picks are still pending | SharpFlow's picks for the game from its current file |
| `benchmark/rows/<sport>/<YYYY-MM>.jsonl` | once the market resolves | each SharpFlow real play (units > 0, not cancelled, in the final file) |
| `h2h_record.json` | every run | per sport and market group: SharpFlow, Vault's shown size, Vault's counted lock, the same games, and by day |

- **The headline is what SharpFlow showed at our cut** (`set: at_cut`): every real play in the picks file public at the cut,
  graded at that file's units and `oddsLock` (American odds), by Polymarket's resolution. A play SharpFlow cancels later is still
  graded and flagged `cancelled_later`, so its record can't drop losers after the fact.
- **Plays added or sized up after the cut** are `set: after_cut`, reported on their own line.
- **Moneyline and total picks** map to exactly one market.
- **Spread picks** name only the team, not the line. The script guesses the rung (the one with the most SharpFlow-listed money on
  that team) and keeps that result as `res_mapped`, but gives no priced result: SharpFlow's price belongs to a line we can't see.
- **A game is skipped, not written, when Polymarket's API didn't answer for every market**, so an outage never writes a permanent
  "no market" row.
- **A cut is archived only once it is 30 minutes old,** so a commit pushed a little late is already on GitHub.
- **SharpFlow's own result and profit are kept beside each row** (`their_res`, `their_profit`). The record counts every row where
  the two results disagree.
- **What changed after the cut, on 2026-11-11:**
  - **Knicks moneyline:** 0 units at the cut, 1 unit in the final file, and it lost.
  - **Lakers-Bucks Under 230.5:** 1 unit at the cut, then cancelled, and it lost. SharpFlow's own record leaves it out.

## Known limits

- **Vault's frozen cards from 2026-11-11 predate the shown size,** so they have locks only.
- **Cards built before this change have no `sf.cid`.** They are matched in their keyframe by market type, line, side and stored
  price. With no single match the play is listed as `no_market`.
- **The archive needs SharpFlow's repo history.** If SharpFlow rewrote that history, a game not yet archived would be lost. The job
  runs every 2 hours to keep that window short.

## On the page

The Proven Sharps page (Sharp Money and the NBA page, `sharp-money/side-cards.js`) has a **Cards / Record** switch. Record reads
`cards_record.json`, `h2h_record.json` and this month's and last month's row files straight from `pm-holders-data`, and shows per sport:
progress toward the 300 counted moneyline locks, the lock and shown-size tables with CLV, cards not counted by reason, the
data-quality flag, SharpFlow graded the same way (with after-cut, cancelled and unpriced-spread counts), and the 20 most recent
games with both sides' plays and results. Locally, `?rec=/path/to/pm_record/` points it at a copy.

## Matching SharpFlow: which rule set shows

The goal is to match or beat SharpFlow's ROI. Card rules can't be judged on history: every backfill row comes from a wallet chosen
because it had already won, so any rule looks better than it is. They are judged forward, on the same games, against SharpFlow's
own at-cut plays:

| Rule set | Exclusions | On the card |
|---|---|---|
| `all` | Vault's hedger (25% both sides, 8+ markets) and churn (volume / PnL > 100) on every wallet | the shown size today |
| `sfx` | SharpFlow's published market-maker and trader list | shadow, graded beside it |

The head-to-head (`vault_shown_size`, `vault_sfx`, `benchmark`) and the Record page show all three. The shown size moves to
whichever Vault rule set is beating SharpFlow once both have a usable sample. That switch is a decision made with the user, not
automatic, and the pre-registered lock is unchanged either way.

## Open plays

`cards_record.json` and `h2h_record.json` each carry an `open` list: locked plays with no graded row yet (the game is not final or the
market has not resolved), from the last 7 days. Vault's list has the shown size (variant `all`) on every frozen card and the
pre-registered lock on counted cards; the benchmark's has its real plays as shown at our cut. The Record page adds Vault's live
suggested sizes from the live cards (games not yet locked) and shows them all under "Open plays", each with its status: locks at,
locked, or awaiting result. A play leaves the list once its row is graded. The benchmark's plays appear only after our lock, because
its picks are archived at the cut.

