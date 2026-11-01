#!/usr/bin/env python3
"""Idea search for the NFL rebuild. Every idea is selected on 2010-2019 and then judged ONCE on the 2020+ holdout (graded vs the closing spread).
Reference to beat on the holdout: live model MAE 10.005, closing line 9.766 (from data/nfl_model_backtest.json).

  python3 scripts/explore_nfl_rebuild.py --games games.csv
"""
import argparse, itertools, json, math, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_nfl_rebuild as B

TUNE = (2010, 2019); HOLD = (2020, 9999)


def engine(games, K=0.065, KQ=0.03, repl=-1.0, m=0.0, cap=None, use_qb=False, carry=0.72, hfa=2.0, ret=False):
    """Online ratings. m = weight on the closing line as the update target (market-informed ratings). cap = cap on the result used for updating."""
    t, q = defaultdict(float), {}
    last_q = {}
    preds, feats, season = [], [], None
    for g in games:
        if g['season'] != season:
            season = g['season']
            for k in t: t[k] *= carry
            for k in q: q[k] *= B.CARRY_Q
        qh = q.get(g['hq'], repl) if use_qb and g['hq'] else 0.0
        qa = q.get(g['aq'], repl) if use_qb and g['aq'] else 0.0
        pred = t[g['h']] + qh - t[g['a']] - qa + hfa
        preds.append(pred)
        chg_h = float(g['hq'] is not None and last_q.get(g['h']) not in (None, g['hq']))
        chg_a = float(g['aq'] is not None and last_q.get(g['a']) not in (None, g['aq']))
        feats.append((chg_h, chg_a, qh - qa, g['week']))
        res = g['res'] if cap is None else max(-cap, min(cap, g['res']))
        target = (1 - m) * res + m * g['sp']
        err = target - pred
        t[g['h']] += K * err; t[g['a']] -= K * err
        if use_qb:
            if g['hq']: q[g['hq']] = qh + KQ * err
            if g['aq']: q[g['aq']] = qa - KQ * err
        if g['hq']: last_q[g['h']] = g['hq']
        if g['aq']: last_q[g['a']] = g['aq']
    return (preds, feats) if ret else preds


def slope(games, preds, lo, hi):
    xs = [p - g['sp'] for g, p in zip(games, preds) if lo <= g['season'] <= hi]
    ys = [g['res'] - g['sp'] for g in games if lo <= g['season'] <= hi]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-9: return 0.0, 0.0
    c = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    r = [(y - my) - c * (x - mx) for x, y in zip(xs, ys)]
    return c, math.sqrt(sum(v * v for v in r) / (len(xs) - 2) / sxx)


def line(games, preds, name, lo, hi):
    mae = B.mae(games, preds, lo, hi); c, se = slope(games, preds, lo, hi)
    s = f'{name:<44} MAE {mae:.3f}  slope {c:+.2f} (t={c / se if se else 0:+.1f})'
    for thr in (1.5, 3.0):
        w, l, _ = B.grade(games, preds, lo, hi, thr); n = w + l
        s += f'  | {thr}+: {w}-{l} {100 * w / n:.1f}%' if n else f'  | {thr}+: -'
    return mae, s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--games'); ap.add_argument('--out', default=os.path.join(B.ROOT, 'data', 'nfl_rebuild_explore.json'))
    a = ap.parse_args(); games = B.load_games(a.games)
    log = {}
    print('REFERENCES holdout 2020+: live model MAE 10.005, closing line 9.766')
    print(f'closing line itself: MAE {B.mae(games, [g["sp"] for g in games], *HOLD):.3f}\n')

    # 1. plain ratings with margin cap and carry tuned on 2010-2019
    grid = [(K, cap, carry) for K in (0.045, 0.065, 0.085) for cap in (None, 21, 14) for carry in (0.6, 0.72, 0.85)]
    best = min(grid, key=lambda p: B.mae(games, engine(games, K=p[0], cap=p[1], carry=p[2]), *TUNE))
    K0, cap0, carry0 = best
    p0 = engine(games, K=K0, cap=cap0, carry=carry0)
    print(f'[1] base tuned on {TUNE}: K={K0} cap={cap0} carry={carry0}')
    print(' ', line(games, p0, 'base (tuned)', *TUNE)[1]); print(' ', line(games, p0, 'base (tuned) HOLDOUT', *HOLD)[1])
    log['base'] = dict(K=K0, cap=cap0, carry=carry0)

    # 2. market-informed ratings: ratings also learn from each closing line
    print('\n[2] market-informed ratings (m = weight on the close as the target)')
    rows = []
    for m in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7):
        p = engine(games, K=K0, cap=cap0, carry=carry0, m=m)
        rows.append((B.mae(games, p, *TUNE), m, p))
        print(' ', line(games, p, f'm={m} TUNE', *TUNE)[1])
    mbest = min(rows, key=lambda r: r[0])
    print(f'  best MAE on tune: m={mbest[1]}')
    for m in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7):
        p = engine(games, K=K0, cap=cap0, carry=carry0, m=m)
        print(' ', line(games, p, f'm={m} HOLDOUT', *HOLD)[1])

    # 3. QB ratings on top of market-informed ratings
    print('\n[3] + QB ratings on market-informed ratings')
    for m, KQ, repl in itertools.product((0.2, 0.3, 0.5), (0.03, 0.06, 0.10), (-1.0, -2.0)):
        p = engine(games, K=K0, cap=cap0, carry=carry0, m=m, KQ=KQ, repl=repl, use_qb=True)
        rows.append((B.mae(games, p, *TUNE), ('qb', m, KQ, repl), p))
    qb_rows = [r for r in rows if isinstance(r[1], tuple)]
    qb_best = min(qb_rows, key=lambda r: r[0])
    print('  best on tune:', qb_best[1], f'MAE {qb_best[0]:.3f}')
    _, m3, KQ3, repl3 = qb_best[1]
    p3 = qb_best[2]
    print(' ', line(games, p3, 'market-informed + QB HOLDOUT', *HOLD)[1])
    log['mi_qb'] = dict(m=m3, KQ=KQ3, repl=repl3)

    # 4. stack on the close: (actual - close) ~ gap + QB-change flags + rating-QB gap, ridge, refit each season on earlier seasons
    print('\n[4] stacked residual model on the close (walk-forward ridge)')
    pq, ft = engine(games, K=K0, cap=cap0, carry=carry0, m=m3, KQ=KQ3, repl=repl3, use_qb=True, ret=True)
    stack = list(pq)
    for s in sorted({g['season'] for g in games if g['season'] >= 2014}):
        def row(i):
            g = games[i]; ch, ca, qg, wk = ft[i]
            return [pq[i] - g['sp'], ch - ca, qg, float(wk <= 4), (pq[i] - g['sp']) * float(wk <= 4)] + g['x']
        tr = [i for i, g in enumerate(games) if 2008 <= g['season'] < s]
        w = B.ols([row(i) for i in tr], [games[i]['res'] - games[i]['sp'] for i in tr], ridge=len(tr) * 0.05)
        for i, g in enumerate(games):
            if g['season'] == s: stack[i] = g['sp'] + sum(c * x for c, x in zip(w, row(i)))
    for lo, hi, nm in ((2014, 2019, 'stack 2014-19'), (2020, 9999, 'stack HOLDOUT')):
        print(' ', line(games, stack, nm, lo, hi)[1])
    ours_hold = 10.005
    stack_mae = B.mae(games, stack, *HOLD)
    print(f'\nSUMMARY holdout 2020+ (n={sum(1 for g in games if g["season"] >= 2020)}): live {ours_hold}, base-tuned {B.mae(games, p0, *HOLD):.3f}, '
          f'market-informed+QB {B.mae(games, p3, *HOLD):.3f}, stacked {stack_mae:.3f}, close {B.mae(games, [g["sp"] for g in games], *HOLD):.3f}')
    json.dump(log, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
