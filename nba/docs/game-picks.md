# NBA game picks: spread and winner

Written 2026-10-24, before any live pick was recorded or graded. Page: **Game Picks** (Markets). Record: **Track Record**, card "Game picks: spread and winner".
Code: `scripts/game_pick_record.py` (recorder and settle), `scripts/backfill_game_picks.py` (earlier days), `scripts/build_game_picks.py` (page snapshot).

## What this is, and is not

The model is the **Vault line** already on the Slate page: `build_game_model.py`, shipped as `model_state.json` `game`, scored live by `sim_engine.vault_mean`
(team ratings, home court, back-to-back, the injury report in points). **Nothing here changes it and nothing here adds a constant to it.**

It is **context, not an edge.** `docs/game-model.md`: 2,641 games of 2024-25 and 2025-26 against the closing spread, t = 1.23 (adds nothing the line has not priced);
against Kalshi's moneyline at 1pm, Brier 0.2057 for the model against 0.2008 for the price. The first four weeks of a season are the weakest
(`docs/season-start-results.md`: last season's teams are the prior), and the page badges those games "Early season". This record exists to measure that in public, win or lose.
Sharp money is context only: it is not an input and does not count toward anything here.

## Definitions (fixed now)

- **Line.** The posted home spread from the first book in this order that has one: DraftKings, Pinnacle, FanDuel, BetMGM, bet365, Consensus. DraftKings first because it is the
  book the game model's backtest used and the one most users bet. The spread and its two prices come from one book row. The moneyline comes from the first book in the same
  order that posted both sides. **A price that was not stored is never filled in**; a pick with no stored price is graded but has no units.
- **Lock.** A game is recorded from the first poll within **4 hours** of tip (the same window as the Game Simulation) that has a posted spread. Regular season only: the Vault line
  does not exist in the preseason. The **first look is the pick and is never re-priced.** The last look before tip is kept as a second clock, for closing-line value and for "did the
  side flip". Rows written after tip never count.
- **Spread pick.** edge = model home margin + home spread. Above 0: HOME at the spread. Below 0: AWAY at the opposite spread. Exactly 0: no pick. Result: the final home margin plus
  the spread against 0, a **push** at exactly 0. Units: 1 unit at the stored price of the picked side; a push is 0.
- **Winner pick.** The team the model gives better than even odds: Normal(margin / sd), sd = the tune-season sd in `model_state.json` (`game.sd_margin`). Graded straight up. Units: 1 unit at the
  stored moneyline of that team. Exactly even: no pick.
- **Closing-line value.** Spread: the move of the spread between the first look and the last look before tip, in the picked side's favour (points; positive = we got the better number).
  Winner: the no-vig chance of the picked team at the last look minus at the first, when both looks carry both moneylines.
- **Baseline for the winner pick.** The market's own favourite (the side with the negative spread) straight up, on the same games.

## Shadow grades and daily ranks (added 2026-10-24)

Shown on the Game Picks page (a letter beside each pick, `#1` to `#3` for the day's most confident, and a record by grade in the hero) and tracked on Track Record. **Labels to track, not recommendations.**
The cut-offs are fixed in `docs/pick-grades.md` before any grade was read and are not tuned:

- **Spread grade** from the edge in points: **A** 5 or more, **B** 3 to 5, **C** under 3.
- **Winner grade** from the model's chance for its side: **A** 70% or more, **B** 60 to 70%, **C** under 60%.
- **Rank** = the order of the day's picks by edge (spread) or by that chance (winner). A day with fewer than N games is left out of "top N".
- Grades and ranks are **derived** from the stored edge and chance, so the rebuilt days carry them too and nothing in the data changed.
- The Game Picks page keeps the **season total** at the top and, under the day strip, shows the same stats **for the selected day**: spread record and units, the winner record against that day's market favourite, closing-line value, and the record by grade. The selected day's games are ringed in the season strip and shaded on the units line.
- Track Record shows the record by grade and for the top 1 and top 3 of each day, with the closing-line value, and for the winner picks the average chance the model gave and the chance the closing spread implied for the same side, next to the market favourite's record on the same games.

What the 2,641-game history says (`docs/pick-grades.md`): against the closing line the spread **A** tier won 47.3% and the top 3 of each day 49.3% (the biggest gaps do worse); winner **A** won 80.5% where the market implied 79.2%, and the top 3 of each day 76.1% where it implied 76.1%. A grade
therefore says how far the model sits from the line, or how sure it is, not that the pick is better. The page says so in its footer.

## Reading rules (fixed now)

- No rate is quoted for a cell with fewer than **100 graded picks**; the page shows a dash. The record and units are always shown with their count.
- Intervals are Wilson intervals on the win rate once a cell reaches 100.
- A stated-confidence band is **verified** only when its hit rate is within 4 points of its predicted chance over 100+ picks (the `lean_loop.py` rule); otherwise collecting or off by N points.
- Break-even at -110 is 52.4%. ROI-style figures are units per pick at the stored price and are context, not a bet recommendation.
- Any cell that improves is flagged for close monitoring with its sample size. **None is flagged today** (see Results).
- The first clock (the pick) is the headline. The last-look clock is shown beside it, never instead of it.

## Data and where it lives

- **Live record.** `game_pick_record.log` runs after each poll (`snapshot.shadow`) and writes source `gpick` to the day folder on the `nba-data` branch. `game_pick_record.write_open`
  writes `gpicks/open.json` (today's picks that have not settled; the page shows them as locked). `ledger.settle` calls `game_pick_record.record`, which grades every final game from the
  box score's score and writes `gpicks/<tip ET day>.json` (two rows per game, first and last look) and `track.json` `gpick_days` (counts per day).
- **Earlier days.** The record starts when this change reaches the recorder. Regular-season games before that were **rebuilt** (`backfill_game_picks.py`, `data/game_picks_backfill.json`,
  rows tagged `bf`) from rows already on the tape: the Game Simulation's `vault` environment (the model as the page showed it, with that day's injury report in) and ESPN's line feed
  as of the same moment, graded by the very function the live record uses (`game_pick_record.grade_row`). Not a replay with today's model.
- **Page.** `build_game_picks.py` (called by `build_data_health.py`, daily) merges the live days from `nba-data` with the rebuilt days into `data/game_picks.json`, baked into the app as
  `GPICKS`. A game that has a live row replaces its rebuilt row, so there is no double count. Served from Pages the page also reads `gpicks/` from the branch directly.

## Where the rebuilt days differ from the live record (limits)

- The model margin is the simulation's **mean** margin, not `vault_mean`'s exact margin. Measured on 24 live games: mean absolute difference 0.11 points, largest 0.37 (the simulation
  breaks ties and cuts at zero). A pick with an edge under about 0.4 points could differ from what the live recorder would have written.
- The line is the ESPN feed's, taken at the sim row's timestamp. The live recorder reads the board's `mk.books`, built from the same ESPN feed plus Action Network and Pinnacle; the same book order picks the line. DraftKings was present for every game rebuilt.
- Rebuilt rows say so everywhere (`rebuilt` on the list, "Source" per day, the "Rebuilt only" filter). Nothing is added to or subtracted from them after the fact.
- Not rebuilt: preseason games (no Vault line), and any game with no pre-tip sim row.

## Results at the time of writing (2026-10-24)

28 regular-season games, Oct 20 to Oct 23, all rebuilt; no live pick exists yet. Every number below is far under the 100-pick reading rule, so none is quoted as a rate and nothing is claimed.

| | Picks | Record | Units (stored price) |
|---|---|---|---|
| Spread, first look | 28 | 12-16 (no pushes) | -5.16 on 28 priced |
| Winner, first look | 27 (one game exactly even) | 14-13 | -5.48 on 27 priced |
| Market favourite straight up, same games | 27 | 18-9 | n/a |

Closing-line value: 1 of 28 spread picks beat the last look (the line barely moves inside 4 hours); average +0.00 points. Last look instead of first: spread 11-17.

**Nothing improves on its baseline, so nothing is flagged for monitoring.** On these 27 games the model's winner pick did worse than simply taking the market favourite (14-13 against 18-9); n is
tiny, and it is the comparison the page keeps in front of the record. The forward record decides.

## Verification

- `tests/test_game_pick_record.py`: sign conventions (home spread, away pick, pushes, CLV direction), units at the picked side's price, a missing price gives no units, a row after tip never counts as the
  last look, a game not yet final is not settled, and `record()` end to end on a fake `nba-data` folder with the real ledger helpers.
- The rebuilt finals were checked against ESPN directly (CHI @ TOR 92-135, matching the results cache and the sum of player points).
- The page's totals were recomputed independently from `game_picks_backfill.json`: spread units -5.16, winner units -5.48, ATS 12-16, winner 14-13.
