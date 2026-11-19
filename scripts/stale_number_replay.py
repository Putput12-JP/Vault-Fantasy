#!/usr/bin/env python3
"""
Stale number replay: the market moves a line, one soft book still hangs the old number.

Registered in docs/stale-number-prereg.md before any row was graded. Context only: not a bet signal, and nothing here counts toward an
agree total. Rules (do not tune to the output):
  signal   first time per game x market x direction that Pinnacle's line moved >= T pts vs its earliest quote in the previous 90 min,
           >= 2 other books moved the same way by >= 1 pt, and a soft book hangs a number >= 1 pt better than Pinnacle's new one.
  control  same, but Pinnacle moved < 0.5 pt in the window and a soft book is >= 1 pt off Pinnacle (pack reversion).
  score    line CLV in points = Pinnacle's last pre-kickoff line vs the stale number, in the side's favor. Juice is not converted.
Output: data/stale_number_record.json.
"""
import glob, json, math, os, time
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TAPE = os.environ.get('STALE_TAPE_DIR') or os.path.join(ROOT, 'data', 'book_tape')
OUT = os.environ.get('STALE_OUT') or os.path.join(ROOT, 'data', 'stale_number_record.json')
ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
THRS = (1.0, 2.0, 3.0)
WIN, FRESH, LEAD = 90 * 60, 30 * 60, 10 * 60
SOFT = ('DraftKings', 'FanDuel', 'BetMGM', 'bet365', 'BetRivers')
SKIP = ('Pinnacle', 'Consensus', 'Open')
MKS = {'sp': 1, 'tot': 2}    # key -> index into lim


def line(r, mk):
    if r.get('px') or r.get('bf'):
        return None
    q = r.get(mk)
    return q[0] if q and q[0] is not None else None


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


def favor(mk, dirn, stale, ref):
    """Points the stale number is better than ref, for the side. dirn +1 = line went up (home worse / over), -1 = went down.
    Spread line is the home number. A line that rose favors AWAY / over, which want a LOWER stale number; a fall favors home / under."""
    return (ref - stale) if dirn > 0 else (stale - ref)


def run(sport, now):
    cal = []
    games = defaultdict(list)
    for r in load(sport):
        k = game_key(r, sport)
        if k[0]:
            games[k].append(r)
    treat, ctrl = [], []
    for k, rs in games.items():
        start = max((r.get('start') or 0) for r in rs) or None
        if not start or start > now:
            continue
        rs.sort(key=lambda r: r['t'])
        for mk, li in MKS.items():
            pin = [r for r in rs if r['book'] == 'Pinnacle' and not r.get('bf') and line(r, mk) is not None and r['t'] <= start]
            if len(pin) < 2:
                continue
            close = line(pin[-1], mk)
            cal.append((k, mk, close))
            books = defaultdict(list)
            for r in rs:
                if r['book'] not in ('Consensus', 'Open', 'Pinnacle') and r['t'] <= start:
                    ln = line(r, mk)
                    if ln is not None:
                        books[r['book']].append((r['t'], ln, r.get(mk)))
            for bk, seq in books.items():
                BOOKSEQ[(k, mk, bk)] = seq
            fired = set()
            cfired = set()
            for r in pin:
                t = r['t']
                if t > start - LEAD:
                    break
                cur = line(r, mk)
                base = next((line(b, mk) for b in pin if t - WIN <= b['t'] < t), None)
                if base is None:
                    continue
                mv = cur - base
                # latest fresh line, and earliest in-window line, per other book
                now_l, old_l, q_l = {}, {}, {}
                for bk, seq in books.items():
                    late = [x for x in seq if t - FRESH <= x[0] <= t]
                    early = [x for x in seq if t - WIN <= x[0] < t]
                    if late and early:
                        now_l[bk], old_l[bk], q_l[bk] = late[-1][1], early[0][1], late[-1][2]
                lims = [(x['t'], x['lim'][li]) for x in pin if x.get('lim') and x['t'] <= t and x['lim'][li]]
                known = len(lims) >= 2 and lims[-1][0] - lims[0][0] >= 3 * 3600
                lim_up = bool(known and lims[-1][1] >= lims[0][1] * 1.5)
                # treatment: direction = sign of Pinnacle move
                if abs(mv) >= 1.0:
                    d = 1 if mv > 0 else -1
                    agree = sum(1 for bk in now_l if (now_l[bk] - old_l[bk]) * d >= 1.0)
                    for T in THRS:
                        if abs(mv) < T or (d, T) in fired:
                            continue
                        best = None
                        for bk in now_l:
                            if bk not in SOFT:
                                continue
                            ag = sum(1 for x in now_l if x != bk and (now_l[x] - old_l[x]) * d >= 1.0)
                            if ag < 2:
                                continue
                            gap = favor(mk, d, now_l[bk], cur)
                            if gap >= 1.0 and (best is None or gap > best[0]):
                                best = (gap, bk, now_l[bk], ag)
                        if best:
                            fired.add((d, T))
                            treat.append(mkrow(k, sport, mk, d, T, t, mv, best, close, known, lim_up, price_of(q_l.get(best[1]), mk, d)))
                # control: Pinnacle quiet
                elif abs(mv) < 0.5:
                    for bk in now_l:
                        if bk not in SOFT:
                            continue
                        for d in (1, -1):
                            gap = favor(mk, d, now_l[bk], cur)
                            if gap >= 1.0 and (bk, d) not in cfired:
                                cfired.add((bk, d))
                                ctrl.append(mkrow(k, sport, mk, d, 0, t, mv, (gap, bk, now_l[bk], 0), close, known, lim_up, price_of(q_l.get(bk), mk, d)))
    return treat, ctrl, cal


BOOKSEQ = {}


def price_of(q, mk, d):
    """Stored American price of the side taken: spread [line, home, away] (dir>0 takes away), total [line, over, under] (dir>0 takes over)."""
    if not q or len(q) < 3:
        return None
    i = (2 if d > 0 else 1) if mk == 'sp' else (1 if d > 0 else 2)
    return q[i]


def mkrow(k, sport, mk, d, T, t, mv, best, close, known, lim_up, price=None):
    gap, bk, stale, ag = best
    seq = BOOKSEQ.get((k, mk, bk), [])
    age = next((round((t - x[0]) / 60) for x in reversed(seq) if x[0] <= t), None)
    held = next((round((x[0] - t) / 60) for x in seq if x[0] > t and x[1] != stale), None)
    return {'price': price, 'close': close, 'age': age, 'held': held, 't': t, 'game': '|'.join(str(v) for v in k), 'sport': sport, 'mk': mk, 'dir': d, 'thr': T, 'move': round(mv, 2), 'book': bk, 'stale': stale,
            'edge': round(gap, 2), 'agree': ag, 'clv': round(favor(mk, d, stale, close), 2), 'limit_known': known, 'limit_up': lim_up}


def clustered(rows, key='clv'):
    by = defaultdict(list)
    for r in rows:
        by[r['game']].append(r[key])
    g = [sum(v) / len(v) for v in by.values()]
    n = len(g)
    if n == 0:
        return {'games': 0, 'rows': 0}
    m = sum(g) / n
    se = math.sqrt(sum((x - m) ** 2 for x in g) / (n - 1) / n) if n > 1 else None
    allv = [r[key] for r in rows]
    return {'games': n, 'rows': len(rows), 'mean': round(m, 3), 'ci95': round(1.96 * se, 3) if se is not None else None,
            'beat': round(sum(1 for x in allv if x > 0) / len(allv), 3), 'edge_mean': round(sum(r['edge'] for r in rows) / len(rows), 2)}


def diff(a, b):
    if 'mean' not in a or 'mean' not in b or a.get('ci95') is None or b.get('ci95') is None:
        return None
    se = math.sqrt((a['ci95'] / 1.96) ** 2 + (b['ci95'] / 1.96) ** 2)
    return {'delta': round(a['mean'] - b['mean'], 3), 'ci95': round(1.96 * se, 3)}


FINALS = os.environ.get('STALE_FINALS') or os.path.join(ROOT, 'data', 'exchange_edge_results.json')


def payout(a):
    return a / 100 if a > 0 else 100 / -a


def finals():
    try:
        return json.load(open(FINALS))
    except (OSError, ValueError):
        return {}


def residuals(cal, F):
    """Per market, the closing-line residuals e (both orientations) from every game with a stored final: spread = home margin plus the home closing
    number (and its negative), total = points minus the closing total (and its negative). docs/stale-number-price-prereg.md."""
    E = {'sp': [], 'tot': []}
    for k, mk, close in cal:
        f = F.get(k[0])
        if not f or f.get('home') is None or f.get('away') is None:
            continue
        e = (f['home'] - f['away'] + close) if mk == 'sp' else (f['home'] + f['away'] - close)
        E[mk] += [round(e, 6), round(-e, 6)]
    return E


def grade(row, F):
    """Realized profit per unit at the stored price, or None (no final, no stored price). Push returns the stake."""
    f = F.get(row['game'].split('|')[0])
    if not f or f.get('home') is None or row.get('price') is None:
        return None
    L = row['stale']
    if row['mk'] == 'sp':
        v = (f['home'] - f['away'] + L) * (-1 if row['dir'] > 0 else 1)    # dir>0 takes away; home covers when margin + line > 0
    else:
        v = (f['home'] + f['away'] - L) * (1 if row['dir'] > 0 else -1)    # dir>0 takes over
    return 0.0 if abs(v) < 1e-9 else payout(row['price']) if v > 0 else -1.0


def expected(row, E):
    es = E.get(row['mk']) or []
    if len(es) < 100 or row.get('price') is None:
        return None
    c, n = row['clv'], len(es)
    pw = sum(1 for e in es if e > -c + 1e-9) / n
    pl = sum(1 for e in es if e < -c - 1e-9) / n
    return pw * payout(row['price']) - pl


def clust2(rows, key):
    by = defaultdict(list)
    for r in rows:
        if r.get(key) is not None:
            by[r['game']].append(r[key])
    g = [sum(v) / len(v) for v in by.values()]
    n = len(g)
    if n == 0:
        return {'games': 0}
    m = sum(g) / n
    se = math.sqrt(sum((x - m) ** 2 for x in g) / (n - 1) / n) if n > 1 else None
    return {'games': n, 'rows': sum(len(v) for v in by.values()), 'mean': round(m, 4), 'ci95': round(1.96 * se, 4) if se is not None else None}


def main():
    now, res = time.time(), {}
    for sp in ('nfl', 'cfb', 'nba', 'cbb'):
        if not os.path.isdir(os.path.join(TAPE, sp)):
            continue
        treat, ctrl, cal = run(sp, now)
        F, E = finals(), None
        E = residuals(cal, F)
        for r in treat + ctrl:
            r['real'], r['exp'] = grade(r, F), expected(r, E)
        c = clustered(ctrl)
        out = {'control': c, 'cut': [], 'resid_n': {k: len(v) // 2 for k, v in E.items()},
               'priced_control': {'real': clust2(ctrl, 'real'), 'exp': clust2(ctrl, 'exp'), 'price_mean': round(sum(r['price'] for r in ctrl if r['price'] is not None) / max(1, sum(1 for r in ctrl if r['price'] is not None)), 1)}}
        for T in THRS:
            tt = [r for r in treat if r['thr'] == T]
            for tag, f in (('all', lambda r: True), ('market_sp', lambda r: r['mk'] == 'sp'), ('market_tot', lambda r: r['mk'] == 'tot'),
                           ('limit_up', lambda r: r['limit_up']), ('limit_known_flat', lambda r: r['limit_known'] and not r['limit_up'])):
                g = [r for r in tt if f(r)]
                s = clustered(g) if g else {'games': 0, 'rows': 0}
                pr = {'real': clust2(g, 'real'), 'exp': clust2(g, 'exp'), 'price_mean': round(sum(r['price'] for r in g if r['price'] is not None) / max(1, sum(1 for r in g if r['price'] is not None)), 1)}
                pr['real_vs_control'] = diff(pr['real'], out['priced_control']['real']) if g else None
                pr['exp_vs_control'] = diff(pr['exp'], out['priced_control']['exp']) if g else None
                out['cut'].append({'thr': T, 'tag': tag, **s, 'vs_control': diff(s, c) if g else None, 'priced': pr})
        for nm, rows in (('treat', [r for r in treat if r['thr'] == 2.0]), ('control', ctrl)):
            ages = sorted(r['age'] for r in rows if r['age'] is not None)
            held = sorted(r['held'] for r in rows if r['held'] is not None)
            out['diag_' + nm] = {'n': len(rows), 'age_med_min': ages[len(ages) // 2] if ages else None, 'held_med_min': held[len(held) // 2] if held else None,
                                 'never_moved': round(sum(1 for r in rows if r['held'] is None) / len(rows), 2) if rows else None}
        out['recent'] = sorted([r for r in treat if r['thr'] == 2.0], key=lambda r: -r['t'])[:30]
        res[sp] = out
    json.dump({'generated': int(now), 'by_sport': res, 'prereg': 'docs/stale-number-prereg.md', 'note': 'context only, not a bet signal'}, open(OUT, 'w'), separators=(',', ':'))
    for sp, v in res.items():
        print(sp, 'control', v['control'], v.get('diag_control'), 'treat', v.get('diag_treat'))
        for s in v['cut']:
            if s['tag'] in ('all', 'limit_up') or s['thr'] == 2.0:
                print('  ', s['thr'], s['tag'], {k: s.get(k) for k in ('games', 'rows', 'mean', 'ci95', 'beat', 'edge_mean', 'vs_control')})
                if s['tag'] in ('all', 'limit_up') and s['thr'] in (1.0, 2.0):
                    print('      priced', json.dumps(s['priced']))


if __name__ == '__main__':
    main()
