#!/usr/bin/env python3
"""
Minutes model challenger: gradient boosting vs the linear model, on the SAME pre-tip features.

Why: minutes is the biggest error term in every prop (RMSE ~6 min; points RMSE is 5.0 even with TRUE minutes). The shipped model is an
EWMA plus linear deltas (vacated minutes, blowout, back-to-back). Role changes, rotation shifts and blowout x starter
interactions are nonlinear. A UBC-MDS LightGBM minutes model reports R2 0.65 (docs/reverse-engineering-targets.md).

Protocol
  features   known at tip from box scores only: three EWMAs of minutes, last game, last-5 mean/std, starter rate, games played,
             rest days, back-to-back, games in last 7 days, home, position, team's vacated minutes (ORACLE: teammates who did
             not play, as the tune seasons of the shipped model do), the game model's expected margin.
  target     minutes, players who played.
  split      train 2022-23..2024-25 (season ids 2023-2025), test 2025-26 (2026). No injury report is available in this sandbox,
             so both models use oracle absences and are comparable to each other, NOT to the 6.065 RMSE in minutes-model-v3.md.
  models     ridge on the linear features (stand-in for the shipped model), same ridge + role features, LightGBM on everything.
  pass rule  LightGBM beats the linear model by >= 1.5% RMSE and the paired t-stat on squared error is >= 3.

  python3 nba/scripts/build_minutes_gbm.py
"""
import datetime as dt, math, os, sys
from collections import defaultdict, deque
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM

SEASONS = [2022, 2023, 2024, 2025, 2026]
TRAIN, TEST = (2023, 2024, 2025), 2026
ALPHAS = (0.1, 0.2, 0.4)
ROT_MIN, ROT_DAYS = 10.0, 21
STATS = ('pts', 'reb', 'ast', 'fg3m')
STATCOL = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', 'fg3m': 'three_point_field_goals_made'}
RATE_A = 0.07
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-gbm.md')


def build_rows(box, margins):
    pl = {}                                                   # aid -> state
    team_games = defaultdict(deque)                           # team -> recent tip times
    rows = []
    for g in C.games(SEASONS):
        recs = box.get(g['game_id'], [])
        if not recs:
            continue
        tip = g['tip']
        played_ids = {r['athlete_id'] for r in recs if r['played']}
        mg = margins.get(g['game_id'])
        for team, home in ((g['home'], 1), (g['away'], 0)):
            lim = tip - dt.timedelta(days=ROT_DAYS)
            rot = {a: p for a, p in pl.items() if p['team'] == team and p['ew'][1] >= ROT_MIN and p['last'] >= lim}
            out = {a for a in rot if a not in played_ids}
            tg = team_games[team]
            last_team = tg[-1] if tg else None
            b2b = 1.0 if last_team and (tip - last_team) < dt.timedelta(hours=30) else 0.0
            g7 = sum(1 for t in tg if tip - t < dt.timedelta(days=7))
            rest = min(10.0, (tip - last_team).total_seconds() / 86400) if last_team else 5.0
            for r in recs:
                if r['team'] != team or not r['played'] or r['athlete_id'] not in pl:
                    continue
                p = pl[r['athlete_id']]
                if p['n'] < 5:
                    continue
                grp = MM.group(r['pos'])
                vs = sum(q['ew'][1] for a, q in rot.items() if a in out and a != r['athlete_id'] and q['pos'] == grp)
                vo = sum(q['ew'][1] for a, q in rot.items() if a in out and a != r['athlete_id'] and q['pos'] != grp)
                last5 = list(p['h'])
                days_off = min(60.0, (tip - p['last']).total_seconds() / 86400)
                rows.append(dict(
                    season=g['season'], gid=g['game_id'], aid=r['athlete_id'], y=r['minutes'],
                    ew1=p['ew'][0], ew2=p['ew'][1], ew3=p['ew'][2], last=p['lastm'], m5=float(np.mean(last5)),
                    sd5=float(np.std(last5)), sdm_ewma=math.sqrt(p['sq']), st=p['st'], was_start=p['last_start'], n=min(p['n'], 200),
                    rest=rest, b2b=b2b, g7=g7, home=home, days_off=days_off, vs=vs, vo=vo,
                    absm=abs(mg) if mg is not None else 6.0, sgnm=(mg if home else -mg) if mg is not None else 0.0,
                    pos_g=1.0 if grp == 'G' else 0.0, pos_c=1.0 if grp == 'C' else 0.0, n_out=len(out),
                    **{f'rt_{k}': p['rt'][k] for k in STATS}, **{f'act_{k}': r[STATCOL[k]] for k in STATS}))
        # update state after the game
        for r in recs:
            if not r['played']:
                continue
            a = r['athlete_id']
            p = pl.get(a)
            if p is None:
                pl[a] = {'ew': [r['minutes']] * 3, 'n': 1, 'team': r['team'], 'last': tip, 'pos': MM.group(r['pos']),
                         'st': 1.0 if r['starter'] else 0.0, 'lastm': r['minutes'], 'last_start': 1.0 if r['starter'] else 0.0,
                         'h': deque([r['minutes']], maxlen=5), 'sq': 36.0,
                         'rt': {k: r[STATCOL[k]] / max(r['minutes'], 1.0) for k in STATS}}
            else:
                k = max(0.0, 0)
                p['sq'] += 0.1 * ((r['minutes'] - p['ew'][1]) ** 2 - p['sq'])
                p['ew'] = [e + max(al, 1 / (p['n'] + 1)) * (r['minutes'] - e) for e, al in zip(p['ew'], ALPHAS)]
                p['st'] += max(0.2, 1 / (p['n'] + 1)) * ((1.0 if r['starter'] else 0.0) - p['st'])
                p['lastm'], p['last_start'] = r['minutes'], 1.0 if r['starter'] else 0.0
                p['h'].append(r['minutes'])
                w = min(1.0, r['minutes'] / 20.0)
                for k in STATS:
                    p['rt'][k] += max(RATE_A, 1 / (p['n'] + 9)) * w * (r[STATCOL[k]] / max(r['minutes'], 1.0) - p['rt'][k])
                p['n'] += 1
                p['team'], p['last'], p['pos'] = r['team'], tip, MM.group(r['pos'])
        for t in (g['home'], g['away']):
            team_games[t].append(tip)
            while len(team_games[t]) > 12:
                team_games[t].popleft()
    return pd.DataFrame(rows)


def main():
    import lightgbm as lgb
    box = C.player_games(SEASONS)
    print('game model margins...', flush=True)
    margins = MM.expected_margins(box)
    df = build_rows(box, margins)
    df = df[df.y > 0]
    L = ['# Minutes challenger: gradient boosting vs linear', '',
         'Oracle absences (who actually sat); no injury report in this sandbox, so numbers compare models to each other, not to',
         'minutes-model-v3.md. t = paired mean(e_base^2 - e_model^2) / s.e. against the first row. "Stat RMSE" multiplies each model\'s',
         'minutes by the same per-minute rate (EWMA 0.07), so only the minutes differ.', '']
    lin_cols = ['ew2', 'vs', 'vo', 'absm', 'b2b']
    lin2 = lin_cols + ['ew1', 'ew3', 'last', 'm5', 'st', 'was_start', 'rest', 'g7', 'home', 'days_off', 'pos_g', 'pos_c']
    allc = lin2 + ['sd5', 'n', 'sgnm', 'n_out']
    verdicts = []
    for train, test in (((2023, 2024, 2025), 2026), ((2023, 2024), 2025)):
        tr, te = df[df.season.isin(train)], df[df.season == test]

        def ridge(cols, lam=1.0):
            X = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols])
            b = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ tr.y.values)
            return np.column_stack([np.ones(len(te))] + [te[c] for c in cols]) @ b

        res = {'ridge, shipped-style features': ridge(lin_cols), 'ridge, + role/rest/form features': ridge(lin2)}
        gb = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=60, subsample=0.8,
                               subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, verbose=-1)
        gb.fit(tr[allc], tr.y)
        res['LightGBM, all features'] = gb.predict(te[allc])
        y = te.y.values
        base = res['ridge, shipped-style features']
        L += [f'## Train {train}, test {test}: {len(te):,} player-games', '',
              '| Model | MAE | RMSE | R2 | Misses 8+ min | vs first | t | pts RMSE | reb RMSE | ast RMSE | 3PM RMSE |', '|---|---|---|---|---|---|---|---|---|---|---|']
        out = {}
        for name, pr in res.items():
            e = y - pr
            d = (y - base) ** 2 - e ** 2
            t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d))) if d.std() > 0 else 0.0
            rm = math.sqrt((e ** 2).mean())
            out[name] = (rm, t)
            st = [math.sqrt(np.mean((pr * te[f'rt_{k}'].values - te[f'act_{k}'].values) ** 2)) for k in STATS]
            L.append(f'| {name} | {np.abs(e).mean():.3f} | {rm:.3f} | {1 - (e ** 2).mean() / y.var():.3f} | {(np.abs(e) >= 8).mean() * 100:.1f}% | '
                     f'{100 * (1 - rm / math.sqrt(((y - base) ** 2).mean())):+.2f}% | {t:+.2f} | ' + ' | '.join(f'{v:.3f}' for v in st) + ' |')
        g_rm, g_t = out['LightGBM, all features']
        gain = 100 * (1 - g_rm / out['ridge, shipped-style features'][0])
        verdicts.append(gain >= 1.5 and g_t >= 3)
        L += ['', f'Gain over shipped-style linear {gain:+.2f}%, t {g_t:+.2f}. Nonlinearity alone (vs the richer ridge): '
                  f'{100 * (1 - g_rm / out["ridge, + role/rest/form features"][0]):+.2f}%.', '']
    tot = sum(gb.booster_.feature_importance('gain'))
    imp = sorted(zip(allc, gb.booster_.feature_importance('gain')), key=lambda kv: -kv[1])[:8]
    L += ['Top features by gain (last fit): ' + ', '.join(f'{k} ({v / tot * 100:.0f}%)' for k, v in imp), '',
          'Pass rule: LightGBM beats the shipped-style linear model by >= 1.5% RMSE with t >= 3 on BOTH holdouts. Result: '
          f'**{"PASS" if all(verdicts) else "FAIL"}**.', '']
    open(OUT_MD, 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
