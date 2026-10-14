#!/usr/bin/env python3
"""CFB model: does a team-specific home field improve the v2 + special teams model? Walk-forward 2022-2025.

The flat 2.5 becomes 2.5 + c + u, where u is a ridge-shrunk effect of the home team (or its conference) on the margin residual
(actual - model, non-neutral games), learned only from EARLIER seasons, and c is the league-wide mean residual so far. Nothing else changes.
Rule fixed before the run: the ridge lambda is chosen on 2022-2023 by the average miss only; 2024-2025 is read once.

A head-coach flag was meant to be tested here too, but ESPN's free coaches endpoint returns the CURRENT head coach for every season
(Alabama 2023 comes back as DeBoer), so there is no usable coaching history in it. That test needs the CollegeFootballData /coaches feed.

Run: python3 scripts/cfb_hfa_study.py [--dir /tmp/cfbstudy]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_prior_study as v2
import cfb_v2_st_study as sts

def v2_walk(tg, gm, fbs, finals):
    tab = {}
    feats = v2.FEATS
    for y in range(2022, 2026):
        t = v2.features(y, finals[y - 1], fbs[y])
        t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0)); tab[y] = t

    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[feats].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[feats].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    return st.walk_forward(tg, gm, fbs, prior_fn=prior_fn)


def ridge_effects(keys, resid, lam):
    """ridge effect per key on the residual, centred on the mean: returns (mean, {key: effect})"""
    c = float(np.mean(resid)); ks = sorted(set(keys)); ix = {k: i for i, k in enumerate(ks)}
    s = np.zeros(len(ks)); n = np.zeros(len(ks))
    for k, r in zip(keys, resid): s[ix[k]] += r - c; n[ix[k]] += 1
    return c, {k: float(s[ix[k]] / (n[ix[k]] + lam)) for k in ks}


def hfa_layer(df, home, neutral, group, lam):
    """pred + league mean residual so far + the shrunk effect of the home team (group: home id -> key), from EARLIER seasons only"""
    out = df.pred.values.copy()
    for y in sorted(df.season.unique()):
        h = df[(df.season < y) & ~neutral]
        if len(h) < 200: continue
        c, eff = ridge_effects([group(t) for t in home[h.index]], (h.hm - h.pred).values, lam)
        m = (df.season == y).values
        add = np.array([c + (0.0 if nt else eff.get(group(t), 0.0)) for t, nt in zip(home[m], neutral[m])])
        out[m] = out[m] + add
    return out


def bias_venue_layer(df, home, away, neutral, lb, lv):
    """Two kinds of team effect on the residual, from EARLIER seasons only: a strength bias (+b when the team is at home, -b when away, every game) and a venue
    effect (extra points for the home team in non-neutral games). Separate ridge penalties lb / lv (lv=None drops the venue part). Splits what the
    home-only effect above mixes together: a rating that is simply wrong for a team versus a real home-field edge."""
    out = df.pred.values.copy(); teams = sorted(set(home) | set(away)); ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    for y in sorted(df.season.unique()):
        h = df[(df.season < y)]
        if len(h) < 200: continue
        N = len(h); Xb = np.zeros((N, n)); Xv = np.zeros((N, n)); hi, ai, nt = home[h.index].map(ix).values, away[h.index].map(ix).values, neutral[h.index].values
        Xb[np.arange(N), hi] += 1; Xb[np.arange(N), ai] -= 1; Xv[np.arange(N)[~nt], hi[~nt]] = 1
        r = (h.hm - h.pred).values; c = float(r[~nt].mean()); r = r - c
        cols = [Xb / np.sqrt(lb)] + ([Xv / np.sqrt(lv)] if lv else [])
        X = np.hstack(cols); w = np.linalg.solve(X.T @ X + np.eye(X.shape[1]), X.T @ r)
        b = w[:n] / np.sqrt(lb); v = (w[n:] / np.sqrt(lv)) if lv else np.zeros(n)
        m = (df.season == y).values; hh = home[m].map(ix).values; aa = away[m].map(ix).values; nn = neutral[m].values
        out[m] = out[m] + b[hh] - b[aa] + np.where(nn, 0.0, c + v[hh])
    return out


def score(df, col, mask, label):
    s = df[mask & (df.week >= 4)]; q = s.dropna(subset=['mkt']); qo = s.dropna(subset=['open'])
    X = np.c_[np.ones(len(q)), q.mkt, q[col] - q.mkt]; b = np.linalg.lstsq(X, q.hm, rcond=None)[0][2]
    wc, lc = sts.picks(s, col, 'mkt'); wo, lo = sts.picks(s, col, 'open')
    print(f'  {label:26s} miss {np.abs(q.hm - q[col]).mean():.3f} | weight on edge {b:.2f} | 5+ vs close {wc}-{lc} ({wc / max(wc + lc, 1) * 100:.1f}%) | 5+ vs open {wo}-{lo} ({wo / max(wo + lo, 1) * 100:.1f}%)')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); ap.add_argument('--opens', default='/tmp/cfbstudy/opens_hist.json'); a = ap.parse_args()
    tg, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir); YEARS = [2022, 2023, 2024, 2025]
    finals = {}; st.walk_forward(tg, gm, fbs, finals=finals)
    order = [o for o in sts.game_order(gm, fbs, st.YEARS) if o[0] in YEARS]
    base = v2_walk(tg, gm, fbs, finals); base = base[base.season.isin(YEARS)].reset_index(drop=True)
    assert len(order) == len(base)
    ids = [o[1] for o in order]
    df = pd.DataFrame(dict(game_id=ids, season=base.season, week=base.week, hm=base.hm, mkt=base.mkt, v2=base.pred))
    op = json.load(open(a.opens)); df['open'] = df.game_id.map(lambda i: -op[str(i)]['so'] if op.get(str(i)) and op[str(i)]['so'] is not None else np.nan)
    sts.order_weeks = dict(zip(df.game_id, df.week)); stg = sts.st_games(a.dir, YEARS)
    gap = sts.st_walk(order, stg, YEARS, sts.LAM, sts.CARRY); df['gap'] = df.game_id.map(gap).fillna(0.0)
    df['base'] = df.v2 + sts.WEIGHT * df.gap
    home = pd.Series([o[2] for o in order]); away = pd.Series([o[3] for o in order]); neutral = pd.Series([bool(o[4]) for o in order])
    conf = pd.read_csv(f'{a.dir}/teams.csv', encoding='latin-1').set_index('team_id').conference.to_dict()
    tune = (df.season.isin([2022, 2023])).values; test = ~tune
    best = {}
    for name, group, lams in (('team', lambda t: t, (10, 30, 100)), ('conf', lambda t: str(conf.get(t)) if isinstance(conf.get(t), str) else 'other', (5, 20, 80))):
        res = []
        for lam in lams:
            df[f'{name}_{lam}'] = hfa_layer(df.assign(pred=df.base), home, neutral, group, lam)
            res.append((np.abs((df.hm - df[f'{name}_{lam}'])[tune & (df.week >= 4).values]).mean(), lam))
        best[name] = min(res)[1]; print(f'home field by {name}: tune miss by lambda', {l: round(m, 3) for m, l in res}, '-> chosen', best[name])
    df['hfa_team'] = df[f"team_{best['team']}"]; df['hfa_conf'] = df[f"conf_{best['conf']}"]
    df['hfa_flat'] = hfa_layer(df.assign(pred=df.base), home, neutral, lambda t: 'all', 1e9)        # league-wide recalibration only
    res = []
    for lb in (30, 100, 300):
        for lv in (None, 30, 100, 300):
            col = f'bv_{lb}_{lv}'; df[col] = bias_venue_layer(df.assign(pred=df.base), home, away, neutral, lb, lv)
            res.append((np.abs((df.hm - df[col])[tune & (df.week >= 4).values]).mean(), lb, lv))
    print('strength bias + venue effect, tune miss:', {f'b{lb}/v{lv}': round(m, 3) for m, lb, lv in res})
    _, lb, lv = min(res); df['bias_venue'] = df[f'bv_{lb}_{lv}']; print('chosen on 2022-23: bias lambda', lb, 'venue lambda', lv)
    _, lb0, _ = min([r for r in res if r[2] is None]); df['bias_only'] = df[f'bv_{lb0}_None']; print('bias only (no venue) lambda', lb0)
    for lab, mask in (('TUNE 2022-23', tune), ('TEST 2024-25 (read once)', test), ('ALL 2022-25', tune | test)):
        print(f'\n== {lab}  (weeks 4+)')
        for col, name in (('base', 'current (v2 + special teams)'), ('hfa_flat', '+ league mean home field'), ('hfa_conf', '+ conference home field'), ('hfa_team', '+ team home field (home games only)'), ('bias_only', '+ team strength bias, no venue'), ('bias_venue', '+ strength bias + venue')):
            score(df, col, mask if isinstance(mask, np.ndarray) else mask.values, name)
    # what the team effects look like at the end (all four seasons)
    h = df[~neutral.values]; c, eff = ridge_effects([t for t in home[h.index]], (h.hm - h.base).values, best['team'])
    nm = pd.read_csv(f'{a.dir}/teams.csv', encoding='latin-1').set_index('team_id').school.to_dict()
    top = sorted(eff.items(), key=lambda kv: -kv[1]); print(f'\nleague mean residual {c:+.2f}; largest team effects (points, shrunk):')
    print('  high', [(nm.get(k, k), round(v, 2)) for k, v in top[:6]]); print('  low ', [(nm.get(k, k), round(v, 2)) for k, v in top[-6:]])
    df.to_csv(os.path.join(a.dir, 'hfa_rows.csv'), index=False)


if __name__ == '__main__':
    main()
