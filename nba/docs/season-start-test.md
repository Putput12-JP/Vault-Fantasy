# Game model season start: pre-registered test

Written and committed before any result was computed.

## Why

The game model (Vault line on the Slate and Game Lines pages; context only, it does not beat the closing line) starts
each season from last season's team ratings shrunk 40% toward average. Two blind spots showed up on the 2026-27 opener:

1. **Rosters.** A trade or signing never moves a team's rating. PHI is rated as last season's PHI with LeBron James and
   Jaylen Brown on the roster; 154 players are on a new team since their last game.
2. **Scoring level.** In the first week of 2024-25 and 2025-26 the model's total sat 3.6 and 4.8 points under the
   closing total (83% and 91% of games) while games went over the close; the gap closes by about week 4. Likely causes:
   the league base learns very slowly (0.002 per point), the season-start shrink removes scoring level the team
   offense / defense terms had absorbed, and playoff games (slower, lower scoring) update offense and defense.

## Variants (fixed now)

**R, roster carry.** At each new season, after the usual shrink, every team's rating moves by
`k x C x (value of players who joined - value of players who left)`, where value is the model's own per-player value
(game score above replacement, the number the injury adjustment already uses), C is the model's existing points per
unit of value, and k is one scalar chosen from {0.25, 0.5, 0.75, 1.0, 1.25} on the tune seasons (2022-23, 2023-24),
by first-4-weeks margin MAE with who actually sat (as the model's other parameters were tuned). A player's team for the
new season is the team he first plays for in it (the opening roster; in the backtest this is known slightly after the
fact for late signings, noted as a limitation). Live, it is the current roster (ESPN, the Minutes Lab's source).

**T, scoring level.** At each new season, the league base is set to last regular season's actual points per team,
team offense and defense are re-centered to average zero, and playoff games no longer update offense and defense
(team ratings still learn from them).

Everything else is unchanged, and both variants keep the model's current tuned parameters.

## Measures (test seasons 2024-25 and 2025-26, injury report as of tip, as the model's own test)

- **R**: margin MAE against the final margin over each season's **first 4 weeks** (28 days from its first game), and
  over the whole season.
- **T**: total MAE against the final total, same two windows. The model's average total minus the closing total in
  the first week is reported.
- Differences against the current model with standard errors from a paired bootstrap over games (1,000 resamples).
  Against-the-spread and the information test against the closing line are reported, not used for the decision.

## Decision

Each variant is judged on its own measure:

- **GO** if its first-4-weeks MAE is lower than the current model's by 2+ standard errors **and** its whole-season MAE
  is not higher by more than 2 standard errors. GO variants go into the live Vault line together.
- Either way, the game model stays **context only**: this test is about the line being informed, not about betting it.
- The Slate always names who joined and left each team. If R fails, it labels the Vault line as built on last
  season's rosters. If T fails, it leaves out the Vault total for each team's first 4 weeks (the measured bias window).
