# Pick'em V2: stale-line test (verdict NO-GO)

Run 2026-10-27 (Central). Follow-up to docs/pickem-v2.md. Idea: when Pinnacle's line has moved and the app's has not (app 5.5, Pinnacle 5), take the soft side.
Code: `scripts/build_pickem_stale_data.py` (rebuild from the `nba-data` branch). Pinnacle carries pts, reb, ast, 3pm and pra props only, so pr / pa / ra are not covered. Pinnacle is a price reference, never a place to bet.

Method: decide at 4, 3, 2 and 1 hours before tip. Take the app's line and Pinnacle's line at that moment (stored series, last value at or before the time). If they differ, the soft side is over when the app line is lower, under when higher. Score against the app's line at that moment; pushes are excluded. Regular season, Oct 20-26, PrizePicks standard and Underdog.

| App, decision time | legs | hit | 95% range |
|---|---|---|---|
| PrizePicks, 4h, gap 0.5+ | 370 | 52.4% | 47.3% to 57.5% |
| PrizePicks, 3h, gap 0.5+ | 379 | 51.5% | 46.4% to 56.4% |
| PrizePicks, 2h, gap 0.5+ | 394 | 50.8% | 45.8% to 55.7% |
| PrizePicks, 1h, gap 0.5+ | 419 | 49.4% | 44.6% to 54.2% |
| PrizePicks, 3h, gap 1+ | 134 | 50.7% | 42.4% to 59.1% |
| Underdog, 3h | 477 | 60.0% | 55.5% to 64.3% |

- PrizePicks pays flat and needs 54.2% to 59.1% per pick. Stale lines hit about 51% at every decision time and gap size. No edge, and nothing improves earlier in the day.
- Underdog's soft sides hit 60.0%, but Underdog cuts the payout on them: mean multiplier 0.871, single-leg ROI at its stored price -2.5%. Train (Oct 20-23, 382 legs) 62.8% hit, +0.4% ROI; holdout (Oct 24-26, 93 legs) 48.4% hit, -14.4% ROI.

Verdict: NO-GO. The 5.5-vs-5 gap is already in the PrizePicks line or too small to matter (a half point is about 2 to 4 points of chance), and Underdog prices the gap in. No change to the page; the V2 verdict stands.
