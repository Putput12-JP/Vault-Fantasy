# Game model round 4: the Vault ratings against the first posted spread

Written 2026-11-10, before this test was scored on 2025-26 or on this season. Runner: `nba/scripts/test_game_model_round4.py`.
Results land in `nba/docs/game-model-round4-results.md` only after this file is committed.

## Why

Three rounds changed the model and none made a pick against the **closing** spread win (49.7 to 50.8% however the ratings are built). The line our
picks are graded on is taken 4 hours before tip, which is nearly the close: it moves 0.44 points from there. So the question this round is not the
model. It is the **clock**.

`docs/game-model.md` has always shown the model beating ESPN's opening line, and has always set that aside, correctly: the model used the injury
report and the open was posted before the news. Scouting on 2024-25 only (the season rounds 3 and 4 use for fitting and looking) took the news away
from the model: **ratings only, no injury report at all**. It still pointed the right way. At a gap of 2 or more points the opening spread then moved
toward the model's side by 0.95 points on average (t 7.8) and the side covered the open 391-334 (53.9%). An efficient opening line would not move
toward a ratings model that knows less than it does.

Two things could still make that an illusion, and this round is built to remove both:

1. **The model may have seen a game the open had not.** The open has no timestamp. If it was posted before a team's previous game, the model's
   ratings include a result the line could not have.
2. **The open may not have been a number anyone could bet.** ESPN's "open" is a field in a feed, not a line we watched.

## What is scored

**Two samples, two clocks.**

- **History: 2025-26** (label 2026; never read for this question). The line is ESPN's opening spread (DraftKings where present, else ESPN BET).
  The ratings are the model's **as of 36 hours before tip**: no game that tipped inside those 36 hours has updated anything. That is earlier than
  an NBA line is normally posted, so the model cannot hold a result the open lacked. 2024-25 is reported beside it as the season already looked at.
- **This season: the recorder's own tape.** For every regular-season game through 2026-11-09, the first DraftKings spread the recorder saw
  (`snapshots/<day>/espn.jsonl` on `nba-data`; a median of about 25 hours before tip), its two prices, and the last DraftKings spread seen before
  tip. A number with a timestamp that was on the screen. The ratings are the model's as of that first sight, using only games that tipped at least
  12 hours earlier (the daily build's first run is 7:23 AM Eastern, after the overnight box scores).

**The model, both samples: ratings only.** Team ratings, home court and the back-to-back flag from the schedule. No injury report, no lineups, no
line, no sharp money. Two rating sets, both already frozen:

| | Ratings |
|---|---|
| N | the shipped model (`data/game_model.json`) |
| NL | round 3's option L, as fitted on 2024-25 (W 0.75, KL 0.16): the ratings also learn from the closing line of games already played |

**The pick.** edge = model home margin + the early home spread. Positive: home at that spread. Negative: away. Graded on the final against that
early spread. **Primary cut: a gap of 2 or more points** (fixed now from the 2024-25 look). 0+, 3+ and 5+ are reported.

## Metrics

- **Line move toward the pick**, in points, from the early spread to the closing spread (history) or to the last look before tip (tape), in the
  picked side's favour, with its t over picks. This is closing-line value: the quiet measure, since a line move is far less noisy than a final.
- **Record against the early spread.** History has no stored opening price, so it is a win-loss record only (a price is never invented).
  The tape has the price at first sight, so it also has units.
- For reference on the tape: the locked 4-hour record (`data/game_picks.json`) on the same games at the same gap.

## Verdict (fixed now, per rating set, at the 2+ gap)

- **History passes** when on 2025-26 the line moved toward the pick with t >= 2.5 and the record against the open is 52.4% or better.
- **The tape passes** when the line moved toward the pick with t >= 2.5 and the units at the stored first-sight price are above zero.
- **GO** = both pass for the same rating set. N is preferred when both rating sets pass: it needs nothing new in the daily build.
- **What a GO is.** A reason to lock the spread pick at the first posted line instead of 4 hours before tip, recorded from the merge forward and
  flagged for close monitoring with its sample size. It is a claim about the clock, proven on one held-out season and one live tape. It is not a
  claim that the model beats the close, which three rounds say it does not.
- **What a GO is not allowed to do.** Re-price any locked pick. The existing record stays as locked; an early-lock record would be its own row,
  rebuilt for past days from the tape and labelled rebuilt.

## Limits, stated before the numbers

- An opening number is a small-limit number. A record at the open says what a bettor who was there got; it says nothing about size.
- The tape sample is 154 games. At a 2+ gap that is on the order of 80 picks: enough to read a line move, not enough to read a win rate. The
  units rule is a direction check, not a proof.
- 2024-25 picked the 2+ cut, so its row is in sample for that choice.
