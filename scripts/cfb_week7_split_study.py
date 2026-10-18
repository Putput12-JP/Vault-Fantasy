#!/usr/bin/env python3
"""CFB week 7 retro, candidate fixes in the in-season ridge. Two untested ideas:

  split   Offense and defense EPA ratings do not carry the same signal: defense is the noisier, less persistent side of the ball, but the ridge shrinks both toward the prior with one
          strength (ALPHA 300). Give each side its own strength: ALPHA x MO for offense and ALPHA x MD for defense. Grid fixed in advance: MO in (1, 0.5), MD in (1, 2, 4).
          Chosen on 2022-23 by the AVERAGE MISS only. (MO 1, MD 1 is the live model.)
  cap     One huge game can swing a rating (a team-game EPA per play far from the rest). Winsorise each team-game's EPA per play at the 2.5th and 97.5th percentile of all
          team-games before 2026-style fitting, one variant, fixed in advance.
Everything else is the live model: v2 prior, special teams term, K 70, HFA 2.5. 2022-23 tune, 2024-25 read once, 2026 weeks 4-7 live replay. Picks compared at the same count as the live 5+ rule.
Run: python3 scripts/cfb_week7_split_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.linear_model import Ridge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
from cfb_week7_study import rec, fmt

YEARS = [2022, 2023, 2024, 2025, 2026]; ALL = [2021] + YEARS
MO, MD = 1.0, 1.0


def fit_split(obs, pa, pb):
    if len(obs) < 30: return dict(pa), dict(pb)
    teams = sorted(set(obs.pos_team_id) | set(obs.def_pos_team_id)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    so, sd = 1 / np.sqrt(MO), 1 / np.sqrt(MD)          # column scale s makes the ridge penalty on the real coefficient alpha / s^2
    r = np.arange(len(obs)); o = obs.pos_team_id.map(ix).values; dd = obs.def_pos_team_id.map(ix).values
    X = sp.csr_matrix((np.r_[np.full(len(obs), so), np.full(len(obs), sd), obs.home_off.values * 10.0], (np.r_[r, r, r], np.r_[o, n + dd, np.full(len(obs), 2 * n)])), shape=(len(obs), 2 * n + 1))
    base = obs.pos_team_id.map(lambda t: pa.get(t, 0.0)).values + obs.def_pos_team_id.map(lambda t: pb.get(t, 0.0)).values
    m = Ridge(alpha=st.ALPHA).fit(X, obs.epa.values - base, sample_weight=obs.plays.values)
    a, b = dict(pa), dict(pb)
    for t, i in ix.items(): a[t] = pa.get(t, 0.0) + so * m.coef_[i]; b[t] = pb.get(t, 0.0) + sd * m.coef_[n + i]
    return a, b


def main():
    global MO, MD
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
    st.fit = fit_split; out = {}
    variants = [('MO1_MD1', 1, 1, False), ('MO1_MD2', 1, 2, False), ('MO1_MD4', 1, 4, False), ('MO.5_MD1', .5, 1, False), ('MO.5_MD2', .5, 2, False), ('MO.5_MD4', .5, 4, False), ('cap', 1, 1, True)]
    lo, hi = tg.epa.quantile(.025), tg.epa.quantile(.975)
    for name, mo, md, cap in variants:
        MO, MD = mo, md; T = tg.assign(epa=tg.epa.clip(lo, hi)) if cap else tg
        r = st.walk_forward(T, gm, fbs, years=ALL, prior_fn=prior_fn); r = r[r.season.isin(YEARS)].reset_index(drop=True)
        assert len(r) == len(base) and (r.hm.values == base.hm.values).all()
        out[name] = r.pred.values + base.gap.values; print('built', name, flush=True)
    q = base.copy()
    for k, v in out.items(): q[k] = v
    q = q[q.week >= 4].copy(); q.to_csv(os.path.join(a.dir, 'split_rows.csv'), index=False)
    tune = q.season.isin([2022, 2023]); groups = (('tune 22-23', tune), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    print('\naverage miss (market close in the last column)')
    for lab, m in groups: s = q[m]; print('  %-11s %s | close %.3f' % (lab, ' '.join('%s %.3f' % (k, (s.hm - s[k]).abs().mean()) for k in out), (s.hm - s.mkt).abs().mean()))
    best = min((k for k in out if k != 'cap'), key=lambda k: (q[tune].hm - q[tune][k]).abs().mean()); print('\nchosen on 2022-23 by miss:', best)
    for ln in ('mkt', 'open'):
        print('\n=== 5+ and matched-count picks vs the ESPN %s ===' % ('close' if ln == 'mkt' else 'open'))
        for lab, m in groups:
            s = q[m].dropna(subset=[ln]); c = s.hm - s[ln]; n = int(((s.MO1_MD1 - s[ln]).abs() >= 5).sum()); row = []
            for k in ('MO1_MD1', best, 'cap'):
                e = s[k] - s[ln]; sel = s[e.abs() >= 5]; idx = e.abs().sort_values(ascending=False).index[:n]; row.append('%s 5+ %s | matched %s' % (k, fmt(rec(sel, e[sel.index], c[sel.index])), fmt(rec(s.loc[idx], e[idx], c[idx]))))
            print('  %-11s n=%d  %s' % (lab, n, '\n              '.join(row)))


if __name__ == '__main__':
    sys.exit(main())
