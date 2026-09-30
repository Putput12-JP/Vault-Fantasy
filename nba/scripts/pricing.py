#!/usr/bin/env python3
"""
The Player Props page's pricing, in Python, so the recorder can log what the page would show (the shadow ledger)
without a browser. It must match ui/projections.template.html number for number: same projection (Minutes Lab
minutes x rate + usage cascade, then prop model v2's adjustments), same distribution, calibration, market blend,
fees and gates. `python3 nba/scripts/pricing.py --check` prices the example board and prints rows to compare with
the page.

One addition the page shares (applyOuts in the template): players listed Out on the injury report or Inactive on
NBA.com's lineups get 0 minutes, and their minutes go to teammates by the Minutes Lab's rule (in proportion to
minutes, same-position players NB times more). The page does this for any team the viewer has not edited.
"""
import json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
sys.path.insert(0, HERE)

EDGE_MIN = 0.03
PK_BE = 0.5425               # pick'em break-even per pick on standard 5- and 6-pick flex entries (flat-payout lines)
COMBO = {'pra': ['pts', 'reb', 'ast'], 'pr': ['pts', 'reb'], 'pa': ['pts', 'ast'], 'ra': ['reb', 'ast']}
COUNT = {'reb', 'ast', '3pm'}


class Pricer:
    def __init__(self, D=None, PR=None, MS=None, example=False):
        import render_app
        self.D = D or json.load(open(os.path.join(DATA, 'player_projections.json')))
        self.PR = PR or render_app.pricing()
        ms = MS or json.load(open(os.path.join(DATA, 'model_state.json')))
        self.state = ms.get('example' if example else 'live') if ms else None
        self.example = example
        self.NB = self.D['rebalance']['same'] / self.D['rebalance']['other']
        self.pidx = {p['id']: (t, p) for t, T in self.D['teams'].items() for p in T['players']}

    # ── Minutes Lab ──────────────────────────────────────────────────────────────────────────
    def mins(self, team, outs=()):
        """Default minutes, then each Out player set to 0 with his minutes rebalanced (setMin, balance on)."""
        T = self.D['teams'][team]
        m = {p['id']: p['min0'] for p in T['players']}
        for pid in outs:
            p = next((x for x in T['players'] if x['id'] == pid), None)
            if not p or m[pid] == 0:
                continue
            delta = m[pid]
            m[pid] = 0
            for _ in range(4):
                if abs(delta) <= .05:
                    break
                pool = [q for q in T['players'] if q['id'] != pid and m[q['id']] > 0 and (m[q['id']] < 48 if delta > 0 else True)]
                w = [m[q['id']] * (self.NB if q['grp'] == p['grp'] else 1) for q in pool]
                W = sum(w)
                if not W:
                    break
                moved = 0
                for q, wi in zip(pool, w):
                    nv = max(0, min(48, m[q['id']] + delta * wi / W))
                    moved += nv - m[q['id']]
                    m[q['id']] = nv
                delta -= moved
        return m

    def project(self, team, m):
        T = self.D['teams'][team]
        present = [p for p in T['players'] if m[p['id']] > 0]
        out = [p for p in T['players'] if p['min0'] >= 10 and m[p['id']] == 0]
        res = {}
        for p in T['players']:
            mu = {}
            for s in ('pts', 'reb', 'ast', '3pm', 'stl', 'blk'):
                v = m[p['id']] * p['rate'][s]
                c = self.D['cascade'].get(s)
                if c and c.get('use') and out and m[p['id']] > 0:
                    vs = sum(o['min0'] * o['rate'][s] for o in out if o['grp'] == p['grp'])
                    vo = sum(o['min0'] * o['rate'][s] for o in out if o['grp'] != p['grp'])
                    avg = sum(q['rate'][s] for q in present) / max(1, len(present))
                    rel = p['rate'][s] / avg if avg > 0 else 1
                    b = c['beta']
                    v += m[p['id']] / 48 * (b[0] * vs + b[1] * vo + b[2] * vs * rel + b[3] * vo * rel)
                mu[s] = max(0, v)
            res[p['id']] = mu
        return res

    # ── prop model v2 ────────────────────────────────────────────────────────────────────────
    def v2_terms(self, team, p, s, mu, mn, g):
        zero = {'opp': 0, 'pace': 0, 'market': 0, 'shooting': 0, 'season': 0, 'home': 0, 'b2b': 0, 'bias': 0}
        st = self.state
        if not self.PR.get('stacker') or s not in self.PR['stacker'] or not st or not g or not (mn > 0):
            return zero
        opp = g['away'] if team == g['home'] else g['home'] if team == g['away'] else None
        T, O, P = st['teams'].get(team), opp and st['teams'].get(opp), st['players'].get(str(p['id'])) or {}
        home = 1 if team == g['home'] else 0
        b2b = 1 if T and T.get('last') and g['tip'] - T['last'] < 30 * 3600 else 0
        pace = (T['pace'] + O['pace'] - st['lg_pace']) / T['pace'] if T and O and st.get('lg_pace') else 1
        mkt = 1
        if g.get('total') is not None and g.get('spread') is not None and T and T.get('pts'):
            mkt = (g['total'] / 2 + (-g['spread'] if home else g['spread']) / 2) / T['pts']
        oppF = O['def'][p['grp']][s] if O and O.get('def', {}).get(p['grp']) else 1
        rate = p['rate'][s]
        sr = P.get('sr')
        struct = mn * (sr[0] if s == 'pts' else sr[1]) - mu if sr and s in ('pts', '3pm') else 0
        z = P.get('szn')
        season = mn * ((z['S'][s] + 200 * rate) / (z['M'] + 200) - rate) if z and z.get('season') == st['season'] and z['M'] > 0 else 0
        f = [mu * (oppF - 1), mu * (pace - 1), mu * (mkt - 1), struct, season, mu * (home - .5), mu * b2b, mu, 1]
        c = [x * b for x, b in zip(f, self.PR['stacker'][s])]
        return {'opp': c[0], 'pace': c[1], 'market': c[2], 'shooting': c[3], 'season': c[4], 'home': c[5], 'b2b': c[6], 'bias': c[7] + c[8]}

    def mu_for(self, pid, stat, g, cache, outs):
        if pid not in self.pidx:
            return None
        team, p = self.pidx[pid]
        if team not in cache:
            m = self.mins(team, outs.get(team, ()))
            cache[team] = (m, self.project(team, m))
        m, pr = cache[team]
        x, mn = pr[pid], m[pid]
        snap = self.example and self.state and self.state['players'].get(str(pid))
        if snap and snap.get('min') and snap.get('rate'):
            mn = snap['min']
            x = {s: mn * r for s, r in snap['rate'].items()}
            p = dict(p, rate=snap['rate'])
        mu = 0
        for s in COMBO.get(stat, [stat]):
            t = self.v2_terms(team, p, s, x[s], mn, g)
            mu += max(0, x[s] + sum(t.values()))
        P = self.state['players'].get(str(pid)) if self.state else None
        sdm = P['sdm'] if P else 6
        rate = sum(p['rate'][s] for s in COMBO.get(stat, [stat]))
        return {'mu': mu, 'min': mn, 'team': team, 'extra': (rate * sdm) ** 2}

    # ── distribution, calibration, blend ─────────────────────────────────────────────────────
    def p_over_raw(self, stat, mu, line, extra=0):
        v0, v1, v2, v3 = self.PR['variance'][stat]
        v = max(.25, v0 + v1 * mu + v2 * mu * mu + (v3 * extra if v3 else 0))
        return nb_sf(math.floor(line), mu, v) if stat in COUNT else 1 - Phi((line - mu) / math.sqrt(v))

    def cal(self, stat, p):
        K = self.PR['calibration'].get(stat)
        if not K:
            return p
        if p <= K[0][0]:
            return K[0][1] * p / K[0][0] if K[0][0] > 0 else K[0][1]
        L = K[-1]
        if p >= L[0]:
            return L[1] + (1 - L[1]) * (p - L[0]) / max(1e-9, 1 - L[0])
        for i in range(1, len(K)):
            if p <= K[i][0]:
                return K[i - 1][1] + (K[i][1] - K[i - 1][1]) * (p - K[i - 1][0]) / max(1e-9, K[i][0] - K[i - 1][0])
        return p

    def gate(self, venue, stat, side):
        if venue != 'kalshi':
            return 'no-go'
        m = re.match(r'^(GO|WATCH|NO-GO)(?: \((YES|NO)\))?', self.PR['verdict'].get(stat) or 'NO-GO')
        if not m or m.group(1) == 'NO-GO' or (m.group(2) and m.group(2) != side):
            return 'no-go'
        return m.group(1).lower()

    # ── one prop, every venue (priceRow) ─────────────────────────────────────────────────────
    def price(self, e, g, cache, outs):
        mm = self.mu_for(e['p'], e['s'], g, cache, outs)
        if not mm:
            return None
        s = e['s']
        kc, bc = self.PR['kalshi'].get(s) or self.PR['book'].get(s), self.PR['book'].get(s)
        model = lambda line: self.cal(s, self.p_over_raw(s, mm['mu'], line, mm['extra'])) if mm['min'] > 0 else None
        cands, bfair = [], []
        for bk, line, o, u, *_ in e.get('books', []):
            po, pu = am_p(o), am_p(u)
            if po is None or pu is None or line is None:
                continue
            mkt, pm = po / (po + pu), model(line)
            fair = blend(bc, mkt, pm) if pm is not None and bc else None
            bfair.append((line, fair))
            if fair is not None:
                cands.append({'venue': 'book', 'bk': bk, 'side': 'Over', 'line': line, 'price': o, 'edge': fair - po, 'fair': fair, 'mkt': mkt, 'g': self.gate('book', s, 'Over')})
                cands.append({'venue': 'book', 'bk': bk, 'side': 'Under', 'line': line, 'price': u, 'edge': (1 - fair) - pu, 'fair': 1 - fair, 'mkt': 1 - mkt, 'g': self.gate('book', s, 'Under')})
        for rung in e.get('kal', []):
            line, bid, ask = rung[:3]
            mid = (bid + ask) / 2 if bid is not None and ask is not None else (ask if ask is not None else bid)
            pm = model(line)
            fair = blend(kc, min(.99, max(.01, mid)), pm) if pm is not None and mid is not None and kc else None
            if fair is None:
                continue
            if ask is not None and 0 < ask < 1:
                cands.append({'venue': 'kalshi', 'bk': 'Kalshi', 'side': 'YES', 'line': line, 'price': ask, 'edge': fair - ask - k_fee(ask), 'fair': fair, 'mkt': mid, 'g': self.gate('kalshi', s, 'YES')})
            if bid is not None and 0 < bid < 1:
                cands.append({'venue': 'kalshi', 'bk': 'Kalshi', 'side': 'NO', 'line': line, 'price': 1 - bid, 'edge': (1 - fair) - (1 - bid) - k_fee(1 - bid), 'fair': 1 - fair, 'mkt': 1 - mid, 'g': self.gate('kalshi', s, 'NO')})
        # pick'em apps (the page's Pick'em panel): fair = the first book's blend at the same line, else the model;
        # priced lines against their own price, flat ones against the flex break-even. Never gated.
        for app, line, o, u, *_ in e.get('pk', []):
            pm = model(line)
            same = next((f for l, f in bfair if l == line and f is not None), None)
            fair = same if same is not None else pm
            if fair is None:
                continue
            po, pu = am_p(o), am_p(u)
            cands.append({'venue': 'pickem', 'bk': app, 'side': 'Over', 'line': line, 'price': o, 'edge': fair - (po if po is not None else PK_BE), 'fair': fair, 'mkt': po, 'g': 'no-go'})
            cands.append({'venue': 'pickem', 'bk': app, 'side': 'Under', 'line': line, 'price': u, 'edge': (1 - fair) - (pu if pu is not None else PK_BE), 'fair': 1 - fair, 'mkt': pu, 'g': 'no-go'})
        return {'mu': mm['mu'], 'min': mm['min'], 'team': mm['team'], 'cands': cands}


def outs_from_board(board):
    """team -> [player ids] listed Out (injury report) or Inactive (NBA.com lineups)."""
    out = {}
    for pid, P in (board.get('players') or {}).items():
        inj, lu = P[2] if len(P) > 2 else None, P[3] if len(P) > 3 else None
        if (inj and re.match(r'out', inj, re.I)) or lu == 'X':
            out.setdefault(P[1], []).append(int(pid))
    return {t: sorted(v) for t, v in out.items()}      # the page rebalances in id order too


def erf(x):
    t = 1 / (1 + 0.3275911 * abs(x))
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-x * x)
    return y if x >= 0 else -y


def Phi(x):
    return 0.5 * (1 + erf(x / math.sqrt(2)))


def nb_sf(k, mu, v):
    if mu <= 0:
        return 0
    cdf = 0
    if v <= mu * 1.0001:
        p = math.exp(-mu)
        for i in range(k + 1):
            cdf += p
            p *= mu / (i + 1)
        return max(0, 1 - cdf)
    r, q = mu * mu / (v - mu), mu / v
    p = q ** r
    for i in range(k + 1):
        cdf += p
        p *= (i + r) / (i + 1) * (1 - q)
    return max(0, 1 - cdf)


def lg(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def blend(c, mkt, mdl):
    return 1 / (1 + math.exp(-(c['a'] + c['wm'] * lg(mkt) + c['wp'] * lg(mdl))))


def am_p(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(a) or a == 0:
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def k_fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def price_board(board, pricer=None):
    """Every candidate on a board -> list of dicts with player, stat, game and the priceRow fields."""
    pricer = pricer or Pricer(example=bool(board.get('example')))
    games = {str(g['id']): g for g in board.get('games', [])}
    outs, cache, rows = outs_from_board(board), {}, []
    for e in board.get('props', []):
        g = games.get(str(e['g']))
        r = pricer.price(e, g, cache, outs)
        if r:
            for c in r['cands']:
                rows.append(dict(c, p=e['p'], s=e['s'], gid=str(e['g']), mu=r['mu'], min=r['min'], team=r['team']))
    return rows


if __name__ == '__main__':
    if '--check' in sys.argv:
        ex = json.load(open(os.path.join(DATA, 'prop_board.json')))['example']
        rows = price_board(ex)
        for r in rows[:12]:
            print(f"{r['p']} {r['s']:4s} {r['venue']:6s} {r['bk']:10s} {r['side']:5s} {r['line']:5} mu {r['mu']:.4f} fair {r['fair']:.4f} edge {r['edge']:+.4f} {r['g']}")
        print(len(rows), 'candidates')
