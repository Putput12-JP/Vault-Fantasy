#!/usr/bin/env python3
"""
Novig edge record, per sport: how often Novig's price, when it sits above Pinnacle's no-vig fair price, beats where Pinnacle closes.

Everything is replayed from the book tape (data/book_tape/nfl/*.jsonl), so it needs no extra logging and cannot drift from the
chart's numbers. The tape holds Pinnacle's lines and prices and Novig's bid/ask (px for the winner market, nsp and ntot for the
spread and total at Pinnacle's line), each appended when it changes. Novig quotes were first stored on 2026-10-17, so there is
no earlier history and none is invented.

Definitions, fixed before any result was looked at (do not tune them to the output):
  fair   Pinnacle's price with the vig removed (power method, as in fetch-sharp-money.mjs), for the side
  cost   what buying that side at Novig costs: its ask, which is 1 minus the best bid on the other outcome
  EV     fair / cost - 1, pregame, no exchange fee (Novig charges only when live)
  signal the first time a game's market side reaches EV >= 1%, >= 2%, >= 4% (each threshold counted once per game side)
  stale  at the signal, Pinnacle's fair for the side is up 1.0+ points over the previous 4 hours while Novig's mid moved
         less than 0.5 points: "Pinnacle moved, Novig has not"
  close  Pinnacle's last quote before kickoff
  CLV    close fair - cost, in points, only when Pinnacle's line at the close equals the line at the signal. A line that
         moved is counted separately (line_moved, and whether it moved in the side's favour), never converted to a price.
Only games that have started are graded. Nothing here counts toward an agree total and it is not a bet signal.

Run per sport (nfl, cfb, nba). The NFL tape matches games by team abbreviation, the other two by the game key the Sharp Money
feed assigns (gk). Output: data/exchange_edge_record.json, with by_sport[<sport>] = {summary, recent}; the top-level summary and recent
are the NFL's, kept so an older cached page keeps working.
"""
import datetime as dt, glob, json, math, os, time
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TAPE = os.environ.get('EDGE_TAPE_DIR') or os.path.join(ROOT, 'data', 'book_tape')       # <TAPE>/<sport>/*.jsonl
OUT = os.environ.get('EDGE_OUT') or os.path.join(ROOT, 'data', 'exchange_edge_record.json')
THRS = (1.0, 2.0, 4.0)
STALE_PIN, STALE_NOV, WINDOW = 0.01, 0.005, 4 * 3600
MARKETS = (('ml', 'ml', 'px'), ('sp', 'sp', 'nsp'), ('tot', 'tot', 'ntot'))


def pfn(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def ff(a, b):
    """Fair chance of the first side after removing the vig. Power method (x^k + y^k = 1), the same as devig() in
    fetch-sharp-money.mjs, so a +900 longshot is not read as +700 fair."""
    x, y = pfn(a), pfn(b)
    lo, hi = 0.5, 3.0
    for _ in range(40):
        k = (lo + hi) / 2
        if x ** k + y ** k > 1:
            lo = k
        else:
            hi = k
    return x ** ((lo + hi) / 2)


def pin_fair_line(m, v):
    """(fair chance of the home/over side, line) from a Pinnacle value."""
    if m == 'ml':
        return ff(v[1], v[0]), None
    return ff(v[1], v[2]), v[0]


def nov_quote(f, v):
    """(line, bid, ask) of the home/over side from a Novig value."""
    return (None, v[0], v[1]) if f == 'px' else (v[0], v[1], v[2])


def at(hist, t):
    v = None
    for ht, hv in hist:
        if ht <= t:
            v = hv
        else:
            break
    return v


def load(sport):
    rows = []
    for fp in sorted(glob.glob(os.path.join(TAPE, sport, '*.jsonl'))):
        for l in open(fp):
            l = l.strip()
            if l:
                try:
                    rows.append(json.loads(l))
                except ValueError:
                    pass
    return rows


def process(rows, now):
    games = defaultdict(list)
    for r in rows:
        if r['book'] in ('Pinnacle', 'Novig') and not r.get('bf'):         # backfilled rows have no prices and are never graded
            games[r.get('gk') or (r['away'], r['home'], r['start'])].append(r)
    events = []
    for gid, rs in games.items():
        away, home, start = rs[0]['away'], rs[0]['home'], rs[0]['start']
        label = f'{away}@{home}'
        rs.sort(key=lambda r: r['t'])
        hist = defaultdict(list)                       # (book, field) -> [(t, value)]
        for r in rs:
            for f in ('ml', 'sp', 'tot', 'px', 'nsp', 'ntot'):
                if r.get(f) is not None:
                    hist[(r['book'], f)].append((r['t'], r[f]))
        fired = set()
        mine = []
        for t in sorted({r['t'] for r in rs}):
            if t >= start - 300:
                continue
            for m, pf, nf in MARKETS:
                pv, nv = at(hist[('Pinnacle', pf)], t), at(hist[('Novig', nf)], t)
                if pv is None or nv is None:
                    continue
                fair, line = pin_fair_line(m, pv)
                nline, bid, ask = nov_quote(nf, nv)
                if nline is not None and nline != line:
                    continue
                for side, cost, sfair in (('A', ask, fair), ('B', 1 - bid, 1 - fair)):
                    ev = (sfair / cost - 1) * 100
                    p0, n0 = at(hist[('Pinnacle', pf)], t - WINDOW), at(hist[('Novig', nf)], t - WINDOW)
                    stale = None
                    if p0 is not None and n0 is not None:
                        f0, l0 = pin_fair_line(m, p0)
                        nl0, b0, a0 = nov_quote(nf, n0)
                        if l0 == line and nl0 == nline:
                            sg = 1 if side == 'A' else -1
                            pm = sg * (fair - f0)
                            nm = sg * (((bid + ask) / 2) - ((b0 + a0) / 2))
                            stale = pm >= STALE_PIN and abs(nm) < STALE_NOV
                    for thr in THRS:
                        if ev >= thr and (m, side, thr) not in fired:
                            fired.add((m, side, thr))
                            mine.append({'gk': rs[0].get('gk'), 'game': label, 'start': start, 't': t, 'm': m, 'side': side, 'thr': thr, 'ev': round(ev, 2),
                                         'cost': round(cost, 3), 'fair': round(sfair, 4), 'line': line, 'stale': stale})
        # grade against Pinnacle's last quote before kickoff
        for e in mine:
            e['graded'] = False
            if start >= now:
                continue
            pf = next(p for m, p, n in MARKETS if m == e['m'])
            close = at(hist[('Pinnacle', pf)], start)
            if close is None:
                continue
            cfair, cline = pin_fair_line(e['m'], close)
            e['graded'] = True
            sfair = cfair if e['side'] == 'A' else 1 - cfair
            if cline == e['line']:
                e['clv'] = round((sfair - e['cost']) * 100, 2)
            else:
                # the side wants a higher home line (spread) or a lower over line (total); the opposite side wants the reverse
                d = (e['line'] - cline) if e['m'] == 'sp' else (cline - e['line'])
                e['line_moved'] = True
                e['line_favoured'] = (d > 0) if e['side'] == 'A' else (d < 0)
        events += mine
    return events


def summarize(sel):
    sig = len(sel)
    gr = [x for x in sel if x.get('graded')]
    same = [x['clv'] for x in gr if 'clv' in x]
    lm = [x for x in gr if x.get('line_moved')]
    o = {'signals': sig, 'graded': len(gr), 'same_line': len(same), 'line_moved': len(lm), 'line_favoured': sum(1 for x in lm if x['line_favoured']),
         'pending': sig - len(gr)}
    if same:
        mu = sum(same) / len(same)
        o['mean_clv'] = round(mu, 2)
        o['beat_close'] = round(sum(1 for c in same if c > 0) / len(same), 3)
        if len(same) > 1:
            sd = math.sqrt(sum((c - mu) ** 2 for c in same) / (len(same) - 1))
            o['ci95'] = round(1.96 * sd / math.sqrt(len(same)), 2)
    return o


def main():
    now = int(time.time())
    by = {}
    for sport in ('nfl', 'cfb', 'nba'):
        events = process(load(sport), now)
        by[sport] = {'calls': sorted([e for e in events if e['thr'] == 1.0], key=lambda e: -e['t'])[:400], 'summary': [{'thr': thr, 'tag': tag, **summarize([e for e in events if e['thr'] == thr and (tag == 'all' or e['stale'] is True)])}
                                 for thr in THRS for tag in ('all', 'stale')],
                     'recent': sorted(events, key=lambda e: -e['t'])[:60]}
        print(f"edge record {sport}: {len(events)} signals, {sum(1 for e in events if e.get('graded'))} graded")
    out = {'generated': dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec='seconds'), 'since': '2026-10-17',
           'rules': 'EV = Pinnacle no-vig fair / Novig cost - 1, first sight per game side; stale = Pinnacle fair +1.0 pt in 4h and Novig mid under 0.5 pt; CLV = close fair - cost in points, same line only',
           'by_sport': by, 'summary': by['nfl']['summary'], 'recent': by['nfl']['recent']}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
