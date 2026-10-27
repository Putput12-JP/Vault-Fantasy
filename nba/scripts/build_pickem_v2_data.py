#!/usr/bin/env python3
"""
Pick'em V2 backtest dataset: every pick'em app line we stored (PrizePicks, Underdog, Sleeper), one row per app quote, with the
last quote before tip, the Pinnacle / consensus close at the SAME line when one exists, and the settled result from the box score.

  python3 nba/scripts/build_pickem_v2_data.py <nba-data checkout> [out.json]

Nothing here is estimated: a field is stored or it is None. `fair_pin` is the de-vigged Pinnacle over chance at exactly the app's line
(propclose.json, the close of each game); `fair_mkt` is the stored consensus at exactly that line when there is no Pinnacle number.
The sharp close is a fair-price REFERENCE only; it is never a place to bet.
"""
import glob, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from nba_common import name_key
from prop_board import PP_STAT, UD_STAT, SL_STAT, extra_stat
from ledger import STAT_COL

root = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'data', 'pickem_v2_legs.json')
days = sorted(glob.glob(os.path.join(root, 'snapshots', '20*')))

# ---- who and which game: the ledger / pkn / minutes metas carry (pid, player, team, game, tip) ----
name_pid, games, team_game = {}, {}, {}
meta = {'prizepicks': {}, 'underdog': {}, 'sleeper': {}}
for d in days:
    for line in open(os.path.join(d, 'meta.jsonl')):
        r = json.loads(line); s = r.get('src')
        if s in meta:
            meta[s][r['k']] = r
        elif r.get('pid') and r.get('game') and r.get('player'):
            name_pid[(name_key(r['player']), r['team'])] = int(r['pid'])
            games[str(r['game'])] = r['tip']
            team_game[(r['team'], r['tip'])] = str(r['game'])
        if s and r.get('game') and r.get('tip') and r.get('team'):
            team_game[(r['team'], r['tip'])] = str(r['game']); games[str(r['game'])] = r['tip']

series = defaultdict(list)
for app in meta:
    for d in days:
        p = os.path.join(d, app + '.jsonl')
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line); series[(app, r['k'])].append((r['t'], r['v']))

close = {}
for d in days:
    p = os.path.join(d, 'propclose.json')
    if os.path.exists(p):
        for gid, x in json.load(open(p)).items():
            close[gid] = x
box = {}
def getbox(gid):
    if gid not in box:
        p = os.path.join(root, 'results', gid + '.json')
        box[gid] = json.load(open(p)) if os.path.exists(p) else None
    return box[gid]
season = {}
sp = os.path.join(root, 'season_types.json')
if os.path.exists(sp):
    season = json.load(open(sp))

rows, miss = [], defaultdict(int)
for (app, k), ser in series.items():
    m = meta[app].get(k)
    if not m:
        miss['nometa'] += 1; continue
    if app == 'prizepicks':
        stat = PP_STAT.get(m.get('stat')) or extra_stat(m.get('stat')); kind = m.get('odds'); tip = m.get('start')
    elif app == 'underdog':
        stat = UD_STAT.get(m.get('stat')) or extra_stat(m.get('stat')); kind = m.get('kind'); tip = m.get('start')
    else:
        stat = SL_STAT.get(m.get('stat')) or extra_stat(m.get('stat')); kind = m.get('kind'); tip = None
    if stat not in STAT_COL or stat not in ('pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra'):
        miss['stat'] += 1; continue
    team = m.get('team')
    pid = name_pid.get((name_key(m.get('player')), team))
    gid = team_game.get((team, tip)) if tip else None
    if not pid or not gid:
        miss['nojoin'] += 1; continue
    tip = games[gid]
    ser.sort()
    pre = [(t, v) for t, v in ser if t < tip]
    live = [(t, v) for t, v in pre if v is not None]
    if not live:
        miss['nopre'] += 1; continue
    t1, v1 = live[-1]; t0, v0 = live[0]
    b = getbox(gid)
    if b is None:
        miss['nobox'] += 1; continue
    st = b.get(str(pid))
    y = None if not st else sum(st.get(c, 0) for c in STAT_COL[stat])
    row = {'app': app, 'kind': kind, 'pid': pid, 'name': m['player'], 'team': team, 'gid': gid, 'tip': tip, 'stat': stat,
           'line': v1[0], 'line0': v0[0], 't_last': t1, 't_first': t0, 'v': v1[1:], 'y': y,
           'preseason': bool(season) and str(season.get(gid, season.get(str(gid), ''))).lower().startswith('pre')}
    c = (close.get(gid) or {}).get('props', {}).get(f'{pid}|{stat}') or []
    for ln, p, src in c:
        if abs(ln - row['line']) < 1e-9:
            row['fair_' + ('pin' if src == 'pin' else 'mkt' if src == 'mkt' else 'kal')] = p
    row['pin_line'] = next((ln for ln, p, src in c if src == 'pin'), None)
    row['pin_p'] = next((p for ln, p, src in c if src == 'pin'), None)
    rows.append(row)
json.dump({'rows': rows, 'miss': miss, 'season_types_sample': list(season.items())[:3] if season else None}, open(out, 'w'), separators=(',', ':'))
print(len(rows), dict(miss))
