#!/usr/bin/env python3
"""Lead-lag clock and stale-quote age, measured from the stored book tape (data/book_tape/<sport>/<YYYY-MM>.jsonl, rows appended only when a
book's numbers change, so a row's time is when that book last changed).

1. How long does a US book take to follow Pinnacle? An event is a Pinnacle change whose time is known to within 30 minutes (some poll of that sport
   saw no change in the half hour before it; rows are only written when a number changes, so a row's time is the first poll that saw it):
     spread / total  Pinnacle's line changes by 0.5 or more, from L0 to L1
     moneyline       Pinnacle's no-vig home chance changes by 2 points or more, p0 to p1
   For every other book, judged on its own level (a book that always hangs another number is judged on its moves, not its number):
     led        it had already moved the same way by the same step in the hour up to the Pinnacle row. No lag is scored.
     lag        otherwise, the minutes until it first moves the same way by the same step (moneyline: half the move)
     not followed  it never did before kickoff
   Events within 3 hours of kickoff are left out: a book may have no time to follow. The thresholds were fixed before looking and are not tuned.
   Resolution is our polling gap: a lag of under about 10 minutes cannot be told apart from 0. Reported with n; nothing is scored under n of 15.
2. Stale-quote age, for games that have not started: per market, Pinnacle's last move and each US book's last change, and whether the book's number
   differs from Pinnacle's right now.

Outputs: data/lead_lag.json (the clock, by sport / market / book) and data/book_age.json (the current ages, keyed like data.json games).
usage: build_lead_lag.py [--data path-or-url data.json] [--now unix]"""
import argparse, bisect, collections, glob, json, math, os, statistics, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/sharp-data/data.json'
US = ('DraftKings', 'FanDuel', 'BetMGM', 'BetRivers', 'bet365')
ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
LOCAL_MAX_GAP = 30 * 60
KICKOFF_BUFFER = 3 * 3600
LEAD_WINDOW = 3600
LINE_STEP = 0.5
ML_STEP = 0.02
MIN_N = 15


def imp(a):
    return None if a in (None, 0) else (-a / (-a + 100) if a < 0 else 100 / (a + 100))


def devig2(a, b):
    """No-vig chance of the first side from two American prices (power method)."""
    po, pu = imp(a), imp(b)
    if not po or not pu:
        return None
    if po + pu <= 1:
        return po / (po + pu)
    lo, hi = 1.0, 10.0
    for _ in range(40):
        k = (lo + hi) / 2
        lo, hi = (k, hi) if po ** k + pu ** k > 1 else (lo, k)
    k = (lo + hi) / 2
    return po ** k / (po ** k + pu ** k)


def load_rows():
    rows = []
    for sp in ('nfl', 'cfb', 'nba'):
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'book_tape', sp, '20*.jsonl'))):   # monthly files only: the backfill rows have no prices
            with open(f) as fh:
                for line in fh:
                    if line.strip():
                        r = json.loads(line)
                        r['sport'] = sp
                        rows.append(r)
    return rows


def gkey(r):
    if r.get('gk'):
        return r['gk']
    return 'nfl|%s|%s|%s' % (ALIAS.get(r['away'], r['away']), ALIAS.get(r['home'], r['home']), r['start'])


def series(rows):
    """{game: {book: [(t, state)]}} with state carrying only what that row reported, merged forward so a row that omits a market keeps the last value."""
    g = collections.defaultdict(lambda: collections.defaultdict(list))
    meta = {}
    for r in sorted(rows, key=lambda r: r['t']):
        k = gkey(r)
        meta[k] = dict(sport=r['sport'], start=r['start'], away=r['away'], home=r['home'])
        book = r['book']
        if book in ('Open', 'Consensus'):
            continue
        prev = g[k][book][-1][1] if g[k][book] else {}
        st = dict(prev)
        if r.get('sp'):
            st['sp'] = r['sp'][0]
        if r.get('tot'):
            st['tot'] = r['tot'][0]
        if r.get('ml'):
            st['ml'] = devig2(r['ml'][1], r['ml'][0])          # no-vig chance the HOME side wins
        elif r.get('px'):
            st['ml'] = (r['px'][0] + r['px'][1]) / 2
        g[k][book].append((r['t'], st))
    return g, meta


def level(st, m):
    return None if st is None else st.get(m)


def at(ser, t, m):
    """The book's value for market m as of time t, rows stamped at t included (None if it had not posted one)."""
    v = None
    for ts, st in ser:
        if ts > t:
            break
        if st.get(m) is not None:
            v = st[m]
    return v


def events(pin, m, start, polls):
    """Pinnacle changes of at least one step, whose time is localised: some poll of this sport saw no change in the 30 minutes before it."""
    out = []
    prev = None
    step = LINE_STEP if m != 'ml' else ML_STEP
    for t, st in pin:
        v = st.get(m)
        if v is None:
            continue
        if prev is not None and abs(v - prev) >= step - 1e-9 and start - t >= KICKOFF_BUFFER:
            i = bisect.bisect_left(polls, t)
            if i > 0 and t - polls[i - 1] <= LOCAL_MAX_GAP:
                out.append((t, prev, v))
        prev = v
    return out


def follow(ser, t1, v0, v1, m, start):
    """Did this book move the same way by at least the same step, before Pinnacle (led), after it (lag) or not at all (none)?
    The book's own level is the baseline, so a book that always hangs a different number is judged on its moves, not on its number."""
    d = v1 - v0
    need = abs(d) if m != 'ml' else 0.5 * abs(d)
    sign = 1 if d > 0 else -1
    at1 = at(ser, t1, m)                              # level at the Pinnacle row (a row stamped at the same time counts as at or before)
    pre = at(ser, t1 - LEAD_WINDOW, m)
    if at1 is None:
        return 'none', None
    if pre is not None and sign * (at1 - pre) >= need - 1e-9:
        return 'led', None
    for ts, st in ser:
        x = st.get(m)
        if ts > t1 and ts < start and x is not None and sign * (x - at1) >= need - 1e-9:
            return 'lag', (ts - t1) / 60
    return 'none', None


def summary(lags, led, none):
    n = len(lags) + led + none
    out = dict(n=n, led=led, not_followed=none, followed=len(lags))
    if n >= MIN_N:
        out['pct_led'] = round(led / n, 3)
        out['pct_not_followed'] = round(none / n, 3)
    if n >= MIN_N:
        out['pct_followed_within_15'] = round(sum(1 for x in lags if x <= 15) / n, 3)
        out['pct_followed_within_60'] = round(sum(1 for x in lags if x <= 60) / n, 3)
    if len(lags) >= MIN_N:
        s = sorted(lags)
        out.update(median_min=round(statistics.median(s), 1), p25_min=round(s[len(s) // 4], 1), p75_min=round(s[(3 * len(s)) // 4], 1),
                   within_15=round(sum(1 for x in s if x <= 15) / len(s), 3), within_60=round(sum(1 for x in s if x <= 60) / len(s), 3))
    return out


def clock(g, meta):
    polls = {}
    for k, books in g.items():
        polls.setdefault(meta[k]['sport'], set()).update(t for ser in books.values() for t, _ in ser)
    polls = {k: sorted(v) for k, v in polls.items()}
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [[], 0, 0]))      # (sport, market) -> book -> [lags, led, none]
    ev_n = collections.Counter()
    for k, books in g.items():
        pin = books.get('Pinnacle')
        if not pin:
            continue
        sp = meta[k]['sport']
        for m in ('sp', 'tot', 'ml'):
            for t1, v0, v1 in events(pin, m, meta[k]['start'], polls[sp]):
                ev_n[(sp, m)] += 1
                for b in US + ('Novig', 'Kalshi'):
                    if b not in books or (m != 'ml' and b in ('Novig', 'Kalshi')):
                        continue
                    kind, mins = follow(books[b], t1, v0, v1, m, meta[k]['start'])
                    a = acc[(sp, m)][b]
                    if kind == 'lag':
                        a[0].append(mins)
                    elif kind == 'led':
                        a[1] += 1
                    else:
                        a[2] += 1
    res = {}
    for (sp, m), bk in acc.items():
        allags, allled, allnone = [], 0, 0
        r = {}
        for b, (lags, led, none) in bk.items():
            r[b] = summary(lags, led, none)
            if b in US:
                allags += lags; allled += led; allnone += none
        r['US books (all five)'] = summary(allags, allled, allnone)
        res.setdefault(sp, {})[m] = dict(events=ev_n[(sp, m)], by_book=r)
    return res


def pin_gaps(g):
    gaps = []
    for books in g.values():
        p = books.get('Pinnacle') or []
        gaps += [(b[0] - a[0]) / 60 for a, b in zip(p, p[1:])]
    return round(statistics.median(gaps), 1) if gaps else None


def ages(g, meta, now, keymap):
    out = {}
    for k, books in g.items():
        m0 = meta[k]
        if m0['start'] <= now:
            continue
        pin = books.get('Pinnacle')
        if not pin:
            continue
        res = {}
        for m in ('sp', 'tot', 'ml'):
            pl = level(pin[-1][1], m)
            if pl is None:
                continue
            tp = max((t for t, st in pin if st.get(m) is not None and (len(pin) == 1 or True)), default=None)
            last_move = None                                       # time Pinnacle's number last changed
            prev = None
            for t, st in pin:
                v = st.get(m)
                if v is None:
                    continue
                if prev is None or abs(v - prev) >= (1e-9 if m != 'ml' else 0.005):
                    last_move = t
                prev = v
            row = dict(pin=pl, pin_moved=last_move, books={})
            for b in US:
                s = books.get(b)
                if not s:
                    continue
                v = level(s[-1][1], m)
                if v is None:
                    continue
                last = None
                pv = None
                for t, st in s:
                    x = st.get(m)
                    if x is None:
                        continue
                    if pv is None or abs(x - pv) >= (1e-9 if m != 'ml' else 0.005):
                        last = t
                    pv = x
                row['books'][b] = dict(v=v, changed=last, seen=s[-1][0], same=abs(v - pl) < (1e-9 if m != 'ml' else ML_STEP))
            res[m] = row
        if res:
            out[keymap.get(k, k)] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=URL)
    ap.add_argument('--now', type=int, default=int(time.time()))      # only used to tell which games have not started
    ap.add_argument('--out-clock', default=os.path.join(ROOT, 'data', 'lead_lag.json'))
    ap.add_argument('--out-age', default=os.path.join(ROOT, 'data', 'book_age.json'))
    a = ap.parse_args()
    rows = load_rows()
    g, meta = series(rows)
    keymap = {}
    try:
        src = open(a.data).read() if not a.data.startswith('http') else urllib.request.urlopen(a.data, timeout=60).read().decode()
        for x in json.loads(src).get('games', []):
            if x['sport'] == 'nfl':
                keymap['nfl|%s|%s|%s' % (ALIAS.get(x['away']['abbr'], x['away']['abbr']), ALIAS.get(x['home']['abbr'], x['home']['abbr']), x['start'])] = x['key']
    except Exception as e:
        print('no data.json, NFL ages keep the tape key:', e)
    res = clock(g, meta)
    stamp = max((r['t'] for r in rows), default=0)               # the tape's own newest row, so the files change only when the tape does
    doc = dict(tape_through=stamp, games=len(g), rows=len(rows), pinnacle_median_gap_min=pin_gaps(g),
               rule=dict(event='Pinnacle line moved 0.5+ (spread, total) or no-vig chance moved 2+ points (moneyline), time known to within 30 minutes, 3+ hours before kickoff',
                         lag='minutes to the first book row at or past the new level (moneyline: half the move)', min_n=MIN_N),
               by_sport=res)
    with open(a.out_clock, 'w') as f:
        json.dump(doc, f, indent=1)
    age = dict(tape_through=stamp, games=ages(g, meta, a.now, keymap))
    with open(a.out_age, 'w') as f:
        json.dump(age, f, separators=(',', ':'))
    print('games', len(g), 'rows', len(rows), 'pinnacle median gap (min)', doc['pinnacle_median_gap_min'])
    for sp, ms in res.items():
        for m, d in ms.items():
            u = d['by_book'].get('US books (all five)', {})
            print(sp, m, 'events', d['events'], 'US', json.dumps(u))
    print('book_age games', len(age['games']))


if __name__ == '__main__':
    main()
