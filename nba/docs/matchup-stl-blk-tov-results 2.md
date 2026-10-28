# Matchup test for steals, blocks and turnovers, Stage 1: results

Rules: [matchup-stl-blk-tov-test.md](matchup-stl-blk-tov-test.md) (committed and merged before the runner, `81b3e39af`). Numbers: `nba/data/matchup_stl_blk_tov.json`. Run once on 2026-10-26.
Indices from the team box scores, real teams only, every daily league-mean table asserted over exactly 30 teams (214 and 212 tables, no failure). Baseline = the extra model's walk (minutes x shrunk rate, no opponent or pace term), 28,252 player-games in 2025-26 (1,322 games), slopes fitted jointly with pace on 2024-25 and frozen. Nothing here changes what the page prices or bets.

## Verdict: **steals PASS, turnovers PASS, blocks FAIL**

| | Steals (S_tov: opponent's turnovers committed) | Blocks (B_2pa: opponent's two-point attempts) | Turnovers (T_forced: turnovers the defense forces) |
|---|---|---|---|
| Matchup slope, fitted jointly with pace on 2024-25 | +0.682 | +0.784 | +0.792 |
| Matchup slope estimated on 2025-26 alone | +0.783 (t 7.91) | +0.372 (t 2.08) | +0.752 (t 10.77) |
| **Gain over a pace-only projection** | **+0.00107 (t 3.74)** | +0.00015 (t 0.62) | **+0.0032 (t 4.61)** |
| Random-defense control over pace-only | -0.00137 (t -4.47) | -0.00060 (t -2.56) | -0.0039 (t -6.12) |
| Halves of 2025-26 | +0.00071, +0.00143 | +0.00020, +0.00010 | +0.00292, +0.00347 |
| Verdict | **PASS** | FAIL | **PASS** |

| Condition | Steals | Blocks | Turnovers |
|---|---|---|---|
| Matchup slope fitted on 2024-25 positive | yes | yes | yes |
| Incremental gain over pace, t >= 2.5 | yes (3.74) | **no (0.62)** | yes (4.61) |
| Control not at t >= 2.5 | yes | yes | yes |
| Both halves positive | yes | yes | yes |
| Own 2025-26 slope positive, t >= 2.5 | yes (7.91) | **no (2.08)** | yes (10.77) |
| League mean over exactly 30 teams | yes | yes | yes |

Context (no verdict): the matchup alone against the bare projection: steals +0.00153 (t 5.02), blocks +0.00063 (t 2.21, under 2.5, so blocks are not even "the matchup is pace"; the signal is just weak), turnovers +0.00329 (t 4.75). Pace alone against the bare projection: steals +0.00045 (t 3.43), blocks +0.00069 (t 4.36), turnovers -0.00003 (t -3.50, pace does not help turnovers and slightly hurts).
Correlation of the matchup index with the pace index: steals 0.32, blocks 0.32, turnovers 0.18.

Dose response by index fifth (actual minus projection, as a share of the projection): **steals -8.1%, +1.2%, +4.9%, +6.0%, +11.4%** (index -0.117 to +0.102); **turnovers -9.9%, -3.1%, +4.4%, +6.8%, +12.3%** (index -0.125 to +0.132); blocks -3.3%, -6.1%, +5.5%, +7.3%, +10.1% (not monotone at the low end).

## Read

- **Steals and turnovers carry real information beyond pace**: slopes near 0.7 to 0.8 in both seasons, the control fails, both halves positive, and a clean dose response. The swing from the softest to the hardest matchup is about 19% on steals and 22% on turnovers, much wider than on points, because these counts are small and teams differ a lot in turnovers.
- **Blocks do not clear the bar.** Pace explains what the matchup does there (opponent two-point attempts and pace move together), and the 2025-26 slope is weak and unsteady (0.37 against 0.78 fitted).
- **Pace belongs in the extras model for steals and blocks** on this evidence (t 3.43 and 4.36 over the bare projection) and not for turnovers. That is a separate finding and was not registered as a change.
- **No price result and no live change.** These markets are display-only: no bets, no simulations, no price history, and nothing records their projections against the box score. A pass earns the registered next step only: wiring through the extras' own path in Python and the page with a frozen slope and a kill switch, a parity check, and a **new forward record** of the extra-stat projection against results each night.
- The same 2025-26 season has been read many times; the slopes were fitted on a different season, which is the protection. Playoff games are in both the prior-season rates and the walk.
