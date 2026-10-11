#!/usr/bin/env python3
"""
Proof the page's JavaScript GBM (ui/minutes_gbm.js) returns the same minutes as the Python scorer live pricing uses
(Pricer.game_minutes_gbm), on the live model state, for every team in synthetic games, with and without players ruled out.

  python3 nba/scripts/check_minutes_gbm_js_parity.py        (needs node)
"""
import json, os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import minutes_gbm as MG
import pricing as PX

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, '..', 'ui', 'minutes_gbm.js')

pr = PX.Pricer(example=False)
GB = pr.state['gbm']
teams = sorted(pr.state['teams'])
tip = max(pr.state['team_last'].values()) + 150 * 86400 // 30          # five days after the last game: some state is fresh, some stale
random.seed(7)
cases = []
for i, team in enumerate(teams):
    opp = teams[(i + 7) % len(teams)]
    g = {'id': f'syn{i}', 'tip': tip, 'home': team if i % 2 else opp, 'away': opp if i % 2 else team, 'spread': [-4.5, 7.5, None, -12.0][i % 4]}
    pl = {int(a): MG.from_export(r) for a, r in GB['players'].items()}
    rot = sorted(MG.rotation(pl, team, tip))
    status = {a: 'Out' for a in random.sample(rot, min(len(rot), i % 3))} | ({rot[0]: 'Doubtful'} if rot and i % 5 == 0 else {})
    roster = [x['id'] for x in pr.D['teams'].get(team, {}).get('players', [])]
    pr.cand_override.pop((team, str(g['id'])), None)
    if hasattr(pr, '_gbm_pl'):
        del pr._gbm_pl
    expect = pr.game_minutes_gbm(team, g, status, {})
    cases.append({'team': team, 'g': g, 'status': {str(k): v for k, v in status.items()}, 'roster': roster,
                  'expect': {str(k): v for k, v in expect.items()}})
payload = {'model': MG.load_model(), 'gb': GB, 'cases': cases}
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(payload, f)
    path = f.name
runner = f"""
const m = require({json.dumps(os.path.abspath(JS))}), d = JSON.parse(require('fs').readFileSync({json.dumps(path)}, 'utf8'));
let worst = 0, n = 0, missing = 0;
for (const c of d.cases){{
  const got = m.gbmMinutes(d.model, d.gb, c.team, c.g, c.status, c.roster);
  for (const [a, v] of Object.entries(c.expect)){{ if (!(a in got)) {{ missing++; continue; }} worst = Math.max(worst, Math.abs(got[a] - v)); n++; }}
  for (const a of Object.keys(got)) if (!(a in c.expect)) missing++;
}}
console.log(JSON.stringify({{n, worst, missing}}));
"""
r = subprocess.run(['node', '-e', runner], capture_output=True, text=True)
os.unlink(path)
if r.returncode:
    raise SystemExit(r.stderr)
res = json.loads(r.stdout)
print(f"{len(cases)} team-games, {res['n']} players compared, {res['missing']} present in only one side; max |JS - Python| = {res['worst']:.2e} min")
if res['worst'] > 1e-6 or res['missing'] or not res['n']:
    raise SystemExit('JS PARITY FAILED')
print('JS PARITY OK')
