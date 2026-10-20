#!/usr/bin/env python3
"""
Decay backtest for docs/minutes-lab-preseason.md (rules fixed there before this ran).

Each veteran's season is replayed game by game. For game n+1 the Lab-style blend is
    pred = (n x EWMA + K x start) / (n + K),   EWMA alpha 0.25 over minutes in games played (as the Lab does),
with start = last-season-only (standard, K = 4 as today) or preseason-informed (K from a grid).
Scored against the minutes actually played. Paired MAE difference by games played so far, player-clustered bootstrap.

  nba/.venv/bin/python nba/scripts/build_preseason_decay.py     # -> data/preseason_decay.json
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_preseason_signals as B

ALPHA, K_STD = 0.25, 4
K_GRID = (2, 4, 8, 12, 16, 24)
BINS = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 15), (16, 25), (26, 40), (41, 200)]
MAX_N = 30


def game_minutes(season):
    rs = B.load_rs(season)
    rs = rs.sort_values(['pid', 'date'])
    return {pid: g['min'].values for pid, g in rs.groupby('pid')}, \
           {pid: str(g.team_id.iloc[0]) for pid, g in rs.groupby('pid')}, \
           {pid: str(g.team_id.iloc[-1]) for pid, g in rs.groupby('pid')}


def moved_flags(d):
    """preseason team differs from last season's final team"""
    P, _, _ = B.load_pre()
    P = P[P.box_min > 0]
    pre_team = P.groupby(['season', 'pid']).team.agg(lambda s: s.mode().iloc[0]).astype(str)
    lastteam = {}
    for S in B.SEASONS:
        _, _, last = game_minutes(S - 1)
        lastteam[S] = last
    return [pre_team.get((S, pid)) != lastteam[S].get(pid) for S, pid in zip(d.S, d.pid)]


def main():
    d, _, _ = B.build_table()
    d = d[(d.L_min >= 400) & (d.box_min >= 40)].copy().reset_index(drop=True)
    d['moved'] = moved_flags(d)
    d['moved_f'] = d.moved.astype(float)
    d = d[d.E_gp >= 1].reset_index(drop=True)
    out = {'n_player_seasons': int(len(d)), 'moved_share': float(d.moved.mean())}

    # ---- start models, leave-one-season-out
    tgt = d[d.E_gp >= 10].index
    dd = d.loc[tgt]
    sL = B.loso(dd, ['L_mpg'], 'E_mpg')
    sP = B.loso(dd, ['L_mpg', 'mpg_1h'], 'E_mpg')
    dd = dd.assign(mv_x=dd.moved_f * dd.mpg_1h)
    sPm = B.loso(dd, ['L_mpg', 'mpg_1h', 'moved_f'], 'E_mpg')
    eL, eP, eM = (sL - dd.E_mpg).abs().values, (sP - dd.E_mpg).abs().values, (sPm - dd.E_mpg).abs().values
    m1, se1, z1 = B.paired(dd, eP, eM)
    out['moved_term'] = {'mae_pooled': float(eP.mean()), 'mae_with_moved': float(eM.mean()), 'paired_gain': m1, 'se': se1, 'z': z1,
                         'keep': bool(z1 >= 2)}
    use_moved = out['moved_term']['keep']
    feats_P = ['L_mpg', 'mpg_1h'] + (['moved_f'] if use_moved else [])
    out['feats_P'] = feats_P
    # per-row starts for ALL rows (predicting each season from models fit on the other two)
    d['sL'] = np.nan
    d['sP'] = np.nan
    for S in B.SEASONS:
        tr = d[(d.S != S) & (d.E_gp >= 10)]
        te = d.S == S
        bL = B.ols(tr[['L_mpg']].values, tr.E_mpg.values)
        bP = B.ols(tr[feats_P].values, tr.E_mpg.values)
        d.loc[te, 'sL'] = B.pred(bL, d.loc[te, ['L_mpg']].values)
        d.loc[te, 'sP'] = B.pred(bP, d.loc[te, feats_P].values)

    # ---- replay
    mins = {S: game_minutes(S)[0] for S in B.SEASONS}
    recs = []
    for i, r in d.iterrows():
        g = mins[r.S].get(r.pid)
        if g is None:
            continue
        e = None
        for n, x in enumerate(g[:80]):
            if n:
                e = x_prev if e is None else e
            # EWMA over games before this one
            pred = {}
            ew = None
            if n:
                ew = g[0]
                for y in g[1:n]:
                    ew += ALPHA * (y - ew)
            def blend(start, K):
                return start if n == 0 else (n * ew + K * start) / (n + K)
            row = {'S': r.S, 'pid': r.pid, 'n': n, 'y': x, 'std': blend(r.sL, K_STD)}
            for K in K_GRID:
                row[f'pre{K}'] = blend(r.sP, K)
                row[f'std{K}'] = blend(r.sL, K)
            recs.append(row)
            x_prev = x
    R = pd.DataFrame(recs)
    for c in [c for c in R.columns if c.startswith(('std', 'pre'))]:
        R['e_' + c] = (R[c] - R.y).abs()
    out['rows'] = int(len(R))

    # ---- K choice by season-held-out (games 0..MAX_N)
    early = R[R.n <= MAX_N]
    kchoice = {}
    for S in B.SEASONS:
        tr = early[early.S != S]
        best = min(K_GRID, key=lambda K: tr['e_pre%d' % K].mean())
        kchoice[int(S)] = {'K': int(best), 'heldout_mae_pre': float(early[early.S == S]['e_pre%d' % best].mean()),
                           'heldout_mae_std4': float(early[early.S == S]['e_std'].mean())}
    out['k_by_heldout_season'] = kchoice
    out['mae_by_K_all'] = {str(K): float(early['e_pre%d' % K].mean()) for K in K_GRID}
    out['mae_std_by_K_all'] = {str(K): float(early['e_std%d' % K].mean()) for K in K_GRID}
    Kbest = min(K_GRID, key=lambda K: early['e_pre%d' % K].mean())
    out['K_pre'] = int(Kbest)

    # ---- paired gain by games played so far (standard Lab K=4 vs preseason-informed K*)
    gain = {}
    pids = R.groupby(['S', 'pid']).indices
    keys = list(pids)
    rng = np.random.default_rng(20261020)
    for lo, hi in BINS:
        sub = R[(R.n >= lo) & (R.n <= hi)]
        diff = (sub.e_std - sub['e_pre%d' % Kbest]).values
        keyidx = sub.groupby(['S', 'pid']).indices
        ks = list(keyidx)
        sums = np.array([diff[keyidx[k]].sum() for k in ks])
        cnts = np.array([len(keyidx[k]) for k in ks])
        boots = []
        for _ in range(2000):
            pick = rng.integers(0, len(ks), len(ks))
            boots.append(sums[pick].sum() / cnts[pick].sum())
        se = float(np.std(boots))
        gain[f'{lo}-{hi}'] = {'rows': int(len(sub)), 'players': int(len(ks)), 'mae_std': float(sub.e_std.mean()),
                              'mae_pre': float(sub['e_pre%d' % Kbest].mean()), 'gain': float(diff.mean()), 'se': se,
                              'z': float(diff.mean() / se) if se else 0.0}
    out['gain_by_games_played'] = gain
    # exploratory (added after the pre-registered run, amendment 1): same comparison against a standard blend that
    # also uses the best K, and the size of the jump when the preseason term switches off at N_ret
    gain2 = {}
    Kstd = min(K_GRID, key=lambda K: early['e_std%d' % K].mean())
    for lo, hi in BINS:
        sub = R[(R.n >= lo) & (R.n <= hi)]
        diff = (sub['e_std%d' % Kstd] - sub['e_pre%d' % Kbest]).values
        keyidx = sub.groupby(['S', 'pid']).indices
        ks = list(keyidx)
        sums = np.array([diff[keyidx[k]].sum() for k in ks]); cnts = np.array([len(keyidx[k]) for k in ks])
        boots = [sums[pk].sum() / cnts[pk].sum() for pk in (rng.integers(0, len(ks), len(ks)) for _ in range(2000))]
        gain2[f'{lo}-{hi}'] = {'gain': float(diff.mean()), 'se': float(np.std(boots)), 'z': float(diff.mean() / np.std(boots))}
    out['gain_vs_std_bestK'] = {'K_std': int(Kstd), 'by_bin': gain2}
    # shipped shape (amendment 2): the preseason term fades linearly to zero from game 6 so nothing jumps at N_ret
    ok = [hi for (lo, hi) in BINS if gain[f'{lo}-{hi}']['gain'] >= 0.05 and gain[f'{lo}-{hi}']['z'] >= 2]
    nret = (max(ok) + 1) if ok else 0
    w = np.clip((nret - R.n) / (nret - 5), 0, 1)
    R['taper'] = R['std'] + w * (R['pre%d' % Kbest] - R['std'])
    R['e_taper'] = (R.taper - R.y).abs()
    tap = {}
    for lo, hi in BINS:
        sub = R[(R.n >= lo) & (R.n <= hi)]
        tap[f'{lo}-{hi}'] = {'mae_std': float(sub.e_std.mean()), 'mae_taper': float(sub.e_taper.mean()), 'mae_pre_untapered': float(sub['e_pre%d' % Kbest].mean())}
    out['taper'] = tap
    jump = R[R.n == 11]
    out['jump_at_n11'] = {'mean_abs_pre_minus_std4': float((jump['pre%d' % Kbest] - jump['std']).abs().mean()),
                          'mean_abs_pre_minus_stdbestK': float((jump['pre%d' % Kbest] - jump['std%d' % Kstd]).abs().mean())}
    # retire rule: last bin with gain >= 0.05 and z >= 2
    last_ok = None
    for (lo, hi) in BINS:
        g = gain[f'{lo}-{hi}']
        if g['gain'] >= 0.05 and g['z'] >= 2:
            last_ok = (lo, hi)
    out['retire'] = {'last_qualifying_bin': list(last_ok) if last_ok else None,
                     'N_ret_games_played': (last_ok[1] + 1) if last_ok else 0,
                     'rule': 'preseason term active while games played <= upper end of the last bin with gain >= 0.05 min and z >= 2'}
    with open(os.path.join(B.DATA, 'preseason_decay.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k not in ('gain_by_games_played',)}, indent=1, default=float))
    print(json.dumps({'taper': out['taper']}, indent=0))
    print(json.dumps({'vs_std_bestK': out['gain_vs_std_bestK'], 'jump': out['jump_at_n11']}, indent=1, default=float))
    print('\ngames played so far | rows | MAE std(K=4) | MAE pre(K=%d) | gain | se | z' % Kbest)
    for k, g in gain.items():
        print('%8s %7d  %.3f  %.3f  %+.3f  %.3f  %5.2f' % (k, g['rows'], g['mae_std'], g['mae_pre'], g['gain'], g['se'], g['z']))


if __name__ == '__main__':
    main()
