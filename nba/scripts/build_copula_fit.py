#!/usr/bin/env python3
"""
Game Simulation v2, step A: the pre-registered copula fit in docs/copula-fit.md.

A Gaussian copula over the market's no-vig single-leg chances. rho per family (relationship x stat pair) is fitted by maximum
likelihood on 2024-25 pairs (each pair's outcome: over or under on each leg), frozen by the rules, then scored on 2025-26.
Standard errors are game-clustered. -> data/copula_corr.json and docs/copula-fit-results.md
"""
import csv, json, math, os, sys
from collections import defaultdict
from itertools import combinations
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_hit_rates import devig, real_main

ROOT = os.path.join(HERE, '..')
STATS = ('pts', 'reb', 'ast', '3pm')
SL = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': '3-pointers'}
MIN_PAIRS, Z_KEEP, RHO_KEEP, Z_PASS = 2000, 2.0, 0.02, 2.0
ND = NormalDist()
NTERM = 5


def legs(season, when):
    """game -> [(athlete, team, stat, p_over, outcome)] one leg per player, stat and game."""
    G, seen = defaultdict(list), set()
    for r in csv.DictReader(open(os.path.join(ROOT, 'raw', 'tables', 'props_espn.csv'))):
        if r['kind'] != 'main' or r['season'] != str(season) or r['market'] not in STATS or r['played'] != '1' or r['actual'] == '':
            continue
        if when == 'open':
            line, po, pu = r['line_open'], r['over_px_open'], r['under_px_open']
        else:
            if r['cur_is_pretip'] != '1':
                continue
            line, po, pu = r['line_cur'], r['over_px_cur'], r['under_px_cur']
        if not line or not real_main(po, pu):
            continue
        k = (r['game_id'], r['athlete_id'], r['market'])
        if k in seen:
            continue
        p, line, y = devig(po, pu), float(line), float(r['actual'])
        if p is None or y == line:
            continue
        seen.add(k)
        G[r['game_id']].append((r['athlete_id'], r['team'], r['market'], p, 1.0 if y > line else 0.0))
    return G


def fam_key(a, b):
    rel = 'self' if a[0] == b[0] else 'team' if a[1] == b[1] else 'opp'
    s1, s2 = sorted((a[2], b[2]), key=STATS.index)
    return (rel, s1, s2)


def pair_rec(a, b):
    """(P0, s, [d1..d5], p1, p2, over-over): the pair's outcome chance is P0 + s * sum(rho^n d_n) under the copula."""
    p1, p2 = a[3], b[3]
    h1, h2 = ND.inv_cdf(1 - p1), ND.inv_cdf(1 - p2)
    ph = ND.pdf(h1) * ND.pdf(h2)
    he1 = (1.0, h1, h1 * h1 - 1, h1 ** 3 - 3 * h1, h1 ** 4 - 6 * h1 * h1 + 3)
    he2 = (1.0, h2, h2 * h2 - 1, h2 ** 3 - 3 * h2, h2 ** 4 - 6 * h2 * h2 + 3)
    d = [ph * he1[n - 1] * he2[n - 1] / math.factorial(n) for n in range(1, NTERM + 1)]
    y1, y2 = a[4], b[4]
    P0 = (p1 if y1 else 1 - p1) * (p2 if y2 else 1 - p2)
    return (P0, 1.0 if y1 == y2 else -1.0, d, p1 * p2, 1.0 if (y1 and y2) else 0.0)


def collect(G, fams=None):
    """family -> game -> [pair records]"""
    out = defaultdict(lambda: defaultdict(list))
    for gid, L in G.items():
        for a, b in combinations(L, 2):
            f = fam_key(a, b)
            if fams is not None and f not in fams:
                continue
            out[f][gid].append(pair_rec(a, b))
    return out


def D(d, rho, k=0):
    """k-th derivative in rho of sum rho^n d_n"""
    if k == 0:
        return sum(d[n - 1] * rho ** n for n in range(1, NTERM + 1))
    if k == 1:
        return sum(n * d[n - 1] * rho ** (n - 1) for n in range(1, NTERM + 1))
    return sum(n * (n - 1) * d[n - 1] * rho ** (n - 2) for n in range(2, NTERM + 1))


def ll(recs, rho):
    t = 0.0
    for P0, s, d, _, _ in recs:
        t += math.log(max(1e-12, P0 + s * D(d, rho)))
    return t


def fit(games):
    recs = [r for g in games.values() for r in g]
    lo, hi, gr = -0.45, 0.45, (math.sqrt(5) - 1) / 2
    a, b = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fa, fb = ll(recs, a), ll(recs, b)
    for _ in range(45):
        if fa > fb:
            hi, b, fb = b, a, fa
            a = hi - gr * (hi - lo); fa = ll(recs, a)
        else:
            lo, a, fa = a, b, fb
            b = lo + gr * (hi - lo); fb = ll(recs, b)
    rho = (lo + hi) / 2
    H, scores = 0.0, []
    for g in games.values():
        u = 0.0
        for P0, s, d, _, _ in g:
            f = max(1e-12, P0 + s * D(d, rho)); g1 = s * D(d, rho, 1) / f; g2 = s * D(d, rho, 2) / f - g1 * g1
            u += g1; H -= g2
        scores.append(u)
    se = math.sqrt(sum(u * u for u in scores)) / H if H > 0 else float('nan')
    return rho, se


def clustered_total(per_game):
    """total over games and its game-clustered standard error"""
    n = len(per_game)
    T = sum(per_game)
    m = T / n
    se = math.sqrt(sum((x - m) ** 2 for x in per_game) * n / max(1, n - 1)) if n > 1 else float('nan')
    return T, se


def score_model(rho_of, G, fams=None):
    """per-game sums of log-likelihood gain under the frozen model, plus the calibration-slope pieces"""
    per_game, byfam, slope = [], defaultdict(list), []
    P = collect(G, fams)
    by_game = defaultdict(float); fam_game = defaultdict(lambda: defaultdict(float)); sg = defaultdict(lambda: [0.0, 0.0])
    npairs = 0
    for f, games in P.items():
        rho = rho_of.get(f, 0.0)
        if rho == 0.0:
            continue
        for gid, recs in games.items():
            for P0, s, d, indep, oo in recs:
                Dv = D(d, rho)
                gain = math.log(max(1e-12, P0 + s * Dv) / P0)
                by_game[gid] += gain; fam_game[f][gid] += gain
                e = oo - indep
                sg[gid][0] += Dv * e; sg[gid][1] += Dv * Dv
                npairs += 1
    gids = list(G.keys())
    tot = [by_game.get(g, 0.0) for g in gids]
    T, se = clustered_total(tot)
    # calibration slope of (over-over - independent) on the copula's predicted difference
    num = sum(v[0] for v in sg.values()); den = sum(v[1] for v in sg.values())
    b = num / den if den > 0 else float('nan')
    var = sum((v[0] - b * v[1]) ** 2 for v in sg.values()) / den ** 2 if den > 0 else float('nan')
    fams_out = {}
    for f, gm in fam_game.items():
        ft = [gm.get(g, 0.0) for g in gids]
        t, s_ = clustered_total(ft)
        fams_out[f] = (t, s_)
    return {'pairs': npairs, 'gain': T, 'gain_se': se, 'z': T / se if se and se == se else 0, 'slope': b, 'slope_se': math.sqrt(var) if var == var else float('nan'), 'fams': fams_out, 'games': len(gids)}


def lift(rho):
    return (0.25 + math.asin(max(-1, min(1, rho))) / (2 * math.pi)) / 0.25


def name(f):
    rel, a, b = f
    return f"{'Same player' if rel == 'self' else 'Teammates' if rel == 'team' else 'Opponents'}: {SL[a]} with {SL[b]}"


def main():
    Ge, Gt, Gc = legs(2025, 'open'), legs(2026, 'open'), legs(2026, 'close')
    Pe = collect(Ge)
    fits = {}
    for f, games in Pe.items():
        n = sum(len(g) for g in games.values())
        rho, se = fit(games)
        z = rho / se if se and se == se and se > 0 else 0.0
        fits[f] = {'n': n, 'games': len(games), 'rho': rho, 'se': se, 'z': z,
                   'keep': n >= MIN_PAIRS and abs(z) >= Z_KEEP and abs(rho) >= RHO_KEEP}
    frozen = {f: v['rho'] for f, v in fits.items() if v['keep']}
    test = score_model(frozen, Gt)
    close = score_model(frozen, Gc)
    # informational: one rho per relationship
    pooled = {}
    for rel in ('self', 'team', 'opp'):
        gm = defaultdict(list)
        for f, games in Pe.items():
            if f[0] == rel:
                for gid, recs in games.items():
                    gm[gid] += recs
        r_, _ = fit(gm)
        for f in Pe:
            if f[0] == rel:
                pooled[f] = r_
    ptest = score_model(pooled, Gt)
    # informational: agreement with the covariance method
    cov = {}
    try:
        for r in json.load(open(os.path.join(ROOT, 'data', 'pickem_corr.json')))['families']:
            cov[tuple(r['key'])] = r['explore']['c']
    except Exception:
        pass
    pairs_ = [(fits[f]['rho'], cov[f]) for f in fits if f in cov and f[0] != 'self']
    agree = (sum(1 for a, b in pairs_ if a * b > 0), len(pairs_))

    slope_ok = test['slope'] == test['slope'] and test['slope'] - 1.96 * test['slope_se'] <= 1 <= test['slope'] + 1.96 * test['slope_se'] \
        and test['slope'] - 1.96 * test['slope_se'] > 0
    verdict = 'GO' if test['z'] >= Z_PASS and slope_ok else 'NO-GO'
    rows = []
    for f, v in sorted(fits.items(), key=lambda kv: -abs(kv[1]['z'])):
        t = test['fams'].get(f)
        rows.append({'rel': f[0], 'a': f[1], 'b': f[2], 'family': name(f), **{k: (round(x, 5) if isinstance(x, float) else x) for k, x in v.items()},
                     'lift50': round(lift(v['rho']), 4), 'test_gain': round(t[0], 3) if t else None, 'test_z': round(t[0] / t[1], 2) if t and t[1] else None})
    res = {'rules': {'min_pairs': MIN_PAIRS, 'z_keep': Z_KEEP, 'rho_keep': RHO_KEEP, 'z_pass': Z_PASS}, 'verdict': verdict,
           'frozen': [{'rel': f[0], 'a': f[1], 'b': f[2], 'rho': round(r, 5)} for f, r in sorted(frozen.items())],
           'test': {k: (round(v, 5) if isinstance(v, float) else v) for k, v in test.items() if k != 'fams'},
           'close': {k: (round(v, 5) if isinstance(v, float) else v) for k, v in close.items() if k != 'fams'},
           'pooled': {k: (round(v, 5) if isinstance(v, float) else v) for k, v in ptest.items() if k != 'fams'},
           'cov_agree': agree, 'families': rows}
    json.dump(res, open(os.path.join(ROOT, 'data', 'copula_corr.json'), 'w'), indent=1)

    def zs(t): return f"{t['gain']:+.1f} log-lik, SE {t['gain_se']:.1f}, z {t['z']:+.2f}"
    L = ['# Game Simulation v2, step A: copula fit results', '', f"Rules: docs/copula-fit.md (committed before the fit). Verdict: **{verdict}**.", '',
         f"- Kept families (frozen): {len(frozen)} of {len(fits)}. Explore: {len(Ge)} games / {sum(len(v) for v in Ge.values()):,} legs. Test: {len(Gt)} games / {sum(len(v) for v in Gt.values()):,} legs.",
         f"- **Test total gain over independence (2025-26, opening prices):** {zs(test)} on {test['pairs']:,} pairs. Rule: z >= {Z_PASS}.",
         f"- **Calibration slope:** {test['slope']:.2f} (95% interval {test['slope'] - 1.96 * test['slope_se']:.2f} to {test['slope'] + 1.96 * test['slope_se']:.2f}). Rule: contains 1 and excludes 0.",
         f"- Robustness, frozen model on pre-tip closing prices: {zs(close)} on {close['pairs']:,} pairs; slope {close['slope']:.2f}.",
         f"- Informational, one rho per relationship instead of per family: {zs(ptest)}.",
         f"- Informational, sign agreement with the covariance method (teammates and opponents): {agree[0]} of {agree[1]} families.", '',
         '| Family | Pairs | rho | SE | z | Kept | 2-pick lift at 50% | Test gain | Test z |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['family']} | {r['n']:,} | {r['rho']:+.3f} | {r['se']:.3f} | {r['z']:+.1f} | {'yes' if r['keep'] else ''} | {r['lift50']:.3f} | "
                 f"{'' if r['test_gain'] is None else f'{r['test_gain']:+.1f}'} | {'' if r['test_z'] is None else f'{r['test_z']:+.1f}'} |")
    open(os.path.join(ROOT, 'docs', 'copula-fit-results.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
