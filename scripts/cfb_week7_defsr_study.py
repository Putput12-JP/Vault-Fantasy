#!/usr/bin/env python3
"""CFB week 7 retro: JP+ puts its largest stake (2.5 units) on picks flagged DEF_SR_DOMINANT (defensive success rate) and AWAY_CONVICTION, and those picks are 6-3 and 18-8.
JP+ does not publish the flag definition, so this tests an explicit guess, fixed BEFORE the run: the side our model picks has a defensive success-rate rating in the top 10% (variant
top10) or top 20% (top20) of FBS that week, from the same opponent-adjusted weekly ridge the model uses (success rate allowed, prior = last season x 0.85, only earlier games).
Judged on the live 5+ point picks, weeks 4+: do flagged picks cover more than unflagged ones? Tune 2022-23, TEST 2024-25, 2026 live replay, vs the ESPN close and open.
Run: python3 scripts/cfb_week7_defsr_study.py --dir /tmp/cfbstudy   (needs base_rows.csv, opens_hist.json, the parquet files)
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
from cfb_week7_study import rec, fmt
from cfb_week7_sr_study import metric_tables

ALL = [2021, 2022, 2023, 2024, 2025, 2026]; D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfbd')


def ratings_by_week(T, fbs):
    out = {}; prior = ({}, {})
    for y in ALL:
        F = fbs[y]; Ty = T[(T.season == y) & T.pos_team_id.isin(F) & T.def_pos_team_id.isin(F)]; cur = prior
        for w in range(1, 18):
            cur = st.fit(Ty[Ty.week < w], *prior) if (Ty.week < w).sum() >= 30 else prior
            out[(y, w)] = cur
        prior = ({t: st.S * v for t, v in cur[0].items()}, {t: st.S * v for t, v in cur[1].items()})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); fbs[2026] = {t['id'] for t in json.load(open(os.path.join(D, 'teams_fbs_2026.json')))}
    tgS, _ = metric_tables(a.dir, tg); R = ratings_by_week(tgS, fbs)
    d = d[d.week >= 4].copy()
    def pct(r):
        (_, b) = R[(r.season, r.week)]; F = fbs[r.season]; vals = np.array([b.get(t, 0.0) for t in F]); return vals
    cache = {}
    top10, top20 = [], []
    for r in d.itertuples():
        k = (r.season, r.week)
        if k not in cache: cache[k] = pct(r)
        vals = cache[k]; b = R[k][1]
        for line in ('mkt',):
            pass
        pick_home = (r.v2st - (r.mkt if not np.isnan(r.mkt) else 0)) > 0
        team = r.home_id if pick_home else r.away_id
        rank = (vals < b.get(team, 0.0)).mean()               # share of FBS teams with a better (lower) defense rating
        top10.append(rank <= 0.10); top20.append(rank <= 0.20)
    d['top10'], d['top20'] = top10, top20
    for ln in ('mkt', 'open'):
        print('\n=== 5+ point picks graded vs the ESPN %s, flagged (top defensive success rate on the picked side) vs not ===' % ('close' if ln == 'mkt' else 'open'))
        for lab, m in (('tune 22-23', d.season.isin([2022, 2023])), ('TEST 24-25', d.season.isin([2024, 2025])), ('2026 wk4-7', d.season == 2026), ('all 22-26', d.season > 0)):
            z = d[m].dropna(subset=[ln]).copy(); e = z.v2st - z[ln]; c = z.hm - z[ln]; big = e.abs() >= 5; row = []
            for fl in ('top10', 'top20'):
                f = big & z[fl]; n = big & ~z[fl]
                # the flag is evaluated for the side picked against the CLOSE; reuse for the open (same side in nearly all games)
                row.append('%s flagged %s (n=%d) | unflagged %s' % (fl, fmt(rec(z[f], e[f], c[f])), int(f.sum()), fmt(rec(z[n], e[n], c[n]))))
            print('  %-11s %s' % (lab, ' || '.join(row)))
    d.to_csv(os.path.join(a.dir, 'defsr_rows.csv'), index=False)


if __name__ == '__main__':
    sys.exit(main())
