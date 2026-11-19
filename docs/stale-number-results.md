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

## Priced (2026-11-19, registration `docs/stale-number-price-prereg.md`)

The line gap converted to price, two ways (rules in the registration, written and pushed before this ran). Primary cut, T = 2, profit per 1 unit staked at the stale book's stored price (mean juice about -115), clustered by game, treatment against the pack-reversion control:

| Sport | Games | Realized (graded) | Control realized | Realized difference | Expected (from outcomes) | Control expected | Expected difference |
|---|---|---|---|---|---|---|---|
| NBA | 38 | +4.1% (95% interval 28.4) | -0.2% (208 games) | +0.04, interval 0.30 (not different) | +4.3% (2.2) | -1.1% | **+5.4 pts, interval 2.4** |
| CFB | 18 | +41.0% (37.2) | -7.8% (174 games) | +0.49, interval 0.39 (not different) | +0.3% (5.1) | -3.0% | +3.3 pts, interval 5.1 (not different) |
| NFL | 0 | | | | | | |

Verdict: **still not proven.** The pass rule needs both measures to clear the control with 100+ games; there are 56, and the realized measure is inside its interval in both sports.

- **The points-to-price map is sane.** Measured on 222 NBA and 270 CFB games with a stored final: the closing line leaves about 49% cover, 49% not and 2% push, so the same map prices a plain -110 bet near the vig. A number 1.5 points better than the close wins about 54.7% in NBA.
- **What it says for NBA:** after paying about -115, a 1.7 point stale number is worth about +4% expected per unit, against about -1% for a stale number when Pinnacle did not move. That is a real gap on the model-based measure. The realized results on 38 games (+4%, interval 28%) are too few to confirm or deny it.
- **CFB is not different from the control** on either measure, with 18 games.
- **Flagged for close monitoring (improves, small sample):** NBA at T = 1, expected measure: +2.5% (interval 1.2) on 107 games, +3.6 points over the control (interval 1.4); realized +6.3% (interval 15.9). T = 1 is a registered report cut, not the primary one, so it is not a pass. NBA with Pinnacle's limit up at T = 2: expected +6.3% on 31 games.
- **Limits of the map:** fitted on all games including each play's own game (a small leak, the same for treatment and control), no push or price adjustment for key numbers in NFL (no NFL signals here), and the stale price must still be there when a follower acts (median 30 minutes in NBA).

Next: the CBB tape reads forward on its own. No new thresholds on this data.
