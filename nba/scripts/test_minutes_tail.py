#!/usr/bin/env python3
"""Left-tail (quantile) minutes. Rule: docs/minutes-left-tail.md (committed before this ran). Nothing here changes pricing.
  python3 nba/scripts/test_minutes_tail.py     needs lightgbm, numpy, scipy; reads /tmp/rotation_pool.json"""
import json, math, os, statistics as st, sys
from collections import defaultdict
import numpy as np
from scipy.stats import nbinom
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_minutes_spread as SP
import test_rotation_minutes as TR
import test_minutes_bakeoff as B

LV = [round(0.05 * i, 2) for i in range(1, 20)]; STATS = B.STATS
PHI = [round(0.02 * i + 0.01, 2) for i in range(30)]

def ct(rows, f):
    g = defaultdict(list)
    for r in rows: g[r['gid']].append(f(r))
    m = [st.mean(v) for v in g.values()]
    return st.mean(m), (st.mean(m) / (st.stdev(m) / math.sqrt(len(m))) if len(m) > 2 and st.stdev(m) > 0 else 0.0), len(m)

def nb_p(mu, phi, k):          # P(Y <= k), mu array (...), k array broadcastable
    r = 1.0 / phi; return nbinom.cdf(k, r, r / (r + np.maximum(mu, 1e-6)))

def nb_pmf(mu, phi, y):
    r = 1.0 / phi; return nbinom.pmf(y, r, r / (r + np.maximum(mu, 1e-6)))

def main():
    import lightgbm as lgb
    P = json.load(open(B.CACHE)); recs = P['recs']; pool = TR.add_history(P['pool']); B.gbm_features(pool)
    model = json.load(open(os.path.join(HERE, '..', 'data', 'rotation_minutes_model.json')))
    B.fit_predict(pool); te = [r for r in pool if r['season'] == B.TEST]; B.score(te, model)
    tr = [r for r in pool if r['season'] in B.TRAIN and r['played'] and r['min'] > 0 and r['gx'] is not None and r['gn'] >= 5]
    kw = dict(SP.MEAN_KW); kw['n_estimators'] = 150
    X = [r['gx'] for r in tr]; y = [r['min'] for r in tr]
    okt = [r for r in te if r['gx'] is not None]
    preds = np.column_stack([lgb.LGBMRegressor(objective='quantile', alpha=a, **kw).fit(X, y).predict([r['gx'] for r in okt]) for a in LV])
    for r, q in zip(okt, preds): r['_q'] = np.sort(q)
    pl = [r for r in te if r['played'] and r['min'] > 0 and 'GP' in r]
    fit = [r for r in pl if r['gid'] % 2 == 0]; hold = [r for r in pl if r['gid'] % 2 == 1]
    qe = np.quantile([r['min'] - r['GP'] for r in fit], LV)
    for r in pl:
        r['QB'] = np.clip(r['GP'] + qe, 0, 48)                                           # point baseline distribution
        r['QT'] = np.clip(r['_q'] * (r['GP'] / r['G'] if r['G'] > 0 else 1.0), 0, 48) if '_q' in r else r['QB']
    res = {'fit_rows': len(fit), 'holdout_rows': len(hold), 'holdout_games': len({r['gid'] for r in hold}), 'train_rows': len(tr), 'with_tail_model': sum('_q' in r for r in hold)}
    # 1 calibration, 3 early exit, 5 mean preserved
    cov = {a: float(np.mean([r['min'] < r['QT'][LV.index(a)] for r in hold])) for a in (0.1, 0.25, 0.5, 0.75, 0.9)}
    covb = {a: float(np.mean([r['min'] < r['QB'][LV.index(a)] for r in hold])) for a in (0.1, 0.25, 0.5, 0.75, 0.9)}
    res['coverage_tail'], res['coverage_point'] = cov, covb
    res['early'] = {'pred_tail': float(np.mean([np.mean(r['QT'] < 0.4 * r['GP']) for r in hold])), 'pred_point': float(np.mean([np.mean(r['QB'] < 0.4 * r['GP']) for r in hold])),
                    'actual': float(np.mean([r['min'] < 0.4 * r['GP'] for r in hold]))}
    res['mean_err_tail'] = float(np.mean([r['QT'].mean() - r['min'] for r in hold])); res['mean_err_point'] = float(np.mean([r['QB'].mean() - r['min'] for r in hold]))
    # 2 pinball
    lv = np.array(LV); pin = lambda q, m: float(np.mean(np.maximum(lv * (m - q), (lv - 1) * (m - q))))
    for r in hold: r['pinB'], r['pinT'] = pin(r['QB'], r['min']), pin(r['QT'], r['min'])
    d, t, n = ct(hold, lambda r: r['pinB'] - r['pinT'])
    res['pinball'] = {'point': st.mean(r['pinB'] for r in hold), 'tail': st.mean(r['pinT'] for r in hold), 'gain': d, 't': t, 'games': n}
    # 4 props
    rec = {(x['gid'], x['aid']): x for x in recs}
    def stat_arrays(rows):
        out = {}
        for s in STATS:
            sel = [(r, rec[(r['gid'], r['aid'])]) for r in rows if (r['gid'], r['aid']) in rec and r['pm'] > 0]
            out[s] = ([a for a, _ in sel], np.array([b['mu'][s] / a['pm'] for a, b in sel]), np.array([b['y'][s] for a, b in sel]))
        return out
    fa, ha = stat_arrays(fit), stat_arrays(hold)
    ll, per_row, phis = {}, defaultdict(lambda: defaultdict(list)), {}
    for s in STATS:
        for k, key in (('point', 'GP'), ('tail', 'QT')):
            rows, rate, yy = fa[s]
            M = np.array([[r['GP']] if k == 'point' else r['QT'] for r in rows])
            best = max(PHI, key=lambda p: np.log(np.maximum(nb_pmf(rate[:, None] * M, p, yy[:, None]).mean(1), 1e-12)).sum())
            phis[(s, k)] = best
            rows, rate, yy = ha[s]
            M = np.array([[r['GP']] if k == 'point' else r['QT'] for r in rows]); losses = []
            base = np.floor(rate * np.array([r['GP'] for r in rows]))
            for off in (-1, 0, 1):
                L = base + off + 0.5; ok = L > 0
                p_over = 1 - nb_p(rate[:, None] * M, best, np.floor(L)[:, None]).mean(1); p_over = np.clip(p_over, 1e-4, 1 - 1e-4)
                o = (yy > L).astype(float); l = -(o * np.log(p_over) + (1 - o) * np.log(1 - p_over))
                for r, v, z in zip(rows, l, ok):
                    if z: per_row[(r['gid'], r['aid'], s, off)][k] = v
                losses.append(l[ok])
            ll[(s, k)] = float(np.concatenate(losses).mean())
    res['phi'] = {'%s_%s' % k: v for k, v in phis.items()}
    res['logloss'] = {s: {'point': ll[(s, 'point')], 'tail': ll[(s, 'tail')]} for s in STATS}
    keyrow = {(r['gid'], r['aid']): r for r in hold}; byrow = defaultdict(list)
    for (g, a, s, off), d_ in per_row.items():
        if 'point' in d_ and 'tail' in d_: byrow[(g, a)].append(d_['point'] - d_['tail'])
    rr = [{'gid': g, 'v': st.mean(v), 'r': keyrow[(g, a)]} for (g, a), v in byrow.items()]
    d, t, n = ct(rr, lambda z: z['v'])
    res['logloss_all'] = {'point': st.mean(ll[(s, 'point')] for s in STATS), 'tail': st.mean(ll[(s, 'tail')] for s in STATS), 'gain': d, 't': t, 'games': n}
    for name, f in (('top5', lambda z: z['r']['rank'] <= 5), ('rank_6_plus', lambda z: z['r']['rank'] > 5), ('early_exit_rows', lambda z: z['r']['min'] < 0.4 * z['r']['GP'])):
        sub = [z for z in rr if f(z)]; res.setdefault('context', {})[name] = {'rows': len(sub), 'logloss_gain_point_minus_tail': st.mean(z['v'] for z in sub) if sub else None}
    ru = {'1': all(abs(cov[a] - a) <= 0.02 for a in cov), '2': res['pinball']['gain'] > 0 and res['pinball']['t'] >= 3,
          '3': abs(res['early']['pred_tail'] - res['early']['actual']) <= 0.015,
          '4': res['logloss_all']['gain'] > 0 and res['logloss_all']['t'] >= 3 and all(res['logloss'][s]['tail'] <= res['logloss'][s]['point'] for s in STATS),
          '5': abs(res['mean_err_tail']) <= 0.5}
    ru['ALL'] = all(ru.values()); res['rule'] = ru
    json.dump(res, open(os.path.join(HERE, '..', 'data', 'minutes_tail.json'), 'w'), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
main()
