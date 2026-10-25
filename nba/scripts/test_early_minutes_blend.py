#!/usr/bin/env python3
"""
Early-season minutes blend. Rules: docs/early-minutes-blend-test.md (committed before this file existed). Nothing here changes pricing.

  python3 nba/scripts/test_early_minutes_blend.py          walk the prop model (about 5 min), score once -> data/early_minutes_blend.json
  python3 nba/scripts/test_early_minutes_blend.py --cache  reuse the cached walk records (same numbers, faster)

The walk records are cached to $EARLY_BLEND_CACHE (default /tmp/early_blend_recs.json) only to avoid a second 5-minute walk; the score is the same either way.
"""
import json, os, random, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, '..', 'data', 'early_minutes_blend.json')
CACHE = os.environ.get('EARLY_BLEND_CACHE', '/tmp/early_blend_recs.json')
STATS = ['pts', 'reb', 'ast', '3pm']
FIT, TEST = 2025, 2026
E_LO, E_HI = 4, 10
C_LO, C_HI = 11, 20


def walk_records():
    if '--cache' in sys.argv and os.path.exists(CACHE):
        return json.load(open(CACHE))
    import build_prop_model_v3_full as F
    recs = F.walk_v2(F.inputs())
    slim = [{'gid': int(r['gid']), 'season': r['season'], 'aid': r['aid'], 'team': r['team'], 'min': r['min'], 'pm': r['pm'],
             'mu': {s: r['mu'][s] for s in STATS}, 'y': {s: r['y'][s] for s in STATS}} for r in recs]
    json.dump(slim, open(CACHE, 'w'), separators=(',', ':'))
    return slim


def annotate(recs):
    """Team game number per (season, team) and the first-three average f per (season, team, player). Returns rows for players who played."""
    games = defaultdict(set)
    for r in recs:
        games[(r['season'], r['team'])].add(r['gid'])
    num = {}
    for k, gs in games.items():
        for i, g in enumerate(sorted(gs), 1):
            num[(k, g)] = i
    first3 = defaultdict(list)
    for r in recs:
        k = (r['season'], r['team'])
        n = num[(k, r['gid'])]
        r['k'] = n
        if n <= 3 and r['min'] > 0:
            first3[(k, r['aid'])].append(r['min'])
    rows = []
    for r in recs:
        if r['min'] <= 0 or r['pm'] <= 0:
            continue
        v = first3.get(((r['season'], r['team']), r['aid']))
        r['f'] = st.mean(v) if v and len(v) >= 2 else None
        rows.append(r)
    return rows, games


def fit_w(rows):
    num = den = 0.0
    for r in rows:
        if r['f'] is None:
            continue
        num += (r['min'] - r['pm']) * (r['f'] - r['pm']); den += (r['f'] - r['pm']) ** 2
    return min(1.0, max(0.0, num / den)) if den else 0.0, (num / den if den else None)


def new_pm(r, w):
    return r['pm'] + w * (r['f'] - r['pm']) if r['f'] is not None else r['pm']


def boot(by_game, draws=2000, seed=7):
    gk = list(by_game)
    allv = [v for g in gk for v in by_game[g]]
    rng = random.Random(seed)
    ms = []
    for _ in range(draws):
        s = n = 0
        for g in rng.choices(gk, k=len(gk)):
            s += sum(by_game[g]); n += len(by_game[g])
        ms.append(s / n)
    ms.sort()
    sd = st.pstdev(ms); mean = st.mean(allv)
    return {'mean': mean, 'sd': sd, 't': (mean / sd) if sd else None, 'ci': [ms[int(draws * .025)], ms[int(draws * .975)]], 'games': len(gk), 'rows': len(allv)}


def minutes_gain(rows, w):
    by = defaultdict(list)
    for r in rows:
        if r['f'] is None:
            continue
        by[r['gid']].append(abs(r['min'] - r['pm']) - abs(r['min'] - new_pm(r, w)))
    b = boot(by)
    olds = [abs(r['min'] - r['pm']) for r in rows if r['f'] is not None]
    news = [abs(r['min'] - new_pm(r, w)) for r in rows if r['f'] is not None]
    return {**{k: (round(v, 5) if isinstance(v, float) else v) for k, v in b.items() if k != 'ci'}, 'ci95': [round(x, 5) for x in b['ci']],
            'mae_old': round(st.mean(olds), 4), 'mae_new': round(st.mean(news), 4)}


def prop_gain(rows, w):
    R = [r for r in rows if r['f'] is not None]
    mae = {s: st.mean(abs(r['y'][s] - r['mu'][s]) for r in R) for s in STATS}
    by = defaultdict(list); per = {}
    for s in STATS:
        eo, en = [], []
        for r in R:
            mun = r['mu'][s] * new_pm(r, w) / r['pm']
            e_old, e_new = abs(r['y'][s] - r['mu'][s]), abs(r['y'][s] - mun)
            by[r['gid']].append((e_old - e_new) / mae[s]); eo.append(e_old); en.append(e_new)
        per[s] = {'mae_old': round(st.mean(eo), 4), 'mae_new': round(st.mean(en), 4), 'better': st.mean(en) <= st.mean(eo)}
    b = boot(by)
    return {'pooled_gain': round(b['mean'], 5), 'sd': round(b['sd'], 5), 't': round(b['t'], 3) if b['t'] is not None else None, 'ci95': [round(x, 5) for x in b['ci']],
            'games': b['games'], 'rows_x_stats': b['rows'], 'per_stat': per}


def main():
    recs = walk_records()
    rows, games = annotate(recs)
    first = {s: min(g for (ss, t), gs in games.items() if ss == s for g in gs) for s in (FIT, TEST)}
    print('walk records', len(recs), '| player-games who played', len(rows), '| first game id by season', first)
    fit_rows = [r for r in rows if r['season'] == FIT and E_LO <= r['k'] <= E_HI]
    w, raw = fit_w(fit_rows)
    print(f'w = {w:.4f} (unclipped {raw:.4f}) fitted on {sum(r["f"] is not None for r in fit_rows)} FIT window rows')
    test_E = [r for r in rows if r['season'] == TEST and E_LO <= r['k'] <= E_HI]
    test_C = [r for r in rows if r['season'] == TEST and C_LO <= r['k'] <= C_HI]
    res = {'w': round(w, 4), 'w_unclipped': round(raw, 4) if raw is not None else None,
           'counts': {'fit_E_rows': len(fit_rows), 'fit_E_blended': sum(r['f'] is not None for r in fit_rows),
                      'test_E_rows': len(test_E), 'test_E_blended': sum(r['f'] is not None for r in test_E),
                      'test_E_games': len({r['gid'] for r in test_E}), 'test_C_rows': len(test_C), 'test_C_blended': sum(r['f'] is not None for r in test_C)}}
    res['test_E_minutes'] = minutes_gain(test_E, w)
    res['test_E_props'] = prop_gain(test_E, w)
    h1 = [r for r in test_E if r['k'] <= 7]; h2 = [r for r in test_E if r['k'] >= 8]
    res['halves_minutes_gain'] = [round(st.mean(abs(r['min'] - r['pm']) - abs(r['min'] - new_pm(r, w)) for r in h if r['f'] is not None), 5) for h in (h1, h2)]
    conds = {'minutes_t_ge_2_5': (res['test_E_minutes']['t'] or 0) >= 2.5,
             'props_t_ge_2_5': (res['test_E_props']['t'] or 0) >= 2.5,
             'no_stat_worse': all(v['better'] for v in res['test_E_props']['per_stat'].values()),
             'both_halves_positive': all(x > 0 for x in res['halves_minutes_gain']),
             'w_strictly_inside': 0.0 < w < 1.0}
    res['conditions'] = conds
    res['verdict'] = 'PASS' if all(conds.values()) else 'FAIL'
    res['context'] = {'fit_E_in_sample_minutes': minutes_gain(fit_rows, w), 'test_C_minutes': minutes_gain(test_C, w), 'test_C_props': prop_gain(test_C, w)}
    res['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    print(json.dumps(res, indent=1))
    json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
