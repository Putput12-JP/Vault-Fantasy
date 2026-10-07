#!/usr/bin/env python3
"""
Game Simulation v2, step B3: M4 (docs/game-script-minutes-b2.md) plus the clamp calibration of docs/game-script-minutes-b3.md.

  --selfcheck  fit on 2022-23 and 2023-24, calibrate, score 2024-25 (informational development check)
  --freeze     fit on 2022-23 to 2025-26, calibrate, write data/game_script_frozen.json (commit before the first 2026-27 tip)
  --check      the frozen file is committed unchanged and its last commit is before the first 2026-27 tip
  --test       score the frozen model on the first 200 settled 2026-27 regular-season games (refuses unless --check passes)
"""
import datetime as dt, hashlib, json, math, os, random, statistics, subprocess, sys
from collections import defaultdict
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM
import build_game_model as GM
import build_game_script_test as GS
import build_game_script_test_b2 as B2

ROOT = os.path.join(HERE, '..')
FROZEN = os.path.join(ROOT, 'data', 'game_script_frozen.json')
RESULTS = os.path.join(ROOT, 'docs', 'game-script-minutes-b3-results.md')
FIRST_TIP_UTC = '2026-10-20T23:00:00+00:00'
SEED, N_TEST_GAMES = 20261010, 200


def draw_m4(grp, E, rng, P, n, stats=None):
    out = {id(r): [] for r in grp}
    pe = P['pot'][B2.ebin(E)]
    for _ in range(n):
        if rng.random() < pe:
            k = 2 if rng.random() < P['p2'] else 1
            m = P['pool'][int(rng.random() * len(P['pool']))] * (1 if rng.random() < .5 else -1)
            if stats is not None:
                stats[0] += 1
        else:
            k, m = 0, E + P['s_reg'] * rng.gauss(0, 1)
        if stats is not None:
            stats[1] += 1
        z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
        us = P['mods'][True]['shock_sd'] * z1
        ub = P['mods'][False]['shock_sd'] * (P['rho'] * z1 + math.sqrt(1 - P['rho'] ** 2) * z2)
        f = B2.feats(m, k)
        for r in grp:
            M = P['mods'][r['st']]
            out[id(r)].append(B2.clamp(r['base'] + sum(c * x for c, x in zip(M['b'], f)) + (us if r['st'] else ub) + M['noise_sd'] * rng.gauss(0, 1)))
    return out


def kind_of(a, b):
    return 'ss' if a['st'] and b['st'] else 'bb' if not a['st'] and not b['st'] else 'sb'


def calibrate(R, P, iters=4, n=40):
    by = defaultdict(list)
    for r in R:
        by[(r['g'], r['team'])].append(r)
    keys = sorted(by)[::3]
    for it in range(iters):
        rng = random.Random(SEED + it)
        obs = {'ss': [0.0, 0], 'bb': [0.0, 0], 'sb': [0.0, 0]}; sim = {'ss': [0.0, 0], 'bb': [0.0, 0], 'sb': [0.0, 0]}
        for key in keys:
            grp = by[key]; E = grp[0]['E']
            dr = draw_m4(grp, E, rng, P, n)
            mu = {id(r): sum(dr[id(r)]) / n for r in grp}
            for a, b in combinations(grp, 2):
                k = kind_of(a, b)
                obs[k][0] += (a['y'] - mu[id(a)]) * (b['y'] - mu[id(b)]); obs[k][1] += 1
                sim[k][0] += sum((x - mu[id(a)]) * (y - mu[id(b)]) for x, y in zip(dr[id(a)], dr[id(b)])) / n; sim[k][1] += 1
        o = {k: v[0] / v[1] for k, v in obs.items()}; s = {k: v[0] / v[1] for k, v in sim.items()}
        ss_, sb_ = P['mods'][True]['shock_sd'], P['mods'][False]['shock_sd']
        var_s = ss_ ** 2 * (o['ss'] / s['ss']) if s['ss'] > 0 and o['ss'] > 0 else ss_ ** 2
        var_b = sb_ ** 2 * (o['bb'] / s['bb']) if s['bb'] > 0 and o['bb'] > 0 else sb_ ** 2
        rho = P['rho']
        if ss_ > 0 and sb_ > 0:
            rho = max(-0.9, min(0.0, rho + (o['sb'] - s['sb']) / (ss_ * sb_)))
        P['rho'] = rho
        for role, v in ((True, var_s), (False, var_b)):
            P['mods'][role]['shock_sd'] = math.sqrt(max(0.0, v))
            P['mods'][role]['noise_sd'] = math.sqrt(max(0.25, P['mods'][role]['var'] - max(0.0, v)))
    return P


def expected_margins_for(box, seasons):
    Pm = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params']) if os.path.exists(GM.OUT_JSON) else GM.DEFAULT
    _, recs = GM.run(Pm, seasons, box, record_from=seasons[0])
    return {r['g']['game_id']: r['none'][0] for r in recs}


def rows(seasons, record_from):
    box = C.player_games(seasons)
    lines = expected_margins_for(box, seasons)
    R = GS.rows_for(box, lines, seasons, record_from)
    B2.add_ot(R, box)
    return R


def m3_part(R):
    m3, sdm = GS.fit_models(R)
    return {('s' if k else 'b'): {'b1': v['b1'], 'sd1': v['sd1'], 'b0': v['b0']} for k, v in m3.items()}, m3, sdm


def frozen_blob(R, P, seasons):
    part, _, _ = m3_part(R)
    blob = {'rules': 'docs/game-script-minutes-b3.md', 'fit_seasons': seasons, 'rows': len(R), 'games': len({r['g'] for r in R}),
            'pot': P['pot'], 'p2': P['p2'], 'pool': [round(x, 1) for x in P['pool']], 's_reg': P['s_reg'], 'rho': P['rho'],
            'mods': {('s' if k else 'b'): {kk: ([float(x) for x in vv] if isinstance(vv, list) else float(vv)) for kk, vv in v.items()} for k, v in P['mods'].items()},
            'm1': part}
    blob['fingerprint'] = hashlib.sha256(json.dumps({k: blob[k] for k in ('pot', 'p2', 'pool', 's_reg', 'rho', 'mods')}, sort_keys=True).encode()).hexdigest()
    return blob


def load_frozen():
    b = json.load(open(FROZEN))
    P = {'pot': b['pot'], 'p2': b['p2'], 'pool': b['pool'], 's_reg': b['s_reg'], 'rho': b['rho'], 'mods': {k == 's': v for k, v in b['mods'].items()}}
    m3 = {k == 's': {'b1': v['b1'], 'sd1': v['sd1'], 'b0': v['b0']} for k, v in b['m1'].items()}
    return P, m3, b


def verdict_rows(a, b0, ot_obs, n_tg):
    c = a['corr']
    inside = {k: c[k]['obs'] - 1.96 * c[k]['obs_se'] <= c[k]['sim'] <= c[k]['obs'] + 1.96 * c[k]['obs_se'] for k in c}
    zero_out = c['ss']['obs'] - 1.96 * c['ss']['obs_se'] > 0 or c['ss']['obs'] + 1.96 * c['ss']['obs_se'] < 0
    se = math.sqrt(ot_obs * (1 - ot_obs) / max(1, n_tg))
    g1 = 0.76 <= a['cov'] <= 0.84 and abs(a['pit'] - 0.5) <= 0.02 and abs(a['cov'] - 0.8) <= abs(b0['cov'] - 0.8) + 0.01
    g2 = all(inside.values()) and zero_out
    g3 = abs(a['mae'] - a['mae_m1']) <= 0.05
    g4 = abs(a['ot_sim'] - ot_obs) <= 0.015 or abs(a['ot_sim'] - ot_obs) <= 1.96 * se
    return g1, g2, g3, g4, inside, zero_out


def report_md(title, a, b0, m3res, ot_obs, n_tg, fit_n, test_n, note):
    g1, g2, g3, g4, inside, zero_out = verdict_rows(a, b0, ot_obs, n_tg)
    c = a['corr']
    L = [f'## {title}', '', note, '', f'- Fit rows {fit_n:,}; scored rows {test_n:,}; team-games {n_tg:,}; overtime share observed {ot_obs * 100:.1f}%.', '',
         '| Check | Rule | M4 with clamp calibration | M4 uncalibrated (B2) | B0 independent | Pass |', '|---|---|---|---|---|---|',
         f"| Starters 80% coverage | 76% to 84% | {a['cov'] * 100:.1f}% |  | {b0['cov'] * 100:.1f}% | {'yes' if g1 else 'NO'} (with rank rule) |",
         f"| Starters mean rank of actual | 0.50 +/- 0.02 | {a['pit']:.3f} |  | {b0['pit']:.3f} |  |"]
    for kind, lab in (('ss', 'starters with starters'), ('bb', 'bench with bench'), ('sb', 'starters with bench')):
        ck = c[kind]
        u = (m3res or {}).get(kind)
        L.append(f"| Togetherness, {lab} | inside observed 95% interval | model {ck['sim']:+.3f}, observed {ck['obs']:+.3f} ({ck['obs'] - 1.96 * ck['obs_se']:+.3f} to {ck['obs'] + 1.96 * ck['obs_se']:+.3f}) | {'' if u is None else f'{u:+.3f}'} | {b0['corr'][kind]['sim']:+.3f} | {'yes' if inside[kind] else 'NO'} |")
    L += [f"| Mean minutes MAE vs M1 | within 0.05 | M4 {a['mae']:.3f}, M1 {a['mae_m1']:.3f} |  | B0 {b0['mae']:.3f} | {'yes' if g3 else 'NO'} |",
          f"| Overtime share | within 1.5 points or the observed interval | simulated {a['ot_sim'] * 100:.1f}% vs observed {ot_obs * 100:.1f}% |  |  | {'yes' if g4 else 'NO'} |",
          f"| Starters with starters interval excludes zero | required | {'yes' if zero_out else 'NO'} |  |  |  |", '',
          f"**{'GO' if g1 and g2 and g3 and g4 else 'NO-GO'}** under the B3 rules (coverage {'ok' if g1 else 'fails'}, togetherness {'ok' if g2 else 'fails'}, mean minutes {'ok' if g3 else 'fails'}, overtime {'ok' if g4 else 'fails'}).", '']
    return '\n'.join(L), (g1 and g2 and g3 and g4)


def selfcheck():
    allr = rows(B2.WARM + B2.FIT + B2.TEST, B2.FIT[0])
    fitR = [r for r in allr if r['season'] in B2.FIT]; testR = [r for r in allr if r['season'] in B2.TEST]
    P = B2.fit_m4(fitR)
    import copy
    P0 = copy.deepcopy(P)
    before = (P['mods'][True]['shock_sd'], P['mods'][False]['shock_sd'], P['rho'])
    P = calibrate(fitR, P)
    after = (P['mods'][True]['shock_sd'], P['mods'][False]['shock_sd'], P['rho'])
    part, m3, sdm3 = m3_part(fitR)
    mk = lambda PP: (lambda grp, E, rng, stats: draw_m4(grp, E, rng, PP, B2.S, stats))
    ra = B2.evaluate(testR, mk(P), SEED, m3); ru = B2.evaluate(testR, mk(P0), SEED, m3)
    rb = B2.evaluate(testR, B2.make_models(fitR, P, m3, sdm3)['B0'], SEED + 1, m3)
    tg = {(r['g'], r['team']): r['k'] for r in testR}; ot_obs = sum(1 for k in tg.values() if k > 0) / len(tg)
    txt, ok = report_md('Development check: fit 2022-23 and 2023-24, score 2024-25 (informational, not a test)', ra, rb, {k: ru['corr'][k]['sim'] for k in ru['corr']}, ot_obs, len(tg), len(fitR), len(testR),
                        f"Shock sd starters {before[0]:.2f} to {after[0]:.2f} min, bench {before[1]:.2f} to {after[1]:.2f} min, starter-bench correlation {before[2]:+.2f} to {after[2]:+.2f} after the clamp calibration. 2024-25 was already used to find the bench miss, so this is a sanity check on the calibration, not a test; the freeze does not depend on it.")
    open(RESULTS, 'w').write('# Game Simulation v2, step B3: results\n\nRules: docs/game-script-minutes-b3.md.\n\n' + txt + '\n')
    print(txt)


def freeze():
    seasons = B2.WARM + [2023, 2024, 2025, 2026]
    allr = rows(seasons, 2023)
    P = B2.fit_m4(allr)
    P = calibrate(allr, P)
    blob = frozen_blob(allr, P, [2023, 2024, 2025, 2026])
    json.dump(blob, open(FROZEN, 'w'), indent=1)
    print('frozen', blob['rows'], 'rows', blob['games'], 'games; fingerprint', blob['fingerprint'][:16])
    print('shock sd starters %.2f bench %.2f rho %+.2f' % (P['mods'][True]['shock_sd'], P['mods'][False]['shock_sd'], P['rho']))


def check():
    rel = 'nba/data/game_script_frozen.json'
    repo = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--', rel], capture_output=True, text=True, cwd=repo).stdout.strip()
    ts = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', rel], capture_output=True, text=True, cwd=repo).stdout.strip()
    if not ts or dirty:
        print('FAIL: the frozen file is not committed unchanged'); return False
    ok = int(ts) < dt.datetime.fromisoformat(FIRST_TIP_UTC).timestamp()
    print(('OK' if ok else 'FAIL') + f': last commit of {rel} at {dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).isoformat()}, first tip {FIRST_TIP_UTC}')
    return ok


def test():
    if not check():
        sys.exit('refusing to run: the freeze check failed')
    P, m1, blob = load_frozen()
    seasons = B2.WARM + [2023, 2024, 2025, 2026, 2027]
    try:
        allr = rows(seasons, 2027)
    except FileNotFoundError as e:
        sys.exit(f'no 2026-27 box scores yet ({e.filename}); run nba/scripts/fetch_hoopr.py after games have been played')
    allr.sort(key=lambda r: r['g'])
    gids = sorted({r['g'] for r in allr if not r['po']})
    if len(gids) < N_TEST_GAMES:
        sys.exit(f'only {len(gids)} regular-season games with box scores so far; the rules need {N_TEST_GAMES}')
    keep = set(gids[:N_TEST_GAMES])
    testR = [r for r in allr if r['g'] in keep and not r['po']]
    mk = lambda PP: (lambda grp, E, rng, stats: draw_m4(grp, E, rng, PP, B2.S, stats))
    ra = B2.evaluate(testR, mk(P), SEED, m1)
    fitr = None
    # B0 needs M1's pre-game term and sd per role, stored in the freeze
    def d_b0(grp, E, rng, stats):
        out = {}
        for r in grp:
            M = m1[r['st']]
            mu = B2.clamp(r['base'] + sum(c * x for c, x in zip(M['b1'], GS.m1x(E))))
            out[id(r)] = [B2.clamp(mu + M['sd1'] * rng.gauss(0, 1)) for _ in range(B2.S)]
        return out
    rb = B2.evaluate(testR, d_b0, SEED + 1, m1)
    tg = {(r['g'], r['team']): r['k'] for r in testR}; ot_obs = sum(1 for k in tg.values() if k > 0) / len(tg)
    txt, ok = report_md(f'2026-27 holdout: the first {N_TEST_GAMES} regular-season games (frozen model, fingerprint {blob["fingerprint"][:12]})', ra, rb, None, ot_obs, len(tg), blob['rows'], len(testR),
                        'Scored once, as docs/game-script-minutes-b3.md says. The frozen constants were not changed.')
    with open(RESULTS, 'a') as f:
        f.write('\n' + txt + '\n')
    print(txt)


if __name__ == '__main__':
    if '--selfcheck' in sys.argv:
        selfcheck()
    elif '--freeze' in sys.argv:
        freeze()
    elif '--check' in sys.argv:
        sys.exit(0 if check() else 1)
    elif '--test' in sys.argv:
        test()
    else:
        sys.exit(__doc__)
