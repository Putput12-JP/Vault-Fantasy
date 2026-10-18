#!/usr/bin/env python3
"""
Pinnacle steam record: when Pinnacle's price moves at a fixed line, does it keep going, and was a soft book still at the old price.

Replayed from the book tape (data/book_tape/<sport>/*.jsonl), so it needs no extra logging. Context only: not a bet signal,
and nothing here counts toward an agree total.

Definitions, fixed before any result was looked at (do not tune them to the output):
  fair    Pinnacle's price with the vig removed (power method, same as exchange_edge_record.py), for the side
  signal  the first time, per game market side, Pinnacle's fair rises by T points (T = 1, 2, 3) against its earliest stored
          quote in the previous 24 hours AT THE SAME LINE. A line change is not a price move and is skipped.
  limit   limit_up is true only when two stored Pinnacle limits for that market exist, 3+ hours apart, and the later one is
          50%+ higher. Limits are stored on few rows (most games have none), so limit_known counts how often it can be judged.
  soft    the best stored price for the side at Pinnacle's line from DraftKings, FanDuel or BetMGM at the signal, with its own
          stored quote used as is. soft_ev = fair_now / soft price - 1. Null when no soft book is at that line.
  close   Pinnacle's last quote before kickoff. Graded only when its line equals the signal's line.
  cont    close fair - signal fair, in points, for the side (positive = Pinnacle kept moving the same way)
  clv     close fair - soft cost, in points, only when a soft price existed
Only games that have started are graded. Output: data/steam_record.json, by_sport[<sport>] = {summary, recent}.
"""
import glob, json, math, os, time
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TAPE = os.environ.get('STEAM_TAPE_DIR') or os.path.join(ROOT, 'data', 'book_tape')
OUT = os.environ.get('STEAM_OUT') or os.path.join(ROOT, 'data', 'steam_record.json')
ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
THRS = (1.0, 2.0, 3.0)
WIN, LIM_GAP, LIM_UP = 24 * 3600, 3 * 3600, 1.5
SOFT = ('DraftKings', 'FanDuel', 'BetMGM')
MK = {'ml': (0, 1), 'sp': (1, 2), 'tot': (1, 2)}   # price slots; ml is [away, home], sp [line, home, away], tot [line, over, under]


def pfn(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def fair_first(a, b):
    x, y, lo, hi = pfn(a), pfn(b), 0.5, 3.0
    for _ in range(40):
        k = (lo + hi) / 2
        if x ** k + y ** k > 1:
            lo = k
        else:
            hi = k
    return x ** ((lo + hi) / 2)


def prices(r, mk):
    q = r.get(mk)
    if not q or r.get('px') or r.get('bf'):
        return None
    i, j = MK[mk]
    if q[i] is None or q[j] is None or (mk != 'ml' and q[0] is None):
        return None
    return q[0] if mk != 'ml' else None, q[i], q[j]


def side_fair(r, mk, side):
    p = prices(r, mk)
    if not p:
        return None
    a, b = (p[1], p[2]) if side == 0 else (p[2], p[1])
    return fair_first(a, b), p[0]


def load(sport):
    rows = []
    for f in sorted(glob.glob(os.path.join(TAPE, sport, '*.jsonl'))):
        for l in open(f):
            if l.strip():
                try:
                    rows.append(json.loads(l))
                except ValueError:
                    pass
    return rows


def game_key(r, sport):
    if sport == 'nfl':
        a, h = ALIAS.get(r.get('away'), r.get('away')), ALIAS.get(r.get('home'), r.get('home'))
        return (a, h, round(r.get('start', 0) / 21600))
    return (r.get('gk'),)


def run(sport, now):
    games = defaultdict(list)
    for r in load(sport):
        k = game_key(r, sport)
        if k[0]:
            games[k].append(r)
    sig = []
    for k, rs in games.items():
        start = max((r.get('start') or 0) for r in rs) or None
        pin = sorted((r for r in rs if r['book'] == 'Pinnacle' and not r.get('bf')), key=lambda r: r['t'])
        if not start or start > now or len(pin) < 2:
            continue
        pre = [r for r in pin if r['t'] <= start]
        if len(pre) < 2:
            continue
        for mk in MK:
            for side in (0, 1):
                seen = set()
                close = side_fair(pre[-1], mk, side)
                for r in pre[:-1]:
                    cur = side_fair(r, mk, side)
                    if not cur:
                        continue
                    base = None
                    for b in pre:
                        if b['t'] >= r['t']:
                            break
                        sb = side_fair(b, mk, side)
                        if sb and r['t'] - b['t'] <= WIN and sb[1] == cur[1]:
                            base = sb
                            break
                    if not base:
                        continue
                    mv = (cur[0] - base[0]) * 100
                    for T in THRS:
                        if mv >= T and T not in seen:
                            seen.add(T)
                            sig.append(grade(rs, pre, r, mk, side, T, mv, cur, close, k))
    out = [s for s in sig if s]
    return summarise(out), sorted(out, key=lambda s: -s['t'])[:40]


def grade(rs, pre, r, mk, side, T, mv, cur, close, k):
    lims = [(x['t'], x['lim'][{'ml': 0, 'sp': 1, 'tot': 2}[mk]]) for x in pre if x.get('lim') and x['t'] <= r['t'] and x['lim'][{'ml': 0, 'sp': 1, 'tot': 2}[mk]]]
    known = len(lims) >= 2 and lims[-1][0] - lims[0][0] >= LIM_GAP
    limit_up = bool(known and lims[-1][1] >= lims[0][1] * LIM_UP)
    soft = None
    best = {}
    for x in rs:
        if x['book'] in SOFT and x['t'] <= r['t']:
            best[x['book']] = x
    for x in best.values():
        p = prices(x, mk)
        if p and p[0] == cur[1]:
            a = p[1] if side == 0 else p[2]
            cost = pfn(a)
            soft = cost if soft is None else min(soft, cost)
    row = {'t': r['t'], 'game': '|'.join(str(v) for v in k), 'mk': mk, 'side': side, 'thr': T, 'move': round(mv, 2), 'limit_known': known, 'limit_up': limit_up,
           'soft_ev': round((cur[0] / soft - 1) * 100, 2) if soft else None}
    if close and close[1] == cur[1]:
        row['cont'] = round((close[0] - cur[0]) * 100, 2)
        row['clv'] = round((close[0] - soft) * 100, 2) if soft else None
    return row


def stats(xs):
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if not n:
        return {'n': 0}
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    return {'n': n, 'mean': round(m, 2), 'ci95': round(1.96 * sd / math.sqrt(n), 2) if sd is not None else None, 'pos': round(sum(1 for x in xs if x > 0) / n, 2)}


def summarise(sig):
    out = []
    for T in THRS:
        for tag, f in (('all', lambda s: True), ('limit_up', lambda s: s['limit_up']), ('limit_flat', lambda s: s['limit_known'] and not s['limit_up']), ('limit_unknown', lambda s: not s['limit_known'])):
            g = [s for s in sig if s['thr'] == T and f(s)]
            out.append({'thr': T, 'tag': tag, 'signals': len(g), 'graded': len([s for s in g if 'cont' in s]), 'cont': stats([s.get('cont') for s in g]),
                        'clv': stats([s.get('clv') for s in g]), 'soft_ev_mean': stats([s.get('soft_ev') for s in g]).get('mean')})
    return out


def main():
    now, res = time.time(), {}
    for sp in ('nfl', 'cfb', 'nba'):
        if os.path.isdir(os.path.join(TAPE, sp)):
            s, recent = run(sp, now)
            res[sp] = {'summary': s, 'recent': recent}
    json.dump({'generated': int(now), 'by_sport': res, 'note': 'context only, not a bet signal'}, open(OUT, 'w'), separators=(',', ':'))
    for sp, v in res.items():
        for s in v['summary']:
            if s['tag'] in ('all', 'limit_up'):
                print(sp, s['thr'], s['tag'], 'signals', s['signals'], 'graded', s['graded'], 'cont', s['cont'], 'clv', s['clv'])


if __name__ == '__main__':
    main()
