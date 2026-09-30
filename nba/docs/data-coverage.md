# NBA data coverage

Generated 2026-09-29 by `nba/scripts/build_backtest_tables.py`. Free sources only.

Games = completed regular season, NBA Cup final, play-in and playoffs.

| Month | Games | ESPN lines (open+close) | ESPN prop games | ESPN props (O/U pairs) | pairs w/ pre-tip close | Kalshi prop games | Kalshi strikes | Injury report days |
|---|---|---|---|---|---|---|---|---|
| 2024-10 | 67 | 67 | 0 | 0 | 0 | 0 | 0 | 10 |
| 2024-11 | 222 | 221 | 0 | 0 | 0 | 0 | 0 | 28 |
| 2024-12 | 192 | 192 | 91 | 3,962 | 0 | 0 | 0 | 29 |
| 2025-01 | 224 | 224 | 224 | 10,714 | 0 | 0 | 0 | 31 |
| 2025-02 | 173 | 173 | 173 | 13,568 | 0 | 0 | 0 | 23 |
| 2025-03 | 245 | 245 | 245 | 24,827 | 0 | 0 | 0 | 31 |
| 2025-04 | 151 | 151 | 146 | 14,189 | 0 | 0 | 0 | 27 |
| 2025-05 | 39 | 39 | 39 | 3,753 | 0 | 0 | 0 | 28 |
| 2025-06 | 8 | 8 | 8 | 819 | 0 | 0 | 0 | 7 |
| 2025-10 | 75 | 74 | 75 | 4,755 | 437 | 0 | 0 | 11 |
| 2025-11 | 221 | 221 | 221 | 10,973 | 720 | 82 | 2,600 | 29 |
| 2025-12 | 196 | 196 | 3 | 129 | 10 | 193 | 6,678 | 30 |
| 2026-01 | 233 | 233 | 11 | 918 | 722 | 226 | 11,177 | 31 |
| 2026-02 | 168 | 168 | 0 | 0 | 0 | 159 | 10,127 | 22 |
| 2026-03 | 237 | 237 | 2 | 2 | 1 | 236 | 18,777 | 31 |
| 2026-04 | 147 | 147 | 42 | 5,217 | 1,898 | 146 | 12,643 | 27 |
| 2026-05 | 40 | 40 | 36 | 4,968 | 2,704 | 40 | 5,136 | 26 |
| 2026-06 | 5 | 5 | 5 | 796 | 624 | 5 | 943 | 5 |

## ESPN prop over/under sides

ESPN does not label which prop row is the over. Sides come from the alt-line ladder (ESPN BET) or
row order (DraftKings), then are checked against results: where the book clearly leaned (>58% de-vigged),
its favourite should win well over half the time. A swapped assignment would show well under half.

| Book / method | Fav won | Fav lost | Rate |
|---|---|---|---|
| 58/ladder | 18,191 | 8,027 | 0.694 |
| 100/dk-order | 1,377 | 765 | 0.643 |

## Kalshi player names not matched to a box score

Kalshi settles a market as `scalar` (voided, stake refunded) when the player does not play. On 2025-26,
1,489 of 1,520 unmatched strikes were `scalar`: the player never took the floor, so there is no box score
row to match, and that is correct. Only 31 real misses. Backtests must drop `result == scalar` rows.

1,520 strikes unmatched. Top: Aaron Gordon (89), Anthony Edwards (57), James Harden (54), Victor Wembanyama (53), LeBron James (44), Kawhi Leonard (41), Chet Holmgren (39), Joel Embiid (37), Franz Wagner (36), Jalen Johnson (36), Donovan Mitchell (36), Lauri Markkanen (35)
