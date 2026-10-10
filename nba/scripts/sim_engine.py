#!/usr/bin/env python3
"""
Game Simulation engine in Python: the page's simulation (ui/projections.template.html, "Game Simulation") ported line for line
so docs/game-simulation.md's pre-registered test can score it on settled games. Same inputs as the page (pricing.py's minutes and
stat means for tonight's board), same mechanics, same constants; nothing is tuned here.

  1. inputs(): who plays and what the prop model says about each (page: simInputs). Minutes for players who dress; a player with no
     injury tag plays with the measured chance for his minutes (data/dress_table.json); the 240-minute scaling is the safety net.
  2. run(): draw a margin and a total around the environment, draw each player's raw points, tie each team's points to its simulated
     score, draw assists / rebounds / 3-pointers as negative binomials scaled to the game (page: simRun / simCore), after the
     3,000-game calibration pilot that corrects the raw points centre and spread.

The random numbers differ from the page's (JavaScript has its own generator), so the two agree statistically, not draw for draw.
check_sim_parity.py proves they agree.

  python3 nba/scripts/sim_engine.py            # one example game, printed
"""
import json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pricing as PX

STATS = ['pts', 'reb', 'ast', '3pm']
N_DEFAULT = 10000
PILOT_N = 3000


def sim_var(PR, s, mu, extra):
    """The prop model's variance for a stat at mean mu (works on arrays). Page: simVar."""
    v0, v1, v2, v3 = PR['variance'][s]
    return np.maximum(.25, v0 + v1 * mu + v2 * mu * mu + (v3 * extra if v3 else 0))


def sim_count(rng, mu, v):
    """Negative binomial (gamma-Poisson) when the variance is above the mean, else Poisson; arrays in, ints out. Page: simCount."""
    mu = np.asarray(mu, float); v = np.broadcast_to(np.asarray(v, float), mu.shape)
    out = np.zeros(mu.shape)
    ok = mu > 0
    over = ok & (v > mu * 1.001)
    lam = np.where(ok, mu, 0.0)
    if over.any():
        shape = mu[over] ** 2 / (v[over] - mu[over]); scale = (v[over] - mu[over]) / mu[over]
        lam = lam.copy(); lam[over] = rng.gamma(shape, scale)
    out[ok] = rng.poisson(lam[ok])
    return out


class Game:
    """One game's inputs: teams [away, home], each {team, rows, f, sumMin, hold}; rows carry pid, name, st, min, mu{}, ex{}, pPlay."""

    def __init__(self, g, teams, MS):
        self.g, self.teams, self.MS = g, teams, MS


def inputs(pricer, g, board, mode='live'):
    """Page: simInputs. mode 'example' skips the Minutes Lab players the way the page does."""
    status, outs = PX.status_from_board(board), PX.outs_from_board(board)
    G = pricer.MS_all.get('game') or {}; p_out = G.get('p_out') or {}
    dress = ((pricer.MS_all.get('minutes') or {}).get('dress')) or []

    def dress_p(m):
        if not dress:
            return 1.0
        for hi, p in dress:
            if m < hi:
                return p
        return dress[-1][1]

    names = {int(k): v.get('nm') for k, v in (pricer.state['players'] if pricer.state else {}).items() if v.get('nm')}
    names.update({x['id']: x['name'] for T in pricer.D['teams'].values() for x in T['players']})
    names.update({int(k): v[0] for k, v in (board.get('players') or {}).items()})
    teams = []
    for team in (g['away'], g['home']):
        cache = {}
        model = pricer.game_minutes(team, g, status, cache)
        rows, seen = [], set()

        def add(pid, src):
            st = status.get(pid)
            if pid in seen or st in ('Out', 'Inactive'):
                return
            mu, ex, mn = {}, {}, 0
            for s in STATS:
                m = pricer.mu_for(pid, s, g, cache, outs, team, status)
                if not m or not (m['min'] > 0):
                    return
                mu[s], ex[s], mn = m['mu'], m['extra'], m['min']
            seen.add(pid)
            rows.append({'pid': pid, 'name': names.get(pid, str(pid)), 'st': st, 'min': mn, 'mu': mu, 'ex': ex, 'src': src,
                         'pPlay': (1 - p_out.get(st, 0)) if st else dress_p(mn)})

        for pid in model:
            add(int(pid), 'model')
        if mode != 'example':
            for p in (pricer.D['teams'].get(team) or {}).get('players', []):
                add(p['id'], 'lab')
        sum_min = sum(r['min'] * r['pPlay'] for r in rows)
        f = 240 / sum_min if sum_min > 0 and abs(sum_min - 240) / 240 > .03 else 1
        if f != 1:
            for r in rows:
                r['min'] *= f
                for s in STATS:
                    r['mu'][s] *= f
        rows.sort(key=lambda r: -r['min'])
        teams.append({'team': team, 'rows': rows, 'f': f, 'sumMin': sum_min, 'hold': pricer.roster_hold(team, g, status, cache, None)})
    return Game(g, teams, G)


def _core(PR, teams, mean, rng, N, sd_m, sd_t):
    e = [sum(r['mu']['pts'] * r['pPlay'] for r in t['rows']) for t in teams]
    e_all = e[0] + e[1]
    margin = mean['m'] + sd_m * rng.standard_normal(N)
    total = mean['t'] + sd_t * rng.standard_normal(N)
    tgt = [(total - margin) / 2, (total + margin) / 2]
    out = []
    for k, t in enumerate(teams):
        rows = t['rows']; J = len(rows)
        on = np.zeros((J, N), bool); raw = np.zeros((J, N))
        for j, r in enumerate(rows):
            on[j] = rng.random(N) < r['pPlay']
            raw[j] = np.where(on[j], np.maximum(0, r['rawMu'] + r['rawSd'] * rng.standard_normal(N)), 0)
        s = raw.sum(0)
        sc = np.where(s > 5, tgt[k] / np.where(s > 0, s, 1), 1.0)
        q = tgt[k] / e[k] if e[k] > 0 else np.ones(N)
        qr = np.power(np.maximum(.5, total) / (e_all or 1), .5)
        cols = {s_: np.zeros((J, N)) for s_ in STATS + ['pra']}
        for j, r in enumerate(rows):
            pts = np.floor(raw[j] * sc + .5)
            ast = sim_count(rng, r['mu']['ast'] * q, sim_var(PR, 'ast', r['mu']['ast'] * q, r['ex']['ast']))
            reb = sim_count(rng, r['mu']['reb'] * qr, sim_var(PR, 'reb', r['mu']['reb'] * qr, r['ex']['reb']))
            tp = sim_count(rng, r['mu']['3pm'] * q, sim_var(PR, '3pm', r['mu']['3pm'] * q, r['ex']['3pm']))
            cols['pts'][j], cols['ast'][j], cols['reb'][j], cols['3pm'][j], cols['pra'][j] = pts, ast, reb, tp, pts + reb + ast
        out.append({'on': on, **cols})
    return {'teams': out, 'margin': margin, 'total': total, 'score': [tgt[0], tgt[1]], 'N': N, 'mean': mean, 'sd_m': sd_m, 'sd_t': sd_t}


def run(pricer, game, mean, seed=1, N=N_DEFAULT):
    """Page: simRun. mean = {'m': home margin, 't': total}. Returns the simulated margin, total, scores and every player's draws."""
    PR = pricer.PR
    G = game.MS or {}
    sd_m, sd_t = G.get('sd_margin') or 12, G.get('sd_total') or 17
    sd_team = math.sqrt((sd_m ** 2 + sd_t ** 2) / 4)
    for t in game.teams:
        e = sum(r['mu']['pts'] * r['pPlay'] for r in t['rows'])
        vs = [float(sim_var(PR, 'pts', r['mu']['pts'], r['ex']['pts'])) for r in t['rows']]
        vsum = sum(vs) or 1
        for j, r in enumerate(t['rows']):
            share = r['mu']['pts'] * r['pPlay'] / e if e > 0 else 0
            w = vs[j] / vsum
            r['rawSd'] = math.sqrt(max(.25, (vs[j] - (share * sd_team) ** 2) / (1 - w))) if w < 1 else math.sqrt(vs[j])
            r['rawMu'] = r['mu']['pts']; r['wantSd'] = math.sqrt(vs[j])
    # the calibration pilot (page: simRun): the team tie and the cut at zero move each scorer's mean and spread; measure and correct
    pilot = _core(PR, game.teams, mean, np.random.default_rng(seed + 101), PILOT_N, sd_m, sd_t)
    for k, t in enumerate(game.teams):
        for j, r in enumerate(t['rows']):
            on = pilot['teams'][k]['on'][j]; pts = pilot['teams'][k]['pts'][j]
            m = pts.mean(); a = pts[on]; want = r['mu']['pts'] * r['pPlay']
            if m > .05:
                r['rawMu'] *= max(.8, min(1.25, want / m))
            if len(a) > 50:
                sd = a.std()
                if sd > .05:
                    r['rawSd'] *= max(.7, min(1.5, r['wantSd'] / sd))
    return _core(PR, game.teams, mean, np.random.default_rng(seed), N, sd_m, sd_t)


def quantile(a, p):
    a = np.sort(a)
    return float(a[min(len(a) - 1, int(p * len(a)))])


def played(res, k, j, s):
    """A player's simulated stat over the games he plays."""
    o = res['teams'][k]
    return o[s][j][o['on'][j]]


def market_mean(M):
    """The page's market environment: spread (home, negative = favourite) and total -> home margin and total."""
    return {'m': -M['spread'], 't': M['total']}


def players_mean(game):
    eA = sum(r['mu']['pts'] * r['pPlay'] for r in game.teams[0]['rows'])
    eH = sum(r['mu']['pts'] * r['pPlay'] for r in game.teams[1]['rows'])
    return {'m': eH - eA, 't': eH + eA}


if __name__ == '__main__':
    board = json.load(open(os.path.join(HERE, '..', 'data', 'prop_board.json')))['example']
    pr = PX.Pricer(example=True)
    g = board['games'][0]
    G = inputs(pr, g, board, 'example')
    res = run(pr, G, players_mean(G))
    print(g['away'], '@', g['home'], 'margin', round(res['margin'].mean(), 2), 'total', round(res['total'].mean(), 2))
    for k, t in enumerate(G.teams):
        for j, r in enumerate(t['rows'][:5]):
            a = played(res, k, j, 'pts')
            print(f"  {t['team']} {r['name']:<22} min {r['min']:.0f}  pts want {r['mu']['pts'] * r['pPlay']:.1f} sim {res['teams'][k]['pts'][j].mean():.1f}")
