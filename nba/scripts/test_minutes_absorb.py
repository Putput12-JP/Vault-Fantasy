#!/usr/bin/env python3
"""Teammate-out absorption (replacement graph). Rule: docs/minutes-absorb.md (committed before this ran). Nothing here changes pricing.
  python3 nba/scripts/test_minutes_absorb.py     needs lightgbm + numpy; reads /tmp/rotation_pool.json"""
import json, math, os, statistics as st, sys
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM
import build_minutes_spread as SP
import minutes_gbm as MG
import rotation_minutes as RM
import test_rotation_minutes as TR
import test_minutes_bakeoff as B

K, MIN_PAIR, CAP, RIDGE = 10.0, 8, 20.0, 1.0
STATS = B.STATS

def bucket(rk): return 0 if rk <= 5 else (1 if rk <= 8 else 2)

def walk(pool):
    """B.gbm_features plus, per row: outs = [(aid, ewma, pos, rank bucket)], ym (his ewma), yb (his rank bucket), ypos."""
    box = C.player_games(B.SEASONS); by = defaultdict(list)
    for r in pool: by[(r['gid'], r['team'])].append(r)
    pl, tips = {}, defaultdict(list)
    for g in C.games(B.SEASONS):
        recs = box.get(g['game_id'], [])
        if not recs: continue
        tip = g['tip'].timestamp()
        for team, home in ((g['home'], 1), (g['away'], 0)):
            rows = by.get((int(g['game_id']), team))
            if not rows: continue
            ids = {r['aid'] for r in rows}; rot = MG.rotation(pl, team, tip); out = {a for a in rot if a not in ids}
            order = sorted(rot, key=lambda a: -rot[a]['ew'][1]); rk = {a: i + 1 for i, a in enumerate(order)}
            ctx = MG.team_context(tips[team], tip)
            for r in rows:
                p = pl.get(r['aid'])
                r['gx'], r['gn'] = (MG.features(p, r['aid'], rot, out, tip, ctx, home, r['e'], p['pos']), p['n']) if p else (None, 0)
                r['outs'] = [(a, rot[a]['ew'][1], rot[a]['pos'], bucket(rk[a])) for a in out]
                r['ym'], r['ypos'], r['yb'] = (p['ew'][1], p['pos'], bucket(rk.get(r['aid'], 99))) if p else (None, None, 2)
        for r in recs:
            if not r['played']: continue
            p = pl.get(r['athlete_id'])
            if p is None: pl[r['athlete_id']] = MG.new_player(r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
            else: MG.update_player(p, r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
        for t in (g['home'], g['away']):
            tips[t].append(tip); del tips[t][:-12]

def cell(xb, yb, same): return (xb * 3 + yb) * 2 + (1 if same else 0)

def role_x(r):
    x = np.zeros(18)
    for a, e, pos, xb in r['outs']: x[cell(xb, r['yb'], pos == r['ypos'])] += e
    return x

def fit_weights(rows):
    """rows: training rows (played, ym known, outs non-empty). -> (role weights, pair delta dict)."""
    X = np.array([role_x(r) for r in rows]); y = np.array([r['min'] - r['ym'] for r in rows])
    w = np.linalg.solve(X.T @ X + RIDGE * 1e3 * np.eye(18) * 0 + RIDGE * np.eye(18), X.T @ y)
    resid = y - X @ w; acc = defaultdict(lambda: [0, 0.0])
    for r, e in zip(rows, resid):
        for a, ex, _, _ in r['outs']:
            if ex <= 0: continue
            k = (a, r['aid']); acc[k][0] += 1; acc[k][1] += e / (ex * len(r['outs']))      # residual shared across the outs, per X-minute
    return w, {k: s / (n + K) for k, (n, s) in acc.items() if n >= MIN_PAIR}

def absorb(r, w, pairs):
    tot = 0.0
    for a, e, pos, xb in r['outs']:
        tot += e * (w[cell(xb, r['yb'], pos == r['ypos'])] + pairs.get((a, r['aid']), 0.0))
    return max(-CAP, min(CAP, tot))

def main():
    import lightgbm as lgb
    pool = json.load(open(B.CACHE)); recs = pool['recs']; pool = TR.add_history(pool['pool']); walk(pool)
    model = json.load(open(os.path.join(HERE, '..', 'data', 'rotation_minutes_model.json')))
    ok = lambda r: r['played'] and r['min'] > 0 and r['gx'] is not None and r['gn'] >= 5 and r['ym'] is not None
    tr = [r for r in pool if r['season'] in B.TRAIN and ok(r)]
    te = [r for r in pool if r['season'] == B.TEST]
    # absorb: train rows use weights from the OTHER training seasons; test rows use all training seasons
    info = {}
    for s in B.TRAIN + (None,):
        fit_rows = [r for r in tr if r['outs'] and r['season'] != s]
        w, pairs = fit_weights(fit_rows)
        tgt = [r for r in (tr if s else te) if (s is None or r['season'] == s) and r.get('gx') is not None and r.get('ym') is not None]
        for r in tgt: r['ab'] = absorb(r, w, pairs)
        info[str(s)] = {'fit_rows': len(fit_rows), 'pairs': len(pairs)}
        if s is None: wfull, pfull = w, pairs
    for r in te: r.setdefault('ab', 0.0)
    gb0 = lgb.LGBMRegressor(**SP.MEAN_KW).fit([r['gx'] for r in tr], [r['min'] for r in tr])
    gb1 = lgb.LGBMRegressor(**SP.MEAN_KW).fit([r['gx'] + [r['ab']] for r in tr], [r['min'] for r in tr])
    okt = [r for r in te if r['gx'] is not None and r['ym'] is not None]
    for r, v0, v1 in zip(okt, gb0.predict([r['gx'] for r in okt]), gb1.predict([r['gx'] + [r['ab']] for r in okt])):
        r['G'], r['Ga'] = max(0., min(48., float(v0))), max(0., min(48., float(v1)))
    for r in te: r.setdefault('G', r['pm']); r.setdefault('Ga', r['G'])
    groups = B.score(te, model)
    for rs in groups.values():
        for r, v in zip(rs, RM.rescale([(r['p'], r['Ga']) for r in rs], model['T'])): r['GPA'] = v
    pl = [r for r in te if r['played'] and r['min'] > 0 and 'GPA' in r]
    o1 = [r for r in pl if r['outs']]; o0 = [r for r in pl if not r['outs']]
    mae = lambda rows, k: st.mean(abs(r[k] - r['min']) for r in rows)
    bias = lambda rows, k: st.mean(r[k] - r['min'] for r in rows)
    m8 = lambda rows, k: sum(abs(r[k] - r['min']) >= 8 for r in rows)
    res = {'info': info, 'test_played': len(pl), 'with_out': len(o1), 'no_out': len(o0)}
    d, t, n = B.cluster_t(o1, lambda r: abs(r['GP'] - r['min']) - abs(r['GPA'] - r['min']))
    res['r1'] = {'mae_GP': mae(o1, 'GP'), 'mae_GPA': mae(o1, 'GPA'), 'gain': d, 't': t, 'games': n}
    res['r2'] = {'bias_GP': bias(o1, 'GP'), 'bias_GPA': bias(o1, 'GPA'), 'miss8_GP': m8(o1, 'GP'), 'miss8_GPA': m8(o1, 'GPA')}
    res['r3'] = {'mae_GP_noout': mae(o0, 'GP'), 'mae_GPA_noout': mae(o0, 'GPA'), 'miss8_all_GP': m8(pl, 'GP'), 'miss8_all_GPA': m8(pl, 'GPA')}
    b = {}
    for name, f in (('size_le_12', lambda z: z <= 12), ('size_13_14', lambda z: 13 <= z <= 14), ('size_ge_15', lambda z: z >= 15)):
        sel = [r for r in pl if r['rank'] <= 8 and f(r['size'])]; b[name] = {'n': len(sel), 'GP': bias(sel, 'GP'), 'GPA': bias(sel, 'GPA')}
    res['r4'] = b
    rmap = {(r['gid'], r['aid']): r for r in pl}; pr = {s: {'GP': [], 'GPA': []} for s in STATS}
    for x in recs:
        r = rmap.get((x['gid'], x['aid']))
        if not r or r['pm'] <= 0: continue
        for s in STATS:
            for k in ('GP', 'GPA'): pr[s][k].append(abs(x['mu'][s] * r[k] / r['pm'] - x['y'][s]))
    res['r5'] = {s: {k: st.mean(v) for k, v in d_.items()} for s, d_ in pr.items()}
    res['r6'] = {k: st.mean(abs(r['p'] * r[k] - (r['min'] if r['played'] else 0.)) for r in te if 'GPA' in r) for k in ('GP', 'GPA')}
    for nn, lo, hi in (('1', 1, 1), ('2', 2, 2), ('3+', 3, 99)):
        sel = [r for r in o1 if lo <= len(r['outs']) <= hi]
        res.setdefault('by_n_out', {})[nn] = {'n': len(sel), 'mae_GP': mae(sel, 'GP'), 'mae_GPA': mae(sel, 'GPA'), 'bias_GP': bias(sel, 'GP'), 'bias_GPA': bias(sel, 'GPA')}
    lab = lambda i: ('X rank %s, Y rank %s, %s' % (['1-5', '6-8', '9+'][i // 6], ['1-5', '6-8', '9+'][(i // 2) % 3], 'same pos' if i % 2 else 'other pos'))
    res['role_weights'] = {lab(i): round(float(wfull[i]), 3) for i in range(18)}
    res['pair_weights_n'] = len(pfull)
    res['rule'] = {'1': res['r1']['gain'] > 0 and res['r1']['t'] >= 3, '2': abs(res['r2']['bias_GPA']) < abs(res['r2']['bias_GP']) and res['r2']['miss8_GPA'] < res['r2']['miss8_GP'],
                   '3': res['r3']['mae_GPA_noout'] - res['r3']['mae_GP_noout'] <= 0.02 and res['r3']['miss8_all_GPA'] <= res['r3']['miss8_all_GP'],
                   '4': all(v['n'] < 500 or abs(v['GPA']) <= 0.5 for v in b.values()) and all(abs(v['GPA']) - abs(v['GP']) <= 0.1 for v in b.values()),
                   '5': all(res['r5'][s]['GPA'] <= res['r5'][s]['GP'] for s in STATS), '6': res['r6']['GPA'] <= res['r6']['GP']}
    res['rule']['ALL'] = all(res['rule'].values())
    json.dump(res, open(os.path.join(HERE, '..', 'data', 'minutes_absorb.json'), 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
main()
