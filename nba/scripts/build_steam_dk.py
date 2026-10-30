#!/usr/bin/env python3
"""
Steam Chaser backtest: Pinnacle prop moves vs DraftKings (ESPN feed). NO-GO, see docs/steam-chaser-backtest.md.

  python3 nba/scripts/build_steam_dk.py <nba-data checkout> <window minutes> <min move, 0.02 = 2pp> <out.json>

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
DKT={'Total Points':'pts','Total Rebounds':'reb','Total Assists':'ast','Total 3-Point Field Goals':'3pm','Total Points, Rebounds, and Assists':'pra'}
dk={}
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
        elif s == 'espn' and r.get('athlete_id') and r.get('book') in ('DraftKings','Draft Kings') and r.get('type') in DKT:
            dk[r['k']] = (int(r['athlete_id']), DKT[r['type']], str(r['game']), int(r['ord']))
        elif s in am: am[s][r['k']] = r
        elif r.get('pid') and r.get('game') and r.get('player'):
            name_pid[(name_key(r['player']), r['team'])] = int(r['pid'])
        if s and r.get('game') and r.get('tip') and r.get('team'):
            team_game[(r['team'], r['tip'])] = str(r['game']); games[str(r['game'])] = r['tip']
for d in days:
    for src in ('pinnacle', 'espn'):
        p = os.path.join(d, src + '.jsonl')
        if not os.path.exists(p): continue
        for line in open(p):
            if src == 'pinnacle' and ';ou|' not in line: continue
            if src == 'espn' and '|game"' in line: continue
            r = json.loads(line)
            if (src == 'pinnacle' and r['k'] in pm) or (src == 'espn' and r['k'] in dk): ser[(src, r['k'])].append((r['t'], r['v']))
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
# DK series grouped by (gid, athlete, stat): {0: over series, 1: under series}
dks = defaultdict(dict)
for k,(aid,st,gid,o) in dk.items():
    if ('espn',k) in ser: dks[(gid,aid,st)][o] = ser[('espn',k)]
aid2name = {}
for (nk,team),pid in name_pid.items(): aid2name[pid]=nk
def dec(a):
    a=float(a); return 1+(a/100 if a>0 else 100/-a)
ev = []
for (gid,aid,stat),D in dks.items():
    if 0 not in D or 1 not in D or gid not in games: continue
    nk = aid2name.get(aid)
    if not nk: continue
    tip = games[gid]; b = getbox(gid)
    if b is None: continue
    st = b.get(str(aid)); y = None if not st else sum(st.get(c, 0) for c in STAT_COL[stat])
    if y is None: continue
    P = pin.get((nk, stat, tip)) or next((v for (n, s2, t0), v in pin.items() if n == nk and s2 == stat and abs(t0 - tip) <= 900), None)
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
        dp = po - ref[2] if ln == ref[1] else None
        kind = 'line' if dline != 0 else ('price' if dp is not None and abs(dp) >= MINMOVE else None)
        if kind is None: continue
        direction = 'Over' if (dline > 0 or (dline == 0 and dp > 0)) else 'Under'
        so = 0 if direction == 'Over' else 1
        q = at(D[so], t); qo = at(D[0], t); qu = at(D[1], t)
        if not q or not qo or not qu or qo[0] != qu[0]: continue
        dline_dk = qo[0]; px = q[1]
        last_fired = t
        # fair chance of the taken side at DK's line (only knowable when DK is on Pinnacle's line)
        same = (dline_dk == ln)
        fair = (po if direction == 'Over' else 1 - po) if same else None
        ev_t = (fair * dec(px) - 1) if fair is not None else None
        # Pinnacle close on the same line
        lastp = [x for x in ps if x[0] < tip][-1]
        fclose = None
        if lastp[1] == ln: fclose = lastp[2] if direction == 'Over' else 1 - lastp[2]
        ev_c = (fclose * dec(px) - 1) if fclose is not None and same else None
        # DK close (last quote before tip) price and line on the taken side
        dkc = at([x for x in D[so] if x[0] < tip], tip)
        nxt = next((tt for tt, x in D[so] if tt > t and x is not None and (x[0] != q[0] or x[1] != px)), None)
        catch = None if nxt is None or nxt >= tip else nxt - t
        if y == dline_dk: res = None
        else: res = (y > dline_dk) if direction == 'Over' else (y < dline_dk)
        # staleness: for a price move DK on Pinnacle's line; for a line move DK on the old (cheap) side line
        stale = same if kind == 'price' else ((dline_dk < ln) if direction == 'Over' else (dline_dk > ln))
        ev.append(dict(kind=kind, stale=stale, dir=direction, t=t, tip=tip, gid=gid, stat=stat, res=res, catch=catch, px=px, same=same,
                       ev_t=ev_t, ev_c=ev_c, hrs=(tip-t)/3600, mag=abs(dline) if kind=='line' else abs(dp), day=tip//86400,
                       dk_line=dline_dk, pin_line=ln, dkc_px=(dkc[1] if dkc and dkc[0]==dline_dk else None)))
json.dump(ev, open(sys.argv[4], 'w'))
print(len(ev))
