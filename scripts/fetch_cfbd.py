#!/usr/bin/env python3
"""Pull the CollegeFootballData inputs the CFB model's v2 preseason prior may use, one JSON file per endpoint and season,
into data/cfbd/. The API key comes from the CFBD_API_KEY environment variable (a GitHub secret in CI); it is never written to a file.

  CFBD_API_KEY=... python3 scripts/fetch_cfbd.py [--years 2021-2026]
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfbd')
BASE = 'https://api.collegefootballdata.com'
ENDPOINTS = {                       # name -> (path, params builder)
    'teams_fbs': '/teams/fbs',
    'talent': '/talent',                       # 247 team talent composite
    'returning': '/player/returning',          # returning production, by team
    'portal': '/player/portal',                # transfer portal entries (per player, with rating/stars)
    'recruiting_teams': '/recruiting/teams',
    'sp': '/ratings/sp',                       # final SP+ (season level: for comparison, not for use as a pre-game input)
    'elo': '/ratings/elo',
    'fpi': '/ratings/fpi',
}


def get(path, year, key):
    url = f'{BASE}{path}?{urllib.parse.urlencode({"year": year})}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json', 'User-Agent': 'vault'})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--years', default='2021-2026'); a = ap.parse_args()
    key = (os.environ.get('CFBD_API_KEY') or '').strip()      # a pasted secret often carries a trailing newline
    if not key: sys.exit('CFBD_API_KEY is not set')
    y0, y1 = (int(x) for x in a.years.split('-')); os.makedirs(OUT, exist_ok=True); manifest = {}
    for name, path in ENDPOINTS.items():
        for y in range(y0, y1 + 1):
            f = f'{name}_{y}.json'
            try:
                d = get(path, y, key)
                json.dump(d, open(os.path.join(OUT, f), 'w'), separators=(',', ':'))
                manifest[f] = len(d) if hasattr(d, '__len__') else 1
            except Exception as e:
                manifest[f] = f'ERROR {type(e).__name__} {getattr(e, "code", "")}'      # never the message: it can echo the request headers, key included
            time.sleep(0.3)
    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1, sort_keys=True)
    print(json.dumps(manifest, indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
