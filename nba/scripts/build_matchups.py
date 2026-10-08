#!/usr/bin/env python3
"""
Defense by position for the Slate page: how much of each box-score stat every team gave up to each position, last regular season.

  python3 nba/scripts/build_matchups.py
Writes nba/data/matchups.json

For every regular-season game log row (data/gamelogs.json) the shooter's position is his best depth-chart slot (PG SG SF PF C,
data/depth_charts.json, current rosters). A team's "allowed to PG" is the sum of its opponents' PG stats in a game, averaged over
the team's games. Rank 1 = gives up the most. Players with no depth slot (about 2% of minutes) are left out of the position
split but counted in the team totals. Persistence (the same ranking built from the first and second half of the season) is
reported so the page can say how much a rank is worth: this is context, not a bet.
"""
import datetime as dt, json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
POS = ['PG', 'SG', 'SF', 'PF', 'C']
STATS = ['pts', 'reb', 'ast', '3pm', 'pra', 'stl', 'blk', 'tov']
TEAM_STATS = ['pts', 'reb', 'ast', '3pm', 'tpa', 'tov']
FAKE = {'STARS', 'WORLD', 'STRIPES'}


def val(c, r, s):
    g = lambda k: r[c.index(k)]
    return g('pts') + g('reb') + g('ast') if s == 'pra' else g(s)


def spearman(a, b):
    ks = sorted(set(a) & set(b))
    def rk(d):
        o = sorted(ks, key=lambda k: d[k])
        return {k: i for i, k in enumerate(o)}
    ra, rb = rk(a), rk(b)
    n = len(ks)
    if n < 5:
        return None
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in ks) / (n * (n * n - 1))


def build():
    g = json.load(open(os.path.join(DATA, 'gamelogs.json')))
    d = json.load(open(os.path.join(DATA, 'depth_charts.json')))
    c, T = g['cols'], g['teams']
    pos = {}
    for t in d['teams'].values():
        for p in t['players']:
            if p['depth']:
                pos[str(p['id'])] = min(p['depth'], key=lambda x: x['rank'])['pos'].upper()
    season = max(r[1] for rows in g['players'].values() for r in rows) - 1       # rows carry the season's end year (2026 = 2025-26)
    games = defaultdict(set)                                    # team -> days it played
    for rows in g['players'].values():
        for r in rows:
            if not r[c.index('playoff')] and T[r[c.index('opp')]] not in FAKE:
                games[T[r[c.index('opp')]]].add(r[0])
    days = sorted({x for v in games.values() for x in v})
    mid = days[len(days) // 2]
    def table(lo, hi):
        pt = defaultdict(lambda: defaultdict(float))            # (team, pos, stat) -> total
        tt = defaultdict(lambda: defaultdict(float))
        ng = defaultdict(set)
        for pid, rows in g['players'].items():
            for r in rows:
                o = T[r[c.index('opp')]]
                if r[c.index('playoff')] or o in FAKE or not (lo <= r[0] < hi):
                    continue
                ng[o].add(r[0])
                for s in STATS:
                    if pid in pos:
                        pt[(o, pos[pid])][s] += val(c, r, s)
                for s in TEAM_STATS:
                    tt[o][s] += val(c, r, s) if s != 'tpa' else r[c.index('tpa')]
        return pt, tt, {k: len(v) for k, v in ng.items()}
    pt, tt, ng = table(0, 10 ** 9)
    teams = {t: {'g': ng[t], 'pos': {}, 'all': {}} for t in ng if ng[t] >= 20}
    for p in POS:
        for s in STATS:
            vals = {t: pt[(t, p)][s] / ng[t] for t in teams}
            order = sorted(vals, key=lambda t: -vals[t])
            for i, t in enumerate(order):
                teams[t]['pos'].setdefault(p, {})[s] = [round(vals[t], 1), i + 1]
    for s in TEAM_STATS:
        vals = {t: tt[t][s] / ng[t] for t in teams}
        order = sorted(vals, key=lambda t: -vals[t])
        for i, t in enumerate(order):
            teams[t]['all'][s] = [round(vals[t], 1), i + 1]
    # persistence: first half vs second half of the season, per position and stat
    h1, _, n1 = table(0, mid)
    h2, _, n2 = table(mid, 10 ** 9)
    per = {}
    for s in STATS:
        rs = []
        for p in POS:
            a = {t: h1[(t, p)][s] / n1[t] for t in teams if n1.get(t)}
            b = {t: h2[(t, p)][s] / n2[t] for t in teams if n2.get(t)}
            rs.append(spearman(a, b))
        rs = [x for x in rs if x is not None]
        per[s] = round(sum(rs) / len(rs), 2) if rs else None
    return {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'season': f'{season}-{str(season + 1)[2:]}' if season else None,
            'through': g.get('through'), 'pos': POS, 'stats': STATS, 'teams': teams, 'persistence': per,
            'coverage': 'players without a depth slot are left out of the position split'}


if __name__ == '__main__':
    out = build()
    json.dump(out, open(os.path.join(DATA, 'matchups.json'), 'w'), separators=(',', ':'))
    print('teams', len(out['teams']), 'season', out['season'], 'half-to-half rank correlation', out['persistence'])
    t = out['teams'].get('DAL') or next(iter(out['teams'].values()))
    print(json.dumps(t['pos']['PG'])[:300])
