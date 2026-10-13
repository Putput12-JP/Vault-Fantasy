#!/usr/bin/env python3
"""ESPN's opening spread (DraftKings) for every college game in data/cfbd/lines_<year>.json. Free and keyless.
Writes data/cfbd/espn_opens_<year>.json: one row per game, home spread (+ = home underdog), keyed by the ESPN event id CFBD already carries.
The CFB model (scripts/cfb_model.py cfbd_opens) reads it ahead of CFBD's spreadOpen, because ESPN records the open as its own field.

  python3 scripts/fetch_espn_opens.py [--year 2026]

Re-runs MERGE into the stored file and never lose an open: a stored open is kept when ESPN stops returning one.
"""
import argparse, json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = 'https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/events/{i}/competitions/{i}/odds'


def num(s):
    m = re.match(r'^\s*([+-]?\d+(?:\.\d+)?)\s*$', str(s or ''))
    return float(m.group(1)) if m else None


def one(i):
    try:
        req = urllib.request.Request(CORE.format(i=i), headers={'User-Agent': 'vault-fantasy'})
        items = json.load(urllib.request.urlopen(req, timeout=30)).get('items') or []
    except Exception as e:
        return i, None, type(e).__name__
    it = next((x for x in items if (x.get('provider') or {}).get('name') == 'DraftKings'), items[0] if items else None)
    if not it: return i, None, 'no odds'
    op = ((it.get('homeTeamOdds') or {}).get('open') or {}).get('pointSpread') or {}
    return i, dict(so=num(op.get('american')), ouo=num(((it.get('open') or {}).get('total') or {}).get('american'))), None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--year', type=int, default=2026); a = ap.parse_args()
    lines = os.path.join(ROOT, 'data', 'cfbd', f'lines_{a.year}.json'); out = os.path.join(ROOT, 'data', 'cfbd', f'espn_opens_{a.year}.json')
    games = {}
    for r in json.load(open(lines)):
        if r.get('id') is not None: games[r['id']] = dict(id=r['id'], wk=r['wk'], home=r['home'], away=r['away'])
    old = {r['id']: r for r in json.load(open(out))} if os.path.exists(out) else {}
    with ThreadPoolExecutor(8) as ex: res = list(ex.map(one, list(games)))
    rows, err = [], 0
    for i, d, e in res:
        o = old.get(i)
        if d is None or d['so'] is None:
            err += d is None
            if o: rows.append(o)                 # keep the stored open
            continue
        rows.append(dict(games[i], so=d['so'], ouo=d['ouo']))
    rows += [o for i, o in old.items() if i not in games]
    json.dump(sorted(rows, key=lambda r: (r['wk'], r['id'])), open(out, 'w'), separators=(',', ':'))
    print(json.dumps(dict(games=len(games), with_open=len(rows), errors=err)))


if __name__ == '__main__':
    main()
