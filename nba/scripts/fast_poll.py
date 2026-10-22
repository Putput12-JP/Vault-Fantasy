#!/usr/bin/env python3
"""
Fast Polymarket poll for Sharp Price V2: the recorder's main poll runs every 5 to 15 minutes, but a sharp account's edge
is gone in minutes (docs/retro/sharp-money-study.md), so while the recorder sleeps between polls this loop checks the
NBA game markets every minute. Free, keyless, three kinds of request:
  Gamma  /markets?id=..   best bid / ask / last for each game market (100 per request)
  Data   /trades?market=a,b,c&takerOnly=true&filterType=CASH&filterAmount=1000   $1,000+ taker tickets, 25 markets per request
It writes beside the main tapes, never into them, so no existing signal or record changes:
  tape_fast.jsonl   tickets in the main tape's row format, plus `f` = when we fetched it (f - t is our detection delay)
  fastpm.jsonl      change-only quotes {t, k, v: [bid, ask, last]}, same shape as polymarket.jsonl
  fastpoll.jsonl    {t, qok, tok, q, tr, lat} one row per cycle; qok = every quote request answered
follow_ledger.py reads all three next to the main files (docs/sharp-follow-prereg.md, addendum 1).
"""
import datetime as dt, glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sharp import day_dirs, ET                                    # noqa: E402

TYPES = ('moneyline', 'spreads', 'totals')
AHEAD_H = 6                                                       # markets whose game tips within this many hours
INTERVAL_S = 60
MIN_USD = 1000                                                    # same size as a ledger event
LOOKBACK_S = 3600                                                 # first cycle of a process: tickets this far back
OVERLAP_S = 120                                                   # re-read this much behind the cursor; ids dedupe
CHUNK_Q, CHUNK_T, PAGES = 100, 25, 4


def curl(url, tries=2):
    for i in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '20', '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        if code == b'200':
            try:
                return json.loads(body)
            except ValueError:
                return None
        time.sleep(1 + i)
    return None


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def markets(dirs, now, ahead_h=AHEAD_H):
    """{market id: {'cid', 'start', 'type'}} for game markets tipping soon, from the recorder's own meta rows."""
    out = {}
    for d in dirs:
        p = os.path.join(d, 'meta.jsonl')
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get('src') == 'polymarket' and r.get('type') in TYPES and r.get('cid') and r.get('start') and now < r['start'] <= now + ahead_h * 3600:
                    out[r['k']] = {'cid': r['cid'], 'start': r['start'], 'type': r['type']}
    return out


def quote_rows(ms, now, get=curl):
    """({k: [bid, ask, last]}, ok). ok is False if any chunk failed: the poll then cannot vouch for every quote."""
    ks, rows, ok = sorted(ms), {}, True
    for i in range(0, len(ks), CHUNK_Q):
        chunk = ks[i:i + CHUNK_Q]
        r = get('https://gamma-api.polymarket.com/markets?limit=100&' + '&'.join('id=' + k for k in chunk))
        if not isinstance(r, list):
            ok = False
            continue
        for m in r:
            k = str(m.get('id'))
            if k in ms and not m.get('closed'):
                rows[k] = [num(m.get('bestBid')), num(m.get('bestAsk')), num(m.get('lastTradePrice'))]
    return rows, ok and bool(rows)


def trade_row(x, k, now):
    """A data-api trade -> the main tape's row (sharp.poll_tapes): the outcome bought, whichever side of the book the taker was on."""
    usd = (x.get('price') or 0) * (x.get('size') or 0)
    buy = x.get('side') == 'BUY'
    oi = x.get('outcomeIndex') if buy else 1 - (x.get('outcomeIndex') or 0)
    return {'t': x['timestamp'], 's': 'pm', 'k': k, 'o': oi, 'usd': round(usd), 'px': round(x['price'] if buy else 1 - x['price'], 4),
            'w': x.get('proxyWallet'), 'who': x.get('pseudonym') or x.get('name'),
            'id': f"{(x.get('transactionHash') or '')[:18]}:{oi}:{round(x.get('size') or 0)}", 'f': int(now)}


def trade_rows(ms, since, now, seen, get=curl):
    """New $1,000+ pre-tip tickets since `since`. ({rows}, ok)."""
    bycid = {m['cid']: k for k, m in ms.items()}
    cids, rows, ok = sorted(bycid), [], True
    for i in range(0, len(cids), CHUNK_T):
        chunk = cids[i:i + CHUNK_T]
        for page in range(PAGES):
            r = get(f"https://data-api.polymarket.com/trades?market={','.join(chunk)}&takerOnly=true&limit=500&offset={page * 500}"
                    f"&filterType=CASH&filterAmount={MIN_USD}")
            if not isinstance(r, list):
                ok = False
                break
            old = False
            for x in r:
                k = bycid.get(x.get('conditionId'))
                if not k:
                    continue
                if x.get('timestamp', 0) < since:
                    old = True
                    continue
                row = trade_row(x, k, now)
                if row['usd'] >= MIN_USD and row['t'] < ms[k]['start'] and row['id'] not in seen:
                    seen.add(row['id'])
                    rows.append(row)
            if old or len(r) < 500:
                break
    return rows, ok


class State:
    def __init__(self, root, now):
        self.root = root
        self.warm = False                                         # first cycle reads an hour of backlog: its tickets have no honest detection delay
        self.last = {}                                            # k -> last quote written (change-only)
        self.seen = set()
        self.cursor = now - LOOKBACK_S
        for d in day_dirs(root, now, 1):                          # ids already saved, by either tape
            for name in ('tape.jsonl', 'tape_fast.jsonl'):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    with open(p) as f:
                        for line in f:
                            try:
                                self.seen.add(json.loads(line)['id'])
                            except (ValueError, KeyError):
                                pass


def append(path, rows):
    if rows:
        with open(path, 'a') as f:
            for r in rows:
                f.write(json.dumps(r, separators=(',', ':')) + '\n')


def cycle(st, now=None, get=curl):
    """One pass: quotes (change-only), new tickets, one poll-log row. Returns the poll row."""
    now = int(now or time.time())
    dirs = day_dirs(st.root, now, 2)
    ms = markets(dirs, now)
    day = os.path.join(st.root, 'snapshots', dt.datetime.fromtimestamp(now, ET).date().isoformat())
    if not ms or not os.path.isdir(day):
        return None
    q, qok = quote_rows(ms, now, get)
    chg = [{'t': now, 'k': k, 'v': v} for k, v in q.items() if st.last.get(k) != v]
    for k, v in q.items():
        st.last[k] = v
    tr, tok = trade_rows(ms, st.cursor - OVERLAP_S, now, st.seen, get)
    if tok and tr:
        st.cursor = max(st.cursor, max(r['t'] for r in tr))
    elif tok:
        st.cursor = max(st.cursor, now - OVERLAP_S)
    if not st.warm:
        for r in tr:
            r.pop('f', None)
        st.warm = True
    lat = sorted(r['f'] - r['t'] for r in tr if 'f' in r)
    append(os.path.join(day, 'fastpm.jsonl'), chg)
    append(os.path.join(day, 'tape_fast.jsonl'), sorted(tr, key=lambda r: r['t']))
    poll = {'t': now, 'qok': qok, 'tok': tok, 'q': len(q), 'tr': len(tr), 'lat': lat[len(lat) // 2] if lat else None}
    append(os.path.join(day, 'fastpoll.jsonl'), [poll])
    return poll


def sleep_polling(root, until, interval=INTERVAL_S, get=curl):
    """Stand in for time.sleep(until - now) in the recorder's loop. A failed cycle never ends the sleep early or raises."""
    st = None
    while True:
        left = until - time.time()
        if left <= 0:
            return
        try:
            st = st or State(root, time.time())
            p = cycle(st, get=get)
            if p:
                print(f"  fast poll  {p['q']} quotes, {p['tr']} new $1k+ tickets, qok {p['qok']} tok {p['tok']}" + (f", median delay {p['lat']}s" if p['lat'] is not None else ''), flush=True)
        except Exception as e:                                    # keep the recorder alive; the poll log shows the gap
            print(f'  fast poll failed: {e}', flush=True)
        time.sleep(max(1, min(interval, until - time.time())))
