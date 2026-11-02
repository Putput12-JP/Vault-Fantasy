#!/usr/bin/env python3
"""
Near-exact record: how often a prop projection lands within a point of what the player really did, for the Track Record page.

Nothing here is a bet and nothing here changes a price. It reads numbers the recorders already stored before tip and the box score:

  proj   the prop model's mean for the player in that game (prop_sim_record row field `mu`, the Player Props projection), last row before tip
  line   the main line on the same prop (prop_sim_record row field `line`), the market's number, as the yardstick

A prop counts when the player played. It is NEAR when |number - actual| <= NEAR_PROP (inclusive). Props the roster guard held are left out, as in
the minutes-model comparison (prop_sim_record.score): their minutes were not trusted, so their projection is not the model's claim.
The Game Simulation's player median is not scored here: it is a whole number, so |median - actual| <= 1 covers three outcomes where a projection's
window covers two points, and its hit rate would look better for that reason alone (on opening fortnight, 3-pointers: 75% against 54%). The Props
Simulation plays out the same `mu`, so the projection is the simulation's centre too.

Game lines (Vault line and simulation within 3 points of the final margin and total) need no new data: the page reads them from sim_days.

  record(root, now, prev, rescan_days, games, L) -> per tip day, per game:
    {'game', 'matchup', 'tip', 's': {stat: [n, proj_in, proj_abs, line_in, line_abs]},
     'hits': [[player, team, stat, proj, actual, line], ...],    every prop the projection had within NEAR_PROP, closest first
     'x': {stat: {'books|o': [n, proj_in, proj_abs, line_in], ...}}}       the same counts split by where the line came from (books, pickem: the psim row's
                                                                  price_src) and which side of it the projection sat (o: above the line, u: below)
  An empty prev (the first run) scans every stored day, so the record starts from opening night, not from the day it shipped. The ledger passes an
  empty prev whenever track.json near_v is not VERSION, so a change to the stored format rescans every night too (v2: hits on all four stats, with the line).
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

VERSION = 2
NEAR_PROP = 1.0                     # a prop projection within this many of the actual (points, rebounds, assists or 3-pointers)
STATS = ['pts', 'reb', 'ast', '3pm']
STAT_BOX = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': 'threePointFieldGoalsMade'}


def _last_pre(x):
    m = x['meta']
    pre = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
    return pre[-1] if pre else None


def record(root, now, prev, rescan_days, games, L):
    days = dict(prev or {})
    if prev:
        since = L.tip_day(now - rescan_days * 86400)
    else:
        found = sorted(os.path.basename(d) for d in glob.glob(os.path.join(root, 'snapshots', '20*')))
        since = found[0] if found else L.tip_day(now - rescan_days * 86400)
    G = {}
    for k, x in L.load_src(root, 'psim', since).items():
        m = x['meta']
        if not m or m.get('held') or m.get('stat') not in STATS or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        v = _last_pre(x)
        if v and v[1] is not None:
            G.setdefault(str(m['game']), []).append((v, m))
    per_day = {}
    for gid, rows in G.items():
        bx = L.box(root, gid)
        if bx is None:
            continue
        s = {st: [0, 0, 0.0, 0, 0.0] for st in STATS}
        hits, x = [], {}
        for v, m in rows:
            st = bx.get(int(m['pid']))
            if not st:                                          # did not play: no actual to be near
                continue
            stat, y = m['stat'], st.get(STAT_BOX[m['stat']], 0)
            line, mu = v[0], v[1]
            a = s[stat]
            ep, el = abs(mu - y), abs(line - y)
            a[0] += 1; a[1] += ep <= NEAR_PROP; a[2] += ep; a[3] += el <= NEAR_PROP; a[4] += el
            c = x.setdefault(stat, {}).setdefault(f"{v[6] if len(v) > 6 and v[6] else 'books'}|{'o' if mu > line else 'u'}", [0, 0, 0.0, 0])
            c[0] += 1; c[1] += ep <= NEAR_PROP; c[2] += ep; c[3] += el <= NEAR_PROP
            if ep <= NEAR_PROP:
                hits.append([m['player'], m['team'], stat, round(mu, 1), y, line])
        if not any(a[0] for a in s.values()):
            continue
        m = rows[0][1]
        hits.sort(key=lambda h: abs(h[3] - h[4]))
        per_day.setdefault(L.tip_day(m['tip']), []).append({'game': gid, 'matchup': m['matchup'], 'tip': m['tip'],
            's': {st: [round(x, 2) if isinstance(x, float) else x for x in a] for st, a in s.items() if a[0]}, 'hits': hits,
            'x': {st: {k: [c[0], c[1], round(c[2], 2), c[3]] for k, c in by.items()} for st, by in x.items()},
            **({'replay': 1} if m.get('replay') else {})})
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: g['tip'])
    return days
