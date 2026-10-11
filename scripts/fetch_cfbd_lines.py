#!/usr/bin/env python3
"""Probe: does CollegeFootballData carry OPENING lines (spreadOpen) for college games, and how complete is it?
Writes data/cfbd/lines_<year>.json, trimmed to one row per game per provider. Key from CFBD_API_KEY (never written).

  CFBD_API_KEY=... python3 scripts/fetch_cfbd_lines.py [--years 2022-2026]
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfbd')
BASE = 'https://api.collegefootballdata.com/lines'


def get(params, key):
    req = urllib.request.Request(f'{BASE}?{urllib.parse.urlencode(params)}',
                                 headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json', 'User-Agent': 'vault'})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--years', default='2022-2026'); a = ap.parse_args()
    key = (os.environ.get('CFBD_API_KEY') or '').strip()
    if not key: sys.exit('CFBD_API_KEY is not set')
    y0, y1 = (int(x) for x in a.years.split('-')); os.makedirs(OUT, exist_ok=True); summary = {}
    for y in range(y0, y1 + 1):
        rows, err = [], 0
        for wk in range(1, 16):
            try:
                for g in get({'year': y, 'week': wk, 'seasonType': 'regular'}, key):
                    for l in g.get('lines') or []:
                        rows.append(dict(id=g.get('id'), wk=wk, home=g.get('homeTeam'), away=g.get('awayTeam'), hs=g.get('homeScore'), as_=g.get('awayScore'),
                                         p=l.get('provider'), sp=l.get('spread'), so=l.get('spreadOpen'), ou=l.get('overUnder'), ouo=l.get('overUnderOpen')))
            except Exception as e:
                err += 1; print(y, wk, 'ERROR', type(e).__name__, getattr(e, 'code', ''))   # never the message: it can echo the key
            time.sleep(0.3)
        json.dump(rows, open(os.path.join(OUT, f'lines_{y}.json'), 'w'), separators=(',', ':'))
        have = [r for r in rows if r['so'] is not None]
        diff = [r for r in have if r['sp'] is not None and r['so'] != r['sp']]
        summary[y] = dict(rows=len(rows), games=len({r['id'] for r in rows}), with_open=len(have), open_differs_from_close=len(diff),
                          providers=sorted({r['p'] for r in rows if r['p']}), errors=err)
        print(y, json.dumps(summary[y]))
    json.dump(summary, open(os.path.join(OUT, 'lines_summary.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
