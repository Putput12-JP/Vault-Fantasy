#!/usr/bin/env python3
"""
Game Simulation v2, step B2: overtime and a shared team minutes shock. The pre-registered test in docs/game-script-minutes-b2.md.

Fit on 2022-23 and 2023-24 (warm-up 2021-22), score on 2024-25. M4 = margin + overtime + a starter/bench team shock + noise;
M3 = step B's margin-only draw (refit on the same seasons); B0 = today's independent draw.
  python3 nba/scripts/build_game_script_test_b2.py
Writes nba/data/game_script_minutes_b2.json and nba/docs/game-script-minutes-b2-results.md
"""
import json, math, os, random, statistics, sys
from collections import defaultdict
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM
import build_game_script_test as GS

ROOT = os.path.join(HERE, '..')
WARM, FIT, TEST = [2022], [2023, 2024], [2025]
S, SEED = 200, 20261008
EBINS = [(0, 3), (3, 6), (6, 10), (10, 999)]


def feats(m, k):
    return [1.0, max(0, m - 10), max(0, -m - 10), max(0, m - 20), max(0, -m - 20), float(k)]


def ebin(E):
    a = abs(E)
    return next(i for i, (lo, hi) in enumerate(EBINS) if lo <= a < hi)


def clamp(v):
    return 0.0 if v < 0 else 48.0 if v > 48 else v


def add_ot(rows, box):
    tot = defaultdict(float)
    for g, rs in box.items():
        for r in rs:
            if r['played']:
                tot[(g, r['team'])] += r['minutes']
    for r in rows:
        r['k'] = max(0, round((tot[(r['g'], r['team'])] - 240) / 25))


def fit_m4(R):
    # overtime
    tg = {}
    for r in R:
        tg[(r['g'], r['team'])] = (r['E'], r['m'], r['k'])
    n = [0] * len(EBINS); o = [0] * len(EBINS)
    for E, m, k in tg.values():
        b = ebin(E); n[b] += 1; o[b] += 1 if k > 0 else 0
    pot = [o[i] / n[i] if n[i] else 0.0 for i in range(len(EBINS))]
    ots = [k for E, m, k in tg.values() if k > 0]
    p2 = sum(1 for k in ots if k >= 2) / len(ots)
    pool = [abs(m) for E, m, k in tg.values() if k > 0]
    s_reg = statistics.pstdev([m - E for E, m, k in tg.values() if k == 0])
    mods = {}
    for role in (True, False):
        sub = [r for r in R if r['st'] == role]
        y = [r['y'] - r['base'] for r in sub]
        b = MM.ols([feats(r['m'], r['k']) for r in sub], y)
        res = [yy - sum(c * x for c, x in zip(b, feats(r['m'], r['k']))) for yy, r in zip(y, sub)]
        for r, e in zip(sub, res):
            r['res'] = e
        mods[role] = {'b': b, 'var': statistics.pvariance(res)}
    # shocks from within-team cross-products of residuals
    by = defaultdict(list)
    for r in R:
        by[(r['g'], r['team'])].append(r)
    acc = {'ss': [0.0, 0], 'bb': [0.0, 0], 'sb': [0.0, 0]}
    for grp in by.values():
        for a, c in combinations(grp, 2):
            kind = 'ss' if a['st'] and c['st'] else 'bb' if not a['st'] and not c['st'] else 'sb'
            acc[kind][0] += a['res'] * c['res']; acc[kind][1] += 1
    cs = {k: v[0] / v[1] for k, v in acc.items()}
    var_s, var_b = max(0.0, cs['ss']), max(0.0, cs['bb'])
    rho = cs['sb'] / math.sqrt(var_s * var_b) if var_s > 0 and var_b > 0 else 0.0
    rho = max(-0.9, min(0.0, rho))
    for role, v in ((True, var_s), (False, var_b)):
        mods[role]['shock_sd'] = math.sqrt(v)
        mods[role]['noise_sd'] = math.sqrt(max(0.25, mods[role]['var'] - v))
    return {'pot': pot, 'p2': p2, 'pool': pool, 's_reg': s_reg, 'mods': mods, 'rho': rho, 'cross': cs}


def make_models(R, P, m3, sdm3):
    def d_m4(grp, E, rng, stats):
        out = {id(r): [] for r in grp}
        pe = P['pot'][ebin(E)]
        for _ in range(S):
            if rng.random() < pe:
                k = 2 if rng.random() < P['p2'] else 1
                m = P['pool'][int(rng.random() * len(P['pool']))] * (1 if rng.random() < .5 else -1)
                stats[0] += 1
            else:
                k, m = 0, E + P['s_reg'] * rng.gauss(0, 1)
            stats[1] += 1
            z1, z2 = rng.gauss(0, 1), rng.gauss(0, 1)
            us = P['mods'][True]['shock_sd'] * z1
            ub = P['mods'][False]['shock_sd'] * (P['rho'] * z1 + math.sqrt(1 - P['rho'] ** 2) * z2)
            f = feats(m, k)
            for r in grp:
                M = P['mods'][r['st']]
                out[id(r)].append(clamp(r['base'] + sum(c * x for c, x in zip(M['b'], f)) + (us if r['st'] else ub) + M['noise_sd'] * rng.gauss(0, 1)))
        return out

    def d_m3(grp, E, rng, stats):
        out = {id(r): [] for r in grp}
        for _ in range(S):
            m = E + sdm3 * rng.gauss(0, 1)
            for r in grp:
                M = m3[r['st']]
                out[id(r)].append(clamp(r['base'] + sum(c * x for c, x in zip(M['b2'], GS.m2x(m))) + M['sd2'] * rng.gauss(0, 1)))
        return out

    def d_b0(grp, E, rng, stats):
        out = {}
        for r in grp:
            M = m3[r['st']]
            mu = clamp(r['base'] + sum(c * x for c, x in zip(M['b1'], GS.m1x(E))))
            out[id(r)] = [clamp(mu + M['sd1'] * rng.gauss(0, 1)) for _ in range(S)]
        return out
    return {'M4': d_m4, 'M3': d_m3, 'B0': d_b0}


def evaluate(R, drawer, seed, m3):
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in R:
        by[(r['g'], r['team'])].append(r)
    cov = [0, 0]; pit = [0.0, 0]; mae = [0.0, 0]; mae1 = [0.0, 0]; split = {'reg': [0, 0], 'po': [0, 0]}
    stats = [0, 0]
    pair = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))
    ov = {True: [0.0, 0], False: [0.0, 0]}; sv = {True: [0.0, 0], False: [0.0, 0]}
    for (gid, team), grp in by.items():
        E = grp[0]['E']
        dr = drawer(grp, E, rng, stats)
        mu = {id(r): sum(dr[id(r)]) / S for r in grp}
        for r in grp:
            M = m3[r['st']]
            mae[0] += abs(mu[id(r)] - r['y']); mae[1] += 1
            mae1[0] += abs(clamp(r['base'] + sum(c * x for c, x in zip(M['b1'], GS.m1x(E)))) - r['y']); mae1[1] += 1
            ov[r['st']][0] += (r['y'] - mu[id(r)]) ** 2; ov[r['st']][1] += 1
            sv[r['st']][0] += sum((x - mu[id(r)]) ** 2 for x in dr[id(r)]) / S; sv[r['st']][1] += 1
            if r['st']:
                d = sorted(dr[id(r)])
                lo, hi = d[int(.1 * S)], d[int(.9 * S) - 1]
                hit = lo <= r['y'] <= hi
                cov[0] += hit; cov[1] += 1
                below = sum(1 for v in d if v < r['y']); eq = sum(1 for v in d if v == r['y'])
                pit[0] += (below + 0.5 * eq) / S; pit[1] += 1
                k = 'po' if r['po'] else 'reg'
                split[k][0] += hit; split[k][1] += 1
        for a, b in combinations(grp, 2):
            kind = 'ss' if a['st'] and b['st'] else 'bb' if not a['st'] and not b['st'] else 'sb'
            P = pair[kind][gid]
            P[0] += (a['y'] - mu[id(a)]) * (b['y'] - mu[id(b)]); P[1] += 1
            da, db = dr[id(a)], dr[id(b)]
            P[2] += sum((x - mu[id(a)]) * (y - mu[id(b)]) for x, y in zip(da, db)) / S
    o_v = {k: v[0] / v[1] for k, v in ov.items()}; s_v = {k: v[0] / v[1] for k, v in sv.items()}
    corr = {}
    for kind, (ra, rb) in (('ss', (True, True)), ('sb', (True, False)), ('bb', (False, False))):
        gids = sorted(pair[kind])
        on = [pair[kind][g][0] for g in gids]; od = [pair[kind][g][1] * math.sqrt(o_v[ra] * o_v[rb]) for g in gids]
        sn = [pair[kind][g][2] for g in gids]; sd_ = [pair[kind][g][1] * math.sqrt(s_v[ra] * s_v[rb]) for g in gids]
        ro, so = GS.ratio(on, od); rs, _ = GS.ratio(sn, sd_)
        corr[kind] = {'obs': ro, 'obs_se': so, 'sim': rs}
    return {'cov': cov[0] / cov[1], 'pit': pit[0] / pit[1], 'mae': mae[0] / mae[1], 'mae_m1': mae1[0] / mae1[1], 'corr': corr, 'ot_sim': (stats[0] / stats[1]) if stats[1] else None,
            'split': {k: (v[0] / v[1] if v[1] else None) for k, v in split.items()}}


def main():
    box = C.player_games(WARM + FIT + TEST)
    lines = MM.expected_margins(box)
    allr = GS.rows_for(box, lines, WARM + FIT + TEST, FIT[0])
    add_ot(allr, box)
    fitR = [r for r in allr if r['season'] in FIT]
    testR = [r for r in allr if r['season'] in TEST]
    P = fit_m4(fitR)
    m3, sdm3 = GS.fit_models(fitR)
    models = make_models(fitR, P, m3, sdm3)
    res = {name: evaluate(testR, fn, SEED + i, m3) for i, (name, fn) in enumerate(models.items())}
    tg = {(r['g'], r['team']): r['k'] for r in testR}
    ot_obs = sum(1 for k in tg.values() if k > 0) / len(tg)

    a, c = res['M4'], res['M4']['corr']
    g1 = 0.76 <= a['cov'] <= 0.84 and abs(a['pit'] - 0.5) <= 0.02 and abs(a['cov'] - 0.8) <= abs(res['B0']['cov'] - 0.8) + 0.01
    inside = {k: c[k]['obs'] - 1.96 * c[k]['obs_se'] <= c[k]['sim'] <= c[k]['obs'] + 1.96 * c[k]['obs_se'] for k in c}
    g2 = all(inside.values()) and (c['ss']['obs'] - 1.96 * c['ss']['obs_se'] > 0 or c['ss']['obs'] + 1.96 * c['ss']['obs_se'] < 0)
    g3 = abs(a['mae'] - a['mae_m1']) <= 0.05
    g4 = abs(a['ot_sim'] - ot_obs) <= 0.015
    verdict = 'GO' if g1 and g2 and g3 and g4 else 'NO-GO'
    out = {'rules': 'docs/game-script-minutes-b2.md', 'verdict': verdict, 'fit_rows': len(fitR), 'test_rows': len(testR), 'ot_obs': ot_obs,
           'params': {'pot': P['pot'], 'p2': P['p2'], 'ot_pool_n': len(P['pool']), 's_reg': P['s_reg'], 'rho': P['rho'], 'cross': P['cross'],
                      'mods': {('starter' if k else 'bench'): {kk: ([round(x, 4) for x in vv] if isinstance(vv, list) else round(vv, 4)) for kk, vv in v.items()} for k, v in P['mods'].items()}},
           'results': res, 'gates': {'coverage_pit': g1, 'togetherness': g2, 'mean_mae': g3, 'overtime_share': g4, 'corr_inside': inside}}
    json.dump(out, open(os.path.join(ROOT, 'data', 'game_script_minutes_b2.json'), 'w'), indent=1, default=float)

    f = lambda x: 'n/a' if x is None else f'{x:.3f}'
    L = ['# Game Simulation v2, step B2: overtime and a shared team minutes shock, results', '', f"Rules: docs/game-script-minutes-b2.md (committed before the test). Verdict: **{verdict}**.", '',
         f"- Fit 2022-23 and 2023-24: {len(fitR):,} player-games. Test 2024-25: {len(testR):,}. Team-games in overtime on the test season: {ot_obs * 100:.1f}%.", '',
         '| Check | Rule | M4 | M3 (margin only) | B0 (independent) | Pass |', '|---|---|---|---|---|---|',
         f"| Starters: 80% coverage | 76% to 84% | {a['cov'] * 100:.1f}% | {res['M3']['cov'] * 100:.1f}% | {res['B0']['cov'] * 100:.1f}% | {'yes' if 0.76 <= a['cov'] <= 0.84 and abs(a['cov'] - 0.8) <= abs(res['B0']['cov'] - 0.8) + 0.01 else 'NO'} |",
         f"| Starters: mean rank of actual | 0.50 +/- 0.02 | {a['pit']:.3f} | {res['M3']['pit']:.3f} | {res['B0']['pit']:.3f} | {'yes' if abs(a['pit'] - 0.5) <= 0.02 else 'NO'} |"]
    for kind, lab in (('ss', 'starters with starters'), ('bb', 'bench with bench'), ('sb', 'starters with bench')):
        ck = c[kind]
        L.append(f"| Togetherness, {lab} | model inside the observed 95% interval | model {ck['sim']:+.3f}, observed {ck['obs']:+.3f} ({ck['obs'] - 1.96 * ck['obs_se']:+.3f} to {ck['obs'] + 1.96 * ck['obs_se']:+.3f}) | {res['M3']['corr'][kind]['sim']:+.3f} | {res['B0']['corr'][kind]['sim']:+.3f} | {'yes' if inside[kind] else 'NO'} |")
    L += [f"| Mean minutes MAE vs M1 | within 0.05 min | M4 {a['mae']:.3f} vs M1 {a['mae_m1']:.3f} | M3 {res['M3']['mae']:.3f} | B0 {res['B0']['mae']:.3f} | {'yes' if g3 else 'NO'} |",
          f"| Overtime share of team-games | within 1.5 points | simulated {a['ot_sim'] * 100:.1f}% vs observed {ot_obs * 100:.1f}% |  |  | {'yes' if g4 else 'NO'} |",
          f"| Starters with starters interval excludes zero | required | {'yes' if (c['ss']['obs'] - 1.96 * c['ss']['obs_se'] > 0 or c['ss']['obs'] + 1.96 * c['ss']['obs_se'] < 0) else 'NO'} |  |  | {'yes' if g2 else 'NO'} (all three togetherness rows and this) |", '',
          '## Fitted constants (fit seasons)', '',
          f"- Overtime probability by |expected margin| (under 3, 3 to 6, 6 to 10, 10+): {', '.join(f'{p * 100:.1f}%' for p in P['pot'])}; two-overtime share of overtime games {P['p2'] * 100:.1f}%; regulation margin spread {P['s_reg']:.2f}.",
          f"- Team shock: starters sd {P['mods'][True]['shock_sd']:.2f} min, bench sd {P['mods'][False]['shock_sd']:.2f} min, correlation {P['rho']:+.2f}. Cross-products used: starters {P['cross']['ss']:+.2f}, bench {P['cross']['bb']:+.2f}, starters with bench {P['cross']['sb']:+.2f}.", '',
          '| Role | const | winner > 10 | loser > 10 | winner > 20 | loser > 20 | per overtime period | noise sd |', '|---|---|---|---|---|---|---|---|']
    for role, k in (('starter', True), ('bench', False)):
        b = P['mods'][k]['b']
        L.append(f"| {role} | {b[0]:+.2f} | {b[1]:+.3f} | {b[2]:+.3f} | {b[3]:+.3f} | {b[4]:+.3f} | {b[5]:+.2f} | {P['mods'][k]['noise_sd']:.2f} |")
    L += ['', f"Starter coverage by season type (M4): regular season {f(a['split']['reg'])}, play-in and playoffs {f(a['split']['po'])}."]
    open(os.path.join(ROOT, 'docs', 'game-script-minutes-b2-results.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
