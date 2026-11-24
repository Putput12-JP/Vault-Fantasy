# Sharps V2: Move grade search (protocol, written before any outcome is read)

**Status: REGISTERED by the commit that adds this file. Research only.** Written 2026-11-23, 7:15 PM CT. Branch `sharps-v2-movegrade-search`
(off `origin/main` `887be78439e7`). Nothing here changes live code, the registered prereg (`docs/sharp-tier-v2-prereg.md`, frozen, not edited),
`flags_v2.py` (`v2f-2`, frozen), or the Move grade spec `mg-1` (`docs/sharps-v2-movegrade-spec.md` on `sharps-v2-movegrade`). Sharp money is context
only (CLAUDE.md): a system that passes here is at most a PROPOSED shadow rule `mg-2` with its own forward prereg, never a bet signal, never an input
to Top Reads, SM_GATE, an agree total, a size or a tier.

The question (the user's, 2026-11-23): is there a per-play letter A to D, built only from market moves available before the cut (Pinnacle no-vig
price move, main line move across books, as in `v2f-2`), where higher letters have better results? The null is assumed: earlier tests of this
kind (steam chaser, EPA, spot score, line-taught ratings) ended NO-GO, and `mg-1` in-sample did not order results (C best, A flat, slope about 0).
A clean NO-GO is a valid result of this protocol.

What has already been seen before this file was written, said for the record: the `mg-1` spec's in-sample tables on the 205 graded plays (section 3
of that spec). No outcome of the tape population (results, after-cut moves, CLV) has been read by me before this commit. The 205 graded plays are
used for nothing below except a report-only table at the end.

## 1. Data (named refs; every number from a stored value)

| Input | Ref |
|---|---|
| Book tape, the population | `data/book_tape/<sport>/<YYYY-MM>.jsonl` at `origin/main` `887be78439e7` (Pinnacle, DraftKings, FanDuel, BetMGM, BetRivers, bet365 rows only; backfill rows carry no prices and are not read) |
| Graded plays (report only) | `origin/pm-holders-data` `3e17a148dc2f` via `scripts/sharps_v2/tier_history.py` `play_rows` |
| NBA final scores | `nba/data/game_picks.json` (`days[*].games`: away, home, away score, home score, start) at `887be78439e7` |
| NFL final scores | `data/bet_results.json` (`games[*]`: season, week, away, home, `away_score`, `home_score`) at `887be78439e7`; week from `data/game_line_history.json` `commence` |
| CFB final scores | `data/cfbd/lines_2026.json` (`hs`, `as_`, `sp`, `ou`) at `887be78439e7`; tape abbreviations mapped to schools by `data/cfbd/teams_fbs_2026.json` abbreviation and alternate names, plus a hand list for abbreviations with no hit (written before any score is read) |
| CBB final scores | none stored for the tape population in this repo at this ref (the `sharp-data` `data.json` keeps only a rolling window). CBB enters target (a) as report only and never a pass condition (the brief: too little tape) |

Matching games to scores uses names, start times and lines only (never scores). A match is accepted only when Pinnacle's last line at or before the
cut agrees with the score file's stored line within 3.0 points on the spread or 4.0 on the total where the file stores one (CFB; NBA and NFL match by
team and start date, within 12 hours for NBA, by season week for NFL). Unmatched games are dropped from target (c) and counted.

## 2. Population and point in time

- Every game on the tape whose start is before the run time (started), per sport NBA, NFL, CFB, CBB. **Cut = start minus 15 minutes** (the `v2f-2`
  population cut). Every feature reads only tape rows with `t <= cut`, through the `v2f-2` functions in `scripts/sharps_v2/flags_v2.py` unchanged
  (24-hour window, the row hanging at the window start, `_pin_clean`, same-line rule).
- Unit: a **side** (home and away of the moneyline and the spread, over and under of the total). Both sides of every market are graded. Standard
  errors and intervals resample whole **games** (cluster bootstrap), so the two mirror sides of a market are never counted as independent.
- Time split, **per sport**, by cut time of the game, earliest first: **fit** = first 60% of games, **validation** = next 20%, **sealed** = last
  20% (ties at a boundary go to the earlier set). Cutoffs are fit only on the fit set's move distribution (home or over side, absolute values,
  per sport and market, as the `mg-1` method), never on an outcome.

## 3. Targets (in priority order; the population each comes from is always stated)

- **(a) After-cut market move (primary, the prereg's primary).** Pinnacle no-vig fair for the side at its last row at or before start, minus at its
  last row at or before the cut, points x 100, at the **same line** (spread and total: both rows at the same line within `PIN_LINE_EPS`; a
  side whose close is at another line is left out and counted apart). Population: tape, every sport (CBB report only).
- **(b) CLV at close (secondary, report only, overlaps the inputs by construction).** Pinnacle no-vig fair at close (same line as the cut) minus the
  implied probability of the best stored US-book price for the side at the cut at Pinnacle's cut line (DraftKings, FanDuel, BetMGM, BetRivers,
  bet365, last row at or before the cut, line within `PIN_LINE_EPS`), points x 100. It shares the US-book rows that Flag C reads, so it is never a
  pass condition. On the 205 graded plays, (b) is the stored `clv` of `play_rows` (Pinnacle close minus the stored price at the cut).
- **(c) Result and flat 1u ROI.** Population: the side graded at **Pinnacle's line at the cut** with a flat 1u at **Pinnacle's stored American price
  for the side at the cut** (a win pays decimal minus 1, a loss -1, a push 0); win % = wins / (wins + losses). NBA, NFL, CFB only. The 205 graded
  plays: flat 1u at the stored price at the cut from `play_rows` (report only, separately labelled).

## 4. Features (all at the cut, toward the side positive)

- `a` = Flag A `pts`: Pinnacle's no-vig move for the side at the same line over the 24-hour window (`flag_pin`), null when `flag_pin` is null.
- `c` = spread and total: Pinnacle's main-line move toward the side, `dir x (to - from)` from `flag_line`'s `pin`; moneyline: the **median** over the
  US books readable for a move (`_book_moves`, history required) of their no-vig move toward the side, points x 100. Null when `flag_line` is null.
- `nb` = (US books moved toward minus US books moved away) / US books readable, a book "moved" when its own line moved 1.0 point or more (spread,
  total) or its no-vig price moved `T_A` or more (moneyline); null when fewer than 2 US books are readable.
- `pct_x` = sign(x) x F(|x|), F the fit-set empirical CDF of |x| (home or over side) for the sport and market; 0 when x is 0.

## 5. The search space: exactly 10 candidate systems (every one is counted; no others will be tried)

Every system gives each side a score `s` (toward positive). Unless fixed in advance (S1), the letter marks are the fit-set **p50, p80, p95** of
|s| (home or over side) for the stratum: **A** `s >= p95`, **B** `p80 <= s < p95`, **C** `p50 <= s < p80`, **D** `-p80 < s < p50`, **against**
(marker, no letter, out of the slope) `s <= -p80`; null `s` = no grade. Comparisons on values rounded to 4 decimals, inclusive at each mark.

| Id | System | Score `s` | Stratum for marks |
|---|---|---|---|
| S1 | `mg-1` exactly as specified (fixed tables of `docs/sharps-v2-movegrade-spec.md` 2.3 and the 1.3 pseudocode; nothing fitted) | n/a | n/a |
| S2 | Flag A magnitude | `a` | sport x market |
| S3 | Flag C magnitude | `c` | sport x market |
| S4 | Larger of the two, extremeness-scaled | the one of `pct_a`, `pct_c` with the larger absolute value (the one readable when the other is null) | sport x market |
| S5 | Agreement of both | mean of `pct_a` and `pct_c`; null unless both readable | sport x market |
| S6 | Books agreeing | `nb` | sport x market |
| S7 | S4, spreads and totals only (moneyline sides null) | as S4 | sport x market |
| S8 | S4, moneylines only (spread and total sides null) | as S4 | sport x market |
| S9 | S4 without a sport split | as S4, but F and the marks pooled over the sports | market |
| S10 | S2 without a sport split | `a` | market (pooled over sports) |

## 6. Statistics

- **Slope**: least-squares slope of the target on the letter score (D = 0, C = 1, B = 2, A = 3) over sides with a letter (against and null left
  out), per sport and pooled over NBA, NFL, CFB (pooled = one regression with a sport-and-market fixed effect, i.e. targets demeaned within sport x
  market before the slope). 95% interval: percentile cluster bootstrap over games, 2,000 resamples, seed 20261111. t = slope / bootstrap se.
- **Permutation p**: letters shuffled among the lettered sides within each sport x market stratum, the pooled slope recomputed, **5,000 shuffles**,
  seed 20261111, one-sided (slope greater than or equal to observed), p = (k + 1) / (5,000 + 1).
- **Per-letter cells**: n, mean, standard error (cluster by game) for (a), (b), (c) ROI and win %. Any cell under n = 30 is tagged small sample.
- **Family-wise control**: on the fit and validation sets, all 10 systems x 2 targets ((a), (c) ROI) = 20 permutation p-values each, adjusted by
  Holm. Only one system reaches the sealed set, which is a single pre-declared test of 2 targets, so its threshold is Bonferroni 0.05 / 2 = 0.025
  and its intervals are 97.5%.

## 7. Selection (validation) and freezing

1. Fit set: marks from moves only. Outcomes on the fit set are computed and reported (screen): a system passes the screen when its pooled fit
   t-statistic on (a) plus on (c) ROI is above 0.
2. Validation set: V = (t on (a) + t on (c) ROI) / 2, pooled. The chosen system is the screen-passing system with the largest V (ties: the lower id).
   When none passes the screen, the chosen system is the largest V of all 10, and the write-up says so.
3. The chosen system is written into `docs/sharps-v2-movegrade-search-results.md` with its marks and committed (**frozen**) before the sealed set's
   outcomes are computed. The sealed set is then read **once**, whatever it says.

## 8. Pass rule (sealed set, chosen system only)

A system **WORKS** only when all of these hold on the sealed set for target (a) or for target (c) ROI:

1. pooled slope (NBA+NFL+CFB) with its 97.5% cluster-bootstrap interval above 0;
2. permutation p below 0.025;
3. slope point estimate above 0 in at least 2 of NBA, NFL, CFB;
4. practically meaningful: (a) slope at least 0.05 points of no-vig fair per letter step; (c) slope at least 1.0 point of ROI per letter step and
   A minus D ROI at least 3.0 points;
5. ordered: mean A >= mean D and mean B >= mean D on that target.

Otherwise **NO-GO** (or **INCONCLUSIVE** when the sealed set is too small to read: fewer than 30 sides in A pooled, or fewer than 2 sports with 100
lettered sides). A pass makes it only a candidate: written as PROPOSED rule `mg-2` with a separate dated forward prereg text, forward shadow only.

## 9. Also reported (report only, never a pass)

- The 205 graded plays by the chosen system's letter (point in time at each play's cut): (a), (b) stored clv, (c) at the stored price.
- Alternative framings: (i) the move that already happened as a descriptive label (shares by letter; no claim about results); (ii) a "moved against"
  caution marker: sealed-set mean of against minus D on (a) and (c) with a 95% interval.
- After the sealed read is written, all 10 systems on the sealed set, Holm-adjusted, labelled exploratory (cannot change the verdict).

Scripts: `scripts/research/mgs_*.py`, `python3 -I`, stdlib only. Times Central. No em dashes.
