#!/usr/bin/env python3
"""
Prop correlation audit, step 2: do props hit together more (or less) often than the model's own probabilities imply?

Reads the legs written by prop_corr_extract.py (the v2 model's pregame over-probability for every settled ESPN main-line leg,
plus the market's no-vig price and the outcome). Changes nothing in the model.

  python3 nba/scripts/prop_corr_analyze.py LEGS.json OUT.json

Unit: a PAIR of legs in the same game (same player / teammates / opponents), base stats only (pts reb ast 3pm). Combo markets
(pra, pr, pa, ra) contain their parts, so their overlap is arithmetic, not information; they are left out of the pairs.

Dependence measure: phi = mean of z1*z2, z = (outcome - p) / sqrt(p(1-p)). For two yes/no outcomes this is exactly the
correlation, whatever the two probabilities are, and 0 if the legs are independent given the model's p. Standard errors are
clustered by game (pairs in one game share everything). Also reported: both-over rate against the product p1*p2, and the
agreement rate (both over or both under) against its independence value, which a one-sided bias in the prices cancels out of.

Brier: joint probability of the four outcomes (over/over, over/under, under/over, under/under).
  independence : P(o,o) = p1*p2
  dependence   : P(o,o) = p1*p2 + phi*sqrt(p1 q1 p2 q2), phi fitted per family on one season, scored on the other (clipped to the
                 feasible range). Also half-size phi (shrinkage). Positive "gain" = dependence beats independence.
"""
import json, math, sys
from collections import defaultdict

STATS = ('pts', 'reb', 'ast', '3pm')
SO = {s: i for i, s in enumerate(STATS)}
MIN_PAIRS, MIN_GAMES = 1000, 200


def fam_key(a, b):
    rel = 'self' if a['aid'] == b['aid'] else 'team' if a['team'] == b['team'] else 'opp'
    s1, s2 = sorted((a['mkt'], b['mkt']), key=SO.get)
    return (rel, s1, s2)


def build_pairs(legs, pkey):
    """-> list of dict pairs. pkey: which probability to treat as the model's ('pm' = v2 model, 'pk' = market no-vig)."""
    by = defaultdict(dict)
    for l in legs:
        if l['mkt'] in SO:
            by[l['gid']][(l['aid'], l['mkt'])] = l          # last wins: two exact duplicate legs exist
    out = []
    for gid, d in by.items():
        L = list(d.values())
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                a, b = L[i], L[j]
                if a['aid'] == b['aid'] and a['mkt'] == b['mkt']:
                    continue
                if a['mkt'] not in SO or b['mkt'] not in SO:
                    continue
                f = fam_key(a, b)
                if f[0] == 'self' and a['mkt'] == b['mkt']:
                    continue
                if (SO[a['mkt']], a['aid']) > (SO[b['mkt']], b['aid']):
                    a, b = b, a
                out.append({'fam': f, 'gid': gid, 'p1': min(.97, max(.03, a[pkey])), 'p2': min(.97, max(.03, b[pkey])),
                            'y1': a['over'], 'y2': b['over'], 'a': a, 'b': b})
    return out


def cl_mean(vals_by_game, n):
    """mean and game-clustered SE of a per-pair statistic; vals_by_game: gid -> sum of the statistic."""
    s = sum(vals_by_game.values())
    m = s / n
    # the cluster sum needs pair counts per game too
    return m


class Acc:
    """accumulate per-pair stats with per-game sums, for a game-clustered mean and SE."""
    def __init__(self):
        self.S = defaultdict(float)
        self.N = defaultdict(int)

    def add(self, gid, v):
        self.S[gid] += v
        self.N[gid] += 1

    def n(self):
        return sum(self.N.values())

    def mean_se(self):
        n = self.n()
        if n == 0:
            return None, None
        m = sum(self.S.values()) / n
        g = len(self.N)
        if g < 2:
            return m, None
        ss = sum((self.S[k] - m * self.N[k]) ** 2 for k in self.N)
        return m, math.sqrt(ss * g / (g - 1)) / n


def zres(y, p):
    return (y - p) / math.sqrt(p * (1 - p))


def family_stats(pairs):
    F = defaultdict(lambda: {'phi': Acc(), 'oo': Acc(), 'agree': Acc()})
    for P in pairs:
        p1, p2, y1, y2 = P['p1'], P['p2'], P['y1'], P['y2']
        f = F[P['fam']]
        f['phi'].add(P['gid'], zres(y1, p1) * zres(y2, p2))
        f['oo'].add(P['gid'], y1 * y2 - p1 * p2)
        f['agree'].add(P['gid'], (1.0 if y1 == y2 else 0.0) - (p1 * p2 + (1 - p1) * (1 - p2)))
    return F


def cells(p1, p2, phi):
    s = math.sqrt(p1 * (1 - p1) * p2 * (1 - p2))
    lo, hi = max(0.0, p1 + p2 - 1), min(p1, p2)
    p11 = min(hi, max(lo, p1 * p2 + phi * s))
    return p11, p1 - p11, p2 - p11, 1 - p1 - p2 + p11


def brier4(P, phi):
    c = cells(P['p1'], P['p2'], phi)
    o = (P['y1'] * P['y2'], P['y1'] * (1 - P['y2']), (1 - P['y1']) * P['y2'], (1 - P['y1']) * (1 - P['y2']))
    return sum((x - y) ** 2 for x, y in zip(c, o))


def brier_oo(P, phi):
    return (cells(P['p1'], P['p2'], phi)[0] - P['y1'] * P['y2']) ** 2


def score(fit_pairs, test_pairs, shrink_names=(('full', 1.0), ('half', 0.5))):
    """fit phi per family on fit_pairs, score on test_pairs. -> {fam: {...}} and pooled"""
    ph = {f: v['phi'].mean_se() for f, v in family_stats(fit_pairs).items()}
    res = defaultdict(lambda: defaultdict(Acc))
    for P in test_pairs:
        f = P['fam']
        if f not in ph:
            continue
        for nm, k in shrink_names:
            phi = k * ph[f][0]
            res[f][nm + '4'].add(P['gid'], brier4(P, 0.0) - brier4(P, phi))
            res[f][nm + 'oo'].add(P['gid'], brier_oo(P, 0.0) - brier_oo(P, phi))
        res[f]['base4'].add(P['gid'], brier4(P, 0.0))
    return ph, res


def slice_phi(pairs, fams, keyfn):
    out = {}
    for fam in fams:
        d = defaultdict(Acc)
        for P in pairs:
            if P['fam'] == fam:
                k = keyfn(P)
                if k is not None:
                    d[k].add(P['gid'], zres(P['y1'], P['p1']) * zres(P['y2'], P['p2']))
        out[fam] = {k: (a.n(), len(a.N)) + a.mean_se() for k, a in sorted(d.items())}
    return out


def main(legs_path, out_path):
    legs = json.load(open(legs_path))
    R = {'notes': {}}
    marg = {}
    for pkey in ('pm', 'pk'):
        P25 = build_pairs([l for l in legs if l['season'] == 2025], pkey)
        P26 = build_pairs([l for l in legs if l['season'] == 2026], pkey)
        marg[pkey] = (P25, P26)
        R[pkey] = {'pairs': {'2025': len(P25), '2026': len(P26)}}
        fs = {'2025': family_stats(P25), '2026': family_stats(P26), 'all': family_stats(P25 + P26)}
        fams = sorted(set(fs['all']), key=lambda f: (f[0], SO[f[1]], SO[f[2]]))
        tab = {}
        for f in fams:
            row = {}
            for k, F in fs.items():
                if f not in F:
                    continue
                phi, oo, ag = F[f]['phi'], F[f]['oo'], F[f]['agree']
                (ph_m, ph_se), (oo_m, oo_se), (ag_m, ag_se) = phi.mean_se(), oo.mean_se(), ag.mean_se()
                row[k] = {'n': phi.n(), 'games': len(phi.N), 'phi': ph_m, 'phi_se': ph_se, 'oo_gap': oo_m, 'oo_se': oo_se,
                          'agree_gap': ag_m, 'agree_se': ag_se}
            tab['|'.join(f)] = row
        R[pkey]['families'] = tab
        # Brier: fit on one season, score on the other
        for lab, (fit, test) in (('fit25_test26', (P25, P26)), ('fit26_test25', (P26, P25))):
            ph, res = score(fit, test)
            out = {}
            for f in fams:
                if f not in res:
                    continue
                r = res[f]
                out['|'.join(f)] = {'phi_fit': ph[f][0], 'n': r['full4'].n(), 'games': len(r['full4'].N),
                                    'base_brier4': r['base4'].mean_se()[0],
                                    'gain_full4': r['full4'].mean_se(), 'gain_half4': r['half4'].mean_se(),
                                    'gain_full_oo': r['fulloo'].mean_se(), 'gain_half_oo': r['halfoo'].mean_se()}
            R[pkey][lab] = out
    # pooled Brier over the families that are 'supported' is decided in the report script; keep per-pair accessors for slices
    P25, P26 = marg['pm']
    allp = P25 + P26

    # ---- why: shared-factor slices, pooled over both seasons, model probabilities
    def self_minerr(P):
        e = P['a']['min'] - P['a']['pmin']
        return 'minutes >4 under projection' if e < -4 else 'minutes within 4 of projection' if abs(e) <= 4 else 'minutes >4 over projection'

    def team_spread(P):
        s = P['a']['spread']
        if s is None:
            return None
        s = abs(float(s))
        return 'pregame spread <5' if s < 5 else 'pregame spread 5-9' if s < 9 else 'pregame spread 9+'

    def both_starters(P):
        return 'both likely starters' if P['a']['st'] > 0.7 and P['b']['st'] > 0.7 else 'one or both bench' if P['a']['st'] < 0.7 or P['b']['st'] < 0.7 else None

    R['slices'] = {}
    selfs = [f for f in set(P['fam'] for P in allp) if f[0] == 'self']
    R['slices']['self_by_minutes_error'] = {'|'.join(f): v for f, v in slice_phi(allp, selfs, self_minerr).items()}
    teams = [f for f in set(P['fam'] for P in allp) if f[0] == 'team']
    R['slices']['team_by_spread'] = {'|'.join(f): v for f, v in slice_phi(allp, teams, team_spread).items()}
    R['slices']['team_by_starter_role'] = {'|'.join(f): v for f, v in slice_phi(allp, teams, both_starters).items()}
    opps = [f for f in set(P['fam'] for P in allp) if f[0] == 'opp']
    R['slices']['opp_by_spread'] = {'|'.join(f): v for f, v in slice_phi(allp, opps, team_spread).items()}
    # self pairs split by whether BOTH stats' legs were the same side of the market (always yes) -> split by season for stability
    json.dump(R, open(out_path, 'w'), indent=1, default=lambda o: None)
    print('wrote', out_path)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
