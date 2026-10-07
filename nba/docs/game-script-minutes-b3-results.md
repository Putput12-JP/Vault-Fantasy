# Game Simulation v2, step B3: results

Rules: docs/game-script-minutes-b3.md.

## Development check: fit 2022-23 and 2023-24, score 2024-25 (informational, not a test)

Shock sd starters 1.77 to 1.92 min, bench 2.87 to 2.97 min, starter-bench correlation -0.46 to -0.33 after the clamp calibration. 2024-25 was already used to find the bench miss, so this is a sanity check on the calibration, not a test; the freeze does not depend on it.

- Fit rows 55,097; scored rows 27,833; team-games 2,642; overtime share observed 5.0%.

| Check | Rule | M4 with clamp calibration | M4 uncalibrated (B2) | B0 independent | Pass |
|---|---|---|---|---|---|
| Starters 80% coverage | 76% to 84% | 82.7% |  | 82.7% | yes (with rank rule) |
| Starters mean rank of actual | 0.50 +/- 0.02 | 0.512 |  | 0.509 |  |
| Togetherness, starters with starters | inside observed 95% interval | model +0.234, observed +0.220 (+0.193 to +0.247) | +0.218 | -0.000 | yes |
| Togetherness, bench with bench | inside observed 95% interval | model +0.175, observed +0.214 (+0.172 to +0.255) | +0.164 | +0.000 | yes |
| Togetherness, starters with bench | inside observed 95% interval | model -0.038, observed -0.032 (-0.050 to -0.014) | -0.048 | -0.000 | yes |
| Mean minutes MAE vs M1 | within 0.05 | M4 5.031, M1 5.009 |  | B0 5.036 | yes |
| Overtime share | within 1.5 points or the observed interval | simulated 5.3% vs observed 5.0% |  |  | yes |
| Starters with starters interval excludes zero | required | yes |  |  |  |

**GO** under the B3 rules (coverage ok, togetherness ok, mean minutes ok, overtime ok).

