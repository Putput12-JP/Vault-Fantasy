#!/usr/bin/env python3
"""
Current state of prop model v2 for the page: what the stacker's features read, as of the last final game.

Walks every game from WARM_FROM through today with exactly the updates build_prop_model_v2.py uses
(update_after), then exports, for the teams and rostered players:
  teams    pace and scoring (EWMA), last game time (back-to-backs), defense factor by position group x stat
  players  minutes volatility, shooting-built points and 3PM per minute, season-to-date sums
Also a snapshot taken just before the example board's game (data/prop_board.json), so the example is priced
with only what was known that morning.

  python3 nba/scripts/build_model_state.py
Writes data/model_state.json. Needs raw/hoopr for the seasons walked (fetch_hoopr.py).
"""
import copy, datetime as dt, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model_v2 as V2
from build_prop_model import BASE

DATA = os.path.join(C.HERE, '..', 'data')
WARM = 2          # seasons of history before the current one


def export(ctx, rt, ms, keep, season, base=False):
    teams = {}
    for t in set(ctx.pace) | set(ctx.pts):
        teams[t] = {'pace': round(ctx.pace.get(t, 0), 3), 'pts': round(ctx.pts.get(t, 0), 3),
                    'last': int(ctx.last[t].timestamp()) if t in ctx.last else None,
                    'def': {pos: {s: round(ctx.opp_factor(t, pos, s), 4) for s in BASE} for pos in ('G', 'F', 'C')}}
    players = {}
    for aid in keep:
        sr = ctx.struct_rates(aid)
        z = ctx.szn.get(aid)
        players[aid] = {'sdm': round((ctx.vol.get(aid, 36.0)) ** 0.5, 3),
                        # example only: minutes (EWMA) and rates that morning, the example's base (live uses the Minutes Lab)
                        'min': round(ms.pl[aid]['m'], 1) if base and aid in ms.pl else None,
                        'rate': {s: round(rt[aid]['rate'][s], 5) for s in BASE} if base and aid in rt else None,
                        'sr': [round(sr[0], 5), round(sr[1], 5)] if sr else None,
                        'szn': {'season': z['season'], 'M': round(z['M'], 1), 'S': {s: round(z['S'][s], 1) for s in BASE}} if z and z['M'] else None}
    return {'season': season, 'lg_pace': round(ctx.lg_pace or 0, 3), 'teams': teams, 'players': players}


def main():
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    cur = int(proj['season'][:4]) + 1
    seasons = [s for s in range(cur - WARM, cur + 1) if os.path.exists(os.path.join(C.RAW, 'hoopr', f'player_box_{s}.csv'))]
    keep = {p['id'] for t in proj['teams'].values() for p in t['players']}
    ex_gid = None
    pb = os.path.join(DATA, 'prop_board.json')
    if os.path.exists(pb):
        ex = (json.load(open(pb)).get('example') or {}).get('games') or []
        ex_gid = int(ex[0]['id']) if ex else None
    box = C.player_games(seasons)
    ms, ctx, rt = MM.State(json.load(open(MM.OUT_JSON))['alpha']), V2.Context(), {}
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    example, last_day, n = None, None, 0
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['game_id'] == ex_gid:
            example = export(ctx, rt, ms, keep, g['season'], base=True)
            example['asof'] = g['tip_et'].strftime('%Y-%m-%d')
        V2.update_after(g, rows, rt, prior, ms, ctx)
        last_day, n = g['tip_et'].strftime('%Y-%m-%d'), n + 1
    live = export(ctx, rt, ms, keep, cur)
    live['asof'] = last_day
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'seasons': seasons,
           'games': n, 'live': live, 'example': example}
    path = os.path.join(DATA, 'model_state.json')
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    print(f"walked {n:,} games {seasons}; state through {last_day}; example snapshot "
          f"{'as of ' + example['asof'] if example else 'none'} -> data/model_state.json ({os.path.getsize(path) // 1000} KB)")


if __name__ == '__main__':
    main()
