#!/usr/bin/env python3
"""
Matchup test for points (P_vol, P_eff) and rebounds (R_miss), Stage 1. Rules: docs/matchup-points-rebounds-test.md (committed before this file existed,
data-source clarification included). Nothing here changes pricing.

  python3 nba/scripts/test_matchup_points_rebounds.py          walk the prop model (about 6 min), build the indices from the box scores, score once -> data/matchup_points_rebounds.json
  python3 nba/scripts/test_matchup_points_rebounds.py --cache  reuse the cached walk records
"""
import json, os, random, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import test_matchup_volume as MV            # slope(), slope_t(), evaluate() and the pass-condition arithmetic, as used for 3PM and assists
import test_early_minutes_blend as EB

OUT = os.path.join(HERE, '..', 'data', 'matchup_points_rebounds.json')
CACHE = os.environ.get('PR_CACHE', '/tmp/matchup_pr_recs.json')
FIT, TEST, SEED, MIN_GAMES, N_TEAMS = 2025, 2026, 7, 15, 30


def walk_records():
    if '--cache' in sys.argv and os.path.exists(CACHE):
        return json.load(open(CACHE))
    import build_prop_model_v3_full as F
    recs = F.walk_v2(F.inputs())
    slim = [{'gid': int(r['gid']), 'season': r['season'], 'aid': r['aid'], 'team': r['team'], 'mup': r['mu']['pts'], 'yp': r['y']['pts'], 'mur': r['mu']['reb'], 'yr': r['y']['reb']}
            for r in recs if r['season'] in (FIT, TEST) and r['pm'] > 0]
    json.dump(slim, open(CACHE, 'w'), separators=(',', ':'))
    return slim


def team_games(box, games):
    """gid -> {team: {'fga','fgm','pts','mins'}} from the box scores (field-goal points = points minus free throws made; minutes = sum of players / 5)."""
    out = {}
    for g in games:
        t = defaultdict(lambda: {'fga': 0.0, 'fgm': 0.0, 'pts': 0.0, 'mins': 0.0})
        for r in box.get(g['game_id'], []):
            if not r['played']:
                continue
            x = t[r['team']]
            x['fga'] += r['field_goals_attempted']; x['fgm'] += r['field_goals_made']
            x['pts'] += r['points'] - r['free_throws_made']; x['mins'] += r['minutes'] / 5.0
        if len(t) == 2:
            out[g['game_id']] = dict(t)
    return out


def defense_sample(tg, g):
    """For each of the game's two teams as the defense: per-48 field-goal attempts and points it allowed, and misses (its own plus the ones it forced)."""
    a, h = g['away'], g['home']
    ta, th = tg[g['game_id']][a], tg[g['game_id']][h]
    mins = max(ta['mins'], th['mins'], 1.0)
    f = 48.0 / mins
    ma, mh = (ta['fga'] - ta['fgm']), (th['fga'] - th['fgm'])
    return {a: {'fga': th['fga'] * f, 'pts': th['pts'] * f, 'miss': (ma + mh) * f}, h: {'fga': ta['fga'] * f, 'pts': ta['pts'] * f, 'miss': (ma + mh) * f}}


def season_rates(tg, games):
    acc, n = defaultdict(lambda: defaultdict(float)), defaultdict(int)
    for g in games:
        if g['game_id'] not in tg:
            continue
        for t, d in defense_sample(tg, g).items():
            n[t] += 1
            for k, v in d.items():
                acc[t][k] += v
    return {t: {k: v / n[t] for k, v in d.items()} for t, d in acc.items()}


def vs_table(cur, prior, teams):
    """Per defense: vs league for P_vol (fga allowed), P_eff (points per attempt allowed), R_miss (misses per 48). Blend weight w = games / 15."""
    rates = {}
    for t in teams:
        n = cur['n'].get(t, 0)
        w = min(1.0, n / MIN_GAMES)
        r = {}
        for k in ('fga', 'pts', 'miss'):
            new = cur['sum'][t][k] / n if n else None
            old = prior[t][k]
            r[k] = old if new is None else w * new + (1 - w) * old
        rates[t] = r
    assert len(rates) == N_TEAMS, f'league mean must be over exactly {N_TEAMS} teams, got {len(rates)}'
    mean_fga = st.mean(r['fga'] for r in rates.values())
    mean_miss = st.mean(r['miss'] for r in rates.values())
    eff = {t: r['pts'] / r['fga'] for t, r in rates.items()}
    mean_eff = st.mean(eff.values())
    return {t: {'P_vol': r['fga'] / mean_fga - 1, 'P_eff': eff[t] / mean_eff - 1, 'R_miss': r['miss'] / mean_miss - 1} for t, r in rates.items()}


def indices(season, recs, games, tg, prior):
    by_gid = defaultdict(list)
    for r in recs:
        if r['season'] == season:
            by_gid[r['gid']].append(r)
    sg = [g for g in games if g['season'] == season and g['game_id'] in tg]
    teams = sorted({t for g in sg for t in (g['home'], g['away'])})
    cur = {'sum': defaultdict(lambda: defaultdict(float)), 'n': defaultdict(int)}
    by_day = defaultdict(list)
    for g in sg:
        by_day[g['tip_et'].strftime('%Y-%m-%d')].append(g)
    rng = random.Random(SEED)
    out, ntab = {}, 0
    for day in sorted(by_day):
        tab = vs_table(cur, prior, teams)                                  # BEFORE the day's games
        ntab += 1
        for g in by_day[day]:
            for r in by_gid.get(g['game_id'], ()):
                opp = g['home'] if r['team'] == g['away'] else g['away'] if r['team'] == g['home'] else None
                if opp is None:
                    continue
                ctl = rng.choice([t for t in teams if t not in (opp, r['team'])])
                out[(r['gid'], r['aid'])] = {k: (tab[opp][k], tab[ctl][k]) for k in ('P_vol', 'P_eff', 'R_miss')}
        for g in by_day[day]:
            for t, d in defense_sample(tg, g).items():
                cur['n'][t] += 1
                for k, v in d.items():
                    cur['sum'][t][k] += v
    return out, ntab


def rows_for(recs, idx, key, stat):
    out = []
    for r in recs:
        f = idx.get((r['gid'], r['aid']))
        if not f:
            continue
        p, a = (r['mup'], r['yp']) if stat == 'pts' else (r['mur'], r['yr'])
        out.append({'gid': r['gid'], 'p': p, 'a': a, 'idx': f[key][0], 'idxc': f[key][1], 'tidx': f[key][0], 's_p': p, 's_a': a})
    return out


def main():
    recs = walk_records()
    print('walk records', len(recs), flush=True)
    box = C.player_games([FIT - 1, FIT, TEST])
    games = C.games([FIT - 1, FIT, TEST])
    tg = team_games(box, games)
    idx = {}
    ntab = {}
    for s in (FIT, TEST):
        prior = season_rates(tg, [g for g in games if g['season'] == s - 1])
        assert len(prior) == N_TEAMS, f'prior season {s - 1} has {len(prior)} teams'
        i, ntab[s] = indices(s, recs, games, tg, prior)
        idx.update(i)
    print('indexed rows', len(idx), '| league-mean tables built (each over exactly 30 teams):', ntab, flush=True)
    res = {'league_mean_teams': N_TEAMS, 'tables': ntab}
    for key, stat in (('P_vol', 'pts'), ('P_eff', 'pts'), ('R_miss', 'reb')):
        fit_rows = rows_for([r for r in recs if r['season'] == FIT], idx, key, stat)
        test_rows = rows_for([r for r in recs if r['season'] == TEST], idx, key, stat)
        beta = MV.slope([(r['p'] * r['idx'], r['a'] - r['p']) for r in fit_rows])
        b26, t26, _ = MV.slope_t([(r['gid'], r['p'] * r['idx'], r['a'] - r['p']) for r in test_rows])
        ev = MV.evaluate(stat, test_rows, beta)
        mult = sorted(min(1.3, max(0.7, 1 + beta * r['idx'])) for r in test_rows)
        conds = {'beta_fit_positive': beta > 0,
                 'stat_gain_t_ge_2_5': (ev['matchup']['stat_t'] or 0) >= 2.5,
                 'control_not_t_ge_2_5': (ev['control']['stat_t'] or 0) < 2.5,
                 'own_slope_2025_26_positive_t_ge_2_5': b26 > 0 and (t26 or 0) >= 2.5,
                 'both_halves_positive': all(x > 0 for x in ev['halves_vol_gain']),
                 'league_mean_over_30_teams': True}
        res[key] = {'stat': stat, 'fit_rows': len(fit_rows), 'test_rows': len(test_rows), 'beta_fit_2024_25': round(beta, 4), 'beta_own_2025_26': round(b26, 4),
                    'beta_own_t': round(t26, 2) if t26 is not None else None, 'eval_2025_26': ev, 'conditions': conds, 'verdict': 'PASS' if all(conds.values()) else 'FAIL',
                    'multiplier_p5_p50_p95': [round(mult[len(mult) // 20], 3), round(mult[len(mult) // 2], 3), round(mult[-len(mult) // 20], 3)]}
    res['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    print(json.dumps(res, indent=1))
    if os.path.exists(OUT):
        print('The result file exists; not overwritten.')
    else:
        json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
