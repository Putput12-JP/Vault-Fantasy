# Sharp Money V2: strict gates (price 50%+, under 48 hours)

Date: 2026-10-26. Data: `sharp-data/v2_plays.json` as of this date (222 live plays, 204 settled), kept as `tests/fixtures/sharp_v2/v2_plays_2026-10-26.json`. Every number below is a stored price, a stored result or a stored closing-line value. Nothing is estimated.

## The two gates

A Play now also needs:

1. **A price of 50% or better** (`GATES.MIN_PRICE`). A price under 50% is plus money. The stored price is the book's implied chance, vig included.
2. **A game under 48 hours away** (`GATES.EARLY_H`). Measured at first sight, the way the ledger stores it (`start - firstSeen`).

A candidate that fails either is a Pass, with the reason on the card, and is logged to `v2_passed.json` from now on. Rules live in `sharp-money/v2/gates.js`, the one copy the page and the ledger both run.

## Why these two

Slices of the 204 settled live plays, chronological split (first 60% = 122 plays, last 40% = 82 held out). The rules were fixed from the whole-sample slice, then checked on the held-out part.

| Slice removed | All | First 60% | Held out 40% |
|---|---|---|---|
| 48h+ out | 18-27 (40.0%), ROI -21.7%, n=45 | 11-17, -20.8%, n=28 | 7-10, -23.1%, n=17 |
| Price under 50% | 24-41 (36.9%), ROI -16.5%, n=65 | 13-27, -25.5%, n=40 | 11-14, -2.2%, n=25 |

- **48h+ has a second sample behind it.** `gates.js` already carried it as a caution from the earlier evidence PR: 110-159, ROI -16.3% on 269 settled. Same direction, same size.
- **Price under 50% has one sample.** On the held-out part those plays were close to break-even (-2.2%), so this gate raises the win rate more than it raises ROI: plus-money plays win less often by construction. Treat it as the weaker of the two.
- No rule reaches the 100 held-out decisions that `docs/signal-research.md` asks before a rule is trusted. Both are flagged for close monitoring below.

Looked at and not used: NFL overs (18-26, but held-out 11-13 at -7.4%), single sportsbooks (bet365 12-19), single prop markets, edge size and reference gap (non-monotone), CLV sign (only known after the game).

## Old and new record

Live ledger, settled plays, flat 1 unit at the stored price.

| | Old gates | Strict gates | Held back |
|---|---|---|---|
| Record | 108-96 (52.9%) | **70-42 (62.5%)** | 38-54 (41.3%) |
| Units / ROI | +1.8u / +0.9% | +14.4u / +12.9% | -12.6u / -13.7% |
| ROI without top 5 wins | -3.2% | +8.8% | -23.9% |
| CLV vs exchange close | +3.8% (208) | +2.8% (112) | +5.0% (96) |
| Plays logged / open | 222 / 14 | 116 / 2 | 106 / 12 |
| NFL | 57-48, +5.6% | 30-13 (69.8%), +27.5% | |
| NBA | 49-45, -3.3% | 40-29 (58.0%), +3.7% | |

Official record on the page (live plus 17 backfilled): **119-102 (+6.7u)** becomes **74-44 (+16.1u)**. The backfilled part goes from 11-6 (+5.0u) to 4-2 (+1.7u).

## Flagged for close monitoring

| Record that improved | Sample | Caveat |
|---|---|---|
| All strict plays, 70-42 | 112 settled | Rules were found on this same data. The held-out 40% alone is 30-15 (n=45). |
| NFL strict plays, 30-13 | 43 settled | One season of NFL, mostly unders. |
| NBA strict plays, 40-29 | 69 settled | ROI without the top 5 wins is -3.7%. The gain is not yet broad. |
| Backfilled strict plays, 4-2 | 6 settled | Chosen with hindsight on the exchange close. Do not read. |

CLV on the kept plays is lower (+2.8% against +3.8%): the held-back plays beat the close more but lost more often. CLV alone did not pick the winners here.

## What changed in the data

- `sharp-money/v2/gates.js`: `MIN_PRICE`, `held()` (judges a live candidate), `heldBack()` (re-scores a stored row from `first.price.p` and `start - firstSeen`, or `hoursEarly` on a backfilled row).
- **Live ledger is not edited.** `v2_plays.json` keeps all 222 rows: the first-sight record is frozen, and `scripts/snapshot_sharp_ledgers.py` refuses a vanished id. The 106 rows that fail a gate are re-scored out of the Play record and into the Passed record on read, by every page and by `summary()` in the tracker.
- `data/v2_backfill.json`: 11 of the 17 backfilled plays moved to `passed` by `scripts/retier_v2_backfill.py` (ids listed under `retiered`). `backfill_v2_props.py` and `backfill_v2_slate.py` apply the same gates on a rebuild.

## Limits

- **Early plays that later come inside 48 hours are not re-logged.** A pick first seen 48h+ out is logged as a Pass from now on, and as a Play when it is first seen inside the window. The 12 open plays already in `v2_plays.json` that fail the early gate keep their old first-sight price and are not re-logged, because the id is the pick and first sight is frozen. The re-scored record counts them as held back, so it can miss a play that would have been logged later at another price. A later price is not stored, so it is not invented here.
- 106 stored plays include 12 open and 2 void; the old-versus-new W-L above counts settled only.
- No gate was added for NBA specifically. NBA props still carry the caution that the gates are not tuned to NBA.
