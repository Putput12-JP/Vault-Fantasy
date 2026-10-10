#!/usr/bin/env python3
"""
Proof that sim_engine.py (the Python port the live record and the pre-registered test use) plays the game the way the page does.
Loads the page in Chromium, takes the first game on its baked board, and compares:
  1. INPUTS, exactly: who plays, each player's minutes, play chance, and stat means and variance terms (page simInputs vs sim_engine.inputs).
     These are deterministic, so any difference is a porting error.
  2. RESULTS, statistically: the page's 10,000 simulated games vs the engine's, in the players' own sum environment. JavaScript and
     numpy draw different random numbers, so the comparison is on means and spreads, with Monte Carlo error allowed for.

  python3 nba/scripts/check_sim_parity.py [--seed=N] [-v]   # needs playwright for node (npm i -g playwright) and Chromium
Exit status 1 if inputs differ or results disagree beyond Monte Carlo error.
"""
import json, math, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import pricing as PX, sim_engine as SE

PAGE = os.path.join(HERE, '..', 'projections.html')
SEED = next((a.split('=')[1] for a in sys.argv if a.startswith('--seed=')), '4242')
JS = r"""
const {chromium} = require(process.env.PLAYWRIGHT_NODE || 'playwright');
(async () => {
  const b = await chromium.launch({executablePath: process.env.CHROME || '/opt/pw-browsers/chromium'});
  const p = await b.newPage();
  await p.goto('file://' + process.argv[2] + '#sim', {waitUntil: 'load'}); await p.waitForTimeout(1500);
  const SEED = +process.argv[3];
  const out = await p.evaluate(SEED => {
    const pick = pickBoard(), B = pick.board, g = [...(B.games || [])].sort((a, b) => a.tip - b.tip)[0];
    const T = simInputs(g, B, pick);
    const eA = T[0].rows.reduce((a, r) => a + r.mu.pts * r.pPlay, 0), eH = T[1].rows.reduce((a, r) => a + r.mu.pts * r.pPlay, 0);
    const mean = {m: eH - eA, t: eH + eA}, res = simRun(T, mean, SEED);
    const teams = T.map((t, k) => ({team: t.team, f: t.f, rows: t.rows.map((r, j) => {
      const o = res.teams[k].out[j], st = {};
      for (const s of [...SIM_STATS, 'pra']){ const a = simPlayed(o, s); st[s] = [a.length, simMean(a), simSd(a)]; }
      return {pid: r.pid, min: r.min, pPlay: r.pPlay, mu: r.mu, ex: r.ex, st}; })}));
    return {mode: pick.mode, game: g, board_example: !!B.example, mean, margin: [simMean(res.margin), simSd(res.margin)], total: [simMean(res.total), simSd(res.total)], teams, N: res.N};
  }, SEED);
  console.log(JSON.stringify(out)); await b.close();
})();
"""
f = tempfile.NamedTemporaryFile('w', suffix='.js', delete=False); f.write(JS); f.close()
env = dict(os.environ, NODE_PATH=subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip())
r = subprocess.run(['node', f.name, os.path.abspath(PAGE), SEED], capture_output=True, text=True, env=env)
if r.returncode:
    print(r.stderr[-800:]); sys.exit(2)
J = json.loads(r.stdout.strip().splitlines()[-1])
g = J['game']
print(f"page game {g['away']} @ {g['home']}, board mode {J['mode']}")

board = json.load(open(os.path.join(HERE, '..', 'data', 'prop_board.json')))['example' if J['board_example'] else 'live']
pr = PX.Pricer(example=J['board_example'])
G = SE.inputs(pr, g, board, 'example' if J['mode'] == 'example' else 'live')
bad = []
for k, (jt, pt) in enumerate(zip(J['teams'], G.teams)):
    jp = {r['pid']: r for r in jt['rows']}; pp = {r['pid']: r for r in pt['rows']}
    if set(jp) != set(pp):
        bad.append(f"{jt['team']}: players differ, page-only {sorted(set(jp) - set(pp))[:4]} engine-only {sorted(set(pp) - set(jp))[:4]}")
    for pid in set(jp) & set(pp):
        a, b = jp[pid], pp[pid]
        for key, x, y in [('min', a['min'], b['min']), ('pPlay', a['pPlay'], b['pPlay'])] + [(f'mu.{s}', a['mu'][s], b['mu'][s]) for s in SE.STATS] + [(f'ex.{s}', a['ex'][s], b['ex'][s]) for s in SE.STATS]:
            if abs(x - y) > 1e-6 + 1e-6 * abs(x):
                bad.append(f"{jt['team']} {pid} {key}: page {x:.6f} engine {y:.6f}")
print(f"inputs: {sum(len(t['rows']) for t in J['teams'])} players on the page, {sum(len(t['rows']) for t in G.teams)} in the engine, {len(bad)} differences")

res = SE.run(pr, G, SE.players_mean(G), seed=int(SEED), N=J['N'])
N = J['N']; worst, nz, cells = 0.0, 0, 0
chk = [('margin', J['margin'], (res['margin'].mean(), res['margin'].std())), ('total', J['total'], (res['total'].mean(), res['total'].std()))]
for name, (jm, js), (pm, ps) in chk:
    z = (jm - pm) / math.sqrt((js ** 2 + ps ** 2) / N); print(f"{name}: page {jm:.2f} (sd {js:.2f}) engine {pm:.2f} (sd {ps:.2f}) z {z:+.1f}")
    if abs(z) > 4 or abs(js / ps - 1) > .05: bad.append(f'{name} disagrees')
for k, jt in enumerate(J['teams']):
    for j, jr in enumerate(jt['rows']):
        for s in SE.STATS + ['pra']:
            n, jm, js = jr['st'][s]; a = SE.played(res, k, j, s)
            if n < 500 or len(a) < 500 or js < .3:
                continue
            # Each engine corrects the raw scoring centre by its own 3,000-game pilot (page and engine alike), so points, and PRA which contains
            # them, carry an independent pilot error of about pts sd / sqrt(3000) per engine on top of the final run's Monte Carlo error.
            pilot = 2 * jr['st']['pts'][2] ** 2 / SE.PILOT_N if s in ('pts', 'pra') else 0.0
            z = (jm - a.mean()) / math.sqrt((js ** 2 / n) + (a.std() ** 2 / len(a)) + pilot); cells += 1; worst = max(worst, abs(z)); nz += abs(z) > 3
            if abs(z) > 3 and "-v" in sys.argv: print(f"    z {z:+.1f} {jt['team']} pid {jr['pid']} {s}: page mean {jm:.2f} sd {js:.2f}  engine mean {a.mean():.2f} sd {a.std():.2f}  want {jr['mu'].get(s, 0) * jr['pPlay']:.2f}")
            if jm >= .5 and abs(js / a.std() - 1) > .10: bad.append       # a mean under 0.5 has a heavy right tail, so its sample spread is too noisy to compare(f"{jt['team']} {jr['pid']} {s} spread page {js:.2f} engine {a.std():.2f}")
print(f"player stats compared: {cells}; |z| above 3 on {nz} (expect about {cells * .0027:.1f}); worst |z| {worst:.1f}")
if nz > max(2, cells * .01): bad.append('too many player-stat means disagree beyond Monte Carlo error')
print('PARITY', 'OK' if not bad else 'FAILED')
for x in bad[:15]:
    print('  ', x)
sys.exit(1 if bad else 0)
