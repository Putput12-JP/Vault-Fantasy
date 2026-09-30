#!/usr/bin/env python3
"""
Backtest of the consensus fair engine (consensus.py) on 2025-26: can one venue's prices, moved to another venue's
line, find mispriced prices there? Prices are the ones we archived: DraftKings / ESPN BET main lines at their last
pre-tip update, and Kalshi pre-tip prices (30-minute VWAP). No pick'em or Pinnacle history exists; those are
tracked live.

Three tests, each fit on the first half of 2025-26 (by tip time) and bet on the second half, 3%+ edge after fees:

  books -> Kalshi    DraftKings' line (vig removed) moved to every Kalshi rung for that player-game. Is Kalshi's price
                     wrong where the book disagrees? (the Price gap edge on Kalshi)
  Kalshi -> books    the whole Kalshi ladder fit to one implied mean, priced at DraftKings' line. (Price gap on books)
  Kalshi ladder      each rung priced from the OTHER rungs of the same ladder. (the Structural / ladder gap edge)

For each: log loss of the price, of the consensus, of our model and of the fitted blends; calibration by distance
between the lines (how well moving a line works); and betting. Fair for betting = blend of consensus and model,
logistic on log-odds, fit on the first half only ("consensus + model"); "consensus" alone is also scored.

Ship rule, fixed before this ran: a Price gap or Structural signal (test x stat x side) is GO when its second-half
ROI > 0 with z >= 2 over 50+ games; WATCH when positive; else NO-GO. The engine itself goes live either way as the
fair price for spotting gaps; only GO signals are sized on the Edges page.

  python3 nba/scripts/build_consensus.py
Writes data/consensus_backtest.json and docs/consensus-engine.md.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model as V1
import build_prop_model_v2 as V2
import build_prop_model_v3 as A
import build_prop_model_v3_full as F
import consensus as CE
from build_prop_model import MARKETS, apply_cal, kalshi_fee, am_prob, am_payout

DATA = os.path.join(C.HERE, '..', 'data')
OUT_JSON = os.path.join(DATA, 'consensus_backtest.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'consensus-engine.md')
EDGE = 0.03
KAL_MKTS = ['pts', 'reb', 'ast', '3pm']
DIST_BINS = [(0.5, 'same line'), (1.5, '1 away'), (3.5, '2-3 away'), (6.5, '4-6 away'), (99, '7+ away')]


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def fit_blend(rows, keys):
    """y ~ a + sum b_k logit(x_k), Newton. rows: dicts with the keys and 'y'."""
    X = [[1.0] + [CE.lg(r[k]) for k in keys] for r in rows]
    Y = [1.0 if r['y'] else 0.0 for r in rows]
    n = len(X[0])
    b = [0.0] + [1.0 / len(keys)] * len(keys)
    for _ in range(30):
        g, H = [0.0] * n, [[0.0] * n for _ in range(n)]
        for x, y in zip(X, Y):
            p = 1 / (1 + math.exp(-max(-30, min(30, sum(bi * xi for bi, xi in zip(b, x))))))
            for i in range(n):
                g[i] += (y - p) * x[i]
                for j in range(n):
                    H[i][j] += p * (1 - p) * x[i] * x[j] + (1e-6 if i == j else 0)
        step = V1.MM.solve(H, g)
        b = [bi + si for bi, si in zip(b, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return b


def bprob(b, r, keys):
    z = b[0] + sum(bi * CE.lg(r[k]) for bi, k in zip(b[1:], keys))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def bet_summary(bets):
    """bets: [(gid, return per unit)] -> n, games, ROI, z (clustered by game)."""
    if not bets:
        return {'n': 0}
    g = defaultdict(list)
    for gid, x in bets:
        g[gid].append(x)
    gm = [statistics.mean(v) for v in g.values()]
    se = statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 1 else None
    roi = sum(x for _, x in bets) / len(bets)
    return {'n': len(bets), 'games': len(gm), 'roi': round(roi, 4), 'z': round(statistics.mean(gm) / se, 2) if se else None}


def verdict(s):
    if not s or not s.get('n') or s['roi'] <= 0:
        return 'NO-GO'
    return 'GO' if s['games'] >= 50 and (s['z'] or 0) >= 2 else 'WATCH'


SHIP = ('consensus', 'consensus + model')                      # the pre-registered fairs; the rest are baselines
BASELINES = (('price only', ['price']), ('price + model', ['price', 'model']))


def evaluate(rows, name, bet_fn, fair_keys=(('consensus', ['cons']), ('consensus + model', ['cons', 'model'])) + BASELINES):
    """rows need 'price' (the venue's P(over) as quoted), 'cons', 'model', 'y', 'tip', 'gid', 'dist'. Fit blends on the
    first half, score and bet the second half. bet_fn(row, fair_over) -> list of (side, return per unit)."""
    rows = sorted(rows, key=lambda r: r['tip'])
    half = len(rows) // 2
    fit, test = rows[:half], rows[half:]
    out = {'n': len(rows), 'fit_n': len(fit), 'test_n': len(test)}
    out['logloss'] = {k: round(statistics.mean(ll(r[k], r['y']) for r in test), 5) for k in ('price', 'cons', 'model')}
    blends = {}
    for label, keys in fair_keys:
        b = fit_blend(fit, keys)
        blends[label] = [round(x, 4) for x in b]
        out['logloss'][label] = round(statistics.mean(ll(bprob(b, r, keys), r['y']) for r in test), 5)
    b_pm = fit_blend(fit, ['price', 'model'])
    out['logloss']['price + model'] = round(statistics.mean(ll(bprob(b_pm, r, ['price', 'model']), r['y']) for r in test), 5)
    b_all = fit_blend(fit, ['price', 'cons', 'model'])
    out['logloss']['price + consensus + model'] = round(statistics.mean(ll(bprob(b_all, r, ['price', 'cons', 'model']), r['y']) for r in test), 5)
    out['blend_all'] = [round(x, 4) for x in b_all]
    out['blends'] = blends
    # calibration of the moved consensus, by distance between the lines (all rows: nothing here is fit)
    cal = {}
    for (hi, lab), lo in zip(DIST_BINS, [0.0] + [h for h, _ in DIST_BINS[:-1]]):
        rs = [r for r in rows if lo <= r['dist'] < hi]
        if len(rs) >= 30:
            cal[lab] = {'n': len(rs), 'cons': round(statistics.mean(r['cons'] for r in rs), 4), 'price': round(statistics.mean(r['price'] for r in rs), 4),
                        'hit': round(statistics.mean(1.0 if r['y'] else 0.0 for r in rs), 4),
                        'll_cons': round(statistics.mean(ll(r['cons'], r['y']) for r in rs), 5), 'll_price': round(statistics.mean(ll(r['price'], r['y']) for r in rs), 5)}
    out['by_distance'] = cal
    # betting, second half
    out['bets'] = {}
    for label, keys in fair_keys:
        b = [float(x) for x in blends[label]]
        sides = defaultdict(list)
        for r in test:
            for side, ret in bet_fn(r, bprob(b, r, keys)):
                sides[side].append((r['gid'], ret))
        out['bets'][label] = {side: bet_summary(v) for side, v in sides.items()}
    return out


def main():
    I = F.inputs()
    recs = F.walk_v2(I)
    by = A.by_rec(recs)
    espn, kal = A.load_markets(by)
    v2 = json.load(open(V2.OUT_JSON))
    V = v2['variance']['v2']
    stk = v2['stacker']
    cal = v2['calibration']['v2']
    extra = lambda r, m: (V2.minrate(r, m) * r['sdm']) ** 2
    model = lambda r, m, L: apply_cal(cal[m], V2.p_over(m, V2.mu2(r, stk)[m], L, V, extra(r, m)))
    key = lambda r: (r['gid'], r['aid'])
    tip = {g['game_id']: int(g['tip'].timestamp()) for g in C.games([2026])}

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'edge': EDGE, 'tests': {}}
    books26 = {m: {key(x['r']): x for x in espn.get(('2026', m, 'close'), [])} for m in MARKETS}
    ladders = {m: defaultdict(list) for m in KAL_MKTS}
    for m in KAL_MKTS:
        for x in kal.get(m, []):
            ladders[m][key(x['r'])].append(x)

    def kalshi_bets(r, fair):
        k = r['price']
        out = []
        if fair - k - kalshi_fee(k) >= EDGE:
            c = k + kalshi_fee(k)
            out.append(('YES', (1 - c) / c if r['y'] else -1.0))
        if (1 - fair) - (1 - k) - kalshi_fee(1 - k) >= EDGE:
            c = 1 - k + kalshi_fee(1 - k)
            out.append(('NO', (1 - c) / c if not r['y'] else -1.0))
        return out

    def book_bets(r, fair):
        out = []
        po, pu = am_prob(r['over_px']), am_prob(r['under_px'])
        if fair - po >= EDGE:
            out.append(('Over', am_payout(r['over_px']) if r['y'] else -1.0))
        if (1 - fair) - pu >= EDGE:
            out.append(('Under', am_payout(r['under_px']) if not r['y'] else -1.0))
        return out

    for m in KAL_MKTS:
        # books -> Kalshi
        rows = []
        for k_, lad in ladders[m].items():
            b = books26[m].get(k_)
            if not b:
                continue
            r0 = lad[0]['r']
            ex = extra(r0, m)
            mu = CE.implied_mean(m, [(b['L'], b['pk'], 1.0)], V, ex)
            for x in lad:
                rows.append({'price': x['k'], 'cons': CE.p_over(m, mu, x['L'], V, ex), 'model': model(r0, m, x['L']), 'y': x['yes'],
                             'tip': x['tip'], 'gid': x['gid'], 'dist': abs(x['L'] - b['L'])})
        print(f'{m}: books -> Kalshi {len(rows):,} rungs', flush=True)
        res['tests'].setdefault('books_to_kalshi', {})[m] = evaluate(rows, 'books_to_kalshi', kalshi_bets) if len(rows) >= 400 else {'n': len(rows)}

        # Kalshi ladder -> books
        rows = []
        for k_, b in books26[m].items():
            lad = ladders[m].get(k_)
            if not lad or len(lad) < 2:
                continue
            r0 = b['r']
            ex = extra(r0, m)
            mu = CE.implied_mean(m, [(x['L'], x['k'], 1.0) for x in lad], V, ex)
            rows.append({'price': b['pk'], 'cons': CE.p_over(m, mu, b['L'], V, ex), 'model': model(r0, m, b['L']), 'y': b['over'],
                         'tip': tip.get(int(b['gid']), 0), 'gid': b['gid'], 'dist': min(abs(x['L'] - b['L']) for x in lad),
                         'over_px': b['over_px'], 'under_px': b['under_px']})
        print(f'{m}: Kalshi -> books {len(rows):,} lines', flush=True)
        res['tests'].setdefault('kalshi_to_books', {})[m] = evaluate(rows, 'kalshi_to_books', book_bets) if len(rows) >= 200 else {'n': len(rows)}

        # Kalshi ladder, each rung from the others
        rows = []
        for k_, lad in ladders[m].items():
            if len(lad) < 4:
                continue
            r0 = lad[0]['r']
            ex = extra(r0, m)
            for i, x in enumerate(lad):
                others = [(z['L'], z['k'], 1.0) for j, z in enumerate(lad) if j != i]
                mu = CE.implied_mean(m, others, V, ex)
                rows.append({'price': x['k'], 'cons': CE.p_over(m, mu, x['L'], V, ex), 'model': model(r0, m, x['L']), 'y': x['yes'],
                             'tip': x['tip'], 'gid': x['gid'], 'dist': min(abs(z['L'] - x['L']) for j, z in enumerate(lad) if j != i)})
        print(f'{m}: Kalshi ladder leave-one-out {len(rows):,} rungs', flush=True)
        res['tests'].setdefault('kalshi_ladder', {})[m] = evaluate(rows, 'kalshi_ladder', kalshi_bets) if len(rows) >= 400 else {'n': len(rows)}

    res['verdicts'] = {t: {m: {lab: {side: verdict(s) for side, s in sides.items()} for lab, sides in (d.get('bets') or {}).items() if lab in SHIP}
                           for m, d in ms.items()} for t, ms in res['tests'].items()}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


TEST_NAME = {'books_to_kalshi': 'Books -> Kalshi (Price gap on Kalshi)', 'kalshi_to_books': 'Kalshi ladder -> books (Price gap on books)',
             'kalshi_ladder': 'Kalshi rung from the rest of its ladder (Structural)'}


def write_md(res):
    L = ['# Consensus fair engine: backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_consensus.py`. 2025-26 only (the seasons with both venues archived):",
         'blends fit on the first half by tip time, scored and bet on the second half, 3%+ edge after fees.',
         'Consensus = one venue\'s prices moved to the other venue\'s line through prop model v2\'s distribution shape',
         '(`scripts/consensus.py`); our projection is not in it. "consensus + model" adds our projection in a fitted blend.', '',
         'Ship rule (fixed before running): GO = second-half ROI > 0 with z >= 2 over 50+ games; WATCH = positive; else NO-GO.',
         'Baselines on the same rows (not judged): "price only" = the venue\'s own price recalibrated (catches plain venue',
         'bias, e.g. Kalshi overs), "price + model" = the blend the current GO signals use.', '']
    f = lambda s: f"{s['roi']:+.1%} ({s['n']:,}, {s['games']} g, z {s['z']})" if s and s.get('n') else 'none'
    for t, ms in res['tests'].items():
        L += [f'## {TEST_NAME[t]}', '', '| Stat | Rows | LL price | LL consensus | LL model | LL cons + model | LL price + model | LL price + cons + model |', '|---|---|---|---|---|---|---|---|']
        for m, d in ms.items():
            if not d.get('logloss'):
                L.append(f"| {m} | {d['n']:,} | too few | | | | | |")
                continue
            q = d['logloss']
            L.append(f"| {m} | {d['n']:,} | {q['price']:.4f} | {q['cons']:.4f} | {q['model']:.4f} | {q['consensus + model']:.4f} | {q['price + model']:.4f} | {q['price + consensus + model']:.4f} |")
        L += ['', 'Moving a line: mean consensus vs hit rate and price, by distance between the lines (all rows):', '',
              '| Stat | Distance | Rows | Consensus | Hit rate | Price | LL consensus | LL price |', '|---|---|---|---|---|---|---|---|']
        for m, d in ms.items():
            for lab, c in (d.get('by_distance') or {}).items():
                L.append(f"| {m} | {lab} | {c['n']:,} | {c['cons']:.3f} | {c['hit']:.3f} | {c['price']:.3f} | {c['ll_cons']:.4f} | {c['ll_price']:.4f} |")
        L += ['', 'Betting the second half at 3%+ edge (ROI per unit, bets, games, z by game) and verdict:', '',
              '| Stat | Fair | Side | Result | Verdict |', '|---|---|---|---|---|']
        for m, d in ms.items():
            for lab, sides in (d.get('bets') or {}).items():
                for side, s in sorted(sides.items()):
                    L.append(f"| {m} | {lab} | {side} | {f(s)} | {res['verdicts'][t][m][lab][side] if lab in SHIP else 'baseline'} |")
        L.append('')
    open(OUT_MD, 'w').write('\n'.join(L))


if __name__ == '__main__':
    main()
