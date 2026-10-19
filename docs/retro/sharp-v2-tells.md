# Sharp Money V2 tells: how fast US books follow Pinnacle

Date: 2026-10-18. Code: `scripts/build_lead_lag.py` (tests: `tests/test_lead_lag.py`). Output: `data/lead_lag.json` (the clock) and `data/book_age.json` (current ages, written by the
workflow, not committed by hand). Source: the book tape `data/book_tape/<sport>/2026-10.jsonl`, which only writes a row when a book's number changes.

## What it measures

An event is a Pinnacle change of 0.5 or more (spread, total) or 2 points of no-vig home chance (moneyline), 3+ hours before kickoff, whose time is known
to within 30 minutes (some poll of that sport saw no change in the half hour before it). For each US book, judged on its own level so a book that always
hangs another number is judged on its moves:

- **led**: it had already moved the same way by the same step in the hour up to the Pinnacle row
- **followed**: it moved the same way by the same step after it, with the lag in minutes (moneyline: half the move)
- **not followed**: it never did before kickoff

The thresholds were fixed before looking. Resolution is our polling gap, so a lag under about 10 minutes cannot be told from zero. Nothing is shown under n of 15.

## What it found (tape from 2026-10-17, so one weekend of college football plus a few NBA games)

| Sport and market | Pinnacle moves | Book-moves checked | Never followed | Had already moved | Followed | Median lag when followed | Followed within an hour |
|---|---|---|---|---|---|---|---|
| CFB spread | 26 | 130 | 71.5% | 11.5% | 16.9% | 49.8 min | 9.2% |
| CFB total | 18 | 89 | 74.2% | 13.5% | 12.4% | too few | 7.9% |
| CFB moneyline | 12 | 60 | 76.7% | 13.3% | 10.0% | too few | 5.0% |
| NBA spread | 9 | 45 | 64.4% | 20.0% | 15.6% | too few | 4.4% |
| NFL | 0 | 0 | - | - | - | - | - |

NFL has no localised events yet: its tape was polled a few times a day until recently, so no Pinnacle move can be placed within 30 minutes.

## What it means

- A US book that is behind a Pinnacle move usually **stays behind**: the books never moved the same way before kickoff in about 7 of 10 book-moves, and followed within an hour in
  under 1 of 10. So "the window closes in minutes" is not what the tape says. The gap often just persists. That fits the record: the old +EV-at-a-book signal is 35-43
  (44.9%) with CLV -1.7% (n=67). A persistent gap means Pinnacle and that book disagree, not that the book is about to be corrected.
- Where the book does follow, it is not fast: median 50 minutes on CFB spreads (25th to 75th percentile 20 to 180 minutes).
- Edge windows on the Plays cards are therefore shown as the measured gap age (when the book last changed, when Pinnacle last moved) and not as a countdown.
- All of it is one weekend. Flag: CFB spread 26 events, 130 book-moves (correlated within a game, so the real sample is closer to 26). Rerun as the tape grows.
