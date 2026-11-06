#!/usr/bin/env python3
"""
snapshots/<day>/prophist.json: each player prop's DraftKings line and prices as they moved today, for the Props page's
line-movement chart. Built from the day's espn.jsonl (the recorder already logs every change) and meta.jsonl.

  {"t": <written>, "p": {"<athlete id>|<stat>": [[t, line, over, under], ...]}}

Only main-line player props (ESPN types below), only rows where something changed, oldest first. The page reads the
game day's folder and the day before (a prop can post the evening before) and joins the two.

  python3 nba/scripts/prop_hist.py <nba-data>/snapshots/2026-11-06      # write one day by hand
"""
import json, os, sys, time

# ESPN / DraftKings prop type id -> the page's stat key
TYPES = {'1': 'pts', '2': 'ast', '3': 'reb', '4': '3pm', '5': 'stl', '6': 'blk', '87': 'pa', '88': 'pr', '89': 'ra', '90': 'pra'}


def build(day_dir):
    """-> {'pid|stat': [[t, line, over, under], ...]} for one day folder."""
    mp, lp = os.path.join(day_dir, 'meta.jsonl'), os.path.join(day_dir, 'espn.jsonl')
    if not (os.path.exists(mp) and os.path.exists(lp)):
        return {}
    keys = {}
    for line in open(mp):
        if 'athlete_id' not in line or 'espn' not in line:
            continue
        try:
            m = json.loads(line)
            if m.get('src') != 'espn':
                continue
            parts = m['k'].split('|')
            st = TYPES.get(parts[3])
            if st and parts[4] in ('0', '1'):
                keys[m['k']] = (f"{m['athlete_id']}|{st}", int(parts[4]))
        except (ValueError, KeyError, IndexError):
            continue
    cur, out = {}, {}
    for line in open(lp):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        k = keys.get(r.get('k'))
        if not k:
            continue
        pk, side = k
        state = cur.setdefault(pk, [None, None])
        state[side] = r.get('v')                       # [line, price] or None once pulled
        o, u = state
        if not o:
            continue
        row = [r['t'], o[0], o[1], u[1] if u else None]
        ser = out.setdefault(pk, [])
        if ser and ser[-1][0] == row[0]:              # both sides of one poll: keep the poll's final state, not the half-updated one
            ser.pop()
        if not ser or ser[-1][1:] != row[1:]:
            ser.append(row)
    return out


def write(day_dir, now=None):
    """Write prophist.json when it changed. -> number of props, or None when there is nothing to write."""
    p = build(day_dir)
    if not p:
        return None
    path = os.path.join(day_dir, 'prophist.json')
    try:
        old = json.load(open(path)).get('p')
    except (OSError, ValueError):
        old = None
    if p != old:
        tmp = path + '.tmp'
        json.dump({'t': int(now or time.time()), 'p': p}, open(tmp, 'w'), separators=(',', ':'))
        os.replace(tmp, path)
    return len(p)


if __name__ == '__main__':
    for d in sys.argv[1:]:
        print(d, write(d))
