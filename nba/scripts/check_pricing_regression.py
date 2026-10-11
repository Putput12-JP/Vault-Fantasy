#!/usr/bin/env python3
"""
Regression check that needs no price archive: did a change leave v2 pricing and the v3 shadow exactly as they were?

  python3 nba/scripts/check_pricing_regression.py dump OUT.json [--root DIR]    # DIR = a repo checkout (default: this one)
  python3 nba/scripts/check_pricing_regression.py compare A.json B.json

dump runs that checkout's own pricing.py on (1) the example board: every priced candidate, and (2) the LIVE model state with a
synthetic game for every team: v2 minutes (game_minutes) and the v3 shadow (game_minutes_v3), with and without a starting five.
Typical use: `git worktree add /tmp/base <commit>`, dump from both trees, compare. This replaces check_minutes_parity.py for the
question "did I break v2 or v3?" (that script needs raw/tables, the price archive; it proves backtest == live, which this does not).
"""
import json, os, sys

args = sys.argv[1:]
if args and args[0] == 'compare':
    a, b = (json.load(open(p)) for p in args[1:3])
    bad = [k for k in a if a[k] != b.get(k)]
    for k in a:
        print(f"{k:28s} {'IDENTICAL' if k not in bad else 'DIFFERENT'}  ({len(json.dumps(a[k])):,} bytes)")
    raise SystemExit(1 if bad or set(b) - set(a) else 0)

root = os.path.abspath(args[args.index('--root') + 1]) if '--root' in args else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(root, 'nba', 'scripts'))
import pricing as PX
assert os.path.abspath(PX.__file__).startswith(os.path.abspath(root)), PX.__file__

ex = json.load(open(os.path.join(root, 'nba', 'data', 'prop_board.json')))['example']
rows = PX.price_board(ex)
out = {'example_board': sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)}
pr = PX.Pricer(example=False)
tip = pr.state['asof'] and max(pr.state['team_last'].values()) + 3 * 86400
v2, v3, v3s = {}, {}, {}
for i, team in enumerate(sorted(pr.state['teams'])):
    opp = sorted(pr.state['teams'])[(i + 7) % len(pr.state['teams'])]
    g = {'id': f'syn{i}', 'tip': tip, 'home': team, 'away': opp, 'spread': -4.5 if i % 2 else 7.5, 'total': 224.5}
    st = {a: 'Out' for a in list(pr.state['players'])[:0]}
    for t in (team, opp):
        cache = {}
        five = [int(a) for a, p in pr.state['players'].items() if p.get('m3') and p['m3'][3] == t][:5]
        v2[f'{i}|{t}'] = {str(k): [round(x, 9) for x in (v['min'], v['mu']['pts'], v['mu']['reb'])] for k, v in pr.game_minutes(t, g, st, cache).items()}
        v3[f'{i}|{t}'] = {str(k): round(v, 9) for k, v in pr.game_minutes_v3(t, g, st, {}).items()}
        v3s[f'{i}|{t}'] = {str(k): round(v, 9) for k, v in pr.game_minutes_v3(t, g, st, {}, starters=five).items()}
out.update(v2_minutes=v2, v3_minutes=v3, v3_minutes_with_starters=v3s)
json.dump(out, open(args[1], 'w'), sort_keys=True)
print(f"dumped {len(rows)} board candidates and {len(v2)} team-games x 3 from {root} -> {args[1]}")
