# Sharps V2 grader changes: what to build, with evidence (2026-11-24)

The plays spec (`docs/sharps-v2-plays-spec.md`, section 5.3 and the table at the top) lists four pieces of grader work: `pinclose` rows, a `v2_tier` and a `shown`
section per sport in `cards_record.json`, and a new `pm_record/v2_tier_record.json`. Before building them as specified this note checks each against what already
exists. Data read: `pm-holders-data` at commit `309fe8039b7d` (Nov 24, 6:06 PM CT, 225 graded shown plays: sf, variant all, status graded; voided and unpriced left out)
and the book tape in `origin/main` at `2066d9a0a57` (Nov 24, 6:00 PM CT). Every number below is in-sample, a record and not a signal.

## Verdict

| Piece | Verdict | Why |
|---|---|---|
| `pinclose` rows | **Build** (corrected after review: see "Corrections after review") | Pinnacle's close is stored nowhere. The Record page's "vs the close" reads Polymarket close rows only, which exist for NBA and NFL and never for CBB or CFB. The per-tier and per-play Pinnacle numbers are derived from the tape every time by `tier_history.py` and `move_grade_history.py`, never stored. |
| `cards_record.json` `v2_tier` | **Skip** | Redundant. `tier_record.json` (published on `pm-cards-live` every 10 minutes, the file the Record page reads) already holds every flat cell the spec lists, per sport and tier, split in-sample and forward from the tier log. The only thing it lacks is CLV, which comes from the new rows. |
| `cards_record.json` `shown` | **Skip** | `today_rule` is the existing flat sums of the `sf` rows. `at_the_time` (the size the page showed at each cut) is computed by `tier_history.py` and written up in `docs/side-card-record.md`; no page or file reads it. Nothing is missing that a stored section would fix. |
| `pm_record/v2_tier_record.json` | **Skip** | A second copy of `tier_record.json` under another name. Nothing reads `live.json` `v2_tier_record` (no JS or Python reader), the Record page reads `tier_record.json`, and the builder's `--v2-tier-record` flag (already in `build_side_cards.py` and `pm-cards.yml`) stays inert, as it is today. |
| A per-sport summary of the new rows | **Build, small** | `pm_record/pinclose_record.json`: how many graded plays have a stored close, why the rest do not, mean CLV and move with one standard error. This is not a tier record; the prereg asks every read to report "counts without a readable close or move by reason". |
| Per-tier Pinnacle CLV | **Report, not a file** | `scripts/sharps_v2/pinclose_history.py` reads the stored rows and prints it by sport and tier (it is how this PR's numbers were made). Publishing it in `tier_record.json` would be a UI decision (see "Record page" below), so it is not done here. |

## What the grader sections would add that `tier_record.json` does not

`tier_record.json` per sport and tier holds `w, l, p, n, units, roi`, the `shadow` block, and the buckets `all`, `in_sample`, `forward`, `since_nov16`, `by_market`
(checked on the file live on `pm-cards-live`: no CLV key anywhere). The spec's `v2_tier` would repeat those cells and add `clv_n, clv_mean, clv_ci` and
`derived_differs`. So the whole added value of `v2_tier` and `v2_tier_record.json` is CLV by tier, and that is a function of the new rows, not of a second record.
`derived_differs` (the prereg's data-quality kill rule: forward log rows whose tier differs from a re-derivation) is a read-time check for the final read, not something
the grader should store, because a later re-derivation is exactly what it compares against.

## Can the Record page's "vs the close" already be computed from stored data?

The page (`sv2-record.js`, `rec.closeMap` and `rec.tally`) reads `kind: "close"` rows, which are **Polymarket** closes from `data/pm_closes.json`.

| Sport | Graded shown plays | Stored Polymarket close | Stored Pinnacle close (new rows) | Pinnacle price-vs-close readable (at the ticket's line) | ... of which the close is AFTER the cut |
|---|---|---|---|---|---|
| NBA | 69 | 69 | 69 | 58 | 28 |
| NFL | 33 | 33 | 33 | 19 | 4 |
| CBB | 62 | **0** | 17 | 9 | 2 |
| CFB (no size shown) | 61 | **0** | 46 | 25 | 14 |
| All | 225 | 102 | 165 | 111 | 48 |

So for plays: yes for NBA and NFL (Polymarket's close), no for CBB, a sport whose plays the page shows: every CBB play reads "No closing price stored yet". For tiers: no. The tier table reads
`tier_record.json`, which has no CLV, so no tier has a "vs the close" number at all.

**Most Pinnacle "closes" are not closes.** The tape writes a row only when a number changes, so the last Pinnacle row at or before the start is often the row the cut already saw, or an older one.
Of the 165 stored closes, **98 (59%) are at or before the cut** (NBA 38 of 69, NFL 25 of 33, CBB 14 of 17, CFB 21 of 46), and 25 are more than an hour old at the start (NFL 18 of 33, up to 6.8 hours).
For those the number is the price against Pinnacle's fair **at the cut**, not CLV against a close, so every statistic keeps the two apart: `clv` counts closes after the cut only (48 plays), and
`price_vs_fair_at_cut` (63 plays) is reported under that name.

**The NFL comparison with Polymarket's close, restated.** An earlier version of this note said that on the 18 NFL plays with both closes Polymarket's close read +0.56 and Pinnacle's -0.59, and
leaned on Pinnacle as the sharper reference. That comparison is mostly Pinnacle reads at or before the cut (14 of those 18, up to 6.8 hours stale), which is not a closing line. On the 19 NFL plays with both
(one more after the side-line fix), restricted to closes after the cut there are **4**: Polymarket's close +0.75 points, Pinnacle's close +0.12 (se 0.59). Four plays say nothing, and the claim that Pinnacle is the
better reference, or that a play beating Polymarket's close but not Pinnacle's is a case the Record should hide, is **withdrawn**: it is not supported on closes after the cut. On NBA, 28 plays have both and a close after the cut:
Polymarket -0.07 (se 0.11), Pinnacle -0.19 (se 0.13).

## Where `pinclose` closes are missing today (225 graded plays)

| Reason (stored on the row) | NBA | NFL | CBB | CFB |
|---|---|---|---|---|
| `no_tape_rows_for_game` (the tape has no Pinnacle row for the game; the CBB tape starts Nov 19, 9:08 AM CT) | 0 | 0 | 45 | 15 |
| close stored, but not at the ticket's line (`ticket_line_not_main_at_close`) | 11 | 14 | 8 | 21 |
| close and price-vs-close readable | 58 | 19 | 9 | 25 |

A spread or total whose ticket line is not Pinnacle's main line at the close keeps its close and `close_line` (a stored tape value) and gets a null CLV with the reason. Nothing is estimated.
Before the side-line fix (next sections) the "not at the ticket's line" cells were NBA 14, NFL 15, CBB 7, CFB 23 and the readable cells NBA 55, NFL 18, CBB 8, CFB 23.

## Why store it when the tape is in the repo

The tape holds Pinnacle's rows, so every number here can be re-derived (the cross-check below confirms it). Three reasons to store the close anyway:
(1) CLAUDE.md says to use "a stored closing-line value"; a derivation from a plain file in `main` can change when that file is repaired (`scripts/clean_book_tape_outliers.py`
already rewrote stored tape rows once, though it never touches Pinnacle) and a record should not move without a commit to the record;
(2) the Record page reads only `pm-holders-data` files, so a stored row is the only way it could ever show a Pinnacle close without shipping a 40 MB tape;
(3) the registered tests (`docs/sharp-tier-v2-prereg.md`, "Primary metric" and the flags section) name "the grader's `pinclose` row" as the source of the close, and
the move after the cut. That sentence is in a frozen file and says the grader work "is not built yet"; this PR is that work, and the prereg is not edited.
The cost is 156 KB of rows across the four month files (+47 KB NBA, +23 KB NFL, +42 KB CFB, +44 KB CBB, about 690 bytes a row), a 10 KB summary file and one fail-soft workflow step.

## What was built

- `scripts/sharps_v2/pinclose.py`: appends `<sf key>|pinclose` rows (kind `pinclose`), once per graded shown play, after the result row and at least 30 minutes after game start.
  Fields: `close_fair, close_t, close_line` (Pinnacle's last readable tape row at or before game start, inclusive), `close_age_min`, `close_after_cut`, `tape_last_t`, `tape_age_min`, `price` (the stored
  price at the cut), `line` (the stored Polymarket line, for outcomes[0]) and `side_line` (the play's own line), `clv` and `pts` (close fair minus price, in probability and points),
  `fair_cut, line_cut` and `move_pts` (the market move after the cut), and `why` / `move_why` (the stored reason when null). The read uses `flags_v2._reads`: the same side mapping (home, away, over, under
  from the card's own team names) and two-way multiplicative no-vig the flags use. A row is **held, not written**, when the sport's tape (any book) does not run past the game's start, the card file is
  missing, or the side cannot be mapped to a team while the game has tape rows. A null row is final and stores its reason; a `0.0` move is stored only when the tape saw a row between the cut and the start.
- `scripts/grade_side_cards.py` and `scripts/benchmark_h2h.py`: the three places that read every row kind but `close` now also skip `pinclose`. Without that the grader's
  `record()` raises `KeyError: 'play'` on the first new row (verified on the real data). Nothing else in either file moves.
- `.github/workflows/pm-record.yml`: one step between the grade and the benchmark steps, skipped with the rest when there is no holders data, running the new tests and the
  script, each failing soft with a warning. No workflow pushes to a new branch: the rows ride the existing `pm record` commit to `pm-holders-data`.
- `pm_record/pinclose_record.json` (written by the same step, by `save_record`, so an idle run makes no commit).
- `scripts/sharps_v2/pinclose_history.py`: the by-sport and by-tier report, an independent re-derivation of every stored row from the raw tape (own arithmetic, explicit side line, 165 of 165 agree,
  0 differ), and a cross-check against the two on-the-fly reads (`tier_history.pin_close_pts` for CLV, `move_grade_history.after_moves` for the move), which is **not** independent (next section).

## Corrections after review (2026-11-24, before any row was written to the data branch)

1. **The ticket line was the wrong sign for outcomes[1] plays.** The stored `line` is Polymarket's line for outcomes[0] (the page says so: "the stored line belongs to the first outcome"). The first version compared
   Pinnacle's own line for the side with it, so a spread play on outcomes[1] read as "ticket line not main at close" when it was main (nba-mem-cha-2026-11-23, Hornets, stored -2.5, Pinnacle +2.5: now `pts` -0.66).
   The comparison now uses `side_line` (the stored line for outcomes[0], its negative for outcomes[1]; a total's line is the same for both; unreadable gives `ticket_line_unknown`, never a guess).
   Seven spread plays changed from "not at the ticket's line" to readable (NBA 3: atl-mil Bucks, hou-was Wizards, mem-cha Hornets; NFL 1: jax-ten Titans; CFB 2: byu-kan Kansas, smu-nd SMU; CBB 1: Loyola Maryland, which also needed fix 4).
   Sign audit on the 48 spread rows with a close line: outcomes[0] sides equal the side's own line 7 times and its negative 0 times; outcomes[1] sides equal it 7 times and the negative 0 times; the stored Polymarket line equals
   Pinnacle's line for outcomes[0] sides 7 times and for outcomes[1] sides 0 times (its negative 7 times).
   **The same flaw is in two frozen reads, which are not changed here:** `scripts/sf_signals.py` `ev_read` is called with the card's `sf.line` as the ticket line, so `tier_history.pin_close_pts`, `build_side_cards.card_signals` and with them
   the stored `sf.signals.ev` (the tier facts a4 and b2, and the Move/flag history that read them) report "ticket line not main at cut" on outcomes[1] spread plays whose line is main. Plays whose price check was wrongly
   unreadable for that reason are 7 of the 225 on the CLV side alone; how many a4/b2 facts and tiers that moves has not been measured and is not fixed here (a tier rule change is a new registration). That is why the cross-check
   against `tier_history` is no proof: it shares the flaw (7 of its 7 disagreements, all "stored only", are outcomes[1] spread plays). The independent check above is the proof.
2. **A close at or before the cut is not a close, and a tape that saw nothing is not a zero.** Each row now stores `close_age_min`, `close_after_cut` and the tape's liveness (`tape_last_t`, the last row of ANY book for the sport at or before
   start, and `tape_age_min`). `move_pts` is null with `move_why: "no_pinnacle_tape_after_cut"` when no Pinnacle row of any game of the sport lies between the cut and the start (see item 5) (it was a stored 0.0 before: nfl-ne-det-2026-11-15 had a close 6.8 hours before kickoff).
   Decision: a close at or before the cut is **stored** (the price against Pinnacle's fair at the cut is information) but flagged `close_after_cut: false`, and **excluded from every statistic labelled CLV vs the close**; the record
   and the report give it separately as `price_vs_fair_at_cut`. The stale-close share by sport is in `pinclose_record.json` (`close_after_cut.false_share`, `older_than_60_min`) and in the Record docs.
   Reading the liveness: a tape outage across a kickoff **is** detectable: no row from any book in the window, and no tape commits (`tape_age_min` large, `move_why` `no_pinnacle_tape_after_cut`); the row records it and the held rule stops a stale
   checkout from becoming a final null.
3. **A prereg gap found in review, not implemented here.** `docs/sharp-tier-v2-prereg.md` (the data-quality kill rule: more than 5% of forward log rows whose tier differs from a re-derivation from the stored card) is implemented nowhere yet.
4. **Side mapping.** A side the card names differently from the tape ("Loyola Maryland Greyhounds" against "Loyola (MD)") now resolves by complement on a two-sided moneyline or spread: when the other side maps to a team this side is the opposite one.
   Of the 225 plays, the old mapping could not map 18 sides (2 CBB plays with tape, 16 without tape); with the complement 3 resolve (Loyola Maryland, "Delaware Fightin' Blue Hens", and one CBB play with no tape) and the remaining 15 (6 CBB, 9 CFB) have no tape
   rows for the game at all, so their final `no_tape_rows_for_game` null does not depend on the names. A side that cannot be mapped while the game HAS tape rows is held, not written (none in this data).
5. **The move's liveness is Pinnacle-only.** The first review fix counted a row of ANY book in the cut-to-start window as proof the tape was alive. Pinnacle's rows sit on a 10 to 20 minute grid in the same feed while other books write in between, so a DraftKings row does not show Pinnacle was re-read.
   `move_pts` now needs at least one Pinnacle row of the sport in (cut, start], else null with `no_pinnacle_tape_after_cut`; `pin_last_t` / `pin_age_min` are stored beside `tape_last_t` / `tape_age_min` (any book, unchanged). Ten stored zeros became nulls (NBA 6, CBB 1, CFB 3): moves readable 94 to 84.

## Record page

No UI change in this PR. The page reads only `result` and `close` rows (`sv2-record.js`), so the new rows are inert there (checked on the real rows: tally, per-sport records, latest
list and frozen list are identical with and without the 225 new rows). Showing the Pinnacle close next to the Polymarket close is a design decision, not plumbing: the label "vs the close" is
Polymarket's today, only 48 of 225 plays have a Pinnacle close after the cut (NFL 4, CBB 2), and the rest are prices against Pinnacle's fair at the cut. It needs its own label, a small-sample tag, and a decision
on whether tiers get a column. Recommended once forward CBB has a few dozen plays with a close after the cut.
