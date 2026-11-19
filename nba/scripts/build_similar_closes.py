#!/usr/bin/env python3
"""
Closing prop lines per player-game, for the "Similar players vs <opponent>" card on the prop data-dive page.

The lean recorder logs every prop at its last look before tip (leans/<day>.json on the nba-data branch, clock 'c'). That line is the only per-game
prop line we store for players other than the one on screen, so the card only has games from the first recorded day on. Nothing is estimated:
a game without a stored closing line is not on the card.

  {"generated": ..., "first": "2026-10-22", "through": "2026-11-18",
   "p": {"<athlete id>|<stat>": [[day (days since 1970-01-01), closing line, opponent abbreviation], ...]}}     newest first

  python3 nba/scripts/build_similar_closes.py        needs `git fetch origin nba-data` first; writes data/similar_closes.json
"""
import datetime as dt, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = os.path.join(HERE, '..', 'data', 'similar_closes.json')
BRANCH = 'origin/nba-data'
EPOCH = dt.date(1970, 1, 1)


def git(*a):
    r = subprocess.run(['git', '-C', ROOT, *a], capture_output=True)
    return r.stdout if r.returncode == 0 else b''


def main():
    names = sorted(f for f in git('ls-tree', '-r', '--name-only', BRANCH).decode().split('\n') if f.startswith('leans/') and f.endswith('.json'))
    if not names:
        sys.exit(f'no leans/ files on {BRANCH}; keeping the last file')
    out, days = {}, []
    for f in names:
        raw = git('show', f'{BRANCH}:{f}')
        if not raw:
            continue
        d = json.loads(raw)
        ix = {k: i for i, k in enumerate(d['cols'])}
        day = (dt.date.fromisoformat(d['day']) - EPOCH).days
        seen = set()
        for r in d['rows']:
            if r[ix['clock']] != 'c' or r[ix['line']] is None:
                continue
            game = d['games'].get(r[ix['game']])
            if not game:
                continue
            away, home = [x.strip() for x in game[0].split('@')]
            team = r[ix['team']]
            opp = home if team == away else away if team == home else None
            key = (r[ix['pid']], r[ix['stat']], r[ix['game']])
            if opp is None or key in seen:
                continue
            seen.add(key)
            out.setdefault(f'{r[ix["pid"]]}|{r[ix["stat"]]}', []).append([day, r[ix['line']], opp])
        days.append(d['day'])
    for v in out.values():
        v.sort(reverse=True)
    json.dump({'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'first': min(days), 'through': max(days), 'p': out},
              open(OUT, 'w'), separators=(',', ':'))
    print(f'wrote {os.path.relpath(OUT)}: {sum(len(v) for v in out.values())} closing lines, {len(days)} days, {min(days)} to {max(days)}, {os.path.getsize(OUT) // 1000} KB')


if __name__ == '__main__':
    main()
