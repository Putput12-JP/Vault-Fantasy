# Do players who keep hitting a line keep hitting it?

Generated 2026-10-01T05:52Z by `nba/scripts/build_hit_rates.py`. Every line priced before tip; the player's record
against that same line from games before it only. Rule fixed first: bet OVER at 8+ of last 10, UNDER at 2 or fewer;
GO = test-set ROI > 0 with z >= 2 over 50+ games.

## Sportsbook 2024-25, opening line (exploration set)

40,332 lines.

| Last 10 vs this line | Lines | Streak said | Market said | Actually hit |
|---|---|---|---|---|
| 0-2 of 10 | 4,215 | 16% | 49.2% | 45.3% |
| 3-4 of 10 | 13,237 | 36% | 50.1% | 46.8% |
| 5-6 of 10 | 16,492 | 55% | 51.2% | 48.3% |
| 7-8 of 10 | 5,854 | 73% | 52.2% | 51.0% |
| 9-10 of 10 | 496 | 91% | 53.3% | 49.8% |

Does the streak add to the price? outcome - price = a + b x (L10 rate - price): b = 0.032 (t = 2.24), n = 40,294. Average outcome - price -0.029.

| Bet | Bets | Games | ROI | z |
|---|---|---|---|---|
| L5 over (hit 4+ of 5) | 6,658 | 888 | -10.4% | -7.25 |
| L5 under (hit 1 or fewer of 5) | 8,660 | 903 | -1.4% | -0.93 |
| L10 over (hit 8+ of 10) | 2,159 | 632 | -7.3% | -2.96 |
| L10 under (hit 2 or fewer of 10) | 4,215 | 784 | +0.8% | 0.42 |
| L20 over (hit 16+ of 20) | 781 | 349 | -2.8% | -0.69 |
| L20 under (hit 4 or fewer of 20) | 2,775 | 580 | -0.5% | -0.19 |
| Season over (80%+, 10+ games) | 394 | 203 | -8.0% | -1.42 |
| Season under (20% or less, 10+ games) | 2,650 | 531 | -0.1% | -0.03 |
| L10 over, 15+ pts above price | 6,022 | 840 | -9.6% | -6.25 |
| L10 under, 15+ pts below price | 9,502 | 898 | +0.6% | 0.47 |
| Baseline: every over | 40,332 | 926 | -11.9% | -16.09 |
| Baseline: every under | 40,332 | 926 | -1.2% | -1.69 |

At the same price: 2-or-fewer unders return +1.2% more than other unders (4,215 bets); 8+ of 10 overs +3.5% vs other overs (2,159 bets).

Consistent players (147 player-stats with 15+ lines in each half): first-half vs second-half beat-the-price correlation 0.031. Top fifth: +0.150 then -0.007; bottom fifth: -0.189 then -0.040. Betting the top fifth's overs in the second half: ROI -8.6% (z -1.81); the bottom fifth's unders: +0.0% (z 0.01).

## Sportsbook 2025-26, pre-tip close (test)

4,951 lines.

| Last 10 vs this line | Lines | Streak said | Market said | Actually hit |
|---|---|---|---|---|
| 0-2 of 10 | 315 | 17% | 46.9% | 43.2% |
| 3-4 of 10 | 1,528 | 36% | 48.6% | 45.3% |
| 5-6 of 10 | 2,126 | 55% | 49.8% | 48.9% |
| 7-8 of 10 | 904 | 73% | 51.4% | 46.2% |
| 9-10 of 10 | 69 | 91% | 52.4% | 53.6% |

Does the streak add to the price? outcome - price = a + b x (L10 rate - price): b = 0.0143 (t = 0.33), n = 4,942. Average outcome - price -0.026.

| Bet | Bets | Games | ROI | z |
|---|---|---|---|---|
| L5 over (hit 4+ of 5) | 909 | 131 | -12.8% | -3.41 |
| L5 under (hit 1 or fewer of 5) | 947 | 151 | +1.3% | 0.41 |
| L10 over (hit 8+ of 10) | 332 | 96 | -15.0% | -2.81 |
| L10 under (hit 2 or fewer of 10) | 315 | 105 | +0.8% | 0.13 |
| L20 over (hit 16+ of 20) | 136 | 57 | -6.2% | -0.77 |
| L20 under (hit 4 or fewer of 20) | 114 | 64 | -8.3% | -0.88 |
| Season over (80%+, 10+ games) | 156 | 41 | -20.5% | -1.98 |
| Season under (20% or less, 10+ games) | 29 | 20 | -9.5% | -0.44 |
| L10 over, 15+ pts above price | 961 | 139 | -13.0% | -3.31 |
| L10 under, 15+ pts below price | 817 | 147 | -1.8% | -0.4 |
| Baseline: every over | 4,951 | 288 | -11.3% | -5.04 |
| Baseline: every under | 4,951 | 288 | -1.4% | -0.74 |

At the same price: 2-or-fewer unders return +2.4% more than other unders (315 bets); 8+ of 10 overs -4.1% vs other overs (332 bets).

## Sportsbook 2025-26, opening line (test)

20,630 lines.

| Last 10 vs this line | Lines | Streak said | Market said | Actually hit |
|---|---|---|---|---|
| 0-2 of 10 | 1,775 | 17% | 48.4% | 43.7% |
| 3-4 of 10 | 6,586 | 36% | 49.2% | 45.9% |
| 5-6 of 10 | 8,483 | 55% | 50.2% | 49.4% |
| 7-8 of 10 | 3,208 | 73% | 51.2% | 49.8% |
| 9-10 of 10 | 297 | 92% | 52.3% | 61.3% |

Does the streak add to the price? outcome - price = a + b x (L10 rate - price): b = 0.1037 (t = 5.06), n = 20,349. Average outcome - price -0.019.

| Bet | Bets | Games | ROI | z |
|---|---|---|---|---|
| L5 over (hit 4+ of 5) | 3,729 | 383 | -7.8% | -4.0 |
| L5 under (hit 1 or fewer of 5) | 4,061 | 391 | +2.5% | 1.21 |
| L10 over (hit 8+ of 10) | 1,235 | 286 | -2.3% | -0.67 |
| L10 under (hit 2 or fewer of 10) | 1,775 | 346 | +2.2% | 0.74 |
| L20 over (hit 16+ of 20) | 524 | 165 | +3.7% | 0.68 |
| L20 under (hit 4 or fewer of 20) | 976 | 265 | +3.5% | 0.91 |
| Season over (80%+, 10+ games) | 346 | 94 | -3.1% | -0.47 |
| Season under (20% or less, 10+ games) | 292 | 111 | -1.2% | -0.16 |
| L10 over, 15+ pts above price | 3,502 | 380 | -6.7% | -2.95 |
| L10 under, 15+ pts below price | 4,292 | 388 | +2.0% | 0.95 |
| Baseline: every over | 20,630 | 395 | -10.1% | -8.83 |
| Baseline: every under | 20,630 | 395 | -2.7% | -2.55 |

At the same price: 2-or-fewer unders return +5.2% more than other unders (1,775 bets); 8+ of 10 overs +8.0% vs other overs (1,235 bets).

## Kalshi 2025-26, 30-min pre-tip VWAP (test)

56,958 lines.

| Last 10 vs this line | Lines | Streak said | Market said | Actually hit |
|---|---|---|---|---|
| 0-2 of 10 | 19,962 | 10% | 18.1% | 15.3% |
| 3-4 of 10 | 11,839 | 35% | 39.1% | 36.4% |
| 5-6 of 10 | 11,022 | 55% | 54.7% | 51.6% |
| 7-8 of 10 | 8,784 | 75% | 70.1% | 67.0% |
| 9-10 of 10 | 5,351 | 94% | 83.3% | 82.0% |

Does the streak add to the price? outcome - price = a + b x (L10 rate - price): b = 0.0663 (t = 5.23), n = 56,958. Average outcome - price -0.028.

| Bet | Bets | Games | ROI | z |
|---|---|---|---|---|
| L5 over (hit 4+ of 5) | 13,039 | 1043 | -5.5% | -6.87 |
| L5 under (hit 1 or fewer of 5) | 23,879 | 1054 | +2.7% | 4.6 |
| L10 over (hit 8+ of 10) | 9,358 | 1013 | -3.8% | -4.68 |
| L10 under (hit 2 or fewer of 10) | 19,962 | 1043 | +2.5% | 4.83 |
| L20 over (hit 16+ of 20) | 7,516 | 980 | -2.5% | -3.11 |
| L20 under (hit 4 or fewer of 20) | 17,714 | 1039 | +2.3% | 4.48 |
| Season over (80%+, 10+ games) | 6,307 | 940 | -2.4% | -2.75 |
| Season under (20% or less, 10+ games) | 15,348 | 1030 | +2.3% | 4.55 |
| L10 over, 15+ pts above price | 6,114 | 906 | -6.4% | -2.68 |
| L10 under, 15+ pts below price | 9,175 | 1026 | +7.4% | 3.7 |
| Baseline: every over | 56,958 | 1079 | -14.5% | -13.21 |
| Baseline: every under | 56,958 | 1079 | +3.3% | 3.72 |

At the same price: 2-or-fewer unders return +3.2% more than other unders (19,923 bets); 8+ of 10 overs +3.5% vs other overs (9,339 bets).

Consistent players (322 player-stats with 15+ lines in each half): first-half vs second-half beat-the-price correlation 0.006. Top fifth: +0.104 then -0.030; bottom fifth: -0.143 then -0.034. Betting the top fifth's overs in the second half: ROI -14.4% (z -4.63); the bottom fifth's unders: +0.2% (z 0.08).

