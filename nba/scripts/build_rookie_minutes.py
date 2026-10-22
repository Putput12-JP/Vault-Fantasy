#!/usr/bin/env python3
"""
docs/rookie-minutes-test.md (rules fixed there before any result was computed).

Does a rookie's first-half preseason minutes predict his early-season minutes beyond his draft-pick bucket?
Leave-one-class-out over the 2023, 2024 and 2025 draft classes (seasons 2024 to 2026).

  nba/.venv/bin/python nba/scripts/build_rookie_minutes.py      # -> data/rookie_minutes.json
"""
import csv, io, json, os, sys, urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_preseason_signals as B
import build_preseason_decay as DC

BUCKETS = [(1, 3), (4, 10), (11, 20), (21, 30), (31, 45), (46, 60)]        # PICK_BUCKETS in build_player_projections.py
CLASSES = {2024: 2023, 2025: 2024, 2026: 2025}                              # season -> draft class
K_GRID = (2, 4, 8, 12)
MAX_N = 30


def bucket(pick):
    for lo, hi in BUCKETS:
        if lo <= pick <= hi:
            return f'{lo}-{hi}'
    return None


def draft(year):
    path = os.path.join(B.RAW, f'draft_{year}.csv')
    if not os.path.exists(path):
        url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_draft/draft_{year}.csv'
        body = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'vault-nba'}), timeout=60).read()
        open(path, 'wb').write(body)
    d = pd.read_csv(path)
    return {C.name_key(r.athlete_display_name): int(r.overall_pick) for r in d.itertuples()}   # the draft file's ids are not ESPN athlete ids: join by name, as the Lab does


def main():
    P, T, bad = B.load_pre()
    pre = B.agg_pre(P, T)
    rows, allrook = [], []
    for S, cls in CLASSES.items():
        picks = draft(cls)
        rs = B.load_rs(S)
        early = B.agg_rs(rs[rs.tgn <= 15])
        nm = rs.drop_duplicates('pid').set_index('pid').athlete_display_name.map(C.name_key)
        ps = pre[pre.season == S].set_index('pid')
        pn = ps['name'].map(C.name_key)
        picks_by_pid = {pid: picks[k] for pid, k in nm.items() if k in picks}
        picks_pre = {pid: picks[k] for pid, k in pn.items() if k in picks}
        for pid, pick in picks_by_pid.items():
            if pid in early.index:
                allrook.append({'S': S, 'pid': pid, 'pick': pick, 'bucket': bucket(pick), 'E_mpg': early.loc[pid, 'mpg'],
                                'E_gp': early.loc[pid, 'gp']})
        for pid, pick in picks_pre.items():
            if pid in ps.index and pid in early.index:
                r = ps.loc[pid]
                rows.append({'S': S, 'pid': pid, 'name': r['name'], 'pick': pick, 'bucket': bucket(pick), 'box_min': r.box_min,
                             'n': r.n, 'mpg_1h': r.mpg_1h, 'mpg_total': r.mpg_total, 'starts': r.starts,
                             'E_mpg': early.loc[pid, 'mpg'], 'E_gp': early.loc[pid, 'gp']})
    A = pd.DataFrame(allrook)
    D = pd.DataFrame(rows)
    out = {'drafted_with_early_games': int(len(A)), 'preseason_ge40_before_gp_rule': int((D.box_min >= 40).sum())}
    D = D[(D.box_min >= 40)]
    out['excluded_under_5_early_games'] = int((D.E_gp < 5).sum())
    D = D[D.E_gp >= 5].copy().reset_index(drop=True)
    out['n'] = int(len(D)); out['by_class'] = {int(k): int(v) for k, v in D.S.value_counts().sort_index().items()}

    # ---- leave-one-class-out predictions
    def bucket_means(train_S):
        a = A[A.S.isin(train_S)]
        return a.groupby('bucket').E_mpg.mean().to_dict()

    for c in ('R0', 'R1', 'R2', 'R3'):
        D[c] = np.nan
    for S in CLASSES:
        trS = [x for x in CLASSES if x != S]
        bm = bucket_means(trS)
        D['bm'] = D.bucket.map(bm)
        tr, te = D[D.S.isin(trS)], D[D.S == S]
        D.loc[te.index, 'R0'] = te.bm
        for name, feats in (('R1', ['bm', 'mpg_1h']), ('R2', ['mpg_1h']), ('R3', ['bm', 'mpg_total'])):
            b = B.ols(tr[feats].values, tr.E_mpg.values)
            D.loc[te.index, name] = B.pred(b, te[feats].values)
    err = {c: (D[c] - D.E_mpg).abs().values for c in ('R0', 'R1', 'R2', 'R3')}
    out['mae'] = {c: float(e.mean()) for c, e in err.items()}
    out['corr'] = {'1H': float(np.corrcoef(D.mpg_1h, D.E_mpg)[0, 1]), 'total': float(np.corrcoef(D.mpg_total, D.E_mpg)[0, 1]),
                   'bucket_mean': float(np.corrcoef(D.R0, D.E_mpg)[0, 1])}
    comp = {}
    for a, b_ in (('R0', 'R1'), ('R3', 'R1'), ('R0', 'R3'), ('R0', 'R2')):
        m, se, z = B.paired(D, err[a], err[b_])
        comp[f'{a} vs {b_}'] = {'mae_gain': m, 'se': se, 'z': z}
    out['paired'] = comp
    out['by_class_mae'] = {int(S): {c: float((D[D.S == S][c] - D[D.S == S].E_mpg).abs().mean()) for c in ('R0', 'R1')} for S in CLASSES}
    g = comp['R0 vs R1']; g3 = comp['R3 vs R1']
    out['pass'] = bool(g['mae_gain'] >= 0.5 and g['z'] >= 2 and g3['z'] >= 2)
    # final fit on all three classes, for the live read and for shipping
    bm_all = bucket_means(list(CLASSES))
    D['bm'] = D.bucket.map(bm_all)
    b1 = B.ols(D[['bm', 'mpg_1h']].values, D.E_mpg.values)
    out['fit_R1'] = [float(x) for x in b1]
    out['bucket_means'] = {k: round(v, 2) for k, v in bm_all.items()}
    # what the model says about starters and how many are big movers
    D['d'] = B.pred(b1, D[['bm', 'mpg_1h']].values) - D.bm
    out['spread_of_R1_minus_R0'] = {'sd': float(D.d.std()), 'abs_mean': float(D.d.abs().mean())}

    # ---- decay replay (only if the pass rule passes)
    if out['pass']:
        mins = {S: DC.game_minutes(S)[0] for S in CLASSES}
        recs = []
        for r in D.itertuples():
            g_ = mins[r.S].get(r.pid)
            if g_ is None:
                continue
            for n, x in enumerate(g_[:80]):
                ew = None
                if n:
                    ew = g_[0]
                    for y in g_[1:n]:
                        ew += DC.ALPHA * (y - ew)
                bl = lambda st, K: st if n == 0 else (n * ew + K * st) / (n + K)
                row = {'pid': r.pid, 'S': r.S, 'n': n, 'y': x, 'std': bl(r.R0, 4)}
                for K in K_GRID:
                    row[f'pre{K}'] = bl(r.R1, K)
                recs.append(row)
        R = pd.DataFrame(recs)
        for c in [c for c in R.columns if c.startswith(('std', 'pre'))]:
            R['e_' + c] = (R[c] - R.y).abs()
        early_ = R[R.n <= MAX_N]
        Kb = min(K_GRID, key=lambda K: early_[f'e_pre{K}'].mean())
        out['K_rookie'] = int(Kb)
        out['mae_by_K'] = {str(K): float(early_[f'e_pre{K}'].mean()) for K in K_GRID}
        gain, rng = {}, np.random.default_rng(20261020)
        for lo, hi in DC.BINS:
            sub = R[(R.n >= lo) & (R.n <= hi)]
            diff = (sub.e_std - sub[f'e_pre{Kb}']).values
            idx = sub.groupby('pid').indices
            ks = list(idx)
            sums = np.array([diff[idx[k]].sum() for k in ks]); cnt = np.array([len(idx[k]) for k in ks])
            boots = [sums[p].sum() / cnt[p].sum() for p in (rng.integers(0, len(ks), len(ks)) for _ in range(2000))]
            se = float(np.std(boots))
            gain[f'{lo}-{hi}'] = {'rows': int(len(sub)), 'players': len(ks), 'mae_std': float(sub.e_std.mean()),
                                  'mae_pre': float(sub[f'e_pre{Kb}'].mean()), 'gain': float(diff.mean()), 'se': se,
                                  'z': float(diff.mean() / se) if se else 0.0}
        out['gain_by_games_played'] = gain
        ok = [hi for (lo, hi) in DC.BINS if gain[f'{lo}-{hi}']['gain'] >= 0.05 and gain[f'{lo}-{hi}']['z'] >= 2]
        out['N_ret_games_played'] = (max(ok) + 1) if ok else 0          # the literal rule: 201 = never retires (amendment 1)
        ok10 = [hi for (lo, hi) in DC.BINS if gain[f'{lo}-{hi}']['gain'] >= 0.10 and gain[f'{lo}-{hi}']['z'] >= 2]
        out['N_ret_materiality_0.10'] = (max(ok10) + 1) if ok10 else 0   # amended rule, docs/rookie-minutes-test.md: 26
        out['taper_from'] = out['N_ret_materiality_0.10'] - 6            # linear fade over the five games before it

    # ---- live read: the 2026-27 class
    pk = draft(2026)
    ps = pre[pre.season == 2027].set_index('pid')
    live = []
    pn27 = ps['name'].map(C.name_key)
    for pid, pick in {p: pk[k] for p, k in pn27.items() if k in pk}.items():
        if ps.loc[pid, 'box_min'] >= 40:
            r = ps.loc[pid]
            bm = bm_all.get(bucket(pick))
            live.append({'name': r['name'], 'pick': pick, 'team': str(r['team']), 'n': int(r.n), 'h1_mpg': round(float(r.mpg_1h), 1),
                         'h1_min': round(float(r.h1_min), 1), 'starts': int(r.starts), 'lab_today': round(bm, 1),
                         'with_preseason': round(float(B.pred(b1, [[bm, r.mpg_1h]])[0]), 1)})
    live.sort(key=lambda x: -abs(x['with_preseason'] - x['lab_today']))
    out['live'] = live
    with open(os.path.join(B.DATA, 'rookie_minutes.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k not in ('live', 'gain_by_games_played')}, indent=1, default=float))
    if 'gain_by_games_played' in out:
        for k, g in out['gain_by_games_played'].items():
            print('%8s rows %5d  std %.2f pre %.2f gain %+.3f se %.3f z %5.2f' % (k, g['rows'], g['mae_std'], g['mae_pre'], g['gain'], g['se'], g['z']))
    print('\nlive rookies (%d):' % len(live))
    for x in live[:14]:
        print(x)


if __name__ == '__main__':
    main()
