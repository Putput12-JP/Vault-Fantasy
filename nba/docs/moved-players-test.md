# Players on a new team: pre-registered minutes test

Written and committed before any result was computed.

## Why

The minutes model (v2, which prices every prop) only counts a player toward his team's minutes once he has played a
game for that team. Everyone else on the team is then rescaled to fill the team's minutes. So a player who changed
teams (trade, signing) is left out of his new team for his first game, and his new teammates' minutes are stretched to
cover his. The backtests (`build_minutes_model.py`, `build_prop_model_v2.walk`) had the same rule, so this was never
measured.

Live it is worse: the player is priced from the Minutes Lab's separate estimate on top, so the team's minutes run past
what a game holds. For the 2026-27 opener, 154 players are on a new team since their last game; PHI's model projects
Embiid, Maxey and Edgecombe at 48 minutes each with LeBron James and Jaylen Brown left out of the count.

## The change (one variant, fixed now)

**v2mv**: identical to the shipped v2 except that a player dressed for a team-game whose minutes history is from
another team counts as a candidate. His base is his own minutes average and starter share carried over unchanged, with
his position group as before; every other term is computed exactly as for any player. The team minutes target is
re-tuned on 2023-24 by the same ratio method minutes v3 used (`build_prop_model_v3_full.walk_v3`), because the
candidate list changes. Rookies and anyone with no NBA minutes history stay as they are (not projected by the model).

## Data and protocol

Same as every prop-model test: state walked from 2022, stacker and calibration fit on 2024-25, tested on 2025-26
(`build_prop_model_v3_full.compare`, identical player-games and prices).

## Measures

1. **Minutes accuracy on 2025-26**, on player-games both rules project (MAE of projected vs actual minutes):
   - **New-arrival team-games**: team-games where at least one dressed player is within his first 10 games for that
     team (season openers after an offseason move, and games after a trade). This is where the rescale stretches
     teammates.
   - **All team-games.**
   Differences with standard errors from a paired bootstrap over games (1,000 resamples).
2. **The moved players themselves** under v2mv (v2 does not project them at all): minutes MAE over their first 10
   games for a new team. Reported, not part of the decision.
3. **Every signal's verdict** (Kalshi and sportsbook GO / WATCH / NO-GO) under both rules, from the same harness.

## Decision

- **v2mv replaces v2's minutes rule** if its MAE on new-arrival team-games is lower by 2+ standard errors **and** its
  MAE on all team-games is not higher by more than 2 standard errors. This is a fix for known double counting, so it
  is judged on minutes accuracy, not on whether edges survive.
- **Signals follow the inputs.** If v2mv ships, the live record runs on v2mv minutes. A signal that is GO today and is
  not GO under v2mv moves to WATCH. No signal is promoted by this test.
- **If v2mv fails**, v2 stays and the result is reported before anything else changes.

## Live wiring if it ships

The current roster (Minutes Lab rosters from ESPN, refreshed daily) is the team: a player with minutes history from
another team is a candidate for the team that lists him now, and is no longer a candidate for the team he left. The
Minutes Lab's estimate stays only for players with no minutes history (rookies). `pricing.game_minutes`, the page's
`gameMinutes`, and `check_minutes_parity.py` change together, and parity must stay exact.
