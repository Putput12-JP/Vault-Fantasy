#!/usr/bin/env python3
"""
Pick'em V2 walk-forward backtest (rules in docs/pickem-v2.md). Reads the dataset from build_pickem_v2_data.py.

  python3 nba/scripts/backtest_pickem_v2.py nba/data/pickem_v2_legs.json [nba/data/pickem_v2_backtest.json]

Unit: one leg = one app line (PrizePicks standard, Underdog) on one side, scored from the box score. A tie is a push (not a leg).
Reference chance: `fair_pin` (de-vigged Pinnacle over chance at exactly the app's line) or `fair_mkt` (stored consensus at exactly the line).
Legs on different teams are independent (docs/pickem-different-teams.md), so a slip's value follows from the legs' hit rate:
  power n  pays PAYS[n] if all hit            flex   pays FLEX[n][k] for k hits of n
Frozen before the holdout was scored: train = regular-season tip days 2026-10-20..23 (Central), holdout = 10-24..26; the rule is the
(source, threshold, format) with the best train value among those with >= MIN_TRAIN legs; verdict GO needs the holdout lower CI bound of the
slip ROI above 0 with >= MIN_HOLD legs, WATCH needs the point estimate above 0 in both train and holdout, else NO-GO.
"""
import datetime as dt, json, math, sys
from math import comb

PAYS = {2: 3, 3: 5, 4: 10, 5: 20, 6: 37.5}                      # pickem_record.py / the page's PP_PAYS (power)
FLEX = {3: {3: 2.25, 2: 1.25}, 4: {4: 5, 3: 1.5}, 5: {5: 10, 4: 2, 3: .4}, 6: {6: 25, 5: 2, 4: .4}}   # 5-flex reproduces pricing.PK_BE (.5425)
THRESH = [.50, .52, .54, .56]
MIN_TRAIN, MIN_HOLD = 100, 100
REG = dt.datetime(2026, 10, 20, 5, tzinfo=dt.timezone.utc).timestamp()      # first regular-season tip day, Central midnight
SPLIT = dt.datetime(2026, 10, 24, 5, tzinfo=dt.timezone.utc).timestamp()


def slip_ev(p, fmt, n):
    if fmt == 'power':
        return PAYS[n] * p ** n - 1
    return sum(comb(n, k) * p ** k * (1 - p) ** (n - k) * m for k, m in FLEX[n].items()) - 1


def breakeven(fmt, n):
    lo, hi = .3, .9
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (lo, m) if slip_ev(m, fmt, n) > 0 else (m, hi)
    return hi


def wilson(w, n, z=1.96):
    if not n:
        return (None, None)
    p = w / n; c = (p + z * z / 2 / n) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / (1 + z * z / n)
    return c - h, c + h


def legs(rows, src):
    """Unique app lines with a stored reference at exactly that line, on the side the reference likes."""
    seen = {}
    for r in rows:
        if r['y'] is None or r['tip'] < REG or not (r['app'] == 'prizepicks' and r['kind'] == 'standard' or r['app'] == 'underdog'):
            continue
        seen[(r['app'], r['pid'], r['stat'], r['line'], r['tip'])] = r
    out = []
    for r in seen.values():
        f = r.get(src)
        if f is None or r['y'] == r['line']:
            continue
        over = f >= .5
        if r['app'] == 'underdog':                                   # a priced line must sit near even money on the chosen side (the page's rule)
            try:
                px = float(r['v'][0] if over else r['v'][1]); ip = -px / (-px + 100) if px < 0 else 100 / (px + 100)
            except Exception:
                continue
            if not .44 <= ip <= .56:
                continue
        out.append({'p': f if over else 1 - f, 'hit': (r['y'] > r['line']) == over, 'tip': r['tip'], 'app': r['app'], 'stat': r['stat'], 'side': 'o' if over else 'u'})
    return out


def evaluate(L, t, fmt, n):
    s = [x for x in L if x['p'] >= t]
    w = sum(x['hit'] for x in s); N = len(s)
    if not N:
        return None
    lo, hi = wilson(w, N)
    return {'n': N, 'hit': w / N, 'ci': [lo, hi], 'roi': slip_ev(w / N, fmt, n), 'roi_ci': [slip_ev(lo, fmt, n), slip_ev(hi, fmt, n)], 'be': breakeven(fmt, n), 'mean_fair': sum(x['p'] for x in s) / N}


if __name__ == '__main__':
    rows = json.load(open(sys.argv[1]))['rows']
    res = {'cells': [], 'break_even': {f'{f}{n}': round(breakeven(f, n), 4) for f in ('power', 'flex') for n in range(2, 7) if f == 'power' or n in FLEX}}
    pick = None
    for src in ('fair_pin', 'fair_mkt'):
        L = legs(rows, src); tr = [x for x in L if x['tip'] < SPLIT]; ho = [x for x in L if x['tip'] >= SPLIT]
        for t in THRESH:
            for fmt, n in [('power', k) for k in range(2, 7)] + [('flex', k) for k in FLEX]:
                a, b = evaluate(tr, t, fmt, n), evaluate(ho, t, fmt, n)
                res['cells'].append({'src': src, 'thr': t, 'fmt': fmt, 'n_picks': n, 'train': a, 'hold': b})
                if a and a['n'] >= MIN_TRAIN and (pick is None or a['roi'] > pick['train']['roi']):
                    pick = res['cells'][-1]
    res['selected'] = pick
    h = pick['hold']
    res['verdict'] = ('GO' if h and h['n'] >= MIN_HOLD and h['roi_ci'][0] > 0 else
                      'WATCH' if h and h['n'] >= MIN_HOLD and pick['train']['roi'] > 0 and h['roi'] > 0 else 'NO-GO')
    json.dump(res, open(sys.argv[2] if len(sys.argv) > 2 else 'pickem_v2_backtest.json', 'w'), indent=1)
    print('break-even per leg', res['break_even'])
    print('selected', pick['src'], pick['thr'], pick['fmt'], pick['n_picks'], '\n train', pick['train'], '\n hold', pick['hold'], '\nVERDICT', res['verdict'])
    best = sorted([c for c in res['cells'] if c['hold'] and c['hold']['n'] >= MIN_HOLD], key=lambda c: -c['hold']['roi'])[:6]
    print('best holdout cells (descriptive, not selected):')
    for c in best:
        print(' ', c['src'], c['thr'], c['fmt'], c['n_picks'], 'train roi', c['train'] and round(c['train']['roi'], 3), 'hold n', c['hold']['n'], 'hit', round(c['hold']['hit'], 3), 'roi', round(c['hold']['roi'], 3), [round(x, 3) for x in c['hold']['roi_ci']])
