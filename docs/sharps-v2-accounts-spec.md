# Sharps V2: account data spec (Following page, `wallets.json`)

Written 2026-11-21. Planner spec for the V2 account fields. Sources: the accounts audit of 2026-11-21 (measured on the 10:21 AM CT
build), `scripts/build_side_cards.py`, `scripts/pm_clv_tiers.py`, `scripts/rank_pm_wallets.py`, `sharp-money/following.js` (v=13),
`docs/side-cards.md` ("Wallets file"), `docs/sharps-audit-2026-11-18.md`, `docs/sharp-shadow-rules-nov16.md`.

Sharp money is context only. Nothing in this file is a bet signal, a size, a pick or an input to Top Reads, SM_GATE or any agree
total. Every number below is a stored field, a count of stored rows, or arithmetic on stored fields. All times Central.

## 0. Compatibility contract

- **Additive only.** No existing key in `wallets.json` is renamed, removed or retyped: top level `built`, `v`, `context_only`,
  `floor_usd`, `floor_usd_by_sport`, `tier_rule`, `proven_rule`, `note`, `sports`; per wallet `name`, `w_`, `l_`, `n`, `roi`,
  `l30_roi`, `pnl`, `usual`, `clv`, `dive`, `legs`, `positions`, `l30`, `d30`, `odds`, `curve`, `sc`, `rk` (`tier`, `n`, `mean`, `p`);
  per position every key listed in `docs/side-cards.md`. `following.js?v=13` reads exactly these (`index()`, line 192) and must
  render the V2 file unchanged.
- `legs` keeps its 20 cap and its meaning. `sc` keeps its any-sport meaning. `rk.mean` stays the raw mean. `usual` stays the mean.
- Classic iterates every key under `sports.<sport>`, so wallets that are not on the current list (retained, section 2.L) go under a
  **new top-level key** `retained`, never under `sports`.
- `v` goes from `1` to `2`. A new top-level `v2_fields` string names the added keys (for a reader to check before use).

## 1. Tier vocabulary (per wallet x sport)

The tier is `rk.tier` from `pm_clv_tiers.fit()` as of the build, unchanged. No new threshold: these are the module's own constants
(`MIN_N = 30`, `P_SHARP = 0.95`, `P_DULL = 0.05`, `MIN_RANKED = 5`, `MIN_WALLETS = 30`, entry price kept only inside `.02 < avg < .98`),
set before its walk-forward and not tuned. Tiers exist in NBA and NFL only (`sf_tiers.TIER_SPORTS`).

| V2 tier (`v2.tier`) | Rule | Page words |
|---|---|---|
| `beats` "Beats the close" | `rk.tier == "sharp"`: CLV games n >= 30 and P(mu > 0) >= 0.95 | "Beats the closing price, N games" |
| `even` "Even with the close" | `rk.tier == "mid"`: n >= 30, 0.05 < P(mu > 0) < 0.95 | "No clear price edge, N games" |
| `loses` "Loses to the close" | `rk.tier == "dull"`: n >= 30, P(mu > 0) <= 0.05 | "Buys worse than the close, N games" |
| `few` "Too few closing prices" | `rk.tier == "thin"` (n < 30), or `rk` null (no CLV game, a fit with params None, or CFB/CBB) | "Too few closing prices to judge (N)" with N = `rk.n` or 0 |

The scorecard list (`data/pm_wallets*.json`, its own rule: min 5 games, t >= 3) is **not** folded into the tier, because its cut
points are not the `pm_clv_tiers` ones. It shows as its own chip, own sport only (field `sc_sport`, 2.I).

Muted chips (grey, never green, never a tier, never in a sort's first key):

| Chip | Rule | Words |
|---|---|---|
| Past winner | `n >= 6`, win rate >= 55%, dollar ROI > 3% on variant `all` at `now` (`PROVEN_N`, `PROVEN_WR`, `PROVEN_ROI`, unchanged) | "Past winner, picked after the fact" |
| Inactive | `n30_games == 0` (2.F) | "No bets in 30 days" |
| On the price scorecard | `sc_sport` true | "On the {SPORT} price scorecard, N games" (N = `sc_n`) |

Sort for V2 (UI, recorded so it is testable): tier order `beats`, `even`, `few`, `loses`; inside a tier by `rk.post` descending,
nulls last. `loses` sorts last (fixes audit bug 11).

## 2. New additive fields

All are written by `build_side_cards.py` in the `--wallets-out` block (lines 1218 to 1236), computed from `fl.stats(w, now)` for
**every** listed wallet (today an open wallet's book is taken at its first game's cut, audit bug 14; the new fields never are).
"Stored only" means no number is estimated, imputed or taken from a model.

| # | Key (per wallet unless noted) | Definition | Stored inputs | Stored only |
|---|---|---|---|---|
| A | `rk.post`, `rk.sd` (added inside `rk`) | Shrunk CLV estimate (posterior mean) and its posterior sd, in price units (x100 = cents). Already computed at `pm_clv_tiers.py:91`, dropped at `build_side_cards.py:1235`. | ledger `avg`, stored closes (T-15 keyframes, `pm_closes.json`) | Yes |
| B | `v2.tier` | `beats` / `even` / `loses` / `few` per section 1 | `rk.tier` | Yes |
| C | `flat_roi` | Mean of pnl / stake over cash positions with stake > 0, variant `all` (`book()["flat_roi"]`, line 399) | ledger `stake`, `pnl` | Yes |
| D | `fwd` | Forward-only book since Vault started tracking: `{w, l, p, n, pnl, roi, flat_roi, clv_n, clv_mean}` from `stats()["fwd"]` (rows with `src == "forward"`, non-hedged), same formulas as the `all` book. **Definition: a row counts when it settled at or after the wallet's `first_seen`; the bet may have been placed before it** (open when tracking began). Not look-ahead on a result; stated so the sample is read correctly. Nov 21: listed wallets' forward non-hedged rows with a first fill before `first_seen`: NBA 140 of 2,010 (33 wallets), NFL 81 of 517 (16), CFB 23 of 398 (7), CBB 38 of 594 (7). | ledger rows, `src`, `first_seen.json` | Yes |
| E | `first_seen` | Epoch the wallet first entered the ledger universe (`ledger.first_seen[w]`; CBB follow-only wallets from `follow_only.json`). A wallet in both files publishes the **earlier** date, the one `build_pm_ledger` stamped `src` with, so the date and the forward rows agree (the stats and cuts keep reading the registered date, so no V1 number moves). | `first_seen.json`, `follow_only.json` | Yes |
| F | `last_settled`, `n30_games` | Latest `settled_at` over the wallet's positions (any result, variant `all`); count of distinct games (`ev`) with a decided position settled in `[now - 30 d, now)` | ledger `settled_at`, `markets` slug | Yes |
| G | `usual_med` | Median stake (cost) of cash positions (not split, stake > 0) with stake >= the sport floor ($250, CBB $100), variant `all`. Null when none. | ledger `stake` | Yes |
| H | per position: `side_usd`, `side_rungs`, `side_press` | For the wallet's group (`ev`, `gst`, `g`, `side`): sum of `usd` over every listed rung, the rung count, and `side_usd / usual_med` (null when `usual_med` null). Same value on each rung of the side. Labelled "mark value over median cost". | position `usd` (shares x scan price), G | Yes |
| I | `sc_sport`, `sc_n` | On the scorecard's `sharp` list for **this** sport; `sc_n` = that file's `wallets[w][0]` (games), null if absent | `data/pm_wallets*.json` | Yes |
| J | per position: `px_age_min` | `round((built - px_t) / 60)`: minutes since the price shown was logged. Null when `px_t` null. | position `px_t`, `built` | Yes |
| K | `since.json` (separate file), top-level `since_from`, `since_file` | Dated settled positions for "Since you followed": every non-hedged position at or above the sport floor settled in `[since_from, built)`, `since_from = built - 60 d`, newest first, each `[settled_at, first_fill, r, flat, ev, stake]`: `r` 1 win, 0 loss, 2 push; `first_fill` = min ledger `first` over the position's rows (so a page can drop bets placed before the follow); `flat` = round(pnl / stake, 3), null for a split position; `ev` the game; `stake` whole dollars. **The unit is a position** (a spread and a moneyline on one game are two items): `ev` and `stake` let a page tally games the way `legs` does (one result per game, the biggest position) and call the position count "bets". Replaces `legs` for this use only. Kept out of `wallets.json` for the size budget. | ledger `settled_at`, `first`, `stake`, `pnl`, `split` | Yes |
| L | top-level `retained.<sport>.<wallet>` | A wallet listed in `sports.<sport>` at some build in the last 60 days that no longer qualifies: `{retained: true, left_at, name, name_disp, first_seen, fwd, last_settled, n30_games, v2, rk}`, no `positions`, no list (its dated list is under `retained` in `since.json`). Dropped 60 days after `left_at`. | previous published `wallets.json` (`--prev-wallets`, passed by the workflow), ledger | Yes |
| M | `name_disp`, `name_src` | Display name: `name` when non-null and not hex-like (`^0x[0-9a-fA-F]{20,}`, the `shortName` test); else the newest non-null, non-hex name for the wallet in **any** `universe/*.json` snapshot or keyframe `names`; else `"Unnamed " + w[0:6] + "..." + w[-4:]`. `name_src` = `universe`, `keyframe` or `none`. | `universe/*.json`, keyframe `names` | Yes |
| N | `exp_w`, `luck_p` | Price-implied expected wins over decided positions and P(wins >= actual) (already `dive.exp_w`, `dive.all[5]`); surfaced at top level for the sheet | ledger `avg` per position | Yes |

Size budget. Old file 946 KB (Nov 21 10:21 AM build, 712 rows). **Budget: new fields at most 400 KB, whole `wallets.json` at most 1,350 KB**,
`retained` included. The first plan (K as `since_list` inside the wallets file, 60 days) measured, on the Nov 21 inputs: 1,607 KB whole, 660 KB
new (`since_list` 364 KB: 300.6 KB under `sports` over 9,167 positions plus 63.4 KB under `retained`; `retained` 108 KB in all; `fwd` 70 KB;
the rest under 21 KB each). The planned first cut (window 60 to 45 days) saves only about 47 KB and still leaves about 1,560 KB, so it
does not work; the spec's own estimate had left `retained` out. **Plan that fits (measured): K moves to `since.json`, published beside
`wallets.json`.** Result: wallets file **1,242 KB, new fields 295 KB**, inside both budgets; `since.json` 711 KB, not budgeted because the classic
page (which re-reads `wallets.json` every 2 minutes) never fetches it. The budget is enforced: the build exits 3 over budget and the pm-cards
workflow runs `scripts/sharps_v2/check_size.py live/wallets.json` before its publish step, so an over-budget file never reaches
`pm-cards-live`; `SHARPS_V2_WALLETS=file python3 -m unittest tests.test_sharps_v2_wallets` runs the same check as a test. If `since.json`
grows too large later, the cuts in order are: window 60 to 45 days (about 14 percent), then times as offsets from `since_from`.

### Deferred (needs data we do not store)

| Item | Why not now | New collection it needs |
|---|---|---|
| Entry price of an open position | The holders scan reads `/holders` (shares only). `px_first` is the market at first sight, not a cost; it must never stand in. | Fetch the wallet's trades for open markets and compute `avg = cost / shares` the way `build_pm_ledger.py:265` does; store as `entry_avg`, `entry_t` per position |
| Price tier for CFB and CBB | No tested CLV model there (`TIER_SPORTS = nba, nfl`); the card's college `rk` is untested | A registered walk-forward of `pm_clv_tiers` on college closes before any college tier is shown |
| "Since you followed" before `since_from` | List covers 60 days | A per-wallet forward list on a history branch (append-only), if follows older than 60 days matter |
| Per-follow tombstones keyed to a user | Follows live in the viewer's localStorage; the build cannot see them, so L retains every leaver | A server-side follow store (not planned) |
| Any expected ROI from following | Not a stored quantity | None; out of scope by rule |

## 3. Historical data plan (CLAUDE.md: fix history, not only new rows)

`wallets.json` is a snapshot rebuilt every 10 minutes from the ledger (`sharp-history`, append-only) and force-pushed to `pm-cards-live`.
So nearly all history is fixed by recomputation:

**Recomputed on every build, over all history:**
- A, B: refit at `now` from every stored close (unchanged fit; only more keys published).
- C, D, F, G, N: from every ledger row. D covers each wallet's rows settled at or after its own `first_seen` (earliest universe entry 2026-11-11 9:54 AM CT,
  epoch 1794412455; a wallet in both `first_seen.json` and `follow_only.json` publishes the earlier date, the one `src` was stamped with). No
  row settled before a wallet's published `first_seen` is counted as forward (`src` is set by `build_pm_ledger.py:269` and not touched). A
  bet placed before `first_seen` and settled after it does count (see D).
- K: the full 60-day window, so every follow made in the last 60 days is re-tallied correctly on the first V2 build (no survivorship,
  floor applied, bets placed before the follow excluded via `first_fill`).
- M: from every stored universe snapshot.
- The existing book keys of open wallets move from "first game's cut" to `now` (bug 14). Only `l30`, `l30_roi`, `d30`, `curve` can move
  (their 30-day window); `n`, `w_`, `l_`, `roi`, `pnl` cannot (nothing settles between now and a future cut).

**One-time backfill:** L. On the first V2 build (no `--prev-wallets` with V2 keys), seed `retained` by replaying the listing rule
(proven, or `rk.tier == sharp` as of that cut, not excluded; the scorecard list is not replayed: no earlier copy is stored and today's list would be look-ahead) at each daily 12:00 AM CT cut over the prior 60 days with
`fl.stats(w, cut)` and `fl.clv_tiers(cut)` (point in time: rows settled before the cut, closes of games started before it). A wallet listed
at any of those cuts and not now gets `left_at` = the first cut after its last listed cut. After that, `left_at` carries forward from the
previous published file.

**Not touched:** the ledger rows and `first_seen.json`; frozen cards and `live.json`; the side-card record, the pre-registered tests
(`docs/sharp-card-prereg*.md`) and the Nov 16 shadow rules; `pm_clv_tiers` constants; the scorecard files; the classic page.

**The 2026-11-16 12:00 AM CT cutoff** (epoch 1794808800) is the shadow rules' `in_sample` line for card plays
(`docs/sharp-shadow-rules-nov16.md`). It is **not** the wallet forward cutoff and no V2 account field uses it: a wallet's forward record
starts at its own `first_seen` (ledger `src`). The spec states this so the two are never mixed on the page.

## 4. Old and new numbers to report (PR, Model/data and UI)

Measure old on `scratchpad/wallets.json` (built 2026-11-21 10:21 AM CT) and new on a V2 build run against the same ledger commit, holders
state and closes (pin `now` to 1795278075).

| Visible number | Old | New |
|---|---|---|
| CLV line on a tiered row | `rk.mean * 100` (raw, labelled "shrunk") on 85 rows | `rk.post * 100`; report the median and max of abs(post - mean) in cents per sport |
| Tier tags | price-sharp 31, mid 27, dull 27, thin 172, none 455 | Beats 31, Even 27, Loses 27, Too few 627; must match exactly (same fit) |
| Scorecard tag | `sc` true on 28 rows (6 from another sport) | `sc_sport` true rows per sport (expect 22) |
| "Hot" | 668 rows labelled hot | 668 "Past winner" chips (same rule, at `now`); report any count change from bug 14 |
| Inactive | not shown; 406 rows with no game in 30 d, 322 none in 180 d | `n30_games == 0` count per sport (expect 406) |
| Usual stake | mean cost, median across rows $2,293, range $2 to $358,487 | `usual_med` median across rows, and rows where usual_med vs usual differ by over 2x |
| x usual | per rung; 23 multi-rung sides, max side 8.1x as the sum of rung presses | `side_press` per side; report the 23 sides old max rung vs new side value |
| Price "now" | no age shown; 57 positions over 6 h, 15 over 24 h | `px_age_min` distribution; the same 57 and 15 counts |
| Since you followed | `legs`, 20 cap, any size, follow-out wallets dropped | `since.json`: for synthetic follows at 2026-11-11 12:00 AM CT and at `built - 14 d`, old W-L in games vs new W-L in games (the same unit), the new list also counted in bets (positions) with flat units, per sport; count of wallets where the cap or floor changes the game tally |
| Retained | 0 | `retained` rows per sport and the follow-out wallets the old tally dropped |
| Names | 347 of 712 render as hex (296 null, 51 hex) | `name_src == none` count |
| Forward record | not shown | rows with `fwd.n > 0` per sport (about 210 of 712 on Nov 21 ledger, NBA 97, NFL 60, CFB 32, CBB 21) and their summed n |
| Flat ROI | not shown | `flat_roi` beside `roi` per tier; median per tier per sport |
| 30-day block (open wallets) | `l30` at first game's cut | `l30` at `now`; rows whose W-L changed |
| File size | 946 KB | V2 total and the new-field share; at most 1,350 KB and 400 KB (since.json reported, not budgeted) |

Close monitoring (house rule): every wallet or slice whose shown record **improves** under V2 is listed in the PR, one line each, with its own
sample size and n under 30 marked a small sample: forward records above the wallet's all-time dollar ROI; flat ROI above dollar ROI;
since-you-followed tallies (old legs against the new per-game tally, for each synthetic follow); retained rows; open wallets whose 30-day
block improves under the read at `now`. A name now shown is a label and is counted, not listed. `compare_wallets.py` section D prints all of
these. Forward records start 2026-11-11 at the earliest, so every `fwd` record is young; the script prints the measured age of the oldest.

## 5. Tests

- Classic contract: load the V2 file in `following.js?v=13`; directory row count, feed and sheet render the same as on the V1 file
  built from the same inputs.
- `rk.tier`, `n`, `mean`, `p` byte-identical V1 vs V2; `v2.tier` mapping per section 1 on every row.
- K: no item below the floor, none outside `[since_from, built)`, none hedged; `flat` null exactly on split positions; the floor, the window ends and the 30-day edge are boundary-tested (floor and `since_from` in, `built` out); `since_list` is a position list and `games_tally` collapses it to one result per game.
- E: a wallet in both `follow_only.json` and `first_seen.json` publishes the earlier date and never has a forward row settled before it.
- H: `side_usd` equals the sum of its rungs' `usd`; rungs of one side carry the same `side_press`.
- M: no `name_disp` is null; hex-like names never pass through.
- L: no `retained` wallet is also in `sports`; none older than 60 days from `left_at`; seeding is point in time (a unit test with a
  wallet that becomes proven only after a cut is never retained for that cut).
- Size: whole file at most 1,350 KB and new fields at most 400 KB on the Nov 21 inputs; the build exits 3 over budget and the workflow gate (`check_size.py`) stops the publish; the same check runs as a test when `SHARPS_V2_WALLETS` points at a built file.
