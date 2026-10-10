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
Joint odds (the second half of the pre-registered test), fixed before any result. Over pairs where both played, using the simulation's own
half-lines (sim_record.py), over/over and under/under pooled, errors clustered by game, at least 150 games and 2,000 pairs:
  DIFFERENT TEAMS (the main test: pick'em apps that only allow different teams; real opposing players are close to independent,
  docs/pickem-different-teams.md). The simulation must agree: observed both-hit rate minus simulated within 2 standard errors. Verdict OK or
  NO-GO. NO-GO means it invents dependence (the risk is the shared game total) and its different-team joint odds must not be used.
  TEAMMATES (apps that allow same-team picks; the two combinations that passed): bias inside 2 standard errors AND the simulation's Brier score
  beats the independent product's with z >= 2. GO lets a teammate pair price use the simulation.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, '..', 'data'); DOCS = os.path.join(HERE, '..', 'docs')
MIN_GAMES = 150
STATS = ['pts', 'reb', 'ast', '3pm']
inside = lambda u: .1 < u < .9


def judge(x, lo, hi, n):
    return 'collecting' if n < MIN_GAMES else 'pass' if lo <= x <= hi else 'fail'


JOINT_SETS = [('o:pp', 'Different teams: points with points'), ('o:rr', 'Different teams: rebounds with rebounds'),
              ('o:pa', "Different teams: one player's points with the other's assists"), ('o:a3', "Different teams: one player's assists with the other's 3-pointers"),
              ('t:pa', "Teammates: one player's points with another's assists"), ('t:a3', "Teammates: one player's assists with another's 3-pointers")]


def joint(games):
    """Per set: observed, simulated and independent both-hit rates and the two z scores, clustered by game."""
    out = {}
    for c, _ in JOINT_SETS:
        G = []
        for g in games:
            v = ((g.get('jt') or {}).get('c') or {}).get(c)
            if v:
                z = [sum(v[sd][i] for sd in v) for i in range(6)]            # n, obs, sim, ind, brier sim, brier ind (over/over and under/under pooled)
                G.append(z)
        n = sum(z[0] for z in G)
        if len(G) < 2 or not n:
            out[c] = {'games': len(G), 'pairs': n}
            continue
        def ratio(vals):                                                    # mean per pair and its game-clustered standard error
            r = sum(vals) / n
            e = [v - r * z[0] for v, z in zip(vals, G)]
            return r, math.sqrt(len(G) / (len(G) - 1) * sum(x * x for x in e)) / n
        bias, se_b = ratio([z[1] - z[2] for z in G]); imp, se_i = ratio([z[5] - z[4] for z in G])
        zb, zi = bias / se_b if se_b else 0, imp / se_i if se_i else 0
        enough = len(G) >= MIN_GAMES and n >= 2000
        if c.startswith('o:'):
            verdict = 'collecting' if not enough else 'OK' if abs(zb) < 2 else 'NO-GO'
        else:
            verdict = 'collecting' if not enough else 'GO' if abs(zb) < 2 and zi >= 2 else 'NO-GO'
        out[c] = {'games': len(G), 'pairs': n, 'observed': round(sum(z[1] for z in G) / n, 4), 'simulated': round(sum(z[2] for z in G) / n, 4),
                  'independent': round(sum(z[3] for z in G) / n, 4), 'bias': round(bias, 4), 'z_bias': round(zb, 2),
                  'brier_gain': round(imp, 5), 'z_gain': round(zi, 2), 'verdict': verdict}
    return out


def main():
    path = sys.argv[sys.argv.index('--track') + 1] if '--track' in sys.argv else os.path.join(DATA, 'track.json')
    t = json.load(open(path)) if os.path.exists(path) else {}
    games = sorted([g for d in (t.get('sim_days') or {}).values() for g in d], key=lambda g: g['tip'])
    out = {'generated': t.get('t'), 'min_games': MIN_GAMES, 'envs': {}, 'joint': joint(games)}
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
    out['go_joint'] = {c: v.get('verdict', 'collecting') for c, v in out['joint'].items()}
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
    NAMES = dict(JOINT_SETS)
    md += ['## Joint odds (pairs where both played, over/over and under/under pooled)', '']
    for c, v in out['joint'].items():
        if 'observed' not in v:
            md.append(f"- {NAMES[c]}: {v.get('pairs', 0)} pairs in {v.get('games', 0)} games, nothing to score yet")
        else:
            extra = f"Brier gain over independence {v['brier_gain']:+.5f}, z {v['z_gain']:+.1f} (needs >= 2 for teammates)" if c.startswith('t:') else 'different teams: independence is expected, so only the bias counts'
            md.append(f"- {NAMES[c]}: {v['pairs']:,} pairs in {v['games']} games. Both hit: observed {v['observed']:.1%}, simulated {v['simulated']:.1%}, independent {v['independent']:.1%}. "
                      f"Bias z {v['z_bias']:+.1f} (needs |z| < 2); {extra}: **{v['verdict']}**")
    md += ['', 'Until a set is GO (teammates) or OK (different teams), the simulation prices nothing for it.', '',
           f"## Verdict: calibration {'GO' if out['go'] else 'not called yet' if len(games) < MIN_GAMES else 'NO-GO'}; joint odds " + ', '.join(f"{c} {v}" for c, v in out['go_joint'].items()), '']
    open(os.path.join(DOCS, 'game-simulation-results.md'), 'w').write('\n'.join(md))
    print(f"game simulation test: {len(games)} games scored; verdict {'GO' if out['go'] else 'collecting' if len(games) < MIN_GAMES else 'NO-GO'}")


if __name__ == '__main__':
    main()
