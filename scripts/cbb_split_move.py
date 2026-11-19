#!/usr/bin/env python3
"""
CBB "money vs bets, and the line moved their way" forward test. Registration: docs/cbb-split-move-prereg.md (read it first).
Context only: not a bet signal, never feeds Top Reads, SM_GATE or an agree total.

  python3 scripts/cbb_split_move.py log    --data sharp-out/data.json   freeze a lock row for each CBB game 30 to 90 minutes before tip
  python3 scripts/cbb_split_move.py settle --data sharp-out/data.json   grade frozen rows from final scores and the Pinnacle close in the tape
  python3 scripts/cbb_split_move.py report                              write data/cbb_split_move_record.json (cells, bootstrap intervals)

Every definition below is fixed by the prereg. Do not tune any of them to a result. A change is a new dated registration.

Row, frozen at the first run inside the lock window (nothing in a frozen row is ever overwritten; only "result" is added):
  gk, away, home, start, lock_t
  sp  {line (home spread), home_px, away_px, open_line, pin_line, splits {home:{t,m}, away:{t,m}}}   consensus, from the sharp-data file
  tot {line, over_px, under_px, open_line, splits {over:{t,m}, under:{t,m}}}
  cell_sp / cell_tot  treat | split_only | move_only | none | nosplit, with the side and the numbers that put it there
"""
import argparse, glob, json, os, random, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG = os.environ.get('CBB_SM_LOG') or os.path.join(ROOT, 'data', 'cbb_split_move.json')
REC = os.environ.get('CBB_SM_REC') or os.path.join(ROOT, 'data', 'cbb_split_move_record.json')
TAPE = os.environ.get('CBB_SM_TAPE') or os.path.join(ROOT, 'data', 'book_tape', 'cbb')
URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/sharp-data/data.json'
REGISTERED_FROM = 1795154400   # 2026-11-20 00:00 CT (06:00 UTC): only locks at or after this count; the registration commit resets it if it lands later
VERSION = 1

# ---- fixed by the prereg ----
LOCK_MIN, LOCK_MAX = 30 * 60, 90 * 60     # lock window, seconds before tip
GAP = 20          # money share minus bets share, points, on the side
MAX_TICKETS = 45  # the side holds at most this share of bets
MOVE = 1.0        # line moved this many points toward the side since the open
CTRL_GAP = 10     # move_only: the side the line moved toward has a gap under this
RLM_BETS = 70     # totals: one side holds at least this share of bets
SEED, BOOT = 20261119, 10000


def load(src):
    if src.startswith('http'):
        return json.loads(subprocess.run(['curl', '-s', '--compressed', '--max-time', '60', src], capture_output=True, check=True).stdout)
    return json.load(open(src))


def read_log():
    try:
        return json.load(open(LOG))
    except Exception:
        return {'version': VERSION, 'rows': {}}


def write_log(d):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    tmp = LOG + '.tmp'
    json.dump(d, open(tmp, 'w'), separators=(',', ':'), sort_keys=True)
    os.replace(tmp, LOG)


def gap(sp):
    return None if not sp or sp.get('t') is None or sp.get('m') is None else sp['m'] - sp['t']


def classify_spread(row):
    """Spread cell. Side line = points the side receives (away = -home line). 'Toward' = the side's number got worse for backers."""
    s = row['sp']
    if s['line'] is None or s['open_line'] is None or not s['splits'] or not s['splits'].get('home') or not s['splits'].get('away'):
        return {'cell': 'nosplit'}
    out = None
    for side in ('home', 'away'):
        sg = 1 if side == 'home' else -1
        toward = (sg * s['open_line']) - (sg * s['line'])      # side line at the open minus now; home side line = home spread, away = its negative
        g, t = gap(s['splits'][side]), s['splits'][side]['t']
        if g is None:
            return {'cell': 'nosplit'}
        info = {'side': side, 'gap': g, 'tickets': t, 'toward': toward, 'side_line_now': sg * s['line']}
        if g >= GAP and t <= MAX_TICKETS:
            info['cell'] = 'treat' if toward >= MOVE else 'split_only'
            return info
        if toward >= MOVE and g < CTRL_GAP:
            out = dict(info, cell='move_only')
    return out or {'cell': 'none'}


def classify_total(row):
    """Totals reverse line move: one side has RLM_BETS+ of bets and the line moved MOVE+ toward the OTHER side. Secondary, one cell only."""
    t = row['tot']
    if t['line'] is None or t['open_line'] is None or not t['splits'] or not t['splits'].get('over'):
        return {'cell': 'nosplit'}
    ob, ub = t['splits']['over']['t'], t['splits']['under']['t']
    if ob is None or ub is None:
        return {'cell': 'nosplit'}
    d = t['line'] - t['open_line']          # + = line went up = toward the over
    if ob >= RLM_BETS and d <= -MOVE:
        return {'cell': 'rlm', 'side': 'under', 'bets_on_other': ob, 'moved': d}
    if ub >= RLM_BETS and d >= MOVE:
        return {'cell': 'rlm', 'side': 'over', 'bets_on_other': ub, 'moved': d}
    return {'cell': 'none'}


def ab(t):
    return t.get('abbr') if isinstance(t, dict) else t


def snap(g, now):
    c, o, p, sp = g.get('consensus') or {}, g.get('open') or {}, g.get('pin') or {}, g.get('splits') or {}
    cs, os_, ps = c.get('sp') or {}, o.get('sp') or {}, p.get('sp') or {}
    ct, ot = c.get('tot') or {}, o.get('tot') or {}
    row = {'gk': g['key'], 'away': ab(g['away']), 'home': ab(g['home']), 'start': g['start'], 'lock_t': now, 'v': VERSION,
           'counts': now >= REGISTERED_FROM,
           'sp': {'line': cs.get('line'), 'home_px': cs.get('home'), 'away_px': cs.get('away'), 'open_line': os_.get('line'),
                  'pin_line': ps.get('line'), 'splits': sp.get('sp')},
           'tot': {'line': ct.get('line'), 'over_px': ct.get('over'), 'under_px': ct.get('under'), 'open_line': ot.get('line'),
                   'pin_line': (p.get('tot') or {}).get('line'), 'splits': sp.get('tot')}}
    row['cell_sp'], row['cell_tot'] = classify_spread(row), classify_total(row)
    return row


def do_log(data):
    now = int(time.time())
    d, n = read_log(), 0
    for g in data['games']:
        if g.get('sport') != 'cbb' or g['key'] in d['rows']:
            continue
        ttk = g['start'] - now
        if not LOCK_MIN <= ttk <= LOCK_MAX or g.get('status') not in (None, 'scheduled', 'pre'):
            continue
        d['rows'][g['key']] = snap(g, now)
        n += 1
    write_log(d)
    print(f'locked {n} new CBB games; log holds {len(d["rows"])}')


def pin_close(gk, start):
    """Pinnacle's last spread/total line at or before tip, from the tape; [home spread line, total line] or None."""
    last = None
    for f in sorted(glob.glob(os.path.join(TAPE, '*.jsonl'))):
        for ln in open(f):
            if f'"{gk}"' not in ln:
                continue
            r = json.loads(ln)
            if r.get('gk') == gk and r.get('book') == 'Pinnacle' and r['t'] <= start and (last is None or r['t'] >= last['t']):
                last = r
    if not last:
        return None
    return [last['sp'][0] if last.get('sp') else None, last['tot'][0] if last.get('tot') else None]


def amer(px):
    return None if px is None else (px / 100 if px > 0 else 100 / -px)      # profit per 1u on a win


def grade(line_side, px, margin):
    """margin = side score - other score. Returns (result, units) at the frozen number and price."""
    v = margin + line_side
    if v == 0:
        return 'P', 0.0
    return ('W', amer(px)) if v > 0 else ('L', -1.0)


def do_settle(data):
    d, fin, n = read_log(), {g['key']: g.get('final') for g in data['games'] if g.get('final')}, 0
    for gk, r in d['rows'].items():
        if r.get('result') or gk not in fin:
            continue
        h, a = fin[gk]['home'], fin[gk]['away']
        res = {'final': [a, h]}
        cs = r['cell_sp']
        if cs.get('cell') in ('treat', 'split_only', 'move_only') and r['sp']['line'] is not None:
            side = cs['side']
            sg, m = (1, h - a) if side == 'home' else (-1, a - h)
            px = r['sp']['home_px'] if side == 'home' else r['sp']['away_px']
            if px is not None:
                res['sp'], res['sp_units'] = grade(sg * r['sp']['line'], px, m)
        ct = r['cell_tot']
        if ct.get('cell') == 'rlm' and r['tot']['line'] is not None:
            tot = h + a
            px = r['tot']['over_px'] if ct['side'] == 'over' else r['tot']['under_px']
            if px is not None:
                v = (tot - r['tot']['line']) if ct['side'] == 'over' else (r['tot']['line'] - tot)
                res['tot'], res['tot_units'] = ('P', 0.0) if v == 0 else (('W', amer(px)) if v > 0 else ('L', -1.0))
        pc = pin_close(gk, r['start'])
        if pc and cs.get('side') and r['sp']['pin_line'] is not None and pc[0] is not None:
            sg = 1 if cs['side'] == 'home' else -1
            res['sp_clv'] = sg * r['sp']['pin_line'] - sg * pc[0]       # points received at the lock minus at the close, same book; + = follower beat the close
        if pc and ct.get('side') and r['tot']['pin_line'] is not None and pc[1] is not None:
            res['tot_clv'] = (pc[1] - r['tot']['pin_line']) if ct['side'] == 'over' else (r['tot']['pin_line'] - pc[1])
        r['result'] = res
        n += 1
    write_log(d)
    print(f'settled {n} games')


def boot(vals, rng):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    ms = []
    for _ in range(BOOT):
        s = [vals[rng.randrange(len(vals))] for _ in vals]
        ms.append(sum(s) / len(s))
    ms.sort()
    return [round(ms[int(.025 * BOOT)], 4), round(ms[int(.975 * BOOT)], 4)]


def cell_stats(rows, mk, rng):
    u = [r['result'].get(mk + '_units') for r in rows if r.get('result') and mk + '_units' in r['result']]
    w = sum(1 for r in rows if r.get('result', {}).get(mk) == 'W')
    l = sum(1 for r in rows if r.get('result', {}).get(mk) == 'L')
    p = sum(1 for r in rows if r.get('result', {}).get(mk) == 'P')
    clv = [r['result'].get(mk + '_clv') for r in rows if r.get('result') and r['result'].get(mk + '_clv') is not None]
    return {'logged': len(rows), 'graded': len(u), 'w': w, 'l': l, 'p': p,
            'roi': round(sum(u) / len(u), 4) if u else None, 'roi_ci95': boot(u, rng) if u else None,
            'clv_n': len(clv), 'clv_mean': round(sum(clv) / len(clv), 4) if clv else None, 'clv_ci95': boot(clv, rng) if clv else None}


def do_report():
    d, rng = read_log(), random.Random(SEED)
    rows = [r for r in d['rows'].values() if r.get('counts')]
    out = {'generated': int(time.time()), 'prereg': 'docs/cbb-split-move-prereg.md', 'locked_counted': len(rows),
           'locked_not_counted': len(d['rows']) - len(rows), 'spread': {}, 'total': {}}
    for c in ('treat', 'split_only', 'move_only'):
        out['spread'][c] = cell_stats([r for r in rows if r['cell_sp'].get('cell') == c], 'sp', rng)
    out['spread']['none'] = sum(1 for r in rows if r['cell_sp'].get('cell') == 'none')
    out['spread']['nosplit'] = sum(1 for r in rows if r['cell_sp'].get('cell') == 'nosplit')
    out['total']['rlm'] = cell_stats([r for r in rows if r['cell_tot'].get('cell') == 'rlm'], 'tot', rng)
    json.dump(out, open(REC, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('log', 'settle', 'report'))
    ap.add_argument('--data', default=URL)
    a = ap.parse_args()
    if a.mode == 'report':
        do_report()
    else:
        (do_log if a.mode == 'log' else do_settle)(load(a.data))
