#!/usr/bin/env python3
"""
Team allowance for the live matchup term on points and rebounds (docs/matchup-points-rebounds-results.md, docs/matchup-live.md).

For each of the 30 real teams as a DEFENSE, as of the last completed game: how far its field-goal attempts allowed per 48 (P_vol), its field-goal points allowed per attempt (P_eff)
and the misses per 48 in its games (R_miss) sit from the league mean, as a fraction. Last season's full-season rate is blended in until a team has 15 games (weight = games / 15).
It is exactly the arithmetic the registered test used (test_matchup_points_rebounds.py: team_games, season_rates, vs_table), run on today's box scores.

  python3 nba/scripts/build_team_allowance.py [--season N]      writes data/team_allowance.json; --season N builds as if season N were the current one (checks)
"""
import datetime as dt, json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = [a for a in sys.argv if a != '--cache']
import nba_common as C
import test_matchup_points_rebounds as M
import test_matchup_stl_blk_tov as X       # steals / turnovers indices (S_tov, T_forced, Pace): the registered test's own functions

DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'team_allowance.json')


def main():
    if '--season' in sys.argv:
        cur = int(sys.argv[sys.argv.index('--season') + 1])
    else:
        cur = int(json.load(open(os.path.join(DATA, 'player_projections.json')))['season'][:4]) + 1
    seasons = [s for s in (cur - 1, cur) if os.path.exists(os.path.join(C.RAW, 'hoopr', f'player_box_{s}.csv'))]
    if cur - 1 not in seasons:
        sys.exit(f'no box scores for the prior season {cur - 1}')
    box, games = C.player_games(seasons), C.games(seasons)
    tg = M.team_games(box, games)
    prior = M.season_rates(tg, [g for g in games if g['season'] == cur - 1])
    teams = sorted(prior)
    acc = {'sum': defaultdict(lambda: defaultdict(float)), 'n': defaultdict(int)}
    through = None
    for g in games:
        if g['season'] != cur or g['game_id'] not in tg:
            continue
        through = g['tip_et'].strftime('%Y-%m-%d') if through is None or g['tip_et'].strftime('%Y-%m-%d') > through else through
        for t, d in M.defense_sample(tg, g).items():
            acc['n'][t] += 1
            for k, v in d.items():
                acc['sum'][t][k] += v
    tab = M.vs_table(acc, prior, teams)                    # asserts the league mean is over exactly 30 teams
    tg2 = X.team_games(box, games)                         # steals and turnovers: same box scores, the other test's definitions
    prior2 = X.season_rates(tg2, [g for g in games if g['season'] == cur - 1])
    acc2 = {'sum': defaultdict(lambda: defaultdict(float)), 'n': defaultdict(int)}
    for g in games:
        if g['season'] == cur and g['game_id'] in tg2:
            for t, d in X.sample(tg2, g).items():
                acc2['n'][t] += 1
                for k, v in d.items():
                    acc2['sum'][t][k] += v
    tab2 = X.vs_table(acc2, prior2, teams)                 # asserts exactly 30 teams too
    for t in teams:
        tab[t].update({'S_tov': tab2[t]['tov_comm'], 'T_forced': tab2[t]['tov_forced'], 'Pace': tab2[t]['pace']})
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'season': cur, 'through': through, 'games_new': sum(acc['n'].values()) // 2,
           'source': 'team box scores; docs/matchup-points-rebounds-test.md. Fractions: 0.05 = five percent above the league. Blend weight = games / 15.',
           'teams': {t: {'g': acc['n'].get(t, 0), 'w': round(min(1.0, acc['n'].get(t, 0) / M.MIN_GAMES), 2), **{k: round(v, 4) for k, v in tab[t].items()}} for t in teams}}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f"team allowance: season {cur}, through {through}, {len(teams)} teams, games played this season {out['games_new']} -> data/team_allowance.json")


if __name__ == '__main__':
    main()
