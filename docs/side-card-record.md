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

Shadows of the shown size are graded beside it with the same rules, and never appear on a card or in the main Open plays list. Clicking a rule in the Record's "Same plays under other rules" table filters Open plays and Completed plays to that rule; its open plays come from `open_shadow` in cards_record.json (locked, not yet graded; `grade_side_cards.py open_plays(shadows=True)`), labelled Shadow:

| Play | What it is | Source |
|---|---|---|
| `pub` | the shown play minus sides the benchmark would mute | `scripts/sf_publish.py` |
| `solo` | the shown play capped at 1u on one proven wallet or a small lead bet | `scripts/sf_solo.py` |
| `only` | the shown play only with a proven wallet for and none against | `scripts/sf_shadows.py`, `docs/sharp-shadow-rules-nov16.md` |
| `two` | `only`, with two or more proven wallets for | same |
| `seas` | `only`, counting a wallet as proven only with 20+ graded positions | same |

`only`, `two` and `seas` rows carry `in_sample` (the card was cut before the rules were written), and `cards_record.json` gives a
`forward` line beside `all_cards` for them. "Flat 1u" on the Record page is not a play: it is the shown plays' stored flat ROI
times their count.

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

## One record on the page (2026-11-13)

The Record tab shows one system: Vault's record (every suggested play) and its forward test. The benchmark head-to-head is no longer
shown or fetched by the page. `benchmark_h2h.py` still archives and grades it on `pm-holders-data` (`h2h_record.json`,
`pm_record/benchmark/`), so the comparison can be read from the data if it is ever needed again.

## Prices confirmed by a later read (2026-11-13)

Until 2026-11-13 the holders scan logged a price only when it changed, so a steady price kept the time it last moved and a play
could be graded "unpriced" although its price was current. The scan re-read every market's price on each holders read and logs
whether that read succeeded (`price_err` on the cycle row). The grader now confirms such a price: when the stored price is older than
30 minutes, the latest cycle that re-read the market's price successfully before the lock (and within 30 minutes of it) is its
price time (`price_t_src: "confirmed by a later unchanged read"`). Rows already written as unpriced are corrected in place with a
`corrected` note (when, what it was, why). From 2026-11-13 the scan also re-logs every price at the freeze read, so new cards carry a
fresh price time directly. The 30-minute rule of the registration is unchanged; this fixes the recorded price time it reads.


## Change on 2026-11-18: flat 1u, no college size, "hot" wallets

After `docs/sharps-audit-2026-11-18.md` the page (`sharp-money/side-cards.js`, `?v=40`) shows a flat 1u on NBA and NFL plays and no size on
CFB and CBB, and calls the old "proven" wallets "hot". Nothing stored changes: the builder still writes `sf.units` (the old ladder), and the
grader still writes the same rows. The page keeps the ladder as `units_ladder` and reads the record from the stored flat result.

| Record line | Reads |
|---|---|
| Record (headline) | NBA and NFL `sf` plays, stored flat ROI times plays, every history row |
| Old size ladder (shadow) | all sports at the stored ladder units (the headline before Nov 18: 60-59, -9.05u, 119 plays) |
| College at 1u (shadow) | CFB and CBB plays at 1u (32-40, -12.53u, 72 plays) |

The headline moved from -9.05u to +1.95u (28-19, 47 plays) **only because the rule moved the college plays and the ladder out of it**. The rule was
chosen after seeing the results, so it is in-sample and flagged for close monitoring at n = 47. It is not evidence of an edge.

## Change on 2026-11-20: CBB plays shown again (#534, 4:47 PM CT)

At the user's request the page shows CBB plays again at a flat 1u with "untested rule", against the Nov 18 audit's read of CBB (-8.0% forward
on its signal). Nothing stored changes; the headline now adds CBB over all history. This entry was missing until 2026-11-23. Every number is
re-measured from the graded rows on `pm-holders-data` at commit `dec770c0e7bb1292f7b2bc09d754ae6680b76387` by `scripts/sharps_v2/tier_history.py` (flat 1u at the stored price at the cut,
variant `all`, voided plays left out).

| Line | Before (NBA + NFL) | After (NBA + NFL + CBB) |
|---|---|---|
| Plays cut before Nov 20, 12:00 AM CT | 37-23, +4.56u, +7.6%, n=60 | 62-42, +9.37u, +9.0%, n=104 |
| Rows graded before #534 merged (Nov 20, 4:47 PM CT) | 37-23, +4.56u, n=60 | 62-43, +8.37u, n=105 |
| Record read on Nov 23 (all history) | 56-35, +7.98u, +8.8%, n=91 | 85-59, +11.98u, +8.3%, n=144 |

The headline rose on Nov 20 **only because CBB plays were added after CBB plays cut Nov 18 to 19 went 12-2 (+9.03u, n=14)**. That is a choice made
on results: in-sample, flagged for close monitoring at n = 53 CBB plays (29-24, +4.00u, +7.5%).

CBB by cut time: before Nov 18 8:31 AM CT 13-17, -4.23u (n=30; the Nov 18 audit's -6.30u was the ladder); Nov 18 to the change, when CBB was hidden,
13-3, +9.10u (n=16); cut on or after Nov 20 12:00 AM CT 4-5, -0.81u (n=9; it was 2-3, -1.07u, n=5 on Nov 21); cut after the merge 3-4, -0.87u (n=7).

At the size the page actually showed at each cut (ladder before Nov 18 8:31 AM CT, flat 1u on NBA and NFL from then, CBB flat from Nov 20 4:47 PM CT,
CFB none): 91-79, -3.89u on 211u staked, n=170 (NBA -0.49u, NFL +11.43u, CBB -7.17u on the 37 plays shown, CFB -7.65u). The headline the page
shows (+11.98u) is the current rule applied to all history, not what a reader following the page would have had.

## Sharps V2 plays data: evidence tier and the record by tier (2026-11-23)

`scripts/build_side_cards.py` now publishes an evidence tier and the price you would get beside each play (`markets[g].v2`, `markets[g].splits`,
`docs/side-cards.md` "V2 plays data"). Nothing already stored changes: `scripts/sharps_v2/tier_history.py` re-derives the tier of every graded shown
play from its own card at its cut (nothing from the outcome) and prints the record per tier. The tiers are in-sample (the rule was written after
these results) and are not a signal. Forward test: `docs/sharp-tier-v2-prereg.md` (Registered 2026-11-23).

**Data read:** `origin/pm-holders-data` at commit `dec770c0e7bb1292f7b2bc09d754ae6680b76387` (Nov 23, 10:26 AM CT). Every number in this entry is as of that
commit and is reproduced by `python3 -I scripts/sharps_v2/tier_history.py --ref <commit>`, which prints the hash it read.

**Old-card rule (added after review).** On a card from before the tape existed for its game, no price check was possible at the cut, so the price facts
(a4, b2) are *unknown*, not "no price evidence". Those plays are **not derivable**, not Thin. This moved 42 of the 45 CBB Thin plays (and 10 of 24 CFB
Thin plays) to not derivable. A **forward Thin** play (a card written by the new builder, tier stored on the card at its freeze) is a different group: the live rule counts "no price read" as
Thin whatever the reason, so forward Thin includes plays with no price check possible (for example a ticket line that is not Pinnacle's main line).
The two groups must not be read together, and forward Thin will be read on its own record (`tier_record.json` `forward`: only plays whose tier the live builder logged at lock, which starts at the first logged lock and is empty until a logged play is graded). Every record in this entry, and `in_sample` and `since_nov16` in `tier_record.json`, are tiers derived after the fact (rule v2t-1 was written Nov 21 to 23), never forward.

| Old (the record today, no tier) | Record | n |
|---|---|---|
| NBA | 34-24, +0.10u, +0.2% | 58 |
| NFL | 22-11, +7.88u, +23.9% | 33 |
| CBB | 29-24, +4.00u, +7.5% | 53 |
| CFB (no size shown) | 29-32, -9.33u, -15.3% | 61 |
| Headline NBA + NFL + CBB | 85-59, +11.98u, +8.3% | 144 |

| New (the same plays by tier; headline totals unchanged) | Clear | Mixed | Thin | Contested | Not derivable |
|---|---|---|---|---|---|
| NBA | 0 | 0 | 0 | 30-20, +0.96u, n=50 | 4-4, -0.86u, n=8 |
| NFL | 0 | 0 | 0 | 19-11, +4.89u, n=30 | 3-0, +2.99u, n=3 |
| CBB | 1-0, +1.20u, n=1 | 0-1, -1.00u, n=1 | 0-3, -3.00u, n=3 | 4-1, +1.86u, n=5 | 24-19, +4.94u, n=43 |
| CFB (no size) | 0 | 4-9, -5.27u, n=13 | 9-5, +2.53u, n=14 | 8-13, -7.98u, n=21 | 8-5, +1.39u, n=13 |
| Headline | 1-0, +1.20u, n=1 | 0-1, -1.00u, n=1 | 0-3, -3.00u, n=3 | 53-32, +7.72u, +9.1%, n=85 | 31-23, +7.07u, +13.1%, n=54 |

"Not derivable" means a fact the tier needs was not stored on the card at its cut (the CLV tiers were first stored on cards cut Nov 18, the fade rule on
cards cut from Nov 19, and no tape existed yet for the game on many college cards) and no stored fact against the side was already true. It is never
guessed and never folded into a tier. Pinnacle CLV (no-vig close minus the price at the cut, last tape row before kickoff): NBA +0.12 pts (n=47), NFL
-0.59 (n=18), CBB -0.26 (n=4), CFB -0.19 (n=23), headline -0.09 (n=69).

**Flagged for close monitoring: every record that improves, with its n** (flat ROI above 0, or mean Pinnacle CLV above 0; "small sample" under n=30; all
in-sample, none promoted, none a signal; the list is the output of `tier_history.py`, in the same order):

| Slice (metric) | Record | n |
|---|---|---|
| NBA all shown plays (flat ROI) | 34-24, +0.10u | 58 |
| NBA all shown plays (Pinnacle CLV +0.12 pts) | | 47 |
| NBA Contested (flat ROI) | 30-20, +0.96u | 50 |
| NBA Contested (Pinnacle CLV +0.11 pts) | | 42 |
| NBA not derivable (Pinnacle CLV +0.21 pts) | | 5, small sample |
| NFL all shown plays (flat ROI) | 22-11, +7.88u (Pinnacle CLV -0.59, n=18) | 33 |
| NFL Contested (flat ROI) | 19-11, +4.89u (Pinnacle CLV -0.59, n=18) | 30 |
| NFL not derivable (flat ROI) | 3-0, +2.99u | 3, small sample |
| CBB all shown plays (flat ROI) | 29-24, +4.00u | 53 |
| CBB Clear (flat ROI and Pinnacle CLV +1.01 pts) | 1-0, +1.20u | 1, small sample |
| CBB Contested (flat ROI) | 4-1, +1.86u (Pinnacle CLV -0.69, n=3) | 5, small sample |
| CBB not derivable (flat ROI) | 24-19, +4.94u | 43 |
| CFB Mixed (Pinnacle CLV +0.03 pts) | 4-9, -5.27u | 9, small sample |
| CFB Thin (flat ROI) | 9-5, +2.53u | 14, small sample |
| CFB not derivable (flat ROI) | 8-5, +1.39u | 13, small sample |
| Headline NBA+NFL+CBB (flat ROI) | 85-59, +11.98u | 144 |
| Headline Clear (flat ROI and Pinnacle CLV +1.01 pts) | 1-0, +1.20u | 1, small sample |
| Headline Contested (flat ROI) | 53-32, +7.72u | 85 |
| Headline not derivable (flat ROI) | 31-23, +7.07u | 54 |
| Headline not derivable (Pinnacle CLV +0.21 pts) | | 5, small sample |

The tiers do not separate on these samples: Contested +9.1% at se 9.8 against not derivable +13.1% at se 13.7.


## Tier-scaled size shadow v2s-1 (2026-11-23)

By the user's decision of 2026-11-23, the flat 1u was an MVP. A second rule, **v2s-1**, sizes each play by its V2 evidence tier: **Clear 1.5u, Mixed 1u,
Thin 0.5u, Contested 0.5u, CFB nothing**, and a play whose tier is not derivable gets **no shadow size** (null, never 0). It runs **beside** the flat
1u and changes nothing the page shows: the shown size is still a flat 1u on NBA, NFL and CBB with the "untested rule" label, the ladder, `sf_rungs`, the
gates and the locks are untouched, and the shadow never feeds Top Reads, SM_GATE or an agree total. The five values are an **ordering by evidence, not
fitted to results**: nobody looked at a result to pick them. The record below is **in-sample** (the tier rule v2t-1 was written after these results, so
the tiers are derived after the fact) and each play's tier is re-derived point in time from its own card at its cut, as before. Shadow units are each
play's flat result (the unit result at its own stored price, a push 0) times its shadow size; units staked is the sum of the sizes (a push is staked and
returns 0); ROI is units over staked. Printed by `python3 -I scripts/sharps_v2/tier_history.py` and written to `tier_record.json` (`shadow` in every cell).

Data: `pm-holders-data` at commit `b5940c258ee7`, 205 graded shown plays (sf, variant all), 3 voided left out.

| Slice | Flat 1u (the shown size) | Shadow v2s-1 (units on units staked, ROI, se) |
|---|---|---|
| NBA, every play (flat only) | 34-24, +0.10u, +0.2%, n=58 | |
| NBA, derivable plays | 30-20, +0.96u, +1.9%, n=50 | +0.48u on 25u, +1.9%, se 12.6, n=50 |
| NBA, Contested | 30-20, +0.96u, +1.9%, n=50 | +0.48u on 25u, +1.9%, se 12.6, n=50 |
| NBA, Not derivable | 4-4, -0.86u, -10.8%, n=8 | no stake (8 not derivable) |
| NFL, every play (flat only) | 22-11, +7.88u, +23.9%, n=33 | |
| NFL, derivable plays | 19-11, +4.89u, +16.3%, n=30 | +2.45u on 15u, +16.3%, se 16.7, n=30 |
| NFL, Contested | 19-11, +4.89u, +16.3%, n=30 | +2.45u on 15u, +16.3%, se 16.7, n=30 |
| NFL, Not derivable | 3-0, +2.99u, +99.7%, n=3 | no stake (3 not derivable) |
| CBB, every play (flat only) | 29-24, +4.00u, +7.5%, n=53 | |
| CBB, derivable plays | 5-5, -0.94u, -9.4%, n=10 | +0.23u on 6.5u, +3.5%, se 36.9, n=10 |
| CBB, Clear | 1-0, +1.20u, +119.8%, n=1 | +1.80u on 1.5u, +119.8%, n=1 |
| CBB, Mixed | 0-1, -1.00u, -100.0%, n=1 | -1.00u on 1u, -100.0%, n=1 |
| CBB, Thin | 0-3, -3.00u, -100.0%, n=3 | -1.50u on 1.5u, -100.0%, se 0.0, n=3 |
| CBB, Contested | 4-1, +1.86u, +37.3%, n=5 | +0.93u on 2.5u, +37.3%, se 33.7, n=5 |
| CBB, Not derivable | 24-19, +4.94u, +11.5%, n=43 | no stake (43 not derivable) |
| CFB (no size shown), every play (flat only) | 29-32, -9.33u, -15.3%, n=61 | |
| CFB (no size shown), derivable plays | 21-27, -10.72u, -22.3%, n=48 | no stake (13 not derivable) |
| CFB (no size shown), Mixed | 4-9, -5.27u, -40.5%, n=13 | no stake |
| CFB (no size shown), Thin | 9-5, +2.53u, +18.0%, n=14 | no stake |
| CFB (no size shown), Contested | 8-13, -7.98u, -38.0%, n=21 | no stake |
| CFB (no size shown), Not derivable | 8-5, +1.39u, +10.7%, n=13 | no stake (13 not derivable) |
| **Headline NBA+NFL+CBB**, every play (flat only) | 85-59, +11.98u, +8.3%, n=144 | |
| **Headline**, derivable plays | 54-36, +4.91u, +5.5%, n=90 | +3.15u on 46.5u, +6.8%, se 10.1, n=90 |
| Headline, Clear | 1-0, +1.20u, +119.8%, n=1 | +1.80u on 1.5u, +119.8%, n=1 |
| Headline, Mixed | 0-1, -1.00u, -100.0%, n=1 | -1.00u on 1u, -100.0%, n=1 |
| Headline, Thin | 0-3, -3.00u, -100.0%, n=3 | -1.50u on 1.5u, -100.0%, se 0.0, n=3 |
| Headline, Contested | 53-32, +7.72u, +9.1%, n=85 | +3.86u on 42.5u, +9.1%, se 9.8, n=85 |
| Headline, Not derivable | 31-23, +7.07u, +13.1%, n=54 | no stake (54 not derivable) |

How to read it, plainly:

- **Per-tier ROI is the same under both rules** inside one sport, because every play of a tier gets one size. The shadow changes the units and the money
  staked there, not the percentage. Only a slice that mixes tiers (a sport's derivable plays, the headline) can differ in ROI.
- **The shadow does not stake the 54 not derivable plays** (an old-card limit: no price check was possible at the cut), and those were the best flat
  slice (31-23, +7.07u). So the honest same-plays comparison is the **derivable** rows: headline flat **+4.91u on 90u, +5.5%** against shadow **+3.15u on
  46.5u, +6.8%**. The shadow stakes about half as much and earns a slightly higher ROI, a gap of 1.3 points against a standard error near 10.
- **85 of the 90 derivable headline plays are Contested** (0.5u), so today the shadow is mostly a half-size flat bet on Contested plays. Clear, Mixed and
  Thin hold 5 plays in total (n=1, 1 and 3). The 1.5u on Clear rests on one play.
- **Standard error:** a standard error of an ROI is about 5.8 points at n=300, so a sport with n under 300 (NBA 50, NFL 30, CBB 10 derivable) cannot read an
  edge, and the headline's n=90 reads none either (se 10.1). Neither rule is shown to beat the other. This is a record, not a signal.

**Improves under the shadow, flagged for close monitoring** (shadow ROI above the flat ROI of the same plays, with n; in-sample, none promoted):

| Slice | Flat | Shadow | n |
|---|---|---|---|
| CBB derivable plays | -9.4% (-0.94u) | +3.5% (+0.23u) | 10, small sample |
| Headline derivable plays | +5.5% (+4.91u) | +6.8% (+3.15u) | 90 |

The CBB line moves mostly because the one Clear play (a win) is sized up and the three Thin plays (all losses) are sized down; that is an ordering applied after
the fact to ten plays and says nothing about forward results. The registered forward read is in `docs/sharp-tier-v2-prereg.md`, "Shadow size v2s-1" (Registered 2026-11-23).

## Market-move flags v2f-2: the record by flag (2026-11-23)

`scripts/sharps_v2/flags_v2.py` now publishes two flags beside each shown play (`markets[g].v2.flags`, `docs/side-cards.md` "Market-move flags"): **Flag A**, whether
Pinnacle's no-vig price for the side moved toward or away from it at the same line over the 24 hours before the cut, and **Flag C**, whether the market moved the number
(spreads, totals) or the books moved the price (moneylines). Pinnacle's limit is a fact line (from, to), not a flag (user decision D1). Nothing already stored changes:
the history below is derived **point in time** from the tape rows at or before each play's cut (`scripts/sharps_v2/flag_record.py`, printed by
`tier_history.py`), nothing from the result. Every number is **in-sample** (the flag rule was written after these results), flat 1u at the stored price at the cut,
and none of it is a signal. Forward test: `docs/sharp-tier-v2-prereg.md` "Market-move flags v2f-2" (Registered 2026-11-23); forward is zero until a play is logged at lock with its flags.

**Rule change before anything shipped (v2f-1 to v2f-2).** The first draft read the start of the 24-hour window as the first stored row inside it. The tape writes a row only when a book's
numbers change, so that dropped the first move of the window, and a first quote at a new line read as a move of 0 (an invented zero). v2f-2 starts the window at the row hanging when it
opened, returns null for a first quote, takes the limit's "from" the same way, and drops a stored Pinnacle row that has its sides swapped. The thresholds were re-measured: **T_A** NFL
total 1.0 to 1.5, CBB total 1.0 to 1.5, CFB moneyline 2.0 to 2.5 (the other nine are unchanged); **T_C** CFB spread 1.0 to 1.5, CFB total 1.0 to 1.5 (the other six are unchanged). Old (v2f-1) against
new (v2f-2) on the same 205 plays: headline A away 8-6, +0.92u (n=14) to 7-7, -1.02u (n=14); headline C toward 8-3, +2.78u (n=11) to 8-4, +1.78u (n=12); NBA C toward 4-2, +0.37u (n=6) to 4-3, -0.63u (n=7);
NFL A away 1-1, -0.06u to 0-2, -2.00u; CFB A toward 4-6 (n=10) to 5-6 (n=11), A away 2-4 (n=6) to 4-4 (n=8), C toward 5-6 (n=11) to 4-6 (n=10), C away 1-8 (n=9) to 1-6 (n=7); every other cell is the same.
Two slices that improved under v2f-1 (headline A away, NBA C toward) no longer do.

**A second fix in the same rule (window start across lines), before anything shipped.** v2f-2 as first written filtered Pinnacle's rows to the current line BEFORE picking the row showing when the window opened, so a quote
at the current line from days ago became "from" when a different line was showing at the window start (home spread -3.5 three days ago, -3 two days ago, -3.5 an hour ago read as a 6-point move from a 72-hour-old
quote; real cases cfb-miaoh-kentst total and cfb-ncar-vir spread). The start is now picked across all lines and, when it is at another line, `from` is the first earlier quote at the current line inside the window or the
flag is null. Two cells moved, none on the headline: CFB A away 4-4, -0.29u, n=8 to 3-4, -1.36u, n=7; CFB no flag fired 11-9, -0.66u, n=20 to 12-8, +1.40u, n=20 (so that CFB slice now improves and is flagged below, n=20, small
sample). Flag A readable on CFB went from 44 to 43 plays and no other count, threshold or fire rate of Flag C changed; no threshold moved at all. Two smaller changes: every book now needs 2 or more rows to be read, for Flag A and
Flag C alike (a lone old moneyline row used to read as a move of 0 in Flag C only; no graded play changed), and the swapped-row sign check ignores spread lines within 1.5 points of pick'em (it had dropped rows in 8 NBA and 1 CBB
spread markets near -1 and +1; now it drops rows only in 4 CFB moneyline and 6 CFB spread markets, none of them graded plays).

**Data read:** `origin/pm-holders-data` at commit `7024604abfd69fa5f16df6b449b80b7a0ccc33e0` (Nov 23), tape at `origin/main` afd35efe33; 205 graded shown plays (sf, variant
all), 3 voided left out; all 205 flag reads re-derived from the tape (none stored yet). Reproduce with `python3 -I scripts/sharps_v2/tier_history.py --ref <commit>`. No graded play has a
dropped Pinnacle row.

**Coverage, outright.** Flag A is readable on 57 of 58 NBA plays, 32 of 33 NFL, **6 of 53 CBB** and 43 of 61 CFB; Flag C on 58, 33, **7 of 53 CBB** and 46 of 61 CFB. Neither is readable on 61 plays:
**CBB 46** = 8 `side_unmapped` (the card has no Vault join, so no team names; 2 of them have tape rows) + 38 with no Pinnacle row at the cut (the CBB tape began 2026-11-19 9:08 AM CT; 1 of
the 38 has US-book rows); **CFB 15** = 9 `side_unmapped` (no Vault join) + 6 with no Pinnacle row at the cut (4 of them have US-book rows). The 6 plays where only Flag A is null (NBA 1, NFL 1, CBB 1, CFB 3) are `no_same_line_history`: a first quote at the current line, or a quote at the current line only from before the window while a
different line was showing when it opened.

A play can sit in an A slice and a C slice (they are separate flags), so the slices overlap. "No flag fired" = at least one flag readable and neither toward nor away.
"Unreadable" = neither readable. "Improves" in this entry means units above 0, not better than a baseline.

| Old (the record today, no flags) | Record | n |
|---|---|---|
| NBA | 34-24, +0.10u, +0.2% | 58 |
| NFL | 22-11, +7.88u, +23.9% | 33 |
| CBB | 29-24, +4.00u, +7.5% | 53 |
| CFB (no size shown) | 29-32, -9.33u, -15.3% | 61 |
| Headline NBA + NFL + CBB | 85-59, +11.98u, +8.3% | 144 |

| New (the same plays by flag) | NBA | NFL | CBB | CFB (no size) | Headline NBA+NFL+CBB |
|---|---|---|---|---|---|
| A toward | 3-2, +0.35u, n=5 | 4-1, +1.93u, n=5 | n=0 | 5-6, -2.60u, n=11 | 7-3, +2.28u, +22.8% (se 27.8), n=10 |
| A away | 7-5, +0.98u, n=12 | 0-2, -2.00u, n=2 | n=0 | 3-4, -1.36u, n=7 | 7-7, -1.02u, -7.3% (se 27.0), n=14 |
| C toward | 4-3, -0.63u, n=7 | 3-1, +1.35u, n=4 | 1-0, +1.06u, n=1 | 4-6, -3.65u, n=10 | 8-4, +1.78u, +14.9% (se 25.5), n=12 |
| C away | 9-4, +3.75u, n=13 | 0-1, -1.00u, n=1 | n=0 | 1-6, -5.10u, n=7 | 9-5, +2.75u, +19.6% (se 26.9), n=14 |
| No flag fired | 18-14, -2.49u, n=32 | 17-8, +7.09u, n=25 | 3-3, -0.38u, n=6 | 12-8, +1.40u, n=20 | 38-25, +4.22u, +6.7% (se 11.7), n=63 |
| Unreadable | n=0 | n=0 | 25-21, +3.32u, n=46 | 8-7, -0.61u, n=15 | 25-21, +3.32u, +7.2% (se 14.9), n=46 |

The headline totals are unchanged by construction: every play is in "A or C fired", "No flag fired" or "Unreadable" (a play with both flags fired sits in two slices, so the slice counts add to
more than 144). Against the spec's first draft (`docs/sharps-v2-flags-spec.md`, section 2.4 as first written, flags read under v2f-1 on an older data commit) the CFB "C away" cell was 2-8, n=10: that draft
read Flag C on games with no Pinnacle row, which this build requires (the gap is not tape growth; older tape snapshots give the same result).

**Flagged for close monitoring: every flag slice whose record improves, with its n** ("improves" = units above 0; "small sample" under n=30; all in-sample, none promoted, none a signal; the list is the
output of `tier_history.py`):

| Slice | Record | n | se (points of ROI) |
|---|---|---|---|
| NBA A toward | 3-2, +0.35u | 5, small sample | 45.5 |
| NBA A away | 7-5, +0.98u | 12, small sample | 29.2 |
| NBA C away | 9-4, +3.75u | 13, small sample | 27.3 |
| NFL A toward | 4-1, +1.93u | 5, small sample | 35.8 |
| NFL C toward | 3-1, +1.35u | 4, small sample | 45.8 |
| NFL no flag fired | 17-8, +7.09u | 25, small sample | 18.7 |
| CFB (no size) no flag fired | 12-8, +1.40u | 20, small sample | 20.5 |
| CBB C toward | 1-0, +1.06u | 1, small sample | none (n=1) |
| CBB unreadable | 25-21, +3.32u | 46 | 14.9 |
| Headline A toward | 7-3, +2.28u | 10, small sample | 27.8 |
| Headline C toward | 8-4, +1.78u | 12, small sample | 25.5 |
| Headline C away | 9-5, +2.75u | 14, small sample | 26.9 |
| Headline no flag fired | 38-25, +4.22u | 63 | 11.7 |
| Headline unreadable | 25-21, +3.32u | 46 | 14.9 |

Read it plainly: the flagged slices run both ways. NBA "C away" (the market moved the number against the play's side) is the best NBA slice at +3.75u, which is the opposite
of reading a flag as a signal. The standard errors of the flagged slices run from 11.7 to 45.8 points of ROI (the CBB n=1 slice has none), so none separates from zero or from another
slice, and no slice has a sample near the 300 plays per sport that the prereg needs. The flags describe what the market did; they say nothing about whether a play wins.

## Move grade mg-1: the record by letter (2026-11-24)

`scripts/sharps_v2/move_grade.py` now gives each shown play a **Move grade** (`markets[g].v2.move_grade`, `docs/side-cards.md` "Move grade"): a letter A to D for how far the market
moved **toward** the play in the 24 hours before the cut, read only from the two registered market-move flags (Flag A, Pinnacle's no-vig price at the same line; Flag C, the market's number or the books'
price on a moneyline). A flag fired **against** the play shows "moved against" and no letter; neither flag readable shows no grade. Pinnacle's limit is never an input. It is a shadow: it changes no size
(flat 1u on NBA, NFL, CBB, none on CFB), no tier, no gate and no total. Nothing already stored changes: the history below is derived **point in time** from the tape rows at or before each play's cut
(`scripts/sharps_v2/move_grade_record.py`, printed by `tier_history.py`, reproduced with `scripts/sharps_v2/move_grade_history.py`), nothing from the result. Every number is **in-sample** (the rule was written
after these results), flat 1u at the stored price at the cut, and none of it is a signal. Forward test: `docs/sharp-movegrade-prereg.md` (**Registered 2026-11-24**). The forward record is zero by rule while it is proposed: a play counts as forward only when its grade was logged at lock
AND its cut is after the registering commit (`REGISTERED_CUT` in `move_grade_record.py`, set when the user registered on 2026-11-24), so plays logged before registration never count. The page's Forward view says so.

**Cutoffs (points), from the size of 24 hour moves on every started game of the tape, never from results** (C mark = median move, B mark = the registered flag threshold, A mark = 95th percentile and at least half a point past
the flag threshold; `move_grade_history.py` prints the distribution and checks every mark equals the table in `move_grade.py`):

| Sport, market | C mark (price) | B mark T_A | A mark (price) | C mark (line) | B mark T_C | A mark (line) |
|---|---|---|---|---|---|---|
| NBA moneyline | 2.0 | 4.0 | 9.0 | | | |
| NBA spread | 0.5 | 1.5 | 2.0 | 1.0 | 2.0 | 3.5 |
| NBA total | 1.0 | 1.5 | 2.5 | 1.5 | 3.0 | 4.0 |
| NFL moneyline | 0.5 | 1.5 | 3.0 | | | |
| NFL spread | 1.0 | 1.5 | 2.5 | 0.5 | 1.0 | 1.5 |
| NFL total | 0.5 | 1.5 | 2.5 | 0.5 | 1.0 | 1.5 |
| CBB moneyline | 1.0 | 3.0 | 4.5 | | | |
| CBB spread | 1.0 | 1.5 | 2.5 | 0.5 | 1.0 | 2.0 |
| CBB total | 0.5 | 1.5 | 2.5 | 1.0 | 2.5 | 4.0 |
| CFB moneyline | 1.0 | 2.5 | 4.5 | | | |
| CFB spread | 0.5 | 1.5 | 2.5 | 0.5 | 1.5 | 2.5 |
| CFB total | 0.5 | 1.5 | 2.0 | 0.5 | 1.5 | 2.0 |

**Letter shares on the population** (both sides of every started market, 5,454 sides, tape at `origin/main` `a6b75ea6c404`, % of sides with a grade or the marker): A 240 (4.6%), B 630 (12.0%), C 909 (17.3%), D 2,561 (48.8%),
moved against 904 (17.2%), no grade 210. By sport A runs 3.3% to 5.1%, B 10.5% to 13.9%, C 15.4% to 19.0%, D 45.6% to 53.4%, moved against 13.8% to 19.5%.

**Data read:** `origin/pm-holders-data` at commit `f2eac1ad6739dad7d1a827962eb8bab4bcfff2d7` (Nov 23, 6:32 PM CT); 205 graded shown plays (sf, variant all), 3 voided left out; all 205 grades re-derived from the tape (none stored yet).
Reproduce with `python3 -I scripts/sharps_v2/move_grade_history.py --ref f2eac1ad6739 --book-tape <tape at a6b75ea6c404>`. The no-grade reasons: CBB 46 = 8 `side_unmapped` + 38 cut before Pinnacle rows existed for the game; CFB 15 = 9
`side_unmapped` + 6 with no Pinnacle row at the cut. CBB is readable on only 7 of 53 plays; forward the CBB tape exists, so forward CBB plays will mostly get a letter.

| Old (the record today, no grade) | Record | n |
|---|---|---|
| NBA | 34-24, +0.10u, +0.2% | 58 |
| NFL | 22-11, +7.88u, +23.9% | 33 |
| CBB | 29-24, +4.00u, +7.5% | 53 |
| CFB (no size shown) | 29-32, -9.33u, -15.3% | 61 |
| Headline NBA + NFL + CBB | 85-59, +11.98u, +8.3% | 144 |
| All four | 114-91, +2.66u, +1.3% | 205 |

| New (by Move grade) | NBA | NFL | CBB | CFB (no size) | Headline NBA+NFL+CBB | All four |
|---|---|---|---|---|---|---|
| A | 0-3, -3.00u, -100.0% (se 0.0), n=3 | 4-0, +3.22u, +80.6% (se 10.4), n=4 | n=0 | 2-2, -0.12u, -2.9% (se 56.1), n=4 | 4-3, +0.22u, +3.2% (se 36.9), n=7 | 6-5, +0.11u, +1.0% (se 29.4), n=11 |
| B | 5-1, +2.27u, +37.9% (se 30.1), n=6 | 1-1, -0.43u, -21.3% (se 78.7), n=2 | 1-0, +1.06u, n=1 (no se) | 4-7, -4.65u, -42.3% (se 24.4), n=11 | 7-2, +2.91u, +32.3% (se 26.6), n=9 | 11-9, -1.74u, -8.7% (se 19.5), n=20 |
| C | 3-3, +1.12u, +18.7% (se 54.0), n=6 | 5-1, +4.90u, +81.7% (se 37.4), n=6 | 2-0, +1.56u, +77.9% (se 41.9), n=2 | 5-3, +0.59u, +7.4% (se 31.7), n=8 | 10-4, +7.58u, +54.1% (se 28.3), n=14 | 15-7, +8.17u, +37.2% (se 21.5), n=22 |
| D | 15-11, -3.61u, -13.9% (se 15.3), n=26 | 12-7, +2.19u, +11.5% (se 20.6), n=19 | 1-3, -1.94u, -48.5% (se 51.5), n=4 | 7-5, +0.81u, +6.8% (se 27.9), n=12 | 28-21, -3.37u, -6.9% (se 12.1), n=49 | 35-26, -2.55u, -4.2% (se 11.1), n=61 |
| Moved against | 11-6, +3.32u, +19.5% (se 23.8), n=17 | 0-2, -2.00u, -100.0% (se 0.0), n=2 | n=0 | 3-8, -5.36u, -48.7% (se 26.5), n=11 | 11-8, +1.32u, +6.9% (se 22.9), n=19 | 14-16, -4.04u, -13.5% (se 17.9), n=30 |
| No grade | n=0 | n=0 | 25-21, +3.32u, +7.2% (se 14.9), n=46 | 8-7, -0.61u, -4.1% (se 24.5), n=15 | 25-21, +3.32u, +7.2% (se 14.9), n=46 | 33-28, +2.71u, +4.4% (se 12.6), n=61 |

Every play sits in exactly one row, so each column adds up to its old total (the headline: 7 + 9 + 14 + 49 + 19 + 46 = 144 plays, +0.22 + 2.91 + 7.58 - 3.37 + 1.32 + 3.32 = +11.98u).

ROI in these tables and on the Record page is the flat sum of the unrounded results over n (A headline +3.2%, B +32.3%, moved against +6.9%), not the rounded units over n; the page shows the same numbers. SE is one standard error of the per-play result in points of ROI. "Small sample" is under 30 plays here and on the page, one definition.

The prereg's metrics on the same plays (headline, in-sample, report only): market move after the cut, mean points (se), n with a same-line close: A 0.00 (0.00) n=7, B +0.10 (0.23) n=9, C +0.04 (0.04) n=14, D +0.05 (0.08) n=48,
moved against -0.53 (0.23) n=19; Pinnacle CLV (overlaps the inputs by construction): A -1.40 n=5, B -0.04 n=8, C -0.13 n=9, D -0.37 n=33, moved against +1.05 n=14. The move after the cut covers only the 15 minutes from the cut to the start:
91 of the 143 graded plays with a readable move moved exactly 0. Slope of that move on the letter (D=0, C=1, B=2, A=3), 95% bootstrap, 10,000 resamples, seed 20261111: NBA +0.065 [-0.077, +0.234] n=41; NFL -0.089 [-0.260, +0.054] n=30;
CBB +0.027 [-0.007, +0.230] n=7; CFB +0.110 [-0.066, +0.296] n=35; headline -0.002 [-0.099, +0.098] n=78. Every interval spans 0.

**Flagged for close monitoring: every cell that improves, with its n** ("improves" = units above 0; "small sample" under n=30; all in-sample, none promoted, none a signal; the list is the output of `tier_history.py`):

| Cell | Record | n | se (points of ROI) |
|---|---|---|---|
| NBA B | 5-1, +2.27u | 6, small sample | 30.1 |
| NBA C | 3-3, +1.12u | 6, small sample | 54.0 |
| NBA moved against | 11-6, +3.32u | 17, small sample | 23.8 |
| NFL A | 4-0, +3.22u | 4, small sample | 10.4 |
| NFL C | 5-1, +4.90u | 6, small sample | 37.4 |
| NFL D | 12-7, +2.19u | 19, small sample | 20.6 |
| CBB B | 1-0, +1.06u | 1, small sample | none (n=1) |
| CBB C | 2-0, +1.56u | 2, small sample | 41.9 |
| CBB no grade | 25-21, +3.32u | 46 | 14.9 |
| CFB (no size) C | 5-3, +0.59u | 8, small sample | 31.7 |
| CFB (no size) D | 7-5, +0.81u | 12, small sample | 27.9 |
| Headline A | 4-3, +0.22u | 7, small sample | 36.9 |
| Headline B | 7-2, +2.91u | 9, small sample | 26.6 |
| Headline C | 10-4, +7.58u | 14, small sample | 28.3 |
| Headline moved against | 11-8, +1.32u | 19, small sample | 22.9 |
| Headline no grade | 25-21, +3.32u | 46 | 14.9 |
| All four A | 6-5, +0.11u | 11, small sample | 29.4 |
| All four C | 15-7, +8.17u | 22, small sample | 21.5 |
| All four no grade | 33-28, +2.71u | 61 | 12.6 |

**The honest read: the letter does not order the results in-sample.** On the headline, C is the best letter (+7.58u, n=14), A is close to flat (+0.22u, n=7) and D is negative (-3.37u, n=49); in NBA, A went 0-3 while the plays the market moved **against** went 11-6,
+3.32u. Over all four sports A (+0.11u) sits below C (+8.17u) and B is negative (-1.74u). The after-cut move does not order either (headline slope -0.002, interval -0.099 to +0.098). The standard errors run from 10.4 to 78.7 points of ROI (the all-loss cells and the n=1 cell have none
worth the name), so no cell separates from zero or from another. This matches what the flags already showed ("Market-move flags v2f-2" above): they describe the market and have not ordered results. The Move grade is a tidier way to read the same two flags, not new evidence, and the page must not
present it as anything more.

## Spread context on moneyline plays (2026-11-24)

Moneyline plays now carry a **spread fact line** (`v2.spread_ctx`, written up in `docs/side-cards.md` "Spread context"): Pinnacle's spread line for the play's side from and to over the 24 hours before the cut, and how many books
moved toward or away from the side. **It is not tracked and not graded.** There is no record by it, no slice, no row in `tier_record.json`, `flag_record.json` or `move_grade_record.json`, and no count of any kind; the forward log keeps it
(`sc`, `sc_why`) only so a frozen card can be read back as it was shown. It changes no number on this page: not a tier, a size, a Move grade or a result. It carries no claim about results.
