#!/usr/bin/env python3
"""
Correlated pick'em pairs: the pre-registered test in docs/pickem-correlation.md (Phase 3 of Player Props v2).

For legs from different players in the same game, the covariance of the market residuals (outcome - no-vig P(over))
says whether two picks hit together more than their single-leg prices say. Families = teammates / opponents x stat
pair. Explore on 2024-25, freeze candidates (2,000+ pairs, |z| >= 3, game-clustered), test on 2025-26 (same sign,
z >= 2, |c| >= 0.01). -> data/pickem_corr.json and docs/pickem-correlation-results.md
"""
import csv, json, math, os, sys
from collections import defaultdict
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_hit_rates import devig, real_main

ROOT = os.path.join(HERE, '..')
STATS = ('pts', 'reb', 'ast', '3pm', 'pra')
MIN_PAIRS, Z_EXPLORE, Z_TEST, MIN_C = 2000, 3.0, 2.0, 0.01
SL = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists', '3pm': '3-pointers', 'pra': 'pts + reb + ast'}


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
    rel = 'team' if a[1] == b[1] else 'opp'
    s1, s2 = sorted((a[2], b[2]), key=STATS.index)
    return (rel, s1, s2)


def families(G):
    """family -> {n pairs, c (mean residual product), z (game-clustered), joint / indep for ~50% legs, over-over rate}"""
    per = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))     # fam -> game -> [pairs, sum r*r]
    oo = defaultdict(lambda: [0.0, 0.0])                          # fam -> [sum oo outcome, sum p*q]
    for gid, L in G.items():
        for a, b in combinations(L, 2):
            if a[0] == b[0]:
                continue
            f = fam_key(a, b)
            x = per[f][gid]
            x[0] += 1
            x[1] += (a[4] - a[3]) * (b[4] - b[3])
            o = oo[f]
            o[0] += a[4] * b[4]
            o[1] += a[3] * b[3]
    out = {}
    for f, games in per.items():
        n = sum(v[0] for v in games.values())
        s = sum(v[1] for v in games.values())
        c = s / n
        # clustered variance of the mean: sum over games of (S_g - c n_g)^2 / n^2
        var = sum((v[1] - c * v[0]) ** 2 for v in games.values()) / n ** 2
        se = math.sqrt(var) if var > 0 else float('nan')
        out[f] = {'rel': f[0], 'a': f[1], 'b': f[2], 'n': n, 'games': len(games), 'c': round(c, 5), 'se': round(se, 5),
                  'z': round(c / se, 2) if se == se and se > 0 else 0, 'lift': round(1 + c / 0.25, 4),
                  'oo': round(oo[f][0] / n, 4), 'oo_indep': round(oo[f][1] / n, 4)}
    return out


def name(f):
    return f"{'Teammates' if f['rel'] == 'team' else 'Opponents'}: {SL[f['a']]} with {SL[f['b']]}"


def combo(c):
    return 'over / over (or under / under)' if c > 0 else 'over / under'


def main():
    explore = families(legs(2025, 'open'))
    test = families(legs(2026, 'open'))
    close = families(legs(2026, 'close'))
    cands = [f for f in explore.values() if f['n'] >= MIN_PAIRS and abs(f['z']) >= Z_EXPLORE]
    rows = []
    for f in sorted(explore.values(), key=lambda f: -abs(f['z'])):
        k = (f['rel'], f['a'], f['b'])
        t, cl = test.get(k), close.get(k)
        cand = f in cands
        passed = bool(cand and t and t['c'] * f['c'] > 0 and abs(t['z']) >= Z_TEST and abs(t['c']) >= MIN_C)
        rows.append({'family': name(f), 'key': list(k), 'combo': combo(f['c']), 'candidate': cand, 'pass': passed,
                     'explore': f, 'test': t, 'close': cl})
    res = {'rules': {'min_pairs': MIN_PAIRS, 'z_explore': Z_EXPLORE, 'z_test': Z_TEST, 'min_c': MIN_C},
           'n_legs': {'explore': None, 'test': None}, 'families': rows,
           'verdict': 'GO' if any(r['pass'] for r in rows) else 'NO-GO'}
    json.dump(res, open(os.path.join(ROOT, 'data', 'pickem_corr.json'), 'w'), indent=1)
    L = ['# Correlated pick\'em pairs: results', '', f"Rules: docs/pickem-correlation.md. Verdict: **{res['verdict']}**.", '',
         '| Family | Combo | 2024-25 pairs | c | z | 2025-26 pairs | c | z | lift | close z | Candidate | Pass |',
         '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        e, t, cl = r['explore'], r['test'] or {}, r['close'] or {}
        L.append(f"| {r['family']} | {r['combo']} | {e['n']:,} | {e['c']:+.4f} | {e['z']:+.1f} | {t.get('n', 0):,} | {t.get('c', 0):+.4f} | "
                 f"{t.get('z', 0):+.1f} | {t.get('lift', 1):.3f} | {cl.get('z', 0):+.1f} | {'yes' if r['candidate'] else ''} | {'PASS' if r['pass'] else ''} |")
    open(os.path.join(ROOT, 'docs', 'pickem-correlation-results.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
