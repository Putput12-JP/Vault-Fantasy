#!/usr/bin/env python3
"""Fill in final scores for calls that were graded but never got a score stored.

data/exchange_edge_results.json is only written while the live feed still lists a game as final (scripts/sharp_tape.py), so games that
finished between runs were missed and their calls could not be settled. This reads the calls already in data/exchange_edge_record.json,
asks ESPN's public scoreboard for the days those games were played, and stores any completed game's real final score under the call's
game key. A game ESPN does not list as completed is left alone: nothing is guessed. Run it before scripts/exchange_edge_record.py.

--plays FILE [FILE ...] also scores the open and voided game plays (kind book or exch) in the Sharp Money V2 ledgers (v2_plays.json, v2_watch.json,
v2_passed.json): scripts/track-v2-plays.mjs settles them from this same file, and a game the live feed missed would otherwise void 72h
after tip (the Spurs at Suns moneyline of Nov 9 2026 sat open for that reason).
"""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REC = os.path.join(ROOT, 'data', 'exchange_edge_record.json')
RES = os.path.join(ROOT, 'data', 'exchange_edge_results.json')
SCORE = {'nfl': 'football/nfl/scoreboard', 'cfb': 'football/college-football/scoreboard?groups=80&limit=400', 'nba': 'basketball/nba/scoreboard'}
ALIAS = {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX', 'LVR': 'LV', 'OAK': 'LV'}
SPORT_ALIAS = {'cfb': {'CHA': 'CLT'},
               'nba': {'SA': 'SAS', 'GS': 'GSW', 'NY': 'NYK', 'NO': 'NOP', 'UTAH': 'UTA'}}   # ESPN's short NBA codes -> the feed's      # the feed's college abbreviation where it differs from ESPN's (CHA is the Hornets in the NBA, so this is per sport)
n = lambda x, sp=None: SPORT_ALIAS.get(sp, {}).get(x) or ALIAS.get(x, x)


def board(sport, day):
    path = SCORE[sport]
    url = 'https://site.api.espn.com/apis/site/v2/sports/' + path + ('&' if '?' in path else '?') + 'dates=' + day
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault-fantasy'}), timeout=30) as r:
            return json.load(r).get('events', [])
    except Exception as e:
        print('espn', sport, day, 'failed:', e, file=sys.stderr)
        return []


def open_plays(files, res, now):
    """{gk: (sport, 'AWAY@HOME', start)} for V2 game plays with no stored final, 3h+ after tip: open ones, and voids that went void for
    that missing final (scripts/reopen_v2_game_voids.py reopens them once it is stored)."""
    need = {}
    for f in files:
        try:
            plays = json.load(open(f)).get('plays') or {}
        except (OSError, ValueError, AttributeError):
            continue
        for p in (plays.values() if isinstance(plays, dict) else plays):
            g = p.get('game') or {}
            if (p.get('status') in ('open', 'void') and not p.get('regraded') and p.get('kind') in ('book', 'exch') and g.get('gk') and g['gk'] not in res
                    and g.get('away') and g.get('home') and p.get('sport') in SCORE and p.get('start') and p['start'] < now - 3 * 3600):
                need[g['gk']] = (p['sport'], g['away'] + '@' + g['home'], p['start'])
    return need


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    plays = argv[argv.index('--plays') + 1:] if '--plays' in argv else []
    try:
        rec = json.load(open(REC))
    except (OSError, ValueError):
        rec = {}
    res = json.load(open(RES)) if os.path.exists(RES) else {}
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    need = open_plays(plays, res, now)
    for sport, b in (rec.get('by_sport') or {}).items():
        for c in b.get('calls', []):
            if c.get('graded') and c.get('gk') and c['gk'] not in res and c['start'] < now and '@' in str(c.get('game')):
                need[c['gk']] = (sport, c['game'], c['start'])
    if not need:
        return
    days = {}
    for gk, (sport, game, start) in need.items():
        d = dt.datetime.fromtimestamp(start, dt.timezone.utc).date()
        for k in (-1, 0, 1):
            days.setdefault((sport, (d + dt.timedelta(days=k)).strftime('%Y%m%d')), None)
    for key in days:
        days[key] = board(*key)
    added = 0
    for gk, (sport, game, start) in need.items():
        away, home = game.split('@')
        got = added
        for (sp, _), evs in days.items():
            if sp != sport:
                continue
            for e in evs:
                c = e['competitions'][0]
                if not c['status']['type'].get('completed'):
                    continue
                t = {x['homeAway']: x for x in c['competitors']}
                if 'home' not in t or 'away' not in t:
                    continue
                st = dt.datetime.strptime(e['date'], '%Y-%m-%dT%H:%MZ').replace(tzinfo=dt.timezone.utc).timestamp()
                if n(t['away']['team']['abbreviation'], sport) == n(away, sport) and n(t['home']['team']['abbreviation'], sport) == n(home, sport) and abs(st - start) < 6 * 3600:
                    try:
                        res[gk] = {'home': int(t['home']['score']), 'away': int(t['away']['score']), 'sport': sport, 'start': start, 'ah': away, 'hh': home, 'src': 'espn'}
                    except (TypeError, ValueError):
                        continue
                    added += 1
                    break
            if gk in res:
                break
        if added == got and gk not in res and start < now - 6 * 3600:
            print('edge results backfill: no ESPN match for', gk, game, file=sys.stderr)
    json.dump(res, open(RES, 'w'), separators=(',', ':'), sort_keys=True)
    print('edge results backfill: %d of %d missing games scored from ESPN' % (added, len(need)))


if __name__ == '__main__':
    main()
