#!/usr/bin/env python3
"""
Current NBA depth charts, reconciled against live rosters, offseason moves and
the draft, for the minutes model's season-start rotation.

Sources (ESPN, free, no auth):
  site  /teams/{id}/roster                                  who is on the team NOW
  core  /seasons/{yr}/teams/{id}/depthcharts                ESPN's PG/SG/SF/PF/C order
  site  /transactions                                       signings, trades, waivers
  hoopR espn_nba_draft draft_<yr>.csv                       draft picks (prospect ids -> joined by name)
  nba/raw/hoopr/player_box_<last>.csv                       last season's team + minutes

Why reconcile: ESPN's depth charts lag the roster. On 2026-09-29 the Knicks
chart was missing 5 rostered players and still listed one who had left. So:
  - roster is the truth for WHO is on a team
  - depth chart gives the ORDER for players it knows about
  - roster players ESPN has not slotted are kept, flagged 'unslotted', and
    ordered after slotted players by last season's minutes
  - depth entries no longer on the roster are dropped and reported as stale

  python3 nba/scripts/fetch_depth_charts.py
Writes
  nba/data/depth_charts.json             current state (small, publishable)
  nba/raw/depth/<date>.json              dated snapshot, to diff day over day
  nba/raw/depth/transactions_<yr>.json   the offseason transaction log
"""
import csv, datetime as dt, json, os, re, subprocess, sys, unicodedata, urllib.request
from collections import defaultdict

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
DATA = os.path.join(HERE, '..', 'data')
SITE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
CORE = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba'
POS = ['pg', 'sg', 'sf', 'pf', 'c']


def get(url):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '40', url], capture_output=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def name_key(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


def ath_id(ref):
    m = re.search(r'/athletes/(\d+)', ref or '')
    return m.group(1) if m else None


def last_season_usage(season):
    """athlete_id -> {team, gp, mpg, starts} from the last regular season (a traded player's LAST team)."""
    path = os.path.join(RAW, 'hoopr', f'player_box_{season}.csv')
    if not os.path.exists(path):
        return {}
    agg = defaultdict(lambda: {'gp': 0, 'min': 0.0, 'starts': 0, 'team': None, 'last': ''})
    for r in csv.DictReader(open(path)):
        if r['season_type'] != '2' or not r['athlete_id'] or r['did_not_play'] == 'true':
            continue
        m = float(r['minutes'] or 0)
        if m <= 0:
            continue
        a = agg[r['athlete_id']]
        a['gp'] += 1
        a['min'] += m
        a['starts'] += r['starter'] == 'true'
        if r['game_date'] >= a['last']:
            a['last'], a['team'] = r['game_date'], r['team_abbreviation']
    return {k: {'team': v['team'], 'gp': v['gp'], 'mpg': round(v['min'] / v['gp'], 1), 'starts': v['starts']}
            for k, v in agg.items()}


def draft_picks(year):
    url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_draft/draft_{year}.csv'
    try:
        body = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault-nba'}), timeout=60).read().decode()
    except Exception:
        return {}
    return {name_key(r['athlete_display_name']): {'year': year, 'round': int(r['round']), 'pick': int(r['overall_pick'])}
            for r in csv.DictReader(body.splitlines())}


def transactions(season_year):
    out, page = [], 1
    while True:
        d = get(f'{SITE}/transactions?limit=100&page={page}') or {}
        out += d.get('transactions', [])
        if page >= (d.get('pageCount') or 1):
            break
        page += 1
    return [{'date': t['date'][:10], 'team': t['team']['abbreviation'], 'text': t['description']} for t in out]


def main():
    teams = [t['team'] for t in get(f'{SITE}/teams')['sports'][0]['leagues'][0]['teams']]
    r0 = get(f"{SITE}/teams/{teams[0]['id']}/roster")
    yr = r0['season']['year']                      # 2027 = the 2026-27 season
    usage = last_season_usage(yr - 1)
    picks = draft_picks(yr - 1)                    # the June draft before this season
    moves = transactions(yr)

    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'season': yr,
           'season_label': r0['season']['displayName'], 'phase': r0['season']['name'], 'teams': {}}
    stale_total = unslotted_total = 0
    for t in teams:
        ab = t['abbreviation']
        roster = (get(f"{SITE}/teams/{t['id']}/roster") or {}).get('athletes', [])
        on_roster = {a['id']: a for a in roster}
        dc = get(f"{CORE}/seasons/{yr}/teams/{t['id']}/depthcharts") or {}
        slots = {}   # athlete id -> [(pos, rank)]
        stale = []
        for chart in dc.get('items', []):
            for pos, v in (chart.get('positions') or {}).items():
                for rank, e in enumerate(v.get('athletes', []), 1):
                    aid = ath_id((e.get('athlete') or {}).get('$ref'))
                    if aid in on_roster:
                        slots.setdefault(aid, []).append((pos, rank))
                    elif aid and aid not in stale:
                        stale.append(aid)
        players = []
        for aid, a in on_roster.items():
            u = usage.get(aid, {})
            s = sorted(slots.get(aid, []), key=lambda x: x[1])
            dp = picks.get(name_key(a['displayName']))
            players.append({
                'id': int(aid), 'name': a['displayName'], 'pos': (a.get('position') or {}).get('abbreviation'),
                'depth': [{'pos': p, 'rank': r} for p, r in s],
                'best_rank': s[0][1] if s else None,
                'slotted': bool(s),
                'exp': (a.get('experience') or {}).get('years'),
                'rookie': (a.get('experience') or {}).get('years') == 0,
                'draft': dp,
                'last_team': u.get('team'), 'last_gp': u.get('gp', 0), 'last_mpg': u.get('mpg', 0.0),
                'moved': bool(u.get('team')) and u.get('team') != ab,
                'injury': [i.get('status') for i in a.get('injuries', [])] or None,
            })
        # Slotted players by their best depth rank, then everyone else by last season's minutes.
        players.sort(key=lambda p: (not p['slotted'], p['best_rank'] or 99, -p['last_mpg']))
        starters = {}
        for pos in POS:
            first = next((p for p in players if any(d['pos'] == pos and d['rank'] == 1 for d in p['depth'])), None)
            starters[pos] = first['name'] if first else None
        unslotted = [p['name'] for p in players if not p['slotted']]
        stale_total += len(stale)
        unslotted_total += len(unslotted)
        out['teams'][ab] = {'name': t['displayName'], 'starters': starters, 'players': players,
                            'unslotted': unslotted, 'stale_depth_ids': stale,
                            'moves': [m for m in moves if m['team'] == ab]}

    os.makedirs(DATA, exist_ok=True)
    os.makedirs(os.path.join(RAW, 'depth'), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, 'depth_charts.json'), 'w'), separators=(',', ':'))
    json.dump(out, open(os.path.join(RAW, 'depth', f"{dt.date.today().isoformat()}.json"), 'w'))
    json.dump(moves, open(os.path.join(RAW, 'depth', f'transactions_{yr}.json'), 'w'))

    allp = [p for t in out['teams'].values() for p in t['players']]
    print(f"{out['season_label']} {out['phase']}: {len(out['teams'])} teams, {len(allp)} rostered players")
    print(f"  moved teams since last season: {sum(p['moved'] for p in allp)}")
    print(f"  rookies: {sum(p['rookie'] for p in allp)}  (matched to {yr - 1} draft: {sum(bool(p['draft']) for p in allp)})")
    print(f"  not slotted on ESPN's depth chart: {unslotted_total}   stale depth entries dropped: {stale_total}")
    print(f"  offseason transactions: {len(moves)}")


if __name__ == '__main__':
    main()
