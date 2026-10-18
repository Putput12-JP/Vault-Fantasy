#!/usr/bin/env python3
"""CFB week 7 retro, cause hunt: where in the model does the gap to the market (and to JP+) come from, the preseason prior or the in-season ratings?

Builds the PRIOR-ONLY margin for every game (the v2 prior with no in-season data at all) next to the live margin, then asks, per group (tune 2022-23, test 2024-25, 2026 weeks 4-7):
  1. miss of prior-only, in-season-only effect (live minus prior-only) and live, against the market close
  2. does the in-season move (live minus prior-only) point the right way? slope of (final minus close) on the move, and on the prior's own gap to the close
  3. a pre-registered shrink toward the prior:  pred = live + b * (prior_only - live), b fitted on 2022-23 by the average miss only (one parameter), read once on 2024-25 and 2026
Run: python3 scripts/cfb_week7_cause_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
from cfb_week7_study import rec, fmt

YEARS = [2022, 2023, 2024, 2025, 2026]; ALL = [2021] + YEARS


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    base = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    base['open'] = base.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); fbs[2026] = {t['id'] for t in json.load(open(os.path.join(v2.D, 'teams_fbs_2026.json')))}
    finals = {}; st.walk_forward(tg, gm, fbs, years=ALL, finals=finals)
    tab = {}
    for y in YEARS:
        t = v2.features(y, finals[y - 1], fbs[y])
        if y < 2026: t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0))
        tab[y] = t

    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    r = st.walk_forward(tg.iloc[:0], gm, fbs, years=ALL, prior_fn=prior_fn); r = r[r.season.isin(YEARS)].reset_index(drop=True)
    assert len(r) == len(base) and (r.hm.values == base.hm.values).all()
    base['p0'] = r.pred.values + base.gap.values * 0.0        # prior only, no special teams (it has no in-season data either)
    base['move'] = base.v2st - base.p0
    q = base[base.week >= 4].copy(); q.to_csv(os.path.join(a.dir, 'cause_rows.csv'), index=False)
    groups = (('tune 22-23', q.season.isin([2022, 2023])), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    print('1. miss against the final margin (market close in the last column)')
    for lab, m in groups:
        s = q[m]; print('  %-11s prior-only %.3f | live %.3f | close %.3f | sd of the in-season move %.2f' % (lab, (s.hm - s.p0).abs().mean(), (s.hm - s.v2st).abs().mean(), (s.hm - s.mkt).abs().mean(), s.move.std()))
    print('\n2. does the in-season move help? slope of (final minus live) on the move (>0 = move too timid, <0 = overshoots), and of (final minus close) on prior-minus-close')
    for lab, m in groups:
        s = q[m].dropna(subset=['mkt']); mv = s.move; b1 = (mv * (s.hm - s.v2st)).sum() / (mv * mv).sum(); pe = s.p0 - s.mkt; b2 = (pe * (s.hm - s.mkt)).sum() / (pe * pe).sum()
        print('  %-11s move slope %.2f | prior edge slope %.3f | live edge slope %.3f' % (lab, b1, b2, ((s.v2st - s.mkt) * (s.hm - s.mkt)).sum() / ((s.v2st - s.mkt) ** 2).sum()))
    tune = q[q.season.isin([2022, 2023])]; x = tune.p0 - tune.v2st; b = float((x * (tune.hm - tune.v2st)).sum() / (x * x).sum()); print('\n3. shrink toward the prior: b fitted on 2022-23 = %.3f' % b)
    q['shr'] = q.v2st + b * (q.p0 - q.v2st)
    for lab, m in groups:
        s = q[m]; row = []
        for ln in ('mkt', 'open'):
            z = s.dropna(subset=[ln])
            for k in ('v2st', 'shr'):
                e = z[k] - z[ln]; c = z.hm - z[ln]; sel = z[e.abs() >= 5]; row.append('%s vs %s %s' % (k, ln, fmt(rec(sel, e[sel.index], c[sel.index]))))
        print('  %-11s miss live %.3f shrunk %.3f | %s' % (lab, (s.hm - s.v2st).abs().mean(), (s.hm - s.shr).abs().mean(), ' | '.join(row)))
    s = q[q.season == 2026]
    print('\n2026 by week, miss: prior-only / live / close'); [print('  wk%d  %.2f / %.2f / %.2f  (n=%d)' % (w, (g.hm - g.p0).abs().mean(), (g.hm - g.v2st).abs().mean(), (g.hm - g.mkt).abs().mean(), len(g))) for w, g in s.groupby('week')]


if __name__ == '__main__':
    sys.exit(main())
