#!/usr/bin/env python3
"""
Backfill Kalshi NBA markets (player props + game markets) with pre-tip prices.

Kalshi moves settled markets to /historical/* once they pass the historical
cutoff (GET /historical/cutoff). Two phases, both resumable:

  1. markets   /historical/markets?series_ticker=S  (+ live /markets for anything
               settled after the cutoff) -> nba/raw/kalshi/markets_<S>.jsonl
  2. prices    per traded market: /historical/trades?ticker=T&max_ts=<tip>
               The tape comes newest-first, so one call returns the trades just
               before tip. We keep the last trade and a volume-weighted price over
               the final 30 min.  -> nba/raw/kalshi/prices_<S>.jsonl

Tip time is the ESPN scheduled start, joined on date + teams from the hoopR
schedule. Falls back to occurrence_datetime - 3h (Kalshi sets it ~3h after tip).

Ladder strikes: a player market "X: 25+" is YES iff stat >= 25, i.e. over 24.5
(floor_strike). The full ladder per player is a market-implied distribution.

  python3 nba/scripts/backfill_kalshi.py              # all default series
  python3 nba/scripts/backfill_kalshi.py KXNBAPTS     # one series
  python3 nba/scripts/backfill_kalshi.py --markets-only
  python3 nba/scripts/backfill_kalshi.py --am KXNBAGAME KXNBASPREAD   # 1pm ET prices (game model bet clock)
Phase 2 fetches the pre-tip price only (see price_market for the tip-4h price).
"""
import csv, datetime as dt, glob, json, os, subprocess, sys, threading, time, concurrent.futures as cf

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
OUT = os.path.join(RAW, 'kalshi')
K = 'https://api.elections.kalshi.com/trade-api/v2'

PROP_SERIES = ['KXNBAPTS', 'KXNBAREB', 'KXNBAAST', 'KXNBA3PT', 'KXNBAPRA', 'KXNBAPR', 'KXNBAPA', 'KXNBARA']
GAME_SERIES = ['KXNBAGAME', 'KXNBASPREAD', 'KXNBATOTAL', 'KXNBATEAMTOTAL']

# Kalshi team codes -> ESPN abbreviations (hoopR schedule)
TEAM = {'SAS': 'SA', 'NYK': 'NY', 'GSW': 'GS', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH', 'PHO': 'PHX', 'BRK': 'BKN'}


# Kalshi 429s a burst of parallel readers, and per-worker exponential backoff
# then stalls the whole run (first attempt: ~2 markets/s). One shared pacer
# keeps every worker under the limit instead.
RATE_PER_S = 12
_pace_lock, _next_at = threading.Lock(), [0.0]


def pace():
    with _pace_lock:
        now = time.monotonic()
        wait = _next_at[0] - now
        _next_at[0] = max(now, _next_at[0]) + 1 / RATE_PER_S
    if wait > 0:
        time.sleep(wait)


def get(url, tries=6):
    delay = 1.0
    for _ in range(tries):
        pace()
        p = subprocess.run(['curl', '-s', '--max-time', '40', '-w', '\n%{http_code}', url], capture_output=True, text=True)
        body, _, code = p.stdout.rpartition('\n')
        if code == '200':
            try:
                return json.loads(body)
            except Exception:
                pass
        if code == '404':
            return None
        time.sleep(delay)  # 429 / transient: back off
        delay = min(delay * 2, 8)
    return None


def iso_ts(s):
    return int(dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())


# ── tip times from the hoopR schedule ──────────────────────────────────────
def tip_index():
    idx = {}
    for path in glob.glob(os.path.join(RAW, 'hoopr', 'schedule_*.csv')):
        for g in csv.DictReader(open(path)):
            d = dt.datetime.fromisoformat(g['date'].replace('Z', '+00:00'))
            local = (d - dt.timedelta(hours=5)).date()  # ET-ish game date, what Kalshi tickers use
            for day in (local, local - dt.timedelta(days=1), local + dt.timedelta(days=1)):
                idx.setdefault((day.isoformat(), g['away_abbreviation'], g['home_abbreviation']),
                               (int(d.timestamp()), int(g['id'])))
    return idx


MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}


def parse_event(event_ticker):
    """KXNBAPTS-26JUN10SASNYK -> ('2026-06-10', 'SA', 'NY')"""
    code = event_ticker.split('-')[1]
    yy, mon, dd, teams = code[:2], code[2:5], code[5:7], code[7:]
    if mon not in MONTHS or len(teams) < 4:
        return None
    day = dt.date(2000 + int(yy), MONTHS[mon], int(dd)).isoformat()
    for cut in (3, 2, 4):  # most codes are 3+3; a few teams are 2 or 4 letters
        a, h = teams[:cut], teams[cut:]
        if 2 <= len(h) <= 4:
            yield day, TEAM.get(a, a), TEAM.get(h, h)


def tip_for(m, idx):
    for key in parse_event(m['event_ticker']) or []:
        if key in idx:
            return idx[key][0], idx[key][1], 'espn'
    occ = m.get('occurrence_datetime') or m.get('expected_expiration_time')
    return (iso_ts(occ) - 3 * 3600 if occ else None), None, 'occ-3h'


# ── phase 1: market lists ──────────────────────────────────────────────────
KEEP = ('ticker', 'event_ticker', 'title', 'yes_sub_title', 'floor_strike', 'cap_strike', 'strike_type',
        'custom_strike', 'result', 'volume_fp', 'open_time', 'close_time', 'occurrence_datetime',
        'expected_expiration_time', 'settlement_value_dollars', 'expiration_value')


def list_markets(series):
    path = os.path.join(OUT, f'markets_{series}.jsonl')
    seen = {}
    for base in (f'{K}/historical/markets?series_ticker={series}', f'{K}/markets?series_ticker={series}&status=settled'):
        cur = ''
        while True:
            d = get(base + '&limit=1000' + (f'&cursor={cur}' if cur else ''))
            if not d:
                break
            for m in d.get('markets', []):
                seen[m['ticker']] = {k: m.get(k) for k in KEEP}
            cur = d.get('cursor')
            if not cur or not d.get('markets'):
                break
    with open(path, 'w') as f:
        for m in seen.values():
            f.write(json.dumps(m, separators=(',', ':')) + '\n')
    return list(seen.values())


# ── phase 2: pre-tip prices from the trade tape ────────────────────────────
def summarize(trades, end_ts, window=1800):
    if not trades:
        return None
    last = trades[0]
    num = den = 0.0
    for t in trades:
        if iso_ts(t['created_time']) < end_ts - window:
            break
        c = float(t['count_fp'])
        num += float(t['yes_price_dollars']) * c
        den += c
    return {'last': float(last['yes_price_dollars']), 'last_ts': last['created_time'],
            'vwap30': round(num / den, 4) if den else None, 'vol30': round(den, 2), 'n': len(trades)}


def price_market(args, with_am=False):
    m, tip, gid, src = args
    out = {'ticker': m['ticker'], 'game_id': gid, 'tip_ts': tip, 'tip_src': src}
    # Every 2025-26 market is past the historical cutoff, so /historical/trades is
    # the only tape needed. The tip-4h "am" price doubles the calls; it is fetched
    # later only for strikes near the book line (--with-am).
    for label, end in (('pretip', tip),) + ((('am', tip - 4 * 3600),) if with_am else ()):
        d = get(f"{K}/historical/trades?ticker={m['ticker']}&max_ts={end}&limit=200")
        out[label] = summarize((d or {}).get('trades', []), end)
    return out


def price_am(series, traded, idx):
    """Price at 1pm ET on game day (capped at tip-30m): the bet-time clock the game model is tested on.
    -> nba/raw/kalshi/prices_am_<S>.jsonl"""
    sys.path.insert(0, HERE)
    from nba_common import et
    path = os.path.join(OUT, f'prices_am_{series}.jsonl')
    done = {json.loads(l)['ticker'] for l in open(path)} if os.path.exists(path) else set()
    jobs = []
    for m in traded:
        if m['ticker'] in done:
            continue
        tip, gid, src = tip_for(m, idx)
        if not tip:
            continue
        tip_utc = dt.datetime.fromtimestamp(tip, dt.timezone.utc)
        tip_et = et(tip_utc)
        am_et = min(tip_et.replace(hour=13, minute=0), tip_et - dt.timedelta(minutes=30))
        am_ts = tip - int((tip_et - am_et).total_seconds())
        jobs.append((m, gid, tip, am_ts))

    def one(j):
        m, gid, tip, am_ts = j
        d = get(f"{K}/historical/trades?ticker={m['ticker']}&max_ts={am_ts}&limit=200")
        return {'ticker': m['ticker'], 'game_id': gid, 'tip_ts': tip, 'am_ts': am_ts,
                'am': summarize((d or {}).get('trades', []), am_ts, window=3 * 3600)}
    n = 0
    with open(path, 'a') as f, cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(one, jobs):
            f.write(json.dumps(r, separators=(',', ':')) + '\n')
            n += 1
    print(f'{series}: am-priced {n}', flush=True)


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    series = [a for a in argv if a.startswith('KX')] or PROP_SERIES + GAME_SERIES
    idx = tip_index()
    for s in series:
        t0 = time.time()
        mk = list_markets(s)
        traded = [m for m in mk if float(m.get('volume_fp') or 0) > 0]
        print(f'{s}: {len(mk)} markets, {len(traded)} traded ({time.time() - t0:.0f}s)', flush=True)
        if '--markets-only' in argv:
            continue
        if '--am' in argv:
            price_am(s, traded, idx)
            continue
        path = os.path.join(OUT, f'prices_{s}.jsonl')
        done = set()
        if os.path.exists(path):
            done = {json.loads(l)['ticker'] for l in open(path)}
        jobs = []
        for m in traded:
            if m['ticker'] in done:
                continue
            tip, gid, src = tip_for(m, idx)
            if tip:
                jobs.append((m, tip, gid, src))
        n = 0
        with open(path, 'a') as f, cf.ThreadPoolExecutor(8) as ex:
            for r in ex.map(price_market, jobs):
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
                n += 1
                if n % 2000 == 0:
                    f.flush()
                    print(f'  {s} {n}/{len(jobs)}', flush=True)
        print(f'{s}: priced {n} ({time.time() - t0:.0f}s)', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
