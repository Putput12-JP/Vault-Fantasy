#!/usr/bin/env python3
"""
Confidence levels for the Props Simulation lean, and three frozen challengers, scored against the box score.

Why (Nov 5 2026 search, 6,693 settled props, 8 hypothesis families, 24 rules, sealed holdout Nov 2 and Nov 4):
  The model's own confidence, how far its calibrated over chance (pe) sits from 50%, was the only ladder that rose tier by tier on the sealed games:
  level 1 to 4 hit 47.8 / 49.0 / 57.2 / 65.5% (n 561 / 431 / 388 / 220), with always-under on the same props 49.6 / 52.4 / 53.9 / 62.7%.
  No challenger beat it on the sealed games, so the page shows this ladder and the three strongest challengers are tracked forward from
  FORWARD_FROM, frozen exactly as they were checked (every number below was fitted on Oct 20 to Nov 1 only).

The model ladder (shown on the page):
  lean  = the side the model gives 50% or more (pe >= .5 is over)
  level = 1 to 4 by |pe - 0.5| against MODEL_CUTS, the quartiles of Oct 20 to Nov 1. Levels 1 and 2 lost on the sealed games (below 50%).

The challengers (recorded, never shown as a call):
  agree     the model lean, no call when the market's side (pm) disagrees or there is no price; level by |pe - .5|
  minutes   the model lean, no call when a minutes-mixture chance disagrees: the model's per-minute rate times tonight's projected minutes scaled by
            the Oct 20 to Nov 1 spread of actual/projected minutes (MIN_RATIO_Q), priced with a negative binomial (dispersion MIN_PHI); level by |pe - .5|
  combined  p = sigmoid(b + w1 logit(pe) + w2 logit(pm)) (pm missing: pe), lean over when p >= centre, called only when 2 of 3 checks agree
            (model side, minutes vs the minutes the line needs, minutes-scaled median of the last 25 games); level by |p - centre|

Per game the ledger stores, for props the roster guard trusts (as the minutes-model comparison does):
  'c': {'model': {stat: [[n, model side won, under won] x 4 levels]}, 'agree' | 'minutes' | 'combined': [[n, won, under won] x 4 levels]}
`under won` is how often the under landed on the same props, so the page can show the ladder next to always taking the under.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
FORWARD_FROM = '2026-11-05'            # challengers are frozen from this tip day; earlier days are in-sample (the search saw them)
MODEL_CUTS = (0.0345, 0.0683, 0.1223)  # |pe - .5| quartiles, Oct 20 to Nov 1 (5,093 props)
CUTS = {'agree': (0.0399, 0.0801, 0.1329), 'minutes': (0.0393, 0.076, 0.1278), 'combined': (0.0317, 0.0633, 0.1027)}
COMB_W, COMB_B, COMB_C = (0.1036967608253502, 1.1088344260577672), -0.04247055840229226, 0.4729329798251778
MIN_PHI = {'pts': 2.398, 'reb': 1.1585, 'ast': 1.1614, '3pm': 1.0943}
STATS = ['pts', 'reb', 'ast', '3pm']
CHALLENGERS = ['agree', 'minutes', 'combined']
_Q = os.path.join(HERE, '..', 'data', 'conf_ladder_frozen.json')       # MIN_RATIO_Q: 201 quantiles of actual/projected minutes, Oct 20 to Nov 1


def level(conf, cuts=MODEL_CUTS):
    return 1 + sum(conf >= c for c in cuts)


def _lg(p):
    p = min(max(p, .02), .98)
    return math.log(p / (1 - p))


def _nb_sf(k, mean, phi):
    """P(X > k) for a negative binomial with this mean and variance mean * phi (phi > 1)."""
    r, p = mean / (phi - 1), 1 / phi
    if k < 0:
        return 1.0
    lp, cdf = r * math.log(p), 0.0
    for x in range(int(k) + 1):
        cdf += math.exp(lp)
        lp += math.log((x + r) / (x + 1)) + math.log(1 - p)
    return max(0.0, 1 - cdf)


def _season(day):
    import datetime
    d = datetime.date(1970, 1, 1) + datetime.timedelta(days=day)
    return d.year + 1 if d.month >= 8 else d.year


def cday(ts):
    return int((ts - 5 * 3600) // 86400)


class Logs:
    """Each player's game log (data/gamelogs.json), read only before the prop's day."""
    def __init__(self, path=os.path.join(HERE, '..', 'data', 'gamelogs.json')):
        g = json.load(open(path))
        self.C = {c: i for i, c in enumerate(g['cols'])}
        self.P = g['players']
        self.q = json.load(open(_Q))['ratio_q']

    def hist(self, pid, day):
        return [x for x in self.P.get(str(pid), []) if x[self.C['day']] < day]


def _minutes_side(line, mu, pmin, day, H, L):
    if not pmin or not mu or mu <= 0:
        return 0
    need = line / (mu / pmin)
    s, im, ip = _season(day), L.C['min'], L.C['playoff']
    m3 = [x[im] for x in H if x[L.C['season']] == s and not x[ip]][:3]
    l5 = [x[im] for x in H if not x[ip]][:5]
    v = [x for x in (pmin, sum(m3) / len(m3) if m3 else None, sum(l5) / len(l5) if l5 else None) if x is not None]
    return 1 if min(v) > need else -1 if max(v) < need else 0


def _form_side(stat, line, pmin, H, L):
    if not pmin or pmin <= 0:
        return 0
    i, im = L.C[stat], L.C['min']
    G = [(x[im], x[i]) for x in H if x[im] is not None and x[im] >= 8][:25]
    if len(G) < 5:
        return 0
    v = sorted(s * pmin / m for m, s in G)[len(G) // 2]
    return 1 if v > line else -1 if v < line else 0


def calls(row, m, L):
    """{rule: (lean 'over' | 'under', level)} for one psim row and its meta. A rule that makes no call is left out."""
    line, mu, pe, p10, p50, pm, src = row
    out = {'model': ('over' if pe >= .5 else 'under', level(abs(pe - .5)))}
    if pm is not None and (pe >= .5) == (pm >= .5):
        out['agree'] = (out['model'][0], level(abs(pe - .5), CUTS['agree']))
    pmin, stat = m.get('min'), m['stat']
    if L is None:
        return out
    if pmin and mu > 0:
        ph = MIN_PHI[stat]
        p = sum(_nb_sf(math.floor(line), max(mu * min(max(q, 0), 48 / pmin), 1e-3), ph) for q in L.q) / len(L.q)
        if (p >= .5) == (pe >= .5):
            out['minutes'] = (out['model'][0], level(abs(pe - .5), CUTS['minutes']))
    day = cday(m['tip'])
    H = L.hist(m['pid'], day)
    z = COMB_B + COMB_W[0] * _lg(pe) + COMB_W[1] * _lg(pm if pm is not None else pe)
    p = 1 / (1 + math.exp(-z))
    s = 1 if p >= COMB_C else -1
    v = ((pe >= .5) == (s > 0)) + (_minutes_side(line, mu, pmin, day, H, L) == s) + (_form_side(stat, line, pmin, H, L) == s)
    if v >= 2:
        out['combined'] = ('over' if s > 0 else 'under', level(abs(p - COMB_C), CUTS['combined']))
    return out


def score_game(rows, bx, L, box_key):
    """rows: {(pid, stat): (row, meta)} (held props already left out). bx: {pid: box line}. Returns the per-game 'c' entry, or None if nothing settled."""
    c = {'model': {s: [[0, 0, 0] for _ in range(4)] for s in STATS}, **{k: [[0, 0, 0] for _ in range(4)] for k in CHALLENGERS}}
    any_ = False
    for (pid, s), (row, m) in rows.items():
        st = bx.get(int(pid))
        if not st:
            continue
        y = st.get(box_key[s], 0)
        if y == row[0]:
            continue
        over = y > row[0]
        for rule, (lean, lv) in calls(row, m, L).items():
            t = c['model'][s][lv - 1] if rule == 'model' else c[rule][lv - 1]
            t[0] += 1
            t[1] += (lean == 'over') == over
            t[2] += not over
            any_ = True
    if not any_:
        return None
    c['model'] = {s: v for s, v in c['model'].items() if any(t[0] for t in v)}
    return c
