# Signal research: does sharp money, or anything else, earn a place in the agree count?

Date: 2026-10-13. Free data only, from the stored ledger (`state.json` on the `sharp-data` branch) and `data/*.json`.

Scripts (rerun with `--state <state.json>`, or leave it off to read `origin/sharp-data`):

- `scripts/research/sharp_role_backtest.py` writes `docs/signal-research-sharp.json`
- `scripts/research/candidate_signals.py` writes `docs/signal-research-candidates.json`
- `scripts/research/common.py` holds the shared stats and the admission rule

## Rules used

- Split: chronological by kickoff. First 60% of games train, last 40% are held out. Any threshold (large buy, early buy) is fixed on the train rows only, then frozen. The other cut-offs (a 1-point line move, a 2-point price gap) were fixed before looking and not tuned.
- First signal only per game, market and side (same as the frozen ledger).
- A signal is added to the agree count only if, on the held-out rows, it has at least 100 decisions, beats the fair probability logged at alert time, is significant (z at least 1.64), and is not negative on ROI at a stored price or on stored closing-line value. Fair, price and CLV are all stored numbers. Nothing is estimated.
- Sharp money stays context only. It never counts toward an agree total, whatever this research finds.

## 1. Sharp money in a narrower role (held out)

Data: 583 graded first sharp alerts (345 train, 238 held out; the split falls at kickoff 1791586800, about 2026-10-09 23:00 UTC). Large cut: $6,494 (train top quartile). Early cut: 21.8 hours before kickoff (train top quartile).

| Role | Held-out W-L | Win % | vs logged fair | ROI at stored exchange price | Mean CLV | Verdict |
|---|---|---|---|---|---|---|
| All first sharp alerts | 113-122 | 48.1% | -3.5 pts (z -1.04) | -1.0% (235 priced) | +0.002 (stored) | Leave out |
| Very large (>= $6,494) | 37-34 | 52.1% | -2.9 pts (z -0.50) | +5.1% (71 priced) | +0.003 | Leave out |
| Very early (>= 21.8h) | 32-36 | 47.1% | -4.8 pts (z -0.79) | +1.2% (68 priced) | +0.003 | Leave out |
| Very large and very early | 11-8 | 57.9% | +4.5 pts (z 0.40) | +28.8% (19 priced) | +0.011 | Leave out (19 decisions) |
| NFL | 35-40 | 46.7% | -3.2 pts | -2.6% | +0.001 | Leave out |
| CFB | 65-69 | 48.5% | -3.7 pts | +0.6% | +0.002 | Leave out |
| NBA | 13-13 | 50.0% | no fair stored | -4.5% | none | Leave out |
| Tiebreaker (bet signals tie, sharp backs one side) | 2-2 (9 cases total) | 50% | -0.0 pts | -27.5% (3 priced) | +0.002 | Leave out (4 decisions) |

Does a sharp alert make a bet pick better? Held-out bet picks (line, money or behind) with a sharp alert on the same side: 53-54-1 (49.5%, mean CLV +0.007 on 84). Without one: 35-35-1 (50.0%, mean CLV -0.010 on 50). No difference in win rate. The CLV gap (+0.017) is on tiny samples and is not a win-rate effect.

Result: sharp money does not beat the market in any narrower role on held-out games. The only slices with positive ROI are small (71 and 19 priced rows), and the 19-row slice is exactly the kind of cut that looks good by chance. Sharp stays out of the agree count and stays context only. This matches the earlier Polymarket study in `docs/retro/sharp-money-study.md`.

## 2. Candidate replacement third signals (held out)

| Candidate | Train | Held out | Verdict |
|---|---|---|---|
| Pinnacle line move of 1+ point from the first logged number, followed at the new number | 26-19 (57.8%), mean CLV +0.056 | 16-15 (51.6%), 0.3 SE over fair, mean CLV -0.031 | Leave out. 32 decisions. |
| same, spreads only | 12-6 (66.7%) | 7-6 (53.8%), mean line CLV -0.115 | Leave out. 13 decisions. |
| CFB model 5+ point edge vs the first spread (this season) | 11-12 (47.8%), CLV +1.96 pts | 20-14 (58.8%), CLV +1.13 pts, z 0.75 vs 52.4% break-even | Leave out. 34 decisions. |
| Injury and rest news | no history | no history | Not testable |
| Polymarket price at least 2 pts under Pinnacle fair (ML) | 1-2 | 0 held-out rows | Leave out. 3 rows in total. |
| Kalshi or Polymarket price vs model | not testable | not testable | Not testable |

Notes:

- **Line move from open** looked strong on train (66.7% on spreads) and fell to a coin flip on held-out games with negative CLV. That is the usual shape of an in-sample pattern. "Open" here is the first number we logged, not the true open, and the sample is 77 line moves from 71 games, mostly CFB.
- **CFB opening-line edge** is the only candidate with a real historical case: the stored backtest has 435-321 against the open and 368-346 against the close (2022-2025). Two limits keep it out. The model was tuned on 2022-2023, so those seasons cannot be called held out, and the stored totals do not split by season. And the open is the number books post with small limits, so it is not a reliably bettable price. This season it is 31-26 overall (54.4%) and 20-14 on the held-out weeks, which is 34 decisions. It stays a published record on the CFB Model page, not a signal in the agree count. **Flag for close monitoring: 34 held-out decisions (57 this season).**
- **Injury and rest**: `data/nflverse_injuries.json` holds today's status only. With no record of when a status changed, it cannot be placed before a line move. To make it testable, start storing a dated copy every hour. No schedule-rest table is stored either.
- **Polymarket vs Pinnacle**: the rule fired on 3 games (no price gap is common because the exchange sits close to Pinnacle). `data/pm_vs_books.json` (existing study) has `lead: false` and, at its 2-point gap, 64-39 on 103 bets with ROI -10.2% and CLV +0.001. The 4-point rows (8-2, 10 bets, ROI +22.4%) are too small to trust.
- **Kalshi vs model**: the ledger keeps Kalshi game prices as trade tapes only. No price history is joined to a model price for finished games. The `kb-data` branch was not examined.

## Decision

No signal is added. The agree count stays at three bet signals (line, money, behind). No tracking changed, so no record was recomputed and there is no old-versus-new table for this section. The only code change that touches tracking is the grading fix in `docs/dropped-plays-audit.md`, which changes no stored number today.

## What would change the answer

1. 100+ held-out CFB opening-line decisions (roughly 3 more weeks at the current pace) with the open actually bettable (store the price and the limit, not only the line).
2. A dated injury snapshot history, started now.
3. A true opening line for the line-move test, not the first number our poller saw.

## Caveats

- All samples are one season, mostly one month. Several held-out cells have under 40 decisions even where they are shown.
- Most stored alerts have no American price. ROI uses the stored exchange price (a probability, before fees) only where the alert carries one. NFL and NBA spread rows have no price, so they are judged on the logged fair probability and CLV.
- Alerts within a game are correlated. The z values treat them as independent, which makes them look more significant than they are, and none passed anyway.
