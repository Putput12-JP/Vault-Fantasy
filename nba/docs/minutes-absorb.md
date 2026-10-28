# Minutes: teammate-out absorption (replacement graph)

Written 2026-10-28, before any number below was computed. Script: `scripts/test_minutes_absorb.py`. Results go to `minutes-absorb-results.md`. Nothing here changes pricing.
Motivation: [minutes-autopsy-and-implied-results.md](minutes-autopsy-and-implied-results.md). Of GP's 8+ minute misses on 2025-26, those with a teammate out are 21%, and GP was too low in most of them (890 of 953, average 9.8 minutes under).

## Idea
The GBM knows how many rotation minutes are out (`vs` same position group, `vo` other groups). It does not know WHO absorbs them. Learn an absorption weight w(X -> Y): when X (out) is missing, how many minutes does Y gain per minute X normally plays, in the training seasons.
- **Role weights** (always on): rank bucket of X (1-5, 6-8, 9+ by EWMA minutes) x rank bucket of Y x same position group or not = 18 weights, fitted by ridge on `gain_Y = actual_Y - ewma_Y` for Y who played, over rows with at least one rotation player out.
- **Pair weights** (when the data supports it): for a specific pair (X, Y) with 8+ games together with X out in the training seasons, the pair weight is shrunk to the role weight: w_pair = (sum of gain per X-minute over those games + K x w_role) / (n + K), K = 10 games.
- **Feature**: absorb_Y = sum over out X of ewma_X x w(X -> Y), cap at 20 minutes. It is added to the GBM's 21 features as column 22. Same GBM params, same training seasons (2023, 2024, 2025), no oracle absences (out = rotation player not in that game's pool, as in the bake-off).
- Training rows use weights fitted on the other training seasons only (leave-one-season-out), so the GBM is not fitted on weights that saw its own rows. 2025-26 rows use weights from all of 2023-2025.

Candidates, all on 2025-26 and all through the same C3 P(plays) and the same T = 239.67 rescale:
- **GP**: as promoted (GBM conditional minutes).
- **GPA**: the same pipeline with the GBM refit including `absorb`.

## Rule (fixed now). GPA is a candidate for promotion only if ALL hold
1. **Games with at least one rotation player out** (played rows): GPA minutes MAE below GP's with paired cluster t >= 3 (game is the unit).
2. **Bias there**: |mean(GPA - actual)| below |mean(GP - actual)|, and the count of 8+ minute misses in these rows falls.
3. **No harm elsewhere**: games with nobody out, GPA MAE no more than 0.02 minutes above GP's; and overall miss8 count not higher than GP's.
4. **Top 8 by m**: mean(projected - actual) stays within 0.5 minutes in each pool-size bucket that GP meets, and in no bucket is |bias| larger than GP's by more than 0.1.
5. **Props proxy** (mu x new / old, pts, reb, ast, 3pm): no stat's MAE worse than GP's.
6. **Expected minutes** (P x minutes, DNP as 0): MAE not above GP's.
If 1 to 6 hold, the next step is a separate promotion (pricing, JS twin, parity) in its own PR step with old and new numbers; this test does not change pricing. If any fails, nothing is promoted and the failing item is reported as it is.
Context only (not in the rule): the pair-weight share of rows covered, the biggest learned role weights, and the same comparison split by number of players out (1, 2, 3+).
