# Sharps V2: plays data spec (what `scripts/build_side_cards.py` publishes, additively)

Written 2026-11-21 (Central). Planner spec for the V2 plays data. It is the data contract the V2 page (`docs/sharps-v2-spec.md`)
reads for plays. Where the two disagree, this file wins and section 8 says exactly what the page must change.

**Amendments of 2026-11-23 (after implementation and review; where they differ from the text below, they win):**

- **Numbers are dated.** Every measured number in sections 3.3, 6, 7.1, 7.2 and 7.3 (the 166 graded shown plays, 71 readable price checks, the 54 KB and
  tier tables) is as of the Nov 21 inputs named below (`origin/pm-holders-data` at `d48a3dc0bd`). The Nov 23 re-run (205 graded rule picks, 144 in NBA,
  NFL and CBB, at `dec770c0e7bb`) is in `docs/side-card-record.md`, reproduced by `scripts/sharps_v2/tier_history.py`; the build measured 54 KB of V2
  keys on an 839 KB `live.json` (183 games).
- **Old cards (history only):** where no price check was possible at the cut because the tape did not exist yet (`no_tape_rows_for_game`,
  `no_pinnacle_before_cut`, or no stored read and no tape row at the cut), a4 and b2 are unknown and the play is "not derivable", not Thin.
  Forward cards keep the rule of section 3.2 as written, so forward Thin is a different group.
- **Never fail the build (section 1):** the V2 block, the quote tape, the log sync and the slate each run in a guard: on an exception that card or
  step has no V2 keys and a `::warning::` is printed. Short or `null` tape rows are skipped.
- **Size gate (section 6):** the 250 KB live V2 budget is a soft gate. Over it, `check_size.py --live` rewrites `live.json` without the V2 keys and
  warns; it never fails the publish. Only `wallets.json` keeps the hard gate.
- **Log month (section 5.2):** the Central date of game start, not UTC.
- **`--now`** reaches `card()`: `built` and a live card's `asof` use it in pinned runs.
- **`tier_record.json`** (new, beside `live.json`; schema in `docs/side-cards.md`) publishes the per-sport, per-tier flat-1u record for the page.

Inputs measured (all stdlib, all times Central):

- `live.json` built 1795278075 (Sat Nov 21, 10:21 AM CT), the plays audit and UI audit of 2026-11-21.
- `origin/pm-holders-data` at d48a3dc0bd (Nov 21, 10:22 AM CT): 684 frozen cards under `pm_cards/`, 2,027 graded rows under
  `pm_record/cards/`, `pm_record/cards_record.json` generated 1795260596 (Nov 21, 5:29 AM CT).
- Frozen keyframes under `pm_holders/<sport>/frozen/` (local extract of `origin/pm-holders-data`).
- `data/book_tape/<sport>/2026-11.jsonl` at the worktree commit (Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365, Kalshi,
  Novig rows, written on change).
- `origin/sharp-data` `data.json` (generated 2026-11-21 10:18 AM CT) and `state.json` (651 games, split history back to Nov 6).

Binding rules (CLAUDE.md, the workflow):

- Sharp money is context only. Nothing here is a bet signal; nothing feeds Top Reads, SM_GATE or an agree total. The only size is the
  documented side-card exception: flat 1u on NBA, NFL and CBB plays, nothing on CFB, always labelled "untested rule". The evidence tier
  never changes that size.
- Never invent a number. Every published number is a stored price, a stored quote, a stored count, or arithmetic on stored fields.
  A missing value is `null` or an absent key, never 0.
- Additive only. No existing key in `live.json`, in a frozen card, in a graded row or in `cards_record.json` changes its name, shape or
  value. `scripts/sf_rungs.py`, every gate and lock, `sf_tiers.py`, `sf_shadows.py`, `sf_publish.py`, `sf_solo.py`, the frozen
  tests and the shadow logs are untouched.
- Point in time: every field on a frozen card is computed from data at or before that card's cut (T-15). Nothing computed after the cut
  is written to a card.
- Any change that affects tracking also fixes history (section 7). No em dashes anywhere. All times Central.

---

## 1. Files

| File | Change |
|---|---|
| `scripts/sharps_v2/plays_v2.py` (new) | Pure functions: `facts`, `tier_of`, `side_blocks`, `lead`, `exec_at`, `vs_fair`, `splits_live`, `splits_at`, `price_src`, `shown_units`, `shown_units_at`, `pin_close`, `log_row`, `strip_plays_v2`. Stdlib only. Imported by the builder and the grader, so a frozen card and a re-derivation can never disagree on a rule. |
| `scripts/build_side_cards.py` | Calls `plays_v2` at the end of `card()` (after `signals`) and in `main()` (slate pass, shadow log, record copy). New args `--v2-tier-record FILE` (optional). No existing function changes behaviour or output. |
| `scripts/grade_side_cards.py` | New append-only row kind `pinclose`; new record sections `v2_tier` and `shown` per sport; new file `pm_record/v2_tier_record.json`. `plays()`, `grade()`, `summarize()` and every existing record key unchanged. |
| `.github/workflows/pm-cards.yml` | Pass `--v2-tier-record pmdata/pm_record/v2_tier_record.json`; run `tests.test_sharps_v2_plays` with the other unit tests. The shadow log sits under `pm_cards/<sport>/`, so the existing `commit_push("pmdata", "pm_cards", sports, ...)` already commits it. |
| `tests/test_sharps_v2_plays.py` (new) | Section 9. |
| `docs/sharp-tier-v2-prereg.md` (new) | The pre-registration of the tier shadow (PROPOSED until the user approves). |
| `docs/side-card-record.md` | The missing 2026-11-20 entry (section 7.3, text ready). Done in the same PR as the grader change. |

Not edited: `sharp-money/side-cards.js`, `sharp-money/following.js` (other PRs), anything under `sharp-money/sharps-v2/` (the V2 page
workflow), `docs/sharps-v2-spec.md`, `docs/sharps-v2-accounts-spec.md`.

## 2. Where each thing is published

| Place | What | Allowed because |
|---|---|---|
| `live.json` `games[].markets[g].v2` | the per-market play block (section 3) | new key |
| `live.json` `games[].markets[g].splits` | public split (section 4) | new key, the name the V2 page already reads |
| `live.json` top `v2_slate`, `v2_tier_record`, `v2_plays` | slate reads, the per-tier forward record copy, the field list | new keys |
| New frozen cards `markets[g].v2`, `markets[g].splits` | the same blocks, computed at the cut | see below |
| `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` on `pm-holders-data` | the forward shadow log, one row per rule pick at freeze (section 5) | new file, append-only |
| `pm_record/cards/<sport>/<YYYY-MM>.jsonl` | new row kind `pinclose` (key `<sf key>|pinclose`) | new rows, append-only, existing rows untouched |
| `pm_record/cards_record.json` | new per-sport sections `v2_tier`, `shown` | new keys |
| `pm_record/v2_tier_record.json` | compact per-tier record (the builder copies it into `live.json`) | new file |

**Frozen cards.** The pre-registrations freeze rules and definitions ("Nothing below may change after the first frozen card is graded"),
not the set of keys a card may carry. They never forbid an additive key, and the repo already added keys to frozen cards after
registration without a version bump: `sf.cid` (Nov 11), `sf.signals` (Nov 14), `sfx`, `pub` and `flagged`, and `tp` (Nov 18,
`docs/sharp-tier-prereg.md`). So `v2` and `splits` are written on **new** frozen cards only. An existing frozen file is never rewritten
(the builder already skips a card whose file exists). Old cards get their V2 values by derivation in the grader (section 7), like
`derive_signals`.

## 3. `markets[g].v2` (per market group, every card that has holders in `g`)

One object per market group (`ml`, `spread`, `total`). Variant `all` only (the shown play's variant). Present on every market group
that has a `sides` entry, so the No play context list can read the conflict counts too. Fields that only make sense with a rule pick
are `null` when `sf.all.side` is null.

### 3.1 The play and its size

| Field | Type | Definition | Source |
|---|---|---|---|
| `rule` | string | `"v2t-1"`, the tier rule version (section 3.2). A rule change is a new string and a new registration. | constant |
| `side` | string or null | `sf.all.side` when `sf.all.units > 0`, else null. | stored |
| `shown_units` | 0 or 1 | 1 when `side` is set and sport is `nba`, `nfl` or `cbb`; 0 otherwise (CFB, or no pick). The ladder stays in `sf.all.units`, untouched. | CLAUDE.md rule |
| `shown_rule` | string | `"flat 1u on NBA, NFL, CBB; none on CFB; untested rule (since 2026-11-20 4:47 PM CT)"` | constant |
| `untested` | true | always true while `docs/sharp-card-prereg.md` runs; the page prints "untested rule" wherever a size appears | constant |

`shown_units` never reads the tier. A unit test asserts it is identical for every tier (section 9).

### 3.2 Evidence tier and facts

The vocabulary is the V2 page's: **clear, mixed, thin, contested** (lowercase strings), and no tier when there is no pick. S is
`v2.side`, O the other side(s) of the same market group. Every input is a field already on the card at the cut:

| Fact | Meaning | Test on stored fields | Sports |
|---|---|---|---|
| `a1` | past-winner wallets on the other side | sum over O of `sides[o].all.counts.hc + counts.sharp` >= 1 | all |
| `a2` | wallets that beat the close on the other side | sum over O of `sides[o].all.rk.sharp_n` >= 1 | NBA, NFL |
| `a3` | the registered fade-dull rule fires on the other side | `tp.tB.side` set and != S | NBA, NFL (cards cut on or after 2026-11-19 12:00 AM CT) |
| `a4` | price worse than Pinnacle's no-vig fair by 0.3 pts or more | `sf.all.signals.ev.pts` not null and <= -0.3 | all |
| `b1` | wallets that beat the close on this side | `sides[S].all.rk.sharp_n` >= 1 | NBA, NFL |
| `b2` | price better than Pinnacle's no-vig fair by 0.3 pts or more | `sf.all.signals.ev.pts` >= 0.3 | all |
| `b3` | same pick on forward-only wallet books | `sf.fwd.side == S` | all |
| `b4` | two or more past-winner wallets on this side | `sides[S].all.proven.wallets` >= 2 | all |

0.3 is `EV_ON_PTS` in `scripts/sf_signals.py` (registered Nov 14). No new threshold is introduced.

Tier, first match wins (identical to `docs/sharps-v2-spec.md` 1.1):

| Tier | Rule |
|---|---|
| `contested` | any of `a1` to `a4` is true |
| `clear` | none of `a1` to `a4`, (`b1` or `b2`), and `b3` |
| `thin` | none of `a1` to `a4`, not clear, `proven.wallets` <= 1, not `b1`, and `ev.pts` null |
| `mixed` | everything else |
| (null) | no pick (`side` null) |

Published fields:

| Field | Type | Notes |
|---|---|---|
| `tier` | string or null | set for every rule pick in every sport, CFB included (the CFB shadow needs it). The page shows it only when `shown_units` is 1. |
| `facts` | `{a1, a2, a3, a4, b1, b2, b3, b4}` booleans | on live and new frozen cards always true or false. `null` appears only in grader re-derivations of old cards (section 7) where the input was not stored at the cut. |
| `facts_na` | list | facts that do not apply to the sport: `["a2", "b1", "a3"]` on CBB and CFB (no tested closing-price model in college; `tp` is NBA and NFL only). Those facts are published as false. |
| `tested` | absent | reserved. Published only after a registered test passes on its final read; no page label until then. |

Unknown handling (old cards only, never on live or new frozen cards): `contested` when any known `a` fact is true; otherwise, if any of
`a1` to `a4` or `b1` is `null`, the tier is `null` with `tier_why: "fact not stored at the cut: a2"` (the list of null facts).

On the 10:21 AM CT build the rule gives 11 shown plays: **contested 10, thin 1** (CBB Under 144.5, COLMB at BOSTU), clear 0, mixed 0.
Contested by fact: `a2` on 9 of 10, `a1` on 3, `a4` on 3, `a3` on 3 (the Bengals ML is Contested on `a4` alone).

The live tier is a preview: it changes until the cut. The tier that is logged and graded is the one on the frozen card (section 5).

### 3.3 Price: what is shown, what you would get, and the check against fair

| Field | Shape | Definition and source | Absent when |
|---|---|---|---|
| `price_src` | `"pm"` or `"pin"` | which price `sf.all.price` is: `pm` when it equals the keyframe's Polymarket displayed price of S on `sf.all.cid` (`kf.mk[cid].px[oi]`), `pin` when the builder fell back to Pinnacle's vig-included implied price (`build_side_cards.py` `sf_market`, the `px is None and g == "ml"` branch). This is the additive fix of the "on Polymarket" label bug: `sf.all.price` itself is unchanged. | no pick, or `sf.all.price` null |
| `pm` | `{px, t, since_min, kind: "displayed"}` | Polymarket's displayed price of S at the cut: `sf.all.price` and `sf.all.price_t` when `price_src` is `pm`. `since_min` = (cut or build time) minus `t`, minutes. `kind` says it is Gamma `outcomePrices` (a mid or last trade), never the price a follower pays. | `price_src` is not `pm` |
| `exec.pm_ask` | `{px, t}` | Polymarket best ask for S at the cut. **Not stored anywhere today** (keyframes carry `px`, `px_t`, no book). Needs the holders scan to log Gamma `bestBid` / `bestAsk` on its price rows (section 10, D-P1). Until then the key is absent and the page omits the line. A displayed price is never written here. | always, until D-P1 ships |
| `exec.us_best` | `{book, odds, line, px, t, since_min}` | best price for S among DraftKings, FanDuel, BetMGM, BetRivers and bet365 on the **same line**: each book's last book-tape row at or before `asof` (cut on frozen cards, build time on live ones); moneyline: the side's odds; spread: the book's signed line equals the ticket's signed line within `PIN_LINE_EPS` (0.051, registered in `sf_signals.py`); total: same line. Best = lowest vig-included implied probability `px` (`american_prob(odds)`, arithmetic on the stored odds). Ties: alphabetical book. | no book has the line |
| `exec.kalshi` | `{px, t, since_min}` | moneyline only. Kalshi's home contract `[bid, ask]` from the tape: cost of S = ask when S is home, 1 minus bid when S is away (the exchange is a binary contract). | not moneyline, or no Kalshi row |
| `exec.novig` | `{px, t, since_min}` | Novig quote from the tape: moneyline `px` [home bid, home ask], spread `nsp` [home line, home bid, home ask] (signed line must equal the ticket's), total `ntot` [line, over bid, over ask] (same line). Cost of S as for Kalshi. | no row, or line differs |
| `exec.pin` | `{odds, t}` | Pinnacle's vig-included price for S at the cut (`sf.all.pinnacle_odds`) and the time of the tape row it came from. | not readable |
| `exec.asof` | epoch | the time all `exec` reads stop at (cut on frozen cards, min(cut, build time) on live cards) | |
| `vs_fair` | `{pts, fair, t, line, why}` | `sf.all.signals.ev` (unchanged) plus `t`, the time of the Pinnacle row it read, and the ticket `line`. `pts` = (fair minus price) x 100, positive = price better than fair. `why` is the stored reason when `pts` is null (`ticket_line_not_main_at_cut`, `no_pinnacle_before_cut`, `no_tape_rows_for_game`, `side_unmapped`, `no_price`). | never absent on a pick; `pts` may be null |

**Tape times are change times.** The book tape writes a row when a book's numbers change. So `t` is "last change logged at or before
`asof`", not "read at". The page must say "unchanged since 10:15 AM CT", never "read at" (section 8). No staleness threshold is
introduced; `since_min` is published and the page shows the time.

Measured on the 166 graded shown plays (stored cards plus the tape at each cut): `us_best` readable NBA 45 of 50, NFL 16 of 19, CBB 5 of
49, CFB 27 of 48; `kalshi` NBA 39, NFL 2, CBB 4, CFB 15; `novig` NBA 42, NFL 2, CBB 4, CFB 22. `vs_fair.pts` readable on 71 of 166
(NBA 41, NFL 10, CBB 3, CFB 17). CBB tape starts Nov 19 (forward only), so older CBB plays have no quote. On the 10:21 build, 9 of 19
rule picks had `vs_fair.pts` (all moneylines), 7 of them priced worse than fair (mean -0.43 pts).

### 3.4 Conflict block (who holds each side, by class and by account tier)

`v2.sides[<side name>]`, for every side of the market group:

| Field | Definition | Invariant (tested) |
|---|---|---|
| `holders` | number of holders on the side at the card's $250 floor, after the hedge collapse, any class | `sum(sides[s].all.counts.*)` |
| `usd` | their money, mark value (shares x price at the cut), rounded | `sharp_usd + unproven_usd + loser_usd + excluded_usd` |
| `past_winner` | `{n, usd}`: classes `hc` and `sharp` (the page's "past winner, picked after the fact") | `counts.hc + counts.sharp`, `sharp_usd` |
| `losing_record` | `{n, usd}`: class `loser` | `counts.loser`, `loser_usd` |
| `beats` | `{n, usd}`: holders whose CLV tier at the cut is `sharp` (V2 account tier `beats`) | `rk.sharp_n`, `rk.sharp_usd` |
| `loses` | `{n, usd}`: CLV tier `dull` (`loses`) | `rk.dull_n`, `rk.dull_usd` |
| `even` | `{n, usd}`: CLV tier `mid` (`even`) | new count, no V1 field |
| `few` | `{n, usd}`: CLV tier `thin` or no tier row (`few`) | `holders - beats - loses - even` |
| `price_tier` | true on NBA and NFL; false on CBB and CFB, where `beats`, `loses`, `even` are `null` and `few` carries every holder (accounts spec: college rows are always `few`) | |

The account tier is the same mapping as the wallets file V2 (`V2_TIER` in `build_side_cards.py`: `sharp` beats, `mid` even, `dull`
loses, else few) but read **at the card's cut** (`holder_groups` already attaches `rk` as of the cut), never the wallets file's
tier as of now. `beats` and `loses` include holders of class `excluded`, exactly as `rk_side` counts them, so `a2` and `b1` read the
same numbers the card already stores.

Plus `v2.conflict` (a summary over O, null when no pick):

| Field | Definition |
|---|---|
| `past_winner_against` | `{n, usd}` summed over O |
| `beats_for`, `beats_against` | `beats.n` on S, summed over O (null on college) |
| `loses_for`, `loses_against` | same for `loses` (null on college) |
| `fade_dull_other_side` | `a3` |
| `money_share_for` | S `usd` / (S `usd` + O `usd`), 3 decimals; null when both are 0 |

### 3.5 Lead wallet and the same wallet across the slate

| Field | Where | Definition |
|---|---|---|
| `v2.lead` | live and frozen | the largest past-winner holder on S: `{w, usd, class, press}` (`press` = mark / usual cost, the stored V1 semantics, labelled "this position vs average cost"). Null when no past-winner holder on S. |
| `v2.past_winners_for` | live and frozen | every past-winner wallet on S, money order, from the **full** holder list (the card's `list` keeps only the top 4) |
| `v2.lead.slate_plays` | live only | the number of shown plays (`shown_units` 1) in this `live.json` build where `lead.w` is in `past_winners_for` |
| top `v2_slate` | live only | `{plays, by_tier: {clear, mixed, thin, contested}, vs_fair_readable, same_wallet: [{w, plays, keys: ["<ev>|<g>"]}]}` for every wallet on 2 or more shown plays, most plays first. The page decides its own display threshold. |

The slate count is not written to frozen cards: a frozen card is built at its own cut, before later games of the same day freeze, so a
same-day count there would not be point in time. On the 10:21 build: `...5fcee5` on 7 of 11 shown plays, `...e1a138` on 2.

## 4. `markets[g].splits` (public split, context only)

Shape, as the V2 page already reads it, plus provenance keys:

```
{"t": <epoch>, "src": "action_network_consensus", "basis": "live" | "at_cut",
 "sides": {"<side name>": {"bets": <int pct>, "money": <int pct>, "comp": true?}}}
```

- **Join:** `games[].key` of sharp-data `data.json` equals the card's `vault.key` (the builder's `vault_join` already matches the
  Polymarket slug). Moneyline and spread map `home` / `away` through the builder's own `side_norms` (the same home/away read the steam
  and price checks use); total maps `over` / `under`. A side that does not map is left out, never guessed. A group with no split
  (`null` in the feed) has no `splits` key at all; no placeholder, never 0.
- **Live cards (`basis: "live"`):** `data.json` `games[].splits.<ml|sp|tot>` as stored, both sides (`t` = tickets %, `m` = money %).
  `t` = the file's `generated`.
- **New frozen cards (`basis: "at_cut"`):** the last row of `games[].splitHist` with `ts` <= cut (the feed logs a row when the split
  changes). `t` = that row's `ts`. The history stores the home (or over) side only; the other side is 100 minus it and carries
  `comp: true`. Checked on the 10:18 AM CT feed: 279 of 279 live pairs sum to 100 for both bets and money.
- Source is Action Network's public consensus (the free source `scripts/fetch-sharp-money.mjs` already polls). Context only. It is not a
  tier input and has no record. The CBB split-move test (`docs/cbb-split-move-prereg.md`) is separate and untouched.
- On the 10:26 AM CT copy (measured by the V2 page spec, 5.4): 171 of 171 live games with a `vault.key` matched; 111 carried a split.

## 5. Frozen card, shadow log and grader

### 5.1 New frozen cards

`card(..., frozen=True)` writes `markets[g].v2` and `markets[g].splits` with every read stopped at the cut. Nothing else on the card
changes; the byte-compare test (section 9) covers frozen output too.

### 5.2 The shadow log `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl`

Append-only, one row per rule pick (`sf.all.side` set and `sf.all.units > 0`) on each newly frozen card, every sport (CFB rows carry
`shown_units: 0`). Month by the Central date of game start. Rows are sorted by key within a run and never
rewritten. A row is a projection of the frozen card's own stored `v2` block, so a run that wrote a card but died before the log append
is healed on the next run: the builder appends a row for any frozen card that has a `v2` block and no log row with its key. That repair
copies stored values only.

```
{"key": "<sport>/frozen/<date>/<slug>@<gst>.json|<g>|all|sf",   same key as the graded sf row
 "v": 1, "rule": "v2t-1", "src": "frozen", "logged_at": <epoch>, "sport", "ev", "gst", "cut", "group": "<g>",
 "side", "line", "outs", "cid", "price", "price_t", "price_src", "shown_units", "ladder_units",   ladder = sf.all.units, a copy
 "tier", "facts": {...}, "facts_na": [...],
 "ev_pts", "fair", "pin_t",
 "past_winner_for", "past_winner_against", "beats_for", "beats_against", "loses_for", "loses_against",
 "tb_side", "fwd_side", "lead_w", "money_share_for",
 "exec": {...}, "splits": {...} | null,
 "counts": <card test.counts>, "why_not": [...]}
```

`counts` copies the card's `test.counts`: the prereg reads counted cards only (built before game start, ledger run before the cut, not
a duplicate). On the 166 graded shown plays so far every card counts.

### 5.3 Grader additions (`scripts/grade_side_cards.py`)

1. **`pinclose` rows.** For every `sf` play (variant `all`, every sport, every card old and new), once its result row exists, append once:
   `{"key": "<sf key>|pinclose", "kind": "pinclose", "of": "<sf key>", "v": 1, "sport", "ev", "gst", "close_fair", "close_t",
   "close_line", "clv": close_fair - price, "pts": (close_fair - price) x 100, "why", "graded_at"}`.
   The close is Pinnacle's no-vig fair for S from the **last Pinnacle tape row at or before game start**, the same "last quote before
   kickoff" rule `scripts/exchange_edge_record.py` uses, computed with `sf_signals.ev_read(rows, g, norm, line, gst, price)` so the
   fair formula is the registered one. Spread and total need the ticket line to be Pinnacle's main line at the close, else `pts` null and
   `why: "ticket_line_not_main_at_close"`. No close is estimated; a play without one is counted by reason. `close_t` is published so a
   reader sees how old the last change was (the tape writes on change). Writing after the result row means the tape rows up to kickoff
   have been committed for hours; no new waiting time is introduced.
2. **Tier per graded `sf` row**, read, not written: from the shadow log row when one exists (`src: "frozen"`), else re-derived from the
   frozen card with `plays_v2.facts` (stored card fields, `derive_signals` for cards without stored signals, tape rows at or before the
   cut): `src: "derived"`, `in_sample: true`.
3. **`cards_record.json` `sports.<sp>.v2_tier`**: `{forward: {<tier>: summary}, in_sample: {<tier>: summary, "null": summary},
   derived_differs: n}`. Summary = the existing `summarize()` with the `pinclose` rows passed as `closes` (so `clv_n`, `clv_mean`,
   `clv_ci` are the Pinnacle close CLV in probability units) plus a second `pm_clv` block with the existing Polymarket close rows.
   `forward` holds log rows with `cut >= V2T_REGISTERED_AT` and `counts` true. `derived_differs` counts forward log rows whose tier
   differs from a re-derivation (a tape row committed after the freeze); it feeds the prereg's data-quality rule.
4. **`cards_record.json` `sports.<sp>.shown`**: the record at the shown size, computed from the stored flat result:
   `today_rule` (flat 1u on NBA, NFL, CBB over every history row, which is what the page shows now) and `at_the_time` (the size the page
   actually showed at each cut: the ladder before 2026-11-18 8:31 AM CT, flat 1u on NBA and NFL from then, CBB added at
   2026-11-20 4:47 PM CT). Rows are not rewritten; both lines are derived on read.
5. **`pm_record/v2_tier_record.json`**: `{"generated", "rule": "v2t-1", "registered_at": V2T_REGISTERED_AT | null, "prereg":
   "docs/sharp-tier-v2-prereg.md", "report_only": true, "sports": {<sp>: {<tier>: {w, l, p, n, units, flat_roi, clv_n, clv_mean,
   since}}}}` holding the `forward` lines only. Before registration `registered_at` is null and `sports` is empty.

The builder copies that file, unchanged, into `live.json` `v2_tier_record` when `--v2-tier-record` is given and the file parses;
otherwise the key is absent.

## 6. Size

The 10:21 build has 219 market groups with holders and 19 rule picks on a 2,840 KB file. The addition is not measured yet (no build
exists); a rough estimate from the field lists is 100 to 150 KB. The implementer reports the measured number in the PR. Budget: the V2 keys
stay under 250 KB of compact JSON; `scripts/sharps_v2/check_size.py` gains a `--live` mode measuring `live.json` minus
`strip_plays_v2(live.json)`. Over budget fails the publish step and the last good file stays live, as for the wallets file.

## 7. History (CLAUDE.md: fix the historical data and the records)

### 7.1 Can each new field be re-derived for already-graded plays, point in time?

| Field | Re-derivable for old cards? | How, or why not |
|---|---|---|
| `side`, `shown_units` | yes, all 169 | stored `sf.all.side`, `sf.all.units`, sport |
| `shown_units_at` (size shown at the time) | yes | cut time vs the dated page changes (#461, #534 merge times) |
| `price_src` | yes, all 169 | `sf.all.price` vs keyframe `px` on `sf.all.cid`: **169 of 169 are `pm`**. The Pinnacle fallback has never fired on a shown play, so no record changes. |
| `pm` | yes | stored `sf.all.price`, `price_t` |
| `exec.pm_ask` | **no, forward only** | no ask or book was stored at any cut |
| `exec.us_best`, `kalshi`, `novig`, `pin` | yes where the tape has rows (counts in 3.3) | book tape rows at or before the cut; CBB tape starts 2026-11-19 |
| `vs_fair` | yes, 71 of 166 readable | stored `sf.all.signals` on 143 plays, re-derived from the tape on 23 (`derive_signals`). Stored and re-derived agree on 146 of 146 picks that have both. |
| `a1`, `b3`, `b4` | yes, all | stored `counts`, `sf.fwd`, `proven.wallets` |
| `a4`, `b2` | yes | from `vs_fair` |
| `a2`, `b1` | NBA and NFL cards cut on or after 2026-11-18 only | `rk` was first stored on cards cut Nov 18. Re-computing older tiers now would use ledger rows and wallets added after those cuts, so it is not point in time: left `null`. |
| `a3` | NBA and NFL cards cut on or after 2026-11-19 12:00 AM CT only | `tp` exists only from its registration (`sf_tiers.REGISTERED_AT`); an older `tB` would be in-sample and outside its frozen universe: `null` |
| `tier` | 155 of 166 graded; 11 `null` (NBA 8, NFL 3, cut Nov 15 to Nov 18, no known `a` fact true and `a2`/`a3` not stored) | rule above |
| `sides[].past_winner`, `losing_record`, `holders`, `usd` | yes, all | stored `counts` and usd fields |
| `sides[].beats`, `loses` | cards cut on or after 2026-11-18 | stored `rk.sharp_*`, `rk.dull_*` |
| `sides[].even`, `few` | **no, forward only** | the `mid` / `thin` split was never stored on a card |
| `lead`, `past_winners_for` | top 4 only | the card's `list` keeps the 4 largest past-winner wallets per side (same known gap as `seas`) |
| `lead.slate_plays`, `v2_slate` | live only by design | |
| `splits` | yes for games still in `sharp-data` `state.json` | `state.json` `games[key].split` rows with `ts` <= cut: readable on 132 of 169 shown plays (NBA 41 of 50, NFL 18 of 19, CBB 43 of 52, CFB 30 of 48). `state.json` is a single force-pushed snapshot and prunes games, so the backfill must be taken once, now, into `pm_record/v2_tier/splits_backfill.json` (context only, no record reads it). The rest is forward only. |
| `pinclose` | yes, 71 of 166 graded | tape rows at or before kickoff; 57 have no tape for the game (mostly CBB before Nov 19), 37 are off Pinnacle's main line, 1 side unmapped |
| the **logged** tier (shadow log) | **no, forward only** | the log starts at registration; everything before is a derivation, marked `in_sample` |

### 7.2 Records to fix: the per-tier record of every graded play (re-derived, in-sample; numbers as of the Nov 21 inputs, 166 plays)

Flat 1 unit at the stored price at the cut (the grader's own `flat`), variant `all`, 166 graded shown-size plays (3 voided CBB plays on
one postponed game are excluded, as in the record). Pinnacle CLV = no-vig close minus the price at the cut, in points, last tape row at
or before kickoff. Every row below is in-sample: the tier rule was written after these results.

**Old (the record today, no tier):**

| Slice | Record | Flat units | ROI | se | n | Pinnacle CLV (new column) |
|---|---|---|---|---|---|---|
| NBA | 28-22 | -3.18u | -6.4% | 12.6 | 50 | +0.12 pts, n=41 |
| NFL | 13-6 | +5.11u | +26.9% | 21.0 | 19 | -0.70 pts, n=10 |
| CBB | 27-22 | +3.74u | +7.6% | 14.3 | 49 | +0.00 pts, n=3 |
| CFB (no size) | 23-25 | -6.41u | -13.3% | 13.4 | 48 | -0.17 pts, n=17 |
| Headline NBA+NFL+CBB | 68-50 | +5.66u | +4.8% | 8.7 | 118 | -0.04 pts, n=54 |

**New (the same plays split by tier; the headline totals are unchanged):**

| Sport | Clear | Mixed | Thin | Contested | Not derivable |
|---|---|---|---|---|---|
| NBA | none | none | none | 24-18, -2.32u, -5.5%, n=42; CLV +0.11 (n=36) | 4-4, -0.86u, n=8 |
| NFL | none | none | none | 10-6, +2.12u, +13.2%, n=16; CLV -0.70 (n=10) | 3-0, +2.99u, n=3 |
| CBB | 1-0, +1.20u, n=1; CLV +1.01 (n=1) | 0-2, -2.00u, n=2 | 23-19, +3.74u, +8.9%, n=42; CLV n=0 | 3-1, +0.80u, n=4; CLV -0.51 (n=2) | none |
| CFB (no size) | none | 4-8, -4.23u, n=12; CLV +0.04 (n=8) | 14-6, +5.31u, +26.6%, n=20; CLV n=0 | 5-11, -7.49u, -46.8%, n=16; CLV -0.37 (n=9) | none |
| **Headline** | 1-0, +1.20u, n=1 | 0-2, -2.00u, n=2 | 23-19, +3.74u, +8.9%, n=42 | 37-25, +0.60u, +1.0%, se 11.2, n=62; CLV -0.08 (n=48) | 7-4, +2.13u, n=11 |

Contested by fact (graded plays): NBA `a1` 20, `a4` 19, `a2` 17; NFL `a1` 14, `a4` 8, `a2` 1; CBB `a1` 2, `a4` 2; CFB `a1` 9, `a4` 8.
`a3` never fired on a graded play (it exists only on cards cut from Nov 19).

What this supports: nothing. NBA and NFL shown plays are all Contested where decidable; CBB is almost all Thin because no CBB price check
was possible before the CBB tape began on Nov 19. The tiers do not separate on these samples (Contested +1.0% at se 11.2 vs Thin +8.9% at
se 15.6).

**Flagged for close monitoring (house rule), all in-sample, none promoted:**

| Slice | Record | n |
|---|---|---|
| CBB Thin | 23-19, +3.74u, +8.9% | 42 |
| CFB Thin (no size) | 14-6, +5.31u, +26.6% | 20 |
| NFL Contested | 10-6, +2.12u, +13.2% (but Pinnacle CLV -0.70 pts, n=10) | 16 |
| Headline Contested | 37-25, +0.60u, +1.0% | 62 |
| NBA Pinnacle CLV, all shown plays | +0.12 pts | 41 |

### 7.3 Records to fix: the missing 2026-11-20 CBB re-add entry

Verified from the graded rows (same numbers as the plays audit):

| Line | Old headline (NBA + NFL) | New headline (NBA + NFL + CBB) |
|---|---|---|
| Plays cut before 2026-11-20 12:00 AM CT | 37-23, +4.56u, +7.6%, n=60 | 62-42, +9.37u, +9.0%, n=104 |
| Rows graded before the change merged (#534, Nov 20 4:47 PM CT) | 37-23, +4.56u, n=60 | 62-43, +8.37u, n=105 |
| Today (Nov 21 5:29 AM CT record) | 41-28, +1.92u, +2.8%, n=69 | 68-50, +5.66u, +4.8%, n=118 |

CBB before the change: cut before Nov 18 8:31 AM CT 13-17, -4.23u (n=30, the Nov 18 audit's -6.30u was the ladder); cut Nov 18 to the
change, when CBB was hidden, 13-3, +9.10u (n=16; cut Nov 18 to 19: 12-2, +9.03u, n=14). CBB since: cut on or after Nov 20 12:00 AM CT
2-3, -1.07u (n=5); cut after the merge 1-2, -1.13u (n=3).

The size the page actually showed at each cut (ladder before Nov 18, NBA and NFL flat from Nov 18, CBB flat from Nov 20 4:47 PM CT):
**74-70, -10.21u on 185u staked, n=144** (NBA -3.77u n=50, NFL +8.65u n=19, CBB -7.43u n=33, CFB -7.65u n=42). The headline the page shows
(+5.66u) is the current rule applied to all history.

Text for `docs/side-card-record.md`, after the 2026-11-18 entry:

> ## Change on 2026-11-20: CBB plays shown again (#534, 4:47 PM CT)
>
> At the user's request the page shows CBB plays again at a flat 1u with "untested rule", against the Nov 18 audit's read of CBB
> (-8.0% forward on its signal). Nothing stored changes; the record headline now adds CBB over all history.
>
> | Line | Before (NBA + NFL) | After (NBA + NFL + CBB) |
> |---|---|---|
> | Plays cut before Nov 20 | 37-23, +4.56u, n=60 | 62-42, +9.37u, n=104 |
> | Record of Nov 21, 5:29 AM CT | 41-28, +1.92u, n=69 | 68-50, +5.66u, n=118 |
>
> The headline rose **only because CBB plays were added after CBB plays cut Nov 18 to 19 went 12-2 (+9.03u, n=14)**. That is a choice
> made on results: in-sample, flagged for close monitoring at n = 49 CBB plays. CBB since the change: 2-3, -1.07u (n=5). At the sizes the
> page actually showed at each cut the record is 74-70, -10.21u (n=144).

### 7.4 Forward only, said explicitly

`exec.pm_ask`; `sides[].even` and `few`; `a2`, `b1` before Nov 18 and `a3` before Nov 19 (published `null` in re-derivations, never
guessed); quotes for games with no tape at the cut; splits for games already pruned from `state.json` (37 of 169 shown plays); the
slate count; and the logged tier itself (the prereg reads forward log rows only).

## 8. What the V2 page must change (the data contract wins)

The V2 page spec names several fields inside `sf.all`. Writing there would change the value of the existing `sf` key on every card and
break the byte-compare of existing keys, so they move to the new `markets[g].v2` block:

| V2 page spec reads | Read instead |
|---|---|
| `sf.all.shown_units` | `markets[g].v2.shown_units` (fallback rule unchanged when `v2` is absent) |
| `sf.all.price_src` | `markets[g].v2.price_src` |
| `sf.all.exec.pm_ask` | `markets[g].v2.exec.pm_ask` (absent until D-P1) |
| `sf.all.exec.us_best` `{book, odds, line, t}` | `markets[g].v2.exec.us_best` `{book, odds, line, px, t, since_min}` |
| `sf.all.exec.kalshi`, `.novig` `{px, t}` | `markets[g].v2.exec.kalshi`, `.novig` `{px, t, since_min}` |
| `sf.all.close_vs_fair` on frozen cards | not in `live.json`: a card leaves `live.json` at its cut and the close happens after it, and frozen cards are never rewritten. Per play it lives in the `pinclose` rows; per tier it is `clv_mean` in `v2_tier_record`. Drop the per-play line from the V2 page. |
| top `v2_tier_record` `{<tier>: {w, l, p, n, units, since}}` | `v2_tier_record.sports.<sport>.<tier>` `{w, l, p, n, units, flat_roi, clv_n, clv_mean, since}`. Per sport, never pooled. Show "No verdict until n = 300" per sport. |
| `markets[g].v2.tier` "logged at freeze" | on `live.json` it is the live preview; the logged tier is the frozen card's. Strings are lowercase. |

Also:

1. `v2.tier` is set on CFB rule picks too (the shadow logs them). The page must gate on `v2.shown_units` first: 0 means "No play",
   whatever the tier.
2. `v2.facts_na` lists facts that do not apply (college). `v2.facts` is never null in `live.json`.
3. Tape times are change times: copy "unchanged since 10:15 AM CT", not "read 10:15 AM CT".
4. Prefer `v2_slate.same_wallet` (full holder lists) over the client count from `list[]` (top 4 only, can undercount).
5. `markets[g].splits` matches the page's shape; the extra `basis` and `comp` keys can be ignored, but a `comp: true` side should read
   "(the other side is 100 minus the logged side)" in the detail if shown on a frozen card.
6. `exec.pm` exists so the page can name the displayed price as Polymarket's ("55c displayed on Polymarket, a mid or last trade") only when
   `price_src` is `pm`, and name Pinnacle when it is `pin`.

## 9. Tests (`tests/test_sharps_v2_plays.py`, stdlib `unittest`, run by `pm-cards.yml`)

1. **Byte-compare, live and frozen.** Build the 10:21 inputs twice with `time.time` patched to 1795278075 (`card()` stamps `built` from
   the clock): once with `build_side_cards.py` from `origin/main` (read with `git show` into a temp module), once with the new code.
   `strip_plays_v2()` removes exactly `markets[g].v2`, `markets[g].splits`, top `v2_slate`, `v2_tier_record`, `v2_plays`; the stripped
   new output must equal the old output byte for byte (`json.dumps(..., separators=(",", ":"))`), for `live.json` and for every frozen
   card written to a temp `--frozen-out`.
2. Existing tests stay green: `tests.test_side_cards`, `tests.test_sf_rungs`, `tests.test_sf_tiers`, `tests.test_side_card_record`,
   `tests.test_sharps_v2_wallets`.
3. Invariants on every market of the fixture: `sides[s].past_winner.n == counts.hc + counts.sharp`; `beats.n == rk.sharp_n` and
   `loses.n == rk.dull_n` (NBA, NFL); `holders == sum(counts)`; `vs_fair.pts == sf.all.signals.ev.pts`; `side == sf.all.side` when
   `units > 0`.
4. Tier truth table (same cases as the page's `tierOf` test) and the 10:21 fixture: contested 10, thin 1, clear 0, mixed 0; `...5fcee5` on
   7 of 11 in `v2_slate.same_wallet`.
5. `shown_units`: 1 on NBA, NFL, CBB picks; 0 on CFB and no pick; identical for every tier (property test).
6. Exec: never copies the keyframe `px` into `exec`; Kalshi away cost = 1 minus home bid; a line mismatch omits the book; reads stop at
   `asof` (a row 1 second after the cut is ignored).
7. Splits: absent when the feed has none; never 0; `at_cut` uses only `splitHist` rows at or before the cut; `comp` set on the derived
   side; an unmapped side is omitted.
8. Shadow log: one row per pick per new frozen card; a second run appends nothing; a card without a log row is healed from its stored
   `v2`; existing lines are byte-identical after a run.
9. History: the re-derivation over `pm-holders-data` at d48a3dc0bd reproduces section 7.2 (tier counts per sport and the W-L).
10. No U+2014 in any new or changed file.

## 10. Open decisions (for the user)

- **D-P1. Polymarket ask at the cut.** Add Gamma `bestBid` / `bestAsk` to the holders scan's price rows and to keyframe `mk` (additive
  keys; the frozen tests read `px` and `px_t` only). A separate PR on `scripts/scan_pm_holders.py`. Until then no ask is published.
  Grading at the ask would be a new line from its start date, beside the displayed-price line, never a rewrite.
- **D-P2. Register the tier shadow.** `docs/sharp-tier-v2-prereg.md` is PROPOSED. Until the user approves it, the builder may write
  `v2` blocks and the log, but `v2_tier_record` stays empty and the page shows "Tier record: not logged yet".
- **D-P3. 1u on Contested plays** (the page spec's D1). Not part of this spec. Removing a size would change the headline and need a
  CLAUDE.md change and a full re-derivation with old and new numbers.
- **D-P4. Splits backfill.** Approve taking the one-time `state.json` snapshot now (it prunes); otherwise splits are forward only.
