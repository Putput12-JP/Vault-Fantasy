#!/usr/bin/env python3
"""
Lean backfill (docs/lean-tracking.md, "Data and history"): the leans of regular-season games that finished BEFORE lean_record.py existed.

Source: the Props Simulation record ('psim'), which the recorder wrote live, before tip, for pts / reb / ast / 3pm. Each row holds the model's
calibrated P(over) at the main line (p_exact), mu, and the price's no-vig P(over). So these are real as-of rows, not a replay and not priced
with today's model files. What it is NOT: it has only the 4 stats the psim records (no combos), only the last 3 hours before tip (so the
close clock only; the first clock is not available), no sd, no stored price of the side (units are null), and no starter flag.

Left out on purpose: rows with meta 'replay' (BOS @ DET: rebuilt after the fact from stored prices with the model files on hand, not as-of),
and preseason games. Output: nba/data/lean_backfill.json in the same row format as lean_record.COLS, plus 'through' (the last tip included).
The forward record (leans/<day>.json on the nba-data branch) is the only one with a headline; this file is shown apart, labelled.

  python3 nba/scripts/backfill_leans.py --dir=<nba-data checkout> [--write]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ledger as L
import lean_record as LR

OUT = os.path.join(HERE, '..', 'data', 'lean_backfill.json')
START = '2026-10-19'          # first folder with regular-season psim rows (day folders are read one day back for tips just after midnight)


def build(root, now):
    pre = L.preseason_games(root)
    games = {}
    n_replay = n_pre = 0
    for k, x in L.load_src(root, 'psim', START).items():
        m = x['meta']
        if not m:
            continue
        if m.get('replay'):
            n_replay += 1
            continue
        if str(m['game']) in pre:
            n_pre += 1
            continue
        rows = [v for t, v in sorted(x['series'], key=lambda z: (z[0], z[1] is None)) if v is not None and t < m['tip']]
        if rows:
            games.setdefault(str(m['game']), []).append((m, rows[-1]))
    out, g_meta = [], {}
    for gid, items in games.items():
        bx = L.box(root, gid)
        if bx is None:
            continue
        for m, v in items:
            line, mu, p, _, _, pm, src = v
            if p == 0.5:
                continue
            side = 'O' if p > 0.5 else 'U'
            st = bx.get(int(m['pid']))
            y = sum(st.get(c, 0) for c in L.STAT_COL[m['stat']]) if st else None
            res = 'V' if y is None else LR.grade(side, line, y)
            g_meta[gid] = [m['matchup'], m['tip']]
            out.append([gid, m['pid'], m['player'], m['team'], m['stat'], 'c', line, mu, None, p, side, None, pm, m.get('min'), None, None, None,
                        m.get('held'), 0, y, res, None])
    out.sort(key=lambda r: (g_meta[r[0]][1], r[0], r[2], r[4]))
    return {'about': 'psim-derived backfill: see nba/scripts/backfill_leans.py', 'cols': LR.COLS, 'games': g_meta, 'rows': out,
            'through': max((v[1] for v in g_meta.values()), default=None), 'left_out': {'replay_keys': n_replay, 'preseason_keys': n_pre}}


if __name__ == '__main__':
    a = {x.split('=')[0]: (x.split('=') + [None])[1] for x in sys.argv[1:]}
    d = build(a['--dir'], int(__import__('time').time()))
    rows = d['rows']
    live = [r for r in rows if not r[17] and r[20] in ('W', 'L')]
    print(len(d['games']), 'games', len(rows), 'rows,', len(live), 'graded and not held; left out:', d['left_out'])
    from collections import Counter
    print('result by held:', Counter((bool(r[17]), r[20]) for r in rows))
    if '--write' in sys.argv:
        json.dump(d, open(OUT, 'w'), separators=(',', ':'))
        print('wrote', os.path.getsize(OUT) // 1024, 'KB')
