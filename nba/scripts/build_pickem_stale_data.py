#!/usr/bin/env python3
"""
Stale-line dataset: at each decision time before tip (DECIDE_H hours), the app's line vs Pinnacle's line and de-vigged chance at that same
moment, with the game's result. Pinnacle is a price reference only. Nothing is estimated; a field missing in the stored series is None.

  python3 nba/scripts/build_pickem_stale_data.py <nba-data checkout> [out.json]

Row: one app quote (PrizePicks standard or Underdog) that was live at the decision time.
  line_d / pin_line_d   the app's and Pinnacle's line at tip - h hours;  pin_over_d  Pinnacle's de-vigged over chance at its line then
  pin_line_c            Pinnacle's line at the last quote before tip;     line_c  the app's line at the last quote before tip
"""
import glob, json, os, re, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from nba_common import name_key
from prop_board import PP_STAT, UD_STAT
from ledger import STAT_COL

DECIDE_H = (4, 3, 2, 1)
PIN_STAT = {'Total Points': 'pts', 'Total Rebounds': 'reb', 'Total Assists': 'ast', 'Total Threes Made': '3pm', 'Total Pts & Rebs & Asts': 'pra'}
root = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'data', 'pickem_stale_legs.json')
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
        elif s in am:
            am[s][r['k']] = r
        elif r.get('pid') and r.get('game') and r.get('player'):
            name_pid[(name_key(r['player']), r['team'])] = int(r['pid'])
        if s and r.get('game') and r.get('tip') and r.get('team'):
            team_game[(r['team'], r['tip'])] = str(r['game']); games[str(r['game'])] = r['tip']
for d in days:
    for src in ('pinnacle', 'prizepicks', 'underdog'):
        p = os.path.join(d, src + '.jsonl')
        if os.path.exists(p):
            for line in open(p):
                if src == 'pinnacle' and '"|s;0;ou|' not in line.replace('"k":"', '"|', 1) and ';ou|' not in line:
                    continue
                r = json.loads(line)
                if src != 'pinnacle' or r['k'] in pm:
                    ser[(src, r['k'])].append((r['t'], r['v']))
for v in ser.values():
    v.sort()
# Pinnacle by (name, stat, start)
pin = defaultdict(dict)
for k, (nk, st, start, side) in pm.items():
    if ('pinnacle', k) in ser:
        pin[(nk, st, start)][side] = ser[('pinnacle', k)]


def at(s, t):
    v = None
    for tt, x in s:
        if tt > t:
            break
        v = x
    return v


def devig(o, u):
    def ip(a): return -a / (-a + 100) if a < 0 else 100 / (a + 100)
    a, b = ip(o), ip(u); return a / (a + b)


box = {}
def getbox(g):
    if g not in box:
        p = os.path.join(root, 'results', g + '.json'); box[g] = json.load(open(p)) if os.path.exists(p) else None
    return box[g]


rows = []
for (app, k), s in ser.items():
    if app == 'pinnacle':
        continue
    m = am[app].get(k)
    if not m or (app == 'prizepicks' and m.get('odds') != 'standard'):
        continue
    stat = (PP_STAT if app == 'prizepicks' else UD_STAT).get(m.get('stat'))
    if stat not in PIN_STAT.values():
        continue
    tip = m.get('start'); team = m.get('team')
    pid = name_pid.get((name_key(m['player']), team)); gid = team_game.get((team, tip))
    if not pid or not gid:
        continue
    tip = games[gid]; b = getbox(gid)
    if b is None:
        continue
    st = b.get(str(pid)); y = None if not st else sum(st.get(c, 0) for c in STAT_COL[stat])
    P = pin.get((name_key(m['player']), stat, tip)) or next((v for (n, s2, t0), v in pin.items() if n == name_key(m['player']) and s2 == stat and abs(t0 - tip) <= 900), None)
    if not P or 'Over' not in P or 'Under' not in P:
        continue
    for h in DECIDE_H:
        td = tip - h * 3600
        a = at(s, td); po, pu = at(P['Over'], td), at(P['Under'], td)
        a1 = at([x for x in s if x[0] < tip], tip); po1 = at(P['Over'], tip)
        if a is None or po is None or pu is None or po[0] != pu[0]:
            continue
        try:
            row = {'app': app, 'pid': pid, 'name': m['player'], 'gid': gid, 'tip': tip, 'stat': stat, 'h': h, 'y': y,
                   'line_d': a[0], 'v_d': a[1:], 'pin_line_d': po[0], 'pin_over_d': round(devig(po[1], pu[1]), 4),
                   'line_c': a1[0] if a1 else None, 'pin_line_c': po1[0] if po1 else None}
        except Exception:
            continue
        rows.append(row)
json.dump({'rows': rows}, open(out, 'w'), separators=(',', ':'))
print(len(rows))
