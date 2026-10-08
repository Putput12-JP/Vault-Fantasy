# Pick'em pairs on different teams

2026-10-08. A re-read of the pick'em correlation test (docs/pickem-correlation.md, docs/pickem-correlation-results.md) for apps that
only let you combine players on **different teams**. No new data and no new threshold: the test already measured 15 opposing-team
families (every pair of the 5 stats, one player from each team of the same game) under the same fixed rules, and this page reads
those rows. The pooled line below was computed from the saved table after the question was asked, so it is descriptive, not a test.

## Rules that already applied (unchanged)
A family is a candidate if it has 2,000+ pairs and |z| >= 3 on 2024-25. It passes if, on 2025-26, the covariance has the same sign
with z >= 2 (game-clustered) and the 2-pick lift is at least 4% (|c| >= 0.01).

## Result: no opposing-team family qualified
- Candidates on 2024-25: **0 of 15** (the best, rebounds with rebounds, reached z +2.4).
- Passes on 2025-26: **0 of 15**. The largest lift on the test season was **+2.1%** (assists with 3-pointers, z +2.2); the 4% bar was
  never reached. Largest negative: points with rebounds, -1.5% (z -2.0).
- Pooled over all 15 (inverse-variance weights, descriptive only): covariance +0.0010 on the test season, a lift of **+0.4%**, z +1.7.
  On 2024-25 it was +0.0015 (+0.6%, z +2.3). Opposing players' stats are close to independent.

## What that means for a 2-pick on different teams
With no lift, the entry is two independent picks. At a 3x payout each pick needs **57.7%** to break even (1 / sqrt(3)); the correlated
teammate pairs that passed needed about 56.5%. So a different-teams entry only pays if *each* pick is already a strong single bet,
and the sportsbook-line tests found no stat where the model beat the price. The one live idea for that is pick'em lines that sit off
the sharp price (round 2, test 2, docs/edge-tests-r2.md), which is not testable until Pinnacle props post.

## What the page does
- Pick'em Pairs has a switch, "My app only allows picks from different teams". On, it shows no pairs and says why.
- Pick'em of the night follows the same switch: no 2-pick, only the single leans.
- The two families that passed (teammates' points with assists, teammates' assists with 3-pointers) are unchanged for apps that allow
  same-team picks.
