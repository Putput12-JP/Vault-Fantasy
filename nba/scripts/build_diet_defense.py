#!/usr/bin/env python3
"""
Shot diet and defense sheet for the Slate page: where each player's shots and assists come from, and how much of each every team
allows. Context, not an edge (see docs/courtai-teardown.md and the persistence block this writes).

  python3 nba/scripts/fetch_hoopr.py --pbp 2026      # ESPN play-by-play (~290 MB, once)
  python3 nba/scripts/build_diet_defense.py [season]  # default: newest pbp file in raw/hoopr
Writes nba/data/diet_defense.json

Source is ESPN play-by-play through hoopR, because stats.nba.com is unreachable from here and from CI. That limits what exists:
  * Zones come from shot coordinates (feet, hoop at x=25, y=0, far end mirrored): restricted area <= 4 ft, paint non-RA inside the
    16 ft lane up to the free-throw line, corner 3 = a three taken at y <= 8.5 (the straight part of the line), above-break 3 = other
    threes, mid-range = all other twos. Validated on the data: threes start at 22.0 ft, twos end at 23.4 ft.
  * "Kinds" come from ESPN's shot labels (Pullup / Step Back, Driving, Cutting, Putback / Tip, plain Jump Shot). They are NOT
    Synergy play types. Transition, isolation, pick and roll, spot up, handoff, off screen and post up cannot be built from this feed.
  * Assist location is the zone of the assisted made shot: at rim <= 4 ft, short mid (other twos <= 15 ft), long mid (twos > 15 ft),
    corner 3, arc 3.
A player's diet is his share of his own attempts (assists) by slice. A team's defense is the opponents' attempts per 48 minutes by
slice, ranked 1 to 30 with rank 1 = allows the most (the same convention as matchups.json). vs% is that rate against the league
mean. The score for a player against a team is sum(share x vs%) over one category: how many more (+) or fewer (-) attempts than
average the defense gives up in the spots he shoots from. It measures OPPORTUNITY (shot volume), not shot quality.
Regular season only. Every row is dated, so any as-of cut can be rebuilt; the shipped file is season to date.
"""
import csv, datetime as dt, glob, json, math, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw', 'hoopr')
DATA = os.path.join(HERE, '..', 'data')

ZONES = [('ra', 'Restricted area'), ('paint', 'Paint (non-RA)'), ('mid', 'Mid-range'), ('c3', 'Corner 3'), ('ab3', 'Above-break 3')]
KINDS = [('pullup', 'Pull-up / step-back'), ('driving', 'Driving / running'), ('cut', 'Cutting'), ('putback', 'Putback / tip'),
         ('jumper', 'Jump shot, untagged')]
ASSISTS = [('rim', 'At rim'), ('smid', 'Short mid'), ('lmid', 'Long mid'), ('c3', 'Corner 3'), ('arc3', 'Arc 3')]
CATS = [('zone', ZONES), ('kind', KINDS), ('ast', ASSISTS)]
HOOP_Y = 83.5                       # far hoop in the feed's y (the near hoop is y = 0); shots past half court are mirrored
MIN_FGA_PLAYER = 50                 # players below this are left out of the file
THIN_FGA = 200                      # display flag only: shares from fewer attempts than this are shaky (never a model input)
THIN_AST = 40
MIN_TEAM_G = 20


def zone(x, y, three):
    if y > HOOP_Y / 2:
        y = HOOP_Y - y
    dx = x - 25.0
    d = math.hypot(dx, y)
    if three:
        return 'c3' if y <= 8.5 else 'ab3', d
    if d <= 4.0:
        return 'ra', d
    if abs(dx) <= 8.0 and y <= 13.75:
        return 'paint', d
    return 'mid', d


def kind(t):
    if 'Cutting' in t:
        return 'cut'
    if 'Putback' in t or 'Tip Shot' in t:
        return 'putback'
    if 'Pullup' in t or 'Step Back' in t:
        return 'pullup'
    if 'Driving' in t or 'Running' in t:
        return 'driving'
    if t == 'Jump Shot':
        return 'jumper'
    return None


def assist_loc(z, d):
    if z == 'c3':
        return 'c3'
    if z == 'ab3':
        return 'arc3'
    if d <= 4.0:
        return 'rim'
    return 'smid' if d <= 15.0 else 'lmid'


def spearman(a, b):
    ks = sorted(set(a) & set(b))
    n = len(ks)
    if n < 10:
        return None
    def rk(d):
        o = sorted(ks, key=lambda k: d[k])
        return {k: i for i, k in enumerate(o)}
    ra, rb = rk(a), rk(b)
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in ks) / (n * (n * n - 1))


def pearson(a, b):
    n = len(a)
    if n < 10:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return None if va == 0 or vb == 0 else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def newest_file(season=None):
    fs = sorted(glob.glob(os.path.join(RAW, 'pbp_*.csv')))
    if season:
        fs = [f for f in fs if f.endswith(f'pbp_{season}.csv')]
    if not fs:
        sys.exit('no raw/hoopr/pbp_<season>.csv: run nba/scripts/fetch_hoopr.py --pbp <season> first')
    return fs[-1]


def read(path):
    """-> shots [(date, game, shooter, name, shooter_team, opp_team, slices dict, assister)], periods per game, season label."""
    shots, maxp, abbr, season = [], defaultdict(int), {}, None
    with open(path, newline='') as fh:
        for r in csv.DictReader(fh):
            if r['season_type'] != '2':
                continue
            season = r['season']
            g = r['game_id']
            try:
                maxp[g] = max(maxp[g], int(r['period_number']))
            except ValueError:
                pass
            if r['shooting_play'] != 'true' or r['points_attempted'] not in ('2', '3') or not r['athlete_id_1']:
                continue
            try:
                x, y = float(r['coordinate_x_raw']), float(r['coordinate_y_raw'])
            except ValueError:
                continue
            if x < -1000 or y < -1000:                                   # the feed's "no coordinate" sentinel
                continue
            home, away = r['home_team_id'], r['away_team_id']
            abbr[home], abbr[away] = r['home_team_abbrev'], r['away_team_abbrev']
            tm = r['team_id']
            if tm not in (home, away):
                continue
            opp = away if tm == home else home
            z, d = zone(x, y, r['points_attempted'] == '3')
            made = r['scoring_play'] == 'true'
            ast = r['athlete_id_2'] if made and r['athlete_id_2'] and ' assists)' in r['text'] else ''
            shots.append((r['game_date'], g, r['athlete_id_1'], r['athlete_name_1'], abbr[tm], abbr[opp], z, kind(r['type_text']),
                          assist_loc(z, d) if ast else None, ast, r['athlete_name_2'] if ast else ''))
    return shots, maxp, season


def build(path):
    shots, maxp, season = read(path)
    days = sorted({s[0] for s in shots})
    mid = days[len(days) // 2]
    mins = {g: 48 + 5 * max(0, p - 4) for g, p in maxp.items()}
    games = defaultdict(set)                                             # team -> game ids
    allow = defaultdict(lambda: defaultdict(float))                      # (team, half) -> (cat, key) -> attempts per 48 summed over games
    allow_g = defaultdict(set)
    ng = defaultdict(int)
    pl = defaultdict(lambda: {'n': 0, 'a': 0, 'zone': defaultdict(int), 'kind': defaultdict(int), 'ast': defaultdict(int), 'team': '', 'name': '',
                              'half': [defaultdict(int), defaultdict(int)], 'hn': [0, 0], 'day': ''})
    for (day, g, pid, name, team, opp, z, k, al, aid, aname) in shots:
        h = 0 if day < mid else 1
        w = 48.0 / mins[g]
        for half in (None, h):
            tgt = allow[(opp, half)]
            tgt[('zone', z)] += w
            if k:
                tgt[('kind', k)] += w
        games[opp].add(g)
        allow_g[(opp, h)].add(g)
        games[team].add(g)
        p = pl[pid]
        p['n'] += 1
        p['zone'][z] += 1
        p['half'][h][z] += 1
        p['hn'][h] += 1
        if k:
            p['kind'][k] += 1
        if day >= p['day']:
            p['team'], p['name'], p['day'] = team, name, day
        if al:
            q = pl[aid]
            q['a'] += 1
            q['ast'][al] += 1
            if not q['name']:
                q['name'] = aname
    # assists allowed per 48 (by the assisted shot's location), with the same per-game scaling
    for (day, g, pid, name, team, opp, z, k, al, aid, aname) in shots:
        if al:
            h = 0 if day < mid else 1
            w = 48.0 / mins[g]
            allow[(opp, None)][('ast', al)] += w
            allow[(opp, h)][('ast', al)] += w
    teams = sorted(t for t in games if len(games[t]) >= MIN_TEAM_G)
    # games played by a defense, for per-game rates, from the games its opponents shot in
    dg = defaultdict(set)
    for (day, g, pid, name, team, opp, *_r) in shots:
        dg[opp].add(g)
    def rate(t, half, cat, key):
        n = len(dg[t]) if half is None else len(allow_g[(t, half)])
        return allow[(t, half)][(cat, key)] / n if n else None
    out_t, league = {t: {'g': len(dg[t]), 'zone': {}, 'kind': {}, 'ast': {}} for t in teams}, {'zone': {}, 'kind': {}, 'ast': {}}
    for cat, sl in CATS:
        for key, _ in sl:
            vals = {t: rate(t, None, cat, key) for t in teams}
            mean = sum(vals.values()) / len(vals)
            league[cat][key] = round(mean, 2)
            for i, t in enumerate(sorted(teams, key=lambda t: -vals[t])):
                out_t[t][cat][key] = [round(vals[t], 2), i + 1, round((vals[t] / mean - 1) * 100, 1)]
    # persistence: first half of the season vs second half
    pers = {'team_rank': {}, 'player_share': {}}
    for cat, sl in CATS:
        for key, _ in sl:
            a = {t: rate(t, 0, cat, key) for t in teams}
            b = {t: rate(t, 1, cat, key) for t in teams}
            a, b = {t: v for t, v in a.items() if v is not None}, {t: v for t, v in b.items() if v is not None}
            r = spearman(a, b)
            pers['team_rank'][f'{cat}.{key}'] = None if r is None else round(r, 2)
    for key, _ in ZONES:
        xs, ys = [], []
        for p in pl.values():
            if p['hn'][0] >= 100 and p['hn'][1] >= 100:
                xs.append(p['half'][0][key] / p['hn'][0])
                ys.append(p['half'][1][key] / p['hn'][1])
        r = pearson(xs, ys)
        pers['player_share'][f'zone.{key}'] = None if r is None else round(r, 2)
    pers['player_share_n'] = len(xs)
    # a slice whose team ranking does not carry from one half of the season to the other is noise, not a defense trait. The cut is the
    # two-sided 5% critical correlation for the 30 teams (t = 2.048 on 28 degrees of freedom), not a tuned number.
    n_t = len(teams)
    tcrit = {28: 2.048}.get(n_t - 2, 2.048)
    pers['weak_below'] = round(tcrit / math.sqrt(n_t - 2 + tcrit ** 2), 2)
    pers['weak'] = sorted(k for k, v in pers['team_rank'].items() if v is None or v < pers['weak_below'])
    players = {}
    for pid, p in pl.items():
        if p['n'] < MIN_FGA_PLAYER or not p['team']:
            continue
        e = {'name': p['name'], 'team': p['team'], 'fga': p['n'], 'ast': p['a'], 'thin': p['n'] < THIN_FGA,
             'zone': {k: round(p['zone'][k] / p['n'], 3) for k, _ in ZONES},
             'kind': {k: round(p['kind'][k] / p['n'], 3) for k, _ in KINDS}}
        if p['a']:
            e['ast_share'] = {k: round(p['ast'][k] / p['a'], 3) for k, _ in ASSISTS}
            e['ast_thin'] = p['a'] < THIN_AST
        players[pid] = e
    return {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
            'season': f'{int(season) - 1}-{str(season)[2:]}', 'through': days[-1], 'games': len({s[1] for s in shots}),
            'source': 'ESPN play-by-play (hoopR), regular season',
            'cats': {c: [[k, lab] for k, lab in sl] for c, sl in CATS},
            'thin': {'fga': THIN_FGA, 'ast': THIN_AST}, 'league': league, 'teams': out_t, 'players': players, 'persistence': pers,
            'coverage': 'No Synergy play types (transition, isolation, pick and roll, spot up, handoff, off screen, post up): the feed does not carry them. '
                        'Kinds are ESPN shot labels. Rate = opponent attempts per 48; rank 1 allows the most.'}


if __name__ == '__main__':
    out = build(newest_file(sys.argv[1] if len(sys.argv) > 1 else None))
    json.dump(out, open(os.path.join(DATA, 'diet_defense.json'), 'w'), separators=(',', ':'))
    print('season', out['season'], 'through', out['through'], 'games', out['games'], 'teams', len(out['teams']), 'players', len(out['players']))
    print('team rank persistence (first vs second half):', out['persistence']['team_rank'])
    print('player share persistence:', out['persistence']['player_share'], 'n', out['persistence']['player_share_n'])
    print('league', out['league']['zone'])
