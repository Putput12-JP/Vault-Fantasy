#!/usr/bin/env python3
"""
NBA.com daily starting lineups: who starts, Expected vs Confirmed, and when it was confirmed.

Source (free, no auth, no headers needed): the JSON behind nba.com/players/todays-lineups
  https://stats.nba.com/js/data/leaders/00_daily_lineups_<YYYYMMDD>.json
One file per ET game day. Each team lists its players; the five with a `position` (PG/SG/SF/PF/C) are the
starters, `lineupStatus` is Expected until the team confirms, then Confirmed, and `timestamp` is the last update.
Past days keep their final state, so a backfill gives the confirmed five and the time of the last change.

  python3 nba/scripts/fetch_lineups.py                   # today (ET) -> nba/data/lineups_today.json
  python3 nba/scripts/fetch_lineups.py --backfill        # every game day of the last two seasons -> raw + table
Writes
  nba/raw/lineups/<YYYYMMDD>.json      one raw file per game day (backfill)
  nba/raw/tables/lineups.csv           one row per listed player per game (backfill)
  nba/data/lineups_today.json          today's board, compact (live mode)
"""
import csv, datetime as dt, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
import nba_common as C

URL = 'https://stats.nba.com/js/data/leaders/00_daily_lineups_{}.json'
OUT_RAW = os.path.join(C.RAW, 'lineups')
OUT_CSV = os.path.join(C.RAW, 'tables', 'lineups.csv')
OUT_TODAY = os.path.join(HERE, '..', 'data', 'lineups_today.json')
SLOTS = ('PG', 'SG', 'SF', 'PF', 'C')
# NBA.com tricode -> hoopR/ESPN abbreviation
TEAM = {'GSW': 'GS', 'NYK': 'NY', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH'}


def get(day):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '30', URL.format(day)], capture_output=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def team_abbr(tri):
    return TEAM.get(tri, tri)


def compact(d):
    """Raw day file -> {game_id: {team: {'status', 'ts', 'starters': [[name, slot, person_id]], 'inactive': [names]}}}."""
    out = {}
    for g in (d or {}).get('games', []):
        gm = out.setdefault(g['gameId'], {'status': g.get('gameStatusText')})
        for side in ('homeTeam', 'awayTeam'):
            t = g.get(side) or {}
            pl = t.get('players') or []
            st = [p for p in pl if p.get('position') in SLOTS]
            st.sort(key=lambda p: SLOTS.index(p['position']))
            stat = {p.get('lineupStatus') for p in st}
            gm[team_abbr(t.get('teamAbbreviation'))] = {
                'side': 'home' if side == 'homeTeam' else 'away',
                'status': 'Confirmed' if stat == {'Confirmed'} else ('Expected' if st else None),
                'ts': max((p.get('timestamp') or '' for p in st), default='') or None,
                'starters': [[p['playerName'], p['position'], p['personId']] for p in st],
                'inactive': [p['playerName'] for p in pl if p.get('rosterStatus') == 'Inactive'],
            }
    return out


def game_days(seasons):
    return sorted({g['tip_et'].strftime('%Y%m%d') for g in C.games(seasons)})


def backfill(seasons):
    os.makedirs(OUT_RAW, exist_ok=True)
    days = [d for d in game_days(seasons) if not os.path.exists(os.path.join(OUT_RAW, d + '.json'))]
    print(f'{len(days)} days to fetch')

    def one(day):
        d = get(day)
        if d and d.get('games'):
            json.dump(d, open(os.path.join(OUT_RAW, day + '.json'), 'w'), separators=(',', ':'))
            return day, True
        return day, False
    with ThreadPoolExecutor(8) as ex:
        miss = [day for day, ok in ex.map(one, days) if not ok]
    if miss:
        print(f'no file for {len(miss)} days, e.g. {miss[:5]}')
    rows = []
    for f in sorted(os.listdir(OUT_RAW)):
        d = json.load(open(os.path.join(OUT_RAW, f)))
        for g in d.get('games', []):
            for side in ('homeTeam', 'awayTeam'):
                t = g.get(side) or {}
                for p in t.get('players') or []:
                    rows.append({'day': f[:8], 'nba_game_id': g['gameId'], 'team': team_abbr(t.get('teamAbbreviation')),
                                 'side': side[:4], 'person_id': p.get('personId'), 'player': p.get('playerName'),
                                 'name_key': C.name_key(p.get('playerName')), 'slot': p.get('position') or '',
                                 'status': p.get('lineupStatus') or '', 'roster': p.get('rosterStatus') or '',
                                 'ts': p.get('timestamp') or ''})
    with open(OUT_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows):,} rows -> {OUT_CSV}')


def today():
    now = C.et(dt.datetime.now(dt.timezone.utc))
    day = now.strftime('%Y%m%d')
    d = get(day)
    out = {'t': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'day': day, 'games': compact(d)}
    json.dump(out, open(OUT_TODAY, 'w'), separators=(',', ':'))
    n = sum(1 for g in out['games'].values() for k, v in g.items() if isinstance(v, dict) and v['status'] == 'Confirmed')
    print(f"{day}: {len(out['games'])} games, {n} lineups confirmed -> {OUT_TODAY}")


if __name__ == '__main__':
    if '--backfill' in sys.argv:
        backfill([2025, 2026])
    else:
        today()
