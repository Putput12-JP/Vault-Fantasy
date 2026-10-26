#!/usr/bin/env python3
"""Context for docs/matchup-points-rebounds-test.md, "Rule for the live form of points": joint P_vol + P_eff against P_vol alone. Run after test_matchup_points_rebounds.py --cache."""
import json, os, sys, statistics as st
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], '--cache']
import nba_common as C
import test_matchup_points_rebounds as M
import test_early_minutes_blend as EB


def solve2(rows):
    """Least squares through the origin on two regressors: miss = b1 x1 + b2 x2."""
    a11 = sum(x1 * x1 for x1, x2, y in rows); a12 = sum(x1 * x2 for x1, x2, y in rows); a22 = sum(x2 * x2 for x1, x2, y in rows)
    b1 = sum(x1 * y for x1, x2, y in rows); b2 = sum(x2 * y for x1, x2, y in rows)
    det = a11 * a22 - a12 * a12
    return ((b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det)


def main():
    recs = M.walk_records()
    box = C.player_games([M.FIT - 1, M.FIT, M.TEST]); games = C.games([M.FIT - 1, M.FIT, M.TEST]); tg = M.team_games(box, games)
    idx = {}
    for s in (M.FIT, M.TEST):
        prior = M.season_rates(tg, [g for g in games if g['season'] == s - 1])
        i, _ = M.indices(s, recs, games, tg, prior); idx.update(i)
    fit = [(r['mup'] * idx[(r['gid'], r['aid'])]['P_vol'][0], r['mup'] * idx[(r['gid'], r['aid'])]['P_eff'][0], r['yp'] - r['mup']) for r in recs if r['season'] == M.FIT and (r['gid'], r['aid']) in idx]
    b1, b2 = solve2(fit)
    only = json.load(open(os.path.join(HERE, '..', 'data', 'matchup_points_rebounds.json')))['P_vol']['beta_fit_2024_25']
    corr = st.correlation([x for x, _, _ in fit], [y for _, y, _ in fit])
    by = defaultdict(list)
    for r in recs:
        f = idx.get((r['gid'], r['aid']))
        if r['season'] != M.TEST or not f:
            continue
        m = lambda i: min(1.3, max(0.7, 1 + i))
        joint = m(b1 * f['P_vol'][0] + b2 * f['P_eff'][0]); one = m(only * f['P_vol'][0])
        by[r['gid']].append(abs(r['yp'] - r['mup'] * one) - abs(r['yp'] - r['mup'] * joint))     # positive: the joint pair is better than P_vol alone
    b = EB.boot(by)
    res = {'b1_vol': round(b1, 4), 'b2_eff': round(b2, 4), 'p_vol_alone_beta': only, 'corr_index_vol_eff_x_mu': round(corr, 3), 'joint_minus_vol_alone_mae_gain': round(b['mean'], 5),
           't': round(b['t'], 2) if b['t'] is not None else None, 'games': b['games'], 'rule': 'joint if t >= 2.0 else P_vol alone',
           'use': 'joint' if (b['t'] or 0) >= 2.0 else 'P_vol alone'}
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(HERE, '..', 'data', 'matchup_points_joint.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
