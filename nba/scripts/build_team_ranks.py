#!/usr/bin/env python3
"""
Opponent rankings for the prop data-dive page's "Opp rankings" filter.

For each of the 30 teams, as a DEFENSE (and for pace, as a game), over the current season's regular-season games: six measured numbers, each ranked 1 to 30.
Rank 30 always means the friendliest side for an over (fastest pace, the most allowed, the worst defense); rank 1 the toughest. One rule for every chip.

  pace    possessions per game, both teams (FGA + 0.44 FTA - OREB + TOV, averaged over the two sides)
  defrtg  points allowed per 100 of the opponent's possessions
  ast     assists allowed
  paint   points in the paint allowed
  tpa     three-point attempts allowed
  fta     free-throw attempts allowed

Windows: the whole season and each team's last 5, 10 and 15 games. A team with fewer games than the window uses what it has (the games count is stored).
Source: raw/hoopr/team_box_<season>.csv (ESPN team box scores). No model, no prior-season blend: this is what the team has done this season.

  python3 nba/scripts/build_team_ranks.py [--season N]     writes data/team_ranks.json
"""
import csv, datetime as dt, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
RAW = os.path.join(HERE, '..', 'raw', 'hoopr')
OUT = os.path.join(DATA, 'team_ranks.json')

METRICS = [('pace', 'Pace', 'Possessions per game. 30th = fastest'), ('defrtg', 'DefRtg', 'Points allowed per 100 possessions. 30th = worst defense'),
           ('ast', 'Ast allowed', 'Assists allowed per game. 30th = most'), ('paint', 'Paint pts allowed', 'Points in the paint allowed per game. 30th = most'),
           ('tpa', '3PT att allowed', 'Three-point attempts allowed per game. 30th = most'), ('fta', 'FT att allowed', 'Free-throw attempts allowed per game. 30th = most')]
WINDOWS = [('all', None), ('L5', 5), ('L10', 10), ('L15', 15)]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def poss(r):
    return r['fga'] + 0.44 * r['fta'] - r['oreb'] + r['tov']


def load(season):
    path = os.path.join(RAW, f'team_box_{season}.csv')
    if not os.path.exists(path):
        sys.exit(f'no team box scores at {path}')
    by = defaultdict(dict)                 # game_id -> team -> row
    for x in csv.DictReader(open(path)):
        if x['season_type'] != '2':        # regular season only
            continue
        v = {k: num(x[c]) for k, c in [('fga', 'field_goals_attempted'), ('fta', 'free_throws_attempted'), ('oreb', 'offensive_rebounds'), ('tov', 'turnovers'),
                                       ('pts', 'team_score'), ('ast', 'assists'), ('paint', 'points_in_paint'), ('tpa', 'three_point_field_goals_attempted')]}
        if any(a is None for a in v.values()):
            continue
        v['day'] = x['game_date']
        by[x['game_id']][x['team_abbreviation']] = v
    games = defaultdict(list)              # team -> [(day, {metric: value})]
    for gid, sides in by.items():
        if len(sides) != 2:
            continue
        (a, ra), (b, rb) = sorted(sides.items())
        for t, me, op in ((a, ra, rb), (b, rb, ra)):
            pp = (poss(me) + poss(op)) / 2
            games[t].append((me['day'], {'pace': pp, 'defrtg': 100 * op['pts'] / poss(op) if poss(op) > 0 else None, 'ast': op['ast'], 'paint': op['paint'],
                                         'tpa': op['tpa'], 'fta': op['fta']}))
    for t in games:
        games[t].sort(key=lambda g: g[0], reverse=True)      # newest first
    return games


def main():
    if '--season' in sys.argv:
        cur = int(sys.argv[sys.argv.index('--season') + 1])
    else:
        cur = int(json.load(open(os.path.join(DATA, 'gamelogs.json')))['current_season'])
    games = load(cur)
    if len(games) < 20:
        sys.exit(f'only {len(games)} teams have games in {cur}; keeping the last file')
    through = max(g[0][0] for g in games.values())
    out = {t: {'g': len(games[t])} for t in games}
    for wk, n in WINDOWS:
        vals = {}
        for t, gl in games.items():
            sel = gl if n is None else gl[:n]
            vals[t] = {m: sum(g[1][m] for g in sel if g[1][m] is not None) / len([g for g in sel if g[1][m] is not None]) for m, _, _ in METRICS}
            out[t].setdefault('n', {})[wk] = len(sel)
        for m, _, _ in METRICS:
            for i, (t, v) in enumerate(sorted(vals.items(), key=lambda kv: kv[1][m])):
                out[t].setdefault(wk, {})[m] = [i + 1, round(v[m], 2)]
    doc = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'season': cur, 'through': through,
           'windows': [w for w, _ in WINDOWS], 'metrics': [{'k': k, 'l': l, 'h': h} for k, l, h in METRICS], 'teams': out}
    json.dump(doc, open(OUT, 'w'), separators=(',', ':'))
    print(f'wrote {os.path.relpath(OUT)}: {len(out)} teams through {through}')


if __name__ == '__main__':
    main()
