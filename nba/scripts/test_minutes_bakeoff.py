#!/usr/bin/env python3
"""
Minutes bake-off on 2025-26. Rule: docs/minutes-bakeoff.md (committed before this file ran). Nothing here changes pricing.

  python3 nba/scripts/test_minutes_bakeoff.py     needs lightgbm; reads the rotation pool cache (/tmp/rotation_pool.json, built by test_rotation_minutes.py)

A v2 walk minutes | C3 rotation model | G LightGBM conditional minutes (refit on 2023-2025, no oracle absences) | GP = G x C3 P(plays), pool rescaled to T expected.
"""
import json, math, os, statistics as st, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM
import build_minutes_spread as SP
import minutes_gbm as MG
import rotation_minutes as RM
import test_rotation_minutes as TR

CACHE = os.environ.get('ROTATION_CACHE', '/tmp/rotation_pool.json')
OUT_JSON = os.path.join(HERE, '..', 'data', 'minutes_bakeoff.json')
OUT_MD = os.path.join(HERE, '..', 'docs', 'minutes-bakeoff-results.md')
SEASONS = [2022, 2023, 2024, 2025, 2026]
TRAIN, TEST = (2023, 2024, 2025), 2026
STATS = ['pts', 'reb', 'ast', '3pm']
CANDS = ['A', 'C3', 'G', 'GP']


def gbm_features(pool):
    """Walk the games once; for every pool row set r['gx'] (feature vector) and r['gn'] (his games before this one), from state BEFORE the game.
    Out = rotation players (10+ ewma minutes, played within 21 days) who are not in that game's pool: the pool already drops Out players."""
    box = C.player_games(SEASONS)
    by = defaultdict(list)
    for r in pool:
        by[(r['gid'], r['team'])].append(r)
    pl, tips = {}, defaultdict(list)
    for g in C.games(SEASONS):
        recs = box.get(g['game_id'], [])
        if not recs:
            continue
        tip = g['tip'].timestamp()
        for team, home in ((g['home'], 1), (g['away'], 0)):
            rows = by.get((int(g['game_id']), team))
            if not rows:
                continue
            ids = {r['aid'] for r in rows}
            rot = MG.rotation(pl, team, tip)
            out = {a for a in rot if a not in ids}
            ctx = MG.team_context(tips[team], tip)
            for r in rows:
                p = pl.get(r['aid'])
                r['gx'], r['gn'] = (MG.features(p, r['aid'], rot, out, tip, ctx, home, r['e'], p['pos']), p['n']) if p else (None, 0)
        for r in recs:
            if not r['played']:
                continue
            p = pl.get(r['athlete_id'])
            if p is None:
                pl[r['athlete_id']] = MG.new_player(r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
            else:
                MG.update_player(p, r['minutes'], r['starter'], r['team'], tip, MM.group(r['pos']))
        for t in (g['home'], g['away']):
            tips[t].append(tip)
            del tips[t][:-12]


def fit_predict(pool):
    import lightgbm as lgb
    tr = [r for r in pool if r['season'] in TRAIN and r['played'] and r['min'] > 0 and r['gx'] is not None and r['gn'] >= 5]
    gb = lgb.LGBMRegressor(**SP.MEAN_KW).fit([r['gx'] for r in tr], [r['min'] for r in tr])
    te = [r for r in pool if r['season'] == TEST]
    ok = [r for r in te if r['gx'] is not None]
    for r, v in zip(ok, gb.predict([r['gx'] for r in ok])):
        r['G'] = max(0.0, min(48.0, float(v)))
    for r in te:
        r.setdefault('G', r['pm'])                     # no history on the team's state: v2's number
    return len(tr), len(ok), len(te)


def score(te, model):
    groups = defaultdict(list)
    for r in te:
        groups[(r['gid'], r['team'])].append(r)
    for rs in groups.values():
        res = RM.score_pool(model, rs)
        for r, s in zip(rs, res):
            r['C3'], r['p'], r['p_rot'] = s['min'], s['p_plays'], s['p_rot']
            r['A'] = r['pm']
        gp = RM.rescale(list(zip([r['p'] for r in rs], [r['G'] for r in rs])), model['T'])
        for r, v in zip(rs, gp):
            r['GP'] = v
    return groups


def cluster_t(rows, f):
    """Paired t on game means of f(row) (game is the unit)."""
    g = defaultdict(list)
    for r in rows:
        g[r['gid']].append(f(r))
    m = [st.mean(v) for v in g.values()]
    return st.mean(f(r) for r in rows), (st.mean(m) / (st.stdev(m) / math.sqrt(len(m))) if len(m) > 2 and st.stdev(m) > 0 else 0.0), len(m)


def compute():
    """The 2025-26 pool scored by A, C3, G and GP -> (te rows, groups, recs, model, counts). Rows carry gid, aid, pm (v2), C3, G, GP, p."""
    pool = json.load(open(CACHE))
    recs = pool['recs']
    pool = TR.add_history(pool['pool'])
    gbm_features(pool)
    ntr, nok, nte = fit_predict(pool)
    model = json.load(open(os.path.join(HERE, '..', 'data', 'rotation_minutes_model.json')))
    te = [r for r in pool if r['season'] == TEST]
    groups = score(te, model)
    return te, groups, recs, model, (ntr, nok, nte)


def main():
    te, groups, recs, model, (ntr, nok, nte) = compute()
    pl = [r for r in te if r['played'] and r['min'] > 0]
    res = {'fit_rows': ntr, 'test_rows': nte, 'test_played': len(pl), 'gbm_scored': nok, 'T': model['T']}

    # 1. minutes on players who played
    m1 = {}
    for k in CANDS:
        e = [r[k] - r['min'] for r in pl]
        m1[k] = {'mae': round(st.mean(abs(x) for x in e), 4), 'rmse': round(math.sqrt(st.mean(x * x for x in e)), 4), 'bias': round(st.mean(e), 3), 'miss8': round(sum(abs(x) >= 8 for x in e) / len(e), 4)}
    for k in CANDS[1:]:
        d, t, n = cluster_t(pl, lambda r: abs(r['A'] - r['min']) - abs(r[k] - r['min']))
        m1[k]['gain_vs_v2'], m1[k]['t_vs_v2'], m1[k]['games'] = round(d, 4), round(t, 2), n
    d, t, _ = cluster_t(pl, lambda r: abs(r['C3'] - r['min']) - abs(r['GP'] - r['min']))
    m1['GP']['gain_vs_c3'], m1['GP']['t_vs_c3'] = round(d, 4), round(t, 2)
    res['played'] = m1

    # 2. top 8 bias by pool size
    b = {}
    for name, f in (('size_le_12', lambda z: z <= 12), ('size_13_14', lambda z: 13 <= z <= 14), ('size_ge_15', lambda z: z >= 15)):
        sel = [r for r in pl if r['rank'] <= 8 and f(r['size'])]
        b[name] = {'n': len(sel), **{k: round(st.mean(r[k] - r['min'] for r in sel), 3) for k in CANDS}}
    res['top8_bias'] = b

    # 3. props proxy: mu_new = mu x new / pm
    rmap = {(r['gid'], r['aid']): r for r in pl}
    pr = {s: {k: [] for k in CANDS} for s in STATS}
    for x in recs:
        r = rmap.get((x['gid'], x['aid']))
        if not r or r['pm'] <= 0:
            continue
        for s in STATS:
            for k in CANDS:
                pr[s][k].append(abs(x['mu'][s] * r[k] / r['pm'] - x['y'][s]))
    res['props_mae'] = {s: {'n': len(pr[s]['A']), **{k: round(st.mean(pr[s][k]), 4) for k in CANDS}} for s in STATS}

    # 4. expected minutes over all pool rows (DNP = 0); v2 and G get C3's P(plays)
    ex = {}
    for k in CANDS:
        ex[k] = round(st.mean(abs(r['p'] * r[k] - (r['min'] if r['played'] else 0.0)) for r in te), 4)
    res['expected_mae'] = ex
    res['expected_gain_vs_v2'] = {k: dict(zip(('gain', 't', 'games'), map(lambda v: round(v, 4), cluster_t(te, lambda r: abs(r['p'] * r['A'] - (r['min'] if r['played'] else 0.0)) - abs(r['p'] * r[k] - (r['min'] if r['played'] else 0.0)))))) for k in CANDS[1:]}

    # 5. team totals and ghost mass
    tot = {}
    for k in CANDS:
        s_cond = [sum(r[k] for r in rs) for rs in groups.values()]
        s_exp = [sum(r['p'] * r[k] for r in rs) for rs in groups.values()]
        s_dnp = [sum(r[k] for r in rs if not r['played']) for rs in groups.values()]
        tot[k] = {'if_plays_sum': round(st.mean(s_cond), 1), 'expected_sum': round(st.mean(s_exp), 1), 'minutes_on_dnp': round(st.mean(s_dnp), 1)}
    tot['actual_sum'] = round(st.mean(sum(r['min'] for r in rs if r['played']) for rs in groups.values()), 1)
    tot['teams'] = len(groups)
    res['team_totals'] = tot

    # rule verdict
    v2 = m1['A']
    r1 = m1['GP']['mae'] < v2['mae'] and m1['GP']['t_vs_v2'] >= 3 and m1['GP']['mae'] <= m1['C3']['mae']
    r2 = all((x['n'] < 500) or abs(x['GP']) <= 0.5 or abs(x['GP']) < abs(x['A']) for x in b.values()) and \
        all(abs(x['GP']) < abs(x['A']) or abs(x['GP']) <= 0.5 for x in b.values() if x['n'] >= 500)
    r3 = all(res['props_mae'][s]['GP'] <= res['props_mae'][s]['A'] for s in STATS)
    r4 = ex['GP'] < ex['A']
    res['rule'] = {'1_played_mae': r1, '2_top8_bias': r2, '3_props': r3, '4_expected_minutes': r4, 'PROMOTE_GP': bool(r1 and r2 and r3 and r4)}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(json.dumps(res, indent=1))


def write_md(res):
    m, L = res['played'], []
    L += ['# Minutes bake-off results, 2025-26 (rule: [minutes-bakeoff.md](minutes-bakeoff.md))', '',
          f"Fit rows {res['fit_rows']:,} (GBM, 2023-2025); test pool {res['test_rows']:,} rows, {res['test_played']:,} player-games who played. T = {res['T']}. `data/minutes_bakeoff.json` holds every number.", '',
          '## 1. Players who played', '', '| Model | MAE | RMSE | Bias | Misses 8+ | MAE gain vs v2 | t |', '|---|---|---|---|---|---|---|']
    for k in CANDS:
        x = m[k]
        L.append(f"| {k} | {x['mae']} | {x['rmse']} | {x['bias']:+} | {x['miss8'] * 100:.1f}% | " + (f"{x['gain_vs_v2']:+} | {x['t_vs_v2']} |" if 'gain_vs_v2' in x else '| |'))
    L += ['', f"GP against C3: MAE gain {m['GP']['gain_vs_c3']:+}, t {m['GP']['t_vs_c3']}.", '', '## 2. Top 8 bias (projected minus actual) by pool size', '', '| Pool | n | ' + ' | '.join(CANDS) + ' |', '|---|---|' + '---|' * len(CANDS)]
    for n, x in res['top8_bias'].items():
        L.append(f"| {n} | {x['n']} | " + ' | '.join(f"{x[k]:+}" for k in CANDS) + ' |')
    L += ['', '## 3. Props proxy (MAE of the stat projection)', '', '| Stat | n | ' + ' | '.join(CANDS) + ' |', '|---|---|' + '---|' * len(CANDS)]
    for s, x in res['props_mae'].items():
        L.append(f"| {s} | {x['n']} | " + ' | '.join(str(x[k]) for k in CANDS) + ' |')
    L += ['', '## 4. Expected minutes over every pool row (DNP = 0)', '', '| ' + ' | '.join(CANDS) + ' |', '|' + '---|' * len(CANDS), '| ' + ' | '.join(str(res['expected_mae'][k]) for k in CANDS) + ' |', '',
          '## 5. Team totals per team-game', '', '| Model | if everyone plays | expected | minutes on players who did not play |', '|---|---|---|---|']
    for k in CANDS:
        x = res['team_totals'][k]
        L.append(f"| {k} | {x['if_plays_sum']} | {x['expected_sum']} | {x['minutes_on_dnp']} |")
    L += ['', f"Actual minutes of players who played: {res['team_totals']['actual_sum']} over {res['team_totals']['teams']} team-games.", '', '## Rule', '']
    L += [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in res['rule'].items() if k != 'PROMOTE_GP']
    L += ['', f"**{'PROMOTE GP' if res['rule']['PROMOTE_GP'] else 'DO NOT PROMOTE GP'}**", '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
