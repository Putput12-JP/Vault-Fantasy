#!/usr/bin/env python3
"""
Market-anchored projection test. Rules, fixed before any score: docs/game-model-anchored.md. Results: docs/game-model-anchored-results.md.

  python3 nba/scripts/test_game_model_anchored.py [--games FILE] [--first FILE] [--lock FILE] [--out FILE]

--games  per-game history dump (season, am_res, am, tip, sp_close); built from the raw data by build_game_model.run when absent (about a minute).
--first  this season's 4-hour-lock rows (a rebuild_game_picks_lineup_lock.py --rule 4h file, as registered); --lock the lineup-lock rows (data/game_picks.json).
Pure stdlib.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
DATA = os.path.join(HERE, '..', 'data')
DOCS = os.path.join(HERE, '..', 'docs')


def solve(A, b):
    k = len(b); M = [A[i][:] + [b[i]] for i in range(k)]
    for i in range(k):
        p = max(range(i, k), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(k):
            if r != i:
                f = M[r][i] / M[i][i]; M[r] = [a - f * c for a, c in zip(M[r], M[i])]
    return [M[i][k] / M[i][i] for i in range(k)]


def ols(X, y):
    """beta, se, resid sd for y ~ X (X rows include the constant)."""
    n, k = len(y), len(X[0])
    A = [[sum(x[i] * x[j] for x in X) for j in range(k)] for i in range(k)]
    beta = solve(A, [sum(x[i] * v for x, v in zip(X, y)) for i in range(k)])
    s2 = sum((v - sum(b * xi for b, xi in zip(beta, x))) ** 2 for x, v in zip(X, y)) / (n - k)
    se = [math.sqrt(s2 * solve(A, [1.0 if t == j else 0.0 for t in range(k)])[j]) for j in range(k)]
    return beta, se, math.sqrt(s2)


def info(rows, label):
    """result - L = a + g1 (M1 - L) + g2 (M2 - M1). rows: (result, L, M1, M2)."""
    X = [[1.0, m1 - L, m2 - m1] for _, L, m1, m2 in rows]; y = [r - L for r, L, _, _ in rows]
    b, se, _ = ols(X, y)
    return {'label': label, 'n': len(y), 'g1': b[1], 'se1': se[1], 't1': b[1] / se[1], 'g2': b[2], 'se2': se[2], 't2': b[2] / se[2]}


def through_origin(x, y):
    return sum(a * b for a, b in zip(x, y)) / sum(a * a for a in x)


def paired_t(a, b):
    d = [u - v for u, v in zip(a, b)]; n = len(d); m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1))
    return (m, m / (sd / math.sqrt(n))) if sd else (m, 0.0)          # identical errors: no variance, no signal


def folds(rows_by_season):
    """Fit on the other season, score on this one. rows: (result, L, M1, M2)."""
    out = []
    seasons = sorted(rows_by_season)
    for s in seasons:
        fit = [r for t in seasons if t != s for r in rows_by_season[t]]
        w = through_origin([m2 - L for _, L, _, m2 in fit], [r - L for r, L, _, _ in fit])
        k = through_origin([m2 - m1 for _, _, m1, m2 in fit], [r - L for r, L, _, _ in fit])
        test = rows_by_season[s]
        pred = {'A0 line': [L for _, L, _, _ in test],
                'A1 line + w(model - line)': [L + w * (m2 - L) for _, L, _, m2 in test],
                'A2 line + k(news part)': [L + k * (m2 - m1) for _, L, m1, m2 in test],
                'A3 raw model': [m2 for _, _, _, m2 in test]}
        res = [r for r, _, _, _ in test]
        se0 = [(p - r) ** 2 for p, r in zip(pred['A0 line'], res)]
        rep = {}
        for name, p in pred.items():
            se_ = [(a - r) ** 2 for a, r in zip(p, res)]
            d, t = paired_t(se_, se0) if name != 'A0 line' else (0.0, 0.0)
            rep[name] = {'mse': sum(se_) / len(se_), 'mae': sum(abs(a - r) for a, r in zip(p, res)) / len(res), 'd_mse_vs_line': d, 't': t}
        out.append({'test': s, 'w': w, 'k': k, 'n': len(test), 'rep': rep})
    return out


def picks(rows, part, cut):
    """Side by the sign of the part (news: M2 - M1; ratings: M1 - L), at the line, win rate at -110 over decided games."""
    w = l = 0
    for r, L, m1, m2 in rows:
        v = (m2 - m1) if part == 'news' else (m1 - L)
        if abs(v) < cut:
            continue
        cover = r - L
        if cover == 0:
            continue
        w += (cover > 0) == (v > 0); l += (cover > 0) != (v > 0)
    return w, l


def load_history(path):
    if path and os.path.exists(path):
        g = json.load(open(path))
    else:
        import build_game_model as B, nba_common as C
        box = C.player_games(B.WARM + B.TUNE + B.TEST)
        P = dict(B.DEFAULT, **json.load(open(B.OUT_JSON))['params'])
        _, recs = B.run(P, B.WARM + B.TUNE + B.TEST, box, C.closing_lines(), C.InjuryAsOf(B.TEST, C.player_index(box)), record_from=B.TEST[0])
        g = [{'season': r['g']['season'], 'am_res': r['actual_margin'], 'am': r['am'][0], 'tip': r['tip'][0], 'sp_close': (r.get('line') or {}).get('spread_close')} for r in recs]
    by = {}
    for r in g:
        if r['sp_close'] is None:
            continue
        by.setdefault(r['season'], []).append((float(r['am_res']), -float(r['sp_close']), float(r['am']), float(r['tip'])))
    return by


def load_forward(first_path, lock_path):
    sys.path.insert(0, HERE)
    import game_pick_record as G

    def rows(p):
        out = {}
        for day, x in json.load(open(p))['days'].items():
            for r in x['rows']:
                o = dict(zip(G.COLS, r))
                if o['clock'] == 'f' and o['spread'] is not None and o['am'] is not None:
                    out[o['game']] = o
        return out
    a, b = rows(first_path), rows(lock_path)
    return [(float(b[k]['am']), -float(b[k]['spread']), float(a[k]['margin']), float(b[k]['margin'])) for k in b if k in a]


def main(argv):
    arg = lambda f, d=None: argv[argv.index(f) + 1] if f in argv else d
    hist = load_history(arg('--games'))
    fwd = load_forward(arg('--first', os.path.join(DATA, 'game_picks_4h_lock.json')), arg('--lock', os.path.join(DATA, 'game_picks.json')))
    out = {'info': [info(r, str(s)) for s, r in sorted(hist.items())] + [info([x for r in hist.values() for x in r], 'history pooled'), info(fwd, 'this season')],
           'folds': folds(hist), 'picks': {}}
    for name, rows in list(hist.items()) + [('this season', fwd)]:
        out['picks'][str(name)] = {f'{part} {cut}+': picks(rows, part, cut) for part in ('news', 'ratings') for cut in (1, 2, 3)}
    out['n_forward'] = len(fwd)
    print(json.dumps(out, indent=1, default=lambda x: round(x, 4)))
    if arg('--out'):
        json.dump(out, open(arg('--out'), 'w'), default=lambda x: round(x, 4))
    return out


if __name__ == '__main__':
    main(sys.argv[1:])
