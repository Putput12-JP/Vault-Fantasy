#!/usr/bin/env python3
"""
Game logs for the Player Props page (hit rates at the line: L5 / L10 / L20 / season / head-to-head, and the
game-log chart). One compact row per game played, for every rostered player (data/player_projections.json).

  python3 nba/scripts/build_gamelogs.py [--seasons=2026,2027]
Reads raw/hoopr/player_box_<season>.csv (fetch_hoopr.py; the season is the year it ends: 2026 = 2025-26).
Writes data/gamelogs.json and re-renders the page.

Row: [day, season, opp, home, playoff, min, pts, reb, ast, 3pm, stl, blk, tov, fgm, fga, ftm, fta, tpa, oreb, dreb, pf]
  day      days since 1970-01-01 (the game date)      opp  index into `teams`
  playoff  1 for play-in / playoffs                   only games he played (minutes > 0)
Newest first, capped at MAX_GAMES per player.
"""
import csv, datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import render_app

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw', 'hoopr')
DATA = os.path.join(HERE, '..', 'data')
MAX_GAMES = 100
EPOCH = dt.date(1970, 1, 1)


def main(argv):
    args = dict(a.lstrip('-').split('=', 1) for a in argv if '=' in a)
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    cur = int(proj['season'][:4]) + 1                      # '2026-27' -> 2027
    seasons = [int(s) for s in args.get('seasons', f'{cur - 1},{cur}').split(',')]
    keep = {p['id'] for t in proj['teams'].values() for p in t['players']}
    teams, tix, logs = [], {}, {}
    for s in seasons:
        path = os.path.join(RAW, f'player_box_{s}.csv')
        if not os.path.exists(path):
            print(f'{s}: no box scores yet ({os.path.basename(path)})')
            continue
        n = 0
        for r in csv.DictReader(open(path)):
            if not r['athlete_id'] or int(r['athlete_id']) not in keep or r['did_not_play'] == 'true' \
                    or r['season_type'] not in ('2', '3', '5') or not r['minutes'] or float(r['minutes']) <= 0:
                continue
            opp = r['opponent_team_abbreviation']
            if opp not in tix:
                tix[opp] = len(teams)
                teams.append(opp)
            f = lambda c: int(float(r[c] or 0))
            day = (dt.date.fromisoformat(r['game_date'][:10]) - EPOCH).days
            logs.setdefault(int(r['athlete_id']), []).append(
                [day, s, tix[opp], 1 if r['home_away'] == 'home' else 0, 0 if r['season_type'] == '2' else 1,
                 round(float(r['minutes']), 1), f('points'), f('rebounds'), f('assists'), f('three_point_field_goals_made'), f('steals'), f('blocks'), f('turnovers'), f('field_goals_made'), f('field_goals_attempted'), f('free_throws_made'),
                 f('free_throws_attempted'), f('three_point_field_goals_attempted'), f('offensive_rebounds'), f('defensive_rebounds'), f('fouls')])
            n += 1
        print(f'{s}: {n:,} player games')
    for pid in logs:
        logs[pid] = sorted(logs[pid], reverse=True)[:MAX_GAMES]
    last = max((g[0] for gs in logs.values() for g in gs), default=None)
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'current_season': cur,
           'through': (EPOCH + dt.timedelta(days=last)).isoformat() if last else None,
           'cols': ['day', 'season', 'opp', 'home', 'playoff', 'min', 'pts', 'reb', 'ast', '3pm', 'stl', 'blk', 'tov', 'fgm', 'fga', 'ftm', 'fta', 'tpa', 'oreb', 'dreb', 'pf'],
           'teams': teams, 'players': logs}
    path = os.path.join(DATA, 'gamelogs.json')
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    print(f'{len(logs)} players, games through {out["through"]} -> data/gamelogs.json ({os.path.getsize(path) // 1000} KB)')
    render_app.render()


if __name__ == '__main__':
    main(sys.argv[1:])
