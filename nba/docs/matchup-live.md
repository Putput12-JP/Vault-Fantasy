# Shot matchup in the live projections (3PM and assists)

Written 2026-10-25. In force from games on **2026-10-26**. Switch: `nba/data/matchup_terms.json` (`enabled`, per-stat `beta`). Evidence: [matchup-volume-corrected-results.md](matchup-volume-corrected-results.md) (registered Stage 1, PASS for both stats; run 1, [matchup-volume-results.md](matchup-volume-results.md), is invalid).

## What changes

A new term in the v2 projection, `matchup`, shown in the page's "How the projection is built" panel as **Shot matchup**, for **3PM** and **assists** only (points, rebounds, steals, blocks, turnovers are unchanged; combos such as PRA, PR, PA and RA inherit it through their parts).

- **3PM:** the player's 3-point shot mix (corner, above the break) against how much the opponent gives up there, from the Matchups page's own data (`data/diet_defense.json`, point in time, last season blended in until a team has 15 games).
- **Assists:** the player's assist-location mix against the opponent's assists allowed by location.
- **Term** = `base projection x (clip(1 + beta x index, 0.7, 1.3) - 1)`. Slopes **fitted on 2024-25 and frozen**: 3PM **0.881**, AST **0.778**. Index is a fraction (0.10 = ten percent softer than the league).
- **Size on live data (13,410 and 12,240 player-opponent pairs):** the multiplier runs 0.93 to 1.07 (3PM) and 0.92 to 1.08 (AST) for 90% of pairs; 0.92 to 1.08 and 0.90 to 1.10 at the 1st and 99th percentile. The median is 1.00, so it is a spread, not a shift.
- Players with fewer than 50 effective shots (3PM), fewer than 5% of shots from three (3PM) or fewer than 30 effective assists (AST) get no term. The sample board (example mode) never gets one.
- Python (`pricing.py` `matchup_idx`, `matchup_term`) and the page (`matchupIdx`, `matchupTerm`) are the same arithmetic: `check_matchup_js_parity.py` runs the page's own JS in node on the real data and agrees on 28,920 player x opponent x stat checks.

## What the evidence is, and is not

The registered test passed on 2025-26 with slopes fitted on 2024-25: volume error fell for 3-point attempts (t 3.59) and assists (t 3.88), a random-defense control got worse, both halves of the season were positive. **It is not a price result**, and the gains are small on average because most players sit near zero index.
The **player-specific mix added nothing over the opponent's overall allowance** (opponent-only index scored the same), so the real claim is "this defense concedes more 3-point attempts and assists".
2025-26 has been read many times; the forward read below is the confirmation. This was put into live projections at the owner's direction, ahead of that read, with the safeguards below.

## Records and history

Nothing recorded earlier is restated: bets, leans and the Track Record are as priced. Bet rows from 2026-10-26 carry `mt`, the matchup term inside their `mu` (stat units, summed over the parts for combos); rows without `mt` were priced before the term. The lean log, the Game Simulation and the Matchups page are not changed.

## Forward read (registered now, before any 2026-10-26 game)

- **Population:** settled single-stat 3PM and AST prop bets in `bets/<day>.json` on `nba-data` from games on or after 2026-10-26 that carry `mt`, with a result of win or loss and a stored `actual`. The ledger enters a prop at its first 3% edge, so this is the population that matters for betting (it is selected, and says so).
- **Statistic, per stat:** gain = `|actual - (mu - mt)| - |actual - mu|`, i.e. error without the term minus error with it. Game is the unit; bootstrap 2,000 draws, seed 7; t = mean / sd of the bootstrap means. Rows with `mt` equal to 0 are included and count as no change.
- **Read once, per stat, when that stat has at least 500 such rows from at least 25 game nights.** The first read stands.
- **KEEP** the stat's term if gain > 0 with t >= 1.65 (one-sided: the registered test is the prior). **DEMOTE** (set that stat's beta to 0 or `enabled` to false) if gain <= 0, or t < 1.65, at the read.
- **Early stop:** at any monthly look, if a stat's gain is negative with t <= -2.5, demote it at once.
- **Context, no verdict:** ROI and closing-line value of the bets with a non-zero `mt`, split by sign of `mt`; the gain split by whether the opponent-only index alone would have given the same sign.

## Not done here

Points, rebounds, steals, blocks and turnovers. Points can use the same shot-mix data and gets its own registered test next; rebounds, steals, blocks and turnovers need new extraction from the play-by-play (the shot table does not carry them). Nothing is built for them until that test passes.
