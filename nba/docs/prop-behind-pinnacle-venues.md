# Prop prices behind Pinnacle at Polymarket, Novig and Kalshi (pre-registered)

Written 2026-10-26, before any `p_behind_x` alert was logged or graded. It extends `docs/prop-behind-pinnacle.md` to three more venues.
That document stays frozen: its test pool is DraftKings `p_behind` alerts only, and nothing here changes it, its thresholds or its
first look. The new alerts have their own type, `p_behind_x`, so the two results are never pooled.

## The signal

Same rule as `p_behind`, applied to each venue on its own: the venue prices the **same line** as Pinnacle, **3% or more (under 25%)**
better than Pinnacle's power-de-vigged no-vig fair, Pinnacle's line and prices unchanged for **20 minutes**, and Pinnacle plus the
venue's own source answered within **10 minutes**. One alert per venue, prop side and line; the first sighting wins. All thresholds are
frozen at the `p_behind` values.

| Venue | Price used | EV |
|---|---|---|
| Polymarket | Its row in the props board, already priced like a book with the taker fee in (American odds, -300 to +300) | fair x (1 + payout) - 1 |
| Kalshi | The rung at Pinnacle's own number (YES = over): Over costs the YES ask, Under costs 1 minus the YES bid, each plus Kalshi's fee (`kal_fee`), a chance between 0.25 and 0.75; the rung must have been quoted within 10 minutes | fair / cost - 1 |
| Novig | The ask for the side at Pinnacle's strike, a chance between 0.25 and 0.75 (the same range as -300/+300) | fair / ask - 1 |

Novig's price is taken as the ask shown. **No Novig fee is modeled**, because none is documented in our sources; if Novig charges one,
its EV is overstated by that amount, and the grade at the close carries the same error. Only props read in the latest Novig poll have a
ladder on the board, so a Novig quote is never older than the poll that read it.

**Not in the signal:** pick'em apps (payout multipliers, not straight prices) and alternate lines. Kalshi's heavy-money flag (`p_kal`) is a different signal and is unchanged.

## Grading and the rule

Graded exactly like `p_behind` (EV at Pinnacle's same-line close, drift, result and units at the venue's price). Each venue's pass
rule is the `p_behind` rule at its own **100 CLV-graded alerts**, counted per venue: Polymarket, Novig and Kalshi are tested separately and
none borrows the other's alerts or DraftKings'. Anything else is a NO-GO and the alerts stay on the page as labeled context.
Time-out 2026-12-31 as in the original. Context only: never part of a lean, a with/against count or an agree total.

## Known limits

- Polymarket and Novig prop books are thin: a quote may not be fillable at any size. Depth is not part of the rule.
- Pinnacle covers about a quarter of props, so alerts are rare; 100 per venue may not accrue by the time-out.
