#!/usr/bin/env python3
"""
Polymarket game markets (NFL, college football, NBA) from the Pendulum Flow orderbook archive.

Source: https://archive.pendulumflow.com, one Parquet file per UTC hour of every Polymarket order book, free, CC BY 4.0
(credit "pendulumflow" for v3). Published about 5 hours behind, so this is for grading and testing, not live signals.
Market ids come from Polymarket's Gamma API (series per sport); the archive stores a market as its 32 raw bytes and an
outcome token as its 32-byte big-endian integer, so both filter with from_hex().

  closes   Each finished game's Polymarket price at kickoff for the moneyline, every spread and every total line on its
           ladder: the last quote before kickoff (mid of bid and ask when the spread is 10c or tighter, else the last
           trade), both outcome tokens averaged into one chance. -> data/pm_closes.json, kept for the season.
  tape     Every moneyline trade in a date window, for tests (scripts/test_pm_vs_books.py). Cached per hour.

Usage:
  python3 scripts/pm_archive.py closes --sports nfl,nba,cfb --days 4
  python3 scripts/pm_archive.py tape --sport nfl --since 2026-09-03 --until 2026-09-30 --cache .cache/pm_archive
Needs: pip install duckdb pytz
"""
import argparse, datetime as dt, gzip, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SERIES = {'nfl': 12185, 'cfb': 12756, 'nba': 10345}
V3_START = dt.datetime(2026, 8, 18, 6, tzinfo=dt.timezone.utc)
LAG_H = 6                      # the archive publishes about 5 hours behind; wait a little longer
URL = 'https://dl.pendulumflow.com/v3/{d}/{h:02d}/{d}T{h:02d}.parquet'
CLOSES = os.path.join(ROOT, 'data', 'pm_closes.json')
CREDIT = 'Polymarket prices from the Pendulum Flow orderbook archive (archive.pendulumflow.com), CC BY 4.0'
TYPES = ('moneyline', 'spreads', 'totals')


def curl_json(url, tries=3):
    for i in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '60', url], capture_output=True)
        try:
            return json.loads(p.stdout)
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ts(s):
    s = s.replace(' ', 'T').replace('Z', '+00:00')
    return dt.datetime.fromisoformat(s + ':00' if s.endswith('+00') else s).timestamp()


def games(sport, since, until):
    """Game events (those with a moneyline) kicking off in [since, until): slug, title, kickoff and their moneyline,
    spread and total markets with outcomes, token ids (as 64-hex) and line."""
    out, seen = [], set()
    for closed in ('true', 'false'):
        off = 0
        while True:
            q = (f'https://gamma-api.polymarket.com/events?series_id={SERIES[sport]}&closed={closed}&limit=100&offset={off}'
                 f'&end_date_min={iso(since)}&end_date_max={iso(until + 86400)}')
            E = curl_json(q) or []
            for e in E:
                ms = [m for m in e.get('markets') or [] if m.get('sportsMarketType') in TYPES]
                if not any(m['sportsMarketType'] == 'moneyline' for m in ms) or e['id'] in seen:
                    continue
                k = e.get('startTime') or e.get('endDate')
                try:
                    ko = ts(k)
                except Exception:
                    continue
                if not (since <= ko < until):
                    continue
                seen.add(e['id'])
                mk = []
                for m in ms:
                    try:
                        toks = [hex(int(x))[2:].zfill(64) for x in json.loads(m['clobTokenIds'])]
                        outs = json.loads(m['outcomes'])
                    except Exception:
                        continue
                    mk.append({'cid': m['conditionId'].lower()[2:], 'type': m['sportsMarketType'], 'line': m.get('line'),
                               'outcomes': outs, 'tokens': toks, 'q': m.get('question')})
                out.append({'sport': sport, 'slug': e.get('slug'), 'title': e.get('title'), 'kickoff': int(ko), 'markets': mk})
            if len(E) < 100:
                break
            off += 100
    return sorted(out, key=lambda g: g['kickoff'])


def con():
    import duckdb
    c = duckdb.connect()
    c.execute('INSTALL httpfs; LOAD httpfs;')
    return c


def hour_url(t):
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return URL.format(d=d.strftime('%Y-%m-%d'), h=d.hour)


def in_list(cids):
    return ', '.join(f"from_hex('{c}')" for c in cids)


def query(c, t, event, cols, cids, before=None):
    """Rows of one event type for these markets in the hour starting at t (None if the hour is not published)."""
    w = f"event_type = '{event}' AND market IN ({in_list(cids)})"
    if before is not None:
        w += f' AND epoch_ms(timestamp) < {int(before * 1000)}'
    try:
        return c.execute(f"SELECT {cols} FROM read_parquet('{hour_url(t)}') WHERE {w}").fetchall()
    except Exception as e:
        if '404' in str(e) or 'Not Found' in str(e):
            return None
        raise


# ── closes ─────────────────────────────────────────────────────────────────────────────────────
def close_of(g, c):
    """Last quote before kickoff for every outcome token of the game's markets (kickoff hour, then the hour before)."""
    cids = [m['cid'] for m in g['markets']]
    ko, last = g['kickoff'], {}
    for t in ((ko // 3600) * 3600, (ko // 3600) * 3600 - 3600):
        rows = query(c, t, 'best_bid_ask', "lower(hex(asset_id)), epoch_ms(timestamp), best_bid, best_ask", cids, before=ko)
        if rows is None:
            return None
        for a, tm, b, k in rows:
            if a not in last or tm > last[a][0]:
                last[a] = (tm, float(b) if b is not None else None, float(k) if k is not None else None)
        trades = query(c, t, 'last_trade_price', "lower(hex(asset_id)), epoch_ms(timestamp), price", cids, before=ko) or []
        for a, tm, p in trades:
            key = 'trade:' + a
            if key not in last or tm > last[key][0]:
                last[key] = (tm, float(p))
        if all(any(tk in last for tk in m['tokens']) for m in g['markets'] if m['type'] == 'moneyline'):
            break
    def mid(tok):
        q = last.get(tok)
        if q and q[1] is not None and q[2] is not None and 0 < q[1] <= q[2] and q[2] - q[1] <= 0.10:
            return (q[1] + q[2]) / 2, q[1], q[2]
        tr = last.get('trade:' + tok)
        return (tr[1], None, None) if tr else (None, None, None)
    res = {'ml': None, 'spreads': [], 'totals': []}
    for m in g['markets']:
        (m0, b0, a0), (m1, b1, a1) = mid(m['tokens'][0]), mid(m['tokens'][1])
        if m0 is None and m1 is None:
            continue
        p0 = (m0 + (1 - m1)) / 2 if m0 is not None and m1 is not None else m0 if m0 is not None else 1 - m1
        row = {'outcomes': m['outcomes'], 'p': round(p0, 4), 'bid': b0, 'ask': a0}
        if m['type'] == 'moneyline':
            res['ml'] = row
        elif m['type'] == 'spreads':
            res['spreads'].append(dict(row, line=m['line']))
        else:
            res['totals'].append(dict(row, line=m['line']))
    res['spreads'].sort(key=lambda r: (r['outcomes'][0], r['line'] or 0))
    res['totals'].sort(key=lambda r: r['line'] or 0)
    return res


def cmd_closes(a):
    now = time.time()
    data = json.load(open(CLOSES)) if os.path.exists(CLOSES) else {'games': {}}
    G = data.setdefault('games', {})
    c, n = con(), 0
    for sport in a.sports.split(','):
        for g in games(sport, max(V3_START.timestamp(), now - a.days * 86400), now - LAG_H * 3600):
            k = f"{sport}|{g['slug']}"
            if k in G and not a.force:
                continue
            r = close_of(g, c)
            if r is None or r['ml'] is None:
                print(f'  {k}: hour not published yet or no moneyline quote', flush=True)
                continue
            G[k] = {'sport': sport, 'slug': g['slug'], 'title': g['title'], 'kickoff': g['kickoff'], **r}
            n += 1
            print(f"  {k}: ml {r['ml']['outcomes'][0]} {r['ml']['p']}, {len(r['spreads'])} spreads, {len(r['totals'])} totals", flush=True)
    data.update(generated=iso(now), credit=CREDIT)
    json.dump(data, open(CLOSES, 'w'), separators=(',', ':'), sort_keys=True)
    print(f'closes: {n} new, {len(G)} games in {os.path.relpath(CLOSES, ROOT)}')


# ── tape ───────────────────────────────────────────────────────────────────────────────────────
def cmd_tape(a):
    since = dt.datetime.fromisoformat(a.since).replace(tzinfo=dt.timezone.utc).timestamp()
    until = dt.datetime.fromisoformat(a.until).replace(tzinfo=dt.timezone.utc).timestamp()
    G = games(a.sport, since, until)
    ml = {m['cid']: (g['slug'], m) for g in G for m in g['markets'] if m['type'] == 'moneyline'}
    os.makedirs(a.cache, exist_ok=True)
    json.dump(G, open(os.path.join(a.cache, f'{a.sport}_games.json'), 'w'))
    first = max(V3_START.timestamp(), min(g['kickoff'] for g in G) - a.lookback * 86400)
    hours = list(range(int(first // 3600) * 3600, int(max(g['kickoff'] for g in G)) + 3600, 3600))
    print(f'{len(G)} games, {len(ml)} moneylines, {len(hours)} hours', flush=True)
    cids = sorted(ml)

    def one(t):
        p = os.path.join(a.cache, f'{a.sport}_{iso(t)[:13]}.json.gz')
        if os.path.exists(p):
            return 0
        c = con()
        rows = query(c, t, 'last_trade_price', "lower(hex(market)), lower(hex(asset_id)), epoch_ms(timestamp), price, size", cids)
        if rows is None:
            return -1
        with gzip.open(p, 'wt') as f:
            json.dump([[m, aid, tm, float(pr), float(sz)] for m, aid, tm, pr, sz in rows], f)
        return len(rows)
    done = 0
    with ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(one, hours)):
            done += max(r, 0)
            if i % 48 == 0:
                print(f'  {i}/{len(hours)} hours, {done} trades', flush=True)
    print(f'tape: {done} new trades cached in {a.cache}')


def main():
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='cmd', required=True)
    c = s.add_parser('closes'); c.add_argument('--sports', default='nfl,cfb,nba'); c.add_argument('--days', type=float, default=4); c.add_argument('--force', action='store_true')
    t = s.add_parser('tape'); t.add_argument('--sport', default='nfl'); t.add_argument('--since', required=True); t.add_argument('--until', required=True)
    t.add_argument('--cache', default=os.path.join(ROOT, '.cache', 'pm_archive')); t.add_argument('--lookback', type=float, default=7)
    a = p.parse_args()
    {'closes': cmd_closes, 'tape': cmd_tape}[a.cmd](a)


if __name__ == '__main__':
    main()
