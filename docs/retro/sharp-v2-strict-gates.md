# Sharp Money V2: strict gates (price 55%+, under 48 hours)

Date: 2026-10-26. Data: `sharp-data/v2_plays.json` as of this date (222 live plays, 204 settled), kept as `tests/fixtures/sharp_v2/v2_plays_2026-10-26.json`. Every number below is a stored price, a stored result or a stored closing-line value. Nothing is estimated.

## The two gates

A Play now also needs:

1. **A price of 55% or better** (`GATES.MIN_PRICE`). The stored price is the book's implied chance, vig included. The first version of this PR used 50% (no plus money); it was raised to 55% after the price scan below.
2. **A game under 48 hours away** (`GATES.EARLY_H`). Measured at first sight, the way the ledger stores it (`start - firstSeen`).

A candidate that fails either is a Pass, with the reason on the card, and is logged to `v2_passed.json` from now on. Rules live in `sharp-money/v2/gates.js`, the one copy the page and the ledger both run. NBA props are held to the same gates: they stay in Plays.

## Why these two

Chronological split of the 204 settled live plays (first 60% = 122 plays, last 40% = 82 held out).

| Slice removed | All | First 60% | Held out 40% |
|---|---|---|---|
| 48h+ out | 18-27 (40.0%), ROI -21.7%, n=45 | 11-17, -20.8%, n=28 | 7-10, -23.1%, n=17 |
| Price under 55% (any hours) | 67-79 (45.9%), ROI -6.4%, n=146 | | |

- **48h+ has a second sample behind it.** `gates.js` already carried it as a caution from the earlier evidence PR: 110-159, ROI -16.3% on 269 settled. Same direction, same size.
- **Price is a gradient, not a cliff.** ROI at flat 1 unit by price on the 204 live plays: under 40% n=12 (3-9), 40-45% +9.3% (n=19), 45-50% -25.9% (n=34), 50-55% +1.8% (n=81), 55-60% +16.2% (n=39), 60-65% +24.2% (n=18).
- **It repeats on plays the rule was not fitted on.** The Watch ledger (one reference only, 767 settled) goes -7.5% at 50-55% and +5.8% at 55-60% (n=98). The Passed ledger (failed another gate, 802 settled) goes +2.4% at 50-55% and +13.0% at 55-60% (n=87). Inside 48 hours, Passed and Watch NBA props priced 55-65% went 108-72 (60.0%), ROI +3.5%, against -6.7% at 50-55% and -22.9% under 50%. The effect outside Plays is smaller, so expect forward ROI well under the in-sample number. The 60-65% band in Passed (n=38) broke the pattern at -11.0%.
- **Edge size does not predict wins.** Plays with an edge under 3% went 37-21 (+14.4%) inside the strict set. The model's own tracked NBA bets (4,561, `nba-data` branch) lose 6% to 10% in every edge band, including the 3-5% and 8-12% ones; the model's GO gate is -8.8%.
- No rule reaches the 100 held-out decisions that `docs/signal-research.md` asks before a rule is trusted. The 55% line was chosen after seeing the price gradient. All records below are flagged for monitoring.

Looked at and not used: Pinnacle and exchange within 1 point (63 plays, 43-20, but it did not repeat on the 92 plays the gates already held back: 20-28 against 18-26), NFL overs, single sportsbooks, single prop markets, NBA model agreement (20-19 when the model also had a 3%+ edge on the same side, 22-20 when it had none), CLV sign (only known after the game).

## Old and new record

Live ledger, settled plays, flat 1 unit at the stored price. "Old gates" is `main`; "50% floor" is the first version of this PR.

| | Old gates | 50% floor | **55% floor (this PR)** | Held back by 55% |
|---|---|---|---|---|
| Record | 108-96 (52.9%) | 70-42 (62.5%) | **33-11 (75.0%)** | 75-85 (46.9%) |
| Units / ROI | +1.8u / +0.9% | +14.4u / +12.9% | **+11.2u / +25.5%** | -9.5u / -5.9% |
| ROI without top 5 wins | -3.2% | +8.8% | **+18.7%** | -11.4% |
| CLV vs exchange close | +3.8% (208) | +2.8% (112) | +2.0% (45) | +4.3% (163) |
| Plays logged / open | 222 / 14 | 116 / 2 | 46 / 1 | 176 / 13 |
| NFL | 57-48, +5.6% | 30-13, +27.5% | 12-4 (75.0%), +27.0% | |
| NBA | 49-45, -3.3% | 40-29, +3.7% | 21-7 (75.0%), +24.7% | |
| NBA props only | 45-40, -1.5% | 37-29, +0.9% | 19-7 (73.1%), +22.6% | |

Official record on the page (live plus backfilled): **119-102 (+6.7u)** to **33-12 (+10.2u, ROI +22.8%, +15.7% without the top 5 wins)**. The backfilled part goes from 17 plays (11-6, +5.0u) to 1 play (0-1, -1.0u).

## Flagged for close monitoring

| Record that improved | Sample (settled) | Caveat |
|---|---|---|
| All 55%+ plays, 33-11 | 44 | Threshold chosen on the same data. Last 40% alone is 14-3 (n=17); first 60% is 19-8 (n=27). |
| NBA 55%+, 21-7 | 28 (props 19-7, n=26) | ROI without the top 5 wins is +13.0% (props +9.2%). NBA season is 6 days old and its gates were never tuned on NBA. |
| NFL 55%+, 12-4 | 16 | ROI without the top 5 wins is +5.1%. |
| 50% floor version, 70-42 | 112 | Replaced by the 55% floor. The 50-55% band it contained went 37-31 (+4.7%, n=68), positive but not enough to keep it in Plays. |
| Backfilled 55%+, 0-1 | 1 | Nothing to read. |

CLV on the kept plays is lower (+2.0% against +3.8%): the held-back plays beat the close more but lost more often. CLV alone did not pick the winners here. Re-check at 100 settled 55%+ plays (44 now), and on forward-only plays, which the rule has not seen.

## What changed in the data

- `sharp-money/v2/gates.js`: `MIN_PRICE` 0.55; `EARLY_H` 48 is now a gate (it was a caution); `held()` judges a live candidate, `heldBack()` re-scores a stored row from `first.price.p` and `start - firstSeen` (or `hoursEarly` on a backfilled row).
- **Live ledger is not edited.** `v2_plays.json` keeps all 222 rows: the first-sight record is frozen, and `scripts/snapshot_sharp_ledgers.py` refuses a vanished id. The 176 rows that fail a gate are re-scored out of the Play record and into the Passed record on read, by every page and by `summary()` in the tracker.
- `data/v2_backfill.json`: 16 of the 17 backfilled plays moved to `passed` by `scripts/retier_v2_backfill.py` (11 at the 50% floor, 5 more at 55%; ids listed under `retiered`). `backfill_v2_props.py` and `backfill_v2_slate.py` apply the same gates on a rebuild.
- Tests: `tests/v2_strict_gates.test.mjs` re-scores the stored ledger (33-11 kept, 75-85 held back). NBA test boards moved to prices above 55% so the NBA gates still have plays to judge.

## Limits

- **Early plays that later come inside 48 hours are not re-logged.** A pick first seen 48h+ out is logged as a Pass from now on, and as a Play when it is first seen inside the window. The open plays already in `v2_plays.json` that fail a gate keep their old first-sight price and are not re-logged, because the id is the pick and first sight is frozen. A later price is not stored, so it is not invented here.
- 176 held-back plays include 13 open and 3 void; W-L above counts settled only.
- Fewer plays: 46 logged over 9 days, most of them weekend NFL and NBA nights. The Plays tab will often be empty.
