#!/usr/bin/env python3
"""
NBA preseason games from ESPN (hoopR's releases carry regular season and playoffs only).

One scoreboard call per day (seasontype=1 does not accept date ranges), then one summary call per completed
NBA-vs-NBA game. Keeps the box score and every play (substitutions, shots, rebounds, assists, turnovers) in a
compact JSON per game, so first-half minutes and on-floor usage can be rebuilt.

Season label = the year the season ENDS (2024 = 2023-24 preseason), like fetch_hoopr.py.

  python3 nba/scripts/fetch_preseason.py                 # 2024 2025 2026 2027
  python3 nba/scripts/fetch_preseason.py 2027            # one season

Writes nba/raw/preseason/<season>/<game_id>.json (raw/ is gitignored). Re-runs skip games already saved.
"""
import json, os, subprocess, sys, time, datetime as dt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'preseason')
API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
SEASONS = [2024, 2025, 2026, 2027]
NBA_TEAM_IDS = {str(i) for i in range(1, 31)}


def get(url, tries=4):
    # plain curl: ESPN's site API 403s a Mozilla UA (see nba README)
    for k in range(tries):
        r = subprocess.run(['curl', '-s', '--compressed', '-m', '40', url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            try:
                d = json.loads(r.stdout)
                if 'code' not in d or 'events' in d or 'plays' in d:
                    return d
            except ValueError:
                pass
        time.sleep(1.5 * (k + 1))
    return None


def trim_play(p):
    return {
        'id': p.get('id'), 'seq': p.get('sequenceNumber'), 'type': (p.get('type') or {}).get('text'),
        'text': p.get('text'), 'per': (p.get('period') or {}).get('number'),
        'clock': (p.get('clock') or {}).get('displayValue'), 'team': (p.get('team') or {}).get('id'),
        'ath': [a['athlete']['id'] for a in p.get('participants', []) if a.get('athlete')],
        'score': bool(p.get('scoringPlay')), 'shoot': bool(p.get('shootingPlay')), 'val': p.get('scoreValue'),
        'pts_att': p.get('pointsAttempted'), 'x': (p.get('coordinate') or {}).get('x'),
        'y': (p.get('coordinate') or {}).get('y'), 'aw': p.get('awayScore'), 'hm': p.get('homeScore'),
    }


def trim_box(d):
    out = []
    for t in d['boxscore']['players']:
        tid = t['team']['id']
        for grp in t['statistics']:
            keys = grp['keys']
            for a in grp['athletes']:
                if not (a.get('athlete') or {}).get('id'):
                    continue  # a few unnamed box rows carry no id
                st = dict(zip(keys, a['stats'])) if a.get('stats') else {}
                out.append({'team': tid, 'id': a['athlete']['id'], 'name': a['athlete']['displayName'],
                            'starter': bool(a.get('starter')), 'dnp': bool(a.get('didNotPlay')), 'stats': st})
    return out


def main():
    seasons = [int(x) for x in sys.argv[1:]] or SEASONS
    for s in seasons:
        folder = os.path.join(OUT, str(s))
        os.makedirs(folder, exist_ok=True)
        day, end = dt.date(s - 1, 9, 26), dt.date(s - 1, 10, 24)
        events = {}
        while day <= end:
            d = get(f'{API}/scoreboard?dates={day:%Y%m%d}&seasontype=1')
            for e in (d or {}).get('events', []):
                if (e.get('season') or {}).get('type') != 1:
                    continue
                comp = e['competitions'][0]
                tids = {c['team']['id'] for c in comp['competitors']}
                if tids <= NBA_TEAM_IDS and e['status']['type']['completed']:
                    events[e['id']] = {'date': e['date'], 'name': e['name'],
                                       'teams': {c['homeAway']: c['team']['abbreviation'] for c in comp['competitors']}}
            day += dt.timedelta(days=1)
            time.sleep(0.15)
        print(s, 'games found', len(events), flush=True)
        for gid, meta in sorted(events.items(), key=lambda kv: kv[1]['date']):
            path = os.path.join(folder, gid + '.json')
            if os.path.exists(path):
                continue
            d = get(f'{API}/summary?event={gid}')
            if not d or not d.get('plays'):
                print('  no plays', gid, meta['name'], flush=True)
                continue
            rec = dict(meta, id=gid, season=s, box=trim_box(d), plays=[trim_play(p) for p in d['plays']])
            with open(path, 'w') as f:
                json.dump(rec, f)
            time.sleep(0.25)
        print(s, 'saved', len(os.listdir(folder)), flush=True)


if __name__ == '__main__':
    main()
