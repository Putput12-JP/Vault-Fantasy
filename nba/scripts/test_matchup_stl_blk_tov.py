#!/usr/bin/env python3
"""
Matchup test for steals, blocks and turnovers, Stage 1. Rules: docs/matchup-stl-blk-tov-test.md (committed before this file existed). Nothing here changes pricing.

  python3 nba/scripts/test_matchup_stl_blk_tov.py          walk the extra-stat model (about 6 min), build the indices from the box scores, score once -> data/matchup_stl_blk_tov.json
  python3 nba/scripts/test_matchup_stl_blk_tov.py --cache  reuse the cached walk records
"""
import json, os, random, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import test_early_minutes_blend as EB       # boot()

OUT = os.path.join(HERE, '..', 'data', 'matchup_stl_blk_tov.json')
CACHE = os.environ.get('SBT_CACHE', '/tmp/matchup_sbt_recs.json')
FIT, TEST, SEED, MIN_GAMES, N_TEAMS = 2025, 2026, 7, 15, 30
STATS = {'stl': 'tov_comm', 'blk': 'twopa', 'tov': 'tov_forced'}          # stat -> matchup index
KEYS = ['tov_comm', 'twopa', 'tov_forced', 'pace']


def walk_records():
    if '--cache' in sys.argv and os.path.exists(CACHE):
        return json.load(open(CACHE))
    import build_minutes_model as MM
    import build_prop_model as P
    import build_prop_model_extra as X                      # importing it sets P.BASE / P.COMBO to the extra stats, as the model's own script does
    box = C.player_games(P.WARM + P.TUNE + P.TEST)
    inj = C.InjuryAsOf(P.TEST, C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    team_min = json.load(open(P.OUT_JSON))['team_min']
    te = P.walk(P.WARM + P.TUNE + P.TEST, box, inj, P.TEST[0], 'report', margins, mm, {}, team_min)
    team_of = {(g, r['athlete_id']): r['team'] for g, rows in box.items() for r in rows}
    slim = [{'gid': int(r['gid']), 'season': r['season'], 'aid': r['aid'], 'team': team_of.get((r['gid'], r['aid'])),
             'mu': {s: r['pred']['tip'][1][s] for s in STATS}, 'y': {s: r['y'][s] for s in STATS}} for r in te if 'tip' in r['pred']]
    json.dump(slim, open(CACHE, 'w'), separators=(',', ':'))
    return slim


def team_games(box, games):
    """gid -> {team: {'tov','fga','tpa','fta','oreb','mins'}} from the box scores."""
    out = {}
    for g in games:
        t = defaultdict(lambda: {'tov': 0.0, 'fga': 0.0, 'tpa': 0.0, 'fta': 0.0, 'oreb': 0.0, 'mins': 0.0})
        for r in box.get(g['game_id'], []):
            if not r['played']:
                continue
            x = t[r['team']]
            x['tov'] += r['turnovers']; x['fga'] += r['field_goals_attempted']; x['tpa'] += r['three_point_field_goals_attempted']
            x['fta'] += r['free_throws_attempted']; x['oreb'] += r['offensive_rebounds']; x['mins'] += r['minutes'] / 5.0
        if len(t) == 2:
            out[g['game_id']] = dict(t)
    return out


def sample(tg, g):
    """Per team, per 48: tov_comm (its offense's turnovers), twopa (its offense's two-point attempts), tov_forced (turnovers its defense forces), pace (possessions in the game)."""
    a, h = g['away'], g['home']
    ta, th = tg[g['game_id']][a], tg[g['game_id']][h]
    f = 48.0 / max(ta['mins'], th['mins'], 1.0)
    poss = lambda x: x['fga'] + 0.44 * x['fta'] + x['tov'] - x['oreb']
    pace = (poss(ta) + poss(th)) / 2.0 * f
    return {a: {'tov_comm': ta['tov'] * f, 'twopa': (ta['fga'] - ta['tpa']) * f, 'tov_forced': th['tov'] * f, 'pace': pace},
            h: {'tov_comm': th['tov'] * f, 'twopa': (th['fga'] - th['tpa']) * f, 'tov_forced': ta['tov'] * f, 'pace': pace}}


def season_rates(tg, games):
    acc, n = defaultdict(lambda: defaultdict(float)), defaultdict(int)
    for g in games:
        if g['game_id'] not in tg:
            continue
        for t, d in sample(tg, g).items():
            n[t] += 1
            for k, v in d.items():
                acc[t][k] += v
    return {t: {k: v / n[t] for k, v in d.items()} for t, d in acc.items()}


def vs_table(cur, prior, teams):
    rates = {}
    for t in teams:
        n = cur['n'].get(t, 0)
        w = min(1.0, n / MIN_GAMES)
        rates[t] = {k: (prior[t][k] if not n else w * cur['sum'][t][k] / n + (1 - w) * prior[t][k]) for k in KEYS}
    assert len(rates) == N_TEAMS, f'league mean must be over exactly {N_TEAMS} teams, got {len(rates)}'
    mean = {k: st.mean(r[k] for r in rates.values()) for k in KEYS}
    return {t: {k: r[k] / mean[k] - 1 for k in KEYS} for t, r in rates.items()}


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
                out[(r['gid'], r['aid'])] = {k: (tab[opp][k], tab[ctl][k]) for k in KEYS}
        for g in by_day[day]:
            for t, d in sample(tg, g).items():
                cur['n'][t] += 1
                for k, v in d.items():
                    cur['sum'][t][k] += v
    return out, ntab


# ── statistics ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def solve2(s):
    """s = (a11, a12, a22, b1, b2): least squares through the origin on two regressors."""
    a11, a12, a22, b1, b2 = s
    det = a11 * a22 - a12 * a12
    return ((b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det) if det else (0.0, 0.0)


def sums(rows):
    a11 = a12 = a22 = b1 = b2 = 0.0
    for x1, x2, y in rows:
        a11 += x1 * x1; a12 += x1 * x2; a22 += x2 * x2; b1 += x1 * y; b2 += x2 * y
    return (a11, a12, a22, b1, b2)


def own_slope_t(by_game, draws=2000):
    """Joint slopes re-estimated on one season, matchup slope with a game bootstrap t. by_game: {gid: sums tuple}."""
    gk = list(by_game)
    tot = [sum(by_game[g][i] for g in gk) for i in range(5)]
    bm = solve2(tot)[1]
    rng = random.Random(SEED)
    bs = []
    for _ in range(draws):
        s = [0.0] * 5
        for g in rng.choices(gk, k=len(gk)):
            for i in range(5):
                s[i] += by_game[g][i]
        bs.append(solve2(s)[1])
    sd = st.pstdev(bs)
    return bm, (bm / sd if sd else None)


def rows_for(recs, idx, stat):
    out = []
    for r in recs:
        f = idx.get((r['gid'], r['aid']))
        if not f or r['team'] is None:
            continue
        out.append({'gid': r['gid'], 'mu': r['mu'][stat], 'y': r['y'][stat], 'pace': f['pace'][0], 'm': f[STATS[stat]][0], 'mc': f[STATS[stat]][1]})
    return [r for r in out if r['mu'] > 0]


def mult(x):
    return min(1.3, max(0.7, 1 + x))


def gain(rows, base, new):
    by = defaultdict(list)
    for r in rows:
        by[r['gid']].append(abs(r['y'] - r['mu'] * mult(base(r))) - abs(r['y'] - r['mu'] * mult(new(r))))
    b = EB.boot(by)
    return {'gain': round(b['mean'], 5), 't': round(b['t'], 2) if b['t'] is not None else None, 'games': b['games'], 'rows': b['rows']}


def main():
    recs = walk_records()
    print('walk records', len(recs), flush=True)
    box = C.player_games([FIT - 1, FIT, TEST])
    games = C.games([FIT - 1, FIT, TEST])
    tg = team_games(box, games)
    idx, ntab = {}, {}
    for s in (FIT, TEST):
        prior = season_rates(tg, [g for g in games if g['season'] == s - 1])
        assert len(prior) == N_TEAMS, f'prior season {s - 1} has {len(prior)} teams'
        i, ntab[s] = indices(s, recs, games, tg, prior)
        idx.update(i)
    print('indexed rows', len(idx), '| league-mean tables, each over exactly 30 teams:', ntab, flush=True)
    res = {'league_mean_teams': N_TEAMS, 'tables': ntab}
    for stat in STATS:
        fit = rows_for([r for r in recs if r['season'] == FIT], idx, stat)
        test = rows_for([r for r in recs if r['season'] == TEST], idx, stat)
        bp, bm = solve2(sums([(r['mu'] * r['pace'], r['mu'] * r['m'], r['y'] - r['mu']) for r in fit]))
        bp_only = sums([(r['mu'] * r['pace'], 0.0, r['y'] - r['mu']) for r in fit])
        bp_only = bp_only[3] / bp_only[0] if bp_only[0] else 0.0
        bm_only = sums([(r['mu'] * r['m'], 0.0, r['y'] - r['mu']) for r in fit])
        bm_only = bm_only[3] / bm_only[0] if bm_only[0] else 0.0
        pace_only = lambda r: bp_only * r['pace']
        joint = lambda r: bp * r['pace'] + bm * r['m']
        joint_ctl = lambda r: bp * r['pace'] + bm * r['mc']
        zero = lambda r: 0.0
        incr, ctl = gain(test, pace_only, joint), gain(test, pace_only, joint_ctl)
        gids = sorted({r['gid'] for r in test}); half = set(gids[:len(gids) // 2])
        halves = []
        for h in (True, False):
            sel = [r for r in test if (r['gid'] in half) == h]
            halves.append(round(st.mean(abs(r['y'] - r['mu'] * mult(pace_only(r))) - abs(r['y'] - r['mu'] * mult(joint(r))) for r in sel), 5))
        per = defaultdict(lambda: [0.0] * 5)
        for r in test:
            s5 = sums([(r['mu'] * r['pace'], r['mu'] * r['m'], r['y'] - r['mu'])])
            for i in range(5):
                per[r['gid']][i] += s5[i]
        bm26, t26 = own_slope_t(per)
        ctx = {'pace_alone_vs_bare': gain(test, zero, pace_only), 'matchup_alone_vs_bare': gain(test, zero, lambda r: bm_only * r['m']),
               'corr_matchup_pace': round(st.correlation([r['m'] for r in test], [r['pace'] for r in test]), 3)}
        srt = sorted(test, key=lambda r: r['m']); q = len(srt) // 5
        ctx['quintile_residual_pct'] = [round(100 * (sum(r['y'] - r['mu'] for r in srt[i * q:(i + 1) * q]) / max(1e-9, sum(r['mu'] for r in srt[i * q:(i + 1) * q]))), 2) for i in range(5)]
        ctx['quintile_index'] = [round(st.mean(r['m'] for r in srt[i * q:(i + 1) * q]), 4) for i in range(5)]
        conds = {'bm_fit_positive': bm > 0, 'incremental_gain_t_ge_2_5': (incr['t'] or 0) >= 2.5, 'control_not_t_ge_2_5': (ctl['t'] or 0) < 2.5,
                 'both_halves_positive': all(x > 0 for x in halves), 'own_bm_2025_26_positive_t_ge_2_5': bm26 > 0 and (t26 or 0) >= 2.5, 'league_mean_over_30_teams': True}
        verdict = 'PASS' if all(conds.values()) else ('FAIL: the matchup is pace' if (ctx['matchup_alone_vs_bare']['t'] or 0) >= 2.5 and not conds['incremental_gain_t_ge_2_5'] else 'FAIL')
        res[stat] = {'index': STATS[stat], 'fit_rows': len(fit), 'test_rows': len(test), 'b_pace_joint': round(bp, 4), 'b_matchup_joint': round(bm, 4), 'b_pace_only': round(bp_only, 4),
                     'b_matchup_own_2025_26': round(bm26, 4), 'b_matchup_own_t': round(t26, 2) if t26 is not None else None, 'incremental_over_pace': incr, 'control_over_pace': ctl,
                     'halves_incremental_gain': halves, 'context': ctx, 'conditions': conds, 'verdict': verdict}
    res['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    print(json.dumps(res, indent=1))
    if os.path.exists(OUT):
        print('The result file exists; not overwritten.')
    else:
        json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
