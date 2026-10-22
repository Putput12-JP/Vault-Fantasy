#!/usr/bin/env python3
"""CFB model: retune the scale, home field, ridge strength and special teams weight for the CURRENT model (v2 prior + special teams), walk-forward 2022-2025.

K (70), ALPHA (300) and HFA (2.5) were fit for the v1 model and never redone after the v2 prior and the special teams rating. Here the average miss on 2022-2023 picks them
(weeks 4+), and 2024-2025 is read once. No pick record is used to choose anything.

  ALPHA   the in-season ridge strength (higher = ratings move more slowly from the preseason prior); one full walk-forward per value
  K       points per unit of rating gap;  HFA  the flat home field;  W  the special teams weight
  K, HFA and W are searched on a grid for each ALPHA, from the saved rating gap and special teams gap, so they cost no refit.

Run: python3 scripts/cfb_retune_study.py [--dir /tmp/cfbstudy]
"""
import argparse, itertools, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
import cfb_v2_st_study as sts

ALPHAS = (100, 200, 300, 500, 800, 1500)
KS = (50, 60, 70, 80, 90, 100)
HFAS = (1.5, 2.0, 2.5, 3.0, 3.5)
WS = (0.5, 1.0, 1.5)


def v2_walk(tg, gm, fbs, finals):
    tab = {}
    for y in range(2022, 2026):
        t = v2.features(y, finals[y - 1], fbs[y])
        t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0)); tab[y] = t

    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    return st.walk_forward(tg, gm, fbs, prior_fn=prior_fn)


def stats(df, pred, mask):
    s = df[mask & (df.week >= 4).values].copy(); s['p'] = pred[mask & (df.week >= 4).values]
    q = s.dropna(subset=['mkt']); wc, lc = sts.picks(s, 'p', 'mkt'); wo, lo = sts.picks(s, 'p', 'open')
    X = np.c_[np.ones(len(q)), q.mkt, q.p - q.mkt]; b = np.linalg.lstsq(X, q.hm, rcond=None)[0][2]
    lean = ((q.p - q.mkt) * (q.hm - q.mkt) > 0).sum() / max(((q.hm - q.mkt) != 0).sum(), 1)
    return np.abs(q.hm - q.p).mean(), b, (wc, lc), (wo, lo), lean


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); ap.add_argument('--opens', default='/tmp/cfbstudy/opens_hist.json'); a = ap.parse_args()
    tg, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir); YEARS = [2022, 2023, 2024, 2025]
    order = [o for o in sts.game_order(gm, fbs, st.YEARS) if o[0] in YEARS]; hf = np.array([0.0 if o[4] else 1.0 for o in order])
    base_k, base_h = st.K, st.HFA
    runs = {}
    for al in ALPHAS:
        st.ALPHA = al; finals = {}; st.walk_forward(tg, gm, fbs, finals=finals)
        r = v2_walk(tg, gm, fbs, finals); r = r[r.season.isin(YEARS)].reset_index(drop=True)
        runs[al] = ((r.pred.values - base_h * hf) / base_k, r); print('built alpha', al, flush=True)
    r0 = runs[ALPHAS[0]][1]
    df = pd.DataFrame(dict(game_id=[o[1] for o in order], season=r0.season, week=r0.week, hm=r0.hm, mkt=r0.mkt))
    op = json.load(open(a.opens)); df['open'] = df.game_id.map(lambda i: -op[str(i)]['so'] if op.get(str(i)) and op[str(i)]['so'] is not None else np.nan)
    sts.order_weeks = dict(zip(df.game_id, df.week)); stg = sts.st_games(a.dir, YEARS)
    gap = sts.st_walk(order, stg, YEARS, sts.LAM, sts.CARRY); sg = df.game_id.map(gap).fillna(0.0).values
    tune = df.season.isin([2022, 2023]).values; test = ~tune; w4 = (df.week >= 4).values

    def pred(al, k, h, w): return k * runs[al][0] + h * hf + w * sg
    cur = pred(300, base_k, base_h, 1.0)
    print('\\ncurrent settings (alpha 300, K 70, HFA 2.5, W 1.0):')
    for lab, m in (('tune', tune), ('test', test)):
        ms, b, c, o, lean = stats(df, cur, m); print(f'  {lab}: miss {ms:.3f} | weight on edge {b:.2f} | 5+ vs close {c[0]}-{c[1]} | 5+ vs open {o[0]}-{o[1]} | lean {lean * 100:.1f}%')
    res = []
    for al, k, h, w in itertools.product(ALPHAS, KS, HFAS, WS):
        res.append((np.abs((df.hm - pred(al, k, h, w))[tune & w4]).mean(), al, k, h, w))
    res.sort(); print('\\nbest 5 on 2022-23 by miss:'); [print('  miss %.3f  alpha %d  K %d  HFA %.1f  W %.1f' % r) for r in res[:5]]
    print('alpha alone (K, HFA, W at their best for that alpha), tune miss:', {al: round(min(r for r in res if r[1] == al)[0], 3) for al in ALPHAS})
    _, al, k, h, w = res[0]; new = pred(al, k, h, w)
    print(f'\\nchosen on 2022-23: alpha {al}, K {k}, HFA {h}, W {w}')
    for lab, m in (('tune 2022-23', tune), ('TEST 2024-25 (read once)', test)):
        for name, p in (('current', cur), ('retuned', new)):
            ms, b, c, o, lean = stats(df, p, m)
            print(f'  {lab:24s} {name:8s} miss {ms:.3f} | weight on edge {b:.2f} | 5+ vs close {c[0]}-{c[1]} ({c[0] / max(sum(c), 1) * 100:.1f}%) | 5+ vs open {o[0]}-{o[1]} ({o[0] / max(sum(o), 1) * 100:.1f}%) | lean {lean * 100:.1f}%')
    df['current'] = cur; df['retuned'] = new; df.to_csv(os.path.join(a.dir, 'retune_rows.csv'), index=False)
    json.dump(dict(alpha=al, K=k, HFA=h, W=w), open(os.path.join(a.dir, 'retune_params.json'), 'w'))


if __name__ == '__main__':
    main()
