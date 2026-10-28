# Matchup volume test, Stage 1: results

> **SUPERSEDED, run 1 was invalid.** The league mean in this run included the All-Star game's invented teams (see "Correction" at the end and `matchup-volume-corrected-results.md`). Numbers below are kept as the record of that run and must not be quoted.

Rules: [matchup-volume-test.md](matchup-volume-test.md), committed before the runner (`d01f34aac`, clarifications `7fc4a3d64`). Numbers: `nba/data/matchup_volume.json`. Run once on 2026-10-25. Nothing here changes what the page prices or bets.

## Verdict: **FAIL on the registered rule for both stats, but the matchup signal is real in 2025-26**

The registered test froze a slope fitted on 2024-25 and applied it to 2025-26. That slope does not transfer, so applying it makes the projection worse. The signal itself is clearly there when 2025-26 is looked at on its own.

| | 3PM (volume = 3-point attempts) | AST (volume = assists) |
|---|---|---|
| Rows scored, 2024-25 fit / 2025-26 test | 15,999 / 22,319 | 14,274 / 19,774 |
| Slope fitted on 2024-25 (frozen) | **+0.885** | **+0.752** |
| Slope estimated on 2025-26 alone | **+0.119** (t 3.50) | **+0.364** (t 6.88) |
| Frozen slope applied to 2025-26: volume MAE gain | -0.046 (t -15.4) | -0.014 (t -7.9) |
| Same slope on the random-defense control | -0.088 (t -20.7) | -0.025 (t -11.9) |
| Both halves positive | no | no |

| Condition | 3PM | AST |
|---|---|---|
| Slope fitted on 2024-25 positive | yes | yes |
| Volume gain with the frozen slope, t >= 2.5 | **no** | **no** |
| Control not at t >= 2.5 | yes | yes |
| 2025-26 own slope positive, t >= 2.5 | yes | yes |
| Both halves positive | **no** | **no** |
| Stat MAE not worse | **no** | **no** |

## What the data says

- **A dose response in 2025-26.** Splitting players into fifths by the matchup index, the volume the model missed rises steadily:
  3-point attempts vs projection: **-4.8%, +0.9%, +0.6%, +4.3%, +10.4%** (mean index 0.000 to 0.202). Assists vs projection: **-3.0%, +0.4%, +5.9%, +6.4%, +13.0%** (index -0.022 to 0.180).
  In the best-matchup fifth, players got about a tenth more 3-point attempts and 13% more assists than v2 projected. That is large for props.
- **The slope is not stable between seasons.** 0.89 against 0.12 for 3PM and 0.75 against 0.36 for AST, a factor of 7 and 2. Applied at the 2024-25 size, the adjustment overshoots and costs accuracy; the control, which has no real signal, is hurt even more, which is the control behaving correctly.
- **Likely reasons (hypotheses, not tested):** 2024-25 had no prior season, so its index used only the current year's rates from game 15 on (noisier, and the early weeks where matchup data matters most are excluded), while 2025-26 blends last season in; and v2's own defense term was fitted on 2024-25, so its 2024-25 residuals are not the same kind of miss.
- **Not separated here:** whether the player-specific mix adds anything over the opponent-only average. The opponent-only context index scored identically under the frozen slope, which says nothing either way; their own-slope comparison was not computed.

## What this does and does not mean

- It does **not** show the diet score belongs in pricing. The registered rule failed, and the slope that works on 2025-26 was estimated on 2025-26 itself, so any gain from it is in-sample.
- It **does** say the earlier NO-GO (`diet-test.md`) was not evidence that matchups carry nothing. Both indices predict the model's volume miss with a dose response, at t 3.5 and 6.9.
- The next test has to avoid the fit-season problem: freeze the slope from 2025-26 (**3PM 0.12, AST 0.36**) and score it on the 2026-27 games as they happen (a never-priced shadow with a forward read), which is a genuine out-of-sample test with a full prior-season blend. That is registered before it is read, together with the player-mix against opponent-only comparison.

## Correction (2026-10-25, found after this run while building the live term)

The play-by-play carries the All-Star game as a regular-season game with invented teams (2024-25: CAN, CHK, KEN, SHQ; 2025-26: STARS, STRIPES, WORLD). The runner counted them as defenses, so the league mean in the vs-league tables had 37 teams instead of 30 and every index
carried a constant positive offset of about +0.10 that drifted through the season (+0.078 in October to +0.13 in March). A drifting offset can correlate with a league-wide trend in volume, so the 2025-26 slopes and the dose response above may be partly that, not the matchup.
The fix is a bug fix and changes no rule: real teams only (20 or more games, the page's own cut). The corrected run is `matchup-volume-corrected-results.md`; it was run after seeing run 1, with the same pass conditions, and both are reported.
