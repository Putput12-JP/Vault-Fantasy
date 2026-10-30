# Steam Chaser for NBA props: Phase 1 backtest (verdict NO-GO as scoped)

Run 2026-10-30 (Central). Idea, from upside.tools/steam-chaser: when a sharp reference book moves a prop, a slower book keeps the old price for a while; take it.
Code: `scripts/build_steam_pickem.py`, `scripts/build_steam_dk.py`, summaries in `scripts/analyze_steam_pickem.py` and `scripts/analyze_steam_dk.py` (rebuild from the `nba-data` branch, with `results/`).
Data: Oct 20 to 30 regular season. Pinnacle is a price reference only, never a place to bet. Nothing is estimated; a missing field in the stored series skips the row.

Event: a Pinnacle player prop (pts, reb, ast, 3pm, pra) whose line changed, or whose de-vigged over chance moved 2 points or more within 60 minutes (at most one event per prop per 60 minutes). The target quote is the app's or DraftKings' value at the event time. Stale = still on the old number. Play = the side Pinnacle moved toward. Pinnacle quotes are polled every 5 to 15 minutes, so the event time is when we first saw the move.

## Pick'em apps

| Target, move | Graded | Hit (95% range) | Needed |
|---|---|---|---|
| PrizePicks, price move | 752 | 54.8% (51.2 to 58.3) | 54.2% to 59.1% |
| PrizePicks, line move | 75 | 46.7% (35.8 to 57.8) | 54.2% to 59.1% |
| Underdog, price move | 1,079 | 52.1% (49.1 to 55.1) | ROI at its price -4.4% |
| Underdog, line move | 74 | 63.5% (52.1 to 73.6) | ROI at its price +6.1% |

Pinnacle's chance after the event moves a mean 0.0 to 0.4 points more by the close: the move is done by the time we see it. Half of stale PrizePicks lines caught up within 30 minutes; 37 of 78 never did.

## DraftKings (ESPN feed), price moves where DK is on Pinnacle's new line

| Group | Plays | Expected hit | Actual hit | ROI at DK price |
|---|---|---|---|---|
| All stale | 1,124 | 52.1% | 51.9% (z -0.16) | -2.9% |
| EV 2%+ vs Pinnacle fair | 203 | 54.5% | 47.3% (z -2.06) | -10.2% (train -10.1%, holdout -10.3%) |
| EV 4%+ | 85 | 55.1% | 42.4% (z -2.37) | -18.7% |
| EV 0 to 2% | 162 | 53.3% | 40.7% (z -3.21) | -22.8% |
| EV below 0 (DK already past Pinnacle) | 759 | 51.2% | 55.5% (z +2.35) | +3.3% |

Line moves with DK still on the old line: 55 plays, 41.8% hit, ROI -24.5%. DK's catch-up median is about 30 minutes (15 minutes for EV 6%+), so our poll interval can see it. The "positive CLV vs Pinnacle close" (+2.6% at EV 2%+) is the entry edge restated, since Pinnacle barely moves after the event.

## Verdict

NO-GO. The plays that look +EV against Pinnacle lose, and DK's disagreement with Pinnacle is the more informative price. No change to any page, model or tracked record.

**Flag for close monitoring** (improving records, small or post-hoc): DK already moved past Pinnacle, +3.3% ROI, 759 plays, a slice cut after seeing results, so a hypothesis only; Underdog line moves, +6.1% ROI, 74 plays, holdout 9 legs.

## Limits and what would reopen it

- One reference. Steam Chaser uses up to six (Circa, FanDuel, 4Cx, Bet105, Pinnacle, PropBuilder) and an agreement count; Pinnacle's prop limits are low, so its moves may be noisy.
- 11 days, poll-resolution timing.
- Reopen with several sharp references for NBA props (agreement count), then retest the same events on DK and a priced soft book.
