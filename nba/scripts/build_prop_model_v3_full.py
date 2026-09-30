#!/usr/bin/env python3
"""
Prop model v3 candidate, all three workstreams so far (docs/v3-plan.md), against v2 on identical rows and prices.

  v2                shipped: v1 minutes x one-EWMA rates, v2 stacker, v2 variance + line calibration
  v3m               v3 BASE: minutes model v3 (role, returns, new team, market spread) x per-stat memory component rates
                    (B + C), stacker refit on top, v2's variance + line calibration refit to it. Isolates B + C.
  v3m_shape         v3 base + workstream A's ladder distribution (minutes scenarios, NB / beta-binomial / normal),
                    uncalibrated (A's best on Kalshi)
  v3m_shape_linecal v3 base + A's distribution, calibrated on 2024-25 sportsbook main lines

Fit on 2024-25 (the team minutes target for v3 minutes on 2022-24, as v1's was), test 2025-26.
Ship rule, the same as workstream A's and fixed before this ran: a candidate replaces v2 only if every v2 GO signal
stays GO with out-of-sample ROI at least v2's; among those, lowest average Kalshi log loss.

  python3 nba/scripts/build_prop_model_v3_full.py
Writes data/prop_model_v3_full.json and docs/prop-model-v3-full.md.
"""
import datetime as dt, json, math, os, statistics, sys
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as V1
import build_prop_model_v2 as V2
import build_prop_model_v3 as A
from build_prop_model import BASE, COMBO, MARKETS, pav, apply_cal

DATA = os.path.join(C.HERE, '..', 'data')
OUT_JSON = os.path.join(DATA, 'prop_model_v3_full.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'prop-model-v3-full.md')
NAMES = ['v2', 'v3m', 'v3m_shape', 'v3m_shape_linecal']


def inputs():
    box = C.player_games(V2.SEASONS)
    return {'box': box, 'inj': C.InjuryAsOf([2025, 2026], C.player_index(box)), 'margins': MM.expected_margins(box),
            'mm': json.load(open(MM.OUT_JSON)), 'casc': json.load(open(os.path.join(DATA, 'usage_cascade.json')))['stats'],
            'team_min': json.load(open(V1.OUT_JSON))['team_min'], 'lines': C.closing_lines(),
            'mv3': json.load(open(os.path.join(DATA, 'minutes_model_v3.json'))),
            'rv3': json.load(open(os.path.join(DATA, 'rates_v3.json')))}


def walk_v2(I):
    return V2.walk(I['box'], I['inj'], I['margins'], I['mm'], I['casc'], I['team_min'], I['lines'])[0]


def walk_v3(I, feed=None, rates=True):
    """v3 base walk; the team minutes target re-tuned on 2022-24 (as v1's was). -> (recs, team_min)"""
    run = lambda tm: V2.walk(I['box'], I['inj'], I['margins'], I['mm'], I['casc'], tm, I['lines'], base='v3',
                             mv3=I['mv3'], rv3=I['rv3'] if rates else None, feed=feed)[0]
    recs = run(I['team_min'])
    tune = [r for r in recs if r['season'] in (2023, 2024) and r['pm'] > 0]
    ratio = sum(r['min'] for r in tune) / sum(r['pm'] for r in tune)
    tm = round(I['team_min'] * ratio, 1)
    print(f"v3 minutes{' + lineup feed' if feed else ''}: team target {I['team_min']} -> {tm}", flush=True)
    return (run(tm) if abs(ratio - 1) > 0.003 else recs), tm


def compare(recs2, bases, shaped):
    """v2 against each v3-style base (stacker, v2-style spread and line calibration refit to it), plus workstream A's
    ladder shape on the base named `shaped`, uncalibrated and line-calibrated. Identical player-games and prices."""
    keys = set(A.by_rec(recs2))
    for recs in bases.values():
        keys &= set(A.by_rec(recs))
    keep = lambda rs: [r for r in rs if (r['gid'], r['aid']) in keys]
    recs2, bases = keep(recs2), {b: keep(rs) for b, rs in bases.items()}
    by = {b: A.by_rec(rs) for b, rs in bases.items()}
    names = ['v2'] + list(bases) + ([shaped + '_shape', shaped + '_shape_linecal'] if shaped else [])
    fit2, test2 = [r for r in recs2 if r['season'] == V2.FIT], [r for r in recs2 if r['season'] == V2.TEST]
    fits = {b: [r for r in rs if r['season'] == V2.FIT] for b, rs in bases.items()}
    tests = {b: [r for r in rs if r['season'] == V2.TEST] for b, rs in bases.items()}
    print(f'identical player-games: fit {len(fit2):,}  test {len(test2):,}', flush=True)

    stk = {'v2': V2.fit_stacker(fit2)}
    stk.update({b: V2.fit_stacker(fits[b]) for b in bases})
    mu = {b: (lambda s: lambda r: V2.mu2(r, s))(stk[b]) for b in stk}
    var = {'v2': V2.fit_var(fit2, mu['v2'], True)}
    var.update({b: V2.fit_var(fits[b], mu[b], True) for b in bases})
    T3, P3 = (A.fit_minutes(fits[shaped]), A.fit_production(fits[shaped], stk[shaped])) if shaped else (None, None)
    extra = lambda r, m: (V2.minrate(r, m) * r['sdm']) ** 2
    key = lambda r: (r['gid'], r['aid'])

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'names': names, 'bases': list(bases),
           'shaped': shaped, 'n_test': len(test2), 'mean': {}, 'logscore': {}, 'range_cal': {}, 'kalshi': {}, 'espn': {},
           'blend_oos': {}, 'kalshi_bias': {}, 'stacker': {b: stk[b] for b in bases}, 'variance': {b: var[b] for b in bases},
           'minutes_shape': T3, 'production_shape': P3}

    # minutes and projection accuracy on the test season
    e = lambda recs: [r['pm'] - r['min'] for r in recs]
    res['minutes'] = {n: {'mae': round(statistics.mean(abs(x) for x in e(rs)), 3), 'miss8': round(sum(abs(x) >= 8 for x in e(rs)) / len(rs), 4)}
                      for n, rs in [('v2', test2)] + list(tests.items())}
    for m in MARKETS:
        out = {}
        for name, recs in [('v2', test2)] + list(tests.items()):
            er = [mu[name](r)[m] - A.yval(r, m) for r in recs]
            out[name] = {'mae': round(statistics.mean(abs(x) for x in er), 4), 'rmse': round(math.sqrt(statistics.mean(x * x for x in er)), 4),
                         'bias': round(statistics.mean(er), 4)}
        res['mean'][m] = out
        print(f'  {m:4s} RMSE ' + '  '.join(f"{n} {v['rmse']:.3f}" for n, v in out.items()), flush=True)

    espn, kal = A.load_markets(A.by_rec(recs2))
    dcache = {}
    bs = by[shaped] if shaped else {}

    def dist3(r3, m):
        k = (id(r3), m)
        if k not in dcache:
            dcache[k] = A.Dist(P3, r3, m, mu[shaped](r3)[m], T3)
        return dcache[k]

    v2cal = json.load(open(V2.OUT_JSON))['calibration']['v2']
    raw = lambda b, rb, m, L: V2.p_over(m, mu[b](rb)[m], L, var[b], extra(rb, m))
    cal = {b: {m: pav([(raw(b, by[b][key(x['r'])], m, x['L']), 1 if x['over'] else 0) for x in espn.get(('2025', m, 'open'), [])])
               for m in MARKETS} for b in bases}
    cal_shape = {m: pav([(dist3(bs[key(x['r'])], m).over(x['L']), 1 if x['over'] else 0) for x in espn.get(('2025', m, 'open'), [])]) for m in MARKETS} if shaped else {}
    probs = {'v2': lambda r, m, L, c: apply_cal(v2cal[m], V2.p_over(m, mu['v2'](r)[m], L, var['v2'], extra(r, m)))}
    for b in bases:
        probs[b] = (lambda b: lambda r, m, L, c: apply_cal(cal[b][m], raw(b, by[b][key(r)], m, L)))(b)
    if shaped:
        probs[shaped + '_shape'] = lambda r, m, L, c: dist3(bs[key(r)], m).over(L)
        probs[shaped + '_shape_linecal'] = lambda r, m, L, c: apply_cal(cal_shape[m], dist3(bs[key(r)], m).over(L))
    res['calibration'] = dict(cal, **({shaped + '_shape_linecal': cal_shape} if shaped else {}))

    # every player-game: log score of the outcome, and P(over) across each player's range (lines from v2's mean)
    for m in MARKETS:
        ls = {n: [] for n in ['v2'] + list(bases) + ([shaped + '_shape'] if shaped else [])}
        rc = {n: [] for n in names}
        for r in test2:
            y = int(round(A.yval(r, m)))
            ls['v2'].append(-A.v2_logp(var['v2'], m, mu['v2'](r)[m], extra(r, m), y))
            for b in bases:
                rb = by[b][key(r)]
                ls[b].append(-A.v2_logp(var[b], m, mu[b](rb)[m], extra(rb, m), y))
            if shaped:
                ls[shaped + '_shape'].append(-dist3(bs[key(r)], m).logp(y))
            for t in A.thresholds(m, mu['v2'](r)[m]):
                o = 1 if y > t else 0
                for n in names:
                    rc[n].append((probs[n](r, m, t, None), o))
        res['logscore'][m] = {n: round(statistics.mean(v), 4) for n, v in ls.items()}
        res['range_cal'][m] = {n: {'brier': round(statistics.mean((p - o) ** 2 for p, o in v), 5), 'deciles': A.decile_table(v)} for n, v in rc.items()}
        print(f"  {m:4s} log score " + '  '.join(f'{n} {v:.4f}' for n, v in res['logscore'][m].items()), flush=True)
        dcache = {k: v for k, v in dcache.items() if k[1] != m}

    A.eval_markets(res, names, probs, espn, kal)
    res['verdict'] = V2.verdicts(res, names)
    res['ship'] = A.choose(res)
    print('ship:', res['ship'], flush=True)
    return res


def main():
    I = inputs()
    recs3, tm3 = walk_v3(I)
    res = compare(walk_v2(I), {'v3m': recs3}, 'v3m')
    res['team_min_v3'] = tm3
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


HEAD = ['# Prop model v3 candidate (minutes v3 + per-stat memory + ladder shape) vs v2', '',
        'Generated {generated} by `nba/scripts/build_prop_model_v3_full.py`. Fit on 2024-25, tested on 2025-26,',
        '{n_test:,} identical player-games and identical prices for every model.', '',
        '- **v2**: shipped. **v3m**: minutes model v3 x per-stat-memory rates, stacker refit, v2-style spread and line',
        '  calibration (isolates workstreams B + C). **v3m_shape**: v3m\'s mean with workstream A\'s ladder distribution,',
        '  uncalibrated. **v3m_shape_linecal**: the same, calibrated on 2024-25 sportsbook main lines.']
FOOT = ['Inputs: [minutes-model-v3.md](minutes-model-v3.md), [rates-v3.md](rates-v3.md), [prop-model-v3.md](prop-model-v3.md). '
        'Team minutes target for v3 minutes: {team_min_v3}.']


def write_md(res, head=HEAD, foot=FOOT, out=OUT_MD):
    N, P = res['names'], ['v2'] + res['bases']
    fmt = lambda lines: [x.format(**res) for x in lines]
    L = fmt(head) + ['', f"**Shipped: {res['ship']}** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).", '',
                     '## Projection accuracy, 2025-26', '',
                     '| Stat | ' + ' | '.join(f'RMSE {n}' for n in P) + ' | ' + ' | '.join(f'MAE {n}' for n in P) + ' | '
                     + ' | '.join(f'Bias {n}' for n in P) + ' |', '|---|' + '---|' * (3 * len(P))]
    mn = res.get('minutes')
    if mn:
        L.append('| minutes | ' + ' | '.join('' for n in P) + ' | ' + ' | '.join(f"{mn[n]['mae']:.3f}" for n in P) + ' | '
                 + ' | '.join(f"8+ miss {mn[n]['miss8']:.1%}" for n in P) + ' |')
    for m, d in res['mean'].items():
        L.append(f'| {m} | ' + ' | '.join(f"{d[n]['rmse']:.3f}" for n in P) + ' | ' + ' | '.join(f"{d[n]['mae']:.3f}" for n in P) + ' | '
                 + ' | '.join(f"{d[n]['bias']:+.3f}" for n in P) + ' |')
    LS = list(res['logscore'][MARKETS[0]])
    L += ['', '## Every player-game: log score of the outcome, and range Brier', '',
          '| Stat | ' + ' | '.join(f'Log score {n}' for n in LS) + ' | ' + ' | '.join(f'Range Brier {n}' for n in N) + ' |',
          '|---|' + '---|' * (len(LS) + len(N))]
    for m in MARKETS:
        a, b = res['logscore'][m], res['range_cal'][m]
        L.append(f'| {m} | ' + ' | '.join(f'{a[n]:.4f}' for n in LS) + ' | ' + ' | '.join(f"{b[n]['brier']:.4f}" for n in N) + ' |')
    L += ['', '## Kalshi ladders, 2025-26 (log loss; blend t in brackets)', '', '| Stat | Rows | Market | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi'].items():
        L.append(f"| {m} | {d['n']:,} | {d['logloss_market']:.4f} | " + ' | '.join(f"{d[n]['logloss']:.4f} ({d[n]['blend_t']})" for n in N) + ' |')
    L += ['', 'Blended fair price (market + model, fit on the first half) scored on the second half:', '',
          '| Stat | Market alone | ' + ' | '.join(N) + ' |', '|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi'].items():
        L.append(f"| {m} | {d['market_2nd_half_logloss']:.5f} | " + ' | '.join(f"{d[n]['blend_oos_logloss']:.5f}" for n in N) + ' |')
    L += ['', '## ESPN pre-tip close lines, 2025-26 (log loss; blend t in brackets)', '', '| Stat | Rows | Market | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['espn'].items():
        L.append(f"| {m} | {d['n']:,} | {d['logloss_market']:.4f} | " + ' | '.join(f"{d[n]['logloss']:.4f} ({d[n]['blend_t']})" for n in N) + ' |')
    f = lambda x: f"{x['roi']:+.1%} ({x['n']:,}, z {x['z']})" if x and x.get('roi') is not None else 'none'
    L += ['', '## Betting it, out of sample, 3%+ edge', '', 'Kalshi: blend fit on the first half of 2025-26, bet on the second, fees in, ROI per dollar, z by game.', '',
          '| Stat | Side | Price only | ' + ' | '.join(N) + ' |', '|---|---|---|' + '---|' * len(N)]
    for m, d in res['kalshi_bias'].items():
        for side in ('YES', 'NO'):
            L.append(f"| {m} | {side} | {f(d['v2'].get(f'price_only/{side}'))} | " + ' | '.join(f(d[n].get(f'blend/{side}')) for n in N) + ' |')
    g = lambda x: f"{x['0.03']['roi']:+.1%} ({x['0.03']['n']:,}, z {x['0.03']['z']})" if x and x.get('0.03', {}).get('n') else 'none'
    L += ['', '| Sportsbook stat (24-25 fit, 25-26 close) | ' + ' | '.join(N) + ' |', '|---|' + '---|' * len(N)]
    for k, d in res['blend_oos'].items():
        if k.startswith('espn'):
            L.append(f"| {k.split('/')[1]} | " + ' | '.join(g(d.get(n)) for n in N) + ' |')
    L += ['', '## Gates', '', '| Stat | ' + ' | '.join(N) + ' |', '|---|' + '---|' * len(N)]
    for m in MARKETS:
        L.append(f"| {m} | " + ' | '.join(res['verdict'][n][m] for n in N) + ' |')
    L += [''] + fmt(foot) + ['']
    open(out, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
