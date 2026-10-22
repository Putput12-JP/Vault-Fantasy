# Opening night checklist (NBA 2026-27, first tip Tue 2026-10-20)

Nothing here needs a switch thrown. Preseason holds read each game's own `season_type`, so regular-season games (type 2)
are priced as soon as they are on the board. This list is for confirming that, in order.

## Mon night and 1 hour before the first tip
1. `python3 nba/scripts/check_board.py` (read-only, reads the live board).
   - board age under about 15 min; games and props both above 0
   - venues: `Draft Kings`, `Kalshi`, `Polymarket` and at least one pick'em app posting
   - `core stats all present`; note any `labels skipped`
   - `unmapped` counts for Kalshi and Pinnacle are mostly games beyond the 72-hour board, not a fault. A count that grows for a game that IS on the board is.
2. `gh run list --workflow=nba-snapshots.yml --limit 5` and `--workflow=watch-recorder.yml`: recent runs succeeded, no open data-failure issue.
3. Injuries and lineups: the first real report arrives Oct 19-20 (`injuries` was empty on every poll except 10-07). `lineups` returns 403 until about 11:00 UTC each morning; that is "not posted yet", and `scripts/watch_recorder_health.py` already ignores it.
4. SmartStake tape (local, internal only): `tail ~/Library/Logs/smartstake-record.log`, last NBA pass under 20 minutes old.

## What to expect, and what is not a fault
- Expect "stale" chips on Data Health for `game_model.json`, `minutes_model.json` and `usage_cascade.json` this week. They are manual refits (`build_game_model.py`, `build_minutes_model.py`, `build_usage_cascade.py`) and nothing new has been fed to them since the season ended in June. The Vault line deliberately keeps last season's ratings for the first 28 days. Refit after the first week of box scores.
- sportsdataverse's 2026-27 box files (`player_box_2027.csv`) 404 until its nightly build catches up. Game logs, minutes state and the pace/defense state lag until it appears. Shadow bets and Minutes Lab settle from ESPN box scores (`ledger.py`), so they are not affected. Check with `curl -I https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_player_boxscores/player_box_2027.csv`.
- A source that has not answered for 30 minutes holds the props it quoted (`pricing.py` `STALE_SRC_S`). A one-off PrizePicks or Underdog 403 is normal.
- Props for a game that has tipped are hidden from the Props board (the subtitle says how many).

## Oct 21 cleanup (roadmap item 3)
Remove `OPENER_PASS_END` in `snapshot.py` and the early-lines code (`Slate.opening`, `OPEN_CACHE`, `prop_board.opening`, the `B.opening` merge in `renderSlate`).
