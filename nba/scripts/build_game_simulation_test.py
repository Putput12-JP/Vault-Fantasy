#!/usr/bin/env python3
"""
Scores the Game Simulation's pre-registered calibration test (docs/game-simulation.md, "Test before it is allowed to feed anything")
from the live record: track.json's sim_days, written by sim_record.py (the recorder saves each game's simulated ranges before tip,
the ledger scores them against the box score). Run it whenever; it states its verdict only once 150 regular-season games are scored.

Rules (written before any result, unchanged here):
  - totals and margins: the real value lands inside the simulated 80% range 80% +/- 4 points of games
  - player points, rebounds, assists: 80% +/- 5 points of player-games (3-pointers are reported, with no target)
  - Both environments are scored. The market line env centres totals and margins on the market, so it tests the simulation's spread; the
    players' own sum env tests our own forecast. The test is judged on each separately.
  - "Inside" is the mid-rank rule in sim_record.py (u between 0.1 and 0.9), fairer than a raw inside test on count stats.
NOT yet recorded, so not yet tested: the joint-odds half of the pre-registered test (teammate pick'em pairs, simulated both-hit rate vs observed).
sim_record.py does not save pair probabilities yet; until it does, the simulation stays a view and may not price a pair.

  python3 nba/scripts/build_game_simulation_test.py [--track path/to/track.json]
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, '..', 'data'); DOCS = os.path.join(HERE, '..', 'docs')
MIN_GAMES = 150
STATS = ['pts', 'reb', 'ast', '3pm']
inside = lambda u: .1 < u < .9


def judge(x, lo, hi, n):
    return 'collecting' if n < MIN_GAMES else 'pass' if lo <= x <= hi else 'fail'


def main():
    path = sys.argv[sys.argv.index('--track') + 1] if '--track' in sys.argv else os.path.join(DATA, 'track.json')
    t = json.load(open(path)) if os.path.exists(path) else {}
    games = sorted([g for d in (t.get('sim_days') or {}).values() for g in d], key=lambda g: g['tip'])
    out = {'generated': t.get('t'), 'min_games': MIN_GAMES, 'envs': {}, 'joint': 'not recorded yet'}
    for env in ('market', 'players'):
        R = [g for g in games if env in g['env']]
        n = len(R)
        if not n:
            out['envs'][env] = {'games': 0}
            continue
        e = [g['env'][env] for g in R]
        tot = sum(inside(x['ut']) for x in e) / n; mar = sum(inside(x['um']) for x in e) / n
        pl = {s: [sum(x['ps'][s][i] for x in e) for i in range(5)] for s in STATS}
        pin = {s: pl[s][1] / pl[s][0] if pl[s][0] else None for s in STATS}
        pooled = sum(pl[s][1] for s in STATS[:3]) / max(1, sum(pl[s][0] for s in STATS[:3]))
        brier = sum((x['pw'] - x['hw']) ** 2 for x in e) / n
        se = lambda p, m: math.sqrt(p * (1 - p) / m)
        out['envs'][env] = {
            'games': n, 'totals_in': round(tot, 3), 'margins_in': round(mar, 3),
            'totals_below': round(sum(x['ut'] <= .1 for x in e) / n, 3), 'totals_above': round(sum(x['ut'] >= .9 for x in e) / n, 3),
            'margins_below': round(sum(x['um'] <= .1 for x in e) / n, 3), 'margins_above': round(sum(x['um'] >= .9 for x in e) / n, 3),
            'players_in': {s: None if pin[s] is None else round(pin[s], 3) for s in STATS}, 'players_pooled_pts_reb_ast': round(pooled, 3),
            'player_games': {s: pl[s][0] for s in STATS}, 'home_win_brier': round(brier, 4),
            'plays_expected_vs_actual': [round(sum(x['exp'] for x in e), 1), sum(x['n'] - x['dnp'] for x in e)],
            'verdict': {'totals': judge(tot, .76, .84, n), 'margins': judge(mar, .76, .84, n), 'players': judge(pooled, .75, .85, n)},
            'se_totals': round(se(tot, n), 3)}
    out['go'] = all(v.get('verdict', {}).get(k) == 'pass' for v in out['envs'].values() if v.get('games') for k in ('totals', 'margins', 'players')) and any(v.get('games', 0) >= MIN_GAMES for v in out['envs'].values())
    json.dump(out, open(os.path.join(DATA, 'game_simulation_test.json'), 'w'), separators=(',', ':'))
    md = ['# Game Simulation: live calibration result', '', f'Rules: docs/game-simulation.md. Source: the live record (sim_record.py) in track.json. Games scored: {len(games)} (the test is called at {MIN_GAMES}).', '']
    for env, v in out['envs'].items():
        if not v.get('games'):
            md += [f'## {env}: no games scored yet', '']
            continue
        md += [f"## {'Market line' if env == 'market' else 'Players own sum'}: {v['games']} games", '',
               f"- Totals inside the 80% range: {v['totals_in']:.1%} (below {v['totals_below']:.1%}, above {v['totals_above']:.1%}); target 76% to 84%: **{v['verdict']['totals']}**",
               f"- Margins inside: {v['margins_in']:.1%} (below {v['margins_below']:.1%}, above {v['margins_above']:.1%}); target 76% to 84%: **{v['verdict']['margins']}**",
               f"- Player points, rebounds, assists inside: {v['players_pooled_pts_reb_ast']:.1%} of {sum(v['player_games'][s] for s in STATS[:3]):,} player-stats; target 75% to 85%: **{v['verdict']['players']}**",
               '- By stat: ' + ', '.join(f"{s} {v['players_in'][s]:.1%}" for s in STATS if v['players_in'][s] is not None) + ' (3pm has no target)',
               f"- Home win Brier {v['home_win_brier']} (a coin flip is 0.25). Players expected to play {v['plays_expected_vs_actual'][0]}, did {v['plays_expected_vs_actual'][1]}.", '']
    md += ['## Joint odds', '', 'Not recorded yet, so not tested. Until it is, the simulation is a view and prices nothing.', '',
           f"## Verdict: {'GO on calibration (joint odds still untested)' if out['go'] else 'not called yet' if len(games) < MIN_GAMES else 'NO-GO on calibration'}", '']
    open(os.path.join(DOCS, 'game-simulation-results.md'), 'w').write('\n'.join(md))
    print(f"game simulation test: {len(games)} games scored; verdict {'GO' if out['go'] else 'collecting' if len(games) < MIN_GAMES else 'NO-GO'}")


if __name__ == '__main__':
    main()
