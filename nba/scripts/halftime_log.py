#!/usr/bin/env python3
"""
Halftime line recorder: captures the live spread the moment a game reaches halftime.

Why: the "pregame dog up 15+ at the half, take the new dog live" system cannot be
graded without the live halftime price, and ESPN keeps only the last live value
after the game ends (backfill_espn_odds shows it as `current`). snapshot.py skips
the live provider on purpose (ESPN_SKIP = {59}), so nothing else stores it.

One row per game, written the first time the scoreboard shows STATUS_HALFTIME:
  pregame close spread / total / ML (a non-live provider), the live provider's
  current spread + price + total + ML, the score and quarter scores at the half,
  and when we saw it. Grading later needs the final score, which hoopR provides.

  python3 nba/scripts/halftime_log.py --dir=nba-data            poll once
  python3 nba/scripts/halftime_log.py --dir=nba-data --loop --commit --max-minutes=330
Writes <dir>/halftime/<YYYY-MM>.jsonl (append, deduped by game_id).
"""
import datetime as dt, json, os, re, subprocess, sys, time

SCORE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
CORE = 'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba'
LIVE_PROVIDER = 59          # "ESPN Bet - Live Odds"
POLL_S = 60
ET = dt.timezone(dt.timedelta(hours=-4))   # close enough for picking the scoreboard day; we also ask yesterday


def curl(url, tries=2):
    # ESPN 403s urllib, so everything goes through curl.
    for _ in range(tries):
        p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '30', url], capture_output=True)
        try:
            return json.loads(p.stdout)
        except ValueError:
            time.sleep(1.5)
    return None


def am(o):
    return (o or {}).get('american')


def side(t):
    out = {}
    for k in ('open', 'close', 'current'):
        b = (t or {}).get(k) or {}
        out[k] = {'spread': am(b.get('pointSpread')), 'spread_px': am(b.get('spread')), 'ml': am(b.get('moneyLine'))}
    return out


def odds(game_id):
    """{'pre': pregame provider block, 'live': live provider block} from the core odds endpoint."""
    d = curl(f'{CORE}/events/{game_id}/competitions/{game_id}/odds')
    pre = live = None
    for it in (d or {}).get('items', []):
        pid = int((it.get('provider') or {}).get('id') or 0)
        blk = {'provider': (it.get('provider') or {}).get('name'), 'provider_id': pid,
               'details': it.get('details'), 'spread': it.get('spread'), 'over_under': it.get('overUnder'),
               'home': side(it.get('homeTeamOdds')), 'away': side(it.get('awayTeamOdds')),
               'total': {k: {'total': am((it.get(k) or {}).get('total')), 'over_px': am((it.get(k) or {}).get('over')),
                             'under_px': am((it.get(k) or {}).get('under'))} for k in ('open', 'close', 'current')}}
        if pid == LIVE_PROVIDER:
            live = blk
        elif pre is None or (blk['home']['close']['spread'] is not None and pre['home']['close']['spread'] is None):
            pre = blk
    return {'pre': pre, 'live': live}


def lines(c):
    return [x.get('value') for x in c.get('linescores', [])]


def halftime_games(now):
    out = []
    for day in {now.date(), (now - dt.timedelta(days=1)).date()}:
        d = curl(f'{SCORE}?dates={day:%Y%m%d}')
        for e in (d or {}).get('events', []):
            st = e['status']['type']
            if st.get('name') != 'STATUS_HALFTIME':
                continue
            comp = e['competitions'][0]
            by = {c['homeAway']: c for c in comp['competitors']}
            out.append({'game_id': int(e['id']), 'season_type': e['season']['type'], 'tip': e['date'],
                        'home': by['home']['team']['abbreviation'], 'away': by['away']['team']['abbreviation'],
                        'home_half': int(by['home']['score']), 'away_half': int(by['away']['score']),
                        'home_q': lines(by['home']), 'away_q': lines(by['away'])})
    return out


def seen(root):
    ids = set()
    d = os.path.join(root, 'halftime')
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith('.jsonl'):
                for line in open(os.path.join(d, f)):
                    try:
                        ids.add(json.loads(line)['game_id'])
                    except (ValueError, KeyError):
                        pass
    return ids


def flag(row):
    """Does this game meet the system's trigger? Spread is the home line (negative = home favourite)."""
    pre = (row.get('pre') or {}).get('home', {}).get('close', {}).get('spread')
    if pre is None:
        return None
    try:
        pre = float(pre)
    except (TypeError, ValueError):
        return None
    if pre == 0:
        return None
    dog_up = (row['home_half'] - row['away_half']) * (1 if pre > 0 else -1)   # pregame dog's halftime lead
    return {'pre_home_spread': pre, 'dog_lead_half': dog_up, 'trigger15': dog_up >= 15}


def poll(root):
    now = dt.datetime.now(ET)
    done = seen(root)
    new = 0
    for g in halftime_games(now):
        if g['game_id'] in done:
            continue
        o = odds(g['game_id'])
        row = {**g, 'seen': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), **o}
        row['sys'] = flag(row)
        d = os.path.join(root, 'halftime')
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f'{now:%Y-%m}.jsonl'), 'a') as f:
            f.write(json.dumps(row, separators=(',', ':')) + '\n')
        live = (o.get('live') or {}).get('home', {}).get('current', {}).get('spread')
        print(f"halftime {g['away']}@{g['home']} {g['away_half']}-{g['home_half']} live home spread {live} trigger {(row['sys'] or {}).get('trigger15')}", flush=True)
        new += 1
    return new


def commit(root):
    def git(*a):
        return subprocess.run(['git', '-C', root, *a], capture_output=True, text=True)
    git('add', 'halftime')
    if git('diff', '--cached', '--quiet').returncode == 0:
        return
    git('commit', '-m', 'halftime: live lines at the half [skip ci]')
    for _ in range(3):
        if git('push').returncode == 0:
            return
        git('pull', '--rebase', '-X', 'theirs')


def main(argv):
    root = next((a.split('=', 1)[1] for a in argv if a.startswith('--dir=')), 'nba-data')
    mins = next((float(a.split('=', 1)[1]) for a in argv if a.startswith('--max-minutes=')), 330)
    end = time.time() + mins * 60
    while True:
        try:
            n = poll(root)
        except Exception as e:          # a bad poll must not end the loop
            print('poll failed:', e, flush=True)
            n = 0
        if n and '--commit' in argv:
            commit(root)
        if '--loop' not in argv or time.time() + POLL_S > end:
            break
        time.sleep(POLL_S)


if __name__ == '__main__':
    main(sys.argv[1:])
