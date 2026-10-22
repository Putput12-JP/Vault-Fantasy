#!/usr/bin/env python3
"""CFB week 7 retro, next test: a market-implied prior. Our preseason prior is a regression on talent, returning production, recruiting and the portal. The market already prices all of that.
Does centring the in-season EPA ridge on ratings fitted from the market's own closing lines (games already played) make our disagreements with the market more reliable?

Pre-registered, nothing chosen on pick record:
  Market rating  ridge on the closing margins of every FBS game before week w (home margin minus a 2.5 point home field = home rating minus away rating), centred on last season's
                 final market rating x CARRY (0.6, the special teams carry; 2021 opens flat). Strength M_w(team) in points, lambda LAM chosen from (5, 15, 40) on 2022-23 by the average miss of
                 the market rating alone predicting the final margin (weeks 4+).
  EPA on top     the usual weekly opponent-adjusted EPA ridge, but its prior is the market rating split evenly: offense = M/(2K), defense = -M/(2K), so the prior alone reproduces the market
                 rating (K = 70 points per unit). Its ridge strength ALPHA chosen from (300, 1000, 3000) on 2022-23 by average miss (300 = the live setting; larger = trust the market more).
  Margin         the same special teams term and home field as the live model: K x (rating gap) + HFA + special teams gap.
  Judged         average miss against the live model and the close; the weight the model's edge gets against the close; and 5+ point picks on the underdog side (the live pick rule) AT THE
                 LIVE RULE'S PICK COUNT (the largest edges), because a market-anchored model has few 5-point edges. Groups: tune 2022-23, TEST 2024-25 read once, 2026 weeks 4-7.
Run: python3 scripts/cfb_week7_market_prior_study.py --dir /tmp/cfbstudy   (needs base_rows.csv, opens_hist.json and the parquet files from cfb_week7_base_rows.py)
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_st_study as sts
import cfb_model as cm
from cfb_week7_study import rec, fmt

YEARS = [2022, 2023, 2024, 2025, 2026]; ALL = [2021] + YEARS
CARRY, HFA, K = 0.6, st.HFA, st.K
LAMS, ALPHAS = (5, 15, 40), (300, 1000, 3000)


def market_ratings(d, lam):
    """{(season, week): {team: market rating in points}} using only games before that week; the next season is centred on carry x this season's final ratings"""
    out = {}; prior = {}
    for y in ALL:
        g = d[(d.season == y)].dropna(subset=['mkt']).copy(); g['st_home'] = g.mkt - np.where(g.neutral, 0.0, HFA)
        cur = dict(prior)
        for w in range(1, 18):
            obs = g[g.week < w].rename(columns={})
            cur = sts.st_ratings(obs, prior, lam) if len(obs) >= 30 else dict(prior)
            out[(y, w)] = cur
        fin = sts.st_ratings(g, prior, lam) if len(g) >= 30 else dict(prior)
        prior = {t: CARRY * v for t, v in fin.items()}
    return out


def epa_on_market(tg, fbs, mr, alpha):
    """weekly EPA ridge centred on the market rating of that week; returns {(season, week): (offense ratings, defense ratings)}"""
    st.ALPHA = alpha; res = {}
    for y in YEARS:
        F = fbs[y]; T = tg[(tg.season == y) & tg.pos_team_id.isin(F) & tg.def_pos_team_id.isin(F)]
        for w in range(1, 17):
            m = mr[(y, w)]; pa = {t: v / (2 * K) for t, v in m.items()}; pb = {t: -v / (2 * K) for t, v in m.items()}
            res[(y, w)] = st.fit(T[T.week < w], pa, pb) if (T.week < w).sum() >= 30 else (pa, pb)
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir, ALL); fbs = st.fbs_sets(gm, a.dir, ALL); fbs[2026] = {t['id'] for t in json.load(open(os.path.join(cm.DATA, 'cfbd', 'teams_fbs_2026.json')))}
    # rows of earlier seasons for the market ratings: the 2021 closes are in the pbp, not in base_rows (which starts 2022), so build 2021 here from the schedule
    g21 = gm[(gm.season == 2021) & gm.homeTeamId.isin(fbs[2021]) & gm.awayTeamId.isin(fbs[2021]) & (gm.status_type_completed == True)]
    d21 = pd.DataFrame(dict(game_id=g21.game_id.astype(int), season=2021, week=g21.week.astype(int), hm=g21.homeFinalScore - g21.awayFinalScore, mkt=g21.homeTeamSpread, home_id=g21.homeTeamId.astype(int), away_id=g21.awayTeamId.astype(int), neutral=g21.neutral_site == True))
    dd = pd.concat([d21, d[['game_id', 'season', 'week', 'hm', 'mkt', 'home_id', 'away_id', 'neutral']]], ignore_index=True)
    tune = d.season.isin([2022, 2023]) & (d.week >= 4)
    print('market rating alone, miss on 2022-23 weeks 4+ by LAM (the close itself: %.3f)' % (d[tune].hm - d[tune].mkt).abs().mean())
    best = None; MR = {}
    for lam in LAMS:
        mr = market_ratings(dd, lam); MR[lam] = mr
        p = [mr[(r.season, r.week)].get(r.home_id, 0.0) - mr[(r.season, r.week)].get(r.away_id, 0.0) + (0.0 if r.neutral else HFA) for r in d.itertuples()]
        d['mo%d' % lam] = p; m = (d[tune].hm - d.loc[tune, 'mo%d' % lam]).abs().mean(); print('  lam %2d  miss %.3f' % (lam, m))
        if best is None or m < best[0]: best = (m, lam)
    lam = best[1]; print('chosen LAM', lam)
    d['mkt_only'] = d['mo%d' % lam] + d.gap
    res = {}
    for alpha in ALPHAS:
        R = epa_on_market(tg, fbs, MR[lam], alpha)
        p = []
        for r in d.itertuples():
            ra, rb = R[(r.season, r.week)]; P = lambda t: ra.get(t, 0.0) - rb.get(t, 0.0)
            p.append(K * (P(r.home_id) - P(r.away_id)) + (0.0 if r.neutral else HFA))
        d['a%d' % alpha] = np.array(p) + d.gap.values; m = (d[tune].hm - d.loc[tune, 'a%d' % alpha]).abs().mean(); res[alpha] = m
        print('built alpha', alpha, 'tune miss %.3f' % m, flush=True)
    alpha = min(res, key=res.get); print('chosen ALPHA', alpha)
    d['mp'] = d['a%d' % alpha]
    q = d[d.week >= 4].copy(); q.to_csv(os.path.join(a.dir, 'market_prior_rows.csv'), index=False)
    groups = (('tune 22-23', q.season.isin([2022, 2023])), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    for lab, m in groups:
        s = q[m].dropna(subset=['mkt']); print('\n== %s (%d games) | close miss %.3f' % (lab, len(s), (s.hm - s.mkt).abs().mean()))
        for k in ('v2st', 'mkt_only', 'mp'):
            x = np.c_[np.ones(len(s)), s.mkt, s[k] - s.mkt]; w = np.linalg.lstsq(x, s.hm, rcond=None)[0][2]
            print('  %-8s miss %.3f | weight on edge vs close %.3f | sd of edge %.2f' % (k, (s.hm - s[k]).abs().mean(), w, (s[k] - s.mkt).std()))
        for ln in ('mkt', 'open'):
            z = s.dropna(subset=[ln]); e0 = z.v2st - z[ln]; base = np.array([cm.pick_ok(x, w_, mm) for x, w_, mm in zip(e0, z.week, z[ln])]); n = int(base.sum()); c = z.hm - z[ln]; row = []
            for k in ('v2st', 'mkt_only', 'mp'):
                e = z[k] - z[ln]; ok = pd.Series([(x > 0) != (mm > 0) or mm == 0 for x, mm in zip(e, z[ln])], index=z.index)      # the underdog-side rule (not the favorite), any size of edge
                top = e.abs()[ok].sort_values(ascending=False).index[:n]; row.append('%s %s' % (k, fmt(rec(z.loc[top], e[top], c[top]))))
            print('  picks at the live count (n=%d) vs %s: %s' % (n, ln, ' | '.join(row)))


if __name__ == '__main__':
    main()
