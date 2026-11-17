#!/usr/bin/env python3
"""CFB week 7 retro, round 7b: put the market's preseason win totals into the live prior and see what it does to the model's miss and picks.

Round 7 (cfb_week7_wintotals_study.py) found a win total explains final-season strength better than the live v2 prior alone (holding out each season, RMSE 4.51 to 3.19 points against the final market
strength, 6.58 to 5.68 against the model's own final EPA rating, every held-out season). That is a statement about the prior, not about picks, so this tests the model: the live model with its prior
shifted by BETA points per win above the season's mean total, for the teams the source lists (offense and defense each take half). BETA is fixed in advance at 2.0, the weight the EPA-target fit gave in the
three held-out seasons (1.94, 2.30, 2.02); it is not tuned here. Teams a source does not list keep the live prior unchanged. Judged only on games where BOTH teams are listed, weeks 4+, seasons 2023-2025
(2022 has no earlier season to fit the live prior on): average miss against the live model and the close, and 5+ point underdog-side picks at the live rule's count against the close and the open.
Run: python3 scripts/cfb_week7_wintotals_prior_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
import cfb_model as cm
from cfb_week7_study import rec, fmt

K, ALL, YEARS = st.K, [2021, 2022, 2023, 2024, 2025, 2026], [2022, 2023, 2024, 2025, 2026]
BETA = 2.0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); fbs[2026] = {t['id'] for t in json.load(open(os.path.join(cm.DATA, 'cfbd', 'teams_fbs_2026.json')))}
    finals = {}; st.walk_forward(tg, gm, fbs, years=ALL, finals=finals)
    tab = {}
    for y in YEARS:
        t = v2.features(y, finals[y - 1], fbs[y])
        if y < 2026: t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0))
        tab[y] = t
    wts = {}
    for y in YEARS:
        p = os.path.join(cm.DATA, 'win_totals', f'win_totals_{y}.json')
        if os.path.exists(p):
            w = json.load(open(p))['teams']; m = np.mean([v['total'] for v in w.values()]); wts[y] = {int(t): v['total'] - m for t, v in w.items()}
    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]; pa, pb = dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd))
        for t, c in (wts.get(y) or {}).items():
            if t in pa: pa[t] += BETA * c / (2 * K); pb[t] -= BETA * c / (2 * K)
        return (pa, pb)
    r = st.walk_forward(tg, gm, fbs, years=ALL, prior_fn=prior_fn); r = r[r.season.isin(YEARS)].reset_index(drop=True)
    assert len(r) == len(d) and (r.hm.values == d.hm.values).all()
    d['wtp'] = r.pred.values + d.gap.values
    listed = lambda row: row.season in wts and row.home_id in wts[row.season] and row.away_id in wts[row.season]
    d['both'] = [listed(x) for x in d.itertuples()]
    q = d[(d.week >= 4) & d.both & (d.season >= 2023)].dropna(subset=['mkt']).copy(); q.to_csv(os.path.join(a.dir, 'wintotals_prior_rows.csv'), index=False)
    print('games with both teams listed, weeks 4+: %s' % q.groupby('season').size().to_dict())
    groups = (('2023', q.season == 2023), ('2024', q.season == 2024), ('2025', q.season == 2025), ('2026 (25 teams listed)', q.season == 2026), ('2023-25', q.season.isin([2023, 2024, 2025])))
    for lab, m in groups:
        s = q[m]
        if not len(s): continue
        print('\n== %s (%d games) | close miss %.3f' % (lab, len(s), (s.hm - s.mkt).abs().mean()))
        for k in ('v2st', 'wtp'):
            x = np.c_[np.ones(len(s)), s.mkt, s[k] - s.mkt]; w = np.linalg.lstsq(x, s.hm, rcond=None)[0][2]
            print('  %-5s miss %.3f | weight on edge vs close %.3f | sd of edge %.2f' % (k, (s.hm - s[k]).abs().mean(), w, (s[k] - s.mkt).std()))
        for ln in ('mkt', 'open'):
            z = s.dropna(subset=[ln]); e0 = z.v2st - z[ln]; n = int(sum(cm.pick_ok(x, w_, mm) for x, w_, mm in zip(e0, z.week, z[ln]))); c = z.hm - z[ln]; row = []
            for k in ('v2st', 'wtp'):
                e = z[k] - z[ln]; ok = pd.Series([(x > 0) != (mm > 0) or mm == 0 for x, mm in zip(e, z[ln])], index=z.index)
                top = e.abs()[ok].sort_values(ascending=False).index[:n]; row.append('%s %s' % (k, fmt(rec(z.loc[top], e[top], c[top]))))
            print('  picks at the live count (n=%d) vs %s: %s' % (n, ln, ' | '.join(row)))


if __name__ == '__main__':
    main()
