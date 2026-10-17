#!/usr/bin/env python3
"""
NFL sportsbook tape: every book's moneyline, main spread and main total, appended only when it changes.

Feeds the declared re-test in docs/pm-vs-books-test.md (weeks 4-7): the lineup feed fetches book lines 2 to 4 times a
day, too few to tell who moves first, so this records them every run of .github/workflows/nfl-book-tape.yml.
Free, keyless sources only: Action Network's public scoreboard (DraftKings, FanDuel, BetMGM, BetRivers, bet365 and
its consensus), Pinnacle's public guest API, and the Novig and Kalshi exchanges. The two exchanges quote a win chance
rather than a price, so their rows carry "px": [home best bid, home best ask] (0 to 1) and no ml/sp/tot; the Sharp Money
line chart plots the mid on its Money tab, and only when the bid-ask gap is 10 points or less. Recording began 2026-10-17,
because the exchange quotes were never stored before that, so there is no earlier history to backfill. The observation time is when this run fetched the line.

Row: {"t": unix, "src": "an" | "pin", "book", "away", "home", "start", "ml": [away, home], "sp": [home line, home, away],
      "tot": [line, over, under]}  ->  data/book_tape/nfl/<YYYY-MM>.jsonl ; last state in data/book_tape/nfl/last.json
"""
import datetime as dt, json, os, re, subprocess, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIR = os.path.join(ROOT, 'data', 'book_tape', 'nfl')
UA = 'Mozilla/5.0 (VaultFantasy book tape)'
AN_BOOKS = {15: 'Consensus', 30: 'Open', 68: 'DraftKings', 69: 'FanDuel', 75: 'BetMGM', 71: 'BetRivers', 79: 'bet365'}
PIN_KEY = 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R'           # Pinnacle's public web-client key (same as fetch-sharp-money.mjs)
ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
NICK = {'Cardinals': 'ARI', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Bills': 'BUF', 'Panthers': 'CAR', 'Bears': 'CHI', 'Bengals': 'CIN',
        'Browns': 'CLE', 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB', 'Texans': 'HOU', 'Colts': 'IND',
        'Jaguars': 'JAX', 'Chiefs': 'KC', 'Chargers': 'LAC', 'Rams': 'LAR', 'Raiders': 'LV', 'Dolphins': 'MIA', 'Vikings': 'MIN',
        'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG', 'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA',
        '49ers': 'SF', 'Buccaneers': 'TB', 'Titans': 'TEN', 'Commanders': 'WAS'}


def get(url, hdr=(), tries=1):
    """JSON or None. Pinnacle's guest API now and then 403s a cloud IP for a few seconds, so it gets retries."""
    cmd = ['curl', '-s', '--compressed', '--max-time', '30', '-A', UA, '-H', 'Accept: application/json']
    for h in hdr:
        cmd += ['-H', h]
    for i in range(tries):
        try:
            return json.loads(subprocess.run(cmd + [url], capture_output=True).stdout)
        except ValueError:
            time.sleep(1.5 * (i + 1)) if i + 1 < tries else None
    return None


def action(now):
    rows = []
    for d in range(8):
        day = dt.datetime.fromtimestamp(now + d * 86400 - 5 * 3600, dt.timezone.utc).strftime('%Y%m%d')
        js = get(f'https://api.actionnetwork.com/web/v2/scoreboard/nfl?bookIds={",".join(map(str, AN_BOOKS))}&date={day}&periods=event') or {}
        for g in js.get('games', []):
            T = {t['id']: t for t in g.get('teams', [])}
            a, h = T.get(g.get('away_team_id')), T.get(g.get('home_team_id'))
            if not a or not h:
                continue
            start = int(dt.datetime.fromisoformat(g['start_time'].replace('Z', '+00:00')).timestamp())
            if start <= now:
                continue
            for bid, m in (g.get('markets') or {}).items():
                ev, pick = (m or {}).get('event') or {}, lambda arr, s: next((o for o in arr or [] if o.get('side') == s), None)
                mh, ma, sh, sa, to, tu = pick(ev.get('moneyline'), 'home'), pick(ev.get('moneyline'), 'away'), pick(ev.get('spread'), 'home'), pick(ev.get('spread'), 'away'), pick(ev.get('total'), 'over'), pick(ev.get('total'), 'under')
                rows.append({'src': 'an', 'book': AN_BOOKS.get(int(bid), bid), 'away': ALIAS.get(a['abbr'], a['abbr']), 'home': ALIAS.get(h['abbr'], h['abbr']), 'start': start,
                             'ml': [ma['odds'], mh['odds']] if mh and ma else None, 'sp': [sh['value'], sh['odds'], sa['odds']] if sh and sa else None,
                             'tot': [to['value'], to['odds'], tu['odds']] if to and tu else None})
    return rows


def pinnacle(now):
    hdr = (f'X-API-Key: {PIN_KEY}', 'Referer: https://www.pinnacle.com/', 'Origin: https://www.pinnacle.com')
    mus = get('https://guest.api.arcadia.pinnacle.com/0.1/leagues/889/matchups', hdr, tries=4) or []
    mk = get('https://guest.api.arcadia.pinnacle.com/0.1/leagues/889/markets/straight', hdr, tries=4) or []
    games = {}
    for m in mus:
        if m.get('type') != 'matchup' or m.get('parentId') or (m.get('units') and m['units'] != 'Regular'):
            continue
        h = next((p for p in m['participants'] if p['alignment'] == 'home'), None)
        a = next((p for p in m['participants'] if p['alignment'] == 'away'), None)
        hc, ac = h and NICK.get(h['name'].split()[-1]), a and NICK.get(a['name'].split()[-1])
        start = int(dt.datetime.fromisoformat(m['startTime'].replace('Z', '+00:00')).timestamp())
        if hc and ac and start > now:
            games[m['id']] = {'src': 'pin', 'book': 'Pinnacle', 'away': ac, 'home': hc, 'start': start, 'ml': None, 'sp': None, 'tot': None}
    for x in mk:
        g = games.get(x.get('matchupId'))
        if not g or x.get('period') != 0 or x.get('isAlternate') or (x.get('status') and x['status'] != 'open'):
            continue
        pr = lambda d: next((p for p in x['prices'] if p.get('designation') == d), None)
        if x['type'] == 'moneyline' and pr('home') and pr('away'):
            g['ml'] = [pr('away')['price'], pr('home')['price']]
        elif x['type'] == 'spread' and pr('home') and pr('away'):
            g['sp'] = [pr('home')['points'], pr('home')['price'], pr('away')['price']]
        elif x['type'] == 'total' and pr('over') and pr('under'):
            g['tot'] = [pr('over')['points'], pr('over')['price'], pr('under')['price']]
    return list(games.values())


def exch_match(games):
    """(away, home) -> start for the upcoming games the sportsbook sources already know, so exchange rows share their start."""
    m = {}
    for r in games:
        k = (r['away'], r['home'])
        m[k] = min(m.get(k, r['start']), r['start'])
    return m


def norm(x):
    x = str(x).upper()
    return ALIAS.get(x, x)


def kalshi(now, known):
    """Kalshi winner market per NFL game: the home contract's best yes bid and ask."""
    rows, cursor = [], ''
    for _ in range(5):
        js = get('https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXNFLGAME&status=open&limit=200&with_nested_markets=true' + (f'&cursor={cursor}' if cursor else '')) or {}
        for ev in js.get('events', []):
            tk = ev.get('event_ticker', '')
            code = tk.rsplit('-', 1)[-1][7:] if '-' in tk else ''             # e.g. 26OCT18HOUJAC -> HOUJAC (date is 7 chars)
            if len(code) != 6:
                continue
            away, home = norm(code[:3]), norm(code[3:])
            mk = next((m for m in ev.get('markets', []) if norm(m.get('ticker', '').rsplit('-', 1)[-1]) == home), None)
            start = known.get((away, home))
            try:
                bid, ask = round(float(mk['yes_bid_dollars']), 3), round(float(mk['yes_ask_dollars']), 3)
            except (TypeError, ValueError, KeyError):
                continue
            if start and 0 < bid <= ask < 1:
                rows.append({'src': 'kal', 'book': 'Kalshi', 'away': away, 'home': home, 'start': start, 'px': [bid, ask]})
        cursor = js.get('cursor')
        if not cursor or not js.get('events'):
            break
    return rows


def novig(now, known):
    """Novig winner market per NFL game: home best bid, and the ask implied by the best bid on the away outcome."""
    N = 'https://api.novig.com/v3/public/catalog'
    rows = []
    for ev in (get(f'{N}/events?league=NFL&limit=500') or {}).get('items', []):
        mt = re.match(r'^(.+?) @ (.+)$', ev.get('description') or '')
        if not mt:
            continue
        away, home = NICK.get(mt.group(1).split()[-1]), NICK.get(mt.group(2).split()[-1])
        start = known.get((away, home))
        if not (away and home and start):
            continue
        mk = next((m for m in (get(f"{N}/markets?event={ev['eventId']}&marketType=MONEY&limit=10") or {}).get('items', []) if m.get('status') == 'OPEN' and len(m.get('outcomes') or []) == 2), None)
        book = mk and get(f"{N}/markets/{mk['marketId']}/book")
        if not book:
            continue
        best = {}
        for o in mk['outcomes']:
            px = [float(x['price']) for x in (book.get('orders') or {}).get(o['outcomeId'], [])]
            best[norm(o['name'])] = max(px) if px else None
        bh, ba = best.get(home), best.get(away)
        if bh is not None and ba is not None and bh + ba < 1:
            rows.append({'src': 'nov', 'book': 'Novig', 'away': away, 'home': home, 'start': start, 'px': [round(bh, 3), round(1 - ba, 3)]})
    return rows


def main():
    now = int(time.time())
    os.makedirs(DIR, exist_ok=True)
    lp = os.path.join(DIR, 'last.json')
    last = json.load(open(lp)) if os.path.exists(lp) else {}
    new = []
    books = action(now) + pinnacle(now)
    known = exch_match(books)
    for r in books + kalshi(now, known) + novig(now, known):
        k = f"{r['src']}|{r['book']}|{r['away']}@{r['home']}|{r['start']}"
        v = [r['ml'], r['sp'], r['tot']] if 'px' not in r else [None, None, None, r['px']]      # sportsbook keys keep their 3-item state, so no old row is rewritten
        if (v[:3] != [None, None, None] or 'px' in r) and last.get(k) != v:
            last[k] = v
            new.append({'t': now, **r})
    last = {k: v for k, v in last.items() if int(k.rsplit('|', 1)[1]) > now - 86400}      # forget games that have started
    if new:
        with open(os.path.join(DIR, dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime('%Y-%m') + '.jsonl'), 'a') as f:
            for r in new:
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
    json.dump(last, open(lp, 'w'), separators=(',', ':'), sort_keys=True)
    print(f'book tape: {len(new)} changed lines, {len(last)} tracked')


if __name__ == '__main__':
    main()
