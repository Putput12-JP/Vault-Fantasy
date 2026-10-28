#!/usr/bin/env python3
"""Part B of docs/minutes-autopsy-and-implied.md (rule committed before this ran). Reads the nba-data branch (git show), no network.
  python3 nba/scripts/test_minutes_implied.py
Deviation from the registered text: GP minutes are logged from 2026-10-29, so the live days carry v2 minutes only; v2 minutes and the v2-priced projection (psim mu) are used."""
import json, os, statistics as st, subprocess
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = ['2026-10-%02d' % d for d in range(20, 29)]; STATS = ['pts', 'reb', 'ast', '3pm']
def show(p):
    r = subprocess.run(['git', 'show', 'origin/nba-data:' + p], capture_output=True, text=True, cwd=HERE)
    return r.stdout if r.returncode == 0 else ''
def last_rows(day, f):
    o = {}
    for l in show('snapshots/%s/%s.jsonl' % (day, f)).splitlines():
        try: j = json.loads(l)
        except Exception: continue
        if j['v'] is not None: o[j['k']] = j['v']      # null rows are clears; the last real value is what was priced
    return o
def median_line(pts):
    pts = sorted((a, b) for a, b, _ in pts)
    for (l0, p0), (l1, p1) in zip(pts, pts[1:]):
        if p0 >= .5 > p1: return l0 + (p0 - .5) / (p0 - p1) * (l1 - l0)
    return None
rows, seen = [], set()
for day in DAYS:
    pc = json.loads(show('snapshots/%s/propclose.json' % day) or '{}'); mn = last_rows(day, 'minutes'); ps = last_rows(day, 'psim')
    for gid, g in pc.items():
        if gid in seen: continue
        res = show('results/%s.json' % gid)
        if not res: continue
        res = json.loads(res); seen.add(gid)
        pids = {k.split('|')[0] for k in g['props']}
        for pid in pids:
            m = mn.get('%s|%s' % (gid, pid)); a = (res.get(pid) or {}).get('minutes')
            if not m or a is None or not m[0]: continue
            q = []
            for s in STATS:
                ml = median_line(g['props'].get('%s|%s' % (pid, s), [])); pv = ps.get('%s|%s|%s' % (gid, pid, s))
                if ml and pv and pv[1] > 0.3: q.append(ml / pv[1])
            if len(q) >= 2: rows.append({'gid': gid, 'pid': pid, 'v2': m[0], 'act': a, 'gap': m[0] * st.median(q) - m[0], 'err': a - m[0], 'nst': len(q)})
def ols(r):
    x = [z['gap'] for z in r]; y = [z['err'] for z in r]; mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x); b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx; a0 = my - b * mx
    g = defaultdict(float)
    for z in r: g[z['gid']] += (z['gap'] - mx) * (z['err'] - a0 - b * z['gap'])
    se = (sum(v * v for v in g.values()) ** .5) / sxx
    return b, b / se if se else 0
played = [r for r in rows if r['act'] > 0]
b, t = ols(played); s = sorted(played, key=lambda z: z['gap']); k = max(1, len(s) // 10)
dec = lambda xs: (st.mean(z['gap'] for z in xs), st.mean(z['err'] for z in xs))
out = {'rows': len(rows), 'played': len(played), 'games': len({r['gid'] for r in rows}), 'dnp': len(rows) - len(played), 'slope': b, 'cluster_t': t,
       'bottom_decile_gap_err': dec(s[:k]), 'top_decile_gap_err': dec(s[-k:]), 'corr': st.correlation([z['gap'] for z in played], [z['err'] for z in played])}
out['rule'] = {'n_ok': len(played) >= 300, 'slope_pos_t2': b > 0 and t >= 2,
               'deciles_same_sign': out['top_decile_gap_err'][0] > 0 < out['top_decile_gap_err'][1] and out['bottom_decile_gap_err'][0] < 0 > out['bottom_decile_gap_err'][1]}
json.dump(out, open(os.path.join(HERE, '..', 'data', 'minutes_implied.json'), 'w'), indent=1); print(json.dumps(out, indent=1))
