#!/usr/bin/env python3
"""
Data Health page data: is every feed alive, and what does the model stand on.

  recorder   the live snapshot recorder (snapshot.py on GitHub Actions): status.json and the last
             3 days of polls.jsonl, read straight from the origin/nba-data branch (no checkout needed)
  inputs     the fitted models and roster files in nba/data/, with when each was built and how
             often it should be rebuilt
  archive    the backfilled history in nba/raw/ (local only; gitignored)

The page embeds this as a snapshot. When the page is served from GitHub Pages it also fetches
status.json and polls live from the branch, so it is current without a rebuild.

  python3 nba/scripts/build_data_health.py
Writes nba/data/data_health.json and re-renders nba/projections.html.
"""
import datetime as dt, glob, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(__file__))
import render_app

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DATA = os.path.join(HERE, '..', 'data')
RAW = os.path.join(HERE, '..', 'raw')
BRANCH = 'origin/nba-data'
POLL_DAYS = 3

# what each file is, and after how many days it counts as stale
INPUTS = [
    ('depth_charts.json', 'Rosters and depth charts', 'fetch_depth_charts.py', 2),
    ('player_projections.json', 'Minutes Lab projections', 'build_player_projections.py', 2),
    ('minutes_model.json', 'Minutes model', 'build_minutes_model.py', 21),
    ('usage_cascade.json', 'Usage cascade', 'build_usage_cascade.py', 21),
    ('prop_model.json', 'Prop model and variance', 'build_prop_model.py', 21),
    ('game_model.json', 'Game model ratings', 'build_game_model.py', 7),
]


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True).stdout


def recorder():
    subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'nba-data'], check=False)
    try:
        status = json.loads(git('show', f'{BRANCH}:status.json') or 'null')
    except json.JSONDecodeError:
        status = None
    days = sorted(l.rsplit('/', 1)[-1] for l in git('ls-tree', '--name-only', f'{BRANCH}:snapshots').split() if l[:2] == '20')
    polls = []
    for d in days[-POLL_DAYS:]:
        polls += [json.loads(l) for l in git('show', f'{BRANCH}:snapshots/{d}/polls.jsonl').splitlines() if l.strip()]
    last = git('log', '-1', '--format=%ct', BRANCH).strip()
    return {'status': status, 'polls': polls, 'days': days, 'last_commit': int(last) if last else None}


def inputs():
    out = []
    for f, what, script, stale in INPUTS:
        path = os.path.join(DATA, f)
        if not os.path.exists(path):
            out.append({'file': f, 'what': what, 'script': script, 'stale_days': stale, 'generated': None})
            continue
        d = json.load(open(path))
        out.append({'file': f, 'what': what, 'script': script, 'stale_days': stale, 'generated': d.get('generated'),
                    'kb': os.path.getsize(path) // 1000})
    return out


def lines(pattern):
    return sum(sum(1 for _ in open(p)) for p in glob.glob(os.path.join(RAW, pattern)))


def last_of(pattern, field):
    best = ''
    for p in glob.glob(os.path.join(RAW, pattern)):
        for l in open(p):
            if field in l:
                v = l.split(f'"{field}":"', 1)[-1].split('"', 1)[0] if l.startswith('{') else ''
                best = max(best, v)
    return best or None


def archive():
    """Backfilled history. Local only, so these numbers are as of the last build on this Mac."""
    if not os.path.isdir(RAW):
        return None
    box_last = None
    p = os.path.join(RAW, 'hoopr', 'player_box_2026.csv')
    if os.path.exists(p):
        with open(p) as f:
            hdr = f.readline().rstrip('\n').split(',')
            i = hdr.index('game_date')
            box_last = max(l.split(',')[i] for l in f if l.count(',') >= i)
    return [
        {'what': 'Box scores (hoopR)', 'seasons': '2021-22 to 2025-26', 'rows': lines('hoopr/player_box_*.csv'), 'unit': 'player games', 'through': box_last},
        {'what': 'Sportsbook lines and props (ESPN)', 'seasons': '2024-25 to 2025-26', 'rows': lines('espn_odds/games_*.jsonl'), 'unit': 'games', 'through': None},
        {'what': 'Kalshi pre-tip prices', 'seasons': '2024-25 to 2025-26', 'rows': lines('kalshi/prices_*.jsonl'), 'unit': 'markets', 'through': None},
        {'what': 'Official injury reports', 'seasons': '2024-25 to 2025-26', 'rows': lines('injuries/reports_*.jsonl'), 'unit': 'player statuses', 'through': last_of('injuries/reports_*.jsonl', 'report_et')},
    ]


def main():
    out = {'built': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
           'repo': 'Putput12-JP/Vault-Fantasy', 'branch': 'nba-data',
           'recorder': recorder(), 'inputs': inputs(), 'archive': archive()}
    json.dump(out, open(os.path.join(DATA, 'data_health.json'), 'w'), separators=(',', ':'))
    r = out['recorder']
    print(f"recorder: {len(r['days'])} days, {len(r['polls'])} polls in the last {POLL_DAYS} days, "
          f"status {'present' if r['status'] else 'missing'}")
    for a in out['archive'] or []:
        print(f"  archive {a['what']}: {a['rows']:,} {a['unit']} through {a['through']}")
    render_app.render()


if __name__ == '__main__':
    main()
