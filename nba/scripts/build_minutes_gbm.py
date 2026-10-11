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
import minutes_gbm as MG

SEASONS = [2022, 2023, 2024, 2025, 2026]
TRAIN, TEST = (2023, 2024, 2025), 2026
ALPHAS = (0.1, 0.2, 0.4)
ROT_MIN, ROT_DAYS = 10.0, 21
STATS = ('pts', 'reb', 'ast', 'fg3m')
STATCOL = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', 'fg3m': 'three_point_field_goals_made'}
RATE_A = 0.07
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-gbm.md')


def build_rows(box, margins):
    """One row per player-game (features from minutes_gbm.py, the same code live pricing runs), plus evaluation-only columns."""
    pl, side = {}, {}                                         # aid -> minutes_gbm state; aid -> {rt, sq} evaluation-only state
    team_tips = defaultdict(list)
    rows = []
    for g in C.games(SEASONS):
        recs = box.get(g['game_id'], [])
        if not recs:
            continue
        tip = g['tip'].timestamp()
        played_ids = {r['athlete_id'] for r in recs if r['played']}
        mg = margins.get(g['game_id'])
        for team, home in ((g['home'], 1), (g['away'], 0)):
            rot = MG.rotation(pl, team, tip)
            out = {a for a in rot if a not in played_ids}                 # ORACLE absences
            ctx = MG.team_context(team_tips[team], tip)
            for r in recs:
                if r['team'] != team or not r['played'] or r['athlete_id'] not in pl:
                    continue
                p = pl[r['athlete_id']]
                if p['n'] < 5:
                    continue
                x = MG.features(p, r['athlete_id'], rot, out, tip, ctx, home, mg, p['pos'])      # last known position, all live has
                sd = side[r['athlete_id']]
                rows.append(dict(zip(MG.COLS, x), season=g['season'], gid=g['game_id'], aid=r['athlete_id'], y=r['minutes'],
                                 sdm_ewma=math.sqrt(sd['sq']),
                                 **{f'rt_{k}': sd['rt'][k] for k in STATS}, **{f'act_{k}': r[STATCOL[k]] for k in STATS}))
        for r in recs:
            if not r['played']:
                continue
            a = r['athlete_id']
            p = pl.get(a)
            if p is None:
                pl[a] = MG.new_player(r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
                side[a] = {'sq': 36.0, 'rt': {k: r[STATCOL[k]] / max(r['minutes'], 1.0) for k in STATS}}
            else:
                sd = side[a]
                sd['sq'] += 0.1 * ((r['minutes'] - p['ew'][1]) ** 2 - sd['sq'])
                w = min(1.0, r['minutes'] / 20.0)
                for k in STATS:
                    sd['rt'][k] += max(RATE_A, 1 / (p['n'] + 9)) * w * (r[STATCOL[k]] / max(r['minutes'], 1.0) - sd['rt'][k])
                MG.update_player(p, r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
        for t in (g['home'], g['away']):
            team_tips[t].append(tip)
            del team_tips[t][:-12]
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
