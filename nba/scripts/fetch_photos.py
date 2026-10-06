#!/usr/bin/env python3
"""
Player headshots and team logos for the app, embedded in the page as small data URIs (the published artifact blocks
external images, so anything it shows has to ride inside the file).

  players  each team's top ROSTER_N by minutes (data/player_projections.json min0) at 56x41, from ESPN's image service
           (a.espncdn.com, keyed by the same ESPN athlete id the whole app uses). Everyone else shows initials; on the
           website (where external images load) the page falls back to ESPN's URL for them.
  teams    all 30 logos at 48x48.

Only missing images are downloaded: an existing data/photos.json is kept, entries for players who left the top set are
dropped, so the daily job costs a handful of requests.

  python3 nba/scripts/fetch_photos.py
Writes nba/data/photos.json {heads: {athlete id: data URI}, logos: {team: data URI}}.
"""
import base64, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'photos.json')
ROSTER_N = 12
HEAD = 'https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/{}.png&w=56&h=41'
LOGO = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/{}.png&w=48&h=48'


def get(url):
    p = subprocess.run(['curl', '-s', '--max-time', '30', '-w', '\n%{http_code}', url], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    return body if code == b'200' and body[:4] == b'\x89PNG' else None


def uri(png):
    return 'data:image/png;base64,' + base64.b64encode(png).decode()


def main():
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    want = {}
    for t, T in proj['teams'].items():
        for p in sorted(T['players'], key=lambda p: -(p.get('min0') or 0))[:ROSTER_N]:
            want[str(p['id'])] = t
    old = json.load(open(OUT)) if os.path.exists(OUT) else {'heads': {}, 'logos': {}}
    heads = {k: v for k, v in old.get('heads', {}).items() if k in want}
    logos = dict(old.get('logos', {}))
    todo = [k for k in want if k not in heads]
    with ThreadPoolExecutor(8) as ex:
        for k, png in zip(todo, ex.map(lambda k: get(HEAD.format(k)), todo)):
            if png:
                heads[k] = uri(png)
    miss = [t for t in proj['teams'] if t not in logos]
    for t in miss:
        png = get(LOGO.format(t.lower()))
        if png:
            logos[t] = uri(png)
    json.dump({'heads': heads, 'logos': logos}, open(OUT, 'w'), separators=(',', ':'), sort_keys=True)
    print(f"photos: {len(heads)} headshots ({len(todo)} fetched, {len([k for k in todo if k not in heads])} without a photo), "
          f"{len(logos)} logos ({len(miss)} fetched) -> data/photos.json {os.path.getsize(OUT) // 1024} KB")


if __name__ == '__main__':
    main()
