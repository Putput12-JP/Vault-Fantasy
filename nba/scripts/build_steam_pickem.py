#!/usr/bin/env python3
"""
Steam Chaser backtest: Pinnacle prop moves vs PrizePicks and Underdog. NO-GO, see docs/steam-chaser-backtest.md.

  python3 nba/scripts/build_steam_pickem.py <nba-data checkout> <window minutes> <min move, 0.02 = 2pp> <out.json>

Event: a Pinnacle player prop (pts, reb, ast, 3pm, pra) whose line changed, or whose de-vigged over chance moved by the
minimum within the window. The target quote is read at the event time from the stored series; nothing is estimated.
Needs results/ (box scores) in the checkout. Pinnacle is a price reference, never a place to bet.
"""
import glob, json, os, re, sys, statistics, math, bisect
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nba_common import name_key
from prop_board import PP_STAT, UD_STAT
from ledger import STAT_COL
root = sys.argv[1]; WIN = int(sys.argv[2]) * 60; MINMOVE = float(sys.argv[3])
PIN_STAT = {'Total Points': 'pts', 'Total Rebounds': 'reb', 'Total Assists': 'ast', 'Total Threes Made': '3pm', 'Total Pts & Rebs & Asts': 'pra'}
days = sorted(glob.glob(os.path.join(root, 'snapshots', '20*')))
pm, am, ser = {}, {'prizepicks': {}, 'underdog': {}}, defaultdict(list)
name_pid, team_game, games = {}, {}, {}
for d in days:
    for line in open(os.path.join(d, 'meta.jsonl')):
        r = json.loads(line); s = r.get('src')
        if s == 'pinnacle' and r.get('desc') and r.get('type') == 'total':
            m = re.match(r'^(.*) (Total (?:Points|Rebounds|Assists|Threes Made|Pts & Rebs & Asts))$', r['desc'])
            if m and m.group(2) in PIN_STAT:
                pm[r['k']] = (name_key(m.group(1)), PIN_STAT[m.group(2)], r['start'], r['side'])
        elif s in am: am[s][r['k']] = r
        elif r.get('pid') and r.get('game') and r.get('player'):
            name_pid[(name_key(r['player']), r['team'])] = int(r['pid'])
        if s and r.get('game') and r.get('tip') and r.get('team'):
            team_game[(r['team'], r['tip'])] = str(r['game']); games[str(r['game'])] = r['tip']
for d in days:
    for src in ('pinnacle', 'prizepicks', 'underdog'):
        p = os.path.join(d, src + '.jsonl')
        if not os.path.exists(p): continue
        for line in open(p):
            if src == 'pinnacle' and ';ou|' not in line: continue
            r = json.loads(line)
            if src != 'pinnacle' or r['k'] in pm: ser[(src, r['k'])].append((r['t'], r['v']))
for v in ser.values(): v.sort(key=lambda x: x[0])
pin = defaultdict(dict)
for k, (nk, st, start, side) in pm.items():
    if ('pinnacle', k) in ser: pin[(nk, st, start)][side] = ser[('pinnacle', k)]
def ip(a): return -a / (-a + 100) if a < 0 else 100 / (a + 100)
def at(s, t):
    v = None
    for tt, x in s:
        if tt > t: break
        v = x
    return v
box = {}
def getbox(g):
    if g not in box:
        p = os.path.join(root, 'results', g + '.json'); box[g] = json.load(open(p)) if os.path.exists(p) else None
    return box[g]
# Pinnacle state series: at each time either side changes -> (t, line, p_over)  (Over and Under share a line)
def pin_series(P):
    ts = sorted({t for t, _ in P['Over']} | {t for t, _ in P['Under']}); out = []
    for t in ts:
        o, u = at(P['Over'], t), at(P['Under'], t)
        if not o or not u or o[0] != u[0] or o[1] is None or u[1] is None: continue
        a, b = ip(o[1]), ip(u[1]); out.append((t, o[0], a / (a + b)))
    return out
ev = []
for app in ('prizepicks', 'underdog'):
    for (a, k), s in ser.items():
        if a != app: continue
        m = am[app].get(k)
        if not m or (app == 'prizepicks' and m.get('odds') != 'standard'): continue
        stat = (PP_STAT if app == 'prizepicks' else UD_STAT).get(m.get('stat'))
        if stat not in PIN_STAT.values(): continue
        team = m.get('team'); pid = name_pid.get((name_key(m['player']), team)); gid = team_game.get((team, m.get('start')))
        if not pid or not gid: continue
        tip = games[gid]; b = getbox(gid)
        if b is None: continue
        st = b.get(str(pid)); y = None if not st else sum(st.get(c, 0) for c in STAT_COL[stat])
        if y is None: continue
        P = pin.get((name_key(m['player']), stat, tip)) or next((v for (n, s2, t0), v in pin.items() if n == name_key(m['player']) and s2 == stat and abs(t0 - tip) <= 900), None)
        if not P or 'Over' not in P or 'Under' not in P: continue
        ps = pin_series(P)
        if len(ps) < 2: continue
        last_fired = -1e18
        for i in range(1, len(ps)):
            t, ln, po = ps[i]
            if t >= tip or t - last_fired < WIN: continue
            base = [x for x in ps[:i] if x[0] >= t - WIN]
            ref = base[0] if base else ps[i - 1]
            dline = ln - ref[1]
            # move in over-chance expressed at the NEW line; a line shift of d points ~ 2-4pp per half point in props (not assumed: line shifts are their own class)
            dp = po - ref[2] if ln == ref[1] else None
            kind = 'line' if dline != 0 else ('price' if dp is not None and abs(dp) >= MINMOVE else None)
            if kind is None: continue
            direction = 'Over' if (dline > 0 or (dline == 0 and dp > 0)) else 'Under'
            a_now = at(s, t)
            if a_now is None: continue
            aline = a_now[0]
            # stale = app still on a number that makes `direction` the cheap side
            if kind == 'line': stale = (aline < ln) if direction == 'Over' else (aline > ln)
            else: stale = (aline == ln)
            # when does the app move next?
            nxt = next((tt for tt, x in s if tt > t and x is not None and x[0] != aline), None)
            catch = None if nxt is None or nxt >= tip else nxt - t
            if not stale:
                ev.append(dict(app=app, kind=kind, stale=False, t=t, tip=tip, gid=gid)); last_fired = t; continue
            if y == aline: res = None
            else: res = (y > aline) if direction == 'Over' else (y < aline)
            # price of the taken side at the app (Underdog stored American; flat for PP)
            price = None
            if app == 'underdog':
                try: price = a_now[1] if direction == 'Over' else a_now[2]
                except Exception: price = None
            hrs = (tip - t) / 3600
            lastp=[x for x in ps if x[0] < tip][-1]
            cont = None if lastp[1] != ln else ((lastp[2]-po) if direction=='Over' else (po-lastp[2]))
            lcont = (lastp[1]-ln) if direction=='Over' else (ln-lastp[1])
            ev.append(dict(app=app, kind=kind, stale=True, dir=direction, t=t, tip=tip, gid=gid, pid=pid, stat=stat, res=res, catch=catch, price=price, hrs=hrs,
                           mag=abs(dline) if kind == 'line' else abs(dp), cont=cont, lcont=lcont, aline=aline, pline=ln, day=(tip // 86400)))
            last_fired = t
json.dump(ev, open(sys.argv[4], 'w'))
print(len(ev))
