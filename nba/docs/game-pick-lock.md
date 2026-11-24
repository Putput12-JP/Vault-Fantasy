# NBA game picks: the lineup lock

Written 2026-11-23. Replaces the "Lock" paragraph of `game-picks.md` (a game picked 4 hours before tip). Everything else in `game-picks.md` stands:
the model, the line, the pick definitions, the shadow grades, the reading rules.

## The change

A game's spread and winner pick is written **once, when both teams' starting fives are Confirmed on NBA.com's daily lineups, and no later than 20 minutes before tip**
(`game_pick_record.lock_open`, `LOCK_FALLBACK_MIN = 20`). Until then the page shows the live lean, dashed, and records nothing. It used to be written at the first poll
within 4 hours of tip.

A five is confirmed when at least five players carry a starting slot and every one of them is `Confirmed` (`game_pick_record.fives_confirmed`). A game whose
lineups never confirm is picked at the first poll inside 20 minutes. Nothing is ever written after tip.

Nothing else moved: same model (`vault_mean`, with the injury report and NBA.com inactives in), same line (DraftKings first), same first-look-is-the-pick rule, the last look
before tip still kept as the close.

## Why (measured on the tape, 258 games Oct 20 to Nov 22; about 255 in the table, the games with a row at each time)

- The 4-hour pick was written before the news. In the last 4 hours before tip **122 of 258 games had a material injury-report change** (a player moving in or out of
  Out / Doubtful / Questionable). Of those, 96 games changed after the 90-minute mark, 71 after 60 minutes, 53 after 45, 27 after 30, **5 after 20**.
- Nov 22, OKC @ MIA: Gilgeous-Alexander went Questionable to **Out 90 minutes before tip**, Antetokounmpo **59 minutes before**. The model's margin moved from OKC by 3.9 to
  OKC by 1.7 (Gilgeous-Alexander alone) to OKC by 4.6 (both) to OKC by 4.1 at the last poll. The 4-hour pick was written with both Questionable.
- NBA.com confirms the fives late: at the first poll where both were confirmed, tip was a median 17.6 minutes away (p25 16.2, p75 19.2, max 22.6) on the rebuilt days. The recorder
  polls every 3 minutes inside 3 hours of a tip (`FAST_S`), so a lock at "both confirmed" lands at 5 to 23 minutes before tip.
- How far a pick still moves after each candidate lock time (vault margin and DraftKings spread against the last look before tip, 258 games):

| Locked at | Mean margin change to the last look | Games where the margin moves 2+ points | ATS side differs from the last look |
|---|---|---|---|
| 3 hours | 0.37 | 4.3% | 9.4% |
| 90 min | 0.31 | 2.7% | 6.6% |
| 60 min | 0.26 | 3.5% | 6.2% |
| 45 min | 0.11 | 0.8% | 4.7% |
| 30 min | 0.08 | 0.8% | 4.7% |
| **20 min** | **0.01** | **0.0%** | **2.3%** |
| 10 min | 0.00 | 0.0% | 1.6% |

A fixed 20 minutes alone would do nearly the same; "both fives confirmed" is the cleaner statement of the rule, and the fallback guarantees a pick when NBA.com is late or down.

## What it costs

- **Closing-line value is near zero by design.** The pick is written minutes before the last look, so a spread has little time to move. Rebuilt average CLV is +0.05 points (15 of 245
  picks beat the last look). The CLV tile still shows, but it can no longer say much; the old +0.01 on 247 said little too.
- **The pick is written when it can barely be acted on.** The Game Picks page shows the live lean from the morning. The record is the measure; it is not a bet signal (unchanged).

## The record was rebuilt (every number below is on the tape, nothing replayed with today's model)

A change to the lock changes every row, so the days before it were rebuilt at the same rule, not left under the old one
(`rebuild_game_picks_lineup_lock.py`, `data/game_picks_backfill.json`, rows tagged `bf`). For each game, on the recorder's own polls: the lock is the first poll before tip with a
spread posted, a Game Simulation `vault` row, and `lock_open` true on the lineups rows as they stood at that poll; the close is the last such poll. The margin is the vault
row's (the model as the page showed it, with that moment's injury report and inactives in), the line is ESPN's feed by `pick_line`, the grade is `grade_row`.

**Cutover.** `LOCK_V2_FROM = 2026-11-24`. Tip days before it use the rebuilt rows; from it the live recorder's rows replace them. A game before the cutover that is not in the rebuild
(a day not yet final) keeps its live row, written at the old lock, and `build_game_picks.py` prints how many. Rerun the rebuild on a fresher tape after those days settle.

**The old record is kept whole** in `data/game_picks_4h_lock.json` (frozen 2026-11-23, 248 games, live rows plus Oct 20 to 23 rebuilt at that lock) as the shadow to compare against. The live
day files on the `nba-data` branch are untouched. The page ignores live day files before the cutover.

### Check of the rebuild against the live 4-hour record

`--rule 4h` rebuilds the OLD lock from the same tape, so the method can be checked against what the recorder wrote with the exact margin (220 live games, Oct 24 to Nov 22):
mean absolute margin difference **0.12 points** (largest 1.73), same spread on 212, **same ATS side on 216 of 220**, same line book. The four side differences are all picks within 0.4 points of the number.

### Old against new (248 games, Oct 20 to Nov 22)

| | Old record (live, 4 h) | Same rebuild, old rule | **New (lineup lock)** |
|---|---|---|---|
| Spread, units at the posted price | 109-138, **-38.82** | 110-136, -35.92 | **110-135, -35.06** |
| Winner straight up, units | 161-86, **-18.73** | 160-87, -20.38 | **159-88, -23.20** |
| Market favourite on the same games | 172-75 | 172-75 | 173-74 |
| Spread A (edge 5+) | 12-6, +4.95 | 12-8, +2.95 | 11-11, -0.92 |
| Spread B (3 to 5) | 21-27, -7.66 | 21-27, -7.83 | 21-25, -6.11 |
| Spread C (under 3) | 76-105, -36.12 | 77-101, -31.04 | 78-99, -28.03 |
| Winner A (70%+) | 63-15, -1.62 | 64-15, -1.29 | 66-14, **+0.63** |
| Winner B (60 to 70%) | 55-30, -5.99 | 58-30, -3.62 | 52-35, -12.84 |
| Winner C (under 60%) | 43-41, -11.12 | 38-42, -15.47 | 41-39, -10.99 |
| Spread top 3 of each day | 46-47, -5.18 | 43-50, -10.70 | 46-47, -5.15 |
| Winner top 3 of each day | 73-20, -0.31 | 73-20, -0.32 | 73-20, -0.10 |
| CLV, spread (average points, picks beating the last look) | +0.01, 49 of 247 | +0.00, 47 of 243 | +0.05, 15 of 245 |

Read the middle column as the rebuild's own noise: moving from the live record to the rebuild at the *same* rule changes the totals by up to 3 units because the rebuild uses the
simulation's one-decimal mean margin and ESPN's line. The honest effect of the lock is middle column to right column. **Twenty-six of 248 spread picks changed side** (10.5%); the winner
pick changed on one game. Of the 21 changed picks that had a result, the old side went 11-10 and the new side 10-11: no sign the later lock picks better, and no reason to expect one
(`game-model.md`: the model adds nothing the closing spread has not priced, and it is context, not an edge). The aim is that the pick is made on the information a bettor would have at tip.

OKC @ MIA on Nov 22 (the case that prompted this): the pick does **not** change. The lock-time model margin is OKC by 4.1 against a line of MIA -4.5, edge 8.6, grade A, and it lost; the
4-hour pick was OKC by 4.0, edge 8.5. Gilgeous-Alexander and Antetokounmpo were both out, and the model's two adjustments nearly cancel (the line did not move either). That A is the model
and the market disagreeing about two stars out at once, not stale inputs.

### Flagged for close monitoring (records that improved against the old number)

None is evidence. All are far under the 100-pick reading rule except the overall rows, and the improvement is inside the rebuild noise shown above.

- Winner A: 66-14 (+0.63 units), n = 80, was 63-15 (-1.62).
- Spread C: 78-99 (-28.03), n = 177, was 76-105 (-36.12).
- Spread overall: -35.06 units on 245 priced picks, was -38.82 (the rebuild at the old rule alone gives -35.92).
- Winner top 3 of each day: 73-20, -0.10, n = 93, was -0.31.

Worse than the old number: Spread A (n = 22, 11-11), Winner B (n = 87), winner overall (-23.20 against -18.73).

## Limits

- The margin is the Game Simulation's mean margin to one decimal, not `vault_mean`'s exact margin (as `backfill_game_picks.py`, measured above: 0.12 mean difference). A pick with an edge
  under about 0.5 points could differ from what the live recorder would have written.
- The line is the ESPN feed's, not the board's merge with Action Network and Pinnacle. ESPN drops a game's lines at tip, so the close here is the last poll with a spread, up to about
  10 minutes before tip. On 24 live games the live record's close differed from this one by 1 point (one by 3), and on 4 of the first 28 rebuilt games. `data/game_ctx.json` (closing spreads of
  past games, read by the props board) is rebuilt from the close and moved on those 28 games.
- Fives are read from the lineups rows on the tape. Days where NBA.com's file was late or missing take the 20-minute fallback, as the live recorder does.

## Files

`scripts/game_pick_record.py` (`lock_open`, `fives_confirmed`, `LOCK_FALLBACK_MIN`, `LOCK_V2_FROM`), `scripts/snapshot.py` (passes the lineups rows in),
`scripts/rebuild_game_picks_lineup_lock.py`, `scripts/build_game_picks.py` (cutover), `data/game_picks_backfill.json`, `data/game_picks_4h_lock.json`,
`tests/test_game_pick_record.py` (`LockRule`). `backfill_game_picks.py` is superseded for the days before 2026-11-24 and kept for the record of how the first 28 were built.

Rerun: `git archive origin/nba-data snapshots results | tar -x -C DIR`, then `python3 nba/scripts/rebuild_game_picks_lineup_lock.py --tape DIR --before 2026-11-24`
(`--rule 4h` for the check), then `python3 nba/scripts/build_game_picks.py`.
