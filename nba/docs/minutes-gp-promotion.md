# GP promoted to the priced minutes, 2026-10-29

Rule and results: [minutes-bakeoff.md](minutes-bakeoff.md), [minutes-bakeoff-results.md](minutes-bakeoff-results.md). Audit that started it: [minutes-audit-2026-10-28.md](minutes-audit-2026-10-28.md).

## What changed
- **Pricing** (`pricing.py` `gp_minutes`, and its JS twin `ui/rotation_minutes.js`, proven equal by `check_rotation_minutes_js_parity.py`: max difference 2e-14): conditional minutes come from the GBM (v2's number for a player it does not score), P(plays) from the rotation model, and the pool is rescaled so expected minutes (P x minutes) sum to 239.67. The early-season blend no longer applies to players GP covers. v2 stays in the preseason, in the example and when either state is missing.
- **Page**: Tonight shows the chance he plays, a team line "240 expected minutes (N if every player dressed)", and moves players under 25% to a line below the table. Minutes are still "if he plays".
- **Ledger**: the Minutes record keeps v2 in column 0 (so every old day stays comparable) and adds GP's minutes and P(plays) in columns 14 and 15, with a `gp` block per day (MAE, bias, misses, minutes on players who did not play, expected-minutes MAE).

## Old and new, 2025-26 backtest (27,799 player-games who played; 34,443 pool rows)
| | v2 | GP |
|---|---|---|
| Minutes MAE | 4.922 | 4.655 |
| Misses of 8+ minutes | 18.8% | 16.6% |
| Top 8 bias, pool 12 or fewer / 13-14 / 15 or more | +1.22 / -0.39 / -1.83 | +0.41 / +0.23 / +0.13 |
| Expected-minutes MAE (DNP = 0) | 5.256 | 4.983 |
| Team expected minutes | 236.9 | 239.7 |
| Pts / reb / ast / 3pm MAE (27,797 rows) | 4.550 / 1.870 / 1.329 / 0.885 | 4.508 / 1.859 / 1.327 / 0.885 |

Limits, stated plainly: the 2025-26 gain (5.4% on MAE) is smaller than the live gap of the first 8 days (v2 5.86 against GBM 4.98), and 8 days is a small sample. Minutes on players who did not play fall only from 26.3 to 24.8 per team-game, because conditional minutes stay conditional; the ghosts are removed from the expected-minutes view and the display, not from "if he plays".

## Records restated (`restate_lean_backtest_gp.py`)
The lean backtest, same 5,207 lines, same rule. Each projection is scaled by GP minutes over v2 minutes for the same game and player, the approximation the early-blend test used. **The stacker and calibration were not refit on GP minutes**, so read this as an estimate. The committed file (5,250 rows) did not rebuild exactly; its numbers are kept under `committed_before_restate`, and the comparison below uses the rebuild on both sides.

| Record | Old (n) | New | Over share old to new |
|---|---|---|---|
| Overall lean hit rate | 53.0% (5,207) | 51.5%, CI 49.8 to 53.3 | 50.1% to 70.3% |
| Lean minus always-under | -0.15 pts | -1.65 pts | |
| Disagrees with market | 48.1% (2,018) | 46.1% | |
| Over leans | 49.9% (3,662) | 48.8% | |
| pra | 50.6% (403) | 46.2% | |

**Records that improve, for close monitoring (sample size in brackets):** under leans 56.2% to 57.9% (1,545) and rebounds 52.5% to 52.8% (901). Both are small gains inside their intervals. Everything else is flat or worse (assists 56.0% to 53.4%, 3pm 54.3% to 53.6%, pr 52.1% to 47.5%).
The honest read: the old record leaned on v2 projecting rotation players about 2 minutes low, which made unders look good. With accurate minutes the model leans over more often and those leans hit 48.8%, so there is no lean edge in this sample. This is a worse record, not a better one.

## Not restated
- The live ledger from 2026-10-20 to 2026-10-28: its prices were stored under v2 and the daily state they came from is not kept, so GP cannot be replayed without inventing numbers. The Minutes record scores GP from its first logged night; bets from 2026-10-29 carry GP minutes.
- `backtests.json` signals (ROI by stat and venue on book and Kalshi prices): they need the whole walk re-run with GP, and the stacker refit. Tagged `minutes_basis: v2` so the page does not present them as GP.
