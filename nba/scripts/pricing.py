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
import consensus as CE

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
        self.MS_all = ms
        self.state = ms.get('example' if example else 'live') if ms else None
        self.MM = (ms or {}).get('minutes') if self.state and any((v or {}).get('ms') for v in self.state['players'].values()) else None
        self.example = example
        self.cand_override = {}          # (team, game id) -> [player ids]: tests feed the backtest's own candidates
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

    # ── tonight's minutes: minutes model v2 on the backtest's own state (build_prop_model_v2.walk) ─────────
    def game_minutes(self, team, g, status, cache):
        """{pid: {'min', 'rate', 'pos', 'mu'}} for the team's players who have minutes state with this team, exactly
        as the backtest projected them: EWMA minutes + minutes model v2 (vacated minutes, blowout from the spread,
        back-to-back), the candidates rescaled to team_min, then per-minute rate x minutes plus the usage cascade.
        status: pid -> injury / lineup status; Out and Doubtful are out (as in the backtest), Inactive too."""
        key = ('gm', team, str(g['id']))
        if key in cache:
            return cache[key]
        M, P, tip = self.MM, self.state['players'], g['tip']
        S = lambda a: P.get(str(a)) or {}
        out = {a: 1.0 for a, stt in status.items() if stt in ('Out', 'Doubtful', 'Inactive')}
        rot = {int(a): v['ms'] for a, v in P.items() if v.get('ms') and v['ms'][3] == team and v['ms'][0] >= M['rot_min']
               and v['ms'][4] >= tip - M['rot_days'] * 86400}
        roster = {x['id'] for x in self.D['teams'].get(team, {}).get('players', [])}
        roster |= {int(a) for a, v in P.items() if v.get('ms') and v['ms'][3] == team and v['ms'][4] >= tip - 30 * 86400}
        cand = self.cand_override.get((team, str(g['id'])))
        cand = [a for a in (cand if cand is not None else sorted(roster))
                if S(a).get('ms') and S(a)['ms'][3] == team and S(a).get('r') and a not in out]
        tl = (self.state.get('team_last') or {}).get(team)
        b2b = 1.0 if tl and tip - tl < 30 * 3600 else 0.0
        sp = g.get('blow_spread', g.get('spread'))       # tests pass the backtest's game-model margin here
        blow = max(0.0, abs(sp) - 6.0) if sp is not None else 0.0
        pm = {}
        for a in cand:
            m, stt, pos = S(a)['ms'][:3]
            vs = sum(q[0] * out.get(b, 0) for b, q in rot.items() if b != a and q[2] == pos)
            vo = sum(q[0] * out.get(b, 0) for b, q in rot.items() if b != a and q[2] != pos)
            share, starter = m / 48.0, stt >= 0.5
            x = [vs, vo, vs * share, vo * share, blow if starter else 0.0, 0.0 if starter else blow, b2b, b2b * share, 1.0]
            pm[a] = max(0.0, min(48.0, m + sum(b * v for b, v in zip(M['beta'], x))))
        tot = sum(pm.values())
        if tot > 0 and len(pm) >= 7:
            f = M['team_min'] / tot
            pm = {a: min(48.0, v * f) for a, v in pm.items()}
        present = [S(a)['r'] for a in cand]
        res = {}
        for a in cand:
            pos, rates, mu = S(a)['ms'][2], S(a)['r'], {}
            for st_ in ('pts', 'reb', 'ast', '3pm'):
                rate, c = rates[st_], M['cascade'].get(st_)
                if c and c['use']:
                    vs = sum(S(b)['pg'][st_] for b in out if S(b).get('pg') and b != a and b in rot and rot[b][2] == pos)
                    vo = sum(S(b)['pg'][st_] for b in out if S(b).get('pg') and b != a and b in rot and rot[b][2] != pos)
                    avg = sum(q[st_] for q in present) / len(present) if present else 0
                    rel = rate / avg if avg > 0 else 1.0
                    bb = c['beta']
                    mu[st_] = max(0.0, pm[a] * rate + pm[a] / 48.0 * (bb[0] * vs + bb[1] * vo + bb[2] * vs * rel + bb[3] * vo * rel))
                else:
                    mu[st_] = max(0.0, pm[a] * rate)
            res[a] = {'min': pm[a], 'rate': rates, 'pos': pos, 'mu': mu}
        cache[key] = res
        return res

    # ── roster guard (docs/moved-players-results.md) ───────────────────────────────────────────────────────
    HOLD_MIN_PLAYERS, HOLD_MAX_MIN = 8, 44.0

    def roster_hold(self, team, g, status, cache, src=None):
        """None, or why a prop is held: priced and shown, but never a Bet / Lean, an edge, a pick'em leg or a shadow bet.
        The page's rosterHold is the same rule. Measured in the backtest (2022-24 and 2025-26, see
        docs/moved-players-results.md): with 7 or fewer players projected, or anyone projected at 44+ minutes, the
        team's minutes run 2 to 4 too high.
          team    the minutes model projects fewer than HOLD_MIN_PLAYERS of the team's players, or someone at HOLD_MAX_MIN+
          player  src 'lab': no minutes history with his current team (moved in, or a rookie), so his minutes come from
                  the Minutes Lab's estimate, which the backtest never scored. Clears after his first game for the team."""
        if self.example or not self.MM or not team or not g:
            return None
        key = ('hold', team, str(g['id']))
        if key not in cache:
            gm = self.game_minutes(team, g, status, cache)
            top = max((v['min'] for v in gm.values()), default=0.0)
            cache[key] = {'why': 'team', 'n': len(gm), 'top': round(top, 1)} if len(gm) < self.HOLD_MIN_PLAYERS or top >= self.HOLD_MAX_MIN else None
        if cache[key]:
            return cache[key]
        return {'why': 'player'} if src == 'lab' else None

    # ── shadow: minutes model v3 (docs/minutes-v3-pricing.md), logged next to v2, never priced ─────────────
    def game_minutes_v3(self, team, g, status, cache, starters=None):
        """{pid: minutes} from minutes model v3 on its own state, as build_prop_model_v2.walk(base='v3') ran it:
        v2's terms plus role (minutes as a starter or off the bench vs overall, keyed on last game's role, or on
        tonight's confirmed five when `starters` is given, with the starters-known weights) and return from absence,
        rescaled to that test's team total."""
        M3 = (self.MS_all or {}).get('minutes_v3')
        tg = self.state.get('m3_games') if self.state else None
        if not M3 or tg is None:
            return {}
        key = ('gm3', team, str(g['id']), bool(starters))
        if key in cache:
            return cache[key]
        P, tip = self.state['players'], g['tip']
        S = lambda a: P.get(str(a)) or {}
        out = {a: 1.0 for a, stt in status.items() if stt in ('Out', 'Doubtful', 'Inactive')}
        rot = {int(a): v['m3'] for a, v in P.items() if v.get('m3') and v['m3'][3] == team and v['m3'][0] >= M3['rot_min']
               and v['m3'][4] >= tip - M3['rot_days'] * 86400}
        roster = {x['id'] for x in self.D['teams'].get(team, {}).get('players', [])}
        roster |= {int(a) for a, v in P.items() if v.get('m3') and v['m3'][3] == team and v['m3'][4] >= tip - 30 * 86400}
        cand = self.cand_override.get((team, str(g['id'])))
        cand = [a for a in (cand if cand is not None else sorted(roster))
                if S(a).get('m3') and S(a)['m3'][3] == team and S(a).get('r') and a not in out]
        beta = M3['beta_starters'] if starters else M3['beta']
        tl = (self.state.get('team_last') or {}).get(team)
        b2b = 1.0 if tl and tip - tl < 30 * 3600 else 0.0
        sp = g.get('blow_spread3', g.get('spread'))
        blow = max(0.0, abs(sp) - 6.0) if sp is not None else 0.0
        pm = {}
        for a in cand:
            m, stt, pos, tm, last, mst, mbn, st_last, idx, since = S(a)['m3']
            vs = sum(q[0] * out.get(b, 0) for b, q in rot.items() if b != a and q[2] == pos)
            vo = sum(q[0] * out.get(b, 0) for b, q in rot.items() if b != a and q[2] != pos)
            share, starter = m / 48.0, stt >= 0.5
            started = (a in starters) if starters else st_last
            ref = mst if started else mbn
            role = (ref - m) if ref is not None else 0.0
            missed = tg.get(team, 0) - (idx if idx is not None else tg.get(team, 0)) - 1 if tm == team else 0
            k = 0 if missed >= M3['return_missed'] else (since + 1 if since is not None else None)
            x = [vs, vo, vs * share, vo * share, blow if starter else 0.0, 0.0 if starter else blow, b2b, b2b * share,
                 role, m * (k == 0), m * (k in (1, 2)), m * (k in (3, 4, 5)), 1.0]
            pm[a] = max(0.0, min(48.0, m + sum(b * v for b, v in zip(beta, x))))
        tot = sum(pm.values())
        if tot > 0 and len(pm) >= 7:
            f = (M3['team_min_starters'] if starters else M3['team_min']) / tot
            pm = {a: min(48.0, v * f) for a, v in pm.items()}
        cache[key] = pm
        return pm

    def mu_for(self, pid, stat, g, cache, outs, team=None, status=None):
        if pid not in self.pidx and not (self.MM and g and team):
            return None
        rteam, p = self.pidx.get(pid, (team, None))
        team = team or rteam
        gm = self.game_minutes(team, g, status or {}, cache) if self.MM and g else {}
        if pid in gm:                                 # the backtest's path: per-game minutes, the model's own rates
            G = gm[pid]
            mn, x = G['min'], G['mu']
            p = dict(p or {'id': pid}, rate=G['rate'], grp=G['pos'])
            src = 'model'
        elif p is None:
            return None
        else:
            return self.mu_lab(pid, stat, g, cache, outs, team, p)
        mu = 0
        for s in COMBO.get(stat, [stat]):
            t = self.v2_terms(team, p, s, x[s], mn, g)
            mu += max(0, x[s] + sum(t.values()))
        P = self.state['players'].get(str(pid)) if self.state else None
        sdm = P['sdm'] if P else 6
        rate = sum(p['rate'][s] for s in COMBO.get(stat, [stat]))
        return {'mu': mu, 'min': mn, 'team': team, 'extra': (rate * sdm) ** 2, 'src': src}

    def mu_lab(self, pid, stat, g, cache, outs, team, p):
        """Fallback for players with no minutes history on their current team (moved, rookies): Minutes Lab minutes
        and rates, as before."""
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
        return {'mu': mu, 'min': mn, 'team': team, 'extra': (rate * sdm) ** 2, 'src': 'lab'}

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
    def price(self, e, g, cache, outs, team=None, status=None):
        mm = self.mu_for(e['p'], e['s'], g, cache, outs, team, status)
        if not mm:
            return None
        s = e['s']
        kc, bc = self.PR['kalshi'].get(s) or self.PR['book'].get(s), self.PR['book'].get(s)
        model = lambda line: self.cal(s, self.p_over_raw(s, mm['mu'], line, mm['extra'])) if mm['min'] > 0 else None
        cands, bfair = [], []
        for row in e.get('books', []):
            bk, line, o, u = row[:4]
            t = row[6] if len(row) > 6 else None
            po, pu = am_p(o), am_p(u)
            if po is None or pu is None or line is None:
                continue
            mkt, pm = po / (po + pu), model(line)
            fair = blend(bc, mkt, pm) if pm is not None and bc else None
            bfair.append((line, fair))
            if fair is not None:
                cands.append({'venue': 'book', 'bk': bk, 'side': 'Over', 'line': line, 'price': o, 'edge': fair - po, 'fair': fair, 'mkt': mkt, 'g': self.gate('book', s, 'Over'), 't': t})
                cands.append({'venue': 'book', 'bk': bk, 'side': 'Under', 'line': line, 'price': u, 'edge': (1 - fair) - pu, 'fair': 1 - fair, 'mkt': 1 - mkt, 'g': self.gate('book', s, 'Under'), 't': t})
        for rung in e.get('kal', []):
            line, bid, ask = rung[:3]
            t = rung[6] if len(rung) > 6 else None
            mid = (bid + ask) / 2 if bid is not None and ask is not None else (ask if ask is not None else bid)
            pm = model(line)
            fair = blend(kc, min(.99, max(.01, mid)), pm) if pm is not None and mid is not None and kc else None
            if fair is None:
                continue
            if ask is not None and 0 < ask < 1:
                cands.append({'venue': 'kalshi', 'bk': 'Kalshi', 'side': 'YES', 'line': line, 'price': ask, 'edge': fair - ask - k_fee(ask), 'fair': fair, 'mkt': mid, 'g': self.gate('kalshi', s, 'YES'), 't': t})
            if bid is not None and 0 < bid < 1:
                cands.append({'venue': 'kalshi', 'bk': 'Kalshi', 'side': 'NO', 'line': line, 'price': 1 - bid, 'edge': (1 - fair) - (1 - bid) - k_fee(1 - bid), 'fair': 1 - fair, 'mkt': 1 - mid, 'g': self.gate('kalshi', s, 'NO'), 't': t})
        # pick'em apps (the page's Pick'em panel): fair = the first book's blend at the same line, else the model;
        # priced lines against their own price, flat ones against the flex break-even. Never gated.
        for row in e.get('pk', []):
            app, line, o, u = row[:4]
            t = row[5] if len(row) > 5 else None
            pm = model(line)
            same = next((f for l, f in bfair if l == line and f is not None), None)
            fair = same if same is not None else pm
            if fair is None:
                continue
            po, pu = am_p(o), am_p(u)
            cands.append({'venue': 'pickem', 'bk': app, 'side': 'Over', 'line': line, 'price': o, 'edge': fair - (po if po is not None else PK_BE), 'fair': fair, 'mkt': po, 'g': 'no-go', 't': t})
            cands.append({'venue': 'pickem', 'bk': app, 'side': 'Under', 'line': line, 'price': u, 'edge': (1 - fair) - (pu if pu is not None else PK_BE), 'fair': 1 - fair, 'mkt': pu, 'g': 'no-go', 't': t})
        self.add_consensus(e, s, cands, model, mm['extra'])
        return {'mu': mm['mu'], 'min': mm['min'], 'team': mm['team'], 'cands': cands, 'src': mm.get('src')}

    # ── consensus (consensus.py): every other venue's price moved to this line ──────────────────
    def add_consensus(self, e, s, cands, model, extra):
        """Adds to each candidate: cons (the other venues' consensus P(this side)), gap (cons-based fair minus cost),
        gap_g (the gate from build_consensus.py). Kalshi rungs use the backtested blend of consensus and model; other
        venues use the consensus alone (untested there)."""
        V = self.PR['variance']
        quotes = []                                   # (venue, line, P(over), weight)
        for row in e.get('books', []):
            bk, line, o, u = row[:4]
            q = CE.book_quote(line, o, u)
            if q:
                quotes.append((bk, q[0], q[1], CE.WEIGHTS.get(bk, 1.5)))
        for rung in e.get('kal', []):
            line, bid, ask = rung[:3]
            if bid is not None and ask is not None and 0 < bid <= ask < 1:
                quotes.append(('Kalshi', line, (bid + ask) / 2, CE.WEIGHTS['Kalshi']))
        CP = self.PR.get('consensus') or {}
        memo = {}
        for c in cands:
            excl = (c['bk'], c['line']) if c['venue'] == 'kalshi' else (c['bk'], None)
            if excl not in memo:
                qs = [(L, p, w) for v, L, p, w in quotes if not (v == excl[0] and (excl[1] is None or L == excl[1]))]
                mu = CE.implied_mean(s, qs, V, extra) if qs else None
                memo[excl] = mu
            mu = memo[excl]
            if mu is None:
                c.update(cons=None, gap=None, gap_g='no-go')
                continue
            over = c['side'] in ('Over', 'YES')
            p_over = CE.p_over(s, mu, c['line'], V, extra)
            fair_over, g = p_over, 'no-go'
            if c['venue'] == 'kalshi' and CP.get('kalshi', {}).get(s):
                pm = model(c['line'])
                if pm is not None:
                    a, bc, bm = CP['kalshi'][s]
                    fair_over = 1 / (1 + math.exp(-max(-30, min(30, a + bc * CE.lg(p_over) + bm * CE.lg(pm)))))
                g = {'GO': 'go', 'WATCH': 'watch'}.get((CP.get('verdict', {}).get(s) or {}).get(c['side']), 'no-go')
            fair = fair_over if over else 1 - fair_over
            cost = c['price'] + k_fee(c['price']) if c['venue'] == 'kalshi' else PK_BE if c['venue'] == 'pickem' and c['price'] is None else am_p(c['price'])
            c.update(cons=round(p_over if over else 1 - p_over, 4), gap=fair - cost if cost is not None else None, gap_g=g)


def outs_from_board(board):
    """team -> [player ids] listed Out (injury report) or Inactive (NBA.com lineups). board['outs'] lists everyone ruled
    out tonight, props or not; older boards only carried the players with props."""
    if board.get('outs') is not None:
        out = {}
        for o in board['outs']:
            if len(o) < 3 or o[2] in ('Out', 'Inactive'):      # the Lab's rebalance: Out and inactive, not Doubtful
                out.setdefault(o[1], []).append(int(o[0]))
        return {t: sorted(v) for t, v in out.items()}
    out = {}
    for pid, P in (board.get('players') or {}).items():
        inj, lu = P[2] if len(P) > 2 else None, P[3] if len(P) > 3 else None
        if (inj and re.match(r'out', inj, re.I)) or lu == 'X':
            out.setdefault(P[1], []).append(int(pid))
    return {t: sorted(v) for t, v in out.items()}      # the page rebalances in id order too


def status_from_board(board):
    """pid -> 'Out' / 'Doubtful' / 'Questionable' / 'Inactive' / ... for tonight's players (the minutes model counts
    Out and Doubtful as out, as the backtest did, and inactive players too)."""
    st = {}
    for pid, P in (board.get('players') or {}).items():
        inj, lu = P[2] if len(P) > 2 else None, P[3] if len(P) > 3 else None
        if inj:
            st[int(pid)] = inj.split()[0].capitalize()
        if lu == 'X':
            st[int(pid)] = 'Inactive'
    for o in board.get('outs') or []:
        st[int(o[0])] = o[2] if len(o) > 2 else 'Out'
    return st


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


NEWS_S = 3 * 3600       # an injury / lineup change this recent, newer than the price, makes an edge "news"
STALE_S = 15 * 60       # another venue changed its price this long after this one: "stale"


def edge_types(c, others_t, news_t, now):
    """Why a candidate is an edge, strongest first: news, stale, ladder (Kalshi consensus), gap (other venues'
    consensus), model. The page's edgeTypes() is the same rule."""
    E = EDGE_MIN
    gap = c.get('gap') is not None and c['gap'] >= E
    any_edge = gap or c['edge'] >= E
    out = []
    if any_edge and now and any(now - tn <= NEWS_S and (not c.get('t') or c['t'] < tn) for tn in news_t):
        out.append('news')
    if gap and c.get('t') and others_t and max(others_t) - c['t'] >= STALE_S:
        out.append('stale')
    if gap:
        out.append('ladder' if c['venue'] == 'kalshi' else 'gap')
    if c['edge'] >= E:
        out.append('model')
    return out


def price_board(board, pricer=None):
    """Every candidate on a board -> list of dicts with player, stat, game, the priceRow fields and edge types."""
    pricer = pricer or Pricer(example=bool(board.get('example')))
    games = {str(g['id']): g for g in board.get('games', [])}
    outs, cache, rows = outs_from_board(board), {}, []
    status = status_from_board(board)
    news = {}
    for n in board.get('news') or []:
        if n[0]:
            news.setdefault(n[3], []).append(n[0])
    for e in board.get('props', []):
        g = games.get(str(e['g']))
        P = (board.get('players') or {}).get(str(e['p'])) or (board.get('players') or {}).get(e['p'])
        r = pricer.price(e, g, cache, outs, P[1] if P else None, status)
        if r:
            times = [(row[0], row[6]) for row in e.get('books', []) if len(row) > 6 and row[6]] + \
                    [('Kalshi', rung[6]) for rung in e.get('kal', []) if len(rung) > 6 and rung[6]] + \
                    [(row[0], row[5]) for row in e.get('pk', []) if len(row) > 5 and row[5]]
            hold = pricer.roster_hold(r['team'], g, status, cache, r.get('src'))
            for c in r['cands']:
                c['types'] = edge_types(c, [t for v, t in times if v != c['bk']], news.get(r['team'], []), board.get('t'))
                rows.append(dict(c, p=e['p'], s=e['s'], gid=str(e['g']), mu=r['mu'], min=r['min'], team=r['team'], hold=hold))
    return rows


if __name__ == '__main__':
    if '--check' in sys.argv:
        ex = json.load(open(os.path.join(DATA, 'prop_board.json')))['example']
        rows = price_board(ex)
        for r in rows[:12]:
            print(f"{r['p']} {r['s']:4s} {r['venue']:6s} {r['bk']:10s} {r['side']:5s} {r['line']:5} mu {r['mu']:.4f} fair {r['fair']:.4f} edge {r['edge']:+.4f} {r['g']}")
        print(len(rows), 'candidates')
