#!/usr/bin/env python3
"""CFB week 7 retro, round 7: do the market's preseason win totals know something our preseason prior does not?

A full prior backtest is not possible yet: data/win_totals covers about 80 teams in 2022, 69 in 2023 and 2024, 133 in 2025 (scripts/fetch_win_totals.py). So this asks the cheaper question first, on the teams
that are covered: does the win total explain how good a team turned out to be, over and above the live v2 prior?  Pre-registered: target = the team's FINAL-season strength two ways, (a) a ridge on that season's
closing margins (lambda 5, centred on 0), in points, and (b) the model's own final EPA rating, K x (offense - defense), in points. Prior = the live v2 regression prior for that season (fit only on earlier seasons,
so 2022 has none and is dropped). Win total centred on that season's mean among listed teams. Leave-one-season-out over 2023, 2024, 2025: fit target ~ prior (A) and target ~ prior + win total (B) on the other seasons,
score the held-out season by root mean square error. Nothing is tuned.
Run: python3 scripts/cfb_week7_wintotals_study.py --dir /tmp/cfbstudy   (parquet files and base_rows.csv from cfb_week7_base_rows.py)
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
import cfb_v2_st_study as sts
import cfb_model as cm

K, HFA = st.K, st.HFA
ALL = [2021, 2022, 2023, 2024, 2025]; YEARS = [2022, 2023, 2024, 2025]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); finals = {}; st.walk_forward(tg, gm, fbs, years=ALL, finals=finals)
    tab = {}
    for y in YEARS:
        t = v2.features(y, finals[y - 1], fbs[y]); t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0)); tab[y] = t
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); rows = []
    for y in YEARS[1:]:
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]; prior = K * ((Xc @ bo) - (Xc @ bd)); pr = dict(zip(cur.team, prior))
        g = d[(d.season == y)].dropna(subset=['mkt']); g = g.assign(st_home=g.mkt - np.where(g.neutral, 0.0, HFA))
        mk = sts.st_ratings(g, {}, 5)                                   # the season's final market strength, points
        wt = json.load(open(os.path.join(cm.DATA, 'win_totals', f'win_totals_{y}.json')))['teams']; mean = np.mean([v['total'] for v in wt.values()])
        for tid, v in wt.items():
            t = int(tid)
            if t in pr and t in mk: rows.append(dict(season=y, team=t, prior=pr[t], wt=v['total'] - mean, mkt=mk[t], epa=K * (finals[y][0].get(t, 0.0) - finals[y][1].get(t, 0.0))))
    r = pd.DataFrame(rows); print(r.groupby('season').size().to_dict(), 'covered team-seasons')
    for tgt, lab in (('mkt', 'final market strength'), ('epa', 'final EPA rating')):
        print('\n== target: %s' % lab)
        tot = {'A': [], 'B': []}
        for y in YEARS[1:]:
            tr, te = r[r.season != y], r[r.season == y]
            XA = np.c_[np.ones(len(tr)), tr.prior]; XB = np.c_[np.ones(len(tr)), tr.prior, tr.wt]
            ba = np.linalg.lstsq(XA, tr[tgt], rcond=None)[0]; bb = np.linalg.lstsq(XB, tr[tgt], rcond=None)[0]
            ea = te[tgt] - np.c_[np.ones(len(te)), te.prior] @ ba; eb = te[tgt] - np.c_[np.ones(len(te)), te.prior, te.wt] @ bb
            tot['A'] += list(ea ** 2); tot['B'] += list(eb ** 2)
            print('  hold out %d (n=%d): rmse prior only %.2f | prior + win total %.2f | win total weight %.2f pts per win' % (y, len(te), np.sqrt((ea ** 2).mean()), np.sqrt((eb ** 2).mean()), bb[2]))
        print('  all held-out: prior only %.2f | prior + win total %.2f   (target sd %.2f)' % (np.sqrt(np.mean(tot['A'])), np.sqrt(np.mean(tot['B'])), r[tgt].std()))
    print('\ncorrelation of win total with prior: %.2f; with final market strength %.2f; prior with final market strength %.2f' % (r.wt.corr(r.prior), r.wt.corr(r.mkt), r.prior.corr(r.mkt)))


if __name__ == '__main__':
    main()
