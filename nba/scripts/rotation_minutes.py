#!/usr/bin/env python3
"""
Rotation-aware minutes (C3), the scoring half: pure functions, no data access. The model is round 3's (docs/rotation-minutes-round3.md); the weights are fitted once by
build_rotation_minutes_model.py using test_rotation_minutes.py's own fitting code and live in data/rotation_minutes_model.json. This module applies them to one team's pool.
tests/test_rotation_minutes_shadow.py proves it equals test_rotation_minutes.py's xs_common3, xs_min3, predict, pis and rescale on random inputs.

A pool row is a dict:  m (EWMA minutes), st (starter rate), n (games), rank (1 = most minutes in the pool), d3 (mean of his last 3 games' minutes minus m, 0 with no history),
gap (team games since he last played, 0 to 10), last_days (days since his last game), vs / vo (minutes vacated by Out players at his position / elsewhere), nout (rotation players Out),
b2b, home, size (the pool's size), e (expected home margin; only |e| matters).
"""
import math

SD_MARGIN = 13.2
ROT_CUT = 12.0


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def pis(e):
    """P(final |margin| in close, middle, blowout) for margin ~ Normal(e, SD_MARGIN)."""
    e = 0.0 if e is None else e
    cdf = lambda x: phi((x - e) / SD_MARGIN)
    p10 = cdf(10) - cdf(-10)
    p20 = cdf(20) - cdf(-20)
    return [p10, p20 - p10, 1 - p20]


def sig(z):
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def size_feats(r):
    n = r['size']
    return [n / 15.0, 1.0 if n >= 15 else 0.0, 1.0 if n <= 12 else 0.0, (n - 13) / 5.0 * r['rank'] / 10.0]


def x_common(r):
    return [1.0, r['m'] / 48.0, r['st'], min(r['n'], 30) / 30.0, r['rank'] / 10.0, 1.0 if r['rank'] > 8 else 0.0, r['d3'] / 10.0, r['gap'] / 10.0,
            min(r['last_days'], 30) / 30.0, r['vs'] / 48.0, r['vo'] / 48.0, r['nout'] / 5.0, r['b2b'], r['home']] + size_feats(r)


def x_min(r):
    return [1.0, r['m'] / 48.0, r['st'], r['vs'] / 48.0, r['vo'] / 48.0, r['d3'] / 10.0, r['b2b'], r['home'], r['rank'] / 10.0, r['nout'] / 5.0] + size_feats(r)


def predict_state(M, r):
    """(P(plays), P(rotation | plays), E[minutes | plays]) under one state's weights."""
    xc = x_common(r)
    pp = sig(sum(a * b for a, b in zip(M['wp'], xc)))
    pr = sig(sum(a * b for a, b in zip(M['wr'], xc)))
    mu = max(ROT_CUT, sum(a * b for a, b in zip(M['wm'], x_min(r))))
    return pp, pr, pr * mu + (1 - pr) * M['g']


def rescale(preds, T):
    """[(P(plays), conditional minutes)] for one pool -> conditional minutes after the pool's unconditional total is set to T."""
    tot = sum(p * m for p, m in preds)
    f = T / tot if tot > 0 and len(preds) >= 7 else 1.0
    return [min(48.0, f * p * m / max(p, 1e-3)) for p, m in preds]


def score_pool(model, rows):
    """-> [{'min': conditional minutes, 'p_rot': P(rotation | plays), 'p_plays': P(plays)}] in the rows' order. model = data/rotation_minutes_model.json."""
    if not rows:
        return []
    pi = pis(rows[0].get('e'))
    per = [[predict_state(model['states'][s], r) for r in rows] for s in range(3)]
    mixp = [sum(pi[s] * per[s][i][0] for s in range(3)) for i in range(len(rows))]
    mixr = [sum(pi[s] * per[s][i][1] for s in range(3)) for i in range(len(rows))]
    mixm = [sum(pi[s] * per[s][i][2] for s in range(3)) for i in range(len(rows))]
    cm = rescale(list(zip(mixp, mixm)), model['T'])
    return [{'min': cm[i], 'p_rot': mixr[i], 'p_plays': mixp[i]} for i in range(len(rows))]
