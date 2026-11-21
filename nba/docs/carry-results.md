# Game model: roster-continuity carry, results

Generated 2026-11-19T19:12Z by `nba/scripts/test_carry.py`. Rules, committed before this ran: [carry-prereg.md](carry-prereg.md). Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.

Chosen on the first 28 days of 2022-23 and 2023-24: a = 0.4, b = 1.0. Tune margin MAE (first 28 days, who actually sat): S: 10.245, a=0.4|b=0.0: 10.2545, a=0.4|b=0.3: 10.2381, a=0.4|b=0.6: 10.2252, a=0.4|b=1.0: 10.2194, a=0.5|b=0.0: 10.245, a=0.5|b=0.3: 10.241, a=0.5|b=0.6: 10.238, a=0.5|b=1.0: 10.2378, a=0.6|b=0.0: 10.2661, a=0.6|b=0.3: 10.2624, a=0.6|b=0.6: 10.2663, a=0.6|b=1.0: 10.2813.

## CC (margin MAE, points)

| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |
|---|---|---|---|---|---|---|---|
| first28 | 2025 | 211 | 9.669 | 9.598 | -0.071 | 0.054 | -1.3 |
| first28 | 2026 | 207 | 10.638 | 10.667 | 0.029 | 0.053 | 0.55 |
| first28 | pooled | 418 | 10.149 | 10.128 | -0.021 | 0.036 | -0.59 |
| whole | 2025 | 1321 | 10.912 | 10.908 | -0.004 | 0.012 | -0.33 |
| whole | 2026 | 1322 | 11.288 | 11.299 | 0.011 | 0.011 | 0.98 |
| whole | pooled | 2643 | 11.1 | 11.104 | 0.003 | 0.008 | 0.43 |

Continuity by season (teams, min / median / max): {'2025': {'n': 30, 'min': 0.329, 'median': 0.659, 'max': 0.903}, '2026': {'n': 30, 'min': 0.368, 'median': 0.57, 'max': 0.867}}.
Against the close: {'variant': {'model': 11.104, 'close': 10.824, 'n': 2641}, 'shipped': {'model': 11.101, 'close': 10.824, 'n': 2641}}. Information test vs the close: variant {'n': 2641, 'b_market': 1.068, 'g_model_gap': 0.13, 'g_se': 0.095, 't': 1.37}; shipped {'n': 2641, 'b_market': 1.067, 'g_model_gap': 0.118, 'g_se': 0.096, 't': 1.23}.

## Verdict, by the registered rules

| Rule | Result | Met |
|---|---|---|
| 1. Pooled first-28-days t of -2 or less | -0.59 (10.149 to 10.128) | no |
| 2. Negative in each test season | 2024-25 -0.071, 2025-26 +0.029 | no |
| 3. Not worse over the whole season at t +2 | +0.43 (11.100 to 11.104) | yes |
| 4. Information test within 1 t of shipped | 1.37 vs 1.23 | yes |

**NO-GO.** Nothing ships; `game_model.json`, the Slate and the Game Picks record are unchanged.

## Reading it

- **No usable gain.** The first four weeks improve by 0.021 points over 418 games with an SE of 0.036; one test season is better and the other worse. The whole season is flat.
- **The tuner went to the corner of the grid** (a 0.4, b 1.0: carry lower overall, with continuity doing most of the work), which means the tune surface was still sloping. The tune gain was 0.026 points (10.245 to 10.219), not significant either, and it did not carry to 2025-26.
- **Sanity check passes.** The cell a 0.5, b 0 reproduces the shipped model exactly (10.245).
- **Continuity does vary across teams** (30 teams a season: 0.33 to 0.90 in 2024-25, 0.37 to 0.87 in 2025-26, medians 0.66 and 0.57), so the lever had room to work. The data say that knowing who stayed adds little beyond last season's rating plus the model's usual updates.
- **Limits.** Continuity is only known after a team's third game, so games 1 to 3 use the shipped carry; the correction is an additive approximation; only the margin rating is touched. A preseason roster (from depth charts, not on disk for past seasons) would remove the three-game delay and was not tested.
- **Together with the earlier early-season K test (PR 505):** the first four weeks are the model's weak spot, but neither a faster step nor a roster-aware carry fixes it in a way the test seasons confirm.
