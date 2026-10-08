#!/usr/bin/env python3
"""
One-screen health check of the live props board: is every venue posting, which stats arrived, are lineups and injuries in,
and which labels did the feeds send that we did not map (so a stat named differently shows up here instead of vanishing).

  python3 nba/scripts/check_board.py            # reads the live board the page reads
  python3 nba/scripts/check_board.py board.json # or a saved one
"""
import json, subprocess, sys, time
from collections import Counter

URL = 'https://raw.githubusercontent.com/Putput12-JP/Vault-Fantasy/nba-live/board.json'


def load(argv):
    if argv:
        return json.load(open(argv[0]))
    repo = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
    slug = repo.split('github.com')[-1].strip(':/').removesuffix('.git')
    out = subprocess.run(['curl', '-s', '--max-time', '30', f'https://raw.githubusercontent.com/{slug}/nba-live/board.json'], capture_output=True, text=True).stdout
    return json.loads(out)


def main(argv):
    b = load(argv)
    now = time.time()
    games = b.get('games') or []
    props = b.get('props') or []
    print(f"board age      {round((now - b['t']) / 60)} min   games {len(games)}   props {len(props)}   players {len(b.get('players') or {})}")
    stats = Counter(e['s'] for e in props)
    print('stats          ' + (', '.join(f'{s} {n}' for s, n in stats.most_common()) or 'none'))
    venues = Counter()
    for e in props:
        venues['kalshi'] += bool(e.get('kal'))
        venues['books'] += bool(e.get('books'))
        venues['pick'] += bool(e.get('pk'))
        for r in e.get('books') or []:
            venues['book:' + r[0]] += 1
        for r in e.get('pk') or []:
            venues['pick:' + r[0]] += 1
    print('venues         ' + (', '.join(f'{k} {v}' for k, v in sorted(venues.items())) or 'none'))
    pl = b.get('players') or {}
    lu = Counter((v[3] or '-') for v in pl.values())
    print(f"lineups        {dict(lu)}   starters known for {len(b.get('starters') or {})} teams")
    print(f"injuries       {sum(1 for v in pl.values() if v[2])} players flagged, {len(b.get('outs') or [])} out/doubtful/inactive")
    print(f"unmapped       {b.get('unmapped')}")
    print(f"labels skipped {b.get('skipped') or 'none recorded (or an older recorder build)'}")
    miss = [s for s in ('pts', 'reb', 'ast', '3pm', 'pra') if s not in stats]
    new = [s for s in ('stl', 'blk', 'tov', 'sb', 'fgm', 'fga', 'ftm', 'fta', 'tpa', 'oreb', 'dreb', 'pf') if s in stats]
    print('core stats     ' + ('all present' if not miss else 'MISSING ' + ', '.join(miss)))
    print('extra markets  ' + (', '.join(new) if new else 'none posted yet'))


if __name__ == '__main__':
    main(sys.argv[1:])
