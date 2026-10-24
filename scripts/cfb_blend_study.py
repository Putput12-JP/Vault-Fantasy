#!/usr/bin/env python3
"""CFB model: a weekly-refit blend of the model and the market, walk-forward 2022-2025. PRE-REGISTERED: everything below was fixed before the first run.

The question: instead of one fixed rule ("pick when the model is 5+ points off the line"), refit each week how much of the model's disagreement with the market to
believe, using ONLY games already played, and pick on the refit expectation. Weights then move over time, and every pick is graded on weights that did not know its result.

  target      y = actual home margin - market line M  (M = ESPN close, or ESPN's recorded open where it exists)
  inputs      B1: the model's edge over M (v2 + special teams)          B2: two inputs, the rating edge (v2 margin - M) and the special teams term
  refit       before each week w (weeks 4+): ridge (lambda 500, no intercept) on every game from earlier seasons plus this season's weeks 4..w-1;
              fewer than 150 training games means no pick that week
  blend       M + r_hat, r_hat = the fitted expected miss of the line;  a pick is |r_hat| >= T for T in {1.0, 1.5, 2.0, 2.5} points, on the side of r_hat
  matched     also the same number of picks the current rule (|edge| >= 5) makes in that season, taken as the largest |r_hat| (no threshold search)
  judged on   2023-2025 combined and 2024-2025 (2022 has too little training data); the average miss of M + r_hat against the line alone and the model alone, and the pick records
  not tuned   lambda, T, the two input sets and the 150-game floor are fixed here. Nothing is chosen from results.

Run: python3 scripts/cfb_blend_study.py [--dir /tmp/cfbstudy]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_st_study as sts
import cfb_retune_study as rt

LAM, MIN_TRAIN, THRESHOLDS = 500.0, 150, (1.0, 1.5, 2.0, 2.5)


def refit_predict(df, feats, y, minweek=4):
    """r_hat for every game of weeks >= minweek, fit only on games played before it"""
    out = np.full(len(df), np.nan); coefs = {}
    X = df[feats].values; yy = df[y].values; s = df.season.values; w = df.week.values
    ok = ~np.isnan(X).any(axis=1) & ~np.isnan(yy)
    for season in sorted(set(s)):
        for week in range(minweek, 17):
            tr = ok & (w >= minweek) & ((s < season) | ((s == season) & (w < week)))
            te = np.where(ok & (s == season) & (w == week))[0]
            if len(te) == 0 or tr.sum() < MIN_TRAIN: continue
            A = X[tr]; b = np.linalg.solve(A.T @ A + LAM * np.eye(A.shape[1]), A.T @ yy[tr])
            out[te] = X[te] @ b; coefs[(season, week)] = b
    return out, coefs


def record(df, rhat, side_line, th=None, top=None):
    """pick on the sign of r_hat when |r_hat| >= th (or the `top` largest); graded against side_line"""
    d = df.assign(r=rhat).dropna(subset=['r', side_line])
    d = d[d.week >= 4]
    if top is not None: d = d.reindex(d.r.abs().sort_values(ascending=False).index).head(top)
    else: d = d[d.r.abs() >= th]
    c = d.hm - d[side_line]; d = d[c != 0]; c = c[c != 0]
    w = int(((d.r * c) > 0).sum()); return w, len(d) - w


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); ap.add_argument('--opens', default='/tmp/cfbstudy/opens_hist.json'); a = ap.parse_args()
    tg, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir); YEARS = [2022, 2023, 2024, 2025]
    order = [o for o in sts.game_order(gm, fbs, st.YEARS) if o[0] in YEARS]
    finals = {}; st.walk_forward(tg, gm, fbs, finals=finals)
    r = rt.v2_walk(tg, gm, fbs, finals); r = r[r.season.isin(YEARS)].reset_index(drop=True); assert len(r) == len(order)
    df = pd.DataFrame(dict(game_id=[o[1] for o in order], season=r.season, week=r.week, hm=r.hm, close=r.mkt, rating=r.pred))
    op = json.load(open(a.opens)); df['open'] = df.game_id.map(lambda i: -op[str(i)]['so'] if op.get(str(i)) and op[str(i)]['so'] is not None else np.nan)
    sts.order_weeks = dict(zip(df.game_id, df.week)); stg = sts.st_games(a.dir, YEARS)
    gap = sts.st_walk(order, stg, YEARS, sts.LAM, sts.CARRY); df['st'] = sts.WEIGHT * df.game_id.map(gap).fillna(0.0).values
    df['model'] = df.rating + df.st
    res = {}
    for M in ('close', 'open'):
        d = df.copy(); d['y'] = d.hm - d[M]; d['e_model'] = d.model - d[M]; d['e_rating'] = d.rating - d[M]
        cur_n = {s: int(((d.season == s) & (d.week >= 4) & (d.e_model.abs() >= 5) & d[M].notna() & (d.hm != d[M])).sum()) for s in YEARS}
        for name, feats in (('B1 model edge', ['e_model']), ('B2 rating edge + special teams', ['e_rating', 'st'])):
            rh, coefs = refit_predict(d, feats, 'y'); d['rh'] = rh
            print(f'\n######## market = {M}, {name}')
            for lab, ys in (('2023-25', [2023, 2024, 2025]), ('2024-25', [2024, 2025])):
                s = d[d.season.isin(ys) & (d.week >= 4) & d.rh.notna() & d[M].notna()]
                m_line, m_model, m_blend = np.abs(s.hm - s[M]).mean(), np.abs(s.hm - s.model).mean(), np.abs(s.hm - (s[M] + s.rh)).mean()
                lean = (s.rh * (s.hm - s[M]) > 0).sum() / max(((s.hm - s[M]) != 0).sum(), 1)
                print(f'  {lab}: n={len(s)}  miss: line {m_line:.3f}  model alone {m_model:.3f}  line + r_hat {m_blend:.3f}  | lean hit rate {lean * 100:.1f}%')
                for T in THRESHOLDS:
                    sub = d[d.season.isin(ys)]; w, l = record(sub, sub.rh.values, M, th=T); w2, l2 = record(sub, sub.rh.values, 'close' if M == 'open' else 'open', th=T)
                    print(f'      |r_hat| >= {T}: {w}-{l} ({w / max(w + l, 1) * 100:.1f}%) vs {M}   [{w2}-{l2} vs the other line]')
                w, l = 0, 0; wo, lo = 0, 0
                for ys1 in ys:
                    sub = d[d.season == ys1]; a1, b1 = record(sub, sub.rh.values, M, top=cur_n[ys1]); w += a1; l += b1
                    c1 = sub.e_model.values; a2, b2 = record(sub, c1, M, th=5.0); wo += a2; lo += b2
                print(f'      same number of picks as the current rule: {w}-{l} ({w / max(w + l, 1) * 100:.1f}%)   | the current rule itself (|edge| >= 5): {wo}-{lo} ({wo / max(wo + lo, 1) * 100:.1f}%)')
            cs = {k: np.round(v, 3) for k, v in coefs.items() if k[1] in (6, 12)}
            print('  fitted weights (season, week): ', {k: list(v) for k, v in cs.items()})
            res[f'{M}|{name}'] = d.rh.copy()
    df.to_csv(os.path.join(a.dir, 'blend_rows.csv'), index=False)


if __name__ == '__main__':
    main()
