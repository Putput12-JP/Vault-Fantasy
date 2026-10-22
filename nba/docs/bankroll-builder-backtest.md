# Bankroll Builder: backtest on the first nights (run 2026-10-22)

Rules: `nba/docs/experiment-log.md` section 12 (frozen before this ran). Code: `python3 scripts/bankroll_builder.py --backtest`.

**What it is.** The recorded SmartStake tape (10/19 to 10/22, 556 polls) replayed poll by poll through the same code the live tracker uses. For each poll the board
is rebuilt from the recorder's stored snapshots (nba-data branch, rows cut off at the poll), and the model's chance comes from the model files as they stood in
git at that moment (12 daily-refresh commits used, none from after the poll). Picks are logged at the first poll they qualify, followed to tip, settled from the
ESPN box score, graded flat 1 unit at entry. 472 boards rebuilt.

**Limits.** Two regular-season nights only (10/20, 10/21); tonight's slate is not settled. The prop model's fitted parameters (variance, calibration, stacker) are the
ones on hand, last refit 2026-10-09, before any regular-season game, so nothing in them has seen these nights. The tape has gaps (poll spacing 5 to 30 minutes).
The opening-night slate (10/20) produced no picks: its rosters were on roster holds. Sample sizes are tiny; **nothing below is evidence for or against the rules.**

## The rules as frozen (3+ venues, market edge 4%+, model clears price by 2+ points)

| | picks | settled | won | units | ROI | CLV |
|---|---:|---:|---:|---:|---:|---:|
| All | 8 (1 more held back by the slate cap) | 7 | 3 | -1.74 | -24.9% (z -0.76) | +10.1% (n 7, 2 SE = 5.9 pts) |
| Core | 4 | 4 | 1 | -2.20 | -55.0% | +12.8% |
| Standard | 4 | 3 | 2 | +0.46 | +15.3% | +6.4% |

Picks: 7 unders, 1 over; 7 main lines, 1 alt line; 5 three-pointers made, 2 rebounds, 1 PRA. All on the 10/21 slate. Won 43% against a market fair chance of 59%
and a model chance of 68% (n=7).

**Flag, improves but tiny:** the average closing-line value is positive (+10.1%, n=7) while units are negative (-1.74u). Seven picks cannot separate either from noise.

## Shadow logs (not bets): do the gates add anything?

| | picks | settled | won | win rate | model said | market said | units | ROI | CLV |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Market liked, model did not (`market_only`) | 14 | 12 | 6 | 50% | 43% | 58% | -0.92 | -7.6% | +6.6% (n 12) |
| Model liked, market did not (`model_only`) | 46 | 33 | 16 | 48% | 65% | 54% | -4.03 | -12.2% | +2.6% (n 33) |

The model-only legs are the one thing here with a usable sample: the model claimed 65% and they won 48% (n=33). That is the reason the model is a filter on top of
the market's price and never the edge on its own. It matches the earlier prop backtests (the model alone loses to the market).

## Volume check (exploratory, NOT adopted): looser gate

The same replay with Combo Check's gate (2+ venues, market edge 3%+) instead of 3+ venues and 4%+: **8 picks made, 6 more held back by the caps** (5 by the 8-per-slate
cap, 1 by 2-per-team-game), 7 settled, 4 won, +0.09 units, CLV +8.0% (n 7). Same size of sample, no information about which gate is better. The caps are not what limits
the strict version (1 held back).

## What this says about volume

At -110 to -220 the books price close to the market's no-vig price: a live check on 10/22 found about 3,400 legs in the band and almost none are 4% better than three other
venues. The strict rules made 8 picks over two regular-season nights, about 4 per night, none on the opening night. A board of a dozen plays a night would need either
a looser edge gate or a wider price band, and neither has a record yet.
