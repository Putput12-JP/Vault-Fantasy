#!/usr/bin/env python3
"""
Restates the 2025-26 lean backtest (data/lean_backtest.json) with the priced minutes changed from v2 to GP (docs/minutes-bakeoff-results.md).

Same lines, same lean rule, same bootstrap. Each row's projection is rescaled by GP's minutes over v2's: proj_new = proj x GP / pm for the same
(game, player), the approximation the early-blend test used (a stat's projection is proportional to its minutes). Rows with no GP value keep the old
projection and are counted. Needs the rotation pool cache and lightgbm (see test_minutes_bakeoff.py). Writes data/lean_backtest.json (new numbers, the old
ones kept under `before_gp`) and data/lean_rows_nba_gp.json.

  nba/.venv/bin/python nba/scripts/restate_lean_backtest_gp.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_lean_backtest as LB
import lean_search_nba as LS
import test_minutes_bakeoff as BO

DATA = LB.DATA


def summarize(rows):
    rows = [r for r in rows if r['proj'] != r['L']]
    out = {'about': 'descriptive backtest series, see nba/scripts/build_lean_backtest.py', 'overall': LB.block(rows), 'by_stat': {}, 'by_side': {}, 'by_agreement': {}, 'by_gap_tercile': {}}
    for s in sorted({r['m'] for r in rows}):
        out['by_stat'][s] = LB.block([r for r in rows if r['m'] == s])
    out['by_side']['over_leans'] = LB.block([r for r in rows if r['proj'] > r['L']])
    out['by_side']['under_leans'] = LB.block([r for r in rows if r['proj'] < r['L']])
    agree = [r for r in rows if r['pk'] != .5 and (r['proj'] > r['L']) == (r['pk'] > .5)]
    dis = [r for r in rows if r['pk'] != .5 and (r['proj'] > r['L']) != (r['pk'] > .5)]
    out['by_agreement'] = {'agrees_with_market': LB.block(agree), 'disagrees_with_market': LB.block(dis)}
    for t in range(3):
        sel = []
        for s in {r['m'] for r in rows}:
            rs = sorted((r for r in rows if r['m'] == s), key=lambda r: abs(r['proj'] - r['L']))
            k = len(rs)
            sel += rs[k * t // 3: k * (t + 1) // 3]
        out['by_gap_tercile'][['small', 'middle', 'large'][t]] = LB.block(sel)
    return out


def main():
    te, _g, _r, _m, _c = BO.compute()
    gp = {(r['gid'], r['aid']): r['GP'] for r in te}
    import build_prop_model_v2 as V2, build_prop_model_v3 as A, build_prop_model_v3_full as F
    I = F.inputs(); recs = F.walk_v2(I)
    stk = V2.fit_stacker([r for r in recs if r['season'] == V2.FIT])
    espn, _ = A.load_markets(A.by_rec(recs)); old, new, miss = [], [], 0
    for m in A.MARKETS if hasattr(A, 'MARKETS') else LS.STATS:
        for x in espn.get((str(V2.TEST), m, 'close'), []):
            r, L = x['r'], x['L']; proj = V2.mu2(r, stk)[m]
            if abs(proj - L) < 1e-9:
                continue
            xp, mp = r['x']['pts'], max(r['mu']['pts'], 1e-6)
            row = {'m': m, 'gid': int(x['gid']), 'proj': proj, 'L': L, 'pk': x['pk'], 'y': int(x['over']), 'pm': r['pm'], 'sdm': r['sdm'],
                   'st': r.get('st'), 'spread': r.get('spread'), 'home': 0.5 + xp[5] / mp, 'b2b': xp[6] / mp, 'mv': int(bool(r.get('mv'))), 'na': int(bool(r.get('na')))}
            g = gp.get((int(x['gid']), r['aid']))
            old.append(row)
            if g is None or r['pm'] <= 0:
                miss += 1
                new.append(dict(row, proj_v2=proj))
            else:
                new.append(dict(row, proj=proj * g / r['pm'], proj_v2=proj, pm_gp=g))
    old.sort(key=lambda r: r['gid']); new.sort(key=lambda r: r['gid'])
    json.dump(new, open(os.path.join(DATA, 'lean_rows_nba_gp.json'), 'w'), separators=(',', ':'))
    before = summarize(old)
    cur = json.load(open(os.path.join(DATA, 'lean_backtest.json')))
    cur = cur.get('committed_before_restate') or cur            # a rerun compares with the file as it was before the first restatement
    same = before['overall'] == cur['overall']
    after = summarize(new)
    after['before_gp'] = before
    after['committed_before_restate'] = cur
    after['restated'] = {'rows': len(new), 'rows_without_gp': miss, 'old_rebuild_matches_file': same,
                         'method': 'proj_new = proj x GP minutes / v2 minutes for the same game and player; see nba/docs/minutes-bakeoff-results.md'}
    json.dump(after, open(os.path.join(DATA, 'lean_backtest.json'), 'w'), indent=1)
    print('old rebuild equals the committed file:', same, '| rows', len(new), '| without GP', miss)
    for k in ['overall'] + [f'by_stat:{s}' for s in after['by_stat']] + ['by_side:over_leans', 'by_side:under_leans', 'by_agreement:agrees_with_market', 'by_agreement:disagrees_with_market']:
        sec, _, key = k.partition(':')
        a = after[sec] if not key else after[sec][key]
        b = before[sec] if not key else before[sec][key]
        print(f"{k:34s} n={a['n']:5d} lean {b['lean']} -> {a['lean']} {a['lean_ci']} | lean-under {b['lean_minus_under']} -> {a['lean_minus_under']} {a['lean_minus_under_ci']} | over% {b['pct_over_leans']} -> {a['pct_over_leans']}")


if __name__ == '__main__':
    main()
