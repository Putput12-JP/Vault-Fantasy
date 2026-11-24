# Main line: the Action Network books vote (2026-11-24)

## What was wrong

The Props page showed Bam Adebayo assists as **Over 1.5, Polymarket -646**. FanDuel (+108 / -144) and Fanatics (+100 / -130) both had the prop,
at 3.5. Nobody posted 1.5. The page had picked a Polymarket rung with $6 of depth behind it.

Two causes, both in how a prop's headline line is chosen (`priceRow` on the page, `prop_sim_record.main_line` in the recorders, the same rule):

1. **The Action Network books were ignored.** FanDuel, BetMGM, BetRivers, bet365, Caesars and Fanatics are stored in `e['shop']`, beside `e['books']`
   (DraftKings, Pinnacle, Polymarket). `scripts/prop_board.py` keeps them out of `books` on purpose: the consensus, the market-implied mean and the
   prop close all read `books`, and six soft books there would move every one of them. The headline-line rule read `books` only. A prop only the shop books
   posted took a pick'em line, or Polymarket's rung, or Kalshi's, or **no line at all** (the row was hidden on the page and never recorded).
2. **A rung with no bid on the under looked "nearest even".** Polymarket's under on such a rung is the clamp (-10421), so its no-vig chance was
   made up and always read below 50%: the rung with the most likely over won the fallback.

## The rule now

* `e['books']` (not Polymarket) and `e['shop']` all vote on the line. Ties go to the line Pinnacle posts, then a line with a two-sided price, then the
  lower line, as before.
* The price at that line is the books' no-vig chance, as before. Only when none of `e['books']` posts the line does it come from `e['shop']`. The consensus
  and the prop close are unchanged: they still never read `shop`. `lean_record.best_price` likewise reads `shop` only when `books` has no price at the line,
  so a price a record already held is never replaced by a better one from a soft book.
* Polymarket alone: the rung whose over price sits nearest even; a one-sided rung shows no market chance (its fair is the model's alone).
* The page prices the shop books like any book: they show in the Sportsbooks table, can be the best price, and carry an edge. Gates are unchanged (every
  non-Kalshi venue is NO-GO), so nothing new is a bet.

## Not changed on purpose

* The consensus (`quotesOf`, `consensus.py`), the prop close (`ledger.close_log`), Combo Check (`ccQuotes`) and the shadow ledger's candidates still read
  `books` only. Moving them is a consensus change and needs its own test.
* Polymarket one-sided rungs elsewhere on the page still carry a fair built from the clamped under. Their edges read low, never high. Separate fix.

## History

`scripts/repair_shop_lines.py` rebuilds each stored poll from stored prices (`replay_polls`, which now also reads the stored Action Network props) and runs
the recorder under the old and the new rule on the same board. Only rows where the two differ, and where the old rule reproduces the stored row, change.
Props that had no stored row are not inserted: the recorder's mean for them was never stored. 2026-11-11 stored no Action Network props and cannot change;
nothing before 2026-11-03 can.

Dry run on a copy of the `nba-data` branch, 2026-11-03 to 2026-11-23 (the repair is not applied to the branch yet). No row is added or removed, so every
sample size is unchanged; what moves is the line, and how many rows carry a market price (priced props 7,147 to 7,213):

| Record (2026-11-04 on) | n | Old | New |
|---|---|---|---|
| Biggest gap picks, W-L (D = did not play) | 147 to 148 | 73-74, 4 D, 49.7% | 75-73, 3 D, 50.7% |
| Leans, close clock, not held | 14,458 to 14,459 | 7,546-6,912, 52.2% | 7,487-6,972, 51.8% |
| Leans, first clock, not held | 14,457 to 14,459 | 7,650-6,807, 52.9% | 7,711-6,748, 53.3% |
| Leans, close clock, held | 1,926 | 1,058-868, 54.9% | 1,044-882, 54.2% |
| Leans, first clock, held | 1,926 | 1,074-852, 55.8% | 1,085-841, 56.3% |
| Props Sim log loss, market (priced) | 7,147 to 7,213 | 0.6851 | 0.6837 |
| Props Sim log loss, model (priced) | 7,147 to 7,213 | 0.6914 | 0.6905 |

Every move is a different line on the same props, not a different model. The Biggest gap move is two picks; the lean moves are under half a point.
