#!/usr/bin/env python3
"""
Forward read of the live shot-matchup term (docs/matchup-live.md, "Forward read"). Rules are fixed there; this implements them and nothing else.

  python3 nba/scripts/score_matchup_forward.py counts        rows and nights per stat (no accuracy numbers)
  python3 nba/scripts/score_matchup_forward.py monthly       the early-stop check only: a stat whose gain is negative at t <= -2.5 is to be demoted
  python3 nba/scripts/score_matchup_forward.py read          the registered read; a stat is read ONCE, when it has 500 rows from 25 nights

Population: settled single-stat 3PM, AST (games on or after 2026-10-26) and PTS, REB (on or after 2026-10-27) prop bets in bets/<day>.json on origin/nba-data, carrying `mt` (the matchup term inside `mu`),
win or loss, with a stored `actual`. gain = |actual - (mu - mt)| - |actual - mu|, game as the unit, bootstrap 2,000 draws, seed 7, t = mean / sd of the bootstrap means.
KEEP: gain > 0 with t >= 1.65. DEMOTE: otherwise. Results are written to data/matchup_forward.json (a stat already read is never overwritten).
"""
import json, os, random, statistics as st, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, '..', 'data', 'matchup_forward.json')
FROM = {'3pm': '2026-10-26', 'ast': '2026-10-26', 'pts': '2026-10-27', 'reb': '2026-10-27'}      # first game day each stat's term was live (points and rebounds need the daily team-allowance file)
MIN_ROWS, MIN_NIGHTS = 500, 25
STATS = tuple(FROM)


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True, check=True).stdout


def load_rows(ref='origin/nba-data'):
    names = [n for n in git('ls-tree', '--name-only', ref, 'bets/').split() if n.endswith('.json')]
    rows = []
    for n in sorted(names):
        day = n.split('/')[-1][:-5]
        if day < min(FROM.values()):
            continue
        for b in json.loads(git('show', f'{ref}:{n}')):
            if b.get('stat') in STATS and day >= FROM[b['stat']] and b.get('mt') is not None and b.get('result') in ('win', 'loss') and b.get('actual') is not None and b.get('mu') is not None and not b.get('pre'):
                rows.append({'day': day, 'game': str(b['game']), 'stat': b['stat'], 'mu': b['mu'], 'mt': b['mt'], 'actual': b['actual']})
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
            by[r['game']].append(abs(r['actual'] - (r['mu'] - r['mt'])) - abs(r['actual'] - r['mu']))
        out[s] = {'rows': len(R), 'nights': len({r['day'] for r in R}), 'nonzero_mt': sum(1 for r in R if abs(r['mt']) > 1e-9), 'stats': boot(by) if len(by) >= 5 else None}
    return out


def ready(c):
    return c['rows'] >= MIN_ROWS and c['nights'] >= MIN_NIGHTS


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'counts'
    rows = load_rows()
    res = per_stat(rows)
    if cmd == 'counts':
        print(json.dumps({s: {k: v for k, v in c.items() if k != 'stats'} | {'ready': ready(c)} for s, c in res.items()}, indent=1))
        return
    if cmd == 'monthly':
        for s, c in res.items():
            st_ = c['stats']
            flag = bool(st_ and st_['gain'] < 0 and st_['t'] is not None and st_['t'] <= -2.5)
            print(s, json.dumps(c), '| EARLY STOP: demote now' if flag else '| no early stop')
        return
    if cmd == 'read':
        done = json.load(open(OUT)) if os.path.exists(OUT) else {}
        for s, c in res.items():
            if s in done:
                print(s, 'already read; the first read stands:', json.dumps(done[s])); continue
            if not ready(c):
                print(s, f"not ready: {c['rows']} rows, {c['nights']} nights (needs {MIN_ROWS} and {MIN_NIGHTS}); nothing scored"); continue
            g = c['stats']
            verdict = 'KEEP' if g['gain'] > 0 and g['t'] is not None and g['t'] >= 1.65 else 'DEMOTE'
            done[s] = {**c, 'verdict': verdict, 'read_on': datetime.now(timezone.utc).strftime('%Y-%m-%d')}
            print(s, json.dumps(done[s]))
        json.dump(done, open(OUT, 'w'), indent=1)
        return
    print(__doc__)


if __name__ == '__main__':
    main()
