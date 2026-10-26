#!/usr/bin/env python3
"""
Forward read of the steals and turnovers matchup term (docs/matchup-extras-wiring.md, "Forward read"). Rules are fixed there; this implements them and nothing else.

  python3 nba/scripts/score_xstat_forward.py counts | monthly | read

Population: rows of xstats/<day>.json on origin/nba-data (xstat_record.py), steals (stl) and turnovers (tov), minutes above zero.
gain = |actual - mu0| - |actual - (mu0 + mt)|, game as the unit, bootstrap 2,000 draws, seed 7, t = mean / sd of the bootstrap means.
Read once per stat at 500 rows from 25 nights: KEEP if gain > 0 with t >= 1.65, else DEMOTE. Early stop (monthly): gain negative with t <= -2.5. Results go to data/xstat_forward.json (never overwritten).
"""
import json, os, random, statistics as st, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, '..', 'data', 'xstat_forward.json')
MIN_ROWS, MIN_NIGHTS = 500, 25
STATS = ('stl', 'tov')


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True, check=True).stdout


def load_rows(ref='origin/nba-data'):
    rows = []
    for n in sorted(x for x in git('ls-tree', '--name-only', ref, 'xstats/').split() if x.endswith('.json')):
        d = json.loads(git('show', f'{ref}:{n}'))
        cols = d['cols']
        games = d['games']
        for r in d['rows']:
            x = dict(zip(cols, r))
            if x['stat'] in STATS and x['min'] > 0:
                gid = next((g for g, v in games.items() if v[0].split(' @ ')[0] == x['team'] or v[0].split(' @ ')[-1] == x['team']), n)   # one game per team per day
                rows.append({'day': d['day'], 'game': f"{d['day']}|{gid}", 'stat': x['stat'], 'mu0': x['mu0'], 'mt': x['mt'], 'actual': x['actual']})
    return rows


def boot(by_game, draws=2000, seed=7):
    gk = list(by_game)
    rng = random.Random(seed)
    ms = []
    for _ in range(draws):
        s = n = 0
        for g in rng.choices(gk, k=len(gk)):
            s += sum(by_game[g]); n += len(by_game[g])
        ms.append(s / n)
    allv = [v for g in gk for v in by_game[g]]
    sd = st.pstdev(ms)
    mean = st.mean(allv)
    return {'gain': round(mean, 5), 't': round(mean / sd, 3) if sd else None, 'games': len(gk), 'rows': len(allv)}


def per_stat(rows):
    out = {}
    for s in STATS:
        R = [r for r in rows if r['stat'] == s]
        by = defaultdict(list)
        for r in R:
            by[r['game']].append(abs(r['actual'] - r['mu0']) - abs(r['actual'] - (r['mu0'] + r['mt'])))
        out[s] = {'rows': len(R), 'nights': len({r['day'] for r in R}), 'nonzero_mt': sum(1 for r in R if abs(r['mt']) > 1e-9), 'stats': boot(by) if len(by) >= 5 else None}
    return out


def ready(c):
    return c['rows'] >= MIN_ROWS and c['nights'] >= MIN_NIGHTS


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'counts'
    res = per_stat(load_rows())
    if cmd == 'counts':
        print(json.dumps({s: {k: v for k, v in c.items() if k != 'stats'} | {'ready': ready(c)} for s, c in res.items()}, indent=1))
    elif cmd == 'monthly':
        for s, c in res.items():
            g = c['stats']
            print(s, json.dumps(c), '| EARLY STOP: demote now' if g and g['gain'] < 0 and g['t'] is not None and g['t'] <= -2.5 else '| no early stop')
    elif cmd == 'read':
        done = json.load(open(OUT)) if os.path.exists(OUT) else {}
        for s, c in res.items():
            if s in done:
                print(s, 'already read; the first read stands:', json.dumps(done[s])); continue
            if not ready(c):
                print(s, f"not ready: {c['rows']} rows, {c['nights']} nights (needs {MIN_ROWS} and {MIN_NIGHTS}); nothing scored"); continue
            g = c['stats']
            done[s] = {**c, 'verdict': 'KEEP' if g['gain'] > 0 and g['t'] is not None and g['t'] >= 1.65 else 'DEMOTE', 'read_on': datetime.now(timezone.utc).strftime('%Y-%m-%d')}
            print(s, json.dumps(done[s]))
        json.dump(done, open(OUT, 'w'), indent=1)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
