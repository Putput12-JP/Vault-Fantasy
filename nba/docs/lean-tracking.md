# NBA lean tracking: pre-registration

Written 2026-10-22, before any lean has been recorded or graded. The live bet ledger (`track.json`, `bets/`) has not been read for
this design. Nothing below is tuned on a result.

## Why

The shadow ledger (`scripts/ledger.py`) logs **bets**: a prop enters only when its price edge or consensus gap reaches 3%. So three
questions are unmeasured:

1. How often does the model's side win against the actual result, at any edge?
2. Does a bigger projection-minus-line gap win more often?
3. Does the model beat simply fading overs? (audit-2026-10-19.md item D5; the lean diagnostic found always-under already earns
   about +4.6 on assists, so model value over that baseline is not separable yet.)

## Definitions (fixed now)

- **Lean:** the model-only side. Over when the calibrated model P(over) at the line is above 0.5, otherwise under. This is
  `Pricer.cal(p_over_raw(...))` in `pricing.py`, with no market blend. The blended fair is stored beside it but is not the headline.
- **Population:** every prop `price_board` prices that has a posted line, regardless of edge. The 8 priced markets (pts, reb, ast,
  3pm, pra, pr, pa, ra). The EXTRA stats stay excluded, as in the ledger.
- **Reference line:** the modal line across books for the player and stat. Ties go to the line nearest the median.
- **Two clocks:** `first` (first poll the prop is seen within 24 hours of tip) and `close` (last poll before tip). Each is graded
  against its own line. Whether the side flipped between them is recorded.
- **Stored per lean:** mu, line, gap (mu minus line) and gap in standard deviations, model P, blended fair, the market no-vig side,
  minutes, starter confirmed, hold flag, and the stored price of the leaned side when one exists.
- **Settlement:** ESPN box score, the same path as the ledger. A whole-number landing on the line is a push. A player who did not
  play is void. Preseason games go to their own bucket and never count toward the record.
- **Baselines, computed on the same rows:** always-under, always-over, the market's no-vig side.
- **Sharp money:** context only. It is not an input and does not count toward any agree total.

## Reading rules (fixed now)

- No hit rate is quoted for a cell with fewer than **100 settled leans**.
- Intervals are Wilson intervals, with the clustering unit being the game (props from one game are correlated).
- Primary comparison: model lean hit rate against always-under on the same rows, paired and game-clustered. The model "adds value"
  only if the interval for the difference excludes 0 on forward data.
- A stated-confidence band is shown as **verified** only when its forward hit rate is within 4 points of its predicted P over 100+
  leans (the `lean_loop.py` rule). Otherwise it is labelled unverified.
- ROI is context only, at the stored price of the leaned side. No stored price means hit rate only. No price is ever inferred.
- Any cell that improves is flagged for close monitoring with its sample size.

## Settle format and counting (added with phase 3, before any lean settled)

- `lean_record.record()` runs inside `ledger.settle`. For each final game it writes `leans/<tip ET day>.json` (preseason: `leans/pre/`),
  two rows per lean (clock `f` first sighting, `c` last before tip), each graded against its own line: W, L, P (push) or V (did not play).
  `units` is the 1-unit profit at the stored price of the leaned side, null when none was stored. `track.json` keeps only a small per-day
  count (`leans_days`), so the page loads the day files on demand and can cluster by game.
- **Held leans** (roster guard, returning player, preseason) are recorded and tagged, but **the headline counts only non-held leans**.
  Held leans are shown as their own group, never mixed in. (On 2026-10-22 every lean on the board was held by the team guard, so the
  headline starts empty until the guard clears. This is by design and says nothing about the model.)
- **Baselines are derived on the page, not stored:** always-under and always-over from W/L and the side; the market's side from
  `p_mkt > 0.5`; agreement between model and market from `side` against that.
- **Bins (for phase 5):** gap in standard deviations |mu - line| / sd: under 0.1, 0.1-0.25, 0.25-0.5, 0.5-1, 1 and over. Confidence bands
  on the leaned side's model P: 50-55, 55-60, 60-65, 65 and over.
- The first clock reads one extra day folder back, because a lean is first seen up to 24 hours before tip.

## Data and history

- **Forward record** starts when the recorder change merges. It is the only record that carries a headline.
- **Backtest series** (`nba/data/lean_backtest.json`, built by `build_lean_backtest.py`): `data/lean_rows_nba.json`, 2025-26, model fit on
  2024-25. Descriptive only: this season was already used by the lean diagnostic and the lean search, so it is not a clean test. Rows hold
  the projection and the line, not the calibrated P or sd, so gap bins are terciles of |proj - line| inside each stat. Intervals resample games.
  Results (5,250 lines, 320 games): lean 53.3% [51.6, 55.1]; always-under 53.2%; market side 54.4%; lean minus always-under +0.1 pts
  [-2.6, +3.0]. Over leans hit 50.1% and under leans 57.0%. When the model agrees with the market's side it hits 56.2%, when it disagrees
  it hits 48.5% (the market side wins 51.5% of those). Largest-gap tercile: lean 55.7% against always-under 51.5% (+4.2 pts [-0.4, +9.4]).
  **Nothing here improves on a trivial strategy with an interval that excludes 0, so nothing is flagged for monitoring.** The forward record decides.
- **Psim-derived backfill** (`nba/data/lean_backfill.json`, built by `backfill_leans.py`): the Props Simulation record was written live before
  tip with the model's calibrated P(over) at the main line, so regular-season games that finished before the lean recorder existed can be
  rebuilt without a replay and without today's model files. Limits: pts / reb / ast / 3pm only, the last 3 hours before tip (close clock only),
  no sd, no stored price (units null), no starter flag. Left out: 61 keys of the BOS @ DET replay (rebuilt from stored prices with the model
  files on hand, not as-of) and preseason. Built 2026-10-22: 13 games, 746 rows. Only 112 are graded and not held (60 W, 52 L, 53.6%): far
  too few to say anything, so no hit rate is quoted. Shown apart from the forward record, never added to it.
- **Not built:** a lean view of existing live bets. They carry mu and line but not the model P or sd, and the psim backfill already covers
  the same props with the real model P, so it would add nothing.
- **Not reconstructed:** a replay of the snapshot tape for combo markets or the first-sighting clock. Replaying needs the model files as of
  each poll, which are not stored beside the tape, and today's files include results from the games being replayed. No rows are invented.

## Build order

1. This document and the branch (done).
2. Capture: a `leans` source in `ledger.py`, same poll, same pricing path.
3. Settle and cube: a `leans` section in `track.json` with the baselines.
4. Backfill as above.
5. UI: Leans tab on the NBA Track Record, lean badge on Player Props, changelog entry.
6. Verify with one local poll and one hand-checked settled game; desktop and mobile screenshots.
7. PR, with the description split into Model/data and UI, old and new numbers.

Experiment-log row: to be added to `nba/docs/experiment-log.md` once PR 29 (which edits that file) merges.
