# Vault NBA: what is next

Updated 2026-10-08. Ordered by what protects the most first.

## Done this round
- Page size 13.6MB to 7.1MB (headshots as palette PNGs, `scripts/png_shrink.py`), so the 16MB artifact limit is no longer close.
- Opening-night tooling: `scripts/check_board.py` (one-screen board health) and a "labels not mapped" record on every board, so a
  stat a venue names differently shows up instead of vanishing. The opening-night check task (Oct 21) now runs both.

## Before opening night (Oct 20)
1. Run `check_board.py` the hour before the first tip. Looking for: sportsbook prop lines at all (preseason had none; ESPN sent
   only "Milestones" ladders), Pinnacle player props, and which of the 12 extra markets arrive and under which labels.
2. If ESPN still sends only milestone ladders: map them (over-only rungs) as a ladder source, since books would otherwise give the
   page no two-way prop prices.
3. After Oct 20 only: remove the one-time early-lines code (`OPENER_PASS_END` in snapshot.py, `Slate.opening`, `OPEN_CACHE`,
   `prop_board.opening`, the `B.opening` merge in renderSlate).

## Features, in order
4. **Game Lines in the regular season.** A slim Vault-line row (the gap to the market) and "best price" that skips stale books.
5. **Pick'em of the night** and a **weekly recap** (Tonight / Profile). Quick, and what a player opens the app for.
6. **Double-doubles and triple-doubles.** The chance is a small calculation from the existing projections (P(at least two of five
   stats reach 10)). Needs a real feed to show a price; the recorder reads only over/under shapes today.
7. **Minutes Lab follow-ups.** Slider on bench rows; Out back on phone bench rows; soften the "over 240" status on game days.
8. **Profile badges.** More streak and "Locked in" style badges for logged bets.

## Tests already scheduled (nothing to do until then)
- Nov 9: copula A2 first look. Nov 16: minutes B3 holdout. Nov 20: v3 minutes shadow review.
- Nov 23: edge tests round 2, tests 1 and 2 (`docs/edge-tests-r2.md`). Test 3 (alt-line tails) is done: NO-GO.

## Housekeeping
- The notes index (`MEMORY.md`) is over its size limit and older lines are being cut. Tidy it: one line per note, under about 200
  characters, detail in the topic files.
- Accent colour for the app is still undecided (orange, lime or cyan were the candidates).
