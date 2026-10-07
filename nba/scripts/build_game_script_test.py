#!/usr/bin/env python3
"""
Game Simulation v2, step B: minutes tied to the game's score. The pre-registered test in docs/game-script-minutes.md.

Fit on 2022-23 to 2024-25 (warm-up 2021-22), score on 2025-26. M3 draws a margin around the game model's pre-game
expected margin, applies the realized-margin minutes coefficients, adds independent noise; B0 is today's independent draw.
  python3 nba/scripts/build_game_script_test.py
Writes nba/data/game_script_minutes.json and nba/docs/game-script-minutes-results.md
"""
import json, math, os, random, statistics, sys
from collections import defaultdict
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM

ROOT = os.path.join(HERE, '..')
WARM, FIT, HOLD = [2022], [2023, 2024, 2025], [2026]
ALPHA, S, SEED = 0.20, 200, 20261007
BUCKETS = [(0, 7), (7, 14), (14, 20), (20, 999)]


def rows_for(box, lines, seasons_all, record_from):
    st = MM.State(ALPHA)
    out = []
    for g in C.games(seasons_all):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= record_from:
            E = lines.get(g['game_id'])
            for team, sgn in ((g['home'], 1), (g['away'], -1)):
                for r in rows:
                    if r['team'] != team or not r['played'] or r['athlete_id'] not in st.pl or st.pl[r['athlete_id']]['team'] != team:
                        continue
                    p = st.pl[r['athlete_id']]
                    out.append({'g': g['game_id'], 'season': g['season'], 'po': g['playoff'], 'team': team, 'aid': r['athlete_id'], 'base': p['m'],
                                'st': p['st'] >= 0.5, 'y': r['minutes'], 'm': sgn * (g['hs'] - g['as']), 'E': None if E is None else sgn * E})
        st.update(g, rows)
    return [r for r in out if r['E'] is not None]


def m2x(m):
    return [1.0, max(0, m - 10), max(0, -m - 10), max(0, m - 20), max(0, -m - 20)]


def m1x(E):
    return [1.0, max(0, abs(E) - 6)]


def fit_models(R):
    mods = {}
    for role in (True, False):
        sub = [r for r in R if r['st'] == role]
        y = [r['y'] - r['base'] for r in sub]
        b1 = MM.ols([m1x(r['E']) for r in sub], y)
        b2 = MM.ols([m2x(r['m']) for r in sub], y)
        res1 = [yy - sum(b * x for b, x in zip(b1, m1x(r['E']))) for yy, r in zip(y, sub)]
        res2 = [yy - sum(b * x for b, x in zip(b2, m2x(r['m']))) for yy, r in zip(y, sub)]
        b0 = statistics.mean(y)
        mods[role] = {'b0': b0, 'b1': b1, 'b2': b2, 'sd1': statistics.pstdev(res1), 'sd2': statistics.pstdev(res2), 'sd0': statistics.pstdev([v - b0 for v in y]), 'n': len(sub)}
    gm = {}
    for r in R:
        gm[r['g']] = r['m'] - r['E']
    # one value per team-game pair is fine; a game contributes both signs, so use pstdev of the pooled values
    sdm = statistics.pstdev([r['m'] - r['E'] for r in R])
    return mods, sdm


def clamp(v):
    return 0.0 if v < 0 else 48.0 if v > 48 else v


def evaluate(R, mods, sdm, seed):
    rng = random.Random(seed)
    by = defaultdict(list)
    for r in R:
        by[(r['g'], r['team'])].append(r)
    acc = {'m3': {'cov': [0, 0], 'pit': [0.0, 0], 'abs': [0.0, 0]}, 'b0': {'cov': [0, 0], 'pit': [0.0, 0], 'abs': [0.0, 0]}, 'm1': {'abs': [0.0, 0]}, 'm0': {'abs': [0.0, 0]}, 'm2': {'abs': [0.0, 0]}}
    split = {'reg': [0, 0], 'po': [0, 0]}
    pair = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, 0.0]))   # kind -> game -> [obs num, obs den, sim num, sim den]
    for (gid, team), grp in by.items():
        E = grp[0]['E']
        ms = [E + sdm * rng.gauss(0, 1) for _ in range(S)]
        sims = {}
        means = {}
        for r in grp:
            M = mods[r['st']]
            b2, sd2 = M['b2'], M['sd2']
            draws = [clamp(r['base'] + sum(b * x for b, x in zip(b2, m2x(m))) + sd2 * rng.gauss(0, 1)) for m in ms]
            sims[id(r)] = draws
            means[id(r)] = sum(draws) / S
            b1 = sum(b * x for b, x in zip(M['b1'], m1x(E)))
            mu1 = clamp(r['base'] + b1)
            acc['m1']['abs'][0] += abs(mu1 - r['y']); acc['m1']['abs'][1] += 1
            acc['m0']['abs'][0] += abs(clamp(r['base'] + M['b0']) - r['y']); acc['m0']['abs'][1] += 1
            acc['m2']['abs'][0] += abs(clamp(r['base'] + sum(b * x for b, x in zip(b2, m2x(r['m'])))) - r['y']); acc['m2']['abs'][1] += 1
            acc['m3']['abs'][0] += abs(means[id(r)] - r['y']); acc['m3']['abs'][1] += 1
            if r['st']:
                for key, dr in (('m3', sorted(draws)), ('b0', sorted(clamp(mu1 + M['sd1'] * rng.gauss(0, 1)) for _ in range(S)))):
                    lo, hi = dr[int(.1 * S)], dr[int(.9 * S) - 1]
                    acc[key]['cov'][0] += 1 if lo <= r['y'] <= hi else 0; acc[key]['cov'][1] += 1
                    below = sum(1 for v in dr if v < r['y']); eq = sum(1 for v in dr if v == r['y'])
                    acc[key]['pit'][0] += (below + 0.5 * eq) / S; acc[key]['pit'][1] += 1
                k = 'po' if r['po'] else 'reg'
                dr = sorted(draws)
                split[k][0] += 1 if dr[int(.1 * S)] <= r['y'] <= dr[int(.9 * S) - 1] else 0; split[k][1] += 1
        # togetherness of minute residuals within the team-game, by player-type pair
        for a, b in combinations(grp, 2):
            kind = 'ss' if a['st'] and b['st'] else 'bb' if not a['st'] and not b['st'] else 'sb'
            ea, eb = a['y'] - means[id(a)], b['y'] - means[id(b)]
            P = pair[kind][gid]
            P[0] += ea * eb; P[1] += 1
            # simulated: residuals of the draws around the same mean, averaged over the draws
            da, db = sims[id(a)], sims[id(b)]
            P[2] += sum((x - means[id(a)]) * (y - means[id(b)]) for x, y in zip(da, db)) / S
        for r in grp:
            for kind in ('ss', 'bb', 'sb'):
                pass
    # pair-correlation estimates: sum of cross products over pairs divided by pooled variance of residuals of the player type
    return acc, split, pair, by


def ratio(num, den):
    """pooled ratio with game-clustered SE: num and den are lists per game"""
    N, D = sum(num), sum(den)
    r = N / D if D else float('nan')
    se = math.sqrt(sum((n - r * d) ** 2 for n, d in zip(num, den))) / D if D else float('nan')
    return r, se


def main():
    box = C.player_games(WARM + FIT + HOLD)
    lines = MM.expected_margins(box)
    allr = rows_for(box, lines, WARM + FIT + HOLD, FIT[0])
    fitR = [r for r in allr if r['season'] in FIT]
    holdR = [r for r in allr if r['season'] in HOLD]
    mods, sdm = fit_models(fitR)
    acc, split, pair, by = evaluate(holdR, mods, sdm, SEED)

    # variance of minute residuals per role from the holdout, for turning the cross products into correlations
    var = {}
    for role in (True, False):
        v = []
        for (gid, team), grp in by.items():
            pass
    # observed/model-implied correlation: cross products divided by the geometric mean of the two residual variances
    # (residuals around M3's mean given the expected margin); per-game totals for the clustered ratio
    resvar = {True: [], False: []}
    # recompute residual variances (obs) and implied (sim) by role
    rng = random.Random(SEED + 1)
    obs_var = {True: [0.0, 0], False: [0.0, 0]}
    sim_var = {True: [0.0, 0], False: [0.0, 0]}
    for (gid, team), grp in by.items():
        E = grp[0]['E']; ms = [E + sdm * rng.gauss(0, 1) for _ in range(S)]
        for r in grp:
            M = mods[r['st']]
            draws = [clamp(r['base'] + sum(b * x for b, x in zip(M['b2'], m2x(m))) + M['sd2'] * rng.gauss(0, 1)) for m in ms]
            mu = sum(draws) / S
            obs_var[r['st']][0] += (r['y'] - mu) ** 2; obs_var[r['st']][1] += 1
            sim_var[r['st']][0] += sum((x - mu) ** 2 for x in draws) / S; sim_var[r['st']][1] += 1
    ov = {k: v[0] / v[1] for k, v in obs_var.items()}; sv = {k: v[0] / v[1] for k, v in sim_var.items()}
    corr = {}
    for kind, (ra, rb) in (('ss', (True, True)), ('sb', (True, False)), ('bb', (False, False))):
        gids = sorted(pair[kind])
        on = [pair[kind][g][0] for g in gids]; od = [pair[kind][g][1] * math.sqrt(ov[ra] * ov[rb]) for g in gids]
        sn = [pair[kind][g][2] for g in gids]; sd_ = [pair[kind][g][1] * math.sqrt(sv[ra] * sv[rb]) for g in gids]
        ro, so = ratio(on, od); rs, _ = ratio(sn, sd_)
        corr[kind] = {'obs': ro, 'obs_se': so, 'sim': rs, 'pairs': sum(pair[kind][g][1] for g in gids)}

    cov = lambda k: acc[k]['cov'][0] / acc[k]['cov'][1]
    pit = lambda k: acc[k]['pit'][0] / acc[k]['pit'][1]
    mae = {k: acc[k]['abs'][0] / acc[k]['abs'][1] for k in ('m0', 'm1', 'm2', 'm3')}
    c = corr['ss']
    g1 = 0.76 <= cov('m3') <= 0.84 and abs(pit('m3') - 0.5) <= 0.02 and abs(cov('m3') - 0.8) <= abs(cov('b0') - 0.8) + 0.01
    lo, hi = c['obs'] - 1.96 * c['obs_se'], c['obs'] + 1.96 * c['obs_se']
    g2 = lo <= c['sim'] <= hi and (lo > 0 or hi < 0)
    g3 = abs(mae['m3'] - mae['m1']) <= 0.05
    verdict = 'GO' if g1 and g2 and g3 else 'NO-GO'

    # informational: minutes by realized |margin| bucket (holdout starters) and over rates by bucket on the sportsbook legs
    margin_of = {r['g']: abs(r['m']) for r in allr}
    bk = []
    for a, b in BUCKETS:
        st_ = [r['y'] for r in holdR if r['st'] and a <= abs(r['m']) < b]
        bn = [r['y'] for r in holdR if not r['st'] and a <= abs(r['m']) < b]
        bk.append({'bucket': f'{a}-{b}' if b < 999 else f'{a}+', 'starter_min': statistics.mean(st_) if st_ else None, 'n': len(st_), 'bench_min': statistics.mean(bn) if bn else None})
    import build_copula_fit as CF
    overs = []
    for season, tag in ((2025, 'fit 2024-25'), (2026, 'holdout 2025-26')):
        G = CF.legs(season, 'open')
        for a, b in BUCKETS:
            n = h = 0; sres = 0.0
            for gid, L in G.items():
                mg = margin_of.get(int(gid))
                if mg is None or not (a <= mg < b):
                    continue
                for leg in L:
                    n += 1; sres += leg[4] - leg[3]
            overs.append({'season': tag, 'bucket': f'{a}-{b}' if b < 999 else f'{a}+', 'legs': n, 'over_minus_price': sres / n if n else None})

    res = {'rules': 'docs/game-script-minutes.md', 'verdict': verdict, 'fit_rows': len(fitR), 'hold_rows': len(holdR), 'margin_sd': sdm,
           'models': {('starter' if k else 'bench'): {kk: ([round(x, 4) for x in vv] if isinstance(vv, list) else round(vv, 4)) for kk, vv in v.items()} for k, v in mods.items()},
           'coverage': {'m3': cov('m3'), 'b0': cov('b0')}, 'pit_mean': {'m3': pit('m3'), 'b0': pit('b0')}, 'mae': mae,
           'corr': corr, 'gates': {'coverage_pit': g1, 'togetherness': g2, 'mean_mae': g3}, 'split_cov': {k: (v[0] / v[1] if v[1] else None) for k, v in split.items()},
           'buckets': bk, 'overs': overs}
    json.dump(res, open(os.path.join(ROOT, 'data', 'game_script_minutes.json'), 'w'), indent=1, default=float)

    f = lambda x: 'n/a' if x is None else f'{x:.3f}'
    L = ['# Game Simulation v2, step B: minutes tied to the game\'s score, results', '', f"Rules: docs/game-script-minutes.md (committed before the test). Verdict: **{verdict}**.", '',
         f"- Fit: {len(fitR):,} player-games (2022-23 to 2024-25). Holdout 2025-26: {len(holdR):,}. Spread of (realized margin - expected margin): {sdm:.2f} points.", '',
         '| Check | Rule | Result | Pass |', '|---|---|---|---|',
         f"| Starters: central-80% coverage, M3 | 76% to 84% | {cov('m3') * 100:.1f}% (B0, today's independent draw: {cov('b0') * 100:.1f}%) | {'yes' if 0.76 <= cov('m3') <= 0.84 and abs(cov('m3') - 0.8) <= abs(cov('b0') - 0.8) + 0.01 else 'NO'} |",
         f"| Starters: mean rank of the actual minutes, M3 | 0.50 +/- 0.02 | {pit('m3'):.3f} (B0 {pit('b0'):.3f}) | {'yes' if abs(pit('m3') - 0.5) <= 0.02 else 'NO'} |",
         f"| Starters' minute residuals move together | model inside the observed 95% interval, interval excludes 0 | observed {c['obs']:+.3f} ({lo:+.3f} to {hi:+.3f}), model {c['sim']:+.3f}, independent draw 0 | {'yes' if g2 else 'NO'} |",
         f"| Mean minutes, M3 vs M1 | within 0.05 min MAE | M3 {mae['m3']:.3f}, M1 {mae['m1']:.3f} | {'yes' if g3 else 'NO'} |", '',
         f"MAE (minutes, all players): M0 base only {mae['m0']:.3f}; M1 pre-game blowout term {mae['m1']:.3f}; M2 realized margin (hindsight) {mae['m2']:.3f}; M3 simulated margin {mae['m3']:.3f}.", '',
         '## Informational', '',
         f"- Residual correlation within a team, observed (game-clustered SE) against model-implied: starters with starters {corr['ss']['obs']:+.3f} (SE {corr['ss']['obs_se']:.3f}) vs {corr['ss']['sim']:+.3f}; starters with bench {corr['sb']['obs']:+.3f} ({corr['sb']['obs_se']:.3f}) vs {corr['sb']['sim']:+.3f}; bench with bench {corr['bb']['obs']:+.3f} ({corr['bb']['obs_se']:.3f}) vs {corr['bb']['sim']:+.3f}.",
         f"- Starter coverage by season type: regular season {f(res['split_cov']['reg'])}, play-in and playoffs {f(res['split_cov']['po'])}.", '',
         '| Realized margin | Holdout starters (n) | Avg starter minutes | Avg bench minutes |', '|---|---|---|---|']
    for b in bk:
        L.append(f"| {b['bucket']} | {b['n']:,} | {f(b['starter_min'])} | {f(b['bench_min'])} |")
    L += ['', '| Season | Realized margin | Sportsbook legs | Over hit rate minus no-vig price |', '|---|---|---|---|']
    for o in overs:
        L.append(f"| {o['season']} | {o['bucket']} | {o['legs']:,} | {'n/a' if o['over_minus_price'] is None else f'{o['over_minus_price'] * 100:+.1f} pts'} |")
    L += ['', '## Coefficients (minutes added to the recency base; margin m = the player\'s team margin, positive = won)', '',
          '| Role | const | winner beyond 10 | loser beyond 10 | winner beyond 20 | loser beyond 20 | noise sd |', '|---|---|---|---|---|---|---|']
    for role in ('starter', 'bench'):
        M = res['models'][role]; b = M['b2']
        L.append(f"| {role} | {b[0]:+.2f} | {b[1]:+.3f} | {b[2]:+.3f} | {b[3]:+.3f} | {b[4]:+.3f} | {M['sd2']:.2f} |")
    open(os.path.join(ROOT, 'docs', 'game-script-minutes-results.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
