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


def main():
    box = C.player_games(V2.SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(DATA, 'usage_cascade.json')))['stats']
    team_min = json.load(open(V1.OUT_JSON))['team_min']
    lines = C.closing_lines()
    mv3 = json.load(open(os.path.join(DATA, 'minutes_model_v3.json')))
    rv3 = json.load(open(os.path.join(DATA, 'rates_v3.json')))

    recs2, _ = V2.walk(box, inj, margins, mm, casc, team_min, lines)
    recs3, _ = V2.walk(box, inj, margins, mm, casc, team_min, lines, base='v3', mv3=mv3, rv3=rv3)
    tune3 = [r for r in recs3 if r['season'] in (2023, 2024) and r['pm'] > 0]
    ratio = sum(r['min'] for r in tune3) / sum(r['pm'] for r in tune3)
    team_min3 = round(team_min * ratio, 1)
    print(f'v3 minutes: team target {team_min} -> {team_min3} (fit on 2022-24, as v1\'s was)', flush=True)
    if abs(ratio - 1) > 0.003:
        recs3, _ = V2.walk(box, inj, margins, mm, casc, team_min3, lines, base='v3', mv3=mv3, rv3=rv3)

    by2, by3 = A.by_rec(recs2), A.by_rec(recs3)
    keys = set(by2) & set(by3)
    recs2 = [r for r in recs2 if (r['gid'], r['aid']) in keys]
    recs3 = [r for r in recs3 if (r['gid'], r['aid']) in keys]
    by2, by3 = A.by_rec(recs2), A.by_rec(recs3)
    fit2, test2 = [r for r in recs2 if r['season'] == V2.FIT], [r for r in recs2 if r['season'] == V2.TEST]
    fit3, test3 = [r for r in recs3 if r['season'] == V2.FIT], [r for r in recs3 if r['season'] == V2.TEST]
    print(f'identical player-games: fit {len(fit2):,}  test {len(test2):,}', flush=True)

    stk2, stk3 = V2.fit_stacker(fit2), V2.fit_stacker(fit3)
    mu_2 = lambda r: V2.mu2(r, stk2)
    mu_3 = lambda r: V2.mu2(r, stk3)
    V_2 = V2.fit_var(fit2, mu_2, True)
    V_3 = V2.fit_var(fit3, mu_3, True)
    T3, P3 = A.fit_minutes(fit3), A.fit_production(fit3, stk3)
    extra = lambda r, m: (V2.minrate(r, m) * r['sdm']) ** 2
    key = lambda r: (r['gid'], r['aid'])

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'names': NAMES, 'team_min_v3': team_min3,
           'n_test': len(test2), 'mean': {}, 'logscore': {}, 'range_cal': {}, 'kalshi': {}, 'espn': {}, 'blend_oos': {}, 'kalshi_bias': {},
           'stacker_v3': stk3, 'variance_v3': V_3, 'minutes_v3_shape': T3, 'production_v3': P3}

    # projection accuracy on the test season
    for m in MARKETS:
        out = {}
        for name, recs, mf in (('v2', test2, mu_2), ('v3m', test3, mu_3)):
            e = [mf(r)[m] - A.yval(r, m) for r in recs]
            out[name] = {'mae': round(statistics.mean(abs(x) for x in e), 4), 'rmse': round(math.sqrt(statistics.mean(x * x for x in e)), 4),
                         'bias': round(statistics.mean(e), 4)}
        res['mean'][m] = out
        print(f"  {m:4s} RMSE v2 {out['v2']['rmse']:.3f}  v3m {out['v3m']['rmse']:.3f}   MAE v2 {out['v2']['mae']:.3f}  v3m {out['v3m']['mae']:.3f}", flush=True)

    espn, kal = A.load_markets(by2)
    dcache = {}

    def dist3(r3, m):
        k = (id(r3), m)
        if k not in dcache:
            dcache[k] = A.Dist(P3, r3, m, mu_3(r3)[m], T3)
        return dcache[k]

    v2cal = json.load(open(V2.OUT_JSON))['calibration']['v2']
    raw_v3m = lambda r3, m, L: V2.p_over(m, mu_3(r3)[m], L, V_3, extra(r3, m))
    cal_v3m = {m: pav([(raw_v3m(by3[key(x['r'])], m, x['L']), 1 if x['over'] else 0) for x in espn.get(('2025', m, 'open'), [])]) for m in MARKETS}
    cal_shape = {m: pav([(dist3(by3[key(x['r'])], m).over(x['L']), 1 if x['over'] else 0) for x in espn.get(('2025', m, 'open'), [])]) for m in MARKETS}
    probs = {
        'v2': lambda r, m, L, c: apply_cal(v2cal[m], V2.p_over(m, mu_2(r)[m], L, V_2, extra(r, m))),
        'v3m': lambda r, m, L, c: apply_cal(cal_v3m[m], raw_v3m(by3[key(r)], m, L)),
        'v3m_shape': lambda r, m, L, c: dist3(by3[key(r)], m).over(L),
        'v3m_shape_linecal': lambda r, m, L, c: apply_cal(cal_shape[m], dist3(by3[key(r)], m).over(L)),
    }
    res['calibration'] = {'v3m': cal_v3m, 'v3m_shape_linecal': cal_shape}

    # every player-game: log score of the outcome, and P(over) across each player's range (lines from v2's mean)
    for m in MARKETS:
        ls = {'v2': [], 'v3m': [], 'v3m_shape': []}
        rc = {n: [] for n in NAMES}
        for r in test2:
            r3 = by3[key(r)]
            y = int(round(A.yval(r, m)))
            ls['v2'].append(-A.v2_logp(V_2, m, mu_2(r)[m], extra(r, m), y))
            ls['v3m'].append(-A.v2_logp(V_3, m, mu_3(r3)[m], extra(r3, m), y))
            ls['v3m_shape'].append(-dist3(r3, m).logp(y))
            for t in A.thresholds(m, mu_2(r)[m]):
                o = 1 if y > t else 0
                for n in NAMES:
                    rc[n].append((probs[n](r, m, t, None), o))
        res['logscore'][m] = {n: round(statistics.mean(v), 4) for n, v in ls.items()}
        res['range_cal'][m] = {n: {'brier': round(statistics.mean((p - o) ** 2 for p, o in v), 5), 'deciles': A.decile_table(v)} for n, v in rc.items()}
        print(f"  {m:4s} log score " + '  '.join(f'{n} {v:.4f}' for n, v in res['logscore'][m].items()), flush=True)
        dcache = {k: v for k, v in dcache.items() if k[1] != m}

    A.eval_markets(res, NAMES, probs, espn, kal)
    res['verdict'] = V2.verdicts(res, NAMES)
    res['ship'] = A.choose(res)
    print('ship:', res['ship'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res, rv3, mv3)
    print(open(OUT_MD).read())


def write_md(res, rv3, mv3):
    N = res['names']
    L = ['# Prop model v3 candidate (minutes v3 + per-stat memory + ladder shape) vs v2', '',
         f"Generated {res['generated']} by `nba/scripts/build_prop_model_v3_full.py`. Fit on 2024-25, tested on 2025-26,",
         f"{res['n_test']:,} identical player-games and identical prices for every model.", '',
         '- **v2**: shipped. **v3m**: minutes model v3 x per-stat-memory rates, stacker refit, v2-style spread and line',
         '  calibration (isolates workstreams B + C). **v3m_shape**: v3m\'s mean with workstream A\'s ladder distribution,',
         '  uncalibrated. **v3m_shape_linecal**: the same, calibrated on 2024-25 sportsbook main lines.', '',
         f"**Shipped: {res['ship']}** (rule: keep every v2 GO at GO with ROI at least v2's, then lowest Kalshi log loss).", '',
         '## Projection accuracy, 2025-26', '', '| Stat | RMSE v2 | RMSE v3m | MAE v2 | MAE v3m | Bias v2 | Bias v3m |', '|---|---|---|---|---|---|---|']
    for m, d in res['mean'].items():
        L.append(f"| {m} | {d['v2']['rmse']:.3f} | {d['v3m']['rmse']:.3f} | {d['v2']['mae']:.3f} | {d['v3m']['mae']:.3f} | {d['v2']['bias']:+.3f} | {d['v3m']['bias']:+.3f} |")
    L += ['', '## Every player-game: log score of the outcome, and range Brier', '',
          '| Stat | Log score v2 | v3m | v3m_shape | ' + ' | '.join(f'Range Brier {n}' for n in N) + ' |', '|---|---|---|---|' + '---|' * len(N)]
    for m in MARKETS:
        a, b = res['logscore'][m], res['range_cal'][m]
        L.append(f"| {m} | {a['v2']:.4f} | {a['v3m']:.4f} | {a['v3m_shape']:.4f} | " + ' | '.join(f"{b[n]['brier']:.4f}" for n in N) + ' |')
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
    L += ['', f"Inputs: [minutes-model-v3.md](minutes-model-v3.md), [rates-v3.md](rates-v3.md), [prop-model-v3.md](prop-model-v3.md). "
          f"Team minutes target for v3 minutes: {res['team_min_v3']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
