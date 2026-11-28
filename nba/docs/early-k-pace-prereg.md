# Game model: early-season K and pace, pre-registration

Written 2026-11-19, before `nba/scripts/test_early_k_pace.py` was run. Nothing here changes `data/game_model.json`, the Slate or the Game Picks record.

## Why this test, and what it is not

- The possession-efficiency rating model as a **replacement** for the shipped model was already tested and rejected (`game-model-challenger-results.md`, Oct 24: pooled t -3.83). This test does not repeat it.
- That doc's exploratory section looked at a fast-learning challenger in the first 28 days and found nothing, but it carried no verdict and never varied K inside the shipped model. That is the gap.
- Trigger: the Nov 18 Memphis case. Vault carries half of last season's rating (CARRY 0.5) and then moves 4% of each miss (K 0.04), so a team that changed in the offseason stays mis-rated for weeks.

## Variants, all inside the shipped model, shipped parameters otherwise unchanged

Shipped reference **S**: the parameters in `data/game_model.json`, injury report as of tip.

- **E, early K.** The rating step is K x M for a team's first N regular season games of a season, then K. M and N are chosen on the tune seasons only (2022-23, 2023-24; 2021-22 warm-up) by margin MAE over each season's first 28 days, who actually sat. Grid: M in {1.5, 2, 3, 4}, N in {10, 20, 30}.
- **P, pace-normalised margin.** The rating update uses the actual margin scaled to league-average pace: margin x (league possessions / game possessions). Possessions per team = FGA + 0.44 x FTA - OREB + TOV from the box score, averaged over the two teams. Predictions are unchanged in form.
- **Q, pace term in totals.** Each team has a possession pace, updated by an exponential average (step 0.10, carried 0.5 toward league average at season start). The predicted points for each side are multiplied by the matchup pace over league pace. Margins are untouched.

K, CARRY and every other parameter stay at their shipped values. P and Q have no tuned parameters (0.10 and 0.5 are fixed here, not searched).

## Scoring

Test seasons 2024-25 and 2025-26, the injury report as of tip, the closing line where there is one. Paired bootstrap over games, 1,000 draws, seed 11. Report, for the whole season and for the first 28 days:

- margin MAE (E, P) and total MAE (Q), against S and against the market close
- difference vs S with its standard error
- the information test against the close (OLS of the result on the market and the model gap), as in `build_game_model.py`

## Rules for a verdict (fixed now)

A variant is **Better** only if all hold:

1. pooled whole-season t of at least 2 against S (E may instead be judged on the first 28 days if that is its stated purpose, but it must not be worse than S on the whole season at t -2 or below);
2. the difference is in the same direction in each test season;
3. the information test against the close is within 1 t of S.

Otherwise the variant changes nothing live. A result on the first 28 days alone is a hypothesis, not a ship. Anything seen after the run (other windows, other parameters) is exploratory and carries no verdict.

## Not in this test

- Garbage-time capping, on/off or lineup data, shooting-luck shrinkage: separate registrations.
- Forward scoring on 2026-27 games: only after a variant passes, with the parameters frozen first.
