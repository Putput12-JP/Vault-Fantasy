#!/usr/bin/env python3
"""
Prop calibration tests. Rules: docs/prop-calibration-tests.md (committed before this file existed). Nothing here changes pricing.

  python3 nba/scripts/test_prop_calibration.py test1          score Test 1 once (2025-26 lines, look 27) -> data/prop_calibration_tests.json
  python3 nba/scripts/test_prop_calibration.py counts         row counts only for Tests 2 and 3 (no outcomes are printed)
  python3 nba/scripts/test_prop_calibration.py test2          read Test 2 if its sample rule is met, else print counts and stop
  python3 nba/scripts/test_prop_calibration.py test3          read Test 3 on or after 2026-11-18 if its sample rule is met, else print counts and stop

Tests 2 and 3 read the nba-data branch (git fetch origin nba-data first). `counts` and the refusal path never compute a win rate, ROI or log-loss.
"""
import json, math, os, random, statistics as st, subprocess, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lean_search_nba as LS

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, '..', 'data', 'prop_calibration_tests.json')
FROM_DAY = '2026-10-26'
T3_END = '2026-11-17'
T3_READ_ON = '2026-11-18'
EDGE_MIN = 0.03
lg, sig = LS.lg, LS.sig


def load_out():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def save_out(d):
    d['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(d, open(OUT, 'w'), indent=1)


def boot_sd_t(by_game, draws, seed):
    """by_game: {gid: [value, ...]}. Pooled mean, bootstrap sd of the pooled mean (resampling games), t, 95% interval."""
    gk = list(by_game)
    allv = [v for g in gk for v in by_game[g]]
    mean = st.mean(allv)
    rng = random.Random(seed)
    ms = []
    for _ in range(draws):
        s = n = 0
        for g in rng.choices(gk, k=len(gk)):
            s += sum(by_game[g]); n += len(by_game[g])
        ms.append(s / n)
    ms.sort()
    sd = st.pstdev(ms)
    return {'mean': mean, 'sd': sd, 't': mean / sd if sd else None, 'ci': [ms[int(draws * .025)], ms[int(draws * .975)]], 'games': len(gk), 'rows': len(allv)}


# ── Test 1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test1():
    rows = json.load(open(LS.ROWS)); n = len(rows)
    first = rows[:int(n * .4)]
    gaps = sorted(abs(LS.gap(r)) for r in first)
    c = gaps[int(0.9 * len(gaps))]
    cand = lambda r: [1.0, lg(r['pk']), max(-c, min(c, LS.gap(r)))]
    F = {f'fold{i+1}': (rows[:int(n * a)], rows[int(n * a):int(n * b)]) for i, (a, b) in enumerate([(.4, .6), (.6, .8), (.8, 1.0)])}
    print(f"{n} lines | c = {c:.4f} (90th pct of |gap|, first 40% = {len(first)} rows) | " + ' | '.join(f"{k}: fit {len(v[0])} score {len(v[1])}" for k, v in F.items()))
    inc = LS.score(LS.base, F); can = LS.score(cand, F)
    better = {k: inc[k]['ll'] - can[k]['ll'] for k in F}
    diffs = [a - b for k in F for a, b in zip(inc[k]['_l'], can[k]['_l'])]
    gids = [r['gid'] for k in F for r in F[k][1]]
    by = {}
    for g, d in zip(gids, diffs):
        by.setdefault(g, []).append(d)
    random.seed(11)
    gk = list(by); ms = []
    for _ in range(1000):
        ms.append(st.mean([d for g in random.choices(gk, k=len(gk)) for d in by[g]]))
    ms.sort()
    mean = st.mean(diffs); sd = st.pstdev(ms); lo = ms[25]; hi = ms[974]
    looks = LS.EXTERNAL_LOOKS + len(json.load(open(LS.TRIALS))['trials']) + 1
    bar = 0.0003 * math.log(1 + looks)
    t = mean / sd if sd else None
    conds = {'all_three_folds_better': all(v > 0 for v in better.values()), 'ci_lo_above_zero': lo > 0, 'gain_over_bar': mean > bar, 't_at_least_2_5': t is not None and t >= 2.5}
    verdict = 'ACCEPT' if all(conds.values()) else 'REJECT'
    # companion: incumbent reliability on the scored rows
    bands = [(.5, .55), (.55, .6), (.6, .65), (.65, .7), (.7, 1.01)]
    rel = {f'{int(a*100)}-{int(b*100) if b < 1 else 100}': {'n': 0, 'pred': 0.0, 'won': 0} for a, b in bands}
    beyond = tot = 0
    for k, (tr, te) in F.items():
        w = LS.fit(tr, LS.base)
        for r in te:
            p = sig(sum(a * b for a, b in zip(w, LS.base(r)))); side = max(p, 1 - p); won = (p >= .5) == bool(r['y'])
            tot += 1; beyond += abs(LS.gap(r)) > c
            for (a, b), key in zip(bands, rel):
                if a <= side < b:
                    rel[key]['n'] += 1; rel[key]['pred'] += side; rel[key]['won'] += won
    for v in rel.values():
        if v['n']:
            v['pred'] = round(v['pred'] / v['n'], 4); v['hit'] = round(v['won'] / v['n'], 4)
    res = {'c': round(c, 4), 'rows': n, 'scored': tot, 'games_scored': len(by), 'share_beyond_c': round(beyond / tot, 4),
           'folds': {k: {'incumbent_ll': round(inc[k]['ll'], 5), 'candidate_ll': round(can[k]['ll'], 5), 'gain': round(better[k], 6), 'n': inc[k]['n'],
                          'incumbent_hit': round(inc[k]['hit'], 4), 'candidate_hit': round(can[k]['hit'], 4)} for k in F},
           'pooled_gain': round(mean, 6), 'boot_sd': round(sd, 6), 't': round(t, 3) if t is not None else None, 'ci95': [round(lo, 6), round(hi, 6)],
           'looks': looks, 'bar': round(bar, 6), 'conditions': conds, 'verdict': verdict, 'reliability_incumbent': rel}
    print(json.dumps(res, indent=1))
    d = load_out(); d['test1'] = res; save_out(d)
    return res


# ── data from the nba-data branch ──────────────────────────────────────────────────────────────────────────────────────────────

def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True, check=True).stdout


def branch_days(prefix, ref='origin/nba-data'):
    names = git('ls-tree', '--name-only', ref, prefix).split()
    return sorted(n[len(prefix):-5] for n in names if n.endswith('.json') and n[len(prefix):-5] >= FROM_DAY and len(n[len(prefix):-5]) == 10)


def branch_json(path, ref='origin/nba-data'):
    return json.loads(git('show', f'{ref}:{path}'))


def t2_rows(bets_by_day):
    """Qualifying settled bets: win or loss, a stored price, a stored fair and fair_close, regular season."""
    out, miss = [], 0
    for day, bets in bets_by_day.items():
        for b in bets:
            if b.get('pre') or b.get('result') not in ('win', 'loss'):
                continue
            if b.get('price') is None or b.get('pnl') is None or b.get('edge') is None or b.get('fair') is None:
                continue
            if b.get('fair_close') is None:
                miss += 1; continue
            e = b['edge'] + (b['fair_close'] - b['fair'])
            out.append({'day': day, 'game': str(b['game']), 'tip': b.get('tip') or 0, 'pnl': b['pnl'], 'clv': b.get('clv'), 'kept': e >= EDGE_MIN})
    return out, miss


def t3_rows(leans_by_day, days_ok):
    out = []
    for day, d in leans_by_day.items():
        if not (FROM_DAY <= day <= T3_END):
            continue
        C = d['cols']
        for r in d['rows']:
            r = dict(zip(C, r))
            if r['clock'] != 'f' or r['held'] or r['res'] not in ('W', 'L') or r['p_mkt'] is None or r['p_blend'] is None:
                continue
            yo = 1 if ((r['side'] == 'O') == (r['res'] == 'W')) else 0
            out.append({'day': day, 'game': str(r['game']), 'y': yo, 'p_blend': r['p_blend'], 'p_mkt': r['p_mkt']})
    return out


def load_t2():
    return t2_rows({d: branch_json(f'bets/{d}.json') for d in branch_days('bets/')})


def load_t3():
    return t3_rows({d: branch_json(f'leans/{d}.json') for d in branch_days('leans/')}, None)


# ── counts only ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def t2_counts(rows):
    games = {r['game'] for r in rows}
    dr = [r for r in rows if not r['kept']]
    return {'bets': len(rows), 'kept': len(rows) - len(dr), 'dropped': len(dr), 'games': len(games), 'nights': len({r['day'] for r in rows})}


def t3_counts(rows):
    return {'rows': len(rows), 'games': len({r['game'] for r in rows}), 'nights': len({r['day'] for r in rows})}


def counts():
    r2, miss = load_t2(); r3 = load_t3()
    print('Test 2 (since', FROM_DAY + '):', t2_counts(r2), '| missing fair_close:', miss)
    print('Test 3 (', FROM_DAY, 'to', T3_END + '):', t3_counts(r3))


# ── Test 2 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def t2_ready(c):
    return c['nights'] >= 20 and c['games'] >= 100 and c['dropped'] >= 300


def diff_by_game(rows, val, arm):
    """{game: [value]} for rows by arm."""
    by = {}
    for r in rows:
        if arm(r):
            by.setdefault(r['game'], []).append(val(r))
    return by


def paired_diff(rows, val, in_a, in_b, seed=7, draws=2000):
    """mean(val | a) - mean(val | b), resampling games. Returns None if either arm is empty."""
    ga, gb = {}, {}
    for r in rows:
        if in_a(r): ga.setdefault(r['game'], []).append(val(r))
        elif in_b(r): gb.setdefault(r['game'], []).append(val(r))
    games = sorted(set(ga) | set(gb))
    if not ga or not gb:
        return None

    def stat(sample):
        sa = na = sb = nb = 0
        for g in sample:
            sa += sum(ga.get(g, [])); na += len(ga.get(g, [])); sb += sum(gb.get(g, [])); nb += len(gb.get(g, []))
        return (sa / na - sb / nb) if na and nb else None
    D = stat(games)
    rng = random.Random(seed)
    ms = [m for m in (stat(rng.choices(games, k=len(games))) for _ in range(draws)) if m is not None]
    sd = st.pstdev(ms)
    return {'D': D, 'sd': sd, 'z': D / sd if sd else None}


def test2():
    rows, miss = load_t2(); c = t2_counts(rows)
    print('Test 2 counts:', c, '| missing fair_close:', miss)
    if not t2_ready(c):
        print('sample rule not met (need nights >= 20, games >= 100, dropped >= 300). Nothing scored.')
        return None
    rows.sort(key=lambda r: (r['tip'], r['game']))
    order = []
    for r in rows:
        if r['game'] not in order: order.append(r['game'])
    early = set(order[:len(order) // 2])
    D = paired_diff(rows, lambda r: r['pnl'], lambda r: r['kept'], lambda r: not r['kept'])
    h1 = paired_diff([r for r in rows if r['game'] in early], lambda r: r['pnl'], lambda r: r['kept'], lambda r: not r['kept'])
    h2 = paired_diff([r for r in rows if r['game'] not in early], lambda r: r['pnl'], lambda r: r['kept'], lambda r: not r['kept'])
    nights = max(1, c['nights'])
    arms = {}
    for name, f in (('kept', lambda r: r['kept']), ('dropped', lambda r: not r['kept'])):
        sub = [r for r in rows if f(r)]
        clv = [r['clv'] for r in sub if r['clv'] is not None]
        arms[name] = {'bets': len(sub), 'roi': round(st.mean(r['pnl'] for r in sub), 4), 'units_per_night': round(sum(r['pnl'] for r in sub) / nights, 2),
                      'clv': round(st.mean(clv), 4) if clv else None, 'clv_n': len(clv)}
    z = D['z']; both = h1 and h2 and h1['D'] > 0 and h2['D'] > 0
    verdict = 'GO' if (D['D'] > 0 and z is not None and z >= 2.5 and both) else ('WATCH' if (D['D'] > 0 and z is not None and z >= 1.65) else 'NO-GO')
    res = {'counts': c, 'missing_fair_close': miss, 'D': round(D['D'], 4), 'z': round(z, 3) if z is not None else None, 'half1_D': round(h1['D'], 4) if h1 else None,
           'half2_D': round(h2['D'], 4) if h2 else None, 'arms': arms, 'share_dropped': round(c['dropped'] / c['bets'], 4), 'verdict': verdict,
           'read_on': datetime.now(timezone.utc).strftime('%Y-%m-%d')}
    print(json.dumps(res, indent=1))
    d = load_out()
    if 'test2' in d:
        print('Test 2 was already read; the first read stands. Not overwritten.'); return d['test2']
    d['test2'] = res; save_out(d)
    return res


# ── Test 3 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def halved(r):
    return sig(lg(r['p_mkt']) + 0.5 * (lg(r['p_blend']) - lg(r['p_mkt'])))


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def test3():
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    rows = load_t3(); c = t3_counts(rows)
    print('Test 3 counts:', c)
    if today < T3_READ_ON:
        print(f'not before {T3_READ_ON}. Nothing scored.'); return None
    if c['games'] < 100 or c['rows'] < 3000:
        print('sample rule not met (need games >= 100 and rows >= 3000). Nothing scored.'); return None
    for r in rows:
        r['g'] = ll(r['p_blend'], r['y']) - ll(halved(r), r['y'])          # positive: halving helped
        r['m'] = ll(r['p_blend'], r['y']) - ll(r['p_mkt'], r['y'])         # reference: positive means the market alone beat the blend
    days = sorted({r['day'] for r in rows}); mid = days[len(days) // 2]
    by = {}
    for r in rows: by.setdefault(r['game'], []).append(r['g'])
    S = boot_sd_t(by, 2000, 7)
    halves = []
    for sel in (lambda r: r['day'] < mid, lambda r: r['day'] >= mid):
        b = {}
        for r in rows:
            if sel(r): b.setdefault(r['game'], []).append(r['g'])
        halves.append(round(st.mean(v for g in b.values() for v in g), 6))
    bm = {}
    for r in rows: bm.setdefault(r['game'], []).append(r['m'])
    M = boot_sd_t(bm, 2000, 7)
    verdict = 'GO' if (S['t'] is not None and S['t'] >= 2.5 and all(h > 0 for h in halves)) else ('SHIPPED WINS' if (S['t'] is not None and S['t'] <= -2.5) else 'INCONCLUSIVE')
    res = {'counts': c, 'G': round(S['mean'], 6), 't': round(S['t'], 3) if S['t'] is not None else None, 'ci95': [round(x, 6) for x in S['ci']], 'halves_G': halves, 'split_day': mid,
           'reference_blend_minus_market_ll': round(M['mean'], 6), 'reference_t': round(M['t'], 3) if M['t'] is not None else None, 'verdict': verdict, 'read_on': today}
    print(json.dumps(res, indent=1))
    d = load_out()
    if 'test3' in d:
        print('Test 3 was already read; the first read stands. Not overwritten.'); return d['test3']
    d['test3'] = res; save_out(d)
    return res


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'test1': test1, 'counts': counts, 'test2': test2, 'test3': test3}.get(cmd, lambda: print(__doc__))()
