#!/usr/bin/env python3
"""
Possession-efficiency rating model (the method read off a public NBA model) against the shipped Vault line, walk-forward.
Rules, committed before this ran: docs/game-model-challenger.md. Results: docs/game-model-challenger-results.md and data/game_model_challenger.json.

  python3 nba/scripts/test_ratings_challenger.py

Pure stdlib. Uses the same games, lines and injury report as build_game_model.py. The shipped model is run with the parameters already in
data/game_model.json (no retune), so the reference is exactly what the Slate uses. Nothing here writes data/game_model.json.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM

WARM, TUNE, TEST = GM.WARM, GM.TUNE, GM.TEST
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'game_model_challenger.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-challenger-results.md')
GRID = {'K': [0.02, 0.04, 0.06, 0.08, 0.11, 0.14, 0.18], 'CARRY': [0.3, 0.45, 0.6, 0.75, 0.9], 'KP': [0.05, 0.10, 0.15]}
START = {'K': 0.06, 'CARRY': 0.6, 'KP': 0.10}


def team_stats(rows, g):
    """{team: [fga, oreb, tov, fta, minutes]} for the two teams of a game from its player rows, or None when the rows do not split into home and away."""
    t = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0])
    for r in rows:
        x = t[r['team']]
        x[0] += r['field_goals_attempted']; x[1] += r['offensive_rebounds']; x[2] += r['turnovers']; x[3] += r['free_throws_attempted']; x[4] += r['minutes']
    if g['home'] not in t or g['away'] not in t:
        return None
    return t


def game_poss(t, g):
    """Possessions per team, averaged over the two teams, scaled to 48 minutes (overtime games play more minutes than 240)."""
    p = [x[0] - x[1] + x[2] + 0.44 * x[3] for k, x in t.items() if k in (g['home'], g['away'])]
    mins = sum(x[4] for k, x in t.items() if k in (g['home'], g['away']))
    return (sum(p) / 2) * (480.0 / mins) if mins else None      # mins covers both teams: 480 in regulation


class Ratings:
    """Offense / defense / pace relative to the league, moved by a fixed fraction of each game's surprise."""
    def __init__(self, K, CARRY, KP):
        self.K, self.CARRY, self.KP = K, CARRY, KP
        self.O, self.D, self.P = defaultdict(float), defaultdict(float), defaultdict(float)
        self.base, self.pace0, self.n = 112.0, 99.0, 0
        self.hfa, self.hfa_n, self.season = 2.0, 0, None

    def new_season(self, s):
        if self.season is not None and s != self.season:
            for d in (self.O, self.D, self.P):
                for t in d:
                    d[t] *= self.CARRY
        self.season = s

    def raw(self, g):
        h, a = g['home'], g['away']
        pace = self.pace0 + self.P[h] + self.P[a]
        ph, pa = self.base + self.O[h] + self.D[a], self.base + self.O[a] + self.D[h]
        return (ph - pa) * pace / 100.0 + (0.0 if g['neutral'] else self.hfa)

    def update(self, g, poss):
        h, a = g['home'], g['away']
        pace = poss
        oh, oa = g['hs'] / poss * 100.0, g['as'] / poss * 100.0
        sh, sa = oh - (self.base + self.O[h] + self.D[a]), oa - (self.base + self.O[a] + self.D[h])
        self.O[h] += self.K * sh; self.D[a] += self.K * sh
        self.O[a] += self.K * sa; self.D[h] += self.K * sa
        sp = pace - (self.pace0 + self.P[h] + self.P[a])
        self.P[h] += self.KP * sp; self.P[a] += self.KP * sp
        if not g['playoff']:
            self.n += 2
            w = 1.0 / min(self.n, 400)                          # running league means, over about the last 200 games
            self.base += w * ((oh + oa) / 2 - self.base)
            self.pace0 += w * (pace - self.pace0)
        if not g['neutral'] and not g['playoff']:
            self.hfa_n += 1
            self.hfa += (g['hs'] - g['as'] - (self.raw_nohfa(g)) - self.hfa) / min(self.hfa_n, 1500)

    def raw_nohfa(self, g):
        return self.raw(g) - (0.0 if g['neutral'] else self.hfa)


def walk(P, seasons, box, record_from=None):
    """[(game_id, season, raw margin, actual margin)] for games in seasons >= record_from, walk-forward (the prediction is made before the update)."""
    m, out = Ratings(P['K'], P['CARRY'], P['KP']), []
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        t = team_stats(rows, g)
        poss = game_poss(t, g) if t else None
        if not poss or poss < 60:
            continue
        m.new_season(g['season'])
        if record_from and g['season'] >= record_from:
            out.append((g['game_id'], g['season'], m.raw(g), g['hs'] - g['as']))
        m.update(g, poss)
    return out


def tune(box):
    """Two coordinate sweeps on the tune seasons' margin MAE, starting from START. Returns (params, tune MAE, shrink (a, b), endpoints hit)."""
    P = dict(START)

    def score(p):
        r = [x for x in walk(p, WARM + TUNE, box, record_from=TUNE[0])]
        return statistics.mean(abs(raw - act) for _, _, raw, act in r)
    best = score(P)
    for _ in range(2):
        for k, vals in GRID.items():
            for v in vals:
                trial = dict(P, **{k: v})
                s = score(trial)
                if s < best - 0.0001:
                    best, P = s, trial
    tr = walk(P, WARM + TUNE, box, record_from=TUNE[0])
    xs, ys = [x[2] for x in tr], [x[3] for x in tr]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    mae_shrunk = statistics.mean(abs(a + b * x - y) for x, y in zip(xs, ys))
    ends = [k for k, v in GRID.items() if P[k] in (v[0], v[-1])]
    return P, best, (a, b), mae_shrunk, ends


def tstat(d):
    n = len(d)
    if n < 50:
        return None
    sd = statistics.pstdev(d) * math.sqrt(n / (n - 1))
    return round(statistics.mean(d) / (sd / math.sqrt(n)), 2) if sd else None


def main():
    box = C.player_games(WARM + TUNE + TEST)
    gm = json.load(open(GM.OUT_JSON))
    PS = dict(GM.DEFAULT, **gm['params'])                       # the shipped parameters, not retuned
    P, tune_mae, (a, b), tune_mae_shrunk, ends = tune(box)
    print('challenger params', P, 'tune MAE raw %.3f shrunk %.3f' % (tune_mae, tune_mae_shrunk), 'shrink a=%.3f b=%.3f' % (a, b), 'endpoints', ends, flush=True)
    ch = {gid: raw for gid, _, raw, _ in walk(P, WARM + TUNE + TEST, box, record_from=TEST[0])}
    lines = C.closing_lines()
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    _, recs = GM.run(PS, WARM + TUNE + TEST, box, lines, inj, record_from=TEST[0])
    R = []
    for r in recs:
        L = r.get('line') or {}
        if L.get('spread_close') is None or r['g']['game_id'] not in ch:
            continue
        S = r['tip'][0]
        A = a + b * ch[r['g']['game_id']]
        B = A + (r['tip'][0] - r['none'][0])
        r['V'] = {'S': S, 'A': A, 'B': B, 'C': (S + B) / 2}
        r['M'] = -L['spread_close']
        R.append(r)
    names = {'S': 'Shipped Vault line (injury report at tip)', 'A': 'Challenger, shrunk', 'B': 'Challenger + shipped injury adjustment', 'C': 'Mean of shipped and B'}
    out = {'params': P, 'tune_mae_raw': round(tune_mae, 3), 'tune_mae_shrunk': round(tune_mae_shrunk, 3), 'shrink': {'a': round(a, 3), 'b': round(b, 3)}, 'endpoints': ends,
           'shipped_params': {k: PS[k] for k in ('K', 'CARRY', 'C', 'REP', 'B2B', 'ALPHA')}, 'seasons': {}}
    for label, sel in [(str(s), lambda r, s=s: r['g']['season'] == s) for s in TEST] + [('pooled', lambda r: True)]:
        G = [r for r in R if sel(r)]
        blk = {'games': len(G), 'market_close_mae': round(statistics.mean(abs(r['M'] - r['actual_margin']) for r in G), 3), 'variants': {}}
        errS = [abs(r['V']['S'] - r['actual_margin']) for r in G]
        gS = None
        for v in 'SABC':
            err = [abs(r['V'][v] - r['actual_margin']) for r in G]
            for r in G:
                r[v] = (r['V'][v], 0.0)
            info = GM.info_test(G, v, 'spread_close', 0)
            ats = GM.ats(G, v, 'spread_close', thresholds=(0, 3))
            blk['variants'][v] = {'mae': round(statistics.mean(err), 3), 'winner': round(statistics.mean((r['V'][v] > 0) == (r['actual_margin'] > 0) for r in G), 4),
                                  't_vs_S': None if v == 'S' else tstat([e0 - e1 for e0, e1 in zip(errS, err)]), 'info': info, 'ats0': ats[0], 'ats3': ats[3]}
        out['seasons'][label] = blk
        print(label, len(G), {v: (x['mae'], x['t_vs_S']) for v, x in blk['variants'].items()}, 'market', blk['market_close_mae'], flush=True)
    # verdicts, by the registered rules
    verdict = {}
    for v in 'ABC':
        p = out['seasons']['pooled']['variants'][v]
        per = [out['seasons'][str(s)]['variants'][v]['t_vs_S'] for s in TEST]
        s_t = out['seasons']['pooled']['variants']['S']['info']['t']
        v_t = p['info']['t'] if p['info'] else None
        matches = p['t_vs_S'] is not None and p['t_vs_S'] > -2
        better = bool(p['t_vs_S'] is not None and p['t_vs_S'] >= 2 and all(x is not None and x > 0 for x in per) and v_t is not None and v_t >= s_t - 1)
        verdict[v] = {'matches': matches, 'better': better, 'pooled_t': p['t_vs_S'], 'season_t': per, 'info_t': v_t, 'info_t_shipped': s_t}
    out['verdict'] = verdict
    out['names'] = names
    out['generated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(out, open(OUT_JSON, 'w'), indent=1)
    write_md(out)
    print(json.dumps(verdict))


def pct(x):
    return '' if x is None else f'{x * 100:.1f}%'


def write_md(o):
    L = ['# Game-model challenger: results', '',
         f"Generated {o['generated']} by `nba/scripts/test_ratings_challenger.py`. Rules, committed before this ran: `nba/docs/game-model-challenger.md`. Four variants, scored once.", '',
         f"Challenger parameters (tune seasons only): K {o['params']['K']}, CARRY {o['params']['CARRY']}, KP {o['params']['KP']}; tune margin MAE {o['tune_mae_raw']} raw, {o['tune_mae_shrunk']} after the shrink "
         f"(margin = {o['shrink']['a']} + {o['shrink']['b']} x raw). {'On a grid endpoint: ' + ', '.join(o['endpoints']) + '.' if o['endpoints'] else 'No parameter on a grid endpoint.'}",
         f"Shipped parameters (not retuned): {o['shipped_params']}.", '']
    for label, blk in o['seasons'].items():
        L += [f"## {'Pooled' if label == 'pooled' else label}: {blk['games']:,} games with a closing spread", '',
              f"Market closing margin MAE: {blk['market_close_mae']}.", '',
              '| Variant | Margin MAE | t vs shipped | Winner | Info test g (t) vs the close | ATS, any edge | ATS, edge 3+ |', '|---|---|---|---|---|---|---|']
        for v, x in blk['variants'].items():
            i = x['info']
            L.append(f"| {v}: {o['names'][v]} | {x['mae']} | {'' if x['t_vs_S'] is None else x['t_vs_S']} | {pct(x['winner'])} | {('%.3f (t %.2f)' % (i['g_model_gap'], i['t'])) if i else ''} | "
                     f"{pct(x['ats0']['win'])} on {x['ats0']['n']} | {pct(x['ats3']['win'])} on {x['ats3']['n']} |")
        L.append('')
    L += ['## Verdicts, by the registered rules', '', '| Variant | Matches the shipped model | Better than it | Pooled t | Season t | Info t (shipped) |', '|---|---|---|---|---|---|']
    for v, x in o['verdict'].items():
        L.append(f"| {v} | {'yes' if x['matches'] else 'no'} | {'yes' if x['better'] else 'no'} | {x['pooled_t']} | {x['season_t']} | {x['info_t']} ({x['info_t_shipped']}) |")
    L += ['', 'Better needs: pooled t >= 2, positive in each season, and the information test t within 1 of the shipped model. A variant that is not Better changes nothing live.', '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
