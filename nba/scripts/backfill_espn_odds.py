#!/usr/bin/env python3
"""
Backfill NBA game lines + player props from ESPN's public core API.

Per completed game (from the hoopR schedule, so game_id = ESPN event id):
  /events/{id}/competitions/{id}/odds             game lines, open + close + current
  /events/{id}/competitions/{id}/odds/{p}/propBets player props, open + current

What the data is and is not (probed 2026-09-29, see docs/PLAN.md §3):
  - Game lines: open and close for every 2025-26 game (ESPN BET, then DraftKings
    from Dec 2025).
  - Props: `open` is a real pre-game line + price. `current` is the last value
    ESPN saw, which is often AFTER tip (a live line). Keep `last_updated` so the
    backtest can tell a pre-tip close from a live line.
  - Props carry no over/under label. Each over/under pair is two consecutive
    rows with the same player, type and line; we store `ord` (0 = first row).
    Which one is the over is verified against outcomes in audit_espn_props.py,
    never assumed.

ESPN rejects Python's urllib (403), so requests go through curl.

  python3 nba/scripts/backfill_espn_odds.py 2025 2026
Writes nba/raw/espn_odds/games_<season>.jsonl (resumable: done games are skipped).
"""
import csv, json, os, re, subprocess, sys, concurrent.futures as cf

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, '..', 'raw')
CORE = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba'
KEEP_TYPES = {'STD', 'CC', 'RD16', 'QTR', 'SEMI', 'FINAL'}  # regular season, cup final, playoffs, play-in (STD, season_type 5)


def get(url, tries=3):
    for _ in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '40', url], capture_output=True)
        try:
            return json.loads(p.stdout)
        except Exception:
            continue
    return None


def ref_id(ref):
    m = re.search(r'/(athletes|teams|casinos)/(\d+)', ref or '')
    return int(m.group(2)) if m else None


def am(o):
    return (o or {}).get('american')


def side(t):
    """One team's odds block -> {open, close, current}: spread, spread price, moneyline."""
    out = {'fav_open': (t.get('open') or {}).get('favorite')}
    for k in ('open', 'close', 'current'):
        b = t.get(k) or {}
        out[k] = {'spread': am(b.get('pointSpread')), 'spread_px': am(b.get('spread')), 'ml': am(b.get('moneyLine'))}
    return out


def game_lines(item):
    tot = {k: {'total': am((item.get(k) or {}).get('total')),
               'over_px': am((item.get(k) or {}).get('over')),
               'under_px': am((item.get(k) or {}).get('under'))} for k in ('open', 'close', 'current')}
    return {
        'provider': item.get('provider', {}).get('name'),
        'provider_id': int(item.get('provider', {}).get('id') or 0),
        'spread': item.get('spread'), 'over_under': item.get('overUnder'), 'details': item.get('details'),
        'home': side(item.get('homeTeamOdds') or {}),
        'away': side(item.get('awayTeamOdds') or {}),
        'total': tot,
    }


def props(url):
    base = url.replace('http:', 'https:') + ('&' if '?' in url else '?') + 'limit=1000'
    items, page, pages = [], 1, 1
    while page <= pages:  # ESPN silently caps oversized pages at 25 items; 1000 is honoured
        d = get(f'{base}&page={page}') or {}
        items += d.get('items', [])
        pages = d.get('pageCount') or 1
        page += 1
    rows, seen = [], {}
    for x in items:
        o = x.get('odds', {})
        key = (ref_id((x.get('athlete') or {}).get('$ref')), x['type']['id'], (o.get('total') or {}).get('open'))
        n = seen.get(key, 0)
        seen[key] = n + 1
        rows.append({
            'athlete_id': key[0],
            'type_id': int(x['type']['id']), 'type': x['type']['name'],
            'ord': n,
            'open_line': (x.get('open') or {}).get('target', {}).get('value'),
            'open_px': (o.get('american') or {}).get('open'),
            'cur_line': (x.get('current') or {}).get('target', {}).get('value'),
            'cur_px': (o.get('american') or {}).get('value'),
            'last_updated': x.get('lastUpdated'),
        })
    return rows


def fetch_game(g):
    gid = g['id']
    d = get(f'{CORE}/events/{gid}/competitions/{gid}/odds')
    if d is None:
        return None
    rec = {'game_id': int(gid), 'tip': g['date'], 'type': g['type_abbreviation'], 'season_type': int(g['season_type']),
           'home': g['home_abbreviation'], 'away': g['away_abbreviation'],
           'home_score': g['home_score'], 'away_score': g['away_score'], 'lines': [], 'props': []}
    for item in d.get('items', []):
        rec['lines'].append(game_lines(item))
        pb = (item.get('propBets') or {}).get('$ref')
        if pb:
            pid = rec['lines'][-1]['provider_id']
            for r in props(pb):
                r['provider_id'] = pid
                rec['props'].append(r)
    return rec


def main(argv):
    seasons = [int(a) for a in argv if a.isdigit()] or [2025, 2026]
    out_dir = os.path.join(RAW, 'espn_odds')
    os.makedirs(out_dir, exist_ok=True)
    for s in seasons:
        games = [g for g in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'schedule_{s}.csv')))
                 if g['status_type_completed'] == 'true' and g['type_abbreviation'] in KEEP_TYPES]
        path = os.path.join(out_dir, f'games_{s}.jsonl')
        done = set()
        if os.path.exists(path):
            for line in open(path):
                done.add(json.loads(line)['game_id'])
        todo = [g for g in games if int(g['id']) not in done]
        print(f'{s}: {len(games)} games, {len(done)} done, {len(todo)} to fetch', flush=True)
        n = fails = 0
        with open(path, 'a') as f, cf.ThreadPoolExecutor(8) as ex:
            for rec in ex.map(fetch_game, todo):
                if rec is None:
                    fails += 1
                    continue
                f.write(json.dumps(rec, separators=(',', ':')) + '\n')
                n += 1
                if n % 200 == 0:
                    print(f'  {n}/{len(todo)}', flush=True)
        print(f'{s}: wrote {n}, failed {fails}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
