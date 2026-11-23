# Sharps V2: market-move flags and the play write-up card (spec)

**Status: SPEC ONLY, nothing built.** Written 2026-11-23 (Central). Rule id for everything below: **`v2f-1`**. A change to any
threshold, window or branch after the registering commit is a new rule id (`v2f-2`) and a new registration.

Source request (the user, 2026-11-23): flag Sharps plays when (1) Pinnacle's price moved (example +105 to about -129), (2) Pinnacle's
limit climbed (example about $1.1K to $1.45K), (3) the whole market moved the number (example Cornell +22 to about +19, BookMaker
touching +18.5), and (4) show a short write-up card per play modelled on a "Why I took the Nuggets" card.

The Cornell example is not new to this repo: it is the origin of `docs/stale-number-prereg.md` (registered 2026-11-19, live as the
"Stale number" tag since the same day). This spec reuses that rule's pieces, `scripts/steam_record.py`'s price-move definition and
`scripts/sf_signals.py`'s limit read instead of writing new rules under new names (section 1.6).

Every number in this file was measured with Python stdlib on these inputs, all read 2026-11-23 about 1:20 PM CT:

| Input | Ref |
|---|---|
| Book tape | `data/book_tape/<sport>/<YYYY-MM>.jsonl` at `origin/main` 93458fee |
| Frozen cards and graded record | `origin/pm-holders-data` dff069af (`pm_cards/<sport>/frozen`, `pm_record/cards/<sport>/2026-11.jsonl`) |
| Live slate | `origin/pm-cards-live:live.json`, built 1:17 PM CT (1,415 KB compact; V2 keys 79.7 KB) |

The measuring scripts are not committed by this spec; build task T1 commits them as `scripts/sharps_v2/flag_history.py`.

---

## 0. What data exists and what does not

### 0.1 The book tape (per book, per market, timestamped)

`scripts/book_tape.py` (NFL, sources Action Network, Pinnacle guest API, Novig, Kalshi) and `scripts/sharp_tape.py` (CFB, NBA, CBB, read
from the sharp-data `data.json` that `scripts/fetch-sharp-money.mjs` writes) append one row per book **only when that book's numbers
change**. Runs ride `update-sharp-money.yml` (cron every 10 minutes) and `nfl-book-tape.yml`.

Row: `{t, src, gk?, book, away, home, start, ml:[away,home], sp:[home line, home price, away price], tot:[line, over, under],
lim:[ml, sp, tot] (Pinnacle only), px / nsp / ntot (Novig, Kalshi)}`. `t` is the fetch time of the run that saw the change, so it is
the time of the **last change**, not the last check.

| Sport | Forward tape from (CT) | Books with prices and lines | Pinnacle rows | Pinnacle rows carrying `lim` |
|---|---|---|---|---|
| NFL | 2026-10-01 | Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365, Consensus, Open (+ Novig, Kalshi exchange quotes) | 1,727 | 1,194 (all Pinnacle rows since limits were added) |
| CFB | 2026-10-17 | same set | 7,711 | 7,711 |
| NBA | 2026-10-17 | same set | 5,110 | 5,110 |
| CBB | **2026-11-19** | same set | 1,675 | 1,675 |

Backfill rows (`backfill.jsonl`, `bf: 1`) carry no prices and are never read here.

**Books that are NOT stored:** BookMaker, Circa, Fanatics, Caesars. BookMaker and Circa exist only in the local SmartStake tape
(`scripts/smartstake_to_book_tape.py`), whose terms forbid publishing or showing them: they can never appear on this page. Fanatics
(Action Network book id 2988) and Caesars (123) are fetched for NBA props only (`nba/scripts/snapshot.py`), not for game lines.
The "most extreme book" in this spec is therefore the most extreme of the five US books and Pinnacle. Adding Fanatics and Caesars to the
game tape is decision D4 (section 5).

### 0.2 Pinnacle limits: STORED

Limits are stored. `book_tape.py` and `sharp_tape.py` write Pinnacle's `limits[0].amount` (the maximum stake on that market) as
`lim: [ml, sp, tot]`, and a limit change alone writes a new row. Every frozen card already carries the read at its cut:
`markets[g].sf.all.signals.limit = {open, now, rising, falling, tested, rows, why}` (`scripts/sf_signals.py` `limit_read`, rising =
up $500 or more, or to 1.45x or more, from the first tape row to the cut). So flag 2 is **not deferred**. What the data says about it
is in 1.3 and changes how it should be shown.

### 0.3 Existing definitions this spec reuses (no duplicates)

| Existing | Where | What it is | Used here as |
|---|---|---|---|
| Steam read | `sf_rungs.py` `steam_read`, stored as `sf.all.steam` | Pinnacle decimal price shorten of 3% (gold 4.5% in the last hour) or main line walk of 0.5 toward the side, first tape row to cut. **A ladder input** (STEAM-C, STEAM-S rungs). | Not reused for Flag A on purpose: it feeds the SharpFlow size ladder, and these flags must never touch a size. Flag A uses the steam record's definition instead (next row). |
| Steam record signal | `scripts/steam_record.py` | Pinnacle no-vig fair for the side rises by T points against its earliest stored quote in the previous 24 hours **at the same line**; a line change is skipped. T = 1, 2, 3. Context only, graded. | **Flag A** definition, with T set per sport and market from the data (1.2). |
| Limit read | `sf_signals.py` `limit_read`, stored as `sf.all.signals.limit` | first tape limit to the limit at the cut; rising at +$500 or 1.45x | **Flag B** read, unchanged. |
| Stale-number conditions 1 and 2 | `docs/stale-number-prereg.md` | Pinnacle moved the number by T points and at least 2 other books moved the same direction by 1 point or more | **Flag C** definition for spreads and totals, over a 24-hour window ending at the cut instead of a 90-minute event window, T per sport and market from the data (1.4). Condition 3 (a soft book lags) is not part of Flag C; the existing "Stale number" tag keeps showing that. |
| Price vs fair | `sf_signals.py` `ev_read`, `v2.vs_fair` | Polymarket price at the cut against Pinnacle no-vig fair at the cut | the "line / fair" tile and the prereg primary metric's close side |

### 0.4 The verdicts already on file (why these are context only)

- `scripts/steam_record.py` (`data/steam_record.json`, T = 1): after Pinnacle's price moves, it does **not** keep going (mean continuation to
  the close NFL -0.12 pts, n=246; CFB -0.56, n=647; NBA -0.11, n=475), and a soft book's price at that moment is worse than the close
  (CLV NFL -1.33, CFB -1.22, NBA -1.06 pts). With the limit up, the same: NBA continuation -0.34 (n=287), CLV -1.37.
- Steam Chaser NBA backtest Phase 1: NO-GO (PR 308); the engine (PR 311) and page (PR 312) were built as context only.
- Stale number (2026-11-19): "not proven" (56 of the 100 games the pass rule needs at T = 2).
- `docs/sharps-audit-2026-11-18.md`: the proven-sharps ladder and label did not predict results forward.

So no flag below may be worded as confirmation. They describe **what the market did**.

---

## 1. Flag definitions (rule `v2f-1`)

### 1.1 Common rules

- **Who gets flags:** only market groups with a shown play (`v2.side` set). Not every market of every game (size, 3.1).
- **As of:** `asof` = the card's cut (game start minus 15 minutes) on a frozen card, the build time on a live card. Only tape rows with
  `t <= asof` are read. Nothing after the cut ever enters a frozen card or the history.
- **Window:** the 24 hours ending at `asof` (`window_min: 1440`), the same window `steam_record.py` and `sharp_tape.py`'s `pp` use. The
  "from" value of a book is its first stored row inside the window; when it has no row inside the window, its last row before the
  window (the number it was hanging when the window opened). Hours actually covered are reported as `span_min`.
- **Side mapping:** `build_side_cards.side_norms` (home, away, over, under). An unmapped side gives null flags with `why: "side_unmapped"`.
- **Direction words:** **toward** = the move makes the play's side cost more (Pinnacle's fair for the side went up; the side's spread
  shrank, for example Cornell +22 to +19 or a favourite -3 to -4; a total went up for an over or down for an under). **away** = the
  opposite. **quiet** = readable, under the threshold. **null** = not readable (never 0, never "quiet").
- **Fair** = the two-way multiplicative no-vig (`mine / (mine + other)`), the formula `sf_signals.ev_read` already uses. Points =
  fair x 100.
- **Staleness.** The tape is change-only, so a row's age is not staleness (live NBA plays at 1:17 PM CT had a last Pinnacle change a
  median 309 minutes old, with the feed running). Staleness comes from the per-source heartbeat `seen` in
  `data/exchange_edge_live.json` (`scripts/sharp_tape.py` `heartbeat`; NFL: the newest `t` in `data/book_tape/nfl/last.json`
  for the source). A source whose heartbeat is more than **30 minutes** older than `asof` (the freshness limit the stale-number rule
  registered) is unreadable: Pinnacle stale makes A and C null with `why: "pinnacle_feed_stale"`; US books stale makes C null with
  `why: "books_feed_stale"`. The heartbeat age at `asof` is stored (`src_age_min`). History rows (built from old tape) have no
  stored heartbeat, so they carry `src_age_min: null` and are read as written.
- **No count of flags.** The page never shows "2 of 3", "all three", a score, or any sum. Each flag stands alone.

### 1.2 Flag A: "Pinnacle's price moved" (toward or away from the side)

Rule (the `steam_record.py` signal, evaluated once at `asof`):

1. Pinnacle rows for the market with `t <= asof`; at least **2** such rows in all, and the last one is `now`.
2. Moneyline: the window's first row is `from`. Spread or total: `from` is the window's first row **at the same main line as `now`**
   (a line change is not a price move; it belongs to Flag C).
3. `pin_move_pts = (fair_now - fair_from) x 100` for the side. State: toward if `pin_move_pts >= T_A`, away if `<= -T_A`, else quiet.

Null when: fewer than 2 Pinnacle rows before `asof` (`why: "no_pinnacle_history"`), no Pinnacle row at all (`"no_tape_rows_for_game"`),
unmapped side, or stale feed.

**Distribution (all games in the tape that have started, home or over side, 24-hour window ending 15 minutes before start, absolute
points of no-vig fair):**

| Sport, market | n | median | p75 | p80 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| NBA moneyline | 248 | 1.84 | 3.46 | 4.16 | 5.94 | 8.64 | 13.59 |
| NBA spread (fixed line) | 248 | 0.70 | 1.16 | 1.39 | 1.74 | 2.08 | 2.78 |
| NBA total (fixed line) | 248 | 0.68 | 1.37 | 1.55 | 1.94 | 2.28 | 2.68 |
| NFL moneyline | 116 | 0.74 | 1.29 | 1.47 | 2.00 | 2.35 | 3.35 |
| NFL spread | 116 | 0.67 | 1.32 | 1.39 | 1.69 | 2.40 | 2.87 |
| NFL total | 116 | 0.24 | 0.90 | 1.11 | 1.65 | 2.17 | 2.71 |
| CBB moneyline | 140 | 1.24 | 2.52 | 2.97 | 3.67 | 4.44 | 5.19 |
| CBB spread | 167 | 0.77 | 1.20 | 1.34 | 1.88 | 2.40 | 2.92 |
| CBB total | 167 | 0.43 | 0.97 | 1.09 | 1.66 | 2.20 | 3.38 |
| CFB moneyline | 331 | 0.82 | 1.81 | 2.17 | 2.92 | 3.89 | 5.53 |
| CFB spread | 337 | 0.47 | 1.13 | 1.37 | 1.83 | 2.19 | 3.04 |
| CFB total | 337 | 0.45 | 1.11 | 1.34 | 1.66 | 2.03 | 2.84 |

On the graded plays (signed toward the play side, so the median says which way the market went on Sharps picks): NBA median -0.66
(n=58), NFL 0.00 (n=33), CBB +0.22 (n=7), CFB +0.27 (n=46). Sharps plays are not, on the median, sides Pinnacle was moving toward.

**Threshold `T_A`:** the 80th percentile of the absolute move for the sport and market, rounded to the nearest 0.5 point. It marks
roughly the largest fifth of moves in either direction (measured fire rate 15% to 24%), so about one play in ten is "toward".

| T_A (points) | Moneyline | Spread | Total |
|---|---|---|---|
| NBA | 4.0 | 1.5 | 1.5 |
| NFL | 1.5 | 1.5 | 1.0 |
| CBB | 3.0 | 1.5 | 1.0 |
| CFB | 2.0 | 1.5 | 1.5 |

**The user's example as a reference:** +105 to -129 is 48.8% to 56.3% raw implied, **+7.5 points** (the request said about 6.7; the
no-vig figure needs the other side's price, which the screenshot does not show). That is above p95 in every sport and market except
NBA moneylines (p95 8.6), so it would show as "toward" everywhere.

### 1.3 Flag B: "Pinnacle's limit" (a fact about the market, not a side)

Read: `sf_signals.limit_read` at `asof`, unchanged (`open` = the first stored limit for the market group, `now` = the last at or
before `asof`, `rising` = +$500 or 1.45x). Stored also: `pct = (now / open - 1) x 100`. Null when no row before `asof` carries a limit
(`why: "no_limit_before_cut"`).

**What the data shows: Pinnacle raises limits on a schedule as the start nears, on nearly every market.**

| Sport | Markets | Limit at the cut / first stored limit, median | Share that rose at all | Share at +32% or more (the example) | Median limit by hours before start, moneyline (>24h, 12-24h, 4-12h, 1-4h, <1h) |
|---|---|---|---|---|---|
| NBA | 744 | 6.67x | 99% | 99% | $1,800, $1,800, $5,000, $12,000, $12,000 |
| NFL | 252 | 6.67x | 98% | 98% | $10,000, $20,000, $20,000, $50,000, $75,000 |
| CBB | 474 | 2.00x | 97% | 97% | $500, $1,000, $1,500, $3,000, $3,000 |
| CFB | 1,005 | 10.0x | 96% | 96% | $1,500, $3,000, $5,000, $5,000, $6,000 |

Even inside the last 4 hours before the cut the limit rose on 51% (NBA), 64% (NFL), 18% (CBB) and 49% (CFB) of markets. On the graded
plays `rising` is true on 98 of the 100 shown plays that have a limit read (NBA 57 of 58, NFL 33 of 33, CBB 8 of 9; CFB 46 of 46). The
user's example (+$350, +32%) does **not** meet the existing rising rule and is smaller than the normal ramp.

Two more facts: a limit belongs to the **market**, not to a side, so it can never point toward or away from the play; and
`steam_record.py` found that a price move with the limit up did not keep going either (NBA continuation -0.34, n=287).

**Therefore Flag B is shown as a fact line, never as an on/off chip:** "Pinnacle limit $3,000 to $20,000 in the last 24 hours. Pinnacle
raises limits toward start on almost every game (99% of NBA markets this season)." The share is the stored sport share above,
recomputed by T1 and published in `v2_plays.flags.limit_schedule_share`. A "limit raised ahead of schedule" chip would need a fitted
schedule (sport x market x hours to start) and its own registration: **deferred**, decision D1.

### 1.4 Flag C: "The market moved the number" (spreads and totals) / "The books moved the price" (moneylines)

**Spread and total** (stale-number conditions 1 and 2, at `asof`, 24-hour window):

1. Pinnacle's main line for the side moved by `T_C` points or more from `from` to `now` (direction words as in 1.1).
2. At least **2** of the five US books (DraftKings, FanDuel, BetMGM, BetRivers, bet365) moved their own main line by **1 point or more
   in the same direction** over the same window.
3. State toward or away when both hold; quiet otherwise. Null when Pinnacle has no row or fewer than 2 US books have a row before
   `asof` (`why: "too_few_books"`), or a feed is stale.

Stored for display: Pinnacle `from` and `to`, every readable book's `from` and `to`, `books` (readable), `same_way` (books that moved 1
point or more the same way as Pinnacle), and `extreme` = the book (Pinnacle or US) whose line at `asof` is furthest in the move's
direction, ties to the earliest timestamp. Consensus and Open rows are never counted.

**Moneyline** (no line exists, so the books' price): at least 2 of the five US books moved their no-vig fair for the side by `T_A`
(the moneyline value for the sport) or more in one direction, and none moved that far the other way. Display: each book's American
price from and to; `extreme` = the book with the largest move.

**Distribution, Pinnacle main line move, absolute points (same games as 1.2):**

| Sport, market | median | p75 | p80 | p90 | p95 | share with no move |
|---|---|---|---|---|---|---|
| NBA spread | 1.00 | 1.50 | 1.80 | 2.50 | 3.50 | 18% |
| NBA total | 1.50 | 2.50 | 3.00 | 3.50 | 4.00 | 12% |
| NFL spread | 0.00 | 0.00 | 0.50 | 0.50 | 1.00 | 77% |
| NFL total | 0.00 | 1.00 | 1.00 | 1.00 | 1.50 | 58% |
| CBB spread | 0.50 | 1.00 | 1.00 | 1.50 | 2.00 | 40% |
| CBB total | 1.00 | 2.00 | 2.40 | 3.00 | 4.00 | 30% |
| CFB spread | 0.50 | 1.00 | 1.00 | 1.50 | 2.50 | 41% |
| CFB total | 0.50 | 1.00 | 1.00 | 1.50 | 2.00 | 44% |

Median of the six books' line moves: NBA spread p80 2.00, NBA total 3.00, NFL spread 0.00, CBB spread 1.00, CFB spread 1.00. How many
of the six books moved half a point or more (NBA spreads, 248 games): 0 books 8 games, 1: 25, 2: 28, 3: 21, 4: 32, 5: 42, all 6: 92.
Moneyline, median book no-vig move: pooled p80 2.82 points (NBA 4.46, NFL 1.06, CBB 3.25, CFB 2.05).

**Threshold `T_C`:** the 80th percentile of Pinnacle's absolute line move for the sport and market, rounded **up** to the half point,
with a floor of 1.0 (the stale-number rule's book move). Measured fire rate, either direction: NBA spread 19%, total 21%; NFL spread
4%, total 18%; CBB spread 32%, total 20%; CFB spread 30%, total 34%. (NFL lines barely move inside 24 hours, so the floor binds.)

| T_C (points) | Spread | Total |
|---|---|---|
| NBA | 2.0 | 3.0 |
| NFL | 1.0 | 1.0 |
| CBB | 1.0 | 2.5 |
| CFB | 1.0 | 1.0 |

**The user's example as a reference:** Cornell +22 to +19 is a 3.0 point move toward Cornell (CBB spread p95 2.0, p99 3.0): it would
read "toward", with BookMaker's +18.5 as the extreme if BookMaker were stored (it is not; 0.1).

### 1.5 "Moved against" versions and how flags read next to the play

Each of A and C has three readable states for the play's side: toward, away, quiet. The page words "away" as **"moved against
<side>"**. There is no combined verdict, and a play whose side the market moved away from keeps its card, its tier and its size
exactly as they are (the flags change nothing; section 2).

### 1.6 Minimum data, null rules, and what is never done

| Flag | Exists when | Else |
|---|---|---|
| A | 2+ Pinnacle rows before `asof`, the side maps, Pinnacle heartbeat within 30 min | null with `why` |
| B | 1+ Pinnacle row with a limit before `asof` | null with `why: "no_limit_before_cut"`; 1 row gives `open == now`, shown as "Pinnacle limit $X (one reading)" |
| C | Pinnacle row and 2+ US books with a row before `asof`, side maps, both heartbeats within 30 min | null with `why` |

Never: a 0 for a missing value, a limit inferred from a price, a line inferred for a book that has no row, a "from" read after `asof`,
or a flag on a market with no shown play.

### 1.7 How often the flags fire

**Graded plays** (205 shown plays, 2026-11-12 to 2026-11-22, each read at its own cut):

| Sport | A toward / away / quiet / null | B rising / not / null | C toward / away / quiet / null |
|---|---|---|---|
| NBA (58) | 5 / 12 / 41 / 0 | 57 / 1 / 0 | 6 / 13 / 39 / 0 |
| NFL (33) | 5 / 2 / 26 / 0 | 33 / 0 / 0 | 4 / 1 / 28 / 0 |
| CBB (53) | 0 / 0 / 7 / 46 | 8 / 1 / 44 | 1 / 0 / 7 / 45 |
| CFB (61) | 10 / 6 / 30 / 15 | 46 / 0 / 15 | 11 / 10 / 26 / 14 |

**Live slate** (1:17 PM CT build, 12 shown plays): NBA 7 (A: 1 away, 6 quiet; B: 7 rising; C: 7 quiet), NFL 1 (all quiet; B rising),
CBB 2 (A: 1 toward, 1 quiet; B: 1 rising, 1 not; C: 2 toward), CFB 2 (A: 1 quiet, 1 null; B: 2 rising; C: 1 quiet, 1 null).

---

## 2. Honesty and tracking rules

### 2.1 Context only (CLAUDE.md)

- The flags are **context only**: never a bet signal, never an input to Top Reads, SM_GATE, an agree total, `sf_rungs`, the ladder,
  the locks, the evidence tier `v2t-1`, `shown_units` (flat 1u on NBA, NFL and CBB, none on CFB) or the shadow size `v2s-1` (by tier
  only). A test (T2) fails the build if any of those reads `v2.flags`.
- Banned words in every string this feature renders: agree, agrees, agreement, proven, elite, lock, go, confirm, confirms, smart money,
  sharp action. The flag labels describe the market ("Pinnacle's price moved toward Cornell"), never the bettor. The card always shows
  "Context only" and the size line "1u, untested rule" (or "No size on college football").
- No first person and no advice: no "I", "my", "we took", "bet", "take", "play this", "fade".

### 2.2 A new shadow signal, logged at lock

The flags are a tracking change, so they ship as a **new shadow signal** in the existing forward log
`pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` on `pm-holders-data`:

- **New keys only**, append-only: one new key `mf` on rows written after the registering commit (section 3.3). Old rows keep their
  bytes; readers treat a missing `mf` as "not logged", never as quiet or 0. Every pre-existing key, and the frozen tests
  (`docs/sharp-card-prereg.md`, `docs/sharp-card-prereg-cbb.md`, `docs/sharp-tier-v2-prereg.md` primary and v2s-1,
  `docs/stale-number-prereg.md`, Top Reads rules), are untouched.
- The value logged is the one on the frozen card at the cut (repair pass: re-projected from the card's stored `v2.flags`, so a late
  append equals an on-time one).

### 2.3 Proposed prereg section (to add to `docs/sharp-tier-v2-prereg.md`, status PROPOSED with the rest of that file)

Text to add, verbatim:

> ## Market-move flags v2f-1 (shadow, added 2026-11-23, PROPOSED)
>
> Flags A (Pinnacle's price, fixed line, 24 h), B (Pinnacle's limit, a market fact) and C (the market's number) are defined in
> `docs/sharps-v2-flags-spec.md` section 1, thresholds frozen in `scripts/sharps_v2/plays_v2.py` (`FLAGS_T_A`, `FLAGS_T_C`) at the
> registering commit. Logged at lock as `mf` on the `v2_tier` rows. Context only; they change no size, tier, gate or agree total.
>
> **Primary metric:** Pinnacle CLV = Pinnacle's no-vig fair for the side at the last tape row at or before game start (the `pinclose`
> row) minus the stored Polymarket price at the cut, in points, per flag state, per sport, never pooled. Plays with `price_src == "pin"`
> are left out and reported apart. **Slices:** A toward, A away, A quiet; C toward, C away, C quiet; B is reported as a description
> (share rising), not a slice with a verdict, because it is near-universal. **Comparison:** mean CLV of "toward" minus mean CLV of
> "quiet", and "away" minus "quiet", 95% percentile bootstrap, 10,000 resamples, seed 20261111, resampling plays.
>
> **Minimum n:** 300 plays per sport with a readable flag and a readable close before any verdict; under 300 at the final read is
> Underpowered (neither pass nor fail). **Final reads:** the same dates as the tier registration (NBA: first Monday after the 2026-27
> regular season; NFL: Tuesday after Week 18; CFB: Monday after conference championship weekend; CBB: Monday after the 2027 national
> championship game). Monthly interim reads are report-only.
>
> **Pass** (per sport, per flag): the lower 95% bound of "toward minus quiet" is above 0 with n met. A pass lets the user *consider*
> calling the flag tested; the page keeps "context only" until then. **Secondary:** flat 1u ROI per slice (a win pays 1 / price - 1).
> **Expected:** "toward" holds about one play in ten, so 300 per sport with a toward group big enough is unlikely this season; the honest
> expectation is Underpowered, said in advance. A slice that improves is flagged for close monitoring with its n and is never promoted
> on the same data.

### 2.4 History, re-derived point in time

Feasible wherever the tape existed at the cut; the flags read only tape rows with `t <= cut`, so a frozen card's flags re-derive the same
whenever they are computed (except staleness, see 1.1). Coverage of the 205 graded plays: NBA 58 of 58, NFL 33 of 33, CFB 46 of 61 (A)
and 47 of 61 (C), **CBB 7 of 53** (the CBB tape began 2026-11-19 9:08 AM CT; plays cut before that are null forever, said so on the
card as "No market history stored for this game").

**Record per flag today (in-sample, flat 1u at the stored price at the cut, data dff069af):**

| Slice | NBA | NFL | CBB | CFB (no size shown) | NBA+NFL+CBB |
|---|---|---|---|---|---|
| A toward | 3-2, +0.35u, n=5 | 4-1, +1.93u, n=5 | n=0 | 4-6, -2.91u, n=10 | 7-3, +2.28u, +22.8% (se 27.8), n=10 |
| A away | 7-5, +0.98u, n=12 | 1-1, -0.06u, n=2 | n=0 | 2-4, -2.26u, n=6 | 8-6, +0.92u, +6.6% (se 26.9), n=14 |
| A quiet | 24-17, -1.24u, n=41 | 17-9, +6.02u, n=26 | 4-3, +0.68u, n=7 | 15-15, -3.55u, n=30 | 45-29, +5.46u, +7.4% (se 10.7), n=74 |
| A null | n=0 | n=0 | 25-21, +3.32u, n=46 | 8-7, -0.61u, n=15 | 25-21, +3.32u, n=46 |
| B rising | 34-23, +1.10u, n=57 | 22-11, +7.88u, n=33 | 4-4, -0.32u, n=8 | 21-25, -8.72u, n=46 | 60-38, +8.66u, +8.8% (se 9.3), n=98 |
| C toward | 4-2, +0.37u, n=6 | 3-1, +1.35u, n=4 | 1-0, +1.06u, n=1 | 5-6, -2.82u, n=11 | 8-3, +2.78u, +25.3% (se 25.5), n=11 |
| C away | 9-4, +3.75u, n=13 | 0-1, -1.00u, n=1 | n=0 | 2-8, -5.99u, n=10 | 9-5, +2.75u, +19.6% (se 26.9), n=14 |
| C quiet | 21-18, -4.02u, n=39 | 19-9, +7.53u, n=28 | 4-3, +0.49u, n=7 | 15-11, +1.19u, n=26 | 44-30, +4.00u, +5.4% (se 10.7), n=74 |

**Flagged for close monitoring (each improves; all in-sample and small):** A toward NBA+NFL+CBB +2.28u (n=10); NFL A toward +1.93u (n=5);
NBA A away +0.98u (n=12); C toward NBA+NFL+CBB +2.78u (n=11); C away NBA+NFL+CBB +2.75u (n=14) and NBA C away +3.75u (n=13), which
runs the "wrong" way for any reading of these flags as a signal; NFL A quiet +6.02u (n=26) and NFL C quiet +7.53u (n=28); B rising
NBA+NFL+CBB +8.66u (n=98), which is essentially the whole record because B is near-universal. Every standard error is 9 to 28 points;
none of these separates from zero or from each other.

---

## 3. Data contract

### 3.1 `live.json` and frozen cards: `markets[g].v2.flags` and `markets[g].v2.series` (shown plays only)

Additive keys inside the existing `v2` block, so `strip_plays_v2` already removes them and the V1 byte-compare test still holds.

```
v2.flags = {
  "rule": "v2f-1", "asof": 1795477500, "window_min": 1440, "span_min": 1290, "src_age_min": {"pinnacle": 6, "us": 6},
  "pin": {                                   // Flag A, or null
    "state": "toward" | "away" | "quiet", "pts": 2.31, "t_a": 1.5,
    "from": -105, "to": -129,                // American price for the side at the same line (moneyline: the side's price)
    "line": -3.5 | null, "t_from": 1795400000, "t_to": 1795470000, "rows": 12 },
  "limit": {                                 // Flag B fact (sf_signals.limit_read), or null
    "from": 3000, "to": 20000, "pct": 566.7, "rising": true, "rows": 14 },
  "line": {                                  // Flag C, or null
    "kind": "line" | "price", "state": "toward" | "away" | "quiet", "t_c": 1.0,
    "pin": {"from": 22.0, "to": 19.0},       // the side's line (kind line) or American price (kind price)
    "books": 6, "same_way": 4,
    "by_book": {"DraftKings": [22.0, 19.5], "FanDuel": [22.5, 19.0], ...},   // [from, to] at the side's orientation
    "extreme": {"book": "BetMGM", "value": 18.5} },
  "why": {"pin": null, "limit": null, "line": "too_few_books" }              // a reason per null flag, else null
}
v2.series = {                                // the two mini charts, or null
  "t0": 1795390000, "unit": "min",           // every x is minutes after t0 (integers)
  "pin_px": [[0,-105],[95,-110],[600,-121],[1230,-129]],   // Pinnacle price for the side, at most 16 points
  "lines": {"Pinnacle": [[0,22],[300,20],[1100,19]], "DraftKings": [...], ...}   // spreads and totals only, at most 16 points per book
}
```

- **Downsampling:** at most **16 points per series**: first and last kept, the rest evenly spaced by index, consecutive duplicates
  dropped. A step chart (the value holds until the next change, matching a change-only tape).
- **Byte budget (measured on the live slate, compact JSON):** median **519 bytes** per play (moneylines carry one series), max **1,609**
  (a spread with six books); 16 or 24 points cost the same today (8.3 KB for 11 plays). The busiest graded day had 51 shown plays
  (2026-11-14), so a full slate is about 51 x 1.6 KB = **82 KB worst case**, about 30 KB typical. Current V2 keys 79.7 KB, so worst case
  about **162 KB of the 250 KB V2 budget**; the whole file (now 1,415 KB, larger than the 640 to 840 KB the request quoted) grows by the
  same amount.
- **Sub-budget and drop order:** the flags and series together get **90 KB**. Over it, `check_size.py` drops `v2.series` from every
  card first (charts fall back to the from/to numbers), then `v2.flags.line.by_book`, and prints a `::warning::`. Only if the V2 total
  is still over 250 KB does the existing rule strip all V2 keys.

### 3.2 `v2_plays.flags` (top level, live only)

`{"rule": "v2f-1", "t_a": {...table 1.2...}, "t_c": {...table 1.4...}, "window_min": 1440, "stale_min": 30, "limit_schedule_share":
{"nba": 0.99, "nfl": 0.98, "cbb": 0.97, "cfb": 0.96}, "books": ["Pinnacle","DraftKings","FanDuel","BetMGM","BetRivers","bet365"],
"context_only": true}`. The page reads thresholds and shares from here, never from its own constants.

### 3.3 Forward log: new key `mf` on `v2_tier` rows

`mf = {"rule", "asof", "span_min", "src_age_min", "pin_state", "pin_pts", "pin_from", "pin_to", "pin_line", "lim_from", "lim_to",
"lim_rising", "line_kind", "line_state", "line_pin_from", "line_pin_to", "line_books", "line_same_way", "line_extreme_book",
"line_extreme", "why"}`: a projection of `v2.flags` without `by_book` and without the series. Missing flags are null with their reason.

### 3.4 Builder changes

| File | Change |
|---|---|
| `scripts/sharps_v2/plays_v2.py` | New pure functions `flag_pin(rows, g, norm, asof, sport)`, `flag_limit(rows, g, asof)` (wraps `SIG.limit_read`), `flag_line(rows, g, norm, asof, sport)`, `flag_series(rows, g, norm, asof, n=16)`, `flags_block(...)`; constants `FLAGS_RULE = "v2f-1"`, `FLAGS_T_A`, `FLAGS_T_C`, `FLAGS_WINDOW = 86400`, `FLAGS_STALE = 1800`, `FLAGS_SERIES_N = 16`, `FLAGS_US = US_BOOKS`. `market_v2` calls `flags_block` only when `side` is set and stores `v2["flags"]`, `v2["series"]`. `log_row` adds `mf`. `plays_fields` adds `flags`. |
| `scripts/build_side_cards.py` | Pass the heartbeat (`data/exchange_edge_live.json` `seen`, NFL `data/book_tape/nfl/last.json`) into `market_v2`. **Guard:** the `flags_block` call is wrapped in `try/except Exception as e`; on failure the card gets `v2.flags = null`, `v2.series = null`, `v2.flags_error = "<type>"`, and the build prints `::warning::v2 flags dropped for <ev> <g>: <type>`. The build and every other key are never affected. |
| `scripts/sharps_v2/check_size.py` | The 90 KB sub-budget and drop order of 3.1. |
| `scripts/sharps_v2/flag_history.py` (new) | Point-in-time re-derivation for graded plays (2.4), prints the record per flag with n and the monitoring list; `--json` output to `pm_record/v2_flag_record.json` (copied into `live.json` as `v2_flag_record`, a new top key added to `V2_TOP_KEYS`). |
| `scripts/grade_side_cards.py` | Nothing new to grade: the primary metric uses the `pinclose` row the tier registration already adds. |

---

## 4. The write-up card (UI, in each Sharps table row's dropdown)

Lives in `sharp-money/sharps-v2/sv2-sharps.js` `detailHtml(p, ...)`, above the existing "More detail" block. CSS in `sv2.css` under a
new `sv2-wu-` prefix (CLAUDE.md memory: namespace new UI classes). One rendering function, `writeupHtml(p)`, pure (data in, string out),
so the same markup can later feed a share image.

### 4.1 Structure and strings

- **Eyebrow:** `SHARP MONEY PLAY BREAKDOWN <SPORT>` (letter-spaced caps; the separators are spacing in the design, no commas or dots in
  the text). `<SPORT>` = NBA, NFL, COLLEGE BASKETBALL, COLLEGE FOOTBALL.
- **Title:** `The read on <side label>` (for example "The read on Cornell +19.5", "The read on Under 221.5", "The read on Nuggets").
- **Date pill:** game date in Central, `WED NOV 18`; uses `--sv2-follow` fill with `--sv2-page` ink (AA contrast checked in both themes).
- **Four tiles** (glass inset tiles, `--sv2-glass-in-a`):

| Tile | Label | Value | Sub-line |
|---|---|---|---|
| 1 | THE PLAY | `<side label>` | `<Away> @ <Home>`, market name |
| 2 | THE PRICE | Polymarket cents, for example `55c` (and `-122` in American) | live: "Price now"; frozen: "Price at the cut" |
| 3 | LINE AND FAIR | Pinnacle no-vig fair in cents, for example `Fair 53c` | `vs_fair` in points ("2.0 pts above fair" / "1.1 pts below fair" / "No fair check") |
| 4 | STATUS | live: `Freezes 6:45 PM`; frozen, ungraded: `Frozen 6:45 PM`; graded: `Final 105-101` | live/frozen: "1u, untested rule" or "No size on college football"; graded: "Won", "Lost" or "Push" with the flat units at 1u |

- **Section 1, `1  WHO IS ON EACH SIDE`:** two glass panels side by side (`--sv2-glass-fill`, ring `--sv2-glass-ring`), one per side,
  in market order (away then home, over then under), never heavier-money first, so position never implies a pick.
  Rows per panel, from `v2.sides[<side>]`:

| Row label | Value | Source |
|---|---|---|
| Wallets that beat the close | `$14.9K` and `3 wallets` | `beats` (NBA, NFL); college: row reads "Not measured in college" |
| Past-winner wallets | `$3.7K`, `4 wallets` | `past_winner` |
| Wallets that lose to the close | `$504`, `2 wallets` | `loses` (NBA, NFL); college: `losing_record` with label "Wallets with a losing record" |
| All tracked money | `$97.9K`, `54 wallets` | `usd`, `holders` |

  The side with more `usd` gets a "MORE MONEY" tag and a ring of `--sv2-ink` at 1.5px (tier-neutral: not gold, teal, slate or violet,
  so the money highlight is never read as the evidence tier). Equal money: no tag. Dollars `$1.2K` style, under $1,000 whole dollars.
  The panel never says "sharp side".
- **Section 2, `2  WHERE THE LINE WENT`:** left: the headline numbers, right: the chart.
  - Headline: `PINNACLE <SIDE> PRICE` `-105 -> -129` (moneyline, or the fixed-line price on spreads and totals) and, on spreads and
    totals, a second line `MARKET LINE` `+22 -> +19` (Pinnacle) with "Lowest: BetMGM +18.5" (the `extreme`). The arrow is an SVG icon,
    not a glyph.
  - Chips (text plus a small icon, colour never the only cue): `Pinnacle's price moved toward <side>` / `Pinnacle's price moved
    against <side>` / `Pinnacle's price held` / `Pinnacle's price: no history`; `The market moved the number toward <side> (4 of 6
    books)` / `... against <side> (...)` / `The number held` / `Not enough books to read the number`; moneyline C: `The books moved the
    price toward <side> (3 of 5 books)` and its against/held/null forms. Chip tones: toward and against both use the neutral outline
    (`--sv2-glass-pill`, `--sv2-ink`); no green for toward and no red for against, because neither is good or bad for a reader.
  - Fact line (Flag B): `Pinnacle limit $3,000 to $20,000 since <time> CT. Pinnacle raises limits toward start on almost every game
    (99% of NBA markets this season).` One reading: `Pinnacle limit $3,000 (one reading).` Null: `No Pinnacle limit stored for this
    game.`
- **Takeaway box** (`THE TAKEAWAY`, inset `--sv2-glass-in-b`, ring `--sv2-glass-ring`): sentences built by the templates in 4.2.
- **Footer:** `Wallets: Polymarket public positions. Lines: Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365, read every 10
  minutes. Times Central. Context only, not a bet signal. Size: 1u, untested rule.` (CFB: `Size: none on college football.`) Right side:
  `Sharp Money`.

### 4.2 Takeaway templates (deterministic, no AI, no claim beyond the stored numbers)

Inputs: `A` = flags.pin.state or null, `C` = flags.line.state or null, `kindC` = line or price, `side`, `other` (the other side's label;
for totals "the over" / "the under"), `H` = round(span_min / 60), money `m_side`, `m_other` (`v2.sides[*].usd`), `n_all` (sum of
`holders`), `graded` result. The takeaway is **S1 + S2 (+ S3) + S4**, in that order.

**S1, the market (exactly one branch):**

| A | C | S1 |
|---|---|---|
| toward | toward | `In the last {H} hours Pinnacle's price and the market's {number|price} both moved toward {side}.` |
| away | away | `In the last {H} hours Pinnacle's price and the market's {number|price} both moved against {side}.` |
| toward | away | `Pinnacle's price moved toward {side} while the market's {number|price} moved against it, so the market did not settle on one direction.` |
| away | toward | `The market's {number|price} moved toward {side} while Pinnacle's price moved against it, so the market did not settle on one direction.` |
| toward | quiet | `Pinnacle's price moved toward {side} ({from} to {to}); the market's {number|price} held.` |
| toward | null | `Pinnacle's price moved toward {side} ({from} to {to}); there were not enough book readings to say where the {number|price} went.` |
| away | quiet | `Pinnacle's price moved against {side} ({from} to {to}); the market's {number|price} held.` |
| away | null | `Pinnacle's price moved against {side} ({from} to {to}); there were not enough book readings to say where the {number|price} went.` |
| quiet | toward | `The market moved the {number|price} toward {side} ({pin_from} to {pin_to} at Pinnacle, {same_way} of {books} books the same way); Pinnacle's price at that {line|number} held.` |
| null | toward | `The market moved the {number|price} toward {side} ({pin_from} to {pin_to} at Pinnacle, {same_way} of {books} books the same way).` |
| quiet | away | `The market moved the {number|price} against {side} ({pin_from} to {pin_to} at Pinnacle, {same_way} of {books} books the same way); Pinnacle's price at that {line|number} held.` |
| null | away | `The market moved the {number|price} against {side} ({pin_from} to {pin_to} at Pinnacle, {same_way} of {books} books the same way).` |
| quiet | quiet | `The market barely moved on this {market} in the last {H} hours.` |
| quiet | null | `Pinnacle's price barely moved; there were not enough book readings to say where the {number|price} went.` |
| null | quiet | `The {number|price} barely moved at the books; Pinnacle's price history was not readable.` |
| null | null | `No market history is stored for this game, so there is nothing to say about where the line went.` |

`{market}` = moneyline, spread, total. `{H}`: when span_min < 120, the phrase "in the last {H} hours" becomes "since the first stored
reading {M} minutes earlier". On the "against" branches with a shown size, append: ` The play and its size are unchanged by this.`

**S2, the tracked money (exactly one branch; omitted when `v2.sides` is missing):**

| Condition | S2 |
|---|---|
| `n_all < 5` or `m_side + m_other < 1000` (small sample, a display rule) | `Only {n_all} tracked wallets (${total}) hold this market, too few to describe.` |
| `m_side > m_other` | `More of the tracked Polymarket money is on {side} (${m_side} against ${m_other}).` |
| `m_other > m_side` | `More of the tracked Polymarket money is on {other} (${m_other} against ${m_side}).` |
| equal | `The tracked Polymarket money is split evenly (${m_side} each).` |

**S3, money and market point different ways (optional, only when S2 is not the small-sample branch):** when the heavier-money side is
`other` and A or C is toward `side`, or the heavier-money side is `side` and A or C is against `side`:
`The tracked money and the market's moves point in different directions here.` No sentence says which one to follow.

**S4, always last:** `These are descriptions of what the market did. Past moves like these have not shown an edge in Vault's records,
so this is context, not a reason to bet.` Graded cards add before S4: `Final {away score}-{home score}: the play {won|lost|pushed}.`

Placeholders print stored values only; a placeholder whose value is null forces the branch that does not use it (the table already
covers every null pair). A test enumerates all 16 S1 rows x 4 S2 rows x S3 on/off x graded or not and asserts no banned word (2.1) and
no unfilled `{`.

### 4.3 The chart

Inline SVG, no library. Two stacked panes sharing the x axis (Central clock times at the first, middle and last point, "Now" or
"Cut" at the right edge): top, Pinnacle's price for the side as a step line with the from and to values labelled at the ends; bottom
(spreads and totals only), one step line per book from `v2.series.lines`, Pinnacle drawn thicker. Book colours from a fixed six-colour
set that passes 3:1 against `--sv2-card` in both themes (validated in T5); each line is also labelled at its right end with the book
name and value (colour is never the only cue). Legend chips toggle a book (buttons, `aria-pressed`). Height 140px desktop, 120px phone.
No animation on first paint; the toggles use `--sv2-ease-out`, 150ms opacity only, and nothing moves under `prefers-reduced-motion`.

**Text alternative:** the SVG has `role="img"` and an `aria-label` built from the same template as S1 plus the from/to numbers. Under the
chart, a `<details>` "Show the numbers" holds a `<table>` with a `<caption>` (time CT, Pinnacle price, each book's line), which is the
data table for screen readers and for anyone who wants the raw values.

### 4.4 Layout

- **Desktop (row dropdown at 1024px and up):** eyebrow, title and date pill on one row; four tiles in a 4-column grid; section 1 panels
  in 2 columns; section 2 as text left (40%) and chart right (60%); takeaway full width; footer full width.
- **Phone (under 768px):** content first (memory: the first phone screen shows real content): title and the four tiles (2 x 2) come
  first, then the takeaway, then sections 1 and 2 collapsed behind `Who is on each side` and `Where the line went` disclosure buttons
  (closed by default, 44px hit area), chart full width. 16px side gutter, no horizontal scroll.
- **Tokens:** glass `--sv2-glass-fill`, `--sv2-glass-ring`, `--sv2-glass-hi`, `--sv2-glass-pill`, `--sv2-glass-in-a`,
  `--sv2-glass-in-b`; text `--sv2-ink`, `--sv2-mut` (labels), `--sv2-faint` only for the footer; numbers in `--sv2-num`. Tier colours
  (gold Clear, teal Mixed, slate Thin, violet Contested) appear only in the existing tier pill in the tile row, never on flag chips,
  money panels or the chart. Win and loss colours only on the graded status tile.
- **Contrast:** every text pair at 4.5:1 or more in dark, light and Apple skins (checked by T5 with the computed colours, not the
  tokens).
- **Motion:** the dropdown already uses the V2 expander; nothing new is hand-rolled.

### 4.5 Share as an image later

Feasible. The classic page already exports a share card with html2canvas 1.4.1 from cdnjs (`vscShareCard` in
`sharp-money/index.html`, `toBlob` to PNG). Because `writeupHtml(p)` is pure, a later task can render it into an offscreen node at a
fixed 1080px width and reuse `vscShareCard`. Not in this build (decision D6).

### 4.6 Test plan

- **Python (`tests/test_sharps_v2_plays.py`, stdlib unittest, run by `pm-cards.yml`):** fixture tapes for each flag state of A and C on
  moneyline, spread and total, home and away, over and under; the user's Cornell and +105 to -129 numbers as fixtures; a row after
  `asof` never changes the result; fewer than 2 rows gives null, never quiet; stale heartbeat gives null with its reason; `limit_read`
  output equals `sf.all.signals.limit`; series never exceed 16 points and keep first and last; `strip_plays_v2` still returns the V1
  file byte for byte; `shown_units`, `shadow_units`, `tier_of`, the ladder and the gates give identical output with `v2.flags` present,
  absent or garbage; a raised exception inside `flags_block` leaves the card built with `flags: null` and a `::warning::`; `log_row`
  adds `mf` and leaves every old key's value unchanged; the 90 KB drop order.
- **JS (`sharp-money/sharps-v2/tests/sv2-sharps.test.mjs`):** every takeaway branch combination (4.2) renders with no banned word and
  no `{`; null flags render their null strings; college panels show "Not measured in college"; the money tag goes to the larger `usd`
  and never uses a tier class; the chart's `aria-label` and table match the series.
- **Rendered check (CLAUDE.md, memory "verify UI filter wiring"):** run the page against a real `live.json`, open a dropdown on desktop
  and at 375px, screenshot both themes, confirm the old "More detail" and filter buttons still work (namespacing), and check
  `pill.getAnimations()` is untouched on the table's segmented controls.

---

## 5. Build plan

| # | Task | Model | Files | Done when |
|---|---|---|---|---|
| T1 | Commit the measurement as `flag_history.py`; regenerate every distribution and record table in this spec from it at a named data commit | Sonnet builds, Opus reviews the numbers against this spec | `scripts/sharps_v2/flag_history.py`, `docs/side-card-record.md` (new section "Market-move flags v2f-1") | the printed tables equal sections 1 and 2.4, or the spec is corrected first |
| T2 | Flag functions, series, guard, `mf` log key, sub-budget | Sonnet builds; Opus reviews point-in-time reads, null rules and that nothing size-related reads the flags | `scripts/sharps_v2/plays_v2.py`, `scripts/build_side_cards.py`, `scripts/sharps_v2/check_size.py`, `tests/test_sharps_v2_plays.py` | Python tests in 4.6 pass; a local build on the live inputs shows the 3.1 byte numbers |
| T3 | Prereg section added to `docs/sharp-tier-v2-prereg.md` (PROPOSED) | Opus writes, user approves (D5) | that file only | text of 2.3 present, status line unchanged |
| T4 | History record: `pm_record/v2_flag_record.json` written by the record workflow, `v2_flag_record` in `live.json` | Sonnet builds, Opus reviews | `.github/workflows/pm-record.yml`, `plays_v2.V2_TOP_KEYS` | the file matches T1's tables |
| T5 | Write-up card, chart, table, phone layout, contrast check | Sonnet builds; Opus reviews strings against 2.1 and 4.2 | `sharp-money/sharps-v2/sv2-sharps.js`, `sv2.css`, `tests/sv2-sharps.test.mjs` | JS tests pass; desktop and phone screenshots in both themes in the PR |
| T6 | Optional: Fanatics and Caesars game lines on the tape (D4) | Sonnet builds, Opus reviews | `scripts/fetch-sharp-money.mjs` (`SOFT`, ids 2988 and 123 after confirming the scoreboard returns game markets for them), `scripts/book_tape.py` (`AN_BOOKS`) | new rows appear; forward only, no backfill exists |

One PR per task, each with the Model/data and UI split and old/new numbers (CLAUDE.md). T2 and T5 must not run while another open PR
edits `plays_v2.py` or `sv2-sharps.js`.

**Decisions needed from the user:**

- **D1 (Flag B):** show the limit as a fact line only (recommended: it rose on 96% to 99% of markets and has no side), or as a chip
  using the existing rising rule (it would be on for nearly every play), or commission a "limit above schedule" rule (needs a fitted
  schedule and its own registration; deferred).
- **D2 (thresholds):** the per-sport, per-market 80th-percentile tables (recommended), or one pooled value per market (A: moneyline
  2.5, spread and total 1.5; C: 1.0 with the same 2-book condition).
- **D3 (moneyline Flag C):** the US books' price move (recommended), or no Flag C on moneylines.
- **D4:** add Fanatics and Caesars game lines going forward. BookMaker and Circa cannot be shown (SmartStake terms), so the card can
  never show the "BookMaker touching +18.5" part of the example.
- **D5:** approve the prereg section text in 2.3 (it stays PROPOSED with the rest of `docs/sharp-tier-v2-prereg.md` until registered).
- **D6:** share-as-image later (4.5), yes or no.
- **D7:** the title "The read on <side>" and the eyebrow wording.

**Deferred:** a "limit above schedule" flag (D1); BookMaker and Circa (no publishable source); CBB history before 2026-11-19 9:08 AM CT
(no tape, null forever); the share image (D6).
