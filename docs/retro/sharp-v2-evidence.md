# Sharp Money V2: what the stored record says (evidence PR)

Date: 2026-10-18. Free data only: `data.json` and `prop_plays.json` from the `sharp-data` branch (graded 2026-10-10 to 2026-10-18, so about 8 days).
Rerun: `python3 scripts/research/sharp_v2_evidence.py` (writes `docs/sharp-v2-evidence.json`, prints every slice).

Scored with the same rule as `docs/signal-research.md`: chronological split by kickoff (first 60% train, last 40% held out), and a slice earns a place
only if the held-out rows clear `scripts/research/common.py: verdict` (100+ decisions, beats the logged fair probability at z of 1.64 or more, ROI at the stored
price positive, stored CLV positive). Nothing is estimated. ROI uses a stored price, CLV uses a stored closing value.

**This PR changes no tracking, no stored number and no UI.** It is the evidence that decides what V2 is allowed to rank. The one tracking fix it
calls for (an independent prop close) is a separate data PR that will re-grade history.

## Result in one paragraph

No slice of either record clears the admission rule. The Top Reads are a coin flip (283-273, 50.9%) that closes about one point worse than the market
price (CLV -0.9%), and its positive unit total is five long shots (take away the top 10 winners and it is -3.6u). Agreement between signals does not help:
two signals agreeing did worse than one. The prop board loses 6.4% (549-635) while its stored CLV reads +2.8%, and the audit below shows why: the prop CLV
is measured against the same Pinnacle fair price that raised the call, so it mostly repeats the edge the call claimed. The Pinnacle prop fair also
overstates win chance by 4.4 points (z -3.0). Both findings point the same way for V2: rank by an independent price test, not by agree counts or displayed EV.

## 1. Top Reads (560 graded bet-signal picks)

| Slice | W-L | Win % | ROI at stored price | CLV | Held-out decisions | Verdict |
|---|---|---|---|---|---|---|
| All | 283-273 | 50.9% | +11.6% (n=214) | -0.9% (n=421) | 269 | Leave out |
| 1 signal | 237-220 | 51.9% | +13.4% (n=171) | -0.8% (n=334) | 183 | Leave out |
| 2 signals agree | 42-51 | 45.2% | -0.1% (n=37) | -1.3% (n=81) | 47 | Leave out |
| 3 signals agree | 4-2 | 66.7% | +34.6% (n=6) | -0.3% (n=6) | 3 | Leave out (6 games) |
| Line | 148-102 | 59.2% | +16.2% (n=61) | -0.7% (n=191) | 100 | Leave out |
| Money vs bets | 54-75 | 41.9% | +33.1% (n=53) | -0.1% (n=76) | 53 | Leave out |
| Behind (+EV at a book) | 35-43 | 44.9% | -7.9% (n=57) | -1.7% (n=67) | 34 | Leave out |
| Line + money | 18-29 | 38.3% | -58.3% (n=9) | -0.7% (n=41) | 21 | Leave out |
| Both sides flagged on the game | 135-138 | 49.5% | +4.8% (n=126) | -1.4% (n=226) | 117 | Leave out |
| One side only | 148-135 | 52.3% | +21.4% (n=88) | -0.2% (n=195) | 114 | Leave out |
| Sharp-only reads (context, never a pick) | 48-48 | 50.0% | -22.7% (n=20) | -1.0% (n=57) | 43 | Leave out |

**The unit total is long-shot luck.** Stored units exist on 217 of 560 graded picks (39%). The total is +24.9u, but the single best win is +7.2u (a +721
college moneyline) and the five best wins are +18.4u. Without the top 5 it is +6.5u, without the top 10 it is -3.6u. The "money" kind shows +33% ROI on
53 priced picks while winning 41.9% of 129: that is long shots, not skill.

**Contradictions.** 49% of graded picks are on a game where the tool flagged both sides of the same market. Those picks carry CLV of -1.4%.

**Flag for close monitoring (records that look good, small samples):**

- Line kind: 148-102 (59.2%), 250 graded, but CLV is negative (-0.7%, n=191). Wins at a price worse than the close.
- NFL picks: 57-39 (59.4%), 96 graded, CLV +0.3% (n=90). The only sport with positive CLV; 22 priced.
- Behind + line: 23-17 (57.5%), 40 graded, CLV -2.0%.

## 2. Prop board calls (1,184 graded)

| Slice | W-L | Win % | ROI | CLV (stored) | Held-out decisions | Verdict |
|---|---|---|---|---|---|---|
| All | 549-635 | 46.4% | -6.4% | +2.8% | 521 | Leave out |
| Displayed EV under 5% | 333-406 | 45.1% | -9.3% | +2.1% | 312 | Leave out |
| Displayed EV 5 to 10% | 195-197 | 49.7% | +0.3% | +3.2% | 162 | Leave out |
| Displayed EV 10 to 15% | 17-28 | 37.8% | -24.0% | +6.5% | 24 | Leave out |
| Displayed EV 15%+ | 4-4 | 50.0% | +35.9% | +23.7% | 4 | Leave out |
| Called 48h+ before kickoff | 110-159 | 40.9% | -16.3% | +2.3% | 188 | Leave out |
| Called 12 to 48h | 241-269 | 47.3% | -6.4% | +2.3% | 209 | Leave out |
| Called 2 to 12h | 121-118 | 50.6% | +3.9% | +3.2% | 102 | Leave out (flag) |
| Called under 2h | 77-89 | 46.4% | -5.4% | +4.3% | 79 | Leave out |
| Price at a book | 159-158 | 50.2% | -1.6% | +4.2% | 131 | Leave out |
| Price at an exchange | 390-477 | 45.0% | -8.2% | +2.3% | 371 | Leave out |
| Fair from Pinnacle | 529-619 | 46.1% | -6.9% | +2.8% | 509 | Leave out |
| Fair from Kalshi | 20-16 | 55.6% | +9.9% | +3.0% | 15 | Leave out (flag, 36 calls) |
| Receptions (both sides) | 186-187 | 49.9% | +1.6% | +2.1% | 160 | Leave out (flag) |
| Rushing yards, unders | 31-24 | 56.4% | +14.7% | +3.4% | 24 | Leave out (flag, 55 calls) |
| Rushing yards, overs | 26-51 | 33.8% | -30.4% | +4.2% | 32 | Leave out |
| Receiving yards, unders | 74-95 | 43.8% | -14.0% | +3.1% | 76 | Leave out |
| QB props | 114-145 | 44.0% | -11.9% | +2.6% | 110 | Leave out |

Three things hold across the table. The displayed EV does not rank: the 10 to 15% bucket lost 24%. CLV is positive in every row, including the worst
ones (see section 3). And the early calls decay: lines called 48h out win 40.9%.

**Flag for close monitoring (records that look good, small samples):** called 2 to 12h out (239 calls, +3.9% ROI), fair from Kalshi (36 calls, +9.9%),
receptions (373 calls, +1.6%), rushing-yard unders (55 calls, +14.7%), rush-attempt unders (42 calls, +4.5%). None is near the 100-decision held-out bar.

## 3. Prop CLV audit: why +2.8% CLV sits beside -6.4% ROI

The tracker (`scripts/track-prop-plays.mjs`) stores `CLV = closeFair / calledPrice - 1`, where `closeFair` is the last fresh board fair for that
side before kickoff, taken from the same fair source that raised the call (Pinnacle for 97% of calls). So if the fair does not move, CLV equals the call's own edge.

| Quantity (1,184 graded calls) | Value |
|---|---|
| Mean price paid (probability) | 49.4% |
| Mean fair at the call | 51.9% |
| Mean fair at the close | 50.7% |
| Edge the calls claimed (fair / price - 1) | +5.1% |
| Stored CLV | +2.8% |
| Fair drift after the call | -1.1 probability points |
| Share of calls with CLV above zero | 77.9% |
| Hit rate | 46.4% |
| Hit rate minus mean close fair | -4.4 points (z -3.0) |
| Brier score: close fair / price paid / coin flip | 0.2455 / 0.2455 / 0.2500 |

Reading: CLV is mostly the claimed edge (+5.1%) less a 1.1 point drift against the calls (-2.3%). It cannot confirm the edge, because the thing it is
measured against is the thing that claimed it. The close fair does no better than the price paid (same Brier), and the calls won 4.4 points less often than
the close fair said. Calibration by close fair: the 0.45 to 0.50 bucket hit 41.8% (n=352), 0.50 to 0.55 hit 45.5% (n=420), 0.55 to 0.60 hit 61.7% (n=188).
Pinnacle prop limits are small and the outside research ranks Pinnacle among the softest prop references (SmartStake MLB study), so the reference, not luck
alone, is a likely cause. Two weeks cannot prove that, which is why section 4 sets the test.

## 4. What this means for V2

1. **The agree count and displayed EV do not rank anything in V2.** Neither is used to order plays. Signals are shown as a scorecard with records.
2. **Props get an independent close.** 616 of the 1,184 graded calls (52%) have a multi-book closing tape in `prop_close_tape.json` (Pinnacle on 614, an
   exchange on all 616, three or more books on 583). The data PR re-grades those calls against the exchange and book close and reports old and new CLV
   side by side. The remaining 568 calls predate the tape and stay labelled "self-referenced close".
3. **Test the reference.** The data PR walk-forward tests an exchange-weighted fair against Pinnacle on those 616 calls, under the admission rule.
   Adopted only if it passes; otherwise props stay without a "fair" claim.
4. **Contradictions are blocked.** A game with both sides of one market flagged gets no play (49% of graded picks today).
5. **Unit totals are shown with and without the biggest winners**, and only next to the share of picks that carry a stored price.
6. **Sharp-account money stays context only**, shown nowhere in a ranking or an agree count.
7. **Everything here is eight days.** V2 shows n on every number and keeps the trust / watch / ignore labels from the admission rule.

## Limits

- One short window (Oct 10 to Oct 18), mostly college football. The held-out halves are 50 to 500 decisions.
- Picks are correlated within a game and week, so the z values are generous.
- Stored price exists on 39% of picks. ROI is for those only.
- The CLV audit uses the board's own stored `closeFair`. Nothing was re-pulled from a book.
