# Spread and total price floor: held-out result (2026-11-25, 10:20 PM CT)

Pre-registration: `docs/sptot-price-floor-prereg.md` (committed before this was run). Script: `scripts/sptot_floor_test.py`.
Ledgers: `sharp-data/v2_watch.json` and `v2_passed.json` as of Nov 25, 2026 about 10:10 PM CT. Graded at the first-sight price at the
named book. ROI interval: 95% bootstrap, 10,000 resamples, seed 585. CLV: mean of the stored close against the first-sight price,
only on rows that have one (n shown).

**Choice on train (Oct 18 to Nov 8):** no P1 band reached 30 settled rows (P1 had 9 rows at 52% and up, 0 at 53% and up), so the
choice fell to P2: the 52% band, 182-155, +7.34u, ROI +2.2% (95% -7.9% to +12.3%) on 337, CLV -3.79% (n 41).

## Held-out (Nov 9 to Nov 25), full set at price >= floor

| Population | Floor | n | W-L-P | Units | ROI | 95% interval | CLV (n) |
|---|---|---|---|---|---|---|---|
| P1 (Pinnacle + Novig, all other gates) | 55% (current) | 0 | 0-0-0 | 0 | - | - | - |
| P1 | 54% | 0 | 0-0-0 | 0 | - | - | - |
| P1 | 53% | 1 | 1-0-0 | +0.88 | +88.5% | - | - (0) |
| P1 | 52% | 15 | 10-5-0 | +4.08 | +27.2% | -23.6% to +65.6% | +1.31% (4) |
| P2 (Pinnacle edge 2-10%, under 48h) | 55% (current) | 8 | 5-3-0 | +0.90 | +11.3% | -55.4% to +57.5% | - (0) |
| P2 | 54% | 86 | 45-41-0 | -3.66 | -4.3% | -23.5% to +14.9% | -6.75% (4) |
| P2 | 53% | 317 | 172-145-0 | +3.32 | +1.0% | -9.4% to +11.5% | -5.67% (25) |
| P2 | 52% | 727 | 369-358-0 | -30.97 | -4.3% | -11.0% to +2.4% | -4.15% (79) |

Added band only, held-out: P2 [52%, 55%) 364-355, -31.87u, ROI -4.4% (-11.5% to +2.3%) on 719, CLV -4.15% (79).
P1 [52%, 55%) is the same 15 rows as the full set above.

## Verdict: keep 55%
The pre-registered rule needs the chosen floor's band in P1 to show ROI above 0 with the interval's low end above 0, CLV not
negative, and P2 agreeing. P1 has 15 held-out rows and an interval from -23.6% to +65.6%, with CLV on only 4 of them. The chosen
52% floor in P2 lost 4.4% on 719 held-out rows with CLV -4.15%. Every floor's P2 CLV is negative. The floor stays at 55% and is
not changed in PR #585.

## Limits
- Only Novig was stored as a second price, and without liquidity, so P1 is an upper bound on the PR #585 rule; Kalshi and
  Polymarket spread/total quotes were never stored.
- CLV exists for a minority of rows (stored closes are mostly Novig).
- P1 is too small to say anything either way. Rerun once the PR #585 `xref` block has been logged for a few weeks.
