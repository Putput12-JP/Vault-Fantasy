#!/usr/bin/env python3
"""Audit: does the v2 backtest's candidate set (everyone in the post-game box score) flatter the model?
Live pricing builds candidates from the roster / recent-rotation state, not the box score
(pricing.py game_minutes). This re-runs build_prop_model_v2.walk with the live-style rule
(team's players seen in the last 30 days, minus report Outs; non-dressed ones get a stub row that takes
minutes but is never scored) and compares both on the same scored player-games.
Writes nothing. Run: python3 nba/scripts/audit_candidate_set.py   (~2 min)"""
import os, sys, json, statistics as st, datetime as dt, types
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
src = open(os.path.join(HERE, 'build_prop_model_v2.py')).read()
old = """                cand = [r for r in rows if r['team'] == team and r['athlete_id'] in ms.pl
                        and (moved or ms.pl[r['athlete_id']]['team'] == team) and r['athlete_id'] in rt and r['athlete_id'] not in out]"""
new = "                cand = CAND_HOOK(rows, team, ms, rt, out, g, moved)"
assert old in src
V2 = types.ModuleType('v2_patched'); V2.__file__ = os.path.join(HERE, 'build_prop_model_v2.py')
V2.CAND_HOOK = None
exec(compile(src.replace(old, new), V2.__file__, 'exec'), V2.__dict__)
C, MM, V1 = V2.C, V2.MM, V2.V1

def box_hook(rows, team, ms, rt, out, g, moved):
    return [r for r in rows if r['team'] == team and r['athlete_id'] in ms.pl
            and (moved or ms.pl[r['athlete_id']]['team'] == team) and r['athlete_id'] in rt and r['athlete_id'] not in out]

SIZES = {'box': [], 'asof': []}
def asof_hook(rows, team, ms, rt, out, g, moved):
    byid = {r['athlete_id']: r for r in rows if r['team'] == team}
    lim = g['tip'] - dt.timedelta(days=30)
    ids = [a for a, p in ms.pl.items() if p['team'] == team and p['last'] >= lim and a in rt and a not in out]
    # a dressed player who just arrived has no state with this team yet: both modes drop him (moved=False)
    cand = [byid.get(a) or {'athlete_id': a, 'team': team, 'played': False, 'minutes': 0.0} for a in ids]
    SIZES['asof'].append(len(cand)); SIZES['box'].append(len(box_hook(rows, team, ms, rt, out, g, moved)))
    return cand

def run(hook):
    V2.CAND_HOOK = hook
    box = C.player_games(V2.SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    team_min = json.load(open(V1.OUT_JSON))['team_min']
    recs, _ = V2.walk(box, inj, margins, mm, casc, team_min, C.closing_lines())
    return recs

if __name__ == '__main__':
    A = run(box_hook); print('box-score candidates done', len(A), flush=True)
    B = run(asof_hook); print('as-of candidates done', len(B), flush=True)
    for tag, R in (('box', A), ('asof', B)):
        fit = [r for r in R if r['season'] == V2.FIT]; stk = V2.fit_stacker(fit); R_ = [r for r in R if r['season'] == V2.TEST]
        globals()['T_' + tag] = (R_, stk)
    ka = {(r['gid'], r['aid']): r for r in T_box[0]}; kb = {(r['gid'], r['aid']): r for r in T_asof[0]}
    keys = sorted(set(ka) & set(kb)); print(f'test player-games: box {len(ka)}  asof {len(kb)}  common {len(keys)}')
    print(f"mean candidates per team-game: box {st.mean(SIZES['box']):.2f}  as-of {st.mean(SIZES['asof']):.2f}")
    def mae(x, f): return st.mean(f(x))
    print(f"\n{'':8s} {'minutes MAE':>12s}", *[f'{m:>7s}' for m in V2.BASE], '  (v1 projection, common player-games)')
    for tag, d, stk in (('box', ka, T_box[1]), ('asof', kb, T_asof[1])):
        row = [st.mean(abs(d[k]['pm'] - d[k]['min']) for k in keys)]
        row += [st.mean(abs(d[k]['mu'][m] - d[k]['y'][m]) for k in keys) for m in V2.BASE]
        print(f'{tag:8s} {row[0]:12.3f}', *[f'{v:7.3f}' for v in row[1:]])
    print('\nv2 projection MAE (own stacker fit on 2025):')
    for tag, d, stk in (('box', ka, T_box[1]), ('asof', kb, T_asof[1])):
        print(f'{tag:8s}', *[f"{m}={st.mean(abs(V2.mu2(d[k], stk)[m] - d[k]['y'][m]) for k in keys):.3f}" for m in V2.BASE])
