# Game Simulation v2, step A: copula fit results

Rules: docs/copula-fit.md (committed before the fit). Verdict: **NO-GO**.

- Kept families (frozen): 6 of 26. Explore: 525 games / 12,595 legs. Test: 393 games / 11,158 legs.
- **Test total gain over independence (2025-26, opening prices):** +56.7 log-lik, SE 10.4, z +5.43 on 47,067 pairs. Rule: z >= 2.0.
- **Calibration slope:** 0.36 (95% interval -0.07 to 0.78). Rule: contains 1 and excludes 0.
- Robustness, frozen model on pre-tip closing prices: +4.4 log-lik, SE 4.1, z +1.06 on 11,831 pairs; slope -0.14.
- Informational, one rho per relationship instead of per family: +131.6 log-lik, SE 22.9, z +5.74.
- Informational, sign agreement with the covariance method (teammates and opponents): 20 of 20 families.

| Family | Pairs | rho | SE | z | Kept | 2-pick lift at 50% | Test gain | Test z |
|---|---|---|---|---|---|---|---|---|
| Same player: points with rebounds | 2,292 | +0.261 | 0.031 | +8.4 | yes | 1.168 | +34.5 | +4.0 |
| Same player: points with 3-pointers | 1,354 | +0.450 | 0.056 | +8.0 |  | 1.297 |  |  |
| Same player: rebounds with assists | 1,432 | +0.228 | 0.040 | +5.6 |  | 1.146 |  |  |
| Teammates: points with points | 9,492 | -0.057 | 0.014 | -4.1 | yes | 0.964 | +2.0 | +0.7 |
| Same player: points with assists | 1,794 | +0.128 | 0.036 | +3.5 |  | 1.082 |  |  |
| Teammates: assists with 3-pointers | 4,446 | +0.080 | 0.024 | +3.4 | yes | 1.051 | +5.8 | +1.6 |
| Teammates: points with assists | 10,548 | +0.051 | 0.015 | +3.3 | yes | 1.033 | +10.5 | +3.1 |
| Opponents: rebounds with rebounds | 6,234 | +0.048 | 0.020 | +2.4 | yes | 1.030 | -0.4 | -0.1 |
| Same player: rebounds with 3-pointers | 984 | +0.113 | 0.049 | +2.3 |  | 1.072 |  |  |
| Teammates: points with 3-pointers | 7,531 | -0.038 | 0.019 | -2.0 | yes | 0.976 | +4.2 | +1.8 |
| Same player: assists with 3-pointers | 874 | +0.109 | 0.054 | +2.0 |  | 1.069 |  |  |
| Opponents: points with 3-pointers | 8,336 | +0.025 | 0.016 | +1.6 |  | 1.016 |  |  |
| Teammates: rebounds with 3-pointers | 5,913 | +0.032 | 0.020 | +1.6 |  | 1.020 |  |  |
| Teammates: points with rebounds | 14,535 | +0.019 | 0.013 | +1.5 |  | 1.012 |  |  |
| Opponents: assists with assists | 3,428 | +0.029 | 0.025 | +1.1 |  | 1.018 |  |  |
| Teammates: assists with assists | 3,082 | -0.023 | 0.027 | -0.9 |  | 0.985 |  |  |
| Opponents: 3-pointers with 3-pointers | 1,741 | +0.029 | 0.035 | +0.8 |  | 1.018 |  |  |
| Opponents: points with rebounds | 16,065 | -0.008 | 0.012 | -0.7 |  | 0.995 |  |  |
| Opponents: assists with 3-pointers | 4,938 | +0.013 | 0.021 | +0.6 |  | 1.009 |  |  |
| Opponents: points with assists | 11,810 | +0.005 | 0.014 | +0.4 |  | 1.003 |  |  |
| Teammates: rebounds with rebounds | 5,688 | -0.007 | 0.021 | -0.3 |  | 0.996 |  |  |
| Teammates: 3-pointers with 3-pointers | 1,560 | +0.009 | 0.038 | +0.2 |  | 1.006 |  |  |
| Opponents: points with points | 10,485 | -0.003 | 0.013 | -0.2 |  | 0.998 |  |  |
| Opponents: rebounds with assists | 9,164 | +0.001 | 0.016 | +0.1 |  | 1.001 |  |  |
| Opponents: rebounds with 3-pointers | 6,438 | -0.001 | 0.020 | -0.1 |  | 0.999 |  |  |
| Teammates: rebounds with assists | 8,313 | +0.001 | 0.018 | +0.0 |  | 1.000 |  |  |

## Post-hoc notes (written after the verdict; they do not change it)

The verdict above is the pre-registered one: **NO-GO**, because the calibration slope's interval (-0.07 to 0.78) excludes 1. What follows was looked at afterwards and is only for planning step A2.

1. **The test design has a flaw: it assumes the market's single-leg prices are unbiased, and they are not.** Overs hit below their no-vig price: mean (over hit minus price) was -3.9 points in 2024-25 and -2.0 points in 2025-26 (opening prices), -2.2 at the 2025-26 close, worst on assists, rebounds and 3-pointers (up to -6.5 points). The slope used the both-over cell, so that bias lowers it directly: in every kept family both-over was observed below independence (-1.7 to -3.7 points) and both-under above it (+1.4 to +6.3 points), including families where the copula predicted both-over above independence. A symmetric bias in the prices moves both cells in opposite directions and says nothing about dependence.
2. The total-gain test is less exposed than the slope, but the same bias flows into it, so the z of +5.4 should not be read as confirmed dependence either.
3. Per-family slopes were erratic for the same reason (for example teammates' points with assists: gain z +3.1 but a negative both-over slope). Same-player points with rebounds is the one family strong on every cut (rho +0.26, test gain z +4.0, slope 0.54 with an interval of 0.11 to 0.98).
4. Shrinking the fitted correlations helps as expected (half-size: slope 0.71; empirical-Bayes shrink on all 26 families: slope 0.69, interval 0.31 to 1.06), which fits winner's-curse on the 6 families kept by |z|.
5. All 20 teammate and opponent families agree in sign with the covariance method.

## Step A2 (to be pre-registered before it is run)

- Re-center the marginals before measuring dependence: shift each stat's latent threshold by the over bias fitted on the explore season, so the single-leg prices the copula sits on are calibrated.
- Score dependence with the agreement outcome (both over or both under against one of each), which a symmetric price bias cancels out of, instead of the both-over cell.
- Shrink by empirical Bayes across all families instead of selecting on |z|.
- Holdout: the 2026-27 regular season (2025-26 has now been looked at). Fit on 2024-26 combined, frozen before opening night; scored once 150 games have settled.

Until A2 passes, rule 6 of docs/copula-fit.md applies: the simulation keeps independent stats except the team-score tie.
