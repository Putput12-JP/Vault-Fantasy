# NBA rule C: the fair prices agree and Kalshi quotes the line

Shipped Nov 3, 2026 (`sharp-money/v2/gates.js`, `GATES.NBA_FAIR_AGREE`, `GATES.NBA_FAIR_SINCE`). NBA props only. Games and NFL props keep the 55% price floor.

## The rule

An NBA prop is a Play when all of these hold at first sight:

- Pinnacle's fair price and the exchange fair price sit **under 1 point apart**. The old check allowed 4.
- **Kalshi is quoting the line**: a two-sided quote no wider than 6 points (`MAX_EXCH_SPREAD`).
- The price beats the exchange by **3% to 10%** (`GATES.NBA_MIN_EDGE`, added Nov 3, the same day). Pinnacle does not price the side the other way.
- The game is under 48 hours away.

There is **no 55% price floor** for NBA props. This rule's wins sit mostly at prices under 55%, which the floor threw away.

## How it was found

The search covered 1,958 settled NBA prop rows from the Plays, Watch and Passed ledgers, Oct 20 to Nov 2. Each row got features read from the recorder logs at or before its first sight: Kalshi and Novig quotes, DraftKings' open, exchange drift and injury news.

About 4,000 one- to three-condition rules were ranked on Oct 20-27 and checked once on Oct 28 - Nov 2. The top rules by early-days ROI collapsed on the later days, for example +23.9% to -6.1%. Only "the fairs agree within 1 point and Kalshi is quoting" held on both halves.

These dead ends showed nothing on the same data:

- the Vault model agreeing
- the 10k prop simulation
- DraftKings line or price moves since open
- exchange drift before first sight
- injury news in the prior 3 hours
- Novig being present

## The record, rebuilt from stored fields

`gates.heldBack()` re-scores the stored rows. `data/v2_nba_kalshi_reads.json` holds Kalshi's quote at first sight for rows logged before rows stored it; it is built by `scripts/build_v2_nba_kalshi_reads.py` from reads at or before first sight only.

| | Record | Units | ROI (±95%) | n |
|---|---|---|---|---|
| Price floor (55%+, under 48h), Plays ledger | 48-26 | +6.8u | +9.1% ±18.5 | 74 |
| **Rule C, Plays plus promoted Passed rows** | **69-45** | **+15.5u** | **+13.6% ±17.1** | **114** |
| Rule C, first seen before Oct 28 | 32-17 | +10.2u | +20.7% | 49 |
| Rule C, first seen Oct 28 on | 37-28 | +5.3u | +8.2% | 65 |
| Plays held back by rule C | 32-34 | -8.7u | -13.3% | 66 |
| Passed rows rule C promotes | 27-20 | +7.1u | +15.2% | 47 |

Rule C's record by price:

| Price | Record | ROI |
|---|---|---|
| Under 50% | 15-14 | +10.2% |
| 50-55% | 29-16 | +23.5% |
| 55-60% | 14-8 | +11.2% |
| 60% and up | 11-7 | -2.7% |

Rule C's record by gap between the two fair prices, with Kalshi quoting:

| Gap | Record | ROI |
|---|---|---|
| Under 1 point | 69-45 | +13.6% |
| 1 to 2 points | 25-41 | -29.9% |
| 2 to 4 points | 12-11 | +1.6% |

8 of 14 days were positive.

## Read this before trusting it

- **The whole rebuilt record is in-sample.** The rule was picked on these rows. The 95% range on ROI is ±17 points, so the true ROI could be near zero. The live record from `NBA_FAIR_SINCE` is the test.
- **The later half is weaker**, at +8.2% on 65 settled.
- **The 1-2 point gap losing 25-41 has no explanation.** A real effect should fall off smoothly with the gap. That bin is what makes the cut at 1 point look sharp. It is not explained by stat mix, Kalshi spread or a few games.
- A variant that also capped the price under 60% read +19.0%. It was not shipped because the cap was chosen after seeing the data.

## Where it shows

- **Play record.** Plays the rule holds back move to Passed. Passed NBA props it would have played count in the Play record. The note splits four lines:
  - held by the strict gates
  - held by rule C
  - added from Passed
  - the NBA prop record before rule C, then rule C rebuilt (in-sample) and rule C live
- **New rows** store `first.price.kal`.

## Edge floor of 3% (added Nov 3, same day)

Inside rule C, the edge over the exchange separated winners from break-even plays:

| Edge over the exchange | Record | Units | ROI (±95%) | n |
|---|---|---|---|---|
| 3% and up | 32-16 | +14.0u | +29.1% ±26 | 48 |
| 2% to 3% | 37-29 | +1.5u | +2.3% | 66 |
| 3% and up, Oct 20-27 | 12-4 | +6.7u | +41.8% | 16 |
| 3% and up, Oct 28 on | 20-12 | +7.3u | +22.7% | 32 |

**A daily cap does nothing by itself.** A random 5 plays a day kept the same ROI as all of rule C (median +14.3%). It was also not shippable: the top 5 of a night can't be known when a play is first seen.

**Read this before trusting it:**
- **This floor is in-sample too.** It was picked on the same rows after rule C itself.
- **It does not hold for every play type.** On NFL props with the same anchor gates, bigger edges did worse (5%+ went -9.2% on 31). On NBA props outside rule C, no edge bucket made money.
- **The edge quarters were not smooth:** +15%, +3%, -3%, +39%.

**Expect about 3 to 4 NBA prop plays a night.**
