# Stale number replay: first read (2026-11-19)

Registration: `docs/stale-number-prereg.md` (committed before this was run). Script: `scripts/stale_number_replay.py`, output `data/stale_number_record.json`.
Context only. Nothing here is a pick or counts toward an agree total.

## Verdict: not proven (the pass rule needs 100 games at T = 2; there are 56)

Primary cut, T = 2, line CLV in points, treatment against the pack-reversion control (clustered by game):

| Sport | Games | Mean CLV | Beat | Control mean (games) | Treatment minus control |
|---|---|---|---|---|---|
| NBA | 38 (45 rows) | +1.84 | 93% | +0.78 (208) | +1.06, 95% interval 0.47 |
| CFB | 18 (19 rows) | +1.19 | 79% | +0.50 (179) | +0.69, 95% interval 1.02 (not different from 0) |
| NFL | 0 | | | 0.00 (3) | |

- **The control is positive too** (NBA +0.78, CFB +0.50): a book hanging a number 1 point off Pinnacle drifts toward Pinnacle even when Pinnacle did not move. This is the pack reversion the earlier study warned about, so the raw CLV overstates the signal. Only the difference counts.
- **NBA clears its own interval; CFB does not; NFL had no signal.** The rule needs 100 games and the same sign per sport with 20+ games. CFB has 18.
- **Flag for monitoring (improves, small sample):** NBA with Pinnacle's limit up, T = 2: +2.04 CLV, 100% beat, 31 games (34 rows). It is a post-hoc slice of a 45-row cut, so it is a hypothesis.
- **Looser cuts have more games** (NBA T = 1: 107 games, +0.71 over control, interval 0.28) but T = 1 is the weaker, non-primary cut.

## Why this is not yet a bettable edge

1. **Line CLV is not price.** The stale book's juice is not converted to probability, and the earlier steam record found soft prices cost about 1.1 to 1.3 points against the close. A 1.7 point line gap may or may not beat that. This replay does not answer it.
2. **The stale number does not last.** In NBA the median time until that book's line changed was 30 minutes (CFB 60), and 13% to 11% never changed. Polls here are 5 to 15 minutes, so the follower's window is real but short.
3. **The tape may lag the book.** A quote can be old (median age 0 to 10 minutes at the signal), so some "stale" lines may be tape lag rather than the book.
4. **CBB, the sport in the post, is not covered.** The tape has no CBB.

## Next

Forward test only, not new thresholds on this data: add a CBB tape, convert the line gap to a price with the stored trade market or a fitted points-to-probability map, and re-read when the pass rule's 100 games exist.

## Live flag (2026-11-19)

The same registered rule now runs live in `scripts/fetch-sharp-money.mjs` (`G.stale`, alert type `stale`) and shows as a gold "Stale number at <book>" tag on the slate and a gold card on the game page. It is labelled "untested rule" and "context only", is not in `EF_KIND` or `BET_KINDS`, and never feeds Top Reads, SM_GATE or an agree total. Differences from the replay, stated so the two are not confused: the base line is the value in effect at the start of the 90 minutes (the replay used the earliest stored row in the window), and history for each soft book starts when this code first runs, so the first signals appear about 90 minutes after deploy. The EV shown is Pinnacle's fair at that number from its alternate ladder, null when it has none.
