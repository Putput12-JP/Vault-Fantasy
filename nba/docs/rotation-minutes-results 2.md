# Rotation-aware minutes: results

Rules: [rotation-minutes-test.md](rotation-minutes-test.md), committed before the runner (`b52ca7e20`); runner `test_rotation_minutes.py` committed before it was run. Numbers: `nba/data/rotation_minutes.json`.
Run once on 2026-10-25. Fit on 2022-23 to 2024-25, test 2025-26 (27,797 player-games who played, 1,308 games). Nothing here changes what the page prices or bets.

## Verdict: **FAIL** (the pre-registered bar needs every condition; four of seven were met)

| Minutes MAE, 2025-26 | A: as first graded | C: state mixture (candidate) | B: single model (control) | Oracle: true state known |
|---|---|---|---|---|
| All players who played | 4.922 | 4.797 | 4.792 | 4.637 |

| Condition | Needed | Got | Met |
|---|---|---|---|
| Whole-season gain, C over A | t >= 2.5 | +0.124 min, t 8.84 | yes |
| All five cuts positive | yes | cut (d) +0.001, cut (c) -0.035 | **no** |
| Cuts (a) and (c) at t >= 2.5 | yes | (a) 6.98, (c) -1.69 | **no** |
| No cut at t <= -2.5 | yes | worst -1.69 | yes |
| Props pooled gain | t >= 2.5 | +0.15%, t 2.11 | **no** |
| No stat worse | all four | 3PM worse (0.8849 to 0.8866) | **no** |
| Calibration within 4 points | every band with 100+ | all five bands within 3.0 | yes |

## The cuts (gain in minutes MAE, C over A)

| Cut | Gain | t | Player-games |
|---|---|---|---|
| (a) a rotation player is Out | +0.108 | 6.98 | 21,183 |
| (b) pre-game spread beyond 8 | +0.116 | 4.39 | 7,806 |
| (c) ranked 9 to 12 in the pool | **-0.035** | -1.69 | 6,362 |
| (d) starters in games decided by 20 or more | +0.001 | 0.03 | 2,808 |
| (e) each team's first 15 games | **+0.200** | 6.45 | 4,485 |

## What it says

- **It is a real minutes improvement for the rotation**: about 0.12 minutes overall, 0.20 in the first 15 team games, 0.11 when a rotation player is out and 0.12 in lopsided games. Calibration of "in the rotation" is good (predicted 96.0%, actual 96.7% in the top band; 12.5 vs 11.4% in the bottom).
- **It does not help where the problem was framed**: the fringe (ranked 9 to 12) is slightly worse than before, and starters in blowouts are unchanged. Telling who among the last few players gets on the floor is the hard part, and this feature set does not do it.
- **Props barely move**: the pooled gain is 0.15% of error (t 2.11), and 3-pointers get slightly worse. Minutes accuracy of 0.1 per player does not carry through to the props at this size.
- **The mixture by blowout probability adds nothing over a single model that has the blowout probability as a feature**: C against B is -0.005 min (t -3.06, C slightly worse). B against A is +0.129 (t 9.39). B was a control and is not a registered candidate, so it is not promoted by this result.
- **The state matters a lot if it is known**: with the game's true state given, MAE falls to 4.637, a 0.285-minute gain over A (t 16.6). That is the part a simulation that draws the game state can use; a pre-game projection cannot, because the margin is not known before tip. Whether the Game Simulation should draw from the state-conditional models is decided after the B3 read on 2026-11-16, comparing this against B3's own accuracy.

## Limits

16.6% of pool rows have P(plays) under one half (the dress table says about a third of the lowest-minute candidates do not dress), so the pad problem is real, but removing it did not move the props. The test used one season, the walk's minutes state, and a 12-minute cut-off; nothing was tuned and no other cut-off was scored.

## What would be registered next (not run)

A second round with **B as the declared candidate** (rotation features plus the blowout probability, no state split), a stricter bar on the fringe cut, and a separate fringe model for ranks 9 to 15. It would be registered first and tested on 2025-26 with a held-out check on 2024-25. This round does not count for or against it beyond the numbers above.
