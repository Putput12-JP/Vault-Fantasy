# NFL joint-sim prop backtest (research only)

Branch: claude/nfl-joint-sim-props. Nothing is wired into the site.

## Verdict: NO-GO

The shared-environment Monte Carlo loses to the no-vig market and to the current Vault prop model, both in and out of sample.

## Setup
- 12,599 props over 36 weeks (ESPN 10,570, Vault 2026 log 2,029): rec 4,939, rec_yd 4,699, rush_yd 2,125, pass_yd 836.
- In-sample: 2024 wk 1-18 (5,469). Out-of-sample: 2025 wk 1 to 2026 wk 13 (7,130).
- Walk-forward: every rolling share, efficiency and injury-gain table filters to games strictly before the target week. Absences come from the pregame injury report (Out). No sportsbook inputs; lines are only used after sim (p_over vs line in runner.py).
- Edge gate chosen in-sample only: theta 0.15 (max in-sample ROI at close).

## Results (gated, theta 0.15, open prices)
| Split | Record | Units | ROI | ROI 90% CI |
|---|---|---|---|---|
| In-sample | 1370-1406 | -124.1 | -4.5% | -7.5% to -1.4% |
| Out-of-sample | 2016-1904 | -78.2 | -2.0% | -4.6% to +0.5% |
| OOS at close | 2059-1954 | -114.0 | -2.8% | -5.3% to -0.4% |
| OOS, all edges | 3160-3007 | -202.4 | -3.3% | |

CLV (price, open to close): mean -4.5 cents OOS, only 18% positive.

## Calibration vs no-vig market (OOS, open)
Brier 0.277 vs market 0.248; log loss 0.772 vs 0.688. Sim means run low (rec_yd 32.6 vs actual 39.0, rush_yd 35.3 vs 42.7, rec 2.71 vs 3.25). Intervals too narrow (rush_yd 10-90 coverage 70%). Sim adds little over the line: OOS RMSE worse than line in every market; best line+sim blend gains under 1%.

## By market (OOS, open)
rush_yd 413-345 +17.0u +2.2% (close +3.2%, but CLV -6.5c, 2% positive); rec_yd 710-677 -39.8u; rec 825-809 -42.3u; pass_yd 68-73 -13.1u.

## Head-to-head vs current Vault model, same 2,022 2026 props
Brier: sim 0.287, Vault 0.254, market 0.247. All edges: sim 910-906 -98.3u (-5.4%), Vault 748-714 -15.5u (-1.1%). Gated: sim 640-606 -29.6u, Vault 275-275 -1.4u.

## QB-WR correlation
Sim QB vs WR1 yards 0.53 (p10 0.44, p90 0.61), QB-WR2 0.42, WR1-WR2 0.00 (expected negative). Empirical QB vs pregame WR1: 0.48. Brief's prototype: ~0.35.

## Caveats
- rush_yd positive ROI is the only bright spot; negative CLV and wide CI say noise. Overs +7% OOS on just 285 bets, also noise.
- ~1% of prices assumed (missing juice).
