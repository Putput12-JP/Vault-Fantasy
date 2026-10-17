#!/usr/bin/env python3
"""
College football and NBA book tape, read from the Sharp Money data file instead of the sportsbooks directly.

scripts/book_tape.py records the NFL straight from Action Network, Pinnacle, Novig and Kalshi and matches teams by abbreviation.
College and NBA team names differ across those sources (130+ college teams), and fetch-sharp-money.mjs already matches every
source to one game. So this reads its output (data.json: per game Pinnacle, each US book, consensus, open, Novig, Kalshi) and
appends a row whenever a book's numbers change, keyed by the game's key (e.g. "cfb:289489").

Row: {"t", "src": "sd", "gk", "book", "away", "home", "start",
      "ml": [away, home], "sp": [home line, home price, away price], "tot": [line, over, under],   US books, Pinnacle, Consensus, Open
      "lim": [ml, sp, tot],                                                                           Pinnacle only: max stake
      "px": [home bid, home ask], "nsp": [line, home bid, home ask], "ntot": [line, over bid, over ask]}   Novig; Kalshi has px only
  -> data/book_tape/<sport>/<YYYY-MM>.jsonl ; last state in data/book_tape/<sport>/last.json

History before the first run is backfilled once per game, from what each source really keeps (nothing is estimated):
  Pinnacle   the feed's own 5-day move history (pinHist): spread line, total line and moneyline win chance (no prices, so these rows
             carry "mlp" "spl" "totl" and "bf": 1 and never enter the edge record)
  Kalshi     the exchange's hourly candlesticks: the closing yes bid and ask for the home contract
  Novig      its recent trades on the winner market, last price per half hour (a traded price, not a quote)
  US books   no free source keeps their history, so they start at the first run
  -> data/book_tape/<sport>/backfill.jsonl (all three sports, NFL included for the two exchanges).

Recording starts the first run after this lands. Earlier lines were never stored for these sports, so none are invented.
Usage: python3 scripts/sharp_tape.py [--data path-or-url]
"""
import datetime as dt, glob, json, os, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/sharp-data/data.json'
SPORTS = ('cfb', 'nba')
BF_SPORTS = ('nfl', 'cfb', 'nba')
NFL_ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
KAL = 'https://api.elections.kalshi.com/trade-api/v2'
KSERIES = {'nfl': 'KXNFLGAME', 'cfb': 'KXNCAAFGAME', 'nba': 'KXNBAGAME'}
NOV = 'https://api.novig.com/v3/public/catalog'


def load(src):
    if src.startswith('http'):
        return json.loads(subprocess.run(['curl', '-s', '--compressed', '--max-time', '60', src], capture_output=True, check=True).stdout)
    return json.load(open(src))


def both(x, a, b):
    return x and x.get(a) is not None and x.get(b) is not None


def book_vec(x):
    """ml [away, home], sp [home line, home, away], tot [line, over, under] from one book's block, or Nones."""
    ml = [x['ml']['away'], x['ml']['home']] if both(x.get('ml'), 'home', 'away') else None
    sp = [x['sp']['line'], x['sp']['home'], x['sp']['away']] if both(x.get('sp'), 'home', 'away') and x['sp'].get('line') is not None else None
    tot = [x['tot']['line'], x['tot']['over'], x['tot']['under']] if both(x.get('tot'), 'over', 'under') and x['tot'].get('line') is not None else None
    return ml, sp, tot


def quote(q, line=False):
    """[bid, ask] or [line, bid, ask] from a Novig block; only when both sides of the quote exist."""
    if not q or q.get('bid') is None or q.get('ask') is None or not 0 < q['bid'] <= q['ask'] < 1:
        return None
    return [q['line'], q['bid'], q['ask']] if line and q.get('line') is not None else None if line else [q['bid'], q['ask']]


def rows_for(g):
    base = {'src': 'sd', 'gk': g['key'], 'away': g['away']['abbr'], 'home': g['home']['abbr'], 'start': g['start']}
    out = []
    for name, x in [('Pinnacle', g.get('pin')), ('Consensus', g.get('consensus')), ('Open', g.get('open'))] + sorted((g.get('soft') or {}).items()):
        if not x:
            continue
        ml, sp, tot = book_vec(x)
        r = {**base, 'book': name, 'ml': ml, 'sp': sp, 'tot': tot}
        if name == 'Pinnacle' and x.get('lim'):
            r['lim'] = [x['lim'].get('ml'), x['lim'].get('sp'), x['lim'].get('tot')]
        out.append(r)
    nv = g.get('nov') or {}
    if nv:
        r = {**base, 'book': 'Novig', 'px': quote(nv.get('ml')), 'nsp': quote(nv.get('sp'), True), 'ntot': quote(nv.get('tot'), True)}
        out.append(r)
    kl = g.get('kal') or {}
    if kl.get('bid') is not None and kl.get('ask') is not None and 0 < kl['bid'] <= kl['ask'] < 1:
        out.append({**base, 'book': 'Kalshi', 'px': [round(kl['bid'], 3), round(kl['ask'], 3)]})
    return out


def jget(url):
    try:
        return json.loads(subprocess.run(['curl', '-s', '--compressed', '--max-time', '30', '-A', 'Mozilla/5.0 (VaultFantasy line tape)', url], capture_output=True).stdout)
    except ValueError:
        return None


def bf_base(g):
    return {'src': 'sd', 'gk': g['key'], 'away': g['away']['abbr'], 'home': g['home']['abbr'], 'start': g['start'], 'bf': 1}


def bf_pinnacle(g):
    out = []
    for h in g.get('pinHist') or []:
        ts, ml, spl, _, totl, _ = (list(h) + [None] * 6)[:6]
        r = {**bf_base(g), 't': int(ts), 'book': 'Pinnacle', 'mlp': ml, 'spl': spl, 'totl': totl}
        if any(r[k] is not None for k in ('mlp', 'spl', 'totl')):
            out.append({k: v for k, v in r.items() if v is not None})
    return out


def bf_kalshi(g, now):
    """None when the home market is unknown or the read failed, so it is tried again next run."""
    tk = (g.get('kal') or {}).get('hm')
    if not tk:
        return None
    js = jget(f"{KAL}/series/{KSERIES[g['sport']]}/markets/{tk}/candlesticks?start_ts={now - 14 * 86400}&end_ts={now}&period_interval=60")
    if not js or 'candlesticks' not in js:
        return None
    out, prev = [], None
    for c in js['candlesticks']:
        try:
            bid, ask = round(float(c['yes_bid']['close_dollars']), 3), round(float(c['yes_ask']['close_dollars']), 3)
        except (KeyError, TypeError, ValueError):
            continue
        if 0 < bid <= ask < 1 and [bid, ask] != prev:
            prev = [bid, ask]
            out.append({**bf_base(g), 't': int(c['end_period_ts']), 'book': 'Kalshi', 'px': [bid, ask]})
    return out


def bf_novig(g):
    ml = (g.get('nov') or {}).get('ml') or {}
    mk, ho = ml.get('mk'), ml.get('ho')
    if not mk or not ho:
        return None
    js = jget(f"{NOV}/markets/{mk}/trades?limit=500")
    if not js or 'items' not in js:
        return None
    last = {}
    for x in js['items']:
        b = int(x['ts'] / 1000) // 1800 * 1800 + 1800
        p = float(x['price'])
        if b not in last or x['ts'] >= last[b][0]:
            last[b] = (x['ts'], round(p if x['outcomeId'] == ho else 1 - p, 3))
    return [{**bf_base(g), 't': b, 'book': 'Novig', 'px': [v[1], v[1]], 'tr': 1} for b, v in sorted(last.items()) if 0 < v[1] < 1]


def backfill(games, now):
    """Once per game and source: write what the sources already keep. State: data/book_tape/<sport>/backfill_state.json (the NFL's last.json belongs to book_tape.py)."""
    total = 0
    for sp in BF_SPORTS:
        d = os.path.join(ROOT, 'data', 'book_tape', sp)
        os.makedirs(d, exist_ok=True)
        lp = os.path.join(d, 'backfill_state.json')
        last = json.load(open(lp)) if os.path.exists(lp) else {}
        rows = []
        for g in [x for x in games if x['sport'] == sp]:
            for tag, fn in (('bfp', lambda: bf_pinnacle(g) if sp != 'nfl' else []), ('bfk', lambda: bf_kalshi(g, now)), ('bfn', lambda: bf_novig(g))):
                k = f"{tag}|{g['key']}"
                if k in last:
                    continue
                got = fn()
                if got is None:
                    continue
                last[k] = [g['start'], 1]
                rows += got
        if rows:
            with open(os.path.join(d, 'backfill.jsonl'), 'a') as f:
                for r in rows:
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')
        last = {k: v for k, v in last.items() if v[0] > now - 86400}
        json.dump(last, open(lp, 'w'), separators=(',', ':'), sort_keys=True)
        total += len(rows)
        print(f'{sp} backfill: {len(rows)} rows')
    return total


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


def price_am(p):
    return '+' + str(round(100 * (1 - p) / p)) if p < 0.5 else str(round(-100 * p / (1 - p)))


def tape_rows(sp):
    rows = []
    for fp in sorted(glob.glob(os.path.join(ROOT, 'data', 'book_tape', sp, '*.jsonl'))):
        if os.path.basename(fp).startswith('backfill'):
            continue
        for l in open(fp):
            if '"Novig"' in l:
                try:
                    rows.append(json.loads(l))
                except ValueError:
                    pass
    return rows


def ladder_fills(Q, buy_ho, sfair):
    """EV at $100, $500 and $1,000 and the dollars available at +EV, walking Novig's resting orders.
    A resting bid at price p on one outcome lets a buyer take the other outcome at 1 - p; one contract pays $0.01, so an order of qty q costs
    the taker (1 - p) * q / 100 dollars. buy_ho: the side bought is the home / over outcome. Needs the market id from the feed; None otherwise."""
    mk, ho = Q.get('mk'), Q.get('ho')
    if not mk or not ho:
        return None
    book = jget(f"{NOV}/markets/{mk}/book")
    orders = (book or {}).get('orders')
    if not orders or ho not in orders:
        return None
    other = next((k for k in orders if k != ho), None)
    src = orders.get(other) if buy_ho else orders.get(ho)
    if not src:
        return None
    lv = sorted(((1 - float(o['price']), o['qty']) for o in src), key=lambda x: x[0])      # (cost per contract as a chance, contracts), cheapest first
    out = {}
    for S in (100, 500, 1000):
        left, paid, got = S, 0.0, 0.0
        for c, q in lv:
            take = min(q, left / (0.01 * c)) if c > 0 else 0
            paid += take * 0.01 * c
            got += take * 0.01
            left -= take * 0.01 * c
            if left <= 1e-9:
                break
        out[str(S)] = round((sfair / (paid / got) - 1) * 100, 2) if left <= 1e-6 and got else None     # None: the book is not deep enough for this size
    out['ev_dollars'] = round(sum(q * 0.01 * c for c, q in lv if c < sfair))                       # dollars you can put on at a positive price
    return out


def second_opinion(g, m, line, a, cost, sfair):
    """What Kalshi and Polymarket say about the side being bought, next to Novig's cost. Kalshi: the home contract's bid and ask mid (winner market only),
    Polymarket: the market's last price (winner, spread and total, only at Pinnacle's exact line). A source counts as backing the row when its chance for the side
    is at least one cent above Novig's cost. Nothing is guessed: a missing or loose quote leaves that source out."""
    out = {}
    kl = g.get('kal') or {}
    if m == 'ml' and kl.get('bid') is not None and kl.get('ask') is not None and 0 < kl['bid'] <= kl['ask'] < 1 and kl['ask'] - kl['bid'] <= 0.10:
        mid = (kl['bid'] + kl['ask']) / 2
        out['kal'] = round(mid if a else 1 - mid, 3)
    px = ((g.get('pm') or {}).get('px') or {}).get(m)
    if px and px.get('px') and px.get('outs') and len(px['outs']) == 2:
        hn, an = (g['home'].get('name') or '').lower(), (g['away'].get('name') or '').lower()
        first = px['outs'][0].lower()
        if m == 'tot':
            if px.get('line') == line:
                over = px['px'][0] if first.startswith('over') else px['px'][1]
                out['pm'] = round(over if a else 1 - over, 3)
        else:
            f_home = first in hn and first not in an
            f_away = first in an and first not in hn
            if f_home or f_away:
                p_home = px['px'][0] if f_home else px['px'][1]
                if m == 'ml':
                    out['pm'] = round(p_home if a else 1 - p_home, 3)
                elif px.get('line') is not None and (px['line'] if f_home else -px['line']) == line:
                    out['pm'] = round(p_home if a else 1 - p_home, 3)
    if out:
        out['pin'] = round(sfair, 4)
        out['confirm'] = sum(1 for k in ('kal', 'pm') if k in out and out[k] >= cost + 0.0099)       # at least one Kalshi tick (1 cent) above Novig's price
        out['of'] = sum(1 for k in ('kal', 'pm') if k in out)
    return out or None


def live_edges(games, now):
    """Novig's price against Pinnacle's no-vig fair, per game and market, from the current feed. Best side only.
    EV = fair / cost - 1 with cost = Novig's ask on that side (1 minus the best bid on the other), no fee before kickoff.
    Spread and total need Novig to quote Pinnacle's exact line. pm / nm: how far Pinnacle's fair and Novig's mid for that side moved
    over the last 4 hours (pinHist and the tape); stale = Pinnacle up 1.0+ pt while Novig moved under 0.5 pt (same rule as the record)."""
    novtape = {}
    budget = [40]
    for sp in BF_SPORTS:
        for r in tape_rows(sp):
            if r.get('gk') or sp == 'nfl':
                novtape.setdefault(r.get('gk') or (r['away'], r['home']), []).append(r)
    out = []
    for g in games:
        pin, nv = g.get('pin') or {}, g.get('nov') or {}
        if not pin or not nv:
            continue
        hist = g.get('pinHist') or []
        h4 = next((h for h in reversed(hist) if h[0] <= now - 4 * 3600), None)
        nk2 = (NFL_ALIAS.get(g['away']['abbr'], g['away']['abbr']), NFL_ALIAS.get(g['home']['abbr'], g['home']['abbr']))        # the NFL tape uses book_tape.py's abbreviations
        nrows = sorted(novtape.get(g['key']) or novtape.get(nk2) or [], key=lambda r: r['t'])
        ab = g['away']['abbr']
        hb = g['home']['abbr']
        spec = (('ml', 'ml', 'px', None), ('sp', 'sp', 'nsp', 'line'), ('tot', 'tot', 'ntot', 'line'))
        for m, pk, nk, _ in spec:
            P, Q = pin.get(pk), nv.get(pk)
            if not P or not Q or Q.get('bid') is None or Q.get('ask') is None or not 0 < Q['bid'] <= Q['ask'] < 1:
                continue
            if m == 'ml':
                if P.get('home') is None or P.get('away') is None:
                    continue
                fair, line = ff(P['home'], P['away']), None
            elif m == 'sp':
                if P.get('line') is None or Q.get('line') != P['line'] or P.get('home') is None or P.get('away') is None:
                    continue
                fair, line = ff(P['home'], P['away']), P['line']
            else:
                if P.get('line') is None or Q.get('line') != P['line'] or P.get('over') is None or P.get('under') is None:
                    continue
                fair, line = ff(P['over'], P['under']), P['line']
            bid, ask = Q['bid'], Q['ask']
            evA, evB = fair / ask - 1, (1 - fair) / (1 - bid) - 1
            a = evA >= evB
            cost, sfair = (ask, fair) if a else (1 - bid, 1 - fair)
            if m == 'ml':
                label = hb if a else ab
            elif m == 'sp':
                label = f"{hb} {line:+g}" if a else f"{ab} {-line:+g}"
            else:
                label = f"Over {line:g}" if a else f"Under {line:g}"
            row = {'gk': g['key'], 'sport': g['sport'], 'away': ab, 'home': hb, 'start': g['start'], 'm': m, 'label': label, 'line': line,
                   'ev': round(max(evA, evB) * 100, 2), 'cost': round(cost, 3), 'price': price_am(cost), 'fair': round(sfair, 4), 'sg': 1 if a else -1}
            if h4:
                f4 = {'ml': h4[1], 'sp': h4[3] if h4[2] == line else None, 'tot': h4[5] if h4[4] == line else None}[m]
                if f4 is not None:
                    row['pm'] = round(row['sg'] * (fair - f4) * 100, 2)
            old = None
            for r in nrows:
                if r['t'] <= now - 4 * 3600 and r.get(nk) is not None and (m == 'ml' or r[nk][0] == line):
                    old = r[nk]
            if old is not None:
                o = old if m == 'ml' else old[1:]
                row['nm'] = round(row['sg'] * (((bid + ask) / 2) - ((o[0] + o[1]) / 2)) * 100, 2)
            # how long each side has sat: Novig's quote since its last change on the tape, Pinnacle's last move from its own history
            last_n = next((r for r in reversed(nrows) if r.get(nk) is not None), None)
            if last_n:
                cur = [bid, ask]
                got = last_n[nk] if m == 'ml' else last_n[nk][1:]
                if got == cur and (m == 'ml' or last_n[nk][0] == line):
                    row['nov_since'] = last_n['t']
            col = {'ml': (1,), 'sp': (2, 3), 'tot': (4, 5)}[m]
            for i in range(len(hist) - 1, 0, -1):
                if any(hist[i][c] != hist[i - 1][c] for c in col):
                    row['pin_since'] = hist[i][0]
                    break
            if 'pm' in row and 'nm' in row:
                row['stale'] = row['pm'] >= 1.0 and abs(row['nm']) < 0.5
            dp = Q.get('depth') or {}
            ka, kb = ('over', 'under') if m == 'tot' else ('home', 'away')
            if dp.get(kb if a else ka) is not None:
                row['depth'] = dp[kb if a else ka]       # dollars resting within 3 cents of the best price on the side a buyer would hit
            if pin.get('lim') and pin['lim'].get(pk):
                row['lim'] = pin['lim'][pk]
            so = second_opinion(g, m, line, a, cost, sfair)
            if so:
                row['second'] = so
            fills = ladder_fills(Q, a, sfair) if max(evA, evB) > 0 and budget[0] > 0 else None     # book reads only for rows above zero, capped per run
            budget[0] -= 1
            if fills:
                row['fill'] = fills
            del row['sg']
            out.append(row)
    out.sort(key=lambda r: -r['ev'])
    return out


def update_results(all_games):
    """Final scores for the settlement of calls: data/exchange_edge_results.json {gk: {home, away}}. Kept once seen, the feed drops finished games."""
    fp = os.path.join(ROOT, 'data', 'exchange_edge_results.json')
    res = json.load(open(fp)) if os.path.exists(fp) else {}
    n = 0
    for g in all_games:
        f = g.get('final')
        if f and f.get('home') is not None and f.get('away') is not None and g['key'] not in res:
            res[g['key']] = {'home': f['home'], 'away': f['away'], 'sport': g['sport'], 'start': g['start'], 'ah': g['away']['abbr'], 'hh': g['home']['abbr']}
            n += 1
    json.dump(res, open(fp, 'w'), separators=(',', ':'), sort_keys=True)
    print(f'results: {n} new finals, {len(res)} stored')


def heartbeat(games, now, prev):
    """Per source, the last time any game carried a quote from it. The page shows each source's own age, so a stopped feed does not hide behind a fresh one."""
    seen = dict(prev or {})
    def any_(f):
        return any(f(g) for g in games)
    seen_now = {
        'Pinnacle': any_(lambda g: g.get('pin')),
        'Novig': any_(lambda g: (g.get('nov') or {}).get('ml')),
        'Kalshi': any_(lambda g: (g.get('kal') or {}).get('bid') is not None),
        'Polymarket': any_(lambda g: ((g.get('pm') or {}).get('px') or {}).get('ml')),
        'US books': any_(lambda g: g.get('soft')),
    }
    for k, v in seen_now.items():
        if v:
            seen[k] = now
    return seen


def main():
    src = sys.argv[sys.argv.index('--data') + 1] if '--data' in sys.argv else URL
    now = int(time.time())
    feed = load(src)
    update_results(feed.get('games', []))
    allg = [g for g in feed.get('games', []) if g.get('sport') in BF_SPORTS and g.get('start', 0) > now and g.get('away') and g.get('home') and not g.get('final')]
    games = [g for g in allg if g['sport'] in SPORTS]
    total = 0
    for sp in SPORTS:
        d = os.path.join(ROOT, 'data', 'book_tape', sp)
        os.makedirs(d, exist_ok=True)
        lp = os.path.join(d, 'last.json')
        last = json.load(open(lp)) if os.path.exists(lp) else {}
        new = []
        for g in [x for x in games if x['sport'] == sp]:
            for r in rows_for(g):
                v = [r.get(k) for k in ('ml', 'sp', 'tot', 'lim', 'px', 'nsp', 'ntot')]
                k = f"{r['gk']}|{r['book']}"
                if any(x is not None for x in v) and (k not in last or last[k][1] != v):
                    last[k] = [r['start'], v]
                    new.append({'t': now, **{a: b for a, b in r.items() if b is not None}})
        last = {k: v for k, v in last.items() if v[0] > now - 86400}
        if new:
            with open(os.path.join(d, dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime('%Y-%m') + '.jsonl'), 'a') as f:
                for r in new:
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')
        json.dump(last, open(lp, 'w'), separators=(',', ':'), sort_keys=True)
        total += len(new)
        print(f'{sp} tape: {len(new)} changed lines, {len(last)} tracked')
    rows = live_edges(allg, now)
    prev_seen = {}
    try:
        prev_seen = json.load(open(os.path.join(ROOT, 'data', 'exchange_edge_live.json'))).get('seen') or {}
    except (OSError, ValueError):
        pass
    seen = heartbeat(allg, now, prev_seen)
    st = feed.get('status') or {}
    cov = {sp: {'games': (st.get(sp) or {}).get('games'), 'novig': (st.get(sp) or {}).get('novig'), 'kalshi': (st.get(sp) or {}).get('kalshi'), 'pinnacle': (st.get(sp) or {}).get('pinnacle')} for sp in BF_SPORTS}
    json.dump({'generated': dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec='seconds'), 'feed': feed.get('generated'), 'coverage': cov, 'seen': seen, 'rows': rows},
              open(os.path.join(ROOT, 'data', 'exchange_edge_live.json'), 'w'), separators=(',', ':'))
    print(f'live edges: {len(rows)} rows, {sum(1 for r in rows if r["ev"] > 0)} above zero')
    return total + backfill(allg, now)


if __name__ == '__main__':
    main()
