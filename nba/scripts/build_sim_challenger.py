#!/usr/bin/env python3
"""
Simulation challenger: does turning a prop projection into "N simulated games" help, hurt, or change nothing?

Prompted by a public NBA prop page that shows 50 simulated games per player. Rules are in docs/sim-challenger.md
(written before the first run); the pass bars below are the ones written there.

Everything is the v2 walk-forward (build_prop_model_v2.py): fit on 2024-25, tested on 2025-26, identical player-games and
prices for every variant. Only the way the probability is made differs:

  v2           analytic: v2 mean and variance, negative binomial for counts, Normal for points, isotonic calibration. The baseline.
  sim10k       the same mean and variance, but P(over) is the share of 10,000 simulated games over the line. Measures Monte Carlo
               error at a large N; it should match v2 to within noise.
  sim50        the same again with 50 simulated games (probability smoothed (k+.5)/(N+1)). The cost of 50 draws on its own.
  sam50        "Sam style": v1 mean (rate x minutes, no stacker), v1 spread, Normal draws for every stat floored at 0, 50 games,
               smoothed, then calibrated on 2024-25 like the others.
  sam50_shown  sam50 exactly as a page would display it: raw share of the 50 games over, no smoothing, no calibration.

Single props only (pts, reb, ast, 3pm): combo markets need the joint model and are tested by the Game Simulation record.

Scored on every ESPN pre-tip close line and Kalshi pre-tip strike of 2025-26: log loss and Brier against the de-vigged
market, paired log-loss difference against v2 with a game-clustered standard error, the blend t (does the variant add anything
on top of the price), how often the variant disagrees with v2 about which side of the price the true chance is on, and how far
its probability sits from v2's (the Monte Carlo noise, against what sqrt(p(1-p)/N) predicts).

  python3 nba/scripts/build_sim_challenger.py
Writes data/sim_challenger.json and docs/sim-challenger-results.md.
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nba_common as C
import build_minutes_model as MM
import build_prop_model as V1
import build_prop_model_v2 as V2
from build_prop_model import BASE, COUNT_MKTS, pav, apply_cal, am_prob, blend

OUT_JSON = os.path.join(HERE, '..', 'data', 'sim_challenger.json')
OUT_MD = os.path.join(HERE, '..', 'docs', 'sim-challenger-results.md')
MKTS = ['pts', 'reb', 'ast', '3pm']
SEED = 20261020
CHUNK = 1500
VARIANTS = ['v2', 'sim10k', 'sim50', 'sam50', 'sam50_shown']
NDRAWS = {'sim10k': 10000, 'sim50': 50, 'sam50': 50, 'sam50_shown': 50}


def spread(V, mkt, mu, extra):
    v = V[mkt]
    return max(0.25, v[0] + v[1] * mu + v[2] * mu * mu + (v[3] * extra if len(v) > 3 else 0.0))


def draws_share_over(rng, mkt, mu, var, L, N, normal_only=False):
    """Share of N simulated games over L, one row per (mu, var, L). Counts: gamma-Poisson (Poisson when var <= mu). Else Normal."""
    n = len(mu)
    out = np.empty(n)
    for a in range(0, n, CHUNK):
        m, v, l = mu[a:a + CHUNK, None], var[a:a + CHUNK, None], L[a:a + CHUNK, None]
        if mkt in COUNT_MKTS and not normal_only:
            lam = np.where(v > m * 1.0001, rng.gamma(np.maximum(m * m / np.maximum(v - m, 1e-9), 1e-6), 1.0, size=(len(m), N)) * np.maximum(v - m, 0) / np.maximum(m, 1e-9), m)
            x = rng.poisson(np.broadcast_to(lam, (len(m), N)))
        else:
            x = rng.normal(m, np.sqrt(v), size=(len(m), N))
            if normal_only:
                x = np.maximum(x, 0.0)
        out[a:a + CHUNK] = (x > l).mean(axis=1)
    return out


def main():
    box = C.player_games(V2.SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    recs, ctx = V2.walk(box, inj, margins, mm, casc, V2.team_min(), C.closing_lines())
    fit = [r for r in recs if r['season'] == V2.FIT]
    stk = V2.fit_stacker(fit)
    mf2 = lambda r: V2.mu2(r, stk)
    V2v = V2.fit_var(fit, mf2, True)
    V1v = V2.fit_var(fit, V2.mu1, False)
    print(f'fit player-games {len(fit):,}', flush=True)

    by = {(r['gid'], r['aid']): r for r in recs}
    espn = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if row['kind'] != 'main' or row['played'] != '1' or row['market'] not in MKTS:
            continue
        r = by.get((int(row['game_id']), int(row['athlete_id'])))
        if not r:
            continue
        act = float(row['actual'])
        for clock, line, opx, upx in (('open', row['line_open'], row['over_px_open'], row['under_px_open']),
                                      ('close', row['line_cur'], row['over_px_cur'], row['under_px_cur'])):
            if clock == 'close' and row['cur_is_pretip'] != '1':
                continue
            po, pu = am_prob(opx), am_prob(upx)
            if not line or po is None or pu is None or not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
                continue
            L = float(line)
            if act == L:
                continue
            espn[(row['season'], row['market'], clock)].append({'r': r, 'L': L, 'pk': po / (po + pu), 'y': act > L, 'gid': row['game_id']})
    kal = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_kalshi.csv'))):
        if row['result'] not in ('yes', 'no') or row['played'] != '1' or row['market'] not in MKTS:
            continue
        r = by.get((int(row['game_id']), int(row['athlete_id'])))
        px = row['yes_vwap30_pretip'] or row['yes_last_pretip']
        if not r or not px or not (0.05 < float(px) < 0.95):
            continue
        kal[row['market']].append({'r': r, 'L': float(row['strike']), 'pk': float(px), 'y': row['result'] == 'yes', 'gid': row['game_id']})

    def params(rows, mkt, which):
        """mean, variance, line arrays for a variant family ('v2' = stacked mean + v2 spread, 'v1' = plain mean + v1 spread)."""
        if which == 'v2':
            mu = np.array([mf2(x['r'])[mkt] for x in rows])
            var = np.array([spread(V2v, mkt, m, (V2.minrate(x['r'], mkt) * x['r']['sdm']) ** 2) for x, m in zip(rows, mu)])
        else:
            mu = np.array([V2.mu1(x['r'])[mkt] for x in rows])
            var = np.array([spread(V1v, mkt, m, 0.0) for x, m in zip(rows, mu)])
        return mu, var, np.array([x['L'] for x in rows])

    def analytic(rows, mkt):
        mu, var, L = params(rows, mkt, 'v2')
        return np.array([V2.p_over(mkt, m, l, V2v, (V2.minrate(x['r'], mkt) * x['r']['sdm']) ** 2) for x, m, l in zip(rows, mu, L)])

    def raw_p(variant, rows, mkt, rng):
        if variant == 'v2':
            return analytic(rows, mkt)
        which = 'v1' if variant.startswith('sam') else 'v2'
        mu, var, L = params(rows, mkt, which)
        N = NDRAWS[variant]
        s = draws_share_over(rng, mkt, mu, var, L, N, normal_only=variant.startswith('sam'))
        return s if variant == 'sam50_shown' else (s * N + 0.5) / (N + 1)

    rng = np.random.default_rng(SEED)
    cal = {}
    for v in VARIANTS:
        if v in ('sam50_shown', 'sim10k', 'sim50'):
            continue            # sim10k and sim50 reuse v2's calibration (amendment, docs/sim-challenger.md): only the probability engine differs
        cal[v] = {}
        for mkt in MKTS:
            fr = espn.get(('2025', mkt, 'open'), [])
            p = raw_p(v, fr, mkt, rng)
            cal[v][mkt] = pav([(float(pi), 1 if x['y'] else 0) for pi, x in zip(p, fr)])

    def final(variant, rows, mkt, rng):
        p = raw_p(variant, rows, mkt, rng)
        if variant == 'sam50_shown':
            return p
        k = 'v2' if variant in ('sim10k', 'sim50') else variant
        return np.array([apply_cal(cal[k][mkt], float(pi)) for pi in p])

    def ll(p, y):
        return -np.log(np.clip(np.where(y, p, 1 - p), 1e-6, 1.0))

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'seed': SEED, 'variants': VARIANTS, 'sources': {}}
    sets = {'espn_close': {m: espn.get(('2026', m, 'close'), []) for m in MKTS}, 'kalshi': {m: kal.get(m, []) for m in MKTS}}
    for src, per in sets.items():
        res['sources'][src] = {}
        for mkt, rows in per.items():
            if not rows:
                continue
            y = np.array([x['y'] for x in rows]); pk = np.array([x['pk'] for x in rows]); gid = np.array([x['gid'] for x in rows])
            P = {v: final(v, rows, mkt, rng) for v in VARIANTS}
            base = ll(P['v2'], y)
            out = {'n': len(rows), 'logloss_market': round(float(ll(pk, y).mean()), 4)}
            for v in VARIANTS:
                p = P[v]
                lv = ll(p, y)
                d = lv - base
                by_g = defaultdict(list)
                for g_, di in zip(gid, d):
                    by_g[g_].append(di)
                gm = [statistics.mean(v_) for v_ in by_g.values()]
                se = statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 2 else float('nan')
                bl = blend([{'pm': float(pi), 'pk': float(k), 'y': bool(yi)} for pi, k, yi in zip(p, pk, y)], 'pm', 'pk', 'y')
                gap = p - P['v2']
                n_d = NDRAWS.get(v)
                exp_gap = float(np.sqrt((P['v2'] * (1 - P['v2'])).mean() / n_d)) if n_d else None
                out[v] = {'logloss': round(float(lv.mean()), 4), 'brier': round(float(((p - y) ** 2).mean()), 4),
                          'dll_vs_v2': round(float(d.mean()), 4), 'dll_se': round(se, 4),
                          'blend_t': (bl or {}).get('t'),
                          'flip_vs_v2': round(float(((p > pk) != (P['v2'] > pk)).mean()), 4),
                          'rms_gap_vs_v2': round(float(np.sqrt((gap ** 2).mean())), 4),
                          'mc_noise_expected': round(exp_gap, 4) if exp_gap else None}
            res['sources'][src][mkt] = out
            print(src, mkt, {v: (out[v]['logloss'], out[v]['dll_vs_v2']) for v in VARIANTS}, 'market', out['logloss_market'], flush=True)

    res['verdict'] = verdict(res)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


def verdict(res):
    """Bars from docs/sim-challenger.md. A variant beats v2 in a cell only if its paired log-loss difference is below -2 SE.
    sim10k must match v2 (|dll| < 0.001) or the simulator has a bug. A noise verdict for sim50 needs dll > +0.001 in most cells."""
    v = {}
    for src, per in res['sources'].items():
        for mkt, o in per.items():
            for name in ('sim10k', 'sim50', 'sam50', 'sam50_shown'):
                x = o[name]
                z = x['dll_vs_v2'] / x['dll_se'] if x['dll_se'] else 0
                tag = 'BETTER' if z <= -2 else 'WORSE' if z >= 2 else 'SAME'
                v.setdefault(name, []).append((src, mkt, tag, round(z, 1)))
    summary = {}
    for name, cells in v.items():
        summary[name] = {'better': sum(t == 'BETTER' for *_, t, _ in cells), 'same': sum(t == 'SAME' for *_, t, _ in cells),
                         'worse': sum(t == 'WORSE' for *_, t, _ in cells), 'cells': cells}
    return summary


def write_md(res):
    L = ['# Simulation challenger: results', '',
         f"Generated {res['generated']} by `nba/scripts/build_sim_challenger.py`. Rules: docs/sim-challenger.md. Fit on 2024-25, tested on 2025-26,",
         'identical player-games and prices for every variant. Lower log loss is better. `dLL` is the paired log-loss difference against v2',
         '(negative = better than v2), with a game-clustered standard error. `flip` is how often the variant lands on the other side of the price',
         "from v2. `gap` is the root-mean-square distance of its probability from v2's, next to what pure Monte Carlo noise at that N predicts.", '']
    for src, per in res['sources'].items():
        L += [f'## {src}', '']
        for mkt, o in per.items():
            L += [f"### {mkt} (n = {o['n']:,}, market log loss {o['logloss_market']})", '',
                  '| Variant | Log loss | Brier | dLL vs v2 (SE) | Blend t | Flip vs v2 | Gap vs v2 (noise expected) |', '|---|---|---|---|---|---|---|']
            for v in res['variants']:
                x = o[v]
                exp = f" ({x['mc_noise_expected']})" if x['mc_noise_expected'] else ''
                L.append(f"| {v} | {x['logloss']} | {x['brier']} | {x['dll_vs_v2']:+} ({x['dll_se']}) | {x['blend_t']} | {x['flip_vs_v2']:.1%} | {x['rms_gap_vs_v2']}{exp} |")
            L.append('')
    L += ['## Verdict by variant (cells where the paired dLL vs v2 clears 2 SE)', '', '| Variant | Better | Same | Worse |', '|---|---|---|---|']
    for name, s in res['verdict'].items():
        L.append(f"| {name} | {s['better']} | {s['same']} | {s['worse']} |")
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
