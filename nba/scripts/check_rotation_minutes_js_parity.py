#!/usr/bin/env python3
"""
Proof the page's JavaScript rotation minutes + GP (ui/rotation_minutes.js) return the same numbers as live pricing's Python
(Pricer.game_minutes_rot and Pricer.gp_minutes), on the live model state, for every team in synthetic games, with and without players ruled out.

  python3 nba/scripts/check_rotation_minutes_js_parity.py        (needs node)
"""
import json, os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import minutes_gbm as MG
import pricing as PX

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, '..', 'ui', 'rotation_minutes.js')
GJS = os.path.join(HERE, '..', 'ui', 'minutes_gbm.js')

pr = PX.Pricer(example=False)
teams = sorted(pr.state['teams'])
tip = max(pr.state['team_last'].values()) + 150 * 86400 // 30
random.seed(11)
cases = []
for i, team in enumerate(teams):
    opp = teams[(i + 7) % len(teams)]
    g = {'id': f'syn{i}', 'tip': tip, 'home': team if i % 2 else opp, 'away': opp if i % 2 else team, 'spread': [-4.5, 7.5, None, -12.0][i % 4], 'season_type': 2}
    pl = {int(a): MG.from_export(r) for a, r in pr.state['gbm']['players'].items()}
    rot = sorted(MG.rotation(pl, team, tip))
    status = {a: 'Out' for a in random.sample(rot, min(len(rot), i % 3))} | ({rot[0]: 'Doubtful'} if rot and i % 5 == 0 else {})
    cache = {}
    rt = pr.game_minutes_rot(team, g, status, cache)
    v2 = {a: v['min_v2'] for a, v in pr.game_minutes(team, g, status, cache).items()}
    gp = pr.gp_minutes(team, g, status, cache, v2)
    gb = pr.game_minutes_gbm(team, g, status, cache)
    cases.append({'team': team, 'g': g, 'status': {str(k): v for k, v in status.items()}, 'roster': [x['id'] for x in pr.D['teams'].get(team, {}).get('players', [])],
                  'rt': {str(k): v for k, v in rt.items()}, 'gp': {str(k): v for k, v in gp.items()}, 'gb': {str(k): v for k, v in gb.items()}, 'v2': {str(k): v for k, v in v2.items()}})
payload = {'model': pr.ROTM, 'M': pr.MM, 'state': pr.state, 'cases': cases}
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(payload, f)
    path = f.name
runner = f"""
const m = require({json.dumps(os.path.abspath(JS))}), d = JSON.parse(require('fs').readFileSync({json.dumps(path)}, 'utf8'));
let worst = 0, n = 0, missing = 0;
for (const c of d.cases){{
  const out = {{}}; for (const [a, s] of Object.entries(c.status)) if (s === 'Out' || s === 'Doubtful' || s === 'Inactive') out[+a] = 1;
  const rt = m.rotMinutes(d.model, d.M, d.state, c.team, c.g, out, c.roster);
  const gb = {{}}; for (const [a, v] of Object.entries(c.gb)) gb[+a] = v;
  const v2 = {{}}; for (const [a, v] of Object.entries(c.v2)) v2[+a] = v;
  const gp = m.gpMinutes(d.model, rt, gb, v2);
  for (const [exp, got, f] of [[c.rt, rt, ['min', 'p_plays', 'p_rot']], [c.gp, gp, ['min', 'p_plays', 'p_rot']]]){{
    for (const [a, v] of Object.entries(exp)){{ if (!(a in got)) {{ missing++; continue; }} for (const k of f){{ worst = Math.max(worst, Math.abs(got[a][k] - v[k])); }} n++; }}
    for (const a of Object.keys(got)) if (!(a in exp)) missing++;
  }}
}}
console.log(JSON.stringify({{n, worst, missing}}));
"""
r = subprocess.run(['node', '-e', runner], capture_output=True, text=True)
os.unlink(path)
if r.returncode:
    raise SystemExit(r.stderr)
res = json.loads(r.stdout)
print(f"{len(cases)} team-games, {res['n']} players compared, {res['missing']} present in only one side; max |JS - Python| = {res['worst']:.2e}")
if res['worst'] > 1e-6 or res['missing'] or not res['n']:
    raise SystemExit('JS PARITY FAILED')
print('JS PARITY OK')
