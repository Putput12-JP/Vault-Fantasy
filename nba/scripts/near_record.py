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
     'x': {stat: {'books|o': [n, proj_in, proj_abs, line_in], ...}},       the same counts split by where the line came from (books, pickem: the psim row's
                                                                  price_src) and which side of it the projection sat (o: above the line, u: below)
     'e': {'dim|stat|value': [n, won, ret, priced, be, near, lnear], ...}}  did the projection's SIDE win, split five ways per stat (ss stat x side x source, gap,
                                                                  role starter or bench x side, min minutes played vs projected, pe model chance minus price): n props with a side that did not push, won = landed on
                                                                  our side, ret = summed return of 1 unit at the no-vig price (psim p_price) over the
                                                                  `priced` props that have one, be = summed no-vig chance of our side on those (the
                                                                  break-even), near / lnear = projection / line within NEAR_PROP. Plus 'fw|<id>' for
                                                                  each frozen forward-test pocket (FORWARD, docs/near-edge-forward-prereg.md).
  An empty prev (the first run) scans every stored day, so the record starts from opening night, not from the day it shipped. The ledger passes an
  empty prev whenever track.json near_v is not VERSION, so a change to the stored format rescans every night too (v2: hits on all four stats, with the
  line; v3: the side splits in 'e').

The side splits describe where the projection's lean has won. They are not bets and change no price; the no-vig return is before any book's cut.
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

VERSION = 3
NEAR_PROP = 1.0                     # a prop projection within this many of the actual (points, rebounds, assists or 3-pointers)
STATS = ['pts', 'reb', 'ast', '3pm']
STAT_BOX = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': 'threePointFieldGoalsMade'}
MIN_MISS = 6                        # minutes played this far from the projection's minutes counts as a minutes miss


def _gap(g):
    return '0-0.5' if g < .5 else '0.5-1' if g < 1 else '1-2' if g < 2 else '2-3' if g < 3 else '3+'


def _pe(e):                         # model chance of our side minus the price's no-vig chance of it, in points
    return None if e is None else '<0' if e < 0 else '0-3' if e < .03 else '3-6' if e < .06 else '6-10' if e < .1 else '10+'


# Frozen Nov 2, 2026 from Oct 21 to Nov 1 (3,201 props; about 80 slices looked at, so some of these are luck). Scored on props that tip on or after
# FORWARD_FROM only; the page reads them on FORWARD_READ. Do not edit a definition: a changed pocket is a new test with a new start date.
FORWARD_FROM, FORWARD_READ = '2026-11-03', '2026-12-01'
FORWARD = {
    'ast_u_books': lambda p: p['stat'] == 'ast' and p['side'] == 'u' and p['src'] == 'books',
    '3pm_o_books': lambda p: p['stat'] == '3pm' and p['side'] == 'o' and p['src'] == 'books',
    'reb_gap_1_2': lambda p: p['stat'] == 'reb' and 1 <= p['gap'] < 2,
    'starter_u':   lambda p: p['starter'] and p['side'] == 'u',
}


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
        hits, x, e = [], {}, {}
        starters = set(L.box_meta(root, gid).get('starters') or [])
        fwd = L.tip_day(rows[0][1]['tip']) >= FORWARD_FROM
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
            if mu == line or y == line:                         # no side, or a push: nothing won or lost
                continue
            side = 'o' if mu > line else 'u'
            won = (y > line) == (side == 'o')
            pp = v[5] if len(v) > 5 else None
            ps = None if pp is None else (pp if side == 'o' else 1 - pp)
            ms = None if pp is None or v[2] is None else (v[2] if side == 'o' else 1 - v[2])
            mp, ma = m.get('min'), st.get('minutes')
            p = {'stat': stat, 'side': side, 'src': v[6] if len(v) > 6 and v[6] else 'books', 'gap': abs(mu - line), 'starter': int(m['pid']) in starters}
            keys = [f"ss|{stat}|{side}|{p['src']}", f"gap|{stat}|{_gap(p['gap'])}", f"role|{stat}|{'starter' if p['starter'] else 'bench'}|{side}"]
            if mp is not None and ma is not None:
                keys.append(f"min|{stat}|{'short' if ma - mp <= -MIN_MISS else 'long' if ma - mp >= MIN_MISS else 'right'}")
            if ms is not None:
                keys.append(f"pe|{stat}|{_pe(ms - ps)}")
            if fwd:
                keys += [f'fw|{k}' for k, f in FORWARD.items() if f(p)]
            for k in keys:
                c = e.setdefault(k, [0, 0, 0.0, 0, 0.0, 0, 0])
                c[0] += 1; c[1] += won; c[5] += ep <= NEAR_PROP; c[6] += el <= NEAR_PROP
                if ps:
                    c[2] += (1 / ps - 1) if won else -1; c[3] += 1; c[4] += ps
        if not any(a[0] for a in s.values()):
            continue
        m = rows[0][1]
        hits.sort(key=lambda h: abs(h[3] - h[4]))
        per_day.setdefault(L.tip_day(m['tip']), []).append({'game': gid, 'matchup': m['matchup'], 'tip': m['tip'],
            's': {st: [round(x, 2) if isinstance(x, float) else x for x in a] for st, a in s.items() if a[0]}, 'hits': hits,
            'x': {st: {k: [c[0], c[1], round(c[2], 2), c[3]] for k, c in by.items()} for st, by in x.items()},
            'e': {k: [round(z, 3) if isinstance(z, float) else z for z in c] for k, c in e.items()},
            **({'replay': 1} if m.get('replay') else {})})
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: g['tip'])
    return days
