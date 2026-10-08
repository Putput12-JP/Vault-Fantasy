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
MIN_GAMES = 15
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
    # rows carry the season's end year (2026 = 2025-26). Per-game allowed values come from the last full season, blended with the new one
    # by its games played: weight = games / MIN_GAMES for each team, all new at MIN_GAMES. Ranks are taken on the blended values.
    per = defaultdict(lambda: defaultdict(set))                 # season -> team -> days played
    for rows in g['players'].values():
        for r in rows:
            if not r[c.index('playoff')] and T[r[c.index('opp')]] not in FAKE:
                per[r[1]][T[r[c.index('opp')]]].add(r[0])
    newest = max(per)
    prev = max((x for x in per if x < newest and len(per[x]) >= 30), default=None)
    if prev is None or (len(per[newest]) >= 30 and min(len(v) for v in per[newest].values()) >= 20):
        prev, newest = None, newest                              # only one usable season
    last = prev if prev is not None else newest
    def table(season, lo=0, hi=10 ** 9):
        pt = defaultdict(lambda: defaultdict(float))            # (team, pos) -> stat -> total
        tt = defaultdict(lambda: defaultdict(float))
        ng = defaultdict(set)
        for pid, rows in g['players'].items():
            for r in rows:
                o = T[r[c.index('opp')]]
                if r[1] != season or r[c.index('playoff')] or o in FAKE or not (lo <= r[0] < hi):
                    continue
                ng[o].add(r[0])
                for s in STATS:
                    if pid in pos:
                        pt[(o, pos[pid])][s] += val(c, r, s)
                for s in TEAM_STATS:
                    tt[o][s] += val(c, r, s)
        return pt, tt, {k: len(v) for k, v in ng.items()}
    pa, ta, na = table(last)
    pn, tn, nn = table(newest) if last != newest else ({}, {}, {})
    wt = {t: min(1.0, nn.get(t, 0) / MIN_GAMES) for t in na}
    teams = {t: {'g': na[t], 'gn': nn.get(t, 0), 'w': round(wt[t], 2), 'pos': {}, 'all': {}} for t in na if na[t] >= 20}
    def blend(old, new, t, key, s):
        o = old[key][s] / na[t]
        return o if not nn.get(t) else wt[t] * new[key][s] / nn[t] + (1 - wt[t]) * o
    for p_ in POS:
        for s in STATS:
            vals = {t: blend(pa, pn, t, (t, p_), s) for t in teams}
            for i, t in enumerate(sorted(vals, key=lambda t: -vals[t])):
                teams[t]['pos'].setdefault(p_, {})[s] = [round(vals[t], 1), i + 1]
    for s in TEAM_STATS:
        vals = {t: blend(ta, tn, t, t, s) for t in teams}
        for i, t in enumerate(sorted(vals, key=lambda t: -vals[t])):
            teams[t]['all'][s] = [round(vals[t], 1), i + 1]
    ws = [x['w'] for x in teams.values()]
    mix = sum(ws) / len(ws) if ws else 0
    season = (newest if mix >= 1 else last) - 1
    label = f'{last - 1}-{str(last)[2:]}' if mix == 0 else f'{newest - 1}-{str(newest)[2:]}' if mix >= 1 else f'{last - 1}-{str(last)[2:]} blended with {newest - 1}-{str(newest)[2:]}'
    # persistence: first half vs second half of the last full season, per position and stat
    days = sorted({x for v in per[last].values() for x in v})
    mid = days[len(days) // 2]
    h1, _, n1 = table(last, 0, mid)
    h2, _, n2 = table(last, mid, 10 ** 9)
    per = {}
    for s in STATS:
        rs = []
        for p_ in POS:
            a_ = {t: h1[(t, p_)][s] / n1[t] for t in teams if n1.get(t)}
            b_ = {t: h2[(t, p_)][s] / n2[t] for t in teams if n2.get(t)}
            rs.append(spearman(a_, b_))
        rs = [x for x in rs if x is not None]
        per[s] = round(sum(rs) / len(rs), 2) if rs else None
    return {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'season': label, 'mix': round(mix, 2),
            'through': g.get('through'), 'pos': POS, 'stats': STATS, 'teams': teams, 'persistence': per,
            'coverage': 'players without a depth slot are left out of the position split'}


if __name__ == '__main__':
    out = build()
    json.dump(out, open(os.path.join(DATA, 'matchups.json'), 'w'), separators=(',', ':'))
    print('teams', len(out['teams']), 'season', out['season'], 'half-to-half rank correlation', out['persistence'])
    t = out['teams'].get('DAL') or next(iter(out['teams'].values()))
    print(json.dumps(t['pos']['PG'])[:300])
