# Matchup volume test, Stage 1: corrected results

Rules: [matchup-volume-test.md](matchup-volume-test.md), unchanged. Run 1 (`matchup-volume-results.md`) is **invalid**: its league mean counted the All-Star game's invented teams as defenses (37 teams instead of 30), which put a drifting offset of about +0.10 on every index.
This corrected run uses real teams only (20 or more games, the page's own cut). It was run **after seeing run 1**, with the same definitions, slope-fit rule and pass conditions; nothing else changed. Numbers: `nba/data/matchup_volume_corrected.json`. Nothing here changes what the page prices or bets by itself.

## Verdict: **PASS for 3PM and for AST** (all six conditions, each stat judged alone)

| | 3PM (volume = 3-point attempts) | AST (volume = assists) |
|---|---|---|
| Rows scored, 2024-25 fit / 2025-26 test | 16,873 / 22,319 | 15,110 / 22,534 |
| Slope fitted on 2024-25 (frozen) | **+0.881** | **+0.778** |
| Slope estimated on 2025-26 alone | +0.708 (t 10.46) | +0.763 (t 9.12) |
| Frozen slope on 2025-26: volume MAE gain | **+0.0060 (t 3.59)** | **+0.0042 (t 3.88)** |
| Stat MAE gain (3PM / AST) | +0.0026 (t 4.47) | +0.0042 (t 3.88) |
| Random-defense control | -0.0079 (t -5.20) | -0.0030 (t -3.00) |
| Halves of 2025-26 (volume gain) | +0.0028, +0.0090 | +0.0035, +0.0048 |

| Condition | 3PM | AST |
|---|---|---|
| Slope fitted on 2024-25 positive | yes | yes |
| Volume gain with the frozen slope, t >= 2.5 | yes (3.59) | yes (3.88) |
| Control not at t >= 2.5 | yes (-5.20) | yes (-3.00) |
| 2025-26 own slope positive, t >= 2.5 | yes (10.46) | yes (9.12) |
| Both halves positive | yes | yes |
| Stat MAE not worse | yes | yes |

## What changed from run 1

- The index is now centred on zero (fifth means -0.084, -0.032, -0.005, +0.028, +0.090 for 3PM) instead of sitting at +0.10.
- The slope fitted on 2024-25 and the slope estimated on 2025-26 now **agree** (3PM 0.88 against 0.71, AST 0.78 against 0.76); in run 1 they differed by 7x and 2x. The disagreement was the offset.
- The dose response is still there, smaller: volume missed by the model, by index fifth, **3PA -5.1%, -0.4%, +3.2%, +5.0%, +8.8%; assists -3.2%, +0.6%, +7.1%, +8.6%, +10.3%**.

## What it does and does not say

- It says the shot-diet matchup carries information about 3-point attempts and assists that v2 misses, with a slope fitted on a different season, a control that fails, and both halves positive.
- **The gains are small in MAE terms** (0.006 attempts, 0.004 assists per player-game) because most players' index is near zero; the effect is concentrated in the ends. At these slopes a one-in-twenty extreme pair moves a 3PM projection by about 7% and an assist projection by about 6%.
- **The player-specific mix adds nothing measurable over the opponent's overall allowance.** The opponent-only context index scored the same (3PM volume t 3.56 against 3.59; AST 4.12 against 3.88). What the data supports is "this defense gives up more 3-point attempts and assists", not "this defense gives up more of exactly the shots this player takes".
- Not a price result. Whether it beats prices is Stage 2 and the forward 2026-27 read (`matchup-live.md`).
