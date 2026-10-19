#!/usr/bin/env python3
"""Replay the V2 gates over a finished slate, from the stored book tape, so those plays can sit in the record next to the live log.

Why it is a replay and not a copy of the live log: the live log (sharp-data/v2_plays.json) only started on 2026-10-18 evening. A play that would have been
shown earlier was never written down. The book tape (data/book_tape/nfl/<month>.jsonl) did store every US book, Pinnacle and exchange quote with its time, so
for the moneyline the gates can be re-run at each moment the tape changed, using only what had been stored by then. Nothing after that moment is used.

What is replayed (the same rules as sharp-money/v2/gates.js, moneyline only):
  - the price is a US book (DraftKings, FanDuel, BetMGM, BetRivers, bet365), or a Novig ask when Kalshi gives a second price
  - Pinnacle's no-vig moneyline (power de-vig) and the exchange mid (mean of the latest Novig and Kalshi quotes) are the two fair prices;
    a Novig-priced play is checked against Pinnacle and Kalshi instead
  - the price beats both by 2%+, the two fair prices sit within 4 points, the edge is not over 10%, and the other side of the game does not also clear
  - the first moment a side clears everything is its play (first sight stands), at the price and book shown then
What is NOT replayed, and why:
  - props: the ledger keeps only the first price a call showed (often days early) and no exchange price at that time, so what V2 would have shown on the day
    cannot be rebuilt without inventing a number
  - spreads and totals: the live rules give them one fair price (Pinnacle) at the main line, so they are Watch, never Play

An exchange quote counts while it is the last one stored and no older than 30 hours (the exchange rows start on 2026-10-17). The tape stores a quote only
when it changes. Results: flat 1 unit at the stored price, final score from ESPN; a game still in play is left open.

usage: backfill_v2_slate.py --date 2026-10-18 [--out data/v2_backfill.json]"""
import argparse, collections, datetime as dt, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
US = ('DraftKings', 'FanDuel', 'BetMGM', 'BetRivers', 'bet365')
MIN_EDGE, AGREE, BIG_EDGE = 0.02, 0.04, 0.10
ALIVE = 2 * 3600
CT = dt.timezone(dt.timedelta(hours=-5))
ALIAS = {'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX'}
r4 = lambda x: None if x is None else round(x, 4)
mean = lambda xs: sum(xs) / len(xs)


def imp(a):
    return None if not a else (-a / (-a + 100) if a < 0 else 100 / (a + 100))


def devig(a, b):
    """No-vig chance of the first side from two American prices (same power method as prop_close_lib.devig)."""
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


def espn_finals(date):
    url = 'https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + date.replace('-', '')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36'})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    out = {}
    for e in d['events']:
        c = e['competitions'][0]
        t = {x['homeAway']: (x['team']['abbreviation'], int(x['score'] or 0)) for x in c['competitors']}
        out[(ALIAS.get(t['away'][0], t['away'][0]), ALIAS.get(t['home'][0], t['home'][0]))] = dict(state=e['status']['type']['state'], away=t['away'][1], home=t['home'][1])
    return out


def load(date):
    rows = []
    for f in sorted(os.listdir(os.path.join(ROOT, 'data', 'book_tape', 'nfl'))):
        if f.startswith('20') and f.endswith('.jsonl'):
            with open(os.path.join(ROOT, 'data', 'book_tape', 'nfl', f)) as fh:
                rows += [json.loads(l) for l in fh if l.strip()]
    g = collections.defaultdict(list)
    for r in rows:
        if dt.datetime.fromtimestamp(r['start'], CT).strftime('%Y-%m-%d') == date and not r.get('bf'):
            g[(r['away'], r['home'], r['start'])].append(r)
    return {k: sorted(v, key=lambda r: r['t']) for k, v in g.items()}


def state_at(rows, t):
    """The latest stored row per book at or before t."""
    s = {}
    for r in rows:
        if r['t'] > t:
            break
        s[r['book']] = r
    return s


def judge(price, refs, contradicted=False):
    """refs: list of fair chances of this side. Returns (tier, worst, best, reason). Mirrors sharp-money/v2/gates.js judge for a two-reference price."""
    edges = [f / price - 1 for f in refs]
    worst, best = min(edges), max(edges)
    if contradicted:
        return 'pass', worst, best, 'both sides clear a reference'
    if len(refs) < 2:
        return ('watch' if best >= MIN_EDGE else 'none'), worst, best, 'one reference'
    if abs(refs[0] - refs[1]) > AGREE:
        return 'pass', worst, best, 'references disagree'
    if worst < MIN_EDGE:
        return 'none', worst, best, 'does not beat both'
    if worst > BIG_EDGE:
        return 'pass', worst, best, 'edge over 10%'
    return 'play', worst, best, 'clears every gate'


def replay_game(key, rows, fin):
    away, home, start = key
    alive_ts = [r['t'] for r in rows]
    logged, plays = set(), []
    for t in sorted({r['t'] for r in rows if r['t'] < start}):
        st = state_at(rows, t)
        pin = st.get('Pinnacle')
        if not pin or not pin.get('ml'):
            continue
        fair_away = devig(pin['ml'][0], pin['ml'][1])
        if fair_away is None:
            continue
        ex = [r for b, r in st.items() if b in ('Novig', 'Kalshi') and r.get('px') and t - r['t'] < 30 * 3600 and any(0 <= t - a <= ALIVE for a in alive_ts if a <= t)]
        ex_home = {b: (r['px'][0] + r['px'][1]) / 2 for b, r in ((r['book'], r) for r in ex)}
        fairs = {'away': fair_away, 'home': 1 - fair_away}
        cands = {'away': [], 'home': []}
        for side in ('away', 'home'):
            i = 0 if side == 'away' else 1
            for b in US:
                r = st.get(b)
                if r and r.get('ml') and imp(r['ml'][i]):
                    cands[side].append(dict(kind='book', book=b, am=r['ml'][i], p=imp(r['ml'][i]), refs=None))
            if ex_home:
                mids = [m if side == 'home' else 1 - m for m in ex_home.values()]
                for b in ('Novig',):
                    r = st.get(b)
                    if r and r.get('px') and 'Kalshi' in ex_home and b in ex_home:
                        ask = r['px'][1] if side == 'home' else 1 - r['px'][0]
                        kal = ex_home['Kalshi'] if side == 'home' else 1 - ex_home['Kalshi']
                        am_ = int(round(-100 * ask / (1 - ask))) if ask >= 0.5 else int(round(100 * (1 - ask) / ask))
                        cands[side].append(dict(kind='exch', book='Novig', am=am_, p=ask, refs=[('Pinnacle', fairs[side]), ('Kalshi', kal)]))
                for c in cands[side]:
                    if c['kind'] == 'book':
                        c['refs'] = [('Pinnacle', fairs[side]), ('Exchange', mean(mids))]
            else:
                for c in cands[side]:
                    c['refs'] = [('Pinnacle', fairs[side])]
        for side in ('away', 'home'):
            opp = 'home' if side == 'away' else 'away'
            for kind in ('book', 'exch'):
                pool = [c for c in cands[side] if c['kind'] == kind]
                if not pool:
                    continue
                c = min(pool, key=lambda x: x['p'])                                 # the best price on this side
                other = [x for x in cands[opp] if x['kind'] == kind]
                contra = bool(other) and any(min(x['refs'][j][1] / min(o['p'] for o in other) - 1 for j in range(len(x['refs']))) >= MIN_EDGE for x in [min(other, key=lambda x: x['p'])])
                tier, worst, best, why = judge(c['p'], [r[1] for r in c['refs']], contra)
                pid = '|'.join([kind, away, home, str(start), side])
                if tier == 'play' and pid not in logged:
                    logged.add(pid)
                    team = away if side == 'away' else home
                    plays.append(dict(id='bf|' + pid, kind=kind, sport='nfl', start=start, firstSeen=t, backfill=True,
                                      first=dict(title=team + ' to win', sub=away + ' @ ' + home + ' (Money)', market='Money',
                                                 price=dict(am=c['am'], p=r4(c['p']), book=c['book']),
                                                 refs=[dict(n=n, p=r4(p), edge=r4(p / c['p'] - 1)) for n, p in c['refs']], worst=r4(worst), best=r4(best), fairMean=r4(mean([p for _, p in c['refs']])), cautions=[]),
                                      game=dict(away=away, home=home, m='ml', side=side),
                                      close=None, clv=None))
    # result and the exchange close (the last stored Kalshi / Novig mid before kickoff)
    last = state_at(rows, start - 1)
    mids = [(r['px'][0] + r['px'][1]) / 2 for b, r in last.items() if b in ('Novig', 'Kalshi') and r.get('px') and start - r['t'] < 30 * 3600]
    for p in plays:
        side = p['game']['side']
        if mids:
            cp = mean(mids) if side == 'home' else 1 - mean(mids)
            p['close'] = dict(p=r4(cp), src='Kalshi+Novig stored mid', n=len(mids))
            p['clv'] = r4(cp / p['first']['price']['p'] - 1)
        res = fin.get((ALIAS.get(away, away), ALIAS.get(home, home))) or fin.get((away, home))
        if res and res['state'] == 'post':
            if res['home'] == res['away']:
                p['status'], p['units'] = 'push', 0
            else:
                won = (res['home'] > res['away']) == (side == 'home')
                p['status'] = 'won' if won else 'lost'
                p['units'] = r4(1 / p['first']['price']['p'] - 1) if won else -1
            p['final'] = dict(away=res['away'], home=res['home'])
        else:
            p['status'] = 'open'
    return plays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'v2_backfill.json'))
    a = ap.parse_args()
    games, fin = load(a.date), espn_finals(a.date)
    plays, per = {}, []
    for key, rows in sorted(games.items(), key=lambda kv: kv[0][2]):
        ps = replay_game(key, rows, fin)
        per.append(dict(away=key[0], home=key[1], start=key[2], rows=len(rows), plays=len(ps)))
        for p in ps:
            plays[p['id']] = p
    doc = dict(v=1, date=a.date, note='Replayed from data/book_tape with the V2 moneyline gates, using only what was stored at each moment. Not the live log: these plays were never shown. Props, spreads and totals are not replayed (see scripts/backfill_v2_slate.py).',
               games=per, plays=plays)
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
    done = [p for p in plays.values() if p['status'] in ('won', 'lost', 'push')]
    print(len(per), 'games,', len(plays), 'plays,', len(done), 'settled,', sum(1 for p in plays.values() if p['status'] == 'open'), 'open, units', round(sum(p['units'] for p in done), 2))
    for p in sorted(plays.values(), key=lambda p: p['firstSeen']):
        f = p['first']
        print(dt.datetime.fromtimestamp(p['firstSeen'], CT).strftime('%a %H:%M'), p['kind'], f['title'], f['price']['book'], f['price']['am'], 'worst', f['worst'], p['status'], p.get('units'), 'clv', p.get('clv'))


if __name__ == '__main__':
    main()
