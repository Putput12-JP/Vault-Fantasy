# Game Picks audit

Written by `nba/scripts/audit_game_picks.py`. Descriptive: nothing here is fitted. Record through 2026-11-09, 154 regular-season games (28 rebuilt, 126 live).

## 1. Is the record right?

- Finals against the hoopR box scores: **0 of 154 differ**.
- Every spread and winner pick regraded from its stored margin, line, price and final: **0 differ**.
- Picks with no stored price: **0**. Book: DraftKings. Spread prices run -120 to -102 (average break-even 52.5%).
- No pick: 1 game where the model and the line agreed exactly.
- Live picks against the recorder's tape (126 games, 0 without a tape row): first and last rows that differ from the record **0**; locked a median 3.91 hours before tip (earliest 4.00, latest 2.26; 0 outside the 4-hour window).
- Between the lock and the last look the spread moved 0.44 points on average; toward the pick 30 times, away 24. The side flipped on 11 games. Graded at the last look the record is 68-85.

## 2. Is the live model the model that was backtested?

The shipped parameters replayed over the same three seasons the live state walks, ratings only, against the margin the recorder locked. The difference is the injury and rest adjustment the recorder applied.

- Locked margin minus replay: mean +0.26, mean absolute 1.05 points.
- Margin MAE on these games: locked 11.67, ratings only 11.59, hindsight lineups 11.65, the locked line 11.08.

## 3. The spread record, cut (first look)

| Cut | Record | Win% | Units | Picks |
|---|---|---|---|---|
| All | 68-85 | 44.4% | -23.02 | 153 |
| Grade A | 12-4 | 75.0% | +6.95 | 16 |
| Grade B | 12-23 | 34.3% | -11.87 | 35 |
| Grade C | 44-58 | 43.1% | -18.10 | 102 |
| Picked the favourite | 18-25 | 41.9% | -8.29 | 43 |
| Picked the underdog | 50-60 | 45.5% | -14.73 | 110 |
| Home | 33-48 | 40.7% | -17.76 | 81 |
| Away | 35-37 | 48.6% | -5.26 | 72 |
| Injury and rest adjustment 0 to 0.5 pts | 38-40 | 48.7% | -5.64 | 78 |
| Injury and rest adjustment 0.5 to 1.5 pts | 17-17 | 50.0% | -1.34 | 34 |
| Injury and rest adjustment 1.5 to 3 pts | 10-16 | 38.5% | -6.74 | 26 |
| Injury and rest adjustment 3 to up pts | 3-12 | 20.0% | -9.30 | 15 |
| Week 1 (10-20 to 10-26) | 25-27 | 48.1% | -4.24 | 52 |
| Week 2 (10-27 to 11-02) | 17-38 | 30.9% | -22.53 | 55 |
| Week 3 (11-04 to 11-09) | 26-20 | 56.5% | +3.75 | 46 |

Against a 50.8% history (below), 68 wins or fewer in 153 happens 7% of the time.

## 4. The winner record, cut

| Cut | Record | Win% | Units | Picks | Model said | Price implied (with vig) |
|---|---|---|---|---|---|---|
| All | 100-53 | 65.4% | -10.76 | 153 | 65.0% | 68.1% |
| Grade A (70%+) | 41-5 | 89.1% | +4.72 | 46 | 76.7% | 80.5% |
| Grade B (60 to 70%) | 31-17 | 64.6% | -3.73 | 48 | 65.0% | 69.0% |
| Grade C (under 60%) | 28-31 | 47.5% | -11.75 | 59 | 55.8% | 57.7% |
| Model agrees with the market favourite | 95-41 | 69.9% | -4.38 | 136 | 66.2% | 70.8% |
| Model disagrees with it | 5-12 | 29.4% | -6.37 | 17 | 55.3% | 46.1% |

The market's favourite won 107 of 153 on the same games.

## 5. Where the model and the line disagree: the same teams every night

Model minus market, per game, from the team's side (positive: the model rates the team higher than the line does), the team's average result against the spread, and the record of the picks that took that team.

| Team | Games | Model minus market | Result vs spread | Picked |
|---|---|---|---|---|
| LAC | 9 | +5.46 | +0.39 | 5-4 |
| CHA | 11 | +4.08 | -9.14 | 4-6 |
| MIL | 10 | +3.49 | -5.60 | 3-7 |
| SAC | 10 | +3.13 | -3.20 | 3-5 |
| NO | 11 | +2.14 | -1.86 | 6-3 |
| DAL | 10 | +2.14 | +8.30 | 5-4 |
| MIA | 10 | -2.94 | -8.10 | 0-1 |
| PHI | 11 | -2.68 | +0.23 | 0-0 |
| BOS | 10 | -2.52 | +2.40 | 0-2 |
| SA | 11 | -2.11 | +0.59 | 0-2 |
| HOU | 11 | -2.10 | +4.41 | 1-0 |
| TOR | 10 | -1.88 | +0.10 | 0-3 |

Across all 30 teams the two columns correlate -0.21: where they disagreed, the line was closer.
Spread of the margins on these games (sd): model 5.97, line 7.21, finals 16.85.

## 6. The same cuts on the two test seasons (2,641 games, against the closing spread)

| Cut | Record | Win% | Picks | 2024-25 | 2025-26 |
|---|---|---|---|---|---|
| All | 1342-1299 | 50.8% | 2641 | 52.0% | 49.7% |
| Grade A (gap 5+) | 132-147 | 47.3% | 279 | 45.2% | 49.3% |
| Grade B (3 to 5) | 290-251 | 53.6% | 541 | 57.3% | 49.8% |
| Grade C (under 3) | 920-901 | 50.5% | 1821 | 51.4% | 49.7% |
| Picked the favourite | 424-412 | 50.7% | 836 | 53.3% | 48.2% |
| Picked the underdog | 918-887 | 50.9% | 1805 | 51.4% | 50.3% |
| Injury adjustment 0 to 0.5 pts | 509-533 | 48.8% | 1042 | 48.9% | 48.8% |
| Injury adjustment 0.5 to 1.5 pts | 337-277 | 54.9% | 614 | 59.6% | 50.9% |
| Injury adjustment 1.5 to 3 pts | 270-272 | 49.8% | 542 | 50.7% | 48.9% |
| Injury adjustment 3 to up pts | 226-217 | 51.0% | 443 | 51.8% | 50.4% |
| First 3 weeks of the season | 161-149 | 51.9% | 310 | 54.8% | 49.0% |

Grade A this season is 12-4. Its history is the Grade A row above. No cut in this table is above break-even (52.4%) in both seasons.

