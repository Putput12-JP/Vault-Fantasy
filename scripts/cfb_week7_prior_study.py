#!/usr/bin/env python3
"""CFB week 7 retro: is our preseason prior the weak link? Add last season's FINAL SP+, FPI and Elo (CollegeFootballData, all in data/cfbd, none used by the model today) to the v2 regression prior.

Pre-registered: the three variants below, the same ridge (lam 10), the same special teams term, the same weekly in-season ridge. The prior for season y is learned only on seasons before y and
uses only what was public before y kicked off (last season's final ratings). Nothing is chosen by pick record. Judged on the average miss (the project's 0.05 bar) and on 5+ point picks,
and on the early weeks (4-8) where the prior still carries the most weight. 2022-23 is the tuning pair, 2024-25 the test pair, 2026 weeks 4-7 (the live season) an extra out-of-sample read.
  base   prev_o, prev_d, talent, recruiting, returning production, portal                      the live prior
  +sp    base + last season's final SP+ overall, offense, defense
  +all   +sp + last season's final FPI and Elo
Run: python3 scripts/cfb_week7_prior_study.py --dir /tmp/cfbstudy   (needs base_rows.csv, opens_hist.json, the parquet files)
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
from cfb_week7_study import rec, fmt

YEARS = [2022, 2023, 2024, 2025, 2026]; ALL = [2021] + YEARS
D = v2.D
SP_F, ALL_F = ['sp', 'sp_o', 'sp_d'], ['sp', 'sp_o', 'sp_d', 'fpi', 'elo']


def extra(y, teams):
    """last season's (y-1) final SP+/FPI/Elo for each team id, standardised; teams without one get the median"""
    ids = v2.team_ids(y - 1); sp = {ids.get(r['team']): r for r in v2.ld('sp', y - 1) if r['team'] in ids}
    fpi = {ids.get(r['team']): r['fpi'] for r in v2.ld('fpi', y - 1) if r['team'] in ids}; elo = {ids.get(r['team']): r['elo'] for r in v2.ld('elo', y - 1) if r['team'] in ids}
    df = pd.DataFrame({'team': sorted(teams)})
    df['sp'] = df.team.map(lambda t: sp[t]['rating'] if t in sp else np.nan); df['sp_o'] = df.team.map(lambda t: sp[t]['offense']['rating'] if t in sp else np.nan)
    df['sp_d'] = df.team.map(lambda t: sp[t]['defense']['rating'] if t in sp else np.nan)
    df['fpi'] = df.team.map(fpi); df['elo'] = df.team.map(elo)
    for c in ALL_F: df[c] = df[c].fillna(df[c].median()); df[c] = (df[c] - df[c].mean()) / (df[c].std() or 1)
    return df


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    base = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    base['open'] = base.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); fbs[2026] = {t['id'] for t in json.load(open(os.path.join(D, 'teams_fbs_2026.json')))}
    finals = {}; st.walk_forward(tg, gm, fbs, years=ALL, finals=finals)
    tab = {}
    for y in YEARS:
        t = v2.features(y, finals[y - 1], fbs[y]); t = t.merge(extra(y, fbs[y]), on='team')
        if y < 2026: t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0))
        tab[y] = t
    out = {}
    for name, feats in (('base', v2.FEATS), ('+sp', v2.FEATS + SP_F), ('+all', v2.FEATS + ALL_F)):
        def prior_fn(y, _, feats=feats):
            if y <= 2022: return ({}, {})
            train = pd.concat([tab[k] for k in range(2022, y)]); X = train[feats].values
            bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
            cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[feats].values]
            return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
        r = st.walk_forward(tg, gm, fbs, years=ALL, prior_fn=prior_fn); r = r[r.season.isin(YEARS)].reset_index(drop=True)
        assert len(r) == len(base) and (r.hm.values == base.hm.values).all()
        out[name] = r.pred.values + base.gap.values; print('built', name, flush=True)
    q = base.copy()
    for k, v in out.items(): q[k] = v
    q = q[q.week >= 4].copy(); q.to_csv(os.path.join(a.dir, 'prior_study_rows.csv'), index=False)
    groups = (('tune 22-23', q.season.isin([2022, 2023])), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    for lab, m in groups:
        s = q[m]; print('\n== %s (%d games) | market close miss %.3f' % (lab, len(s), (s.hm - s.mkt).abs().mean()))
        for k in out:
            line = []
            for ln in ('mkt', 'open'):
                z = s.dropna(subset=[ln]); e = z[k] - z[ln]; c = z.hm - z[ln]; sel = z[e.abs() >= 5]; line.append('5+ vs %s %s' % (ln, fmt(rec(sel, e[sel.index], c[sel.index]))))
            early = s[s.week <= 8]
            print('  %-5s miss %.3f (wk4-8 %.3f) | %s' % (k, (s.hm - s[k]).abs().mean(), (early.hm - early[k]).abs().mean(), ' | '.join(line)))
    print('\nmatched-count 5+ vs close: the variant takes the same number of picks as base (largest |edge|), per group')
    for lab, m in groups:
        s = q[m].dropna(subset=['mkt']); n = int(((s.base - s.mkt).abs() >= 5).sum()); row = []
        for k in out:
            e = s[k] - s.mkt; c = s.hm - s.mkt; top = e.abs().sort_values(ascending=False).index[:n]; sel = s.loc[top]; row.append('%s %s' % (k, fmt(rec(sel, e[top], c[top]))))
        print('  %-11s n=%d  %s' % (lab, n, ' | '.join(row)))
    s = q[q.season.isin([2024, 2025, 2026])]
    for k in out:
        z = s.dropna(subset=['mkt']); x = np.c_[np.ones(len(z)), z.mkt, z[k] - z.mkt]; print('weight on the model edge vs close, 2024-26, %s: %.3f' % (k, np.linalg.lstsq(x, z.hm, rcond=None)[0][2]))


if __name__ == '__main__':
    sys.exit(main())
