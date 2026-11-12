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
  - A row waits up to 3 days for its close, then is written with `close_status: none_stored`.
  - CFB has no stored closes, so it is graded at once with `no_closes_for_sport`.
- **Which cards count:** every row carries the card's `test.counts`. `cards_record.json` reads counted cards for the test, gives an
  `all_cards` line beside it, and lists the non-counting cards by reason.
- **Statistics:** bootstrap intervals, 10,000 resamples, seed 20261111. The file is `report_only` until the final read date.

**Files:**
- `pm_record/cards/<sport>/<YYYY-MM>.jsonl`: rows keyed `card|group|variant|play`.
- `pm_record/cards_record.json`: the read.
- `pm_record/markets.json`: resolved Gamma facts. A final result never changes, so only resolved markets are cached.

## 2. SharpFlow head-to-head (`scripts/sharpflow_h2h.py`)

SharpFlow rewrites its public files about every 10 minutes, so its site never shows what it said at a given time. Its repo's commit
history does, so the archive is built from that.

| File | When | What |
|---|---|---|
| `sharpflow/<sport>/<date>/<slug>@<gst>.json` | once the cut has passed | that game's entry in SharpFlow's three position files and its picks, from the last commit at or before our cut (no older than 2 hours) |
| `...@<gst>.final.json` | 12 hours after the start, or at 3 days if picks are still pending | SharpFlow's picks for the game from its current file |
| `sharpflow/rows/<sport>/<YYYY-MM>.jsonl` | once the market resolves | each SharpFlow real play (units > 0, not cancelled, in the final file) |
| `h2h_record.json` | every run | per sport and market group: SharpFlow, Vault's shown size, Vault's counted lock, the same games, and by day |

- **SharpFlow plays are graded the same way as ours:** by Polymarket's resolution, at SharpFlow's own locked price (`oddsLock`,
  American odds).
  - **Moneyline and total picks** map to exactly one market.
  - **Spread picks** name only the team, so they map to the spread rung holding the most SharpFlow-listed money on that team
    (`map: most_money_rung`).
- **SharpFlow's own result and profit are kept beside each row** (`their_res`, `their_profit`). The record counts every row where
  the two results disagree.
- **`shown_at_cut` and `units_at_cut` show what SharpFlow displayed at our cut.** The archive keeps both versions, so a pick resized
  or cancelled after the cut is visible. On 2026-11-11 the Knicks moneyline was 0 units at the cut and 1 unit in the final file.

## Known limits

- **Vault's frozen cards from 2026-11-11 predate the shown size,** so they have locks only.
- **Cards built before this change have no `sf.cid`.** They are matched in their keyframe by market type, line, side and stored
  price. With no single match the play is listed as `no_market`.
- **The archive needs SharpFlow's repo history.** If SharpFlow rewrote that history, a game not yet archived would be lost. The job
  runs every 2 hours to keep that window short.
