# Minutes: teammate-out absorption, results

Rule registered first in [minutes-absorb.md](minutes-absorb.md) (commit 57209e3ef). Script `test_minutes_absorb.py`, numbers `data/minutes_absorb.json`. Nothing here changes pricing.

**Verdict: fails the rule (1, 2 and 5 fail). Nothing to promote.** The replacement graph does not improve GP.

| Check (2025-26, 27799 played rows; 21271 with a rotation player out, 6528 with none) | GP | GPA |
|---|---|---|
| MAE, games with a player out | 4.746 | 4.743 (gain 0.003, cluster t -0.08, 1217 games) |
| Mean error (projected minus actual), games with a player out | +0.257 | +0.255 |
| Misses of 8+ minutes, games with a player out | 3681 | 3684 |
| MAE, games with nobody out | 4.361 | 4.360 |
| Misses of 8+ minutes, all | 4611 | 4608 |
| Top-8 bias, size_le_12 (n 7078) | +0.405 | +0.435 |
| Top-8 bias, size_13_14 (n 8413) | +0.231 | +0.242 |
| Top-8 bias, size_ge_15 (n 4606) | +0.127 | +0.107 |
| Props MAE, pts | 4.5079 | 4.5098 |
| Props MAE, reb | 1.8591 | 1.8584 |
| Props MAE, ast | 1.3266 | 1.3266 |
| Props MAE, 3pm | 0.8845 | 0.8845 |
| Expected-minutes MAE | 4.9829 | 4.9809 |

Rule items: 1 FAIL, 2 FAIL, 3 pass, 4 pass, 5 FAIL, 6 pass. Item 5 fails by 0.002 points on pts; the gains elsewhere are about 0.003 minutes, so this is a tie, not a loss.

## Why: the premise was wrong, and the autopsy made it look right

- **There is no teammate-out bias to fix.** In games with a rotation player out, GP is off by +0.26 minutes on average (GPA +0.25). With one, two, or three-plus out the bias stays between +0.2 and +0.3.
- **My autopsy read was a classification artifact, and I am retracting it.** The "teammate out: GP too low in 890 of 953 misses, average -9.8" line came from the order the causes were assigned. A top-8 player who is 8+ minutes too LOW was left to fall into "teammate out" or "unexplained", while a top-8 player who is 8+ too HIGH was sorted into "early exit" or "rotation change". Among misses the direction therefore looks one-sided inside each bucket even though overall bias is near zero. The autopsy results doc now carries this correction.
- The learned weights are small and plausible (an out top-5 player gives same-position bench players 0.06 to 0.09 minutes per minute he usually plays; other-position rotation players 0.00 to 0.03), and 8035 player pairs had enough joint games for a pair weight. The GBM already gets the same-position and other-position vacated minutes (`vs`, `vo`) and uses them.

## What this changes in the ranking

1. **Teammate-out lift: dropped.** Do not build more here.
2. **Left-tail minutes (early exit): still supported**, because early exit is defined by the actual (under 40% of GP minutes), always one-directional, and 15.6% of misses at 12.9 minutes each. That does not depend on the retracted direction reading.
3. **Market-implied gap: still open**, once GP minutes have live days to test against.
