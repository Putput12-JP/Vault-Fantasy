#!/usr/bin/env python3
"""
Forward read of the rotation-aware minutes shadow (C3). Rules: docs/rotation-minutes-shadow.md, "Forward read". This implements them and nothing else.

  python3 nba/scripts/score_rotation_forward.py counts <nba-data checkout>     counts only
  python3 nba/scripts/score_rotation_forward.py read   <nba-data checkout>     the registered read, once, on or after 2026-12-15

Population: players who played, in games whose last pre-tip Minutes row carries `rot` (values 6 to 9: rot minutes, pool size, team game number, rank). Game is the unit; bootstrap 2,000 draws, seed 7.
PASS needs all four: (1) overall minutes MAE gain > 0, t >= 2.5; (2) top-8 bias within 0.5 minutes for rot in pools of 15 or more and of 12 or fewer (each 500+ player-games);
(3) first 15 team games gain > 0, t >= 2.5; (4) props (lean log first look, single-stat pts reb ast 3pm, mu x rot / pm) pooled gain > 0, t >= 2.5, no stat worse.
"""
import json, os, random, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
OUT = os.path.join(HERE, '..', 'data', 'rotation_forward.json')
READ_ON, MIN_GAMES, MIN_ROWS, MIN_BUCKET, SINCE = '2026-12-15', 150, 3000, 500, '2026-10-26'
PROP_STATS = ('pts', 'reb', 'ast', '3pm')


def boot(by_game, draws=2000, seed=7):
    gk = list(by_game)
    rng = random.Random(seed)
    ms = []
    for _ in range(draws):
        s = n = 0
        for g in rng.choices(gk, k=len(gk)):
            s += sum(by_game[g]); n += len(by_game[g])
        ms.append(s / n)
    allv = [v for g in gk for v in by_game[g]]
    sd = st.pstdev(ms)
    mean = st.mean(allv)
    return {'gain': round(mean, 5), 't': round(mean / sd, 3) if sd else None, 'games': len(gk), 'rows': len(allv)}


def load_rows(root, L, now=None):
    import time
    now = now or int(time.time())
    rows = []
    for k, x in L.load_src(root, 'minutes', SINCE).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series'], key=lambda z: (z[0], z[1] is None)) if v is not None and m and t < m['tip']]
        if not m or not pre or len(pre[-1]) < 10 or pre[-1][6] is None or now < m['tip'] + L.SETTLE_AFTER_S:
            continue
        path = os.path.join(root, 'results', f"{m['game']}.json")
        if not os.path.exists(path):
            continue
        b = json.load(open(path)).get(str(m['pid']))
        actual = (b or {}).get('minutes') or 0.0
        if actual <= 0:
            continue
        v = pre[-1]
        rows.append({'game': str(m['game']), 'pid': int(m['pid']), 'day': L.tip_day(m['tip']), 'pm': v[0], 'rot': v[6], 'size': v[7], 'tgn': v[8], 'rank': v[9], 'actual': actual})
    return rows


def load_props(root, rows):
    """lean log first-look rows joined to the minutes rows: {(game, pid): ...} -> list of {game, stat, mu, y, pm, rot}."""
    by = {(r['game'], r['pid']): r for r in rows}
    out = []
    ld = os.path.join(root, 'leans')
    for f in sorted(os.listdir(ld)) if os.path.isdir(ld) else []:
        if not f.endswith('.json') or f[:-5] < SINCE:
            continue
        d = json.load(open(os.path.join(ld, f)))
        cols = d['cols']
        for raw in d['rows']:
            r = dict(zip(cols, raw))
            j = by.get((str(r['game']), int(r['pid'])))
            if r['clock'] != 'f' or r['stat'] not in PROP_STATS or r['res'] not in ('W', 'L', 'P') or r.get('held') or not j or not j['pm'] or r['y'] is None:
                continue
            out.append({'game': str(r['game']), 'stat': r['stat'], 'mu': r['mu'], 'y': r['y'], 'ratio': j['rot'] / j['pm']})
    return out


def evaluate(rows, props):
    gain = lambda r: abs(r['actual'] - r['pm']) - abs(r['actual'] - r['rot'])
    by = lambda sel, f: _by(sel, f)
    res = {'rows': len(rows), 'games': len({r['game'] for r in rows}), 'overall': boot(by(rows, gain))}
    top8 = [r for r in rows if r['rank'] is not None and r['rank'] <= 8 and r['size'] is not None]
    res['top8_bias'] = {}
    for name, f in (('size_ge_15', lambda z: z >= 15), ('size_13_14', lambda z: 13 <= z <= 14), ('size_le_12', lambda z: z <= 12)):
        s = [r for r in top8 if f(r['size'])]
        res['top8_bias'][name] = {'n': len(s), 'v2': round(st.mean(r['pm'] - r['actual'] for r in s), 3) if s else None, 'rot': round(st.mean(r['rot'] - r['actual'] for r in s), 3) if s else None}
    early = [r for r in rows if r['tgn'] is not None and r['tgn'] <= 15]
    res['first_15'] = boot(by(early, gain)) if len({r['game'] for r in early}) >= 5 else None
    # props
    mae = {s: st.mean(abs(p['y'] - p['mu']) for p in props if p['stat'] == s) for s in PROP_STATS if any(p['stat'] == s for p in props)}
    pb, per = defaultdict(list), {}
    for s in mae:
        eo, en = [], []
        for p in (p for p in props if p['stat'] == s):
            a, b = abs(p['y'] - p['mu']), abs(p['y'] - p['mu'] * p['ratio'])
            eo.append(a); en.append(b); pb[p['game']].append((a - b) / mae[s])
        per[s] = {'mae_old': round(st.mean(eo), 4), 'mae_new': round(st.mean(en), 4), 'better': st.mean(en) <= st.mean(eo)}
    res['props'] = {**(boot(pb) if len(pb) >= 5 else {}), 'per_stat': per}
    ranks = [r for r in rows if r['rank'] in (9, 10)]
    res['context'] = {'ranks_9_10_bias': {'v2': round(st.mean(r['pm'] - r['actual'] for r in ranks), 3) if ranks else None, 'rot': round(st.mean(r['rot'] - r['actual'] for r in ranks), 3) if ranks else None, 'n': len(ranks)}}
    return res


def _by(rows, f):
    d = defaultdict(list)
    for r in rows:
        d[r['game']].append(f(r))
    return d


def verdict(res):
    tb = res['top8_bias']
    big, small = tb['size_ge_15'], tb['size_le_12']
    waiting = [n for n, b in (('size_ge_15', big), ('size_le_12', small)) if b['n'] < MIN_BUCKET]
    conds = {'overall_t_ge_2_5': bool(res['overall']['t'] is not None and res['overall']['gain'] > 0 and res['overall']['t'] >= 2.5),
             'bias_within_0_5_in_both_buckets': not waiting and abs(big['rot']) <= 0.5 and abs(small['rot']) <= 0.5,
             'first_15_t_ge_2_5': bool(res['first_15'] and res['first_15']['gain'] > 0 and (res['first_15']['t'] or 0) >= 2.5),
             'props_t_ge_2_5_no_stat_worse': bool(res['props'].get('t') is not None and res['props']['gain'] > 0 and res['props']['t'] >= 2.5 and all(v['better'] for v in res['props']['per_stat'].values()))}
    return conds, waiting


def main():
    import ledger as L
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd not in ('counts', 'read') or len(sys.argv) < 3:
        print(__doc__); return
    root = sys.argv[2]
    rows = load_rows(root, L)
    games = len({r['game'] for r in rows})
    tb = {n: sum(1 for r in rows if r['rank'] is not None and r['rank'] <= 8 and r['size'] is not None and f(r['size'])) for n, f in (('size_ge_15', lambda z: z >= 15), ('size_le_12', lambda z: z <= 12))}
    counts = {'player_games': len(rows), 'games': games, 'top8_size_ge_15': tb['size_ge_15'], 'top8_size_le_12': tb['size_le_12']}
    if cmd == 'counts':
        print(json.dumps(counts)); return
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if today < READ_ON:
        print(f'not before {READ_ON}; nothing scored.', json.dumps(counts)); return
    if games < MIN_GAMES or len(rows) < MIN_ROWS:
        print(f'sample rule not met (need {MIN_GAMES} games and {MIN_ROWS} player-games); nothing scored.', json.dumps(counts)); return
    if os.path.exists(OUT):
        print('already read; the first read stands:', open(OUT).read()[:400]); return
    res = evaluate(rows, load_props(root, rows))
    conds, waiting = verdict(res)
    res.update({'conditions': conds, 'waiting_for_buckets': waiting, 'read_on': today, 'verdict': 'COLLECTING' if waiting and today < '2027-02-01' else ('PASS' if all(conds.values()) else 'FAIL')})
    print(json.dumps(res, indent=1))
    if res['verdict'] != 'COLLECTING':
        json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
