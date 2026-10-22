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

## Data and history

- **Forward record** starts when the recorder change merges. It is the only record that carries a headline.
- **Backtest series:** `data/lean_rows_nba.json` (2025-26, model fit on 2024-25), shown separately and labelled "backtest, not forward".
- **Edge-selected subset:** existing live bets already carry mu and line. They can be shown as a lean view, labelled as selected by
  the 3% rule, so never as the lean record.
- **Open question for phase 4:** whether the snapshot tape since opening night can rebuild leans without hindsight pricing. If it
  cannot, those days stay out. No rows are invented.

## Build order

1. This document and the branch (done).
2. Capture: a `leans` source in `ledger.py`, same poll, same pricing path.
3. Settle and cube: a `leans` section in `track.json` with the baselines.
4. Backfill as above.
5. UI: Leans tab on the NBA Track Record, lean badge on Player Props, changelog entry.
6. Verify with one local poll and one hand-checked settled game; desktop and mobile screenshots.
7. PR, with the description split into Model/data and UI, old and new numbers.

Experiment-log row: to be added to `nba/docs/experiment-log.md` once PR 29 (which edits that file) merges.
