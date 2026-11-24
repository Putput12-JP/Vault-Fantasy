#!/usr/bin/env python3
"""
Game picks for the page: the live record (game_pick_record.py writes gpicks/<tip ET day>.json on the nba-data branch) merged with the rebuilt
earlier days (data/game_picks_backfill.json, backfill_game_picks.py) into data/game_picks.json. render_app.py bakes it into the app as GPICKS;
served from Pages the page also reads gpicks/ live from the branch, so this snapshot only has to be a good first paint.

From G.LOCK_V2_FROM (the lineup lock, docs/game-pick-lock.md) a game that has a live row replaces its rebuilt row, so there is no double count. Before it the
rows were rebuilt at the lineup lock (rebuild_game_picks_lineup_lock.py) and replace the live rows written at the old 4-hour lock, which are kept whole in
data/game_picks_4h_lock.json. Rows keep their `src` column ('live' or 'bf'), and the page keeps the two apart.

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
    """Union by game. From G.LOCK_V2_FROM a live game replaces its rebuilt one (the recorder writes the lineup lock). Before it the live rows were written at the old
    4-hour lock, so the row rebuilt at the lineup lock wins and the live one is only a fallback for a game the rebuild does not have (a day not yet on the tape or
    not yet final): the rule is then different for that game, and it is counted in the printout. Days with no games left are dropped."""
    days = {}
    for day in sorted(set(live or {}) | set(backfill or {})):
        base, over = ((backfill or {}).get(day), (live or {}).get(day)) if day >= G.LOCK_V2_FROM else ((live or {}).get(day), (backfill or {}).get(day))
        x = days.setdefault(day, {'games': {}, 'rows': []})
        for d in (base, over):
            if not d:
                continue
            x['games'].update(d['games'])
            have = {r[0] for r in d['rows']}
            x['rows'] = [r for r in x['rows'] if r[0] not in have] + list(d['rows'])
    for x in days.values():
        x['rows'].sort(key=lambda r: (r[0], r[1]))
        x['games'] = {g: v for g, v in x['games'].items() if any(r[0] == g for r in x['rows'])}
    return {d: x for d, x in sorted(days.items()) if x['games']}


def snapshot():
    bf = os.path.join(DATA, 'game_picks_backfill.json')
    b = json.load(open(bf)) if os.path.exists(bf) else {}
    if b and b.get('cols') != G.COLS:
        print('game_picks_backfill.json uses another column layout: ignored. Rebuild it with backfill_game_picks.py')
        b = {}
    subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'nba-data'], check=False)
    live = live_days()
    days = merge(live, b.get('days'))
    if not days:
        return
    stale = [g for day, d in live.items() if day < G.LOCK_V2_FROM for g, v in d['games'].items()
             if not any(r[0] == g and r[-1] == 'bf' for r in days.get(day, {}).get('rows', []))]
    if stale:
        print(f'  {len(stale)} games before {G.LOCK_V2_FROM} have no rebuilt row yet and keep their live row, written at the old 4-hour lock. '
              f'Rerun rebuild_game_picks_lineup_lock.py on a fresher tape.')
    out = {'generated': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
           'repo': 'Putput12-JP/Vault-Fantasy', 'branch': 'nba-data', 'cols': G.COLS, 'sd_margin': b.get('sd_margin'), 'days': days}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    n = sum(len(d['games']) for d in days.values())
    nlive = sum(1 for d in days.values() for r in d['rows'] if r[-1] == 'live' and r[1] == 'f')
    print(f'game picks: {n} games over {len(days)} days ({nlive} live, {n - nlive} rebuilt) -> data/game_picks.json')


if __name__ == '__main__':
    snapshot()
