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

Recording starts the first run after this lands. Earlier lines were never stored for these sports, so none are invented.
Usage: python3 scripts/sharp_tape.py [--data path-or-url]
"""
import datetime as dt, json, os, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/sharp-data/data.json'
SPORTS = ('cfb', 'nba')


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


def main():
    src = sys.argv[sys.argv.index('--data') + 1] if '--data' in sys.argv else URL
    now = int(time.time())
    games = [g for g in load(src).get('games', []) if g.get('sport') in SPORTS and g.get('start', 0) > now and g.get('away') and g.get('home') and not g.get('final')]
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
    return total


if __name__ == '__main__':
    main()
