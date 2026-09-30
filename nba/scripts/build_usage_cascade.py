#!/usr/bin/env python3
"""
NBA usage cascade: when a teammate sits, how much of HIS production per minute
flows to each remaining player (docs/PLAN.md §4B step 3). The NBA version of the
NFL build_vacated_share.py.

The minutes model already covers "plays more". This isolates "does more per
minute", so the prop model can combine the two without double counting:

  stat = minutes x (ewma rate + cascade)
  cascade = minutes/48 x [ a*vac_same + b*vac_other + c*vac_same*rel + d*vac_other*rel ]
    vac_*  per-game production (same stat) of rotation teammates who are OUT,
           same position group vs other
    rel    the player's own per-minute rate / the average rate of present teammates
           (stars absorb more than role players)

Fit per stat by OLS on the tune seasons (who actually sat), scored on the test
seasons with the injury report 30 min pre-tip and the player's ACTUAL minutes
(so this measures the rate effect only).

  python3 nba/scripts/build_usage_cascade.py
Writes nba/data/usage_cascade.json and nba/docs/usage-cascade.md
"""
import datetime as dt, json, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
from build_minutes_model import group, ols

WARM, TUNE, TEST = [2022], [2023, 2024], [2025, 2026]
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'usage-cascade.md')
STATS = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['three_point_field_goals_made'],
         'fga': ['field_goals_attempted'], 'pra': ['points', 'rebounds', 'assists']}
ALPHA, ROT_MIN, ROT_DAYS = 0.12, 10.0, 21


def sv(r, cols):
    return sum(r[c] for c in cols)


def walk(seasons, box, inj, record_from, mode):
    pl = {}   # aid -> {team, last, pos, m, n, rate{stat: per-min}, pg{stat: per-game}}
    recs = defaultdict(list)
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= record_from:
            played = {r['athlete_id'] for r in rows if r['played']}
            day = g['tip_et'].strftime('%Y-%m-%d')
            cut = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
            lim = g['tip'] - dt.timedelta(days=ROT_DAYS)
            for team in (g['home'], g['away']):
                rot = {a: p for a, p in pl.items() if p['team'] == team and p['m'] >= ROT_MIN and p['last'] >= lim}
                if mode == 'oracle':
                    out = {a for a in rot if a not in played}
                else:
                    out = {a for a, s in inj.status(day, team, cut).items() if s in ('Out', 'Doubtful')}
                present = [p for a, p in rot.items() if a not in out]
                for r in rows:
                    p = pl.get(r['athlete_id'])
                    if r['team'] != team or not r['played'] or not p or p['team'] != team or p['n'] < 5:
                        continue
                    f48 = r['minutes'] / 48.0
                    for st, cols in STATS.items():
                        vs = sum(q['pg'][st] for a, q in rot.items() if a in out and a != r['athlete_id'] and q['pos'] == p['pos'])
                        vo = sum(q['pg'][st] for a, q in rot.items() if a in out and a != r['athlete_id'] and q['pos'] != p['pos'])
                        avg = statistics.mean(q['rate'][st] for q in present) if present else 0
                        rel = p['rate'][st] / avg if avg > 0 else 1.0
                        base = r['minutes'] * p['rate'][st]
                        recs[st].append({'x': [f48 * vs, f48 * vo, f48 * vs * rel, f48 * vo * rel],
                                         'base': base, 'y': sv(r, cols), 'vac': vs + vo})
        for r in rows:
            if not r['played']:
                continue
            p = pl.get(r['athlete_id'])
            m = r['minutes']
            if p is None:
                pl[r['athlete_id']] = p = {'team': r['team'], 'last': g['tip'], 'pos': group(r['pos']), 'm': m, 'n': 0,
                                           'rate': {s: sv(r, c) / m for s, c in STATS.items()},
                                           'pg': {s: sv(r, c) for s, c in STATS.items()}}
            a = max(ALPHA, 1 / (p['n'] + 1))
            p['m'] += a * (m - p['m'])
            for s, c in STATS.items():
                p['rate'][s] += a * (sv(r, c) / m - p['rate'][s]) * min(1.0, m / 20)  # short stints: noisy rate, smaller step
                p['pg'][s] += a * (sv(r, c) - p['pg'][s])
            p['n'] += 1
            p['team'], p['last'] = r['team'], g['tip']
    return recs


def mae(recs, beta):
    return statistics.mean(abs(r['base'] + sum(b * x for b, x in zip(beta, r['x'])) - r['y']) for r in recs)


def bias(recs, beta):
    return statistics.mean(r['base'] + sum(b * x for b, x in zip(beta, r['x'])) - r['y'] for r in recs)


def main():
    box = C.player_games(WARM + TUNE + TEST)
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    tr = walk(WARM + TUNE, box, None, TUNE[0], 'oracle')
    te = walk(WARM + TUNE + TEST, box, inj, TEST[0], 'report')
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'stats': {}}
    zero = [0.0] * 4
    for st in STATS:
        beta = ols([r['x'] for r in tr[st]], [r['y'] - r['base'] for r in tr[st]], ridge=10.0)
        hit = [r for r in te[st] if r['vac'] > 0]
        res['stats'][st] = {
            'beta': [round(b, 4) for b in beta], 'n_test': len(te[st]), 'n_test_vacated': len(hit),
            'mae_all': [round(mae(te[st], zero), 3), round(mae(te[st], beta), 3)],
            'mae_vacated': [round(mae(hit, zero), 3), round(mae(hit, beta), 3)],
            'bias_vacated': [round(bias(hit, zero), 3), round(bias(hit, beta), 3)],
        }
        # Ship a stat's cascade only if it beats the plain rate out of sample, overall AND when a teammate sits.
        res['stats'][st]['use'] = res['stats'][st]['mae_all'][1] < res['stats'][st]['mae_all'][0] and \
            res['stats'][st]['mae_vacated'][1] < res['stats'][st]['mae_vacated'][0]
        s = res['stats'][st]
        print(f"{st:4s} all MAE {s['mae_all'][0]} -> {s['mae_all'][1]} | teammate out n={len(hit):,}: MAE {s['mae_vacated'][0]} -> {s['mae_vacated'][1]}, bias {s['bias_vacated'][0]:+} -> {s['bias_vacated'][1]:+} | beta {s['beta']}", flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    L = ['# NBA usage cascade: backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_usage_cascade.py`. Fit 2022-23 + 2023-24, tested 2024-25 +",
         '2025-26 with the injury report 30 min pre-tip. Uses each player\'s ACTUAL minutes, so this is the per-minute',
         'effect only (the minutes model handles extra playing time).', '',
         '| Stat | Use? | Test player-games | MAE: rate only | MAE: + cascade | Teammate out: n | MAE: rate only | MAE: + cascade | Bias: rate only | Bias: + cascade |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for st, s in res['stats'].items():
        L.append(f"| {st} | {'yes' if s['use'] else 'no'} | {s['n_test']:,} | {s['mae_all'][0]} | {s['mae_all'][1]} | {s['n_test_vacated']:,} | {s['mae_vacated'][0]} | {s['mae_vacated'][1]} | {s['bias_vacated'][0]:+} | {s['bias_vacated'][1]:+} |")
    L += ['', 'Bias < 0 means the plain rate UNDER-predicts: the player does more when teammates sit.', '',
          '**Finding:** the per-minute effect is small. When a teammate sits, most of the extra production comes from',
          'extra MINUTES (see minutes-model.md), not a higher rate. Only stats marked "yes" beat the plain rate out of',
          'sample; the prop model uses the cascade for those and the plain rate for the rest.', '',
          'Weights per stat: [same-position vacated, other-position vacated, same x relative rate, other x relative rate],',
          'each per unit of (minutes / 48) x the out players\' per-game production of that stat.', '']
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
