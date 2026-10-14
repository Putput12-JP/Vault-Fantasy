#!/usr/bin/env python3
"""NFL game model: do the starting quarterback's quality and injury-report absences improve it? Walk-forward, 2017-2025, against the closing spread.

Today the model handles one case: a backup quarterback (a flat points adjustment, build_game_model.py). The market also prices who the quarterback
is and who else is out. Two features, each built only from information available before kickoff:

  QB quality   Each quarterback's career EPA per dropback to date (nflverse play-by-play, games before this one), shrunk toward 0 by K dropbacks.
               Feature = (starter's rating - the team's established starter's rating), home minus away. The team rating already carries the
               established starter, so only a CHANGE in who plays moves it. Established = the most frequent starter over the last 24 games (>= 10 starts).
  Injuries     A "regular" is a player averaging 60%+ of his team's snaps over its previous 4 games (nflverse snap counts, quarterbacks left out).
               Out = listed Out or Doubtful on the game-week injury report (nflverse injuries). Feature = number of regulars out by unit
               (offensive line, receivers, tight end, running back, defensive line, linebackers, defensive backs), home minus away.

Rules set before the run, same shape as the earlier studies:
  Fit        ridge on the model's own miss (final margin minus the model's margin); the ridge strength and K are chosen on 2017-2021 by
             leave-one-season-out miss (root mean square of the final margin), never by pick record. 2022-2025 is read once with the 2017-2021 fit.
  Go / no-go GO only if the test miss falls by more than 2 standard errors of the paired difference AND the 3+ point pick record against the
             close is not worse than the baseline. Separately, a coefficient on the MARKET's miss more than 2 standard errors from zero is reported as
             a hypothesis (the market under-prices it), never as a shipped change.

Run: python3 scripts/nfl_qb_injury_study.py [--dir /tmp/nflst]     (pandas, numpy, pyarrow)
"""
import argparse, json, math, os, re, sys, urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_game_model as bgm
import nfl_special_teams_study as stu

REL = 'https://github.com/nflverse/nflverse-data/releases/download/{t}/{t}_{y}.parquet'
YEARS = list(range(2016, 2026))
TUNE, TEST = list(range(2017, 2022)), list(range(2022, 2026))
GROUPS = {'OL': {'T', 'G', 'C', 'OL', 'OT', 'OG'}, 'WR': {'WR'}, 'TE': {'TE'}, 'RB': {'RB', 'FB', 'HB'}, 'DL': {'DE', 'DT', 'NT', 'DL'},
          'LB': {'LB', 'ILB', 'OLB', 'MLB'}, 'DB': {'CB', 'S', 'DB', 'FS', 'SS'}}
POS2G = {p: g for g, ps in GROUPS.items() for p in ps}
REGULAR, TRAIL = 0.6, 4
KS, LAMS = (150, 300, 600), (1, 10, 100, 1000)


def get(tag, y, d):
    dest = f'{d}/{tag}_{y}.parquet'
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        with urllib.request.urlopen(urllib.request.Request(REL.format(t=tag, y=y), headers={'User-Agent': 'vault'}), timeout=600) as r, open(dest, 'wb') as f: f.write(r.read())
    return dest


def nm(s):
    s = re.sub(r"[.'\-]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def injury_features(d):
    """(season, week, team) -> {unit: regulars out}, plus how many regulars were out in all"""
    snaps = pd.concat([pd.read_parquet(get('snap_counts', y, d), columns=['season', 'week', 'player', 'position', 'team', 'offense_pct', 'defense_pct']) for y in YEARS])
    snaps['team'] = snaps.team.map(bgm.norm_team); snaps['n'] = snaps.player.map(nm); snaps['pct'] = snaps[['offense_pct', 'defense_pct']].max(axis=1).fillna(0)
    inj = pd.concat([pd.read_parquet(get('injuries', y, d), columns=['season', 'week', 'team', 'full_name', 'report_status']) for y in YEARS])
    inj = inj[inj.report_status.isin(['Out', 'Doubtful'])].copy(); inj['team'] = inj.team.map(bgm.norm_team); inj['n'] = inj.full_name.map(nm)
    out = {}
    for t, g in snaps.groupby('team'):
        g = g.sort_values(['season', 'week']); keys = g[['season', 'week']].drop_duplicates().itertuples(index=False, name=None)
        order = {k: i for i, k in enumerate(keys)}; g['gi'] = [order[(s, w)] for s, w in zip(g.season, g.week)]
        pv = g.pivot_table(index='gi', columns=['n', 'position'], values='pct', aggfunc='max').reindex(range(len(order))).fillna(0)
        roll = pv.shift(1).rolling(TRAIL, min_periods=2).mean()
        ti = inj[inj.team == t]
        for (s, w), gi in order.items():
            r = roll.iloc[gi]; reg = r[r >= REGULAR]
            names = {}
            for (n_, pos), v in reg.items():
                if pos == 'QB': continue
                names.setdefault(n_, POS2G.get(pos))
            o = ti[(ti.season == s) & (ti.week == w)]
            cnt = {k: 0 for k in GROUPS}
            for n_ in set(o.n):
                if names.get(n_): cnt[names[n_]] += 1
            out[(s, w, t)] = cnt
    return out


def qb_features(d, games, K):
    """(season, week, home, away) -> (starter - established) rating, home minus away, from career EPA per dropback to date shrunk by K dropbacks"""
    p = pd.concat([pd.read_parquet(f'{d}/pbp_{y}.parquet', columns=['season', 'week', 'passer_player_id', 'qb_dropback', 'epa']) for y in YEARS if os.path.exists(f'{d}/pbp_{y}.parquet')])
    p = p[(p.qb_dropback == 1) & p.passer_player_id.notna() & p.epa.notna()]
    wk = p.groupby(['season', 'week', 'passer_player_id']).agg(n=('epa', 'size'), s=('epa', 'sum')).reset_index().sort_values(['season', 'week'])
    byw = {k: g for k, g in wk.groupby(['season', 'week'])}
    cum, feat, recent = {}, {}, {}
    rate = lambda q: cum[q][1] / (cum[q][0] + K) if q in cum else 0.0
    weeks = {}
    for g in games:
        if g['season'] >= 2016: weeks.setdefault((g['season'], g['week']), []).append(g)
    for key in sorted(weeks):
        for g in weeks[key]:        # every game of a week is scored from ratings built BEFORE that week
            diffs = []
            for tk, qk in (('ht', 'hq'), ('at', 'aq')):
                est = None; h = recent.get(g[tk], [])
                if h:
                    best = max(set(h), key=h.count); est = best if h.count(best) >= 10 else None
                q = g[qk]; diffs.append(0.0 if (q is None or est is None) else rate(q) - rate(est))
            feat[(g['season'], g['week'], g['ht'], g['at'])] = diffs[0] - diffs[1]
        for g in weeks[key]:
            if g['played']:
                for tk, qk in (('ht', 'hq'), ('at', 'aq')):
                    if g[qk]: recent[g[tk]] = (recent.get(g[tk], []) + [g[qk]])[-24:]
        nxt = byw.get(key)
        if nxt is not None:
            for r in nxt.itertuples():
                c = cum.get(r.passer_player_id, (0, 0.0)); cum[r.passer_player_id] = (c[0] + r.n, c[1] + r.s)
    return feat


def ridge_fit(X, y, lam):
    mu, sd = X.mean(0), X.std(0) + 1e-9; Z = (X - mu) / sd
    b = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return lambda Xn: y.mean() + ((Xn - mu) / sd) @ b, b / sd


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/nflst'); a = ap.parse_args(); os.makedirs(a.dir, exist_ok=True)
    for y in YEARS: stu.get(y, a.dir)
    base = stu.baseline(); base['key'] = list(zip(base.season, base.week, base.home, base.away))
    games = bgm.fetch_games()
    inj = injury_features(a.dir)
    base = base[base.season >= 2017].copy()
    for g in GROUPS:
        base[g] = [inj.get((s, w, h), {}).get(g, 0) - inj.get((s, w, aw), {}).get(g, 0) for s, w, h, aw in zip(base.season, base.week, base.home, base.away)]
    cover = float(np.mean([any(inj.get((s, w, t), {}).values()) for s, w, h, aw in zip(base.season, base.week, base.home, base.away) for t in (h, aw)]))
    print(f'games {len(base)}, share of team-games with a regular listed out {cover:.2f}')
    qb = {K: qb_features(a.dir, games, K) for K in KS}
    nz = [qb[KS[0]].get(k, 0.0) for k in base.key]
    print(f'games where a starter differs from the established one: {sum(v != 0 for v in nz)} of {len(nz)}, sd of the feature when it does {np.std([v for v in nz if v != 0]):.3f}')
    base['miss'] = base.result - base.pm
    def X(df, K, cols): return np.column_stack([df[c].values for c in cols if c != 'QB'] + ([df.key.map(qb[K]).fillna(0).values] if 'QB' in cols else []))
    variants = {'QB only': ['QB'], 'Injuries only': list(GROUPS), 'QB + injuries': ['QB'] + list(GROUPS)}
    tune = base[base.season.isin(TUNE)]; test = base[base.season.isin(TEST)]
    res = {}
    for name, cols in variants.items():
        best = None
        for K in (KS if 'QB' in cols else (KS[0],)):
            for lam in LAMS:      # leave-one-season-out on the tuning seasons
                err = []
                for hold in TUNE:
                    trn, tst = tune[tune.season != hold], tune[tune.season == hold]
                    f, _ = ridge_fit(X(trn, K, cols), trn.miss.values, lam); err += list(tst.miss.values - f(X(tst, K, cols)))
                s = math.sqrt(np.mean(np.square(err)))
                if best is None or s < best[0]: best = (s, K, lam)
        _, K, lam = best
        f, coef = ridge_fit(X(tune, K, cols), tune.miss.values, lam)
        t2 = test.copy(); t2['new'] = t2.pm + (f(X(t2, K, cols)))
        e0, e1 = (t2.result - t2.pm).values, (t2.result - t2.new).values
        dd = e0 ** 2 - e1 ** 2; se = dd.std(ddof=1) / math.sqrt(len(dd))
        # the market's miss on the same features (does the market under-price it?), plain OLS on the test seasons
        Xm = X(t2, K, cols); ym = (t2.result - t2.spread).values; ok = ~np.isnan(ym); Xm, ym = Xm[ok], ym[ok]
        Xc = np.column_stack([np.ones(len(Xm)), Xm]); bh = np.linalg.lstsq(Xc, ym, rcond=None)[0]; resid = ym - Xc @ bh
        cov = np.linalg.inv(Xc.T @ Xc) * (resid @ resid / (len(ym) - Xc.shape[1])); tm = bh[1:] / np.sqrt(np.diag(cov)[1:])
        names = [c for c in cols if c != 'QB'] + (['QB'] if 'QB' in cols else [])
        o = dict(K=K, lam=lam, tune_cv_miss=round(best[0], 3), tune_baseline=round(math.sqrt(np.mean(tune.miss.values ** 2)), 3), n=len(t2), miss_base=round(stu.rmse(e0), 3), miss_new=round(stu.rmse(e1), 3),
                 market_miss=round(stu.rmse(t2.result - t2.spread), 3), paired_t=round(float(dd.mean() / se), 2), coef=dict(zip(names, [round(float(c), 3) for c in coef])),
                 market_t=dict(zip(names, [round(float(c), 2) for c in tm])), picks_base={str(t): stu.picks(t2, 'pm', t) for t in (1.5, 3, 5)}, picks_new={str(t): stu.picks(t2, 'new', t) for t in (1.5, 3, 5)})
        res[name] = o; print(name, json.dumps(o))
    json.dump(res, open(os.path.join(a.dir, 'qb_injury_result.json'), 'w'), indent=1)


if __name__ == '__main__':
    sys.exit(main())
