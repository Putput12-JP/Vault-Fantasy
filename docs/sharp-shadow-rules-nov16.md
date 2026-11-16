# Sharps shadow rules, registered 2026-11-16

Written on 2026-11-16 after an audit of the first 100 graded shown-size plays (games of Nov 12 to Nov 15). These are shadows. They do
not change the card, the suggested size, the pre-registered lock or either forward test (`docs/sharp-card-prereg.md`,
`docs/sharp-card-prereg-cbb.md`), and they never feed Top Reads, SM_GATE or an agree total. Sharp money is context only (CLAUDE.md).

## The rules

Each rule keeps the play the card shows (same side, same units, same price at the lock) only when it holds. Variant `all`.

| Play | Name on the Record page | Keeps the shown play when |
|---|---|---|
| `only` | Sharps only | at least 1 proven wallet is on the side and no proven wallet is on any other side of the market group |
| `two` | Two sharps | at least 2 proven wallets are on the side and none against |
| `seas` | Seasoned wallets | the same as `only`, counting a wallet as proven only when its sport book has 20 or more graded positions |
| (none) | Flat 1u | every shown play at 1 unit. Not a play row: the Record page multiplies the stored flat ROI by the play count |

"Proven" is the card's own definition (`scripts/build_side_cards.py`): sport book n >= 6, win rate >= 55%, dollar ROI > 3%.
`only` and `two` read the side's stored `counts`. `seas` reads the side's stored wallet `list`.

**Known gap:** a card lists at most 4 proven wallets per side, the largest by money. `seas` cannot see a seasoned wallet ranked
fifth or lower.

## Why these rules

All from the 100 graded plays. Every number is a stored price and a Polymarket result.

| Slice | Record | Shown units | n |
|---|---|---|---|
| All shown plays | 54-46 | -0.32u | 100 |
| No proven wallet on the side | 16-14 | +1.46u | 30 |
| CBB plays with no proven wallet on the side | 10-10 | +0.61u | 20 of 23 CBB plays |
| A proven wallet on another side | 12-15 | -8.57u | 27 |
| Best proven wallet on the side has under 20 graded positions | 1-5 | -6.12u | 6 |
| Plays above 1u | 14-13 | +1.62u on 63u staked | 27 |

## The in-sample backfill

The grader derives the three plays for every frozen card, so the history is covered. Those rows are **in-sample**: the rules were
chosen after seeing them. Each such row carries `in_sample: true` (card cut before 2026-11-16 12:00 AM Central), and the record
gives a `forward` line that leaves them out.

| Rule | In-sample record | Shown units | Flat ROI | n |
|---|---|---|---|---|
| Shown size (reference) | 54-46 | -0.32u | -3.4% | 100 |
| Sharps only | 26-19 | +4.79u | -0.8% | 45 |
| Two sharps | 12-8 | +3.85u | +0.3% | 20 |
| Seasoned wallets | 25-16 | +7.41u | +4.2% | 41 |
| Flat 1u | 54-46 | -3.39u | -3.4% | 100 |

By sport, in-sample:

| Rule | NFL | CFB | NBA | CBB |
|---|---|---|---|---|
| Shown size | 11-6, +7.15u | 18-23, -8.71u | 13-6, +0.70u | 12-11, +0.55u |
| Sharps only | 4-0, +6.20u | 12-15, -2.31u | 8-3, +0.97u | 2-1, -0.06u |
| Two sharps | 3-0, +5.10u | 4-5, +0.51u | 5-3, -1.76u | none |
| Seasoned wallets | 4-0, +6.20u | 12-14, -1.31u | 7-2, +0.58u | 2-0, +1.94u |

**Flagged for close monitoring (house rule): all three rules look better than the shown size, on samples of 20 to 45 plays that
they were fitted to. That is expected of any rule picked after the results and is not evidence.**

## How they are read

- Only the `forward` line counts. It starts at 0 plays.
- Per sport, never pooled, the same as the registered tests.
- No rule is promoted to the card on this data. A change to what the card shows is a decision made with the user, on the forward
  line, once it has a usable sample. As a guide, the registered tests ask for 300 moneyline locks per sport.
- A change to a rule is a new dated registration. The old one is still read as written.
