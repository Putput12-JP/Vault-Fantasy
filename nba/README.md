# Vault NBA betting model

Separate from the NFL betting code. Plan: [docs/PLAN.md](docs/PLAN.md). What data we have: [docs/data-coverage.md](docs/data-coverage.md).

Free data only. Rebuild everything from scratch (all outputs land in `raw/`, which is gitignored):

```bash
python3 nba/scripts/fetch_hoopr.py                              # box scores + schedules, 2022-2026 (~2 min)
python3 nba/scripts/backfill_espn_odds.py 2025 2026             # ESPN game lines + props (~15 min, resumable)
python3 nba/scripts/backfill_kalshi.py                          # Kalshi props + game markets, pre-tip prices (~2.5 h, resumable)
nba/.venv/bin/python nba/scripts/fetch_injury_reports.py 2025 2026   # NBA injury PDFs (slow on purpose, resumable)
python3 nba/scripts/build_backtest_tables.py                    # join -> raw/tables/*.csv + docs/data-coverage.md
python3 nba/scripts/build_game_model.py                         # week 2: game model tune + walk-forward backtest (~3 min)
python3 nba/scripts/backfill_kalshi.py --am KXNBAGAME KXNBASPREAD KXNBATOTAL   # 1pm ET Kalshi prices (bet clock)
python3 nba/scripts/backtest_game_vs_kalshi.py                  # game model vs prices tradeable at 1pm
python3 nba/scripts/build_minutes_model.py                      # minutes model (~30 s)
python3 nba/scripts/build_usage_cascade.py                      # per-minute cascade when teammates sit (~20 s)
python3 nba/scripts/build_prop_model.py                         # week 3: prop model + backtest vs ESPN + Kalshi (~1 min)
python3 nba/scripts/fetch_depth_charts.py                       # CURRENT depth charts -> data/depth_charts.json (~15 s, run daily)
```

## Live snapshots (week 4, from 2026-09-30)

`scripts/snapshot.py` records every venue's pre-tip price and the injury report, change-only, and runs on
GitHub Actions (`.github/workflows/nba-snapshots.yml`): an hourly poll, and on game days a loop from 9am ET
to the last tip (every 15 min, every 5 min inside 3h of a tip). Output goes to the **`nba-data` branch**,
not main, under `snapshots/<ET date>/`. Read it with:

```bash
git fetch origin nba-data && git worktree add nba/raw/nba-data nba-data   # then git -C nba/raw/nba-data pull
python3 nba/scripts/snapshot.py --dir=nba/raw/snap_test --ahead-h=500     # one local poll, all upcoming games
```

Row format and what each source holds: the docstring at the top of `snapshot.py`. The price of a key at
time X is its last row at or before X; `polls.jsonl` says whether each source actually answered around X.

The injury script needs `pdfplumber`: `python3 -m venv nba/.venv && nba/.venv/bin/pip install pdfplumber`.

## Gotchas (learned the hard way, week 1)

- ESPN's site API 403s a `Mozilla/5.0` user agent that isn't a real browser; plain curl works. Action
  Network is the opposite (needs one). `snapshot.py` sets it per source.

- **ESPN blocks Python's urllib (403).** Scripts shell out to `curl`.
- **ESPN prop pages cap silently at 25 items** if `limit` is too large (2000). Use `limit=1000` and page.
- **ESPN props have no over/under label.** `build_backtest_tables.py` infers sides from the alt-line ladder
  (ESPN BET) or row order (DraftKings, over first) and audits them against results before writing.
  ESPN BET rows with no ladder (Oct to mid-Dec 2024) have random order and are dropped, not guessed.
- **Book 59 "ESPN Bet - Live Odds" is in-game.** Excluded everywhere.
- **ESPN's "current" prop value is usually after tip.** Every 2024-25 prop's `current` is post-tip; only `open`
  is a usable pre-game price there. `cur_is_pretip` flags the rows where current is a real pre-tip close.
- **The NBA injury CDN (Akamai) blocks bursts.** 8 parallel downloads got every file 403'd within ~40 files, for
  hours. The fetcher runs one request at a time with a pause and stops itself on a 403 streak.
- **Kalshi rate-limits parallel readers.** Per-worker backoff stalled the first run at ~2 markets/s; a shared pacer
  (`RATE_PER_S`) runs ~12/s. All 2025-26 markets live under `/historical/*` (cutoff 2026-07-31).
- **ESPN depth charts lag the roster.** They miss new signings and keep departed players (80 unslotted,
  8 stale on 2026-09-29). `fetch_depth_charts.py` treats the roster as truth and the depth chart as order only.
- **Draft picks use prospect ids, not NBA athlete ids.** Joined by name; 54 of 60 2026 picks match a roster
  (the rest are unsigned or stashed overseas).
- **Injury report names glue suffixes on** ("LivelyII,Dereck", "PorterJr.,Kevin"). `nba_common.name_key` strips
  them; before that fix 45k report rows failed to match, including real rotation players.
- **ESPN's opening line has no timestamp.** The game model "beats" it (56-59% ATS at 4+ pts) mostly because the
  open predates the injury news. Only Kalshi's 1pm tape is an honest bet-time price.
- **ESPN "main" prop pairs can hold garbage prices** (a mis-paired alt, a half-updated row). Without the vig filter
  (both sides sum to 100-115%) the backtest showed "+67% ROI on 54% wins". Keep the filter.
- **Kalshi player-prop YES is overpriced in every bucket** (retail buys overs). Any Kalshi prop "edge" must beat the
  price-only baseline, or it is just the bias. `build_prop_model.py` reports both.
- **Per-game-weighted ROI flatters cheap long-shot contracts.** Quote per-contract ROI for money; per-game only for z.
- **Kalshi combo series (PRA, PR, PA, RA) have no 2025-26 history.** Only PTS, REB, AST, 3PT.
