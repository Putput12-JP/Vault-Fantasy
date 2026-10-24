#!/usr/bin/env python3
"""
Game picks for the page: the live record (game_pick_record.py writes gpicks/<tip ET day>.json on the nba-data branch) merged with the rebuilt
earlier days (data/game_picks_backfill.json, backfill_game_picks.py) into data/game_picks.json. render_app.py bakes it into the app as GPICKS;
served from Pages the page also reads gpicks/ live from the branch, so this snapshot only has to be a good first paint.

A game that has a live row replaces its rebuilt row, so the day the recorder starts there is no double count. Rows keep their `src`
column ('live' or 'bf'), and the page keeps the two apart: the rebuilt days are never added into the live record's headline.

  python3 nba/scripts/build_game_picks.py        # also called by build_data_health.py before it renders the app
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game_pick_record as G

ROOT = os.path.join(HERE, '..', '..')
DATA = os.path.join(HERE, '..', 'data')
BRANCH = 'origin/nba-data'
OUT = os.path.join(DATA, 'game_picks.json')


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True).stdout


def live_days():
    """{day: {'games', 'rows'}} from the nba-data branch's gpicks/ folder (no checkout needed), {} when it has none yet."""
    out = {}
    for line in git('ls-tree', '--name-only', f'{BRANCH}:gpicks').split():
        if not line.endswith('.json') or line == 'open.json':
            continue
        try:
            d = json.loads(git('show', f'{BRANCH}:gpicks/{line}') or 'null')
        except json.JSONDecodeError:
            d = None
        if d and d.get('cols') == G.COLS:                      # a file written under another column layout is skipped, never misread
            out[d['day']] = {'games': d['games'], 'rows': d['rows']}
    return out


def merge(live, backfill):
    """Union by game; a live game replaces its rebuilt one. Days with no games left are dropped."""
    days = {}
    for src_days in (backfill or {}, live or {}):
        for day, d in src_days.items():
            x = days.setdefault(day, {'games': {}, 'rows': []})
            x['games'].update(d['games'])
            have = {r[0] for r in d['rows']}
            x['rows'] = [r for r in x['rows'] if r[0] not in have] + list(d['rows'])
    for x in days.values():
        x['rows'].sort(key=lambda r: (r[0], r[1]))
        x['games'] = {g: v for g, v in x['games'].items() if any(r[0] == g for r in x['rows'])}
    return dict(sorted(days.items()))


def snapshot():
    bf = os.path.join(DATA, 'game_picks_backfill.json')
    b = json.load(open(bf)) if os.path.exists(bf) else {}
    if b and b.get('cols') != G.COLS:
        print('game_picks_backfill.json uses another column layout: ignored. Rebuild it with backfill_game_picks.py')
        b = {}
    subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'nba-data'], check=False)
    days = merge(live_days(), b.get('days'))
    if not days:
        return
    out = {'generated': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
           'repo': 'Putput12-JP/Vault-Fantasy', 'branch': 'nba-data', 'cols': G.COLS, 'sd_margin': b.get('sd_margin'), 'days': days}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    n = sum(len(d['games']) for d in days.values())
    live = sum(1 for d in days.values() for r in d['rows'] if r[-1] == 'live' and r[1] == 'f')
    print(f'game picks: {n} games over {len(days)} days ({live} live, {n - live} rebuilt) -> data/game_picks.json')


if __name__ == '__main__':
    snapshot()
