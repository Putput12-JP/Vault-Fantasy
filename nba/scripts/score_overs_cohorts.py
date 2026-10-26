#!/usr/bin/env python3
"""
Overs cohorts, forward tracking (docs/overs-cohorts.md). Rules are fixed there; this implements them and nothing else. Nothing here is a bet or changes a pick.

  python3 nba/scripts/score_overs_cohorts.py counts      rows and games per cohort (no hit rates)
  python3 nba/scripts/score_overs_cohorts.py read        the registered read, once, on or after 2026-11-23 and only when O1 has 300 rows and 100 games
  python3 nba/scripts/score_overs_cohorts.py monitor     the same table after the read, labelled monitoring

Rows: lean log first look on origin/nba-data, not held, graded W or L, games on or after 2026-10-26.
WORKS: the game-clustered 95% interval's lower end is above 52.4% with 300 rows and 100 games. FAILS: its upper end is below 52.4% with the same minimums. Otherwise inconclusive.
"""
import json, os, random, statistics as st, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, '..', 'data', 'overs_cohorts.json')
FROM_DAY, READ_ON, MIN_ROWS, MIN_GAMES, BE = '2026-10-26', '2026-11-23', 300, 100, 110 / 210


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True, check=True).stdout


def gap(r):
    return (r['mu'] - r['line']) / max(abs(r['line']), 0.5)


COHORTS = {
    'O1': lambda r: r['side'] == 'O' and gap(r) >= 0.25,
    'O2': lambda r: r['side'] == 'O' and r['p_mkt'] is not None and r['p_mkt'] > 0.5,
    'O3': lambda r: r['side'] == 'O' and r['p_mkt'] is not None and r['p_mkt'] < 0.5,
    'U1': lambda r: r['side'] == 'U' and gap(r) <= -0.25,
    'A_over': lambda r: r['side'] == 'O',
    'A_under': lambda r: r['side'] == 'U',
}


def load_rows(ref='origin/nba-data'):
    rows = []
    for n in sorted(x for x in git('ls-tree', '--name-only', ref, 'leans/').split() if x.endswith('.json') and '/pre' not in x):
        d = json.loads(git('show', f'{ref}:{n}'))
        if d['day'] < FROM_DAY:
            continue
        cols = d['cols']
        for raw in d['rows']:
            r = dict(zip(cols, raw))
            if r['clock'] == 'f' and not r['held'] and r['res'] in ('W', 'L') and r['line'] is not None and r['mu'] is not None:
                rows.append(r)
    return rows


def stats(rows, draws=2000, seed=7):
    by = defaultdict(list)
    for r in rows:
        by[str(r['game'])].append(1 if r['res'] == 'W' else 0)
    n = len(rows)
    out = {'rows': n, 'games': len(by)}
    if len(by) < 5:
        return out
    gk = list(by)
    rng = random.Random(seed)
    ms = []
    for _ in range(draws):
        s = m = 0
        for g in rng.choices(gk, k=len(gk)):
            s += sum(by[g]); m += len(by[g])
        ms.append(s / m)
    ms.sort()
    out.update({'hit': round(sum(sum(v) for v in by.values()) / n, 4), 'ci95': [round(ms[int(draws * .025)], 4), round(ms[int(draws * .975)], 4)]})
    priced = [r['units'] for r in rows if r.get('units') is not None]
    out['priced_rows'] = len(priced)
    out['units_per_priced_row'] = round(st.mean(priced), 4) if priced else None
    return out


def verdict(s):
    if s['rows'] < MIN_ROWS or s['games'] < MIN_GAMES or 'ci95' not in s:
        return 'collecting'
    return 'WORKS' if s['ci95'][0] > BE else ('FAILS' if s['ci95'][1] < BE else 'inconclusive')


def table(rows):
    return {k: (lambda s: {**s, 'verdict': verdict(s)})(stats([r for r in rows if f(r)])) for k, f in COHORTS.items()}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'counts'
    rows = load_rows()
    if cmd == 'counts':
        print(json.dumps({k: {'rows': len([r for r in rows if f(r)]), 'games': len({str(r['game']) for r in rows if f(r)})} for k, f in COHORTS.items()}, indent=1))
    elif cmd in ('read', 'monitor'):
        t = table(rows)
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if cmd == 'read':
            if today < READ_ON:
                print(f'not before {READ_ON}; nothing scored.'); return
            if t['O1']['rows'] < MIN_ROWS or t['O1']['games'] < MIN_GAMES:
                print(f"O1 has {t['O1']['rows']} rows and {t['O1']['games']} games (needs {MIN_ROWS} and {MIN_GAMES}); nothing recorded as the read."); return
            if os.path.exists(OUT):
                print('already read; the first read stands:', open(OUT).read()[:500]); return
            json.dump({'read_on': today, 'cohorts': t}, open(OUT, 'w'), indent=1)
        print(json.dumps(t, indent=1))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
