# NFL news-timing tape

Question it answers: **does the market price injury and QB news before it is public, or after?** If the line moves first, news is already in the close. If it moves after, there may be something to trade, and a model that reads news faster has an edge. Until now nothing recorded *when* a status changed.

## What is recorded
- `data/game_line_history.json` (already existed, hourly): per game, the `open` snapshot, every later move with a timestamp, and the last pre-kick sample, which is the closing-line proxy.
- `data/nfl_news_tape.jsonl` (new, hourly, append-only): one row per change in
  - a player's injury status (Sleeper: Questionable, Doubtful, Out, IR, PUP and so on),
  - a QB's depth-chart order,
  - the game model's "established QB is out or benched" flag (`data/qb_status.json`).
- `data/nfl_news_state.json` (new): the last seen state, so the next run can diff.

Row shape:
```
{ts, kind: injury|depth|qb_status, baseline, team, pid, name, pos, depth, from, to, body,
 game:{key, opp, home, commence, hours_to_kick}, line:{spread, total, open_spread, ts}}
```
`spread` is the HOME spread, negative = home favored, the same as `game_line_history`. `baseline: true` marks the first run, which writes everyone currently listed so later changes have a `from`; leave those out of timing tests.

## How to test it later (join, do not re-derive)
1. Take non-baseline rows for starters (QB, or `depth` 1) going to `Out` or `Doubtful`.
2. Line at the news = `line.spread`. Line one hour later, 24 hours later and at close come from the `samples` of `game.key` in `game_line_history.json`. Join on `game.commence` and the teams, because the week inside the feed key can lag.
3. Move after the news = later spread minus `line.spread`, signed toward the team that lost the player. If most of the move comes after `ts`, the market is slow. If the line had already moved before `ts`, the news was already priced. Report n for every bucket.

Known limits: resolution is the hourly run; Sleeper's status can itself lag the team report; a player's status can change twice between runs and only the later one is seen.
