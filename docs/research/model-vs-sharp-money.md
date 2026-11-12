# Do Vault's game models and sharp money line up, and does it matter?

Date: 2026-11-12. Research only. No model, gate, Top Reads rule, SM_GATE, agree total or page was changed. Sharp money stays context only.

## Plain-English answer

**Is there a connection?** Weak, and mostly not the kind you would hope for.

- **Wallet money (proven sharp accounts, big exchange tickets) is close to a coin flip relative to the model.** Alert by alert, proven sharps are on the model's side 53% to 61% of the time and big tickets 48% to 49%, and every 95% interval includes 50%. Netting each game's dollars and comparing with the model's spread side tilts slightly *against* the model: proven sharps 52% (NFL), 50% (CFB) and 33% (NBA, interval 22% to 47%); big tickets 39% (NFL), 43% (CFB, interval 36% to 49%) and 44% (NBA).
- **Pinnacle steam usually goes against the model** (CFB 31% agree, interval 24% to 40%; NBA 41%; NFL 25% on 16 alerts). Part of this is arithmetic, not a difference of opinion: the alert is logged at the new number, the model's number does not move, so a move toward a team shrinks or flips the model's edge on that team.
- **"Book behind Pinnacle" leans with the model** (59% to 71%). That makes sense: both are measured against Pinnacle, so when a US book is slow, the model and Pinnacle often sit on the same side of it.
- **Top Reads mostly disagree with the model**: the model is on the read's side only 31% of the time in CFB (interval 26% to 37%) and 34% in NFL, and 48% in NBA. Top Reads are mostly line-move reads, so this is the same steam effect.

**Does agreement change results?** No sign that it helps. In the signal lens, 12 of the 13 families with enough rows to test did *worse* against the fair price when the model agreed than when it disagreed. Only one interval excludes zero (NFL big tickets, -19 points, which is the "agreement hurts" direction); 1 of 13 is about what chance gives. In the model lens the model's own record does not improve when sharp money backs it: 4 of about 36 gaps clear zero (three favour agreement, one goes against it), all on small cells (listed below), which is close to what chance produces. None is promoted.

The likeliest reading: this season the models are below 50% at the stored lines in all three sports (NFL 22-35, CFB 98-117-6, NBA 62-79 ATS), while the sharp signals are near the fair price. When the two disagree, the model is usually the one that is off the market. The model is not a filter that makes a sharp signal better.

**Too small to say anything:**
- Proven-sharps side cards (pm_record on `pm-holders-data`): started 2026-11-11, 1 graded play so far (NBA, a loss). Nothing to compare.
- Sharp-account net position vs the crowd (`cross`): no spread is stored on these alerts, so they cannot be lined up with the model at a number. In the model lens they are 5 to 14 games per cell.
- Every NFL cell. The NFL model has logged live (not backfilled) on 57 graded games, Oct 15 to Nov 9.
- CFB totals by family (7 to 40 games per cell), and the proven-sharp cells in NFL and CFB (42 and 57 alerts with a model view before the agree / disagree split).

## Data and rules

- Snapshot: `sharp-data` as of its 1:37 pm CT commit on Nov 12. Re-running the script later reads the current branch, so the numbers will grow.
- Sharp-money alerts: `state.json` on `sharp-data`, 12,952 alerts logged Sep 28 to Nov 12, each with its timestamp, the fair probability when logged, the stored close, CLV (close minus fair) and the graded result. Only alerts logged before kickoff, first alert per game, market, side and family. Families are kept apart and never pooled.
- Model, point in time only:
  - NFL and CFB: board rows in `data/nfl_model.json` and `data/cfb_model.json` with `backfill: false` and `logged` before kick. The board row is rewritten every run until kickoff, so it is the model's last pre-kick output. 57 NFL and 221 CFB graded games (79 NFL and 156 CFB backfilled rows dropped). CFB totals: live rows in `cfb_model.json` `totals`.
  - NBA: `nba/data/game_picks.json` rows with `src: live` (Oct 24 to Nov 11, 142 games; 28 backfilled games dropped). The first-sighting row is the published record; its CLV is the stored close-minus-first value.
  - Top Reads: the model side the poller stamped on each read, kept only when the stamp's time is before kickoff (53 of 129 NFL, 281 of 412 CFB, 181 of 313 NBA).
- Model side for an alert is taken at the alert's own line: spread and moneyline alerts use model margin plus the stored home spread (the model's value side at that number, not its winner pick); totals use model total minus the stored total. NFL has no totals model.
- ROI: flat 1 unit at the stored price (the exchange price on wallet and ticket alerts, the American price on book alerts and NBA picks). No price is stored on NFL/CFB board rows, steam or split alerts, so those show W-L, win minus fair and CLV only. Exchange fees are not taken out.
- 95% intervals: Wilson for rates; bootstrap of games (2,000 resamples, seed fixed) for ROI and for the agree-minus-disagree gap, so several alerts on one game move together.
- "vs fair" is win rate minus the average fair probability logged with the alert, in points. It is the fair comparison when one group holds more favorites than another.

Script: `scripts/research/model_vs_sharp_money.py` (reads `origin/sharp-data:state.json`, or `--state <path>`). Output: `docs/research/model-vs-sharp-money.json`.

## 1. How often the model agrees with each signal (signal lens)

| Sport | Family | Alerts | With a model view | Model agrees | 95% CI | Agree at model edge 3+ pts |
|---|---|---|---|---|---|---|
| NFL | Proven sharp accounts | 239 | 42 | 55% | [40, 69] | 100% (n 1) |
| NFL | Sharp net vs crowd | 35 | 0 | | | |
| NFL | Big exchange tickets | 402 | 195 | 49% | [42, 56] | 75% (n 4) |
| NFL | Pinnacle steam | 24 | 16 | 25% | [10, 50] | - (n 0) |
| NFL | Handle split | 68 | 31 | 64% | [47, 79] | 100% (n 2) |
| NFL | Book behind Pinnacle | 42 | 14 | 71% | [45, 88] | - (n 0) |
| CFB | Proven sharp accounts | 408 | 57 | 61% | [48, 73] | 65% (n 31) |
| CFB | Sharp net vs crowd | 50 | 0 | | | |
| CFB | Big exchange tickets | 1022 | 655 | 48% | [44, 52] | 47% (n 300) |
| CFB | Pinnacle steam | 197 | 128 | 31% | [24, 40] | 18% (n 57) |
| CFB | Handle split | 408 | 241 | 52% | [46, 58] | 51% (n 90) |
| CFB | Book behind Pinnacle | 463 | 235 | 59% | [52, 65] | 70% (n 105) |
| NBA | Proven sharp accounts | 284 | 133 | 53% | [44, 61] | 49% (n 67) |
| NBA | Sharp net vs crowd | 40 | 0 | | | |
| NBA | Big exchange tickets | 502 | 385 | 49% | [44, 54] | 51% (n 134) |
| NBA | Pinnacle steam | 101 | 85 | 41% | [31, 52] | 41% (n 46) |
| NBA | Handle split | 133 | 56 | 62% | [49, 74] | 75% (n 12) |
| NBA | Book behind Pinnacle | 183 | 117 | 61% | [52, 69] | 67% (n 55) |

## 2. Do sharp signals do better when the model agrees? (signal lens)

Each alert's own graded result, split by whether the model was on the same side at the alert's line. CLV is in cents of probability.

| Sport | Family | Agree W-L | vs fair | ROI [CI] | CLV | Disagree W-L | vs fair | ROI [CI] | CLV | Agree minus disagree, win minus fair [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| NFL | Proven sharp accounts | 9-14 | -11.2 | -25.1% [-65, 19] (n 23) | +0.9c | 10-9 | +2.0 | +4.0% [-44, 50] (n 19) | -0.3c | -13.2 [-44, 20] |
| NFL | Big exchange tickets | 39-57 | -9.0 | -17.8% [-45, 13] (n 96) | +0.5c | 60-39 | +10.0 | +19.4% [-5, 44] (n 99) | -0.3c | -19.0 [-36, -3] |
| NFL | Pinnacle steam | 1-3 | -11.2 | no price | +3.3c | 5-7 | -14.7 | no price | +0.3c | too few |
| NFL | Handle split | 5-15 | -13.9 | no price | +3.3c | 5-6 | -0.1 | no price | -1.5c | -13.8 [-54, 22] |
| NFL | Book behind Pinnacle | 2-7-1 | -31.5 | -51.3% [-100, -2] (n 10) | +4.4c | 3-1 | +21.8 | +48.1% (n 4) | +4.5c | too few |
| CFB | Proven sharp accounts | 15-20 | -3.8 | -4.0% [-44, 38] (n 35) | +0.3c | 11-10-1 | -0.4 | -2.1% [-41, 35] (n 22) | +0.5c | -3.5 [-30, 24] |
| CFB | Big exchange tickets | 147-163-3 | -2.0 | -4.9% [-19, 10] (n 313) | +0.1c | 208-133-1 | +4.3 | +10.5% [-1, 22] (n 342) | -0.0c | -6.4 [-15, 2] |
| CFB | Pinnacle steam | 17-22-1 | -5.8 | no price | -1.0c | 50-36-2 | +5.6 | no price | -2.2c | -11.4 [-31, 8] |
| CFB | Handle split | 49-74-2 | +3.1 | no price | +0.7c | 53-61-2 | +4.2 | no price | +1.0c | -1.1 [-14, 13] |
| CFB | Book behind Pinnacle | 75-62-1 | -0.1 | +4.1% [-11, 19] (n 138) | -0.4c | 58-38-1 | +5.5 | +14.9% [-4, 34] (n 97) | +0.8c | -5.6 [-19, 8] |
| NBA | Proven sharp accounts | 29-40-1 | -7.0 | -12.3% [-41, 16] (n 70) | +0.9c | 38-24-1 | +3.8 | +10.7% [-15, 35] (n 63) | -0.4c | -10.9 [-30, 8] |
| NBA | Big exchange tickets | 82-104-2 | -2.6 | -12.7% [-29, 4] (n 188) | +0.6c | 128-68-1 | +6.8 | +13.5% [-0, 28] (n 197) | -0.3c | -9.4 [-20, 2] |
| NBA | Pinnacle steam | 11-23-1 | -16.3 | no price | +0.8c | 24-26 | -2.4 | no price | -0.8c | -13.9 [-36, 10] |
| NBA | Handle split | 11-24 | -8.3 | no price | +1.3c | 7-14 | -9.9 | no price | -0.9c | +1.6 [-21, 25] |
| NBA | Book behind Pinnacle | 38-33 | -1.4 | +1.8% [-20, 23] (n 71) | +2.8c | 27-19 | +3.9 | +12.1% [-13, 37] (n 46) | +0.0c | -5.3 [-23, 12] |

For reference, every alert in each family, whether or not the model had a view:

| Sport | Family | All W-L | vs fair | ROI [CI] | CLV |
|---|---|---|---|---|---|
| NFL | Proven sharp accounts | 110-126-3 | -3.6 | -2.2% [-10, 6] (n 239) | +0.2c |
| NFL | Sharp net vs crowd | 17-18 | -7.2 | -15.6% [-42, 10] (n 35) | +0.3c |
| NFL | Big exchange tickets | 204-195-3 | +0.9 | +2.7% [-3, 9] (n 402) | +0.2c |
| NFL | Pinnacle steam | 7-16-1 | -20.3 | no price | +1.2c |
| NFL | Handle split | 30-37-1 | +2.0 | no price | +0.8c |
| NFL | Book behind Pinnacle | 18-23-1 | -7.5 | -6.5% [-41, 30] (n 42) | +3.6c |
| CFB | Proven sharp accounts | 199-204-5 | -1.9 | -1.6% [-9, 6] (n 408) | +0.0c |
| CFB | Sharp net vs crowd | 28-22 | +2.2 | -2.8% [-29, 23] (n 50) | +0.6c |
| CFB | Big exchange tickets | 545-471-6 | +0.1 | +1.8% [-2, 6] (n 1022) | +0.1c |
| CFB | Pinnacle steam | 99-95-3 | -0.3 | no price | -1.2c |
| CFB | Handle split | 165-238-5 | +2.5 | no price | +0.6c |
| CFB | Book behind Pinnacle | 250-209-4 | +0.3 | +5.3% [-2, 13] (n 463) | +0.8c |
| NBA | Proven sharp accounts | 141-139-4 | -2.1 | -1.0% [-9, 7] (n 284) | +0.3c |
| NBA | Sharp net vs crowd | 23-17 | +2.9 | +7.5% [-20, 37] (n 40) | +0.5c |
| NBA | Big exchange tickets | 271-226-5 | +1.7 | +0.5% [-4, 5] (n 502) | +0.2c |
| NBA | Pinnacle steam | 43-56-2 | -6.4 | no price | -0.3c |
| NBA | Handle split | 52-81 | -6.1 | no price | +0.6c |
| NBA | Book behind Pinnacle | 104-79 | +1.7 | +7.7% [-4, 20] (n 183) | +1.6c |

## 3. Does the model do better when sharp money agrees? (model lens)

The model's side on every live game it logged, split by whether each family backed the model's team (spread or moneyline), the other team, or both before kickoff. "Net $" uses the side with more logged money. The open-to-last line move uses the feed's open (ESPN), not Pinnacle's, and is tied to CLV by construction.

**NFL, ATS at the last pre-kick line** (all games: 22-35, CLV +0.15 pts). No price stored, so no ROI.

| Family | Backs model's team | Backs other team | Agree W-L (win%) | CLV | Disagree W-L (win%) | CLV | Both sides | Agree minus disagree win% [CI] |
|---|---|---|---|---|---|---|---|---|
| Proven sharp accounts | 6 | 9 | 3-3 (50%) | -0.17 pts | 4-5 (44%) | +0.11 pts | 10 | +5.6 [-44, 50] (win%) |
| Sharp net vs crowd | 8 | 1 | 3-5 (38%) | -0.06 pts | 0-1 (0%) | +0.00 pts | 0 | too few |
| Pinnacle steam | 5 | 8 | 1-4 (20%) | +0.70 pts | 5-3 (62%) | -0.12 pts | 0 | -42.5 [-88, 10] (win%) |
| Handle split | 14 | 10 | 4-10 (29%) | +0.46 pts | 3-7 (30%) | -0.10 pts | 4 | -1.4 [-39, 33] (win%) |
| Book behind Pinnacle | 6 | 11 | 1-5 (17%) | +0.58 pts | 5-6 (46%) | +0.09 pts | 1 | -28.8 [-65, 15] (win%) |
| Proven sharps, net $ | 13 | 12 | 4-9 (31%) | -0.08 pts | 7-5 (58%) | +0.21 pts | 0 | -27.6 [-61, 12] (win%) |
| Big tickets, net $ | 22 | 35 | 8-14 (36%) | +0.16 pts | 14-21 (40%) | +0.14 pts | 0 | -3.6 [-30, 22] (win%) |
| Line move, open to last pre-kick | 18 | 35 | 5-13 (28%) | -0.06 pts | 14-21 (40%) | +0.27 pts | 0 | -12.2 [-38, 13] (win%) |

**CFB, ATS at the last pre-kick line** (all games: 98-117-6, CLV +0.07 pts). No price stored, so no ROI.

| Family | Backs model's team | Backs other team | Agree W-L (win%) | CLV | Disagree W-L (win%) | CLV | Both sides | Agree minus disagree win% [CI] |
|---|---|---|---|---|---|---|---|---|
| Proven sharp accounts | 18 | 16 | 5-12-1 (29%) | +0.00 pts | 8-6-2 (57%) | -0.23 pts | 4 | -27.7 [-60, 7] (win%) |
| Sharp net vs crowd | 5 | 6 | 1-4 (20%) | +0.10 pts | 4-2 (67%) | -0.10 pts | 0 | -46.7 [-83, 7] (win%) |
| Pinnacle steam | 21 | 34 | 9-10-2 (47%) | +0.17 pts | 16-18 (47%) | -0.16 pts | 12 | +0.3 [-27, 29] (win%) |
| Handle split | 77 | 65 | 31-44-2 (41%) | +0.12 pts | 30-33-2 (48%) | -0.03 pts | 30 | -6.3 [-24, 11] (win%) |
| Book behind Pinnacle | 49 | 38 | 27-19-3 (59%) | -0.12 pts | 13-25 (34%) | -0.14 pts | 28 | +24.5 [4, 45] (win%) |
| Proven sharps, net $ | 19 | 19 | 6-12-1 (33%) | -0.05 pts | 10-7-2 (59%) | -0.19 pts | 0 | -25.5 [-55, 8] (win%) |
| Big tickets, net $ | 89 | 120 | 40-47-2 (46%) | +0.07 pts | 51-65-4 (44%) | +0.01 pts | 0 | +2.0 [-12, 17] (win%) |
| Line move, open to last pre-kick | 84 | 114 | 42-40-2 (51%) | +0.02 pts | 45-66-3 (40%) | +0.14 pts | 0 | +10.7 [-4, 26] (win%) |

**CFB totals, graded at the stored open** (all games: 94-121-3).

| Family | Agree W-L | Disagree W-L | Agree minus disagree [CI] |
|---|---|---|---|
| Proven sharp accounts | 5-5 | 1-2 | too few |
| Sharp net vs crowd | - | - | too few |
| Big exchange tickets | 18-14-1 | 15-19 | +12.1 [-12, 36] (win%) |
| Pinnacle steam | 6-1 | 2-5-1 | +57.1 [14, 100] (win%) |
| Handle split | 13-15 | 7-23 | +23.1 [-1, 47] (win%) |
| Book behind Pinnacle | 17-22-1 | 22-28-1 | -0.4 [-22, 20] (win%) |

**NBA, ATS at the first-sighting price** (all games: 62-79, ROI -15.9%, interval -32% to 0%).

| Family | Agree W-L | ROI [CI] | Disagree W-L | ROI [CI] | No signal W-L | ROI | Agree minus disagree ROI [CI] |
|---|---|---|---|---|---|---|---|
| Proven sharp accounts | 1-6 | -72.7% [-100, -18] (n 7) | 7-9 | -17.1% [-65, 30] (n 16) | 41-49 | -12.9% [-32, 7] (n 90) | -55.6 [-118, 19] (ROI) |
| Sharp net vs crowd | 3-5 | -27.9% [-100, 43] (n 8) | 4-8 | -36.1% [-84, 13] (n 12) | 53-65 | -14.1% [-31, 3] (n 118) | +8.1 [-72, 88] (ROI) |
| Pinnacle steam | 4-4 | -3.4% [-75, 68] (n 8) | 8-6 | +8.6% [-45, 51] (n 14) | 49-65 | -17.8% [-35, -1] (n 114) | -12.1 [-95, 73] (ROI) |
| Handle split | 16-28 | -30.5% [-57, -4] (n 44) | 8-11 | -19.0% [-60, 22] (n 19) | 36-40 | -9.5% [-32, 11] (n 76) | -11.5 [-65, 40] (ROI) |
| Book behind Pinnacle | 8-13 | -27.0% [-64, 18] (n 21) | 6-14 | -43.2% [-81, -5] (n 20) | 40-44 | -8.9% [-30, 12] (n 84) | +16.2 [-40, 64] (ROI) |
| Proven sharps, net $ | 6-11 | -31.8% [-77, 14] (n 17) | 15-19 | -16.0% [-49, 17] (n 34) | 41-49 | -12.9% [-32, 7] (n 90) | -15.7 [-67, 40] (ROI) |
| Big tickets, net $ | 27-34 | -15.0% [-38, 8] (n 61) | 33-44 | -18.4% [-40, 2] (n 77) | 2-1 | +30.5% (n 3) | +3.4 [-27, 35] (ROI) |

**NBA, winner at the first-sighting price** (all games: 97-45, ROI -4.1%, interval -16% to +8%). Win rates here are high because the model's winner is usually the favorite; read the ROI column.

| Family | Agree W-L | ROI [CI] | Disagree W-L | ROI [CI] | No signal W-L | ROI | Agree minus disagree ROI [CI] |
|---|---|---|---|---|---|---|---|
| Proven sharp accounts | 12-3 | +5.7% [-24, 30] (n 15) | 5-3 | -20.9% [-66, 18] (n 8) | 62-29 | -4.8% [-18, 9] (n 91) | +26.5 [-24, 77] (ROI) |
| Sharp net vs crowd | 10-4 | +5.0% [-32, 38] (n 14) | 1-5 | -82.2% [-100, -47] (n 6) | 85-34 | -0.8% [-13, 11] (n 119) | +87.2 [35, 134] (ROI) |
| Pinnacle steam | 9-4 | -8.0% [-44, 28] (n 13) | 8-1 | +21.6% [-13, 46] (n 9) | 77-38 | -5.7% [-18, 7] (n 115) | -29.6 [-73, 17] (ROI) |
| Handle split | 2-5 | -57.2% [-100, 2] (n 7) | 42-14 | +2.5% [-13, 18] (n 56) | 51-26 | -5.0% [-21, 11] (n 77) | -59.6 [-108, -1] (ROI) |
| Book behind Pinnacle | 14-8 | -4.9% [-40, 27] (n 22) | 11-9 | -23.6% [-53, 9] (n 20) | 60-24 | +0.2% [-15, 14] (n 84) | +18.7 [-28, 63] (ROI) |
| Proven sharps, net $ | 25-9 | +4.0% [-18, 27] (n 34) | 10-7 | -16.1% [-52, 18] (n 17) | 62-29 | -4.8% [-19, 8] (n 91) | +20.1 [-22, 62] (ROI) |
| Big tickets, net $ | 72-28 | -0.9% [-14, 11] (n 100) | 23-16 | -13.1% [-38, 12] (n 39) | 2-1 | +8.4% (n 3) | +12.2 [-17, 38] (ROI) |

## 4. Top Reads with the model's stamped side

Graded bet reads (line, money, behind) on one side only, with the model side stamped before kickoff.

| Sport | Graded reads | Model stamped before kickoff | Model agrees | Agree W-L | vs fair | ROI [CI] | CLV | Disagree W-L | vs fair | ROI [CI] | CLV | Diff [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NFL | 129 | 53 | 34% [23, 47] | 8-9-1 | -10.5 | -14.9% [-51, 25] (n 14) | +1.9c | 16-19 | +3.3 | -22.8% [-67, 26] (n 27) | +1.4c | -13.8 [-42, 14] |
| CFB | 412 | 281 | 31% [26, 37] | 47-40-1 | +4.1 | +16.5% [-12, 44] (n 66) | +1.1c | 94-99 | +9.3 | +21.9% [-2, 46] (n 162) | +1.0c | -5.2 [-20, 10] |
| NBA | 313 | 181 | 48% [41, 55] | 50-35-2 | +2.7 | +2.7% [-18, 25] (n 87) | +1.1c | 44-49-1 | +5.9 | +4.3% [-22, 31] (n 94) | +0.9c | -3.2 [-19, 14] |

## Flagged for close monitoring (not promoted, same data cannot confirm them)

Records that look better, with sample sizes. Each one was found by slicing this data, so each needs a fresh forward sample before anyone treats it as real.

1. **Big exchange tickets that disagree with the model.** NBA 128-68-1, +6.8 vs fair, ROI +13.5% (interval about 0% to +28%), 197 priced. CFB 208-133-1, +4.3 vs fair, ROI +10.5% (interval -1% to +22%), 342 priced. NFL 60-39, +10.0 vs fair, ROI +19.4% (interval -5% to +44%), 99 priced. Same direction in all three sports, none clear of zero on ROI, and CLV is flat (about 0c), which argues against a real edge.
2. **Book behind Pinnacle when the model disagrees.** CFB 58-38-1, ROI +14.9% (97 priced); NBA 27-19, ROI +12.1% (46 priced). Intervals include zero.
3. **CFB model ATS when a book-behind-Pinnacle alert backs the model's team**: 27-19-3 against 13-25 when it backs the other team, gap +24.5 points (interval +4 to +45). 49 and 38 games.
4. **CFB totals when Pinnacle steam agrees with the model**: 6-1 against 2-5-1 (7 and 8 games). Far too small.
5. **NBA winner pick when a sharp-account net-position alert (cross) backs it**: 10-4 against 1-5 (14 and 6 games). Far too small.

One slice went clearly the other way and is worth knowing about: **NBA winner picks against a handle split** (money share above ticket share on the other team) went 2-5, ROI -57.2%, on 7 games.

## What would change the answer

- More live model history. The models only log point-in-time output from mid-October, so the long sharp-wallet history on `sharp-history` (`pm_ledger`, back to 2024) cannot be lined up with a pre-game model number. A daily frozen copy of each model's slate is all it would take going forward.
- The proven-sharps side cards: re-run once the forward test in `docs/sharp-card-prereg.md` has graded plays (dozens, not 1).
- Storing a price on NFL/CFB board rows and on steam and split alerts, so those cells can show ROI instead of win rate only.
- Logging the line *before* a steam move on steam alerts, so model agreement can be measured on the pre-move number and the arithmetic effect described above goes away.

## Prior work this builds on

- `docs/signal-research.md` (2026-10-13): sharp alerts do not beat the logged fair price in any held-out role. Unchanged here: every family's full record sits within a few points of fair.
- `scripts/backtest_signal_model_agree.py` (Top Reads by model agreement): this study adds the before-kickoff check on the model stamp, which drops 32% (CFB) to 59% (NFL) of the graded reads.
- `data/nfl_model.json` `cards_summary` (the NFL Model page's Sharp Money cards table): that table includes the backfilled weeks 1 to 5; this one does not.

No tracking changed, so no record was recomputed.
