# Minutes: error autopsy and market-implied minutes

Written 2026-10-28, before any number below was computed. Scripts: `scripts/test_minutes_autopsy.py` (A) and `scripts/test_minutes_implied.py` (B). Results go to `minutes-autopsy-and-implied-results.md`. Nothing here changes pricing.
Context: GP is the minutes model promoted in [minutes-gp-promotion.md](minutes-gp-promotion.md). Rule for it: [minutes-bakeoff.md](minutes-bakeoff.md).

## A. Error autopsy (2025-26, the bake-off pool)
Unit: a player-game where he played and GP missed by 8 or more minutes (the same "miss8" the bake-off counts). Cause is assigned from stored fields only, first match wins, in this order:
1. **Blowout**: final margin 20+ (`fm`).
2. **Early exit**: actual minutes under 40% of GP minutes in a game that was not a blowout (injury or foul trouble; the pool has no foul or injury field, so these two are not separated).
3. **Rotation change**: player was a top-8 by `m` and actual minutes are 8+ below GP in a non-blowout, or a player outside the top 8 played 8+ above GP.
4. **Teammate out / lineup**: `nout` of 1 or more on his team.
5. **Rest / schedule**: `b2b` = 1.
6. **Unexplained**: none of the above.
Report: share of miss8 per cause, signed mean error per cause, and the same cause shares for the whole pool (so a cause that is common everywhere is not read as a failure).
**Rule:** a cause is called "where to build next" only if it is at least 25% of miss8 AND its share of miss8 exceeds its share of all played player-games by 1.5x or more. If no cause qualifies, we say the misses are diffuse and do not build against any one.

## B. Market-implied minutes (live days with stored closes, 2026-10-20 to 2026-10-28)
Inputs: `propclose.json` (stored closing probabilities by line, pts, reb, ast, 3pm), our priced projection and v2/GP minutes from `minutes.jsonl`/`ledger.jsonl`, actual minutes from `results/`.
For each player-game and stat s in {pts, reb, ast, 3pm}: market median m_s = the line where over probability crosses 0.5 (linear interpolation between stored lines; skipped if the stored lines do not bracket 0.5). Ratio q_s = m_s / our projection_s (v2-priced). Implied-minutes gap = our GP minutes x (median of q_s over stats with 2 or more usable) minus our GP minutes. Players with fewer than 2 usable stats are dropped.
Test: regress (actual minutes - GP minutes) on the implied-minutes gap, game as cluster. Never invent a number: only stored lines and stored minutes are used.
**Rule:** the gap is useful as a news/minutes signal only if ALL hold: (1) at least 300 player-games usable; (2) slope on the gap is positive with cluster t of 2 or more; (3) in the top and bottom decile of the gap, the mean (actual - GP) has the same sign as the gap. If n is under 300 it is reported as "too small", not as a pass or a fail.
Caveat fixed now: the ratio also contains the market's view of per-minute efficiency, not only minutes. A pass means "the market knows something about our minutes or rates", not "the market's minutes". Splitting those apart is a follow-up and is not part of this pass rule.
