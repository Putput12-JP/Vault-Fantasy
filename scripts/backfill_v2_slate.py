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


def markets_at(st):
    """Per market the fair chance of each side from Pinnacle's stored prices, and every US book's price at the same number. sp: the home line must match."""
    pin = st.get('Pinnacle')
    out = {}
    if not pin:
        return out
    if pin.get('ml'):
        f = devig(pin['ml'][0], pin['ml'][1])
        if f is not None:
            out['ml'] = dict(line=None, fair={'away': f, 'home': 1 - f}, books=[(b, {'away': r['ml'][0], 'home': r['ml'][1]}) for b in US for r in [st.get(b)] if r and r.get('ml')])
    if pin.get('sp'):
        line, hp, ap = pin['sp']
        f = devig(hp, ap)                                              # chance the home side covers
        if f is not None:
            out['sp'] = dict(line=line, fair={'home': f, 'away': 1 - f}, books=[(b, {'home': r['sp'][1], 'away': r['sp'][2]}) for b in US for r in [st.get(b)] if r and r.get('sp') and r['sp'][0] == line])
    if pin.get('tot'):
        line, ov, un = pin['tot']
        f = devig(ov, un)
        if f is not None:
            out['tot'] = dict(line=line, fair={'over': f, 'under': 1 - f}, books=[(b, {'over': r['tot'][1], 'under': r['tot'][2]}) for b in US for r in [st.get(b)] if r and r.get('tot') and r['tot'][0] == line])
    return out


SIDES = {'ml': ('away', 'home'), 'sp': ('away', 'home'), 'tot': ('over', 'under')}


def replay_game(key, rows, fin):
    """Rows for every tier: the first moment each pick reaches Play, Watch or Passed (first sight in that tier stands), as the live tracker logs them."""
    away, home, start = key
    alive_ts = [r['t'] for r in rows]
    logged = {'play': set(), 'watch': set(), 'pass': set()}
    out = {'play': [], 'watch': [], 'pass': []}
    for t in sorted({r['t'] for r in rows if r['t'] < start}):
        st = state_at(rows, t)
        mk = markets_at(st)
        if not mk:
            continue
        ex = [r for b, r in st.items() if b in ('Novig', 'Kalshi') and r.get('px') and t - r['t'] < 30 * 3600 and any(0 <= t - a <= ALIVE for a in alive_ts if a <= t)]
        ex_home = {r['book']: (r['px'][0] + r['px'][1]) / 2 for r in ex}
        for m, info in mk.items():
            a_side, b_side = SIDES[m]
            cands = {a_side: [], b_side: []}
            for side in (a_side, b_side):
                for b, prices in info['books']:
                    am_ = prices[side]
                    if imp(am_):
                        refs = [('Pinnacle', info['fair'][side])]
                        if m == 'ml' and ex_home:
                            mids = [mm if side == 'home' else 1 - mm for mm in ex_home.values()]
                            refs.append(('Exchange', mean(mids)))
                        cands[side].append(dict(kind='book', book=b, am=am_, p=imp(am_), refs=refs))
                if m == 'ml' and 'Novig' in ex_home and 'Kalshi' in ex_home:
                    r = st['Novig']
                    ask = r['px'][1] if side == 'home' else 1 - r['px'][0]
                    kal = ex_home['Kalshi'] if side == 'home' else 1 - ex_home['Kalshi']
                    am_ = int(round(-100 * ask / (1 - ask))) if ask >= 0.5 else int(round(100 * (1 - ask) / ask))
                    cands[side].append(dict(kind='exch', book='Novig', am=am_, p=ask, refs=[('Pinnacle', info['fair'][side]), ('Kalshi', kal)]))
            for side in (a_side, b_side):
                opp = b_side if side == a_side else a_side
                for kind in ('book', 'exch'):
                    pool = [c for c in cands[side] if c['kind'] == kind]
                    if not pool:
                        continue
                    c = min(pool, key=lambda x: x['p'])
                    other = [x for x in cands[opp] if x['kind'] == kind]
                    contra = bool(other) and min(x_r[1] / min(o['p'] for o in other) - 1 for x_r in min(other, key=lambda x: x['p'])['refs']) >= MIN_EDGE
                    tier, worst, best, why = judge(c['p'], [r[1] for r in c['refs']], contra)
                    if tier == 'none':
                        continue
                    pid = '|'.join([kind, m, away, home, str(start), side])
                    if pid in logged[tier]:
                        continue
                    logged[tier].add(pid)
                    team = away if side == 'away' else home
                    hl = info['line']
                    title = team + ' to win' if m == 'ml' else (team + ' ' + ('%+g' % (hl if side == 'home' else -hl)) if m == 'sp' else ('Over ' if side == 'over' else 'Under ') + '%g' % hl)
                    out[tier].append(dict(id='bf|%s|%s' % (tier, pid), kind=kind, sport='nfl', start=start, firstSeen=t, backfill=True,
                                          first=dict(title=title, sub=away + ' @ ' + home + ' (' + {'ml': 'Money', 'sp': 'Spread', 'tot': 'Total'}[m] + ')', market={'ml': 'Money', 'sp': 'Spread', 'tot': 'Total'}[m],
                                                     price=dict(am=c['am'], p=r4(c['p']), book=c['book']),
                                                     refs=[dict(n=n, p=r4(p), edge=r4(p / c['p'] - 1)) for n, p in c['refs']], worst=r4(worst), best=r4(best), fairMean=r4(mean([p for _, p in c['refs']])), cautions=[], why=why),
                                          game=dict(away=away, home=home, m=m, side=side, hline=hl if m == 'sp' else None, line=hl if m == 'tot' else None), close=None, clv=None))
    # result and the exchange close (the last stored Kalshi / Novig mid before kickoff; moneyline only)
    last = state_at(rows, start - 1)
    mids = [(r['px'][0] + r['px'][1]) / 2 for b, r in last.items() if b in ('Novig', 'Kalshi') and r.get('px') and start - r['t'] < 30 * 3600]
    res = fin.get((ALIAS.get(away, away), ALIAS.get(home, home))) or fin.get((away, home))
    for tier in out:
        for p in out[tier]:
            g = p['game']
            if mids and g['m'] == 'ml':
                cp = mean(mids) if g['side'] == 'home' else 1 - mean(mids)
                p['close'] = dict(p=r4(cp), src='Kalshi+Novig stored mid', n=len(mids))
                p['clv'] = r4(cp / p['first']['price']['p'] - 1)
            if res and res['state'] == 'post':
                h, a_ = res['home'], res['away']
                if g['m'] == 'ml':
                    v = 0 if h == a_ else 1 if (h > a_) == (g['side'] == 'home') else -1
                elif g['m'] == 'sp':
                    d = h + g['hline'] - a_; r = d if g['side'] == 'home' else -d; v = 1 if r > 0 else -1 if r < 0 else 0
                else:
                    d = h + a_ - g['line']; r = d if g['side'] == 'over' else -d; v = 1 if r > 0 else -1 if r < 0 else 0
                p['status'] = 'push' if v == 0 else 'won' if v > 0 else 'lost'
                p['units'] = 0 if v == 0 else r4(1 / p['first']['price']['p'] - 1) if v > 0 else -1
                p['final'] = dict(away=a_, home=h)
            else:
                p['status'] = 'open'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'v2_backfill_games.json'))
    a = ap.parse_args()
    games, fin = load(a.date), espn_finals(a.date)
    tiers = {'play': {}, 'watch': {}, 'pass': {}}
    per = []
    for key, rows in sorted(games.items(), key=lambda kv: kv[0][2]):
        got = replay_game(key, rows, fin)
        per.append(dict(away=key[0], home=key[1], start=key[2], rows=len(rows), **{t: len(v) for t, v in got.items()}))
        for t, ps in got.items():
            for p in ps:
                tiers[t][p['id']] = p
    doc = dict(v=2, date=a.date, games=per, plays=tiers['play'], watch=tiers['watch'], passed=tiers['pass'])
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
    for t in ('play', 'watch', 'pass'):
        ps = list(tiers[t].values()); done = [p for p in ps if p['status'] in ('won', 'lost', 'push')]
        w = sum(1 for p in done if p['status'] == 'won')
        print(t, len(ps), 'rows;', len(done), 'settled', '%d-%d' % (w, len(done) - w), 'units', round(sum(p['units'] for p in done), 2), collections.Counter(p['game']['m'] for p in ps))


if __name__ == '__main__':
    main()
