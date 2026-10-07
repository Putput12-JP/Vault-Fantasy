#!/usr/bin/env python3
"""Audit: minutes model v3's walk keeps only players who PLAYED, so the team-minutes rescale (predict) spreads 240 minutes
over the players who actually dressed. That is hindsight about healthy scratches and late DNPs. This re-runs the walk with
the as-of candidate rule used for v2 and live pricing (players with state on the team in the last 30 days, minus report
Outs; non-players take minutes in the rescale and are never scored) and compares both under the shipped alpha / a_new.
Writes nothing. ~2 min.   python3 nba/scripts/audit_minutes_v3.py"""
import os, sys, json, types, datetime as dt, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'build_minutes_model_v3.py')).read()
old = """                for r in rows:
                    aid = r['athlete_id']
                    if r['team'] != team or not r['played'] or aid in out:
                        continue
"""
new = """                for r in CANDS(rows, team, s3, out, g):
                    aid = r['athlete_id']
                    if r['team'] != team or aid in out or (MODE == 'played' and not r['played']):
                        continue
"""
assert old in src
src = src.replace(old, new, 1).replace("recs.append({'g': g['game_id'], 'season': g['season'], 'team': team, 'aid': aid, 'y': r['minutes'],",
                                       "recs.append({'np': not r['played'], 'g': g['game_id'], 'season': g['season'], 'team': team, 'aid': aid, 'y': r['minutes'],", 1)
M = types.ModuleType('mm3_patched'); M.__file__ = os.path.join(HERE, 'build_minutes_model_v3.py'); M.MODE = 'played'
def CANDS(rows, team, s3, out, g):
    if M.MODE == 'played':
        return rows
    byid = {r['athlete_id']: r for r in rows if r['team'] == team}
    lim = g['tip'] - dt.timedelta(days=30)
    ids = [a for a, p in s3.pl.items() if p['team'] == team and p['last'] >= lim and a not in out]
    return [byid.get(a) or {'athlete_id': a, 'team': team, 'played': False, 'minutes': 0.0, 'starter': False} for a in ids]
M.CANDS = CANDS
exec(compile(src, M.__file__, 'exec'), M.__dict__)
C, MM = M.C, M.MM
box = C.player_games(M.SEASONS); inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
margins = MM.expected_margins(box); lines = C.closing_lines()
spreads = {gid: {'model': m, 'best': (lines[gid]['spread_close'] if gid in lines and lines[gid]['spread_close'] is not None else m)} for gid, m in margins.items()}
mm3 = json.load(open(MM.OUT_JSON.replace('minutes_model.json', 'minutes_model_v3.json')))
team_min = json.load(open(os.path.join(C.HERE, '..', 'data', 'prop_model.json')))['team_min']
alpha, a_new = mm3['alpha'], mm3['a_new']; beta2 = [json.load(open(MM.OUT_JSON))['beta'][f] for f in M.V2_FEATURES]
print(f'alpha {alpha} a_new {a_new} team_min {team_min}')
for mode in ('played', 'asof'):
    M.MODE = mode
    recs = M.walk(box, inj, spreads, alpha, a_new)
    played = [r for r in recs if not r.get('np')]
    fit = [r for r in played if r['season'] in M.FIT]
    beta = MM.ols([r['x3'] for r in fit], [r['y'] - r['b3'] for r in fit])
    test = [r for r in recs if r['season'] == M.TEST]
    for name, b, base, xk in (('v2', beta2, 'b2', 'x2'), ('v3', beta, 'b3', 'x3')):
        pred = M.predict(test, b, base, xk, team_min)
        sc = M.score([r for r in test if not r.get('np')], pred)
        print(f"{mode:7s} {name}: test player-games {len([r for r in test if not r.get('np')]):6d} (+{len([r for r in test if r.get('np')])} non-playing candidates)  MAE {sc['mae']}  bias {sc['bias']}  8+ miss {sc['miss8']}")

# team-minutes target under the as-of rule: fit on the fit seasons, score on the test season
print('\nteam_min grid under the as-of rule (v2 minutes). fit = 2024-25 (season 2025), test = 2025-26')
M.MODE = 'asof'
recs = M.walk(box, inj, spreads, alpha, a_new)
fit25 = [r for r in recs if r['season'] == 2025]; test26 = [r for r in recs if r['season'] == M.TEST]
best = None
for tm in [240 + 2 * i for i in range(0, 15)]:
    pr = M.predict(fit25, beta2, 'b2', 'x2', tm); s = M.score([r for r in fit25 if not r.get('np')], pr)
    if best is None or s['mae'] < best[1]: best = (tm, s['mae'])
    print(f'  team_min {tm}: fit-season MAE {s["mae"]} bias {s["bias"]}')
tm = best[0]; print('best on fit season:', best)
for label, t in (('shipped 251.6', team_min), (f'fit {tm}', tm)):
    pr = M.predict(test26, beta2, 'b2', 'x2', t); s = M.score([r for r in test26 if not r.get('np')], pr)
    print(f'  TEST {label}: MAE {s["mae"]} bias {s["bias"]} 8+ miss {s["miss8"]}')
