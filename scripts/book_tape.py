#!/usr/bin/env python3
"""
NFL sportsbook tape: every book's moneyline, main spread and main total, appended only when it changes.

Feeds the declared re-test in docs/pm-vs-books-test.md (weeks 4-7): the lineup feed fetches book lines 2 to 4 times a
day, too few to tell who moves first, so this records them every run of .github/workflows/nfl-book-tape.yml.
Free, keyless sources only: Action Network's public scoreboard (DraftKings, FanDuel, BetMGM, BetRivers, bet365 and
its consensus) and Pinnacle's public guest API. The observation time is when this run fetched the line.

Row: {"t": unix, "src": "an" | "pin", "book", "away", "home", "start", "ml": [away, home], "sp": [home line, home, away],
      "tot": [line, over, under]}  ->  data/book_tape/nfl/<YYYY-MM>.jsonl ; last state in data/book_tape/nfl/last.json
"""
import datetime as dt, json, os, subprocess, time

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


def main():
    now = int(time.time())
    os.makedirs(DIR, exist_ok=True)
    lp = os.path.join(DIR, 'last.json')
    last = json.load(open(lp)) if os.path.exists(lp) else {}
    new = []
    for r in action(now) + pinnacle(now):
        k = f"{r['src']}|{r['book']}|{r['away']}@{r['home']}|{r['start']}"
        v = [r['ml'], r['sp'], r['tot']]
        if v != [None, None, None] and last.get(k) != v:
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
