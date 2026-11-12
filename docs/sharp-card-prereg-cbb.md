# Sharp side card, college basketball: pre-registered forward test

**Status: Registered.** Proposed on 2026-11-12 and approved by the user as written the same day (Nov 12, 2026, about 5:35 PM CT),
with every decision below taken as proposed. The commit that changes this line from PROPOSED is the registration: its hash and time
are the proof that the rule came first. Nothing below may change after the first college basketball (CBB) card frozen under it is
graded. A change means a new registration with its own date.

This does not change `docs/sharp-card-prereg.md`. That registration covers NBA, NFL and CFB, and is read exactly as written.

Sharp money is context only (CLAUDE.md). This test decides only whether a pick label may be *proposed* for the CBB side card. Passing
it does not add the card to Top Reads, SM_GATE or any agree total.

## What is the same as the NBA / NFL / CFB registration

Everything not listed under "What is different" is copied from `docs/sharp-card-prereg.md` as of commit `93f1de8854`
(2026-11-11 3:40 PM CT), word for word in meaning:

- **The lock:** the four press-ladder gates (60% money share above the $250 floor with excluded wallets left out; a wallet for the
  side with a sport book of n >= 15 pressing >= 1.5x; no proven wallet against; at least one proven wallet for).
- **Proven, loser, excluded, position, the $250 floor, the hedge collapse:** as defined in the header of
  `scripts/build_side_cards.py` and in `docs/side-cards.md`. "Sport book" means the wallet's CBB ledger rows only.
- **Variants:** A (all rows, primary) and B (forward rows, secondary), with the same "A passed; B does not support it" wording.
- **Which cards count:** built before game start, on a ledger run that finished before the cut, not a duplicate (earliest cut).
- **Bet, price, result:** moneyline headline, one lock per counted card per market group, Polymarket displayed price of the locked
  outcome at the cut, unpriced if missing or more than 30 minutes before the cut, unpriced over 10% of counted moneyline locks =
  data-quality failure with no verdict, flat 1 unit, the market's own Polymarket resolution, clean-ladder units as a second line.
- **Statistics:** 95% percentile bootstrap, 10,000 resamples, seed 20261111, resampling locks.
- **Reporting:** interim reports monthly and report-only; better-looking slices flagged for close monitoring with their n, never
  promoted on the same data.

## What is different for college basketball

1. **Start.** Only CBB cards whose cut is at or after **6:00 PM CT, Nov 12, 2026** (2026-11-13 00:00 UTC, epoch 1794528000) can
   count. That is after the registration commit. Cards cut earlier stay `counts: false` ("cut before this sport's registration").
   `scripts/build_side_cards.py` lists `cbb` in `REGISTERED_SPORTS` with that start in `REGISTERED_FROM`, in the same commit.
2. **No closing-line value.** `data/pm_closes.json` has no CBB games (on 2026-11-12 it holds NBA 207 and NFL 121). CBB is read on
   ROI only, like CFB, and its CLV is "not available". That is said here in advance.
3. **Final read and minimum n.**

   | Sport | Final read | Minimum n |
   |---|---|---|
   | CBB | the Monday after the 2027 men's national championship game | 300 |

4. **Ledger history.** CBB rows for wallets tracked before 2026-11-12 come from a one-time "fill" walk of each wallet's books
   (`scripts/build_pm_ledger.py`, `sports_read`). Those rows are graded the same way as any other row and are `backfill` or
   `forward` by the wallet's first-seen date, exactly as for the other sports. Variant A uses them; variant B keeps only `forward`.
   **Known limit:** the fill takes several nightly runs to reach every wallet (the ledger stops at its request cap), so early CBB
   cards see thinner wallet books than later ones. A card is built from whatever the ledger held at its cut; nothing is re-graded
   once the fill catches up.

## Decisions (approved as proposed, 2026-11-12)

Each was open in the proposal; the user approved the proposal as written, so each takes the proposed option.

- **A. Wallet universe.** Today CBB games add no wallets to the ledger universe (`UNIVERSE_SPORTS` in `build_pm_ledger.py`), so the
  NBA/NFL/CFB test keeps the universe it was registered on. CBB cards are therefore built only from wallets found through NBA, NFL
  and CFB games, the all-sports leaderboards, the benchmark's full list and Vault's NBA/NFL/CFB wallet files. Options:
  (1) keep it that way (proposed: no effect on the running test). **Approved.**
  (2) let CBB fat-ticket discovery, the benchmark's CBB board and `data/pm_wallets_cbb.json` add wallets. That finds CBB
  specialists, but those wallets would also appear on later NBA/NFL/CFB cards, which is a change to the population the existing test
  reads from that day on. If chosen, it needs its own note in the existing test's interim reports, with the date.
- **B. Minimum n.** 300 matches the other sports. CBB has far more games (Polymarket settled 652 CBB games from Nov 3 to Nov 10), so
  300 counted locks is reachable this season, unlike NFL and CFB. **Approved: 300.**
- **C. Read date.** The Monday after the national championship includes the tournament. A regular-season-only read would end on
  the Monday after Selection Sunday. **Approved: include the tournament.**
- **D. Thresholds borrowed from CFB.** The Sharp Money page's CBB alert thresholds are borrowed from CFB (see #417). They do not
  enter this test (the lock uses only the gates above). **Approved: they stay borrowed and out of the test.** Measuring them for CBB
  is separate page work.

## Known limits, stated before the data

Same as the existing registration (the ledger lags by a night, the cut is Polymarket's start time, money is mark value, holders
below $250 are not on the card, the API's 1,000-row page limit), plus:

- **Polymarket CBB markets are thin.** Measured 2026-11-12: median game moneyline volume $1,725 (CFB $28,471), taker trades of
  $5,000+ were 5 of 733 sampled. Many cards will hold no wallet above the $250 floor and produce no lock.
- **Team names.** Polymarket outcomes are joined to Vault's game by team name; a game that does not join still gets a card and a
  lock, only without Vault's key and logos.
