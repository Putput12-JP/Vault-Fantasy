# Novig game lines: whole-game rotation

`nba/scripts/novig.py` reads Novig's public order books for the moneyline, every spread strike and every total strike of a
game. A game lists about 48 of these markets (1 moneyline, 9 to 15 spreads, 35 to 37 totals on 2026-10-19), and each costs a
book call plus a trades call when the book changed. `NOVIG_BUDGET` is 220 requests a poll, so a 14-game slate (about 670 book
calls) cannot be read in one poll.

## What went wrong

The budget was spent in the order the API listed the markets, so the later games got nothing (on the 2026-10-20 slate the
third game had no moneyline and no spread), and a game read part-way chose its main line from the strikes it had reached.
The API lists spread strikes widest first (6.5, 5.5, 4.5 ...), so a cut-short read of BOS @ DET called 4.5 the main spread
when the true main is 1.5. A main line that flips because of where the budget ran out also changes the `quotes()` key
(`<game>|sp|<home handicap>`), which writes a false line move into `snapshots/<day>/novig.jsonl`.

## The rule now

1. **Whole games.** A poll reads a game's moneyline, every spread strike and every total strike, or none of it. Games are
   taken oldest complete read first (never read first, then by tip time). A game starts only if the remaining budget covers
   its books plus the trades calls it needed last time (`tc`, capped at one per market); the first game of a poll always
   starts. A game that has started is never cut off: its books were reserved when it was chosen.
2. **Complete or not published.** A game is complete when every open line market in the catalog came back with a book (one
   retry for a book that failed). `main_spread` and `main_total` are the strike nearest 50% of a complete ladder
   (`main_line()`; ties go to the deeper book, then the smaller number, never to API order).
3. **Carry with an age.** A game not read this poll, or whose read came up short, keeps its last complete result. Per game
   the board carries `fresh` (read this poll), `asof` (when that read finished) and `age` (seconds since). A carried result
   older than `NOVIG_CARRY_MAX_S` (7200) is dropped, not shown. A game with no complete read has `ml`, `main_spread` and
   `main_total` all `null`, `age` `null`, and `short` set to the number of books that never came back.
4. **Trades are unchanged.** The $250 save threshold, the tape, the per-market cursor and the "unchanged book skips the
   trades call" rule are as before, so the Novig money alert in [novig-money.md](novig-money.md) still counts tickets on every
   strike. One fix: a trades call skipped for budget no longer marks the book as seen, so it is retried on that game's next
   read instead of lost. (Props keep the old behaviour.)
5. **`quotes()` keys.** A carried game keeps the same main line, so its keys and values are the same as the poll before and
   `Day.record` writes nothing for it. A key only changes when a complete read finds a different main strike.
6. **Props** keep their own `NOVIG_PROP_BUDGET` (80) and their rotation.

`board['novig']['rotation']` summarises each poll: games read, carried, with no complete read, short, the oldest age and a
`{game: age}` map. `poll()` also prints it.

## Refresh age

Roughly 48 book calls plus the trades calls of the books that changed per game, so 2 to 4 games per poll at 220 requests.
Polls run every 5 minutes inside 3 hours of the next tip and every 15 minutes otherwise, so a 14-game slate is refreshed in
about 4 to 7 polls: 20 to 35 minutes at the fast cadence. The measured ages from the 2026-10-19 live run are in the pull
request. Raising `NOVIG_BUDGET` shortens it (about 100 requests per extra game).

## Limits

- A carried line can be up to `NOVIG_CARRY_MAX_S` old. Read `age` before treating it as a current price. The Novig panel on
  the page does not show the age yet.
- `rest`, `depth`, `tr` and `usd` on a game now cover its line markets only (before, they also included whichever props the
  rotation reached that poll). A carried game reports `tr` and `usd` as 0: the trades since its last read are not known.
- The trades call returns the newest 100 executions of a market. A market that trades more than 100 times between two reads
  of its game would lose the oldest. Novig NBA books are thin, so this was not seen, but a longer gap between reads makes it
  more likely.
