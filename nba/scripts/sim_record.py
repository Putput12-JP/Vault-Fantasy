#!/usr/bin/env python3
"""
Simulation record: how the Game Simulation did, game by game, for the Track Record page.

The page's simulation (sim_engine.py is its Python port; check_sim_parity.py proves they agree) plays each game 10,000 times. This
module records what it said before tip and scores it against the box score afterwards. Nothing here is a bet and nothing here
changes a price: it only measures whether the simulated ranges were honest. It is the live version of the test written in
docs/game-simulation.md (calibration: how often did the real total, margin and player stats land inside the simulated 80% range).

  log(board, now)      -> (rows, meta) for Day.record('sim', ...), called by snapshot.py after each poll, for games within SIM_WINDOW_H of tip.
                          Two environments per game, both recorded:
                            market   the game's spread and total from the books (the page's default)
                            players  the players' own sum (the model's own game forecast, our check on it)
                          game row   gid|env        [mean margin, mean total, 9 margin deciles, 9 total deciles, home win chance]
                          player row gid|env|pid    [plays chance, minutes, then 9 deciles each for pts, reb, ast, 3pm, over the games he plays]
  record(...)          -> per tip day: each game's last pre-tip record against the final box score (called by ledger.settle).

Scoring uses a mid-rank PIT from the deciles: u is where the actual value sits in the simulated distribution (0.05 = below the 10th
percentile, 0.5 = the middle, 0.95 = above the 90th; ties count half). A calibrated simulation has u spread evenly, so 80% of games
land with 0.1 < u < 0.9 ("inside the 80% range"). Count stats are discrete, so this mid-rank is fairer than a raw inside test.
"""
import os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

SIM_WINDOW_H = 4                    # a game is simulated from this many hours before tip: lineups and injuries have mostly settled
ENVS = ('market', 'players')
STATS = ['pts', 'reb', 'ast', '3pm']
DECILES = [.1, .2, .3, .4, .5, .6, .7, .8, .9]
MIN_PLAY = .5                       # players recorded: a better than even chance of playing ...
MIN_MIN = 8                         # ... and at least this many projected minutes
SL_BOOKS = ['Pinnacle', 'Consensus', 'DraftKings', 'FanDuel', 'BetMGM', 'ESPN BET', 'bet365', 'BetRivers']   # the page's order for the market line


def market_line(g):
    """The page's marketLine(): first book in SL_BOOKS order with a spread, first with a total. {'spread': home spread, 'total'} or None."""
    mk = g.get('mk')
    if mk and mk.get('books'):
        by = {r[0]: r for r in mk['books']}
        order = SL_BOOKS + [b for b in by if b not in SL_BOOKS]
        sp = next((by[b] for b in order if b in by and by[b][1] is not None), None)
        to = next((by[b] for b in order if b in by and by[b][6] is not None), None)
        if sp and to:
            return {'spread': sp[1], 'total': to[6]}
    if g.get('spread') is not None and g.get('total') is not None:     # the example board carries the line directly
        return {'spread': g['spread'], 'total': g['total']}
    return None


def _dec(a):
    return [round(float(x), 1) for x in np.quantile(a, DECILES)] if len(a) else None


def log(board, now):
    """Rows and meta for every game tipping within SIM_WINDOW_H, in both environments."""
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    import pricing as PX, sim_engine as SE
    pr = PX.Pricer(example=bool(board.get('example')))
    if not pr.MM:
        return rows, meta
    for g in board['games']:
        if not (now < g['tip'] <= now + SIM_WINDOW_H * 3600):
            continue
        try:
            game = SE.inputs(pr, g, board, 'example' if board.get('example') else 'live')
            ml = market_line(g)
            seed = int(g['id']) % 100003 + 7919          # fixed per game, so an unchanged input records an unchanged row
            for env in ENVS:
                if env == 'market':
                    if not ml:
                        continue
                    mean = SE.market_mean(ml)
                else:
                    mean = SE.players_mean(game)
                res = SE.run(pr, game, mean, seed)
                base = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'away': g['away'], 'home': g['home'], 'env': env}
                k = f"{g['id']}|{env}"
                rows[k] = [round(float(res['margin'].mean()), 1), round(float(res['total'].mean()), 1), _dec(res['margin']), _dec(res['total']),
                           round(float((res['margin'] > 0).mean()), 3)]
                meta[k] = {**base, 'kind': 'game'}
                for t, tm in enumerate(game.teams):
                    for j, r in enumerate(tm['rows']):
                        if r['pPlay'] < MIN_PLAY or r['min'] < MIN_MIN:
                            continue
                        qs = []
                        for s in STATS:
                            a = SE.played(res, t, j, s)
                            qs.append(_dec(a) if len(a) >= 50 else None)
                        if any(q is None for q in qs):
                            continue
                        kp = f"{g['id']}|{env}|{r['pid']}"
                        rows[kp] = [round(r['pPlay'], 3), round(r['min'], 1)] + qs
                        meta[kp] = {**base, 'kind': 'player', 'pid': r['pid'], 'player': r['name'], 'team': tm['team']}
        except Exception as e:                           # one game's failure never stops the recorder
            print(f"  sim {g.get('id')}: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return rows, meta


def pit(qs, y):
    """Mid-rank position of y among nine deciles, 0.05 to 0.95 (see the module docstring)."""
    lt = sum(1 for q in qs if q < y)
    le = sum(1 for q in qs if q <= y)
    return round(((lt + le) / 2 + .5) / 10, 3)


def inside(u):
    return .1 < u < .9


def record(root, now, prev, rescan_days, games, L):
    """Per tip day: each final game's last pre-tip simulation against the box score. L is the ledger module (box, box_meta,
    load_src, tip_day, SETTLE_AFTER_S), passed in because ledger imports this module. Days outside the rescan window are kept."""
    days = dict(prev or {})
    since = L.tip_day(now - rescan_days * 86400)
    G = {}                                              # game -> env -> {'game': row, 'players': {pid: (row, meta)}}
    for k, x in L.load_src(root, 'sim', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
        if not m or not pre or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        e = G.setdefault(m['game'], {}).setdefault(m['env'], {'meta': m, 'game': None, 'players': {}})
        if m['kind'] == 'game':
            e['game'], e['meta'] = pre[-1], m
        else:
            e['players'][m['pid']] = (pre[-1], m)
    per_day = {}
    for gid, envs in G.items():
        bx = L.box(root, gid)
        if bx is None:
            continue
        sc = (L.box_meta(root, gid).get('score')) or {}
        any_env = next(iter(envs.values()))['meta']
        ha, aw = any_env['home'], any_env['away']
        if ha not in sc or aw not in sc:
            continue
        am, at = sc[ha] - sc[aw], sc[ha] + sc[aw]
        entry = {'game': gid, 'matchup': any_env['matchup'], 'tip': any_env['tip'], 'score': [sc[aw], sc[ha]], 'env': {}}
        for env, e in envs.items():
            if e['game'] is None:
                continue
            mean_m, mean_t, qm, qt, pw = e['game']
            um, ut = pit(qm, am), pit(qt, at)
            per = {s: [0, 0, 0, 0, 0.0] for s in STATS}      # played, inside 80%, below, above, sum of u
            dnp, expect, miss = 0, 0.0, []
            for pid, (row, m) in e['players'].items():
                st = bx.get(int(pid))
                expect += row[0]
                if not st:
                    dnp += 1
                    continue
                for i, s in enumerate(STATS):
                    y = sum(st.get(c, 0) for c in {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['threePointFieldGoalsMade']}[s])
                    qs = row[2 + i]
                    u = pit(qs, y)
                    p = per[s]
                    p[0] += 1; p[1] += inside(u); p[2] += u <= .1; p[3] += u >= .9; p[4] += u
                    miss.append([abs(u - .5), m['player'], m['team'], s, qs[0], qs[4], qs[8], y])
            miss.sort(key=lambda r: -r[0])
            entry['env'][env] = {'m': [qm[0], round(mean_m, 1), qm[8]], 'am': am, 'um': um, 't': [qt[0], round(mean_t, 1), qt[8]], 'at': at, 'ut': ut,
                                 'pw': pw, 'hw': 1 if am > 0 else 0,
                                 'ps': {s: [p[0], int(p[1]), int(p[2]), int(p[3]), round(p[4], 2)] for s, p in per.items()},
                                 'n': len(e['players']), 'dnp': dnp, 'exp': round(expect, 1),
                                 'miss': [[r[1], r[2], r[3], r[4], r[5], r[6], r[7]] for r in miss[:5]]}
        if entry['env']:
            per_day.setdefault(L.tip_day(entry['tip']), []).append(entry)
    for d, gs in per_day.items():
        days[d] = sorted(gs, key=lambda g: g['tip'])
    return days
