# Sharps V2: the Move grade (spec)

**Status: built (PR 574) and registered 2026-11-24 (see docs/sharp-movegrade-prereg.md).** Written 2026-11-23 (Central). Rule id for everything below: **`mg-1`**. A change to any
cutoff, branch or input after the registering commit is a new rule id (`mg-2`) and a new registration.

The user's decision (2026-11-23, not relitigated here): each shown Sharps play gets a **Move grade**, a letter A to D that says how far the
market moved **toward the play** in the 24 hours before the cut. It is independent of the evidence tiers (Clear, Mixed, Thin, Contested). Its
only inputs are Flag A (Pinnacle's no-vig price move at the same line) and Flag C (the market's main line move across the stored books; the
books' price move on moneylines) of rule `v2f-2`, merged and live (`docs/sharps-v2-flags-spec.md`, #571). Pinnacle's limit stays a fact line and never
enters the grade (it rose on 98 of the 100 graded plays that have a limit read). A move **against** the play gets a separate "against" marker, never a
low letter. It is always called the **Move grade**, never a "Sharp grade". It is a **shadow**: logged at lock, given a forward record per letter, and
it changes nothing: not the shown size (flat 1u on NBA, NFL and CBB, none on CFB), not the shadow size `v2s-1`, not Top Reads, SM_GATE or any agree
total. Sharp money is context only (CLAUDE.md).

**Inputs read for every number in this file** (all read 2026-11-23, about 6:35 PM CT; every figure comes from these stored values):

| Input | Ref |
|---|---|
| Book tape (the population for the cutoffs, and the history) | `data/book_tape/<sport>/<YYYY-MM>.jsonl` at `origin/main` `a6b75ea6c404` (newest row 2026-11-23 6:28 PM CT) |
| Frozen cards and graded record | `origin/pm-holders-data` `f2eac1ad6739` (2026-11-23 6:32 PM CT): `pm_cards/<sport>/frozen`, `pm_record/cards/<sport>/2026-11.jsonl` |
| Live slate | `origin/pm-cards-live` `08f51816c637`, `live.json` built 2026-11-23 6:30 PM CT (1,079,312 bytes compact; V2 keys 66.2 KB; flags and series 6.3 KB; 7 shown plays) |
| Rule code read | `scripts/sharps_v2/flags_v2.py` (`v2f-2`, thresholds `FLAGS_T_A`, `FLAGS_T_C`), `plays_v2.py`, `flag_record.py`, `tier_history.py`, `tier_record.py`, `check_size.py`; `sharp-money/sharps-v2/sv2-sharps.js`, `sv2-record.js`, `sv2-core.js`, `sv2.css`, `embed.js` |

The measuring scripts were run with `python3 -I` on those refs (stdlib only) and are not committed by this spec; build task D1 commits them as
`scripts/sharps_v2/move_grade_history.py` and must reproduce every table here at the named refs, or this spec is corrected first.

---

## 1. The scoring rule (`mg-1`)

### 1.1 In plain terms (one sentence per letter, the page legend)

| Mark | Plain sentence |
|---|---|
| **A** | A market-move flag fired toward the play and the move passed the A mark, a size only the largest moves of the season reach in that sport and market. |
| **B** | A market-move flag fired toward the play: Pinnacle's price, or the market's number (the books' price on a moneyline). |
| **C** | No flag fired, but Pinnacle's price or line drifted toward the play by more than a typical day's move, and not that far away from it. |
| **D** | The market did not move toward the play by more than a typical day's move. |
| **Moved against** (marker, no letter) | A market-move flag fired against the play. It is shown in place of a letter, never as a low letter. |
| **No grade** (null) | Neither flag could be read at the cut (no market history stored, too few books, or the side did not map to a team). |

"Flag fired" means the registered `v2f-2` state `toward` or `away`; "typical day's move" means the median 24-hour move (section 2). The letter is a
description of what the market did. It says nothing about whether the play wins.

### 1.2 The real fields it reads

All from the stored `v2.flags` block of the play (rule `v2f-2`), plus the side's direction, which the builder already has (`norms[side]`):

| Field | Meaning | Used for |
|---|---|---|
| `flags.pin.state` | Flag A: `toward` / `away` / `quiet`, or the block is null | fired toward, against |
| `flags.pin.pts` | Pinnacle's no-vig fair move for the side at the same line, points, signed (positive = toward), stored to 2 decimals | the A mark on price, the C drift |
| `flags.line.state` | Flag C: `toward` / `away` / `quiet`, or null | fired toward, against |
| `flags.line.kind` | `line` (spread, total) or `price` (moneyline) | whether a line move exists |
| `flags.line.pin.from`, `flags.line.pin.to` | Pinnacle's main line for the side at the window start and at `asof` (side orientation) | `c_pts` below |
| `norm` (home, away, over, under) | the side | `dir` = `flags_v2._dir_sign(g, norm)`: -1 for a spread side and an under, +1 for an over |

Derived, never stored by `v2f-2` (so `mg-1` stores it): **`c_pts`** = `round(dir x (line.pin.to - line.pin.from), 2)`, Pinnacle's main-line
move toward the side in points; null on a moneyline or when `line` is null. `line.same_way`, `line.books` and `line.extreme` are **shown** in the
"how earned" line (section 7) but are not scoring inputs: Flag C's own rule already requires 2 or more US books moving the same way before it
can fire, and adding a second count would only re-weigh the same fact.

**Not an input, ever:** Pinnacle's limit (`flags.limit`), the evidence tier, the wallets, the price at the cut, `vs_fair`, the result, anything after
the cut. On a moneyline, Flag C's `by_book` holds American prices only (no no-vig fair per book is stored), so a moneyline reaches A only through
Flag A's `pts`; Flag C toward on a moneyline gives at most B.

### 1.3 Pseudocode

```
MG_RULE = "mg-1"
# cutoffs per sport and market (section 2): M = the C mark (median), X = the A mark; T_A, T_C = the registered v2f-2 thresholds
MG_M_A, MG_M_C, MG_X_A, MG_X_C          # tables in 2.3, one constant each in scripts/sharps_v2/move_grade.py

def move_grade(flags, g, norm, sport):
    if norm not in (home, away, over, under):       return null_grade("side_unmapped")
    if flags is not a dict:                          return null_grade("no_flags")          # v2.flags null (flags_error) or absent
    a = flags.pin.state  if flags.pin  else None     # toward | away | quiet | None
    c = flags.line.state if flags.line else None
    if a is None and c is None:                      return null_grade("flags_unreadable")  # why carries flags.why
    pts   = flags.pin.pts if flags.pin else None
    c_pts = round(dir_sign(g, norm) * (flags.line.pin.to - flags.line.pin.from), 2) if g != "ml" and flags.line and flags.line.kind == "line" else None
    if a == "away" or c == "away":                                                          # any flag fired against: the marker, no letter
        return {letter: None, against: True, basis: "against", against_by: [x for x in ("a","c") if state(x) == "away"], ...}
    if a == "toward" or c == "toward":                                                      # a flag fired toward
        if (a == "toward" and pts >= MG_X_A[sport][g]):                 return grade("A", basis "a_mark")
        if (c == "toward" and c_pts is not None and c_pts >= MG_X_C[sport][g]): return grade("A", basis "c_mark")
        return grade("B", basis "fired")
    drift_toward = (pts is not None and pts >=  MG_M_A[sport][g]) or (c_pts is not None and c_pts >=  MG_M_C[sport][g])
    drift_away   = (pts is not None and pts <= -MG_M_A[sport][g]) or (c_pts is not None and c_pts <= -MG_M_C[sport][g])
    if drift_toward and not drift_away:              return grade("C", basis "drift")
    return grade("D", basis "flat")
```

- Comparisons are on the stored 2-decimal values, with `>=` and `<=` inclusive, exactly as `flags_v2.state_of` does, so a stored number and its
  letter never disagree. A value exactly at a mark takes the higher letter (C at `M`, A at `X`).
- One readable flag is enough for a letter (the other is null): `basis` and the stored `a`/`c` states say which flags were read. A play with only
  Flag C readable on a moneyline can reach B at most.
- "Against" wins over "toward": a play with one flag toward and the other away (34 of the 5,454 started market sides on the tape, 0 of the 205
  graded plays) shows the against marker. Decision G1 (section 9).
- A sub-threshold drift away (Pinnacle moved away by at least `M` but no flag fired) is a **D**, not the against marker: the marker is tied to the
  registered flags only.

### 1.4 Null and never-invent rules

| Case | Result |
|---|---|
| No shown side (`v2.side` null) | no `move_grade` key at all (as `flags`) |
| `side_unmapped` | `{letter: null, against: null, why: "side_unmapped"}` |
| `v2.flags` null (`flags_error`) | `{letter: null, against: null, why: "no_flags"}` |
| Both flags null | `{letter: null, against: null, why: "flags_unreadable", flags_why: <v2.flags.why>}` |
| A threshold or mark missing for the sport and market | `{letter: null, against: null, why: "no_cutoff"}` |

Never: a letter from a 0 put in for a missing `pts` or `c_pts`, a letter from the limit, a letter from rows after the cut, a letter recomputed after the
lock, or "quiet" read as "D" when the flag was null (a null flag simply does not count; both null is no grade).

---

## 2. Cutoffs from the distribution of moves (not from results)

### 2.1 Method

Exactly the way `T_A` and `T_C` were set (`docs/sharps-v2-flags-spec.md` 1.2 and 1.4): every game on the tape that has started, the 24-hour window
ending 15 minutes before start, the `v2f-2` window rule, the home side (spread, moneyline) or the over (total), absolute values. For each sport
and market:

- **C mark** `M_A` = the **median** absolute Flag A move, rounded to the nearest 0.5 point (as `T_A`), floor 0.5. `M_C` = the median absolute Pinnacle
  main-line move, rounded **up** to the half point (as `T_C`), floor 0.5 (the smallest line step). "More than a typical day's move."
- **B mark** = the registered flag thresholds `T_A`, `T_C` (the 80th percentile), unchanged and not re-read: B is "a flag fired".
- **A mark** `X_A` = the **95th percentile** absolute Flag A move rounded to the nearest 0.5, and at least `T_A + 0.5`. `X_C` = the 95th percentile
  absolute Pinnacle line move rounded up to the half point, and at least `T_C + 0.5`. The floor keeps A above B where the tape barely moves (it binds
  for NBA spread price and the NFL spread line, whose 95th percentile, 1.0, equals its `T_C`).

Why these three points: A is meant to be rare (the largest moves, about 1 in 20 in either direction, so about 1 in 40 toward), B is the existing
registered "fired" line (about 1 in 10 toward), C splits the unflagged games at their median, and D, the rest, is the common case. Nothing here reads
a result, a price at the cut, or the close.

### 2.2 The distribution (started games, home or over side, absolute points)

| Sport, market | Games | Flag A n | A p50 | A p75 | A p80 | A p90 | A p95 | Line n | Line p50 | Line p75 | Line p80 | Line p90 | Line p95 | Line: no move |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NBA moneyline | 250 | 250 | 1.90 | 3.50 | 4.21 | 5.96 | 8.87 | | | | | | | |
| NBA spread | 250 | 222 | 0.70 | 1.27 | 1.49 | 1.85 | 2.17 | 250 | 1.00 | 1.50 | 2.00 | 2.50 | 3.50 | 18% |
| NBA total | 250 | 219 | 0.80 | 1.43 | 1.60 | 2.06 | 2.30 | 250 | 1.50 | 2.50 | 3.00 | 3.50 | 4.00 | 11% |
| NFL moneyline | 116 | 116 | 0.74 | 1.39 | 1.55 | 2.07 | 2.75 | | | | | | | |
| NFL spread | 116 | 101 | 0.77 | 1.39 | 1.47 | 1.94 | 2.40 | 114 | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | 73% |
| NFL total | 116 | 89 | 0.54 | 1.22 | 1.37 | 2.07 | 2.38 | 114 | 0.00 | 1.00 | 1.00 | 1.00 | 1.50 | 54% |
| CBB moneyline | 191 | 155 | 1.24 | 2.54 | 2.98 | 3.81 | 4.57 | | | | | | | |
| CBB spread | 191 | 164 | 0.88 | 1.34 | 1.48 | 2.03 | 2.41 | 182 | 0.50 | 1.00 | 1.00 | 1.50 | 2.00 | 40% |
| CBB total | 191 | 155 | 0.65 | 1.08 | 1.30 | 1.83 | 2.27 | 182 | 1.00 | 2.00 | 2.50 | 3.00 | 4.00 | 30% |
| CFB moneyline | 352 | 331 | 0.94 | 2.08 | 2.48 | 3.36 | 4.29 | | | | | | | |
| CFB spread | 352 | 300 | 0.69 | 1.37 | 1.49 | 1.95 | 2.30 | 337 | 0.50 | 1.00 | 1.50 | 2.00 | 2.50 | 38% |
| CFB total | 352 | 290 | 0.67 | 1.31 | 1.44 | 1.80 | 2.17 | 337 | 0.50 | 1.00 | 1.50 | 1.50 | 2.00 | 43% |

(Tape at `origin/main` `a6b75ea6c404`. "Line n" counts games where Pinnacle and at least 2 US books are readable, as Flag C requires. The p80 columns
reproduce the registered `T_A` and `T_C` within rounding on the newer tape: none of the twelve `T_A` or eight `T_C` would round to a different value.)

### 2.3 The cutoffs this gives (points)

| Sport, market | C mark `M_A` (price) | B mark `T_A` | A mark `X_A` | C mark `M_C` (line) | B mark `T_C` | A mark `X_C` |
|---|---|---|---|---|---|---|
| NBA moneyline | 2.0 | 4.0 | 9.0 | | | |
| NBA spread | 0.5 | 1.5 | 2.0 (floor) | 1.0 | 2.0 | 3.5 |
| NBA total | 1.0 | 1.5 | 2.5 | 1.5 | 3.0 | 4.0 |
| NFL moneyline | 0.5 | 1.5 | 3.0 | | | |
| NFL spread | 1.0 | 1.5 | 2.5 | 0.5 (floor) | 1.0 | 1.5 (floor) |
| NFL total | 0.5 | 1.5 | 2.5 | 0.5 (floor) | 1.0 | 1.5 |
| CBB moneyline | 1.0 | 3.0 | 4.5 | | | |
| CBB spread | 1.0 | 1.5 | 2.5 | 0.5 | 1.0 | 2.0 |
| CBB total | 0.5 | 1.5 | 2.5 | 1.0 | 2.5 | 4.0 |
| CFB moneyline | 1.0 | 2.5 | 4.5 | | | |
| CFB spread | 0.5 | 1.5 | 2.5 | 0.5 | 1.5 | 2.5 |
| CFB total | 0.5 | 1.5 | 2.0 | 0.5 | 1.5 | 2.0 |

The cutoffs are per sport and per market because the moves are: an NBA moneyline's median price move (1.90) is larger than an NFL moneyline's
p90 (2.07). The nearest-0.5 rounding moves two C marks a quarter point from their median (NFL moneyline 0.74 to 0.5, NFL spread 0.77 to 1.0); it is
the same rounding `T_A` used and is kept for that reason.

### 2.4 Letter shares on the population

Both sides of every started market (each game gives two sides per market, so the toward and the against shares are symmetric by construction),
tape at `a6b75ea6c404`, percentages of sides with a grade or the marker (null left out):

| Sport, market | Sides | A | B | C | D | Moved against | No grade |
|---|---|---|---|---|---|---|---|
| NBA moneyline | 500 | 12 (2%) | 70 (14%) | 46 (9%) | 290 (58%) | 82 (16%) | 0 |
| NBA spread | 500 | 30 (6%) | 52 (10%) | 108 (22%) | 224 (45%) | 86 (17%) | 0 |
| NBA total | 500 | 27 (5%) | 70 (14%) | 77 (15%) | 219 (44%) | 107 (21%) | 0 |
| **NBA** | 1,500 | 69 (4.6%) | 192 (12.8%) | 231 (15.4%) | 733 (48.9%) | 275 (18.3%) | 0 |
| NFL moneyline | 232 | 3 (1%) | 30 (13%) | 43 (19%) | 123 (53%) | 33 (14%) | 0 |
| NFL spread | 232 | 6 (3%) | 17 (7%) | 44 (19%) | 142 (61%) | 23 (10%) | 0 |
| NFL total | 232 | 14 (6%) | 26 (11%) | 45 (19%) | 107 (46%) | 40 (17%) | 0 |
| **NFL** | 696 | 23 (3.3%) | 73 (10.5%) | 132 (19.0%) | 372 (53.4%) | 96 (13.8%) | 0 |
| CBB moneyline | 382 | 10 (3%) | 46 (15%) | 45 (15%) | 153 (49%) | 56 (18%) | 72 |
| CBB spread | 382 | 22 (6%) | 59 (16%) | 49 (13%) | 145 (40%) | 89 (24%) | 18 |
| CBB total | 382 | 14 (4%) | 39 (11%) | 79 (22%) | 175 (48%) | 57 (16%) | 18 |
| **CBB** | 1,146 | 46 (4.4%) | 144 (13.9%) | 173 (16.7%) | 473 (45.6%) | 202 (19.5%) | 108 |
| CFB moneyline | 704 | 12 (2%) | 75 (11%) | 77 (12%) | 411 (62%) | 87 (13%) | 42 |
| CFB spread | 704 | 38 (6%) | 84 (12%) | 154 (23%) | 270 (40%) | 128 (19%) | 30 |
| CFB total | 704 | 52 (8%) | 62 (9%) | 142 (21%) | 302 (45%) | 116 (17%) | 30 |
| **CFB** | 2,112 | 102 (5.1%) | 221 (11.0%) | 373 (18.6%) | 983 (48.9%) | 331 (16.5%) | 102 |
| **All four** | 5,454 | **240 (4.6%)** | **630 (12.0%)** | **909 (17.3%)** | **2,561 (48.8%)** | **904 (17.2%)** | 210 |

That is the target spread: A rare (2% to 8% by market), B about one in eight, C about one in six, D about half, the against marker about one in six.
Two things to know: a moneyline reaches A less often (1% to 3%) because only Flag A's price can carry it there (1.2); and the CBB nulls are games
whose Pinnacle rows began after their cut (the CBB tape began 2026-11-19 9:08 AM CT).

**First draft rejected, said for the record.** The first rule tried was "A = both flags toward, B = one toward". On the same population it gave
moneyline A on 6% to 9% of sides but spread and total A on 0% to 1% (on a moneyline Flag A and Flag C read the same quantity, price, so they fire
together; on a spread a line move resets the same-line price, so they rarely do). A letter whose meaning changes by market is not one sentence, so
A is set by magnitude instead. No result was read to make this choice.

### 2.5 Shares on the 205 graded plays (read at each play's own cut)

| Sport | Plays | A | B | C | D | Moved against | No grade |
|---|---|---|---|---|---|---|---|
| NBA | 58 | 3 | 6 | 6 | 26 | 17 | 0 |
| NFL | 33 | 4 | 2 | 6 | 19 | 2 | 0 |
| CBB | 53 | 0 | 1 | 2 | 4 | 0 | **46** |
| CFB (no size shown) | 61 | 4 | 11 | 8 | 12 | 11 | 15 |
| All | 205 | 11 (7.6%) | 20 (13.9%) | 22 (15.3%) | 61 (42.4%) | 30 (20.8%) | 61 |

(Percentages of the 144 plays with a grade or the marker.) The no-grade reasons are the `v2f-2` ones (flags spec 1.7): CBB 46 = 8 `side_unmapped` + 38 cut
before Pinnacle rows existed for the game; CFB 15 = 9 `side_unmapped` + 6 with no Pinnacle row at the cut.

**CBB and CFB degrade to null, never to a forced letter.** In-sample, CBB is readable on 7 of 53 plays: too few to read anything, and the grade says
"No grade" on the other 46 for good (no tape existed at their cut). Forward, the CBB tape exists (9% of population sides null, section 2.4), so
forward CBB plays will mostly get a letter. CFB plays whose side does not map to a team stay null. A sport whose forward readable share falls under
50% in a month is reported as "mostly unreadable" in that month's interim read (report only).

---

## 3. In-sample record by letter (205 graded plays, point in time)

Each play's Flag A and Flag C are re-derived from the tape rows at or before its own cut (`flag_record.derive_flags`' path; none of the 205 cards
carries a stored `v2.flags` yet), the letter is then computed by 1.3, and the play is joined to its graded row. Flat 1u at the stored price at the
cut (a win pays 1 / price - 1, a loss -1, a push 0), variant `all`, 3 voided plays left out, data `pm-holders-data` `f2eac1ad6739`. ROI se = the
standard error of the per-play flat result, in points of ROI. **Every cell is in-sample** (`mg-1` was written after these results) and every cell
under n=30 is a **small sample**.

### 3.1 Old (no grade) and new (by letter)

| Old: the record today, no grade | Record | n |
|---|---|---|
| NBA | 34-24, +0.10u, +0.2% | 58 |
| NFL | 22-11, +7.88u, +23.9% | 33 |
| CBB | 29-24, +4.00u, +7.5% | 53 |
| CFB (no size shown) | 29-32, -9.33u, -15.3% | 61 |
| Headline NBA + NFL + CBB | 85-59, +11.98u, +8.3% | 144 |
| All four | 114-91, +2.66u, +1.3% | 205 |

| New: by Move grade | NBA | NFL | CBB | CFB (no size shown) | Headline NBA+NFL+CBB | All four |
|---|---|---|---|---|---|---|
| A | 0-3, -3.00u, -100.0% (se 0.0), n=3 | 4-0, +3.22u, +80.6% (se 10.4), n=4 | n=0 | 2-2, -0.12u, -2.9% (se 56.1), n=4 | 4-3, +0.22u, +3.2% (se 36.9), n=7 | 6-5, +0.11u, +1.0% (se 29.4), n=11 |
| B | 5-1, +2.27u, +37.9% (se 30.1), n=6 | 1-1, -0.43u, -21.3% (se 78.7), n=2 | 1-0, +1.06u, n=1 (no se) | 4-7, -4.65u, -42.3% (se 24.4), n=11 | 7-2, +2.91u, +32.3% (se 26.6), n=9 | 11-9, -1.74u, -8.7% (se 19.5), n=20 |
| C | 3-3, +1.12u, +18.7% (se 54.0), n=6 | 5-1, +4.90u, +81.7% (se 37.4), n=6 | 2-0, +1.56u, +77.9% (se 41.9), n=2 | 5-3, +0.59u, +7.4% (se 31.7), n=8 | 10-4, +7.58u, +54.1% (se 28.3), n=14 | 15-7, +8.17u, +37.2% (se 21.5), n=22 |
| D | 15-11, -3.61u, -13.9% (se 15.3), n=26 | 12-7, +2.19u, +11.5% (se 20.6), n=19 | 1-3, -1.94u, -48.5% (se 51.5), n=4 | 7-5, +0.81u, +6.8% (se 27.9), n=12 | 28-21, -3.37u, -6.9% (se 12.1), n=49 | 35-26, -2.55u, -4.2% (se 11.1), n=61 |
| Moved against | 11-6, +3.32u, +19.5% (se 23.8), n=17 | 0-2, -2.00u, -100.0% (se 0.0), n=2 | n=0 | 3-8, -5.36u, -48.7% (se 26.5), n=11 | 11-8, +1.32u, +6.9% (se 22.9), n=19 | 14-16, -4.04u, -13.5% (se 17.9), n=30 |
| No grade | n=0 | n=0 | 25-21, +3.32u, +7.2% (se 14.9), n=46 | 8-7, -0.61u, -4.1% (se 24.5), n=15 | 25-21, +3.32u, +7.2% (se 14.9), n=46 | 33-28, +2.71u, +4.4% (se 12.6), n=61 |

Every play sits in exactly one row, so each column adds up to its old total (for example the headline: 7 + 9 + 14 + 49 + 19 + 46 = 144 plays and
+0.22 + 2.91 + 7.58 - 3.37 + 1.32 + 3.32 = +11.98u).

### 3.2 The prereg's metrics on the same plays (in-sample, report only)

| Headline NBA+NFL+CBB | A | B | C | D | Moved against |
|---|---|---|---|---|---|
| Market move after the cut (primary of 6), mean points, se, n with a same-line close | 0.00 (se 0.00), n=7 | +0.10 (se 0.23), n=9 | +0.04 (se 0.04), n=14 | +0.05 (se 0.08), n=48 | -0.53 (se 0.23), n=19 |
| Pinnacle CLV (secondary, overlaps the inputs by construction), mean points, n | -1.40, n=5 | -0.04, n=8 | -0.13, n=9 | -0.37, n=33 | +1.05, n=14 |

The after-cut move covers only the 15 minutes from the cut to the start, so most plays have none: 91 of the 143 graded plays with a readable move
moved exactly 0. The slope of that move on the letter (D=0, C=1, B=2, A=3), 95% bootstrap, 10,000 resamples, seed 20261111: NBA +0.065 [-0.077,
+0.234] n=41; NFL -0.089 [-0.260, +0.054] n=30; CBB +0.027 [-0.007, +0.230] n=7; CFB +0.110 [-0.066, +0.296] n=35; headline -0.002 [-0.099, +0.098]
n=78. Every interval spans 0.

### 3.3 Flagged for close monitoring: every cell that improves (units above 0), with its n

All in-sample; none promoted; none a signal. "Small sample" = n under 30.

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

### 3.4 The honest read

**The letter does not order the results in-sample.** On the headline, C is the best letter (+7.58u, n=14), A is close to flat (+0.22u, n=7) and D
is negative (-3.37u, n=49); in NBA, A went 0-3 while the plays the market moved **against** went 11-6, +3.32u. Over all four sports A (+0.11u) sits
below C (+8.17u) and B is negative (-1.74u). The after-cut market move does not order either (headline slope -0.002, interval -0.099 to +0.098).
The standard errors run from 10.4 to 78.7 points of ROI (the all-loss cells at n=2 and 3 and the n=1 cell have none worth the name), so no cell separates from zero or from another. This matches what the flags already
showed (`docs/side-card-record.md`, "Market-move flags v2f-2"): they describe the market and have not ordered results. The Move grade is a tidier way
to read the same two flags, not new evidence, and the page must not present it as anything more.

---

## 4. Where it is computed and stored

### 4.1 Code

- **New module** `scripts/sharps_v2/move_grade.py` (stdlib only, pure): `MG_RULE = "mg-1"`, the four cutoff tables `MG_M_A`, `MG_M_C`, `MG_X_A`,
  `MG_X_C` (section 2.3, one literal table each; the docs and tests read them), `move_grade(flags, g, norm, sport)` (1.3), `mg_of(grade)` (the log
  projection) and `mg_fields()` (the `live.json` field list). It imports `flags_v2` for `_dir_sign` and `FLAGS_T_A` / `FLAGS_T_C` and **never edits
  `flags_v2.py`** (frozen at the `v2f-2` registration).
- **`plays_v2.market_v2`**: right after the existing flags `try` block, inside its **own** `try`, when `side` is set:
  `v2["move_grade"] = MG.move_grade(v2.get("flags"), g, norms.get(side), sport)`. On an exception: `v2["move_grade"] = None`,
  `v2["move_grade_error"] = "<type>"`, a `::warning::v2 move grade dropped for <ev> <g>: <type>` line, and nothing else changes. It runs on the full
  flags block, before `check_size.py` can drop anything.
- **`plays_v2.plays_fields`**: adds `"move_grade": MG.mg_fields()` inside `v2_plays` (an existing top key, so `V2_TOP_KEYS` does not change).

### 4.2 The stored block (`markets[g].v2.move_grade`, shown plays only)

```
v2.move_grade = {
  "rule": "mg-1",
  "letter": "A" | "B" | "C" | "D" | null,
  "against": true | false | null,        // null only when there is no grade at all
  "basis": "a_mark" | "c_mark" | "fired" | "drift" | "flat" | "against" | null,
  "against_by": ["a", "c"] | null,       // which flags fired away (against only)
  "a": "toward" | "away" | "quiet" | null, "c": same,           // the two v2f-2 states read
  "a_pts": 2.31 | null,                  // flags.pin.pts as stored
  "c_pts": -0.5 | null,                  // Pinnacle line move toward the side, points (1.2); null on a moneyline
  "c_kind": "line" | "price" | null, "c_same_way": 4 | null, "c_books": 6 | null,   // copied for the "how earned" line
  "cut": {"m_a": 0.5, "t_a": 1.5, "x_a": 2.0, "m_c": 1.0, "t_c": 2.0, "x_c": 3.5},  // the marks used for THIS play's sport and market (m_c, t_c, x_c null on a moneyline)
  "why": null | "side_unmapped" | "no_flags" | "flags_unreadable" | "no_cutoff",
  "flags_why": {"pin": ..., "line": ...} | null                  // copied from v2.flags.why when flags_unreadable
}
v2_plays.move_grade = {"rule": "mg-1", "spec": "docs/sharps-v2-movegrade-spec.md", "m_a": {...}, "m_c": {...}, "x_a": {...}, "x_c": {...},
                       "letters": ["A", "B", "C", "D"], "shown": true, "context_only": true}
```

The block carries its own inputs and marks so that the page can print "how this letter was earned" even when the flags sub-budget has dropped
`v2.flags` (section 4.4), and so a reader never needs the cutoff table to explain one play.

### 4.3 Frozen at lock, never recomputed

- A **frozen card** stores `v2.move_grade` computed at its cut from the flags computed at its cut (point in time by construction: `flags_block` reads
  only tape rows with `t <= asof`).
- The **forward log** `pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl` gets one new key on rows written after the registering commit:
  `mg = {"rule", "letter", "against", "basis", "against_by", "a_pts", "c_pts", "why"}` (`MG.mg_of`), a projection of the frozen card's stored
  `v2.move_grade`, written by `plays_v2.log_row` beside `mf`: `if "move_grade" in v2: row["mg"] = MG.mg_of(v2["move_grade"])`. The repair pass
  re-projects from the same stored block, so a late append equals an on-time one. A card built before the grade has no key and its row has no `mg`
  ("not logged", never D); a dropped grade logs `mg: null`.
- Nothing recomputes a logged grade. The record file (section 5) reads the log's `mg` for forward plays and the card's stored block, then the card's
  stored flags, then the tape, for older plays, in that order.

### 4.4 Size

- Measured: the full block above is **237 bytes** compact (a typical spread play); `mg` on a log row is **97 bytes**.
- Live today: 7 shown plays, about 1.7 KB. Busiest graded day (51 shown plays, 2026-11-14): about **12 KB**. Current V2 keys 66.2 KB of the
  **250 KB** soft budget, so the worst case is about 78 KB.
- **Not in the flags sub-budget.** `v2.move_grade` is its own key, outside `v2.flags` and `v2.series`, so the 90 KB sub-budget (today 6.3 KB) is
  unchanged and `check_size.enforce_flags` never drops it: when the gate drops `series`, `by_book` or all of `flags`, the grade stays (it was computed
  before the gate and carries its own inputs). `check_size.py` needs no change; its test gains one assertion that `move_grade` survives every
  flags drop step.
- **`strip_plays_v2`**: the key sits inside `v2`, so `strip_plays_v2` removes it with the rest of `v2` and the V1 byte-compare test holds unchanged.
  If V2 as a whole goes over 250 KB, the existing rule strips every V2 key, the grade included (the V1 file publishes).

### 4.5 Old keys byte-identical

Every pre-existing key of `live.json`, every frozen card and every log row keeps its name, shape and value: `v2.flags`, `v2.series`, `mf`, the tier,
`shown_units`, `shadow_units`, the ladder (`sf.all.units`), `sf_rungs`, the gates and the locks. A test builds old and new on the same inputs and
`--now`, strips `move_grade`, `move_grade_error`, `v2_plays.move_grade` and `mg`, and asserts JSON-equal (and `strip_plays_v2` byte-equal to V1).

---

## 5. Forward record: `move_grade_record.json`

- **Script** `scripts/sharps_v2/move_grade_record.py`, built like `flag_record.py` and `tier_record.py`: reads the `pm-holders-data` checkout
  (`TH.FsReader`), the graded rows and the book tape; one record per graded `sf` play of variant `all`; slices `a`, `b`, `c`, `d`, `against`,
  `unreadable`; every play is in exactly one slice.
- **Source of each play's letter, point in time:** the log row's `mg` (forward), else the card's stored `v2.move_grade`, else `move_grade()` on the
  card's stored `v2.flags`, else `move_grade()` on `flags_block()` re-derived from the tape rows at or before the cut (`src`: `logged`, `frozen`,
  `frozen_flags`, `derived`). A failure is `unreadable` with a warning, never a guess.
- **Buckets** exactly as `flag_record.json`: `in_sample` = cut strictly before the first log row carrying `mg` (all plays when none), `forward` = only
  plays whose `mg` was logged at lock, joined to the graded record (zero until one is graded), `all`.
- **Shape:** `{built, data_ref, rule, mg_rule: "mg-1", units_basis: "flat 1u at the stored price at the cut", slices, first_logged_cut, logged_rows,
  forward_graded, forward_note, all_sports: ["nba","nfl","cbb"], sports: {nba|nfl|cfb|cbb: {<slice>: {all, in_sample, forward}}}, all: {...}}`,
  `cell = {w, l, p, n, units, roi}` (`roi` a fraction, null at n = 0). Expected size about 6 KB (`flag_record.json` has the same shape with six slices).
- **Workflow:** a new never-blocking step "Move grade record" in `.github/workflows/pm-cards.yml` beside "Flag record" (`python3 -I
  scripts/sharps_v2/move_grade_record.py --data-dir pmdata --book-tape data/book_tape --out live/move_grade_record.json --data-ref ...`, on failure
  `::warning::` and the file is dropped for that run), and the publish step adds `move_grade_record.json` to the `pm-cards-live` tree the same way
  `flag_record.json` is added. The classic page does not read it.
- **History (CLAUDE.md: a tracking change fixes history and records):** the 205 graded plays get their letter re-derived point in time (section 3),
  printed by `tier_history.py` (new block "MOVE GRADE mg-1", beside the flag block, imported only when the flag module imports, so a problem there
  can never reach the tier record) and written to `move_grade_record.json` `in_sample`. `docs/side-card-record.md` gets a new section
  "Move grade mg-1: the record by letter (date)" with the old and new tables and the monitoring list of section 3, regenerated at the build's data
  commit. `docs/side-cards.md` gets "Move grade (`markets[g].v2.move_grade`, forward log key `mg`)" and "`move_grade_record.json`".

### 5.1 PR body template (CLAUDE.md: Model/data and UI, old number and new number)

```
## Model/data
- New: Move grade mg-1 per shown play (v2.move_grade), shadow only. Inputs: v2f-2 Flag A and Flag C only. No effect on shown size (flat 1u),
  shadow size v2s-1, tier v2t-1, Top Reads, SM_GATE or agree totals.
- Cutoffs (points) from the started-game tape at <tape sha>: C mark M_A / M_C, A mark X_A / X_C (table). Old: none. New: <table>.
- Letter shares, population (both sides, <n> sides): old none; new A <x>%, B <x>%, C <x>%, D <x>%, against <x>%, no grade <n>.
- History, <n> graded plays at pm-holders-data <sha>, flat 1u at the stored price at the cut:
  old (no grade): NBA 34-24 +0.10u n=58; NFL 22-11 +7.88u n=33; CBB 29-24 +4.00u n=53; CFB 29-32 -9.33u n=61; headline 85-59 +11.98u n=144
  new (by letter): A <w-l, u, n>; B ...; C ...; D ...; moved against ...; no grade ... (per sport and headline)
- Flagged for close monitoring (improves, units above 0), with n and small-sample tags: <list>
- Forward log: new key mg on v2_tier rows from <commit>; old rows unchanged. move_grade_record.json on pm-cards-live.
- Sizes: live.json V2 <old> KB to <new> KB (budget 250); flags sub-budget unchanged <x> KB (90).
- Byte-compare: old keys identical (<n> live games, <n> frozen cards, <n> log rows).
## UI
- Move grade chip beside the tier chip; "how this letter was earned" line in the write-up and More detail; Moved against marker; legend.
- Record page: By Move grade table (in-sample / forward).
- Cache bumps: sv2.css 27 to 28, sv2-core.js 6 to 7, sv2-sharps.js 8 to 9, sv2-record.js 10 to 11, embed.js 20 to 21 (both shells).
```

---

## 6. Prereg amendment text (to append to `docs/sharp-tier-v2-prereg.md` after the user approves it in chat)

The text below is **not** added to the prereg file by this spec. That file is registered and frozen; the amendment is a new, separate, dated section
appended to its end, and it does not edit any existing rule (`v2t-1`, `v2s-1`, `v2f-2` and their sections stay byte for byte as registered). The
commit that appends it with the status word changed to Registered is the registration.

```
## Move grade mg-1 (shadow, proposed 2026-11-23, Registered 2026-11-24)

Added by the user's decision of 2026-11-23. Rule id `mg-1`, spec `docs/sharps-v2-movegrade-spec.md`, code `scripts/sharps_v2/move_grade.py`
(cutoff tables `MG_M_A`, `MG_M_C`, `MG_X_A`, `MG_X_C`, frozen at the registering commit). This amendment changes no earlier rule of this file:
v2t-1, v2s-1 and v2f-2 and their thresholds, metrics, dates and kill rules stand as registered. Any change to a cutoff, an input or a branch of
mg-1 after registration is a new rule id (mg-2) and a new registration; old rows stay read as written.

What it is. A per-play letter A, B, C or D saying how far the market moved toward the play's side in the 24 hours before the cut, from the
registered v2f-2 Flag A (Pinnacle's no-vig price at the same line) and Flag C (the market's main line, or the books' price on a moneyline) only.
A = a flag fired toward and the move passed the A mark (the 95th percentile of the absolute 24-hour move for the sport and market, at least half a
point past the flag threshold); B = a flag fired toward; C = no flag fired, Pinnacle's price or line moved toward by at least the median 24-hour move
and not that far away; D = otherwise. Any flag fired away gives the "moved against" marker and no letter. Neither flag readable gives no grade.
Pinnacle's limit is never an input. Cutoffs were set from the distribution of moves on every started game of the tape (origin/main a6b75ea6c404,
2026-11-23 6:28 PM CT), never from results.

Context only. The grade never changes the shown size (flat 1u on NBA, NFL and CBB, none on CFB, "untested rule"), the shadow size v2s-1, the
evidence tier, the ladder, sf_rungs, the gates or the locks, and it never feeds Top Reads, SM_GATE or an agree total. Passing this test only lets
the user consider calling the grade tested, as a separate decision. It does not make one.

Logged at lock. New rows of pm_cards/<sport>/v2_tier/<YYYY-MM>.jsonl carry `mg`, a projection of the frozen card's stored v2.move_grade. The
first play that can count is the first one cut after the registering commit. A forward row is read as written (no staleness rule, as for mf).
Old rows without `mg` are "not logged", never D.

Primary metric: the market move after the cut. after = Pinnacle's no-vig fair for the side at the last tape row at or before game start (the
pinclose row) minus its no-vig fair at the cut, in points, same line (a play whose close is at a different line is left out and counted apart).
Plays with price_src == "pin" are left out and reported apart. Statistic, per sport, never pooled: the least-squares slope of after on the letter
score (D = 0, C = 1, B = 2, A = 3) over plays with a letter, 95% percentile bootstrap, 10,000 resamples, seed 20261111, resampling plays. The
"moved against" group is read apart: mean after of "moved against" minus mean after of D, same interval, report only.

Why not CLV as the primary. CLV (Pinnacle's no-vig close minus the stored Polymarket price at the cut) contains Pinnacle's fair at the cut, which
Flag A and therefore the letter are built from, so a letter could "win" on CLV without the market moving after the cut (the same overlap the
v2f-2 section removed). CLV stays as a secondary, labelled as overlapping by construction.

Secondary (reported, never a pass condition): CLV per letter (overlapping), flat 1u ROI per letter at the stored price at the cut
(move_grade_record.json), and the after-cut mean per letter. Expected in advance: the after-cut window is 15 minutes, and 91 of the 143 graded
plays with a readable after-cut move had a move of exactly 0, so the metric has a low spread and most of its information comes from the minority
of games that move in the last 15 minutes.

Minimum n before any verdict, per sport: 300 plays with a letter and a readable after-cut move, and at least 30 in each of A, B and C and 100 in
D. With the population letter shares (A 5.5%, B 14.5%, C 20.9%, D 59.0% of lettered sides) the letter score has a standard deviation of 0.92; with
the after-cut standard deviation measured on the graded headline plays (0.49 points, n=78), 300 plays give the slope a standard error near 0.031
points per letter step, so 80% power at 95% confidence to see a slope of about 0.09 points per step. A needs about 550 lettered plays in a sport to
reach 30, so the honest expectation this season is Underpowered in every sport, said here in advance.

Final reads: the same dates as the tier registration above (NBA: the first Monday after the 2026-27 regular season; NFL: the Tuesday after Week
18; CFB: the Monday after conference championship weekend; CBB: the Monday after the 2027 national championship game). Monthly interim reads
are report-only and can neither pass nor fail a sport; repeated looks do not add up to a pass.

Pass (per sport): the lower 95% bound of the slope is above 0 with every minimum met. Fail: every minimum met and the lower bound at or below 0:
the letter comes off the page at the final read (logging continues to the end of the season), and the "moved against" marker stays only as the
v2f-2 flag it already is. Underpowered: any minimum short at the final read; neither pass nor fail, and the read says which group was short and
by how much.

Data quality, no verdict for the sport: more than 5% of forward mg rows whose letter differs from move_grade() re-run on the same frozen card's
stored v2.flags, or more than 10% of forward rows with mg null for a reason other than side_unmapped.

What every read reports: n per letter and per sport, the plays with no grade by reason, win-loss and flat ROI with standard errors, the after-cut
and CLV means with intervals, the "moved against" read, the CFB read (no size shown) apart, and every cell that improves (units above 0) flagged
for close monitoring with its n (small sample under 30), never promoted on the same data.

In-sample record (not evidence): docs/side-card-record.md, "Move grade mg-1". On the 205 graded plays, read point in time, the letter did not
order results (headline A 4-3 +0.22u n=7, B 7-2 +2.91u n=9, C 10-4 +7.58u n=14, D 28-21 -3.37u n=49, moved against 11-8 +1.32u n=19) and
the after-cut slope was -0.002 (interval -0.099 to +0.098, n=78).
```

---

## 7. The UI

### 7.1 Where the chip sits

- **Plays table** (`sv2-sharps.js` `rowHtml`): inside the existing `c-tier` cell, after `ui.tier(p.tier)`: `ui.tier(p.tier) + ui.moveGrade(mg)`. The
  header label changes from "Tier" to "Tier and move" (the sort on that column stays the tier sort). No new column, so the table width and the
  phone reorder (`c-tier` is `order: 5` under 768px) are unchanged and the chip rides with the tier chip on phones. Decision G4.
- **Write-up card** (`writeupHtml`): in tile 1 "The play", the line that holds `ui.tier(p.tier)` becomes `ui.tier(p.tier) + ' ' + ui.moveGrade(mg)`;
  and section 2 "Where the line went" gets the "how earned" line (7.2) as its first line, above the from/to numbers.
- **More detail** (`moreHtml`): one list item, the same "how earned" sentence, so a reader of the dropdown always sees the numbers behind the letter.
- **Row `aria-label`** (`rowHtml` `label`): append `, Move grade B` / `, moved against` / `, no Move grade`.
- No filter and no sort by letter in `mg-1` (decision G5): a control that selects plays by letter reads as a way to pick bets.

### 7.2 "How this letter was earned" (deterministic templates, stored numbers only)

Inputs: `move_grade` (letter, basis, a_pts, c_pts, c_same_way, c_books, cut), `flags.pin.from/to/line`, `flags.line.pin.from/to`, the side label,
the market, `H` = round(`flags.span_min` / 60) (as the takeaway). A placeholder whose value is null forces the template that does not use it.

| Basis | Sentence |
|---|---|
| `a_mark` | `Move A: Pinnacle's {side} price went {pin_from} to {pin_to} in the last {H} hours, {a_pts} points of no-vig price, past the A mark of {x_a}.` |
| `c_mark` (line) | `Move A: the market moved the number toward {side}, {line_from} to {line_to} at Pinnacle ({c_pts} points, A mark {x_c}), {c_same_way} of {c_books} books the same way.` |
| `fired` via A | `Move B: Pinnacle's {side} price went {pin_from} to {pin_to}, {a_pts} points (the flag mark is {t_a}, the A mark {x_a}).` |
| `fired` via C (line) | `Move B: the market moved the number toward {side}, {line_from} to {line_to} at Pinnacle, {c_same_way} of {c_books} books the same way (A mark {x_c} points).` |
| `fired` via C (price) | `Move B: the books moved the price toward {side}, {c_same_way} of {c_books} books past the flag mark.` |
| `drift` | `Move C: no flag fired; Pinnacle's {side} price drifted {a_pts} points toward it` and/or `its line {c_pts} points toward it` `(C mark {m_a} / {m_c}, flag mark {t_a} / {t_c}).` |
| `flat` | `Move D: no move toward {side} past a typical day's move (Pinnacle price {a_pts:+} points, line {c_pts:+} points; C mark {m_a} / {m_c}).` |
| `against` | `Moved against {side}: {the existing v2f-2 chip sentence with its numbers}. A move against the play is shown instead of a letter.` |
| null | `No Move grade: {reason}` with `side_unmapped` "the side could not be matched to a team", `flags_unreadable` "no market history was stored for this game before it froze", `no_flags` "the market-move read failed for this card". |

When B comes from both flags at once, the Flag A sentence is used and ` The market's number moved the same way.` is appended. Prices are American,
lines signed on spreads, points to 2 decimals as stored. Every rendered string must pass the existing banned-word checks of both test suites
(`tests/test_sharps_v2_flags.py` `BANNED` and `sv2-sharps.test.mjs` `bannedRe`, which include "lean", "strong", "edge", "follow", "lock", "go",
"confirm", "agree"); that is why C says "drifted", never "leaned".

### 7.3 Wording rules (never a bet signal)

- Always "Move grade" or "Move B"; never "Sharp grade", "grade A play", "A play", "rating", "score", "pick" or "signal".
- The legend (7.6) ends with: `A Move grade describes how far the market moved toward this play before it froze. It is not a bet signal and changes
  no size.` The write-up footer adds `Move grade: context only.` beside the existing "Context only, not a bet signal."
- No colour of "good" or "bad": no green on A, no red on D or on the against marker (the same reasoning as the flag chips, flags spec 4.1).
- The grade is never summed or counted with anything ("2 of 3", "A and Clear"); the tier chip and the Move chip sit side by side, each with its own
  word.

### 7.4 Colour and shape (no collision with gold, teal, slate or violet)

Monochrome ink, weight carries the order and the letter carries the meaning (colour is never the only cue):

| Mark | Chip | Tokens |
|---|---|---|
| A | solid fill, letter in page colour | background `--sv2-ink`, text `--sv2-page` |
| B | 1.5px ring, ink letter | ring and text `--sv2-ink` |
| C | 1px ring, ink letter | ring `--sv2-mut`, text `--sv2-ink` |
| D | 1px dashed ring, muted letter | ring and text `--sv2-mut` |
| Moved against | outline pill with the existing `FL_ICON.away` icon and the words "Moved against" | ring `--sv2-mut`, text `--sv2-ink` |
| No grade | nothing in the table; "No Move grade" in the write-up | `--sv2-mut` |

The chip is a 20px rounded square (`--sv2-r-sm` radius) with the letter in `--sv2-num`, then the word "Move" in 12px `--sv2-mut`, so it never
looks like the tier pill (a capsule with pips). Not gold (`--sv2-gold`, Clear), not teal (`--sv2-price`, Mixed), not slate (Thin's neutral), not
violet (`--sv2-violet`, Contested), not `--sv2-follow`, `--sv2-win`, `--sv2-loss` or `--sv2-caution`. Classes under a new `sv2-mg-` prefix (memory:
namespace new UI classes), defined in a new `sv2.css` section after section 12.

Contrast, computed from the token values (WCAG 2 relative luminance), every pair at 4.5:1 or more:

| Pair | Dark | Light |
|---|---|---|
| ink on card (B, C letters) | `#ECECEC` on `#222222` 13.5:1 (Apple `#1C1C1E` 14.4:1) | `#1F1F1F` on `#FFFFFF` 16.5:1 (on `#F5F5F5` 15.1:1) |
| page on ink fill (A letter) | `#1A1A1A` on `#ECECEC` 14.7:1 (Apple `#000000` 17.8:1) | `#FAFAFA` on `#1F1F1F` 15.8:1 (Apple `#F2F2F7` 14.8:1) |
| mut on card (D letter, "Move" word) | `#B0B0B0` on `#222222` 7.3:1 (on `#2A2A2A` 6.6:1) | `#575757` on `#FFFFFF` 7.2:1 (on `#F2F2F7` 6.5:1) |

The build task must re-check on the **composited** row colours (the Clear row's gold wash and the glass card), as the flag chips were checked, not
only on the tokens.

### 7.5 Tooltips and screen readers

- Chip `title` and a `.sv2-sr` span: `Move grade B: a market-move flag fired toward this side. Describes the market, not a bet signal.` (the 1.1
  sentence for the letter). Against: `Moved against: a market-move flag fired against this side. Shown instead of a letter.`
- The letter glyph is `aria-hidden`; the screen-reader text says "Move grade B".
- Touch has no hover, so the "how earned" line in the dropdown carries everything the tooltip says.

### 7.6 Legend

A `<details>` "What the Move grade means" under the table's existing notes (closed by default, 44px summary hit area): the five sentences of 1.1, the
cutoff source in one line ("Marks are set from the size of 24-hour moves on every started game of the season, per sport and market, not from
results."), and the closing line of 7.3.

### 7.7 Mobile

Under 768px the chip stays inside `c-tier` (order 5), wraps under the tier chip when the row is narrow (`flex-wrap`), never adds horizontal scroll,
and is not interactive (no hit area needed). In the write-up the "how earned" line sits in section 2, which is closed by default on phones, and the
tile-1 chip is visible in the first screen (memory: content first).

### 7.8 Record page (`sv2-record.js`)

- New section "By Move grade" after the tier section (`tiersSection`), built with the existing Plays-table record design (`tableHtml`, `labCell`,
  `tallyCells`, `rec.monitor` for the small-sample and improving tags). Rows: A, B, C, D, Moved against, No grade; columns W-L, Units, ROI, n.
- Data: `move_grade_record.json` from `pm-cards-live` (a `MG_URL` beside `TIER_URL`, the same 5-minute cache key and `SV2.dev.param('mgrecord')`
  override). Missing or invalid file: the section says "Move grade record not published yet" and nothing else breaks.
- A bucket switch "In-sample / Forward" (a `.sv2-seg`, wired the way `rec-tbucket` is), with the notes: In-sample "The grade rule was written after
  these results. Read it as history, not a test."; Forward "Only plays whose Move grade was logged when they froze. Starts at zero."
- The sport strip already scopes it; CFB carries the "no size shown" tag; "All" pools NBA, NFL and CBB (`all_sports`), as the tier table does.
- Pure functions (`rec.mgSlice`, `rec.mgTable`) exported for the node tests.

### 7.9 Cache bumps

| File | Change |
|---|---|
| `sharp-money/sharps-v2/embed.js` `V` | `css: 27 -> 28`, `core: 6 -> 7` (if `ui.moveGrade` lands in core), `sharps: 8 -> 9`, `record: 10 -> 11` |
| `sharp-money/sharps-v2/index.html` | `sv2.css?v=28`, `sv2-core.js?v=7`, `sv2-sharps.js?v=9`, `sv2-record.js?v=11` |
| `sharp-money/index.html` and `sharp-money/new/index.html` | `sharps-v2/embed.js?v=21` in **both** shells (memory: the two files are one page) |

(Versions as read at `origin/main` `a6b75ea6c404`; a later merge that bumps any of them first means the builder bumps from the newer value.)

---

## 8. Build tasks (Sonnet builds, Opus reviews; data first, then UI)

One PR per task, each body split Model/data and UI with old and new numbers (5.1). No open PR touches these files today (checked 2026-11-23, 6:35 PM
CT); re-check before each task starts.

| # | Task | Files | Done when |
|---|---|---|---|
| D1 | Commit the measurement: `move_grade_history.py` prints 2.2, 2.3, 2.4, 2.5 and section 3 at named refs | `scripts/sharps_v2/move_grade_history.py` (new) | printed tables equal this spec at `a6b75ea6c404` / `f2eac1ad6739`, or the spec is corrected first |
| D2 | The rule: `move_grade.py`, the `market_v2` call and guard, `plays_fields`, the `mg` log key | `scripts/sharps_v2/move_grade.py` (new), `scripts/sharps_v2/plays_v2.py`, `tests/test_sharps_v2_movegrade.py` (new) | tests below pass; a local build on the live inputs shows the 4.4 sizes; old keys byte-identical |
| D3 | Record: `move_grade_record.py`, `tier_history.py` block, workflow step and publish | `scripts/sharps_v2/move_grade_record.py` (new), `scripts/sharps_v2/tier_history.py`, `.github/workflows/pm-cards.yml`, tests | the file's `in_sample` equals section 3; the workflow publishes it; a failure drops only that file |
| D4 | History docs | `docs/side-card-record.md` (new section), `docs/side-cards.md` (two new sections) | tables regenerated by D1 at the build's data commit, old and new numbers, monitoring list with n |
| D5 | Prereg amendment (after the user approves 6 in chat) | `docs/sharp-tier-v2-prereg.md` (append only) | the section is appended with "Registered"; `git diff` shows no line removed or changed above it |
| U1 | Chip, legend, "how earned" lines, against marker, CSS | `sharp-money/sharps-v2/sv2-core.js` (`ui.moveGrade`, copy), `sv2-sharps.js`, `sv2.css`, `tests/sv2-sharps.test.mjs`, `tests/sv2-core.test.mjs` | JS tests pass; desktop and 375px screenshots, both themes, default and Apple skins, in the PR |
| U2 | Record page "By Move grade" | `sharp-money/sharps-v2/sv2-record.js`, `sv2.css` if needed, `tests/sv2-record.test.mjs` | JS tests pass; screenshots; old Record tables still render and sort |
| U3 | Cache bumps and changelog check | `embed.js`, `sharps-v2/index.html`, `sharp-money/index.html`, `sharp-money/new/index.html` | 7.9 applied; the page loads the new files cold (query-string bust checked in the preview) |

D2 must merge before U1 reads `v2.move_grade` (U1 renders nothing when the key is absent, so order is a safety net, not a requirement). D5 never
merges before the user's approval in chat.

### 8.1 Tests per task

**D1** (measurement)
- Reproduces every number of sections 2 and 3 at the named refs; prints the refs it read.
- Point in time: adding a tape row after a play's cut changes no letter; removing every row after the cut changes nothing.

**D2** (rule, storage, log)
- Frozen-test integrity: `tier_of`, `shown_units`, `shadow_units`, `sf_rungs`, the gates, the locks, Top Reads and SM_GATE produce identical output
  with `v2.move_grade` present, absent, null or garbage (a grep test fails the build if any of those modules reads `move_grade` or `mg`).
- Byte-compare: old and new builds on the same inputs and `--now`, with `move_grade`, `move_grade_error`, `v2_plays.move_grade` and `mg` stripped,
  are JSON-equal (live games matched by event and start, every frozen card, every log row); `strip_plays_v2(new)` equals the V1 file byte for byte;
  `flags_v2.py` is unchanged (`git diff --quiet` on it).
- Point in time: the grade is a pure function of the stored flags block and `norm`; a tape row after `asof` never changes it; the log's `mg` equals
  `mg_of(card.v2.move_grade)` for both the on-time append and the repair pass.
- Null cases: `side_unmapped`; `v2.flags` null (`flags_error`); both flags null (each `why` carried); one flag null and the other quiet, toward or
  away; a moneyline with Flag C null; a spread with `line.pin` missing; `pts` null with state set (garbage: no grade, never a guessed D).
- Boundary cutoffs, every sport and market: `pts` exactly at `M_A`, `T_A`, `X_A` and 0.01 under each; `c_pts` exactly at `M_C`, `T_C`, `X_C` and 0.5
  under; negative mirror values for the drift-away branch; a value equal to a mark takes the higher letter.
- Branch table: A via `a_mark`, A via `c_mark`, B via A only, via C only, via both, B on a moneyline from Flag C price toward with Flag A quiet; C via price drift, via line drift, both; D with drift away only, with drift toward and drift away together, with both flags quiet and
  tiny moves; against by A, by C, by both, and mixed toward plus away (against wins).
- Direction: spread home and away, total over and under, a favourite -3 to -4 and an underdog +22 to +19 read toward.
- Guard: an exception inside `move_grade` leaves the card built with `move_grade: null`, `move_grade_error`, a `::warning::`, and every other key
  (flags included) unchanged.
- Size: `check_size.enforce_flags` at each drop step (series, by_book, flags) leaves every `v2.move_grade` in place; `flags_kb` does not count it.
- Mutation targets (each must fail at least one test): `>=` to `>` at each of the six marks; swapping `M_A` and `X_A`; dropping the `dir_sign`
  (`c_pts` sign flipped); against checked after toward instead of before; reading `flags.limit`; using a 0 for a null `pts`; computing from rows
  after `asof`; `mg_of` dropping `against`.

**D3** (record)
- Every play sits in exactly one slice; slice totals equal the old record per sport and headline.
- Source order `logged` > `frozen` > `frozen_flags` > `derived`, each covered by a fixture; a logged `mg` is never recomputed, even when the card's
  stored flags would now give another letter.
- `in_sample` / `forward` split at the first logged cut carrying `mg`; forward is zero with no log; `roi` null at n = 0, never 0.
- `tier_history.py` output with the new block present equals the old output above it byte for byte (the tier and flag records are untouched).
- The workflow step failing leaves `live.json`, `tier_record.json` and `flag_record.json` published.

**D5** (prereg): `git diff` of `docs/sharp-tier-v2-prereg.md` is additions only, after the last line of the v2f-2 section.

**U1** (chip and text)
- Every letter, the against marker and every null reason render the right chip, tooltip, screen-reader text and "how earned" sentence, with no
  `{`, no `undefined`/`null`/`NaN`, no em or en dash, and no banned word (both banned lists).
- The chip never carries a tier class or a tier colour token; `data-tier` on the row is unchanged; the tier sort still sorts by tier.
- Absent `move_grade` (old card, V2 stripped): the cell shows the tier chip alone and nothing errors.
- Contrast on computed colours, dark, light, Apple, on the plain row and the Clear row: 4.5:1 or more.
- Rendered check (memory: verify UI filter wiring; show real rendered preview): the real `live.json`, a dropdown opened on desktop and at 375px,
  both themes; the filter buttons, "More detail" and every `.sv2-seg` still work, and `pill.getAnimations()` shows travel on a real click.

**U2** (Record): `rec.mgTable` on fixtures (empty file, in-sample only, forward rows), small-sample and improving tags from `rec.monitor`, the
bucket switch, "All" pools NBA+NFL+CBB only, CFB tagged; missing file message.

**U3**: a cold load (cache busted) fetches the new versions in both shells.

### 8.2 The three Opus review lenses

1. **Point in time.** Does any path read a tape row, a price, a close or a result after the cut? Is the letter on a frozen card and in `mg` exactly
   the one computed at the cut and never recomputed? Does the history use the same `flags_block` path as the live builder, at each play's own cut?
   Are the cutoffs from the tape population only (no graded result anywhere in D1's cutoff code)?
2. **Frozen-test integrity and byte-compare.** `flags_v2.py` unchanged; `v2t-1`, `v2s-1`, `v2f-2` code and prereg text unchanged; no size, tier,
   gate, lock, Top Reads, SM_GATE or agree total reads the grade; every old key byte-identical in `live.json`, the frozen cards and the log; the
   prereg diff is additions only.
3. **Honesty and records.** Every number in the PR and docs comes from a stored value at a named ref; old and new numbers side by side; every
   improving cell flagged with its n and a small-sample tag; the in-sample read says plainly that the letter did not order results; page copy never
   implies a bet signal and never says "Sharp grade"; only allowed book names (Pinnacle, DraftKings, FanDuel, MGM, BetRivers, bet365); times Central;
   no em dashes.

---

## 9. Decisions needed from the user

| # | Decision | Recommendation |
|---|---|---|
| G1 | A play with one flag toward and the other away | **Moved against** (the marker wins; 34 of 5,454 population sides, 0 graded plays), rather than a letter from the toward flag |
| G2 | One readable flag only | **Give a letter** from that flag (`basis` and the stored states say which was read; a moneyline with only Flag C can reach B), rather than no grade |
| G3 | The C letter (drift past the median, no flag) | **Keep it** (it is what separates "moved a little" from "did not move"), or drop to three letters A, B, D |
| G4 | Chip placement | **Inside the Tier cell**, header "Tier and move", no new column, rather than its own sortable column |
| G5 | Filter or sort by letter | **None in mg-1** (a selector by letter reads as a bet picker); revisit only after a pass |
| G6 | Colour | **Monochrome ink** (fill, ring, dashed ring), rather than a new hue |
| G7 | Approve the prereg amendment of section 6 | approve as written, after which D5 appends it as Registered |
| G8 | Show the grade on CFB plays (no size shown) | **Yes**, as the tier is shown there, with the CFB read kept apart in every record |
