#!/usr/bin/env python3
"""
Box score fallback: fill finished games the hoopR feed has not published yet, straight from ESPN.

The sportsdataverse (hoopR) release is rebuilt once a night and can land well after the morning refresh, which left last night's
games off the Player Props chart and every model input until the afternoon (Nov 6 games were still missing at 5:23 AM CT on Nov 7).
hoopR is itself built from ESPN's game summaries, so this reads the same source the same way and writes rows in hoopR's schema.

  python3 nba/scripts/fetch_espn_box.py [season] [--days=3]

For each date from `--days` ago through today (US Eastern, the date hoopR keys games on), it lists ESPN's scoreboard and, for every
finished regular season / playoff / play-in game with no rows in raw/hoopr/player_box_<season>.csv, fetches the summary and adds the
player and team rows to player_box_<season>.csv and team_box_<season>.csv (newest first, like hoopR).

Run it right after fetch_hoopr.py. fetch_hoopr re-downloads the current season's files on every run, so ESPN rows are replaced by
hoopR's own as soon as it publishes the game, and nothing here lingers or double counts. A failed ESPN call only skips that game.
"""
import csv, datetime as dt, json, os, sys, urllib.request
from zoneinfo import ZoneInfo

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'hoopr')
SITE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
ET = ZoneInfo('America/New_York')
SEASON_TYPES = {2, 3, 5}          # regular season, playoffs, play-in (preseason and All-Star stay out, as in hoopR's consumers)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'vault-nba'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def finished_games(day):
    """[(event id, season year, season type)] for finished games on an ET date."""
    d = get(f'{SITE}/scoreboard?dates={day:%Y%m%d}&limit=50')
    out = []
    for e in d.get('events', []):
        if e.get('status', {}).get('type', {}).get('completed') and e.get('season', {}).get('type') in SEASON_TYPES:
            out.append((e['id'], int(e['season']['year']), int(e['season']['type'])))
    return out


def _when(iso):
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ET)
    return t.strftime('%Y-%m-%d'), t.strftime('%Y-%m-%dT%H:%M:%S.000000%z')


def _b(x):
    return 'true' if x else 'false'


def _team(t, prefix=''):
    return {f'{prefix}team_id': t.get('id', ''), f'{prefix}team_uid': t.get('uid', ''), f'{prefix}team_slug': t.get('slug', ''),
            f'{prefix}team_location': t.get('location', ''), f'{prefix}team_name': t.get('name', ''),
            f'{prefix}team_abbreviation': t.get('abbreviation', ''), f'{prefix}team_display_name': t.get('displayName', ''),
            f'{prefix}team_short_display_name': t.get('shortDisplayName', ''), f'{prefix}team_color': t.get('color', ''),
            f'{prefix}team_alternate_color': t.get('alternateColor', ''), f'{prefix}team_logo': t.get('logo', '')}


PLAYER_KEYS = {'minutes': ['minutes'], 'points': ['points'], 'rebounds': ['rebounds'], 'assists': ['assists'],
               'turnovers': ['turnovers'], 'steals': ['steals'], 'blocks': ['blocks'], 'offensiveRebounds': ['offensive_rebounds'],
               'defensiveRebounds': ['defensive_rebounds'], 'fouls': ['fouls'], 'plusMinus': ['plus_minus'],
               'fieldGoalsMade-fieldGoalsAttempted': ['field_goals_made', 'field_goals_attempted'],
               'threePointFieldGoalsMade-threePointFieldGoalsAttempted': ['three_point_field_goals_made', 'three_point_field_goals_attempted'],
               'freeThrowsMade-freeThrowsAttempted': ['free_throws_made', 'free_throws_attempted']}

TEAM_KEYS = {'assists': 'assists', 'blocks': 'blocks', 'defensiveRebounds': 'defensive_rebounds', 'fastBreakPoints': 'fast_break_points',
             'fieldGoalPct': 'field_goal_pct', 'flagrantFouls': 'flagrant_fouls', 'fouls': 'fouls', 'freeThrowPct': 'free_throw_pct',
             'largestLead': 'largest_lead', 'leadChanges': 'lead_changes', 'leadPercentage': 'lead_percentage',
             'offensiveRebounds': 'offensive_rebounds', 'pointsInPaint': 'points_in_paint', 'steals': 'steals',
             'teamTurnovers': 'team_turnovers', 'technicalFouls': 'technical_fouls', 'threePointFieldGoalPct': 'three_point_field_goal_pct',
             'totalRebounds': 'total_rebounds', 'totalTechnicalFouls': 'total_technical_fouls', 'totalTurnovers': 'total_turnovers',
             'turnoverPoints': 'turnover_points', 'turnovers': 'turnovers'}
TEAM_PAIRS = {'fieldGoalsMade-fieldGoalsAttempted': ('field_goals_made', 'field_goals_attempted'),
              'threePointFieldGoalsMade-threePointFieldGoalsAttempted': ('three_point_field_goals_made', 'three_point_field_goals_attempted'),
              'freeThrowsMade-freeThrowsAttempted': ('free_throws_made', 'free_throws_attempted')}


def _pct(v):
    try:
        return f'{float(v):.1f}'
    except ValueError:
        return v


def summary_rows(gid, season, stype):
    """(player rows, team rows) for one finished game, keyed like hoopR's CSVs."""
    d = get(f'{SITE}/summary?event={gid}')
    comp = d['header']['competitions'][0]
    gdate, gtime = _when(comp['date'])
    side = {}                                    # team id -> {home_away, score, winner, team}
    for c in comp['competitors']:
        side[c['team']['id']] = {'home_away': c['homeAway'], 'score': c.get('score', ''), 'winner': bool(c.get('winner'))}
    teams = {t['team']['id']: t['team'] for t in d['boxscore']['players']}
    for t in d['boxscore'].get('teams', []):
        teams.setdefault(t['team']['id'], t['team'])
    other = {a: b for a in side for b in side if a != b}
    base = {'game_id': gid, 'season': str(season), 'season_type': str(stype), 'game_date': gdate, 'game_date_time': gtime}

    players = []
    for blk in d['boxscore']['players']:
        tid = blk['team']['id']
        oid = other[tid]
        tm, op = teams[tid], teams[oid]
        common = dict(base, **_team(tm), team_winner=_b(side[tid]['winner']), team_score=side[tid]['score'], home_away=side[tid]['home_away'],
                      opponent_team_id=op.get('id', ''), opponent_team_name=op.get('name', ''), opponent_team_location=op.get('location', ''),
                      opponent_team_display_name=op.get('displayName', ''), opponent_team_abbreviation=op.get('abbreviation', ''),
                      opponent_team_logo=op.get('logo', ''), opponent_team_color=op.get('color', ''),
                      opponent_team_alternate_color=op.get('alternateColor', ''), opponent_team_score=side[oid]['score'])
        del common['team_slug'], common['team_uid']          # set below in hoopR's column order
        for st in blk.get('statistics', []):
            keys = st.get('keys', [])
            for a in st.get('athletes', []):
                ath = a['athlete']
                dnp = bool(a.get('didNotPlay')) or not a.get('stats')
                r = dict(common, athlete_id=ath['id'], athlete_display_name=ath.get('displayName', ''),
                         athlete_short_name=ath.get('shortName', ''), athlete_jersey=ath.get('jersey', ''),
                         athlete_headshot_href=(ath.get('headshot') or {}).get('href', ''),
                         athlete_position_name=(ath.get('position') or {}).get('name', ''),
                         athlete_position_abbreviation=(ath.get('position') or {}).get('abbreviation', ''),
                         team_uid=tm.get('uid', ''), team_slug=tm.get('slug', ''),
                         starter=_b(a.get('starter')), ejected=_b(a.get('ejected')), did_not_play=_b(dnp),
                         reason=a.get('reason', ''), active=_b(a.get('active')))
                for k, cols in PLAYER_KEYS.items():
                    for c in cols:
                        r[c] = ''
                if not dnp:
                    for k, v in zip(keys, a['stats']):
                        cols = PLAYER_KEYS.get(k)
                        if not cols:
                            continue
                        parts = v.split('-', 1) if len(cols) == 2 else [v]
                        for c, p in zip(cols, parts):
                            r[c] = p
                    if r['minutes'] not in ('', '--'):
                        r['minutes'] = f"{float(r['minutes']):.1f}"
                players.append(r)

    team_rows = []
    for t in d['boxscore'].get('teams', []):
        tid = t['team']['id']
        oid = other[tid]
        r = dict(base, **_team(teams[tid]), team_home_away=side[tid]['home_away'], team_score=side[tid]['score'],
                 team_winner=_b(side[tid]['winner']), **_team(teams[oid], 'opponent_'), opponent_team_score=side[oid]['score'])
        for s in t.get('statistics', []):
            v = s.get('displayValue', '')
            if s['name'] in TEAM_PAIRS:
                m, a = (v.split('-', 1) + [''])[:2]
                r[TEAM_PAIRS[s['name']][0]], r[TEAM_PAIRS[s['name']][1]] = m, a
            elif s['name'] in TEAM_KEYS:
                r[TEAM_KEYS[s['name']]] = _pct(v) if s['name'].endswith('Pct') else v
        team_rows.append(r)
    return players, team_rows


def prepend(path, rows):
    """Write rows at the top of a hoopR CSV, in its own column order (missing columns blank)."""
    with open(path, newline='') as f:
        rd = csv.DictReader(f)
        cols, old = rd.fieldnames, list(rd)
    tmp = path + '.part'
    with open(tmp, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore', restval='')
        w.writeheader()
        w.writerows(rows)
        w.writerows(old)
    os.replace(tmp, path)


def main(argv):
    args = dict(a.lstrip('-').split('=', 1) for a in argv if '=' in a)
    pos = [a for a in argv if a.isdigit()]
    today = dt.datetime.now(ET).date()
    season = int(pos[0]) if pos else (today.year + 1 if today.month >= 8 else today.year)
    days = int(args.get('days', 3))
    pb, tb = (os.path.join(RAW, f'{k}_{season}.csv') for k in ('player_box', 'team_box'))
    if not os.path.exists(pb):
        print(f'{season}: no hoopR player box yet; nothing to fill')
        return
    have = {r['game_id'] for r in csv.DictReader(open(pb)) if r['game_id']}

    add_p, add_t, filled, failed = [], [], [], []
    for back in range(days, -1, -1):
        day = today - dt.timedelta(days=back)
        try:
            games = finished_games(day)
        except Exception as e:
            print(f'{day}: scoreboard FAILED  {e}')
            continue
        for gid, yr, stype in games:
            if gid in have or yr != season:
                continue
            try:
                p, t = summary_rows(gid, yr, stype)
            except Exception as e:
                failed.append(f'{gid} ({e})')
                continue
            if not any(r['did_not_play'] == 'false' for r in p):
                failed.append(f'{gid} (summary has no box score yet)')
                continue
            add_p += p
            add_t += t
            filled.append(f"{p[0]['game_date']} {gid}")
    if add_p:
        add_p.sort(key=lambda r: r['game_date_time'], reverse=True)
        add_t.sort(key=lambda r: r['game_date_time'], reverse=True)
        prepend(pb, add_p)
        if os.path.exists(tb):
            prepend(tb, add_t)
    print(f'ESPN fallback {season}: {len(filled)} game(s) filled ({len(add_p)} player rows)' + (': ' + ', '.join(filled) if filled else '')
          + ('' if filled else ' - hoopR already has every finished game'))
    if failed:
        print(f'::warning::ESPN fallback could not fill {len(failed)} game(s): ' + ', '.join(failed))


if __name__ == '__main__':
    main(sys.argv[1:])
