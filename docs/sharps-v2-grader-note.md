# Sharps V2 grader changes: what to build, with evidence (2026-11-24)

The plays spec (`docs/sharps-v2-plays-spec.md`, section 5.3 and the table at the top) lists four pieces of grader work: `pinclose` rows, a `v2_tier` and a `shown`
section per sport in `cards_record.json`, and a new `pm_record/v2_tier_record.json`. Before building them as specified this note checks each against what already
exists. Data read: `pm-holders-data` at commit `309fe8039b7d` (Nov 24, 6:06 PM CT, 225 graded shown plays: sf, variant all, status graded; voided and unpriced left out)
and the book tape in `origin/main` at `2066d9a0a57` (Nov 24, 6:00 PM CT). Every number below is in-sample, a record and not a signal.

## Verdict

| Piece | Verdict | Why |
|---|---|---|
| `pinclose` rows | **Build** | Pinnacle's close is stored nowhere. The Record page's "vs the close" reads Polymarket close rows only, which exist for NBA and NFL and never for CBB or CFB. The per-tier and per-play Pinnacle numbers are derived from the tape every time by `tier_history.py` and `move_grade_history.py`, never stored. |
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

| Sport | Graded shown plays | With a stored Polymarket close | With a stored Pinnacle close (new rows) | Pinnacle CLV readable (close at the ticket's line) |
|---|---|---|---|---|
| NBA | 69 | 69 | 69 | 55 |
| NFL | 33 | 33 | 33 | 18 |
| CBB | 62 | **0** | 15 | 8 |
| CFB (no size shown) | 61 | **0** | 46 | 23 |
| All | 225 | 102 | 163 | 104 |

So for plays: yes for NBA and NFL (Polymarket's close), no for CBB, a sport whose plays the page shows: every CBB play reads "No closing price stored yet". For tiers: no.
The tier table reads `tier_record.json`, which has no CLV, so no tier has a "vs the close" number at all.

The two closes are different measurements, and on the plays that have both they can disagree. On the 55 NBA plays with both: Polymarket close +0.04 points (se 0.11),
Pinnacle close +0.05 (se 0.22). On the 18 NFL plays with both: Polymarket close **+0.56** (se 0.17), Pinnacle close **-0.59** (se 0.24); the sign flips on 9 of 18. Pinnacle is
the sharper reference, and a play that beats Polymarket's own close but not Pinnacle's is the case the Record should not hide. That is a reason to store it.

## Where `pinclose` closes are missing today (225 graded plays)

| Reason (stored on the row) | NBA | NFL | CBB | CFB |
|---|---|---|---|---|
| `no_tape_rows_for_game` (the tape has no Pinnacle row for the game; CBB tape starts Nov 19, 9:08 AM CT) | 0 | 0 | 45 | 15 |
| `side_unmapped` (the card's team names do not map to home or away) | 0 | 0 | 2 | 0 |
| close stored, but not at the ticket's line (CLV null, `ticket_line_not_main_at_close`; the move after the cut is still readable on most) | 14 | 15 | 7 | 23 |
| close and CLV readable | 55 | 18 | 8 | 23 |

Forward the CBB tape exists, so forward CBB plays will mostly be readable. A spread or total whose ticket line is not Pinnacle's main line at the close keeps its close and
`close_line` (a stored tape value) and gets a null CLV with the reason; it is never estimated.

## Why store it when the tape is in the repo

The tape holds Pinnacle's rows, so every number here can be re-derived (the cross-check below confirms it). Three reasons to store the close anyway:
(1) CLAUDE.md says to use "a stored closing-line value"; a derivation from a plain file in `main` can change when that file is repaired (`scripts/clean_book_tape_outliers.py`
already rewrote stored tape rows once, though it never touches Pinnacle) and a record should not move without a commit to the record;
(2) the Record page reads only `pm-holders-data` files, so a stored row is the only way it could ever show a Pinnacle close without shipping a 40 MB tape;
(3) the registered tests (`docs/sharp-tier-v2-prereg.md`, "Primary metric" and the flags section) name "the grader's `pinclose` row" as the source of the close, and
the move after the cut. That sentence is in a frozen file and says the grader work "is not built yet"; this PR is that work, and the prereg is not edited.
The cost is 121 KB of rows across the four month files (+36 KB NBA, +17 KB NFL, +33 KB CFB, +35 KB CBB, about 540 bytes a row), a 6 KB summary file and one fail-soft workflow step.

## What was built

- `scripts/sharps_v2/pinclose.py`: appends `<sf key>|pinclose` rows (kind `pinclose`), once per graded shown play, after the result row and at least 30 minutes after game start.
  Fields: `close_fair, close_t, close_line` (Pinnacle's last readable tape row at or before game start, inclusive), `price` (the stored price at the cut), `clv` and `pts`
  (close fair minus price, in probability and points), `fair_cut, line_cut` and `move_pts` (the market move after the cut), and `why` / `move_why` (the stored reason when
  null). The read uses `flags_v2._reads`: the same side mapping (home, away, over, under from the card's own team names) and two-way multiplicative no-vig the flags use. A row
  is **held, not written null**, when the sport's tape does not run past the game's start (a stale or missing checkout must never become permanent null rows) or the card file
  is missing.
- `scripts/grade_side_cards.py` and `scripts/benchmark_h2h.py`: the three places that read every row kind but `close` now also skip `pinclose`. Without that the grader's
  `record()` raises `KeyError: 'play'` on the first new row (verified on the real data), which is why this edit is part of the same PR as the rows. Nothing else in either file moves.
- `.github/workflows/pm-record.yml`: one step between the grade and the benchmark steps, skipped with the rest when there is no holders data, running the new tests and the
  script, each failing soft with a warning. No workflow pushes to a new branch: the rows ride the existing `pm record` commit to `pm-holders-data`.
- `pm_record/pinclose_record.json` (written by the same step, by `save_record`, so an idle run makes no commit).
- `scripts/sharps_v2/pinclose_history.py`: the by-sport and by-tier report, with a cross-check of every stored row against the two on-the-fly reads
  (`tier_history.pin_close_pts` for CLV, `move_grade_history.after_moves` for the move): **104 of 104 CLV values and 162 of 162 moves agree to 0.01 point**, 0 differ.

## Record page

No UI change in this PR. The page reads only `result` and `close` rows (`sv2-record.js`), so the new rows are inert there (checked on the real rows: tally, per-sport records, latest
list and frozen list are identical with and without the 225 new rows). Showing the Pinnacle close next to the Polymarket close is a design decision, not plumbing: the two are
different benchmarks that disagree on NFL, the label "vs the close" is Polymarket's today, and CBB, the sport that would gain, has 8 readable plays. It needs its own label
("vs Pinnacle's close"), a small-sample tag, and a decision on whether tiers get a column. Recommended once forward CBB has a few dozen readable plays.
