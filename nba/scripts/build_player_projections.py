#!/usr/bin/env python3
"""
Season-start player projections for the team minutes page (nba/projections.html).

Per rostered player (from data/depth_charts.json):
  rates    per-minute pts/reb/ast/3pm/stl/blk/tov/fga, recency-weighted over the last
           three seasons and shrunk to the position prior (same scheme as the prop model)
  minutes  season-start minutes WHEN HE PLAYS, from MEASURED transitions, not guesses:
             returning player  early = a + b * last_mpg      (fit on 2024->25 and 2025->26)
             changed teams     early = a + b * last_mpg      (separate fit: new role)
             rookie            early = mean by draft-pick bucket (2023-24..2025-26 rookies)
           top 13 active, the rest start at 0. Players listed OUT on the roster start at 0.
  spread   variance fits from data/prop_model.json, for a 10th-90th percentile range

Also ships the measured rules the page uses when minutes are edited:
  rebalance  same-position teammates absorb freed minutes at the minutes model's
             vac_same / vac_other ratio
  cascade    per-minute bump for stats where the usage cascade beat the plain rate

  python3 nba/scripts/build_player_projections.py
Writes nba/data/player_projections.json and re-renders nba/projections.html (render_app.py).
"""
import csv, datetime as dt, json, os, statistics, sys, urllib.request
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
from build_minutes_model import group, ols
import render_app

DATA = os.path.join(C.HERE, '..', 'data')
STATS = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['three_point_field_goals_made'],
         'stl': ['steals'], 'blk': ['blocks'], 'tov': ['turnovers'], 'fga': ['field_goals_attempted']}
RATE_ALPHA, PRIOR_GAMES = 0.10, 8
EARLY_GAMES = 15            # "season start" = a player's first 15 games of the new season
ACTIVE = 13                 # NBA active list
TEAM_MIN = 240.0            # replaced by prop_model.json team_min (measured)
PICK_BUCKETS = [(1, 3), (4, 10), (11, 20), (21, 30), (31, 45), (46, 60)]


def sv(r, cols):
    return sum(r[c] for c in cols)


def rates(seasons):
    """End-of-history per-minute rates, EWMA shrunk to position prior."""
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    rt = {}
    box = C.player_games(seasons)
    for g in C.games(seasons):
        for r in box.get(g['game_id'], []):
            if not r['played'] or r['minutes'] <= 0:
                continue
            pos, m = group(r['pos']), r['minutes']
            for s, cols in STATS.items():
                prior[pos][s][0] += sv(r, cols)
                prior[pos][s][1] += m
            p = rt.get(r['athlete_id'])
            if p is None:
                p = rt[r['athlete_id']] = {'n': 0, 'pos': pos,
                                           'rate': {s: prior[pos][s][0] / max(1.0, prior[pos][s][1]) for s in STATS}}
            a = max(RATE_ALPHA, 1 / (p['n'] + 1 + PRIOR_GAMES))
            w = min(1.0, m / 20.0)
            for s, cols in STATS.items():
                p['rate'][s] += a * w * (sv(r, cols) / m - p['rate'][s])
            p['n'] += 1
    pos_prior = {pos: {s: v[0] / max(1.0, v[1]) for s, v in d.items()} for pos, d in prior.items()}
    return rt, pos_prior


def season_mpg(season):
    """athlete -> {team (last), mpg, gp, early_mpg (first EARLY_GAMES), early_team}. Regular season only."""
    games = {}
    for r in csv.DictReader(open(os.path.join(C.RAW, 'hoopr', f'player_box_{season}.csv'))):
        if r['season_type'] != '2' or not r['athlete_id'] or r['did_not_play'] == 'true' or C.num(r['minutes']) <= 0:
            continue
        games.setdefault(int(r['athlete_id']), []).append((r['game_date'], C.num(r['minutes']), r['team_abbreviation']))
    out = {}
    for a, gs in games.items():
        gs.sort()
        early = gs[:EARLY_GAMES]
        out[a] = {'team': gs[-1][2], 'mpg': statistics.mean(m for _, m, _ in gs), 'gp': len(gs),
                  'early_mpg': statistics.mean(m for _, m, _ in early), 'early_team': early[0][2]}
    return out


def draft(year):
    url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_draft/draft_{year}.csv'
    body = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault-nba'}), timeout=60).read().decode()
    return {C.name_key(r['athlete_display_name']): int(r['overall_pick']) for r in csv.DictReader(body.splitlines())}


def fit_minutes():
    """Measured season-start minutes: returners vs movers (linear on last mpg), rookies by pick bucket."""
    X = {'same': [], 'moved': []}
    Y = {'same': [], 'moved': []}
    rookie = defaultdict(list)
    names = {}
    for s in (2024, 2025, 2026):
        for r in csv.DictReader(open(os.path.join(C.RAW, 'hoopr', f'player_box_{s}.csv'))):
            if r['athlete_id']:
                names[int(r['athlete_id'])] = r['athlete_display_name']
    for prev, cur in ((2024, 2025), (2025, 2026)):
        a, b = season_mpg(prev), season_mpg(cur)
        for aid, now in b.items():
            before = a.get(aid)
            if before and before['gp'] >= 10:
                k = 'same' if before['team'] == now['early_team'] else 'moved'
                X[k].append([1.0, before['mpg']])
                Y[k].append(now['early_mpg'])
    for yr, season in ((2023, 2024), (2024, 2025), (2025, 2026)):
        picks = draft(yr)
        b = season_mpg(season)
        for aid, now in b.items():
            pk = picks.get(C.name_key(names.get(aid, '')))
            if pk:
                for lo, hi in PICK_BUCKETS:
                    if lo <= pk <= hi:
                        rookie[f'{lo}-{hi}'].append(now['early_mpg'])
    fit = {k: [round(v, 3) for v in ols(X[k], Y[k], ridge=0.0)] + [len(Y[k])] for k in X}
    fit['rookie'] = {k: [round(statistics.mean(v), 1), len(v)] for k, v in rookie.items()}
    return fit


def main():
    depth = json.load(open(os.path.join(DATA, 'depth_charts.json')))
    rt, pos_prior = rates([2024, 2025, 2026])
    fit = fit_minutes()
    print('season-start minutes fit', json.dumps(fit), flush=True)
    prop = json.load(open(os.path.join(DATA, 'prop_model.json')))
    global TEAM_MIN
    TEAM_MIN = prop.get('team_min', 240.0)
    mm = json.load(open(os.path.join(DATA, 'minutes_model.json')))['beta']
    casc = json.load(open(os.path.join(DATA, 'usage_cascade.json')))['stats']

    def default_minutes(p):
        if p['injury'] and 'Out' in p['injury']:
            return 0.0
        if p['draft'] and (p['rookie'] or not p['last_gp']):
            for lo, hi in PICK_BUCKETS:
                if lo <= p['draft']['pick'] <= hi:
                    return fit['rookie'].get(f'{lo}-{hi}', [4.0])[0]
        if p['last_gp'] >= 10:
            a, b, _ = fit['moved' if p['moved'] else 'same']
            return max(0.0, a + b * p['last_mpg'])
        if p['last_gp']:
            return p['last_mpg'] * 0.5
        return 3.0 if p['rookie'] else 4.0

    teams = {}
    for ab, t in depth['teams'].items():
        players = []
        for p in t['players']:
            r = rt.get(p['id'])
            pos = group(p['pos'])
            rate = r['rate'] if r else pos_prior[pos]
            players.append({'id': p['id'], 'name': p['name'], 'pos': p['pos'], 'grp': pos,
                            'rank': p['best_rank'], 'slotted': p['slotted'], 'rookie': p['rookie'], 'moved': p['moved'],
                            'last_team': p['last_team'], 'last_mpg': p['last_mpg'], 'gp': p['last_gp'],
                            'draft': p['draft']['pick'] if p['draft'] else None,
                            'injury': p['injury'][0] if p['injury'] else None,
                            'sample': r['n'] if r else 0,
                            'rate': {s: round(v, 4) for s, v in rate.items()},
                            'min0': default_minutes(p)})
        # Default = measured minutes WHEN HE PLAYS (the fit is on early-season minutes per game played), which is
        # what a prop needs. Do not scale the team to 240: last season's mpg only counts games played, so a healthy
        # top 13 sums to ~300 and scaling squeezed stars (Shai to 28). The page shows the total as information and
        # moves minutes between teammates only when you edit them. Beyond the 13-man active list, default 0.
        players.sort(key=lambda x: -x['min0'])
        for i, x in enumerate(players):
            x['active'] = i < ACTIVE and x['min0'] > 0
            if not x['active']:
                x['min0'] = 0.0
            x['min0'] = min(38.0, x['min0'])
        for x in players:
            x['min0'] = round(x['min0'], 1)
        players.sort(key=lambda x: -x['min0'])
        teams[ab] = {'name': t['name'], 'players': players, 'starters': t['starters']}

    out = {
        'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
        'season': depth['season_label'], 'depth_generated': depth['generated'],
        'minutes_fit': fit,
        'variance': {k: prop['variance'][k] for k in ('pts', 'reb', 'ast', '3pm', 'pra')},
        'team_min': TEAM_MIN,
        'rebalance': {'same': mm['vac_same'], 'other': mm['vac_other']},
        'cascade': {s: {'beta': casc[s]['beta'], 'use': casc[s]['use']} for s in ('pts', 'reb') if s in casc},
        'teams': teams,
    }
    json.dump(out, open(os.path.join(DATA, 'player_projections.json'), 'w'), separators=(',', ':'))
    render_app.render()   # the app page, data inlined (artifacts cannot fetch local files)
    n = sum(len(t['players']) for t in teams.values())
    print(f"{len(teams)} teams, {n} players -> data/player_projections.json "
          f"({os.path.getsize(os.path.join(DATA, 'player_projections.json')) // 1000} KB)")
    for x in teams['NY']['players'][:9]:
        print(f"  NY {x['name']:24s} {x['min0']:5.1f} min  pts {x['min0'] * x['rate']['pts']:5.1f}  reb {x['min0'] * x['rate']['reb']:4.1f}  ast {x['min0'] * x['rate']['ast']:4.1f}")


if __name__ == '__main__':
    main()
