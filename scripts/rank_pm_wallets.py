#!/usr/bin/env python3
"""
Polymarket wallet ranking with shrinkage and cross-sport pooling (Sharp Price V2).

The scorecards (data/pm_wallets*.json, scripts/build_pm_wallets.py) label a wallet sharp only at t >= 3. In the NBA that
labels 1 wallet of 968, and it says nothing about a wallet with 8 NBA games and a strong NFL record. This ranks every wallet
by the posterior of its true skill (mean closing-line value per game) in a chosen sport:

  y_ws   observed mean per-game score of wallet w in sport s (n_ws games), noise variance sigma_s^2 / n_ws
  mu_ws  true skill, N(m_s, tau_s^2) across wallets, with one correlation rho between a wallet's skills in different sports

m_s, tau_s, sigma_s are estimated from the scorecards themselves (method of moments); rho from wallets seen in two sports.
The posterior for a sport given everything observed on a wallet is a plain conditional Gaussian, so a wallet with few NBA
games leans on the league average and on its NFL / CFB record in proportion to how noisy each is. Nothing is fitted by search.

Tiers (p = posterior chance its skill is above zero): proven >= 0.95, probable >= 0.80, watching >= 0.60, dull <= 0.05.
Cut-offs are conventional, not tuned; the hold-out below is how they are judged.

Hold-out (written to the output): rank every wallet's NBA skill from NFL + CFB data ONLY, then compare the NBA record those
wallets actually have, by tier, against the old hard label (NFL t >= 3) and against ranking by the raw NFL mean.
The scorecards store sums, not dated games, so a within-sport time split is not possible; this is the honest test available.

Usage: python3 scripts/rank_pm_wallets.py [--sport=nba] [--dry]  ->  data/pm_wallet_rank.json
"""
import json, math, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {'nfl': 'pm_wallets.json', 'cfb': 'pm_wallets_cfb.json', 'nba': 'pm_wallets_nba.json'}
OUT = os.path.join(ROOT, 'data', 'pm_wallet_rank.json')
K_VAR = 4                       # prior games' worth of pooled variance mixed into a wallet's own variance
MIN_N_PRIOR = 5                 # the cross-wallet spread is estimated from wallets with this many games: below it a wallet's own variance is noise
MIN_N_RHO = 3                   # games a wallet needs in BOTH sports to inform rho
TIERS = (('proven', 0.95), ('probable', 0.80), ('watching', 0.60))
DULL_P = 0.05


def load(root=ROOT):
    """{sport: {wallet: [n, mean, sample variance or None]}}"""
    out = {}
    for s, f in FILES.items():
        try:
            j = json.load(open(os.path.join(root, 'data', f)))
        except (OSError, ValueError):
            out[s] = {}
            continue
        d = {}
        for w, a in (j.get('wallets') or {}).items():
            n, sm, ss = a[0], a[1], a[2]
            if n < 1:
                continue
            m = sm / n
            d[w] = [n, m, max(ss / n - m * m, 0) * n / (n - 1) if n > 1 else None]
        out[s] = d
    return out


def pooled_var(d):
    """Median wallet variance (5+ games). Wallet variances differ 25-fold (a longshot buyer vs a favourite buyer), so a
    mean would be set by the few high-variance wallets and be wrong for nearly everyone."""
    vs = sorted(v for n, m, v in d.values() if v is not None and n >= MIN_N_PRIOR)
    return vs[len(vs) // 2] if vs else None


def wallet_var(n, v, sp):
    return (K_VAR * sp + (n - 1) * v) / (K_VAR + n - 1) if v is not None and n > 1 else sp


def prior(d, sp):
    """m, tau^2 by DerSimonian-Laird on wallets with MIN_N_PRIOR+ games (the prior then applies to every wallet)."""
    xs = [(n, m, wallet_var(n, v, sp) / n) for n, m, v in d.values() if n >= MIN_N_PRIOR]
    if not xs:
        return 0.0, 0.0
    w = [1 / v for _, _, v in xs]
    sw = sum(w)
    mw = sum(wi * m for wi, (_, m, _) in zip(w, xs)) / sw
    q = sum(wi * (m - mw) ** 2 for wi, (_, m, _) in zip(w, xs))
    c = sw - sum(wi * wi for wi in w) / sw
    tau2 = max(0.0, (q - (len(xs) - 1)) / c) if c > 0 else 0.0
    wt = [1 / (v + tau2) for _, _, v in xs]
    return sum(wi * m for wi, (_, m, _) in zip(wt, xs)) / sum(wt), tau2


def fit(data):
    P = {}
    for s, d in data.items():
        sp = pooled_var(d)
        if sp is None:
            continue
        m, t2 = prior(d, sp)
        P[s] = {'m': m, 'tau2': t2, 'sigma2': sp, 'wallets': len(d)}
    return P


def estimate_rho(data, P, wallets=None):
    """Ratio estimator: E[z_a z_b] = rho * c with z standardised by each sport's total variance."""
    num = den = 0.0
    k = 0
    for w in (wallets if wallets is not None else set().union(*[set(d) for d in data.values()])):
        zs = []
        for s, d in data.items():
            a = d.get(w)
            if a and s in P and a[0] >= MIN_N_RHO and P[s]['tau2'] > 0:
                v = wallet_var(a[0], a[2], P[s]['sigma2']) / a[0]
                tot = P[s]['tau2'] + v
                zs.append(((a[1] - P[s]['m']) / math.sqrt(tot), math.sqrt(P[s]['tau2'] / tot)))
        for i in range(len(zs)):
            for j in range(i + 1, len(zs)):
                num += zs[i][0] * zs[j][0]
                den += zs[i][1] * zs[j][1]
                k += 1
    return (max(0.0, min(0.95, num / den)) if den else 0.0), k


def rho_ci(data, P, rho_pt, B=200, seed=1):
    ws = sorted(set().union(*[set(d) for d in data.values()]))
    rnd = random.Random(seed)
    r = []
    for _ in range(B):
        samp = [rnd.choice(ws) for _ in ws]
        r.append(estimate_rho(data, P, samp)[0])
    r.sort()
    return [round(r[int(0.05 * B)], 3), round(r[int(0.95 * B) - 1], 3)]


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        for r in range(i + 1, n):
            f = M[r][i] / M[i][i]
            for c in range(i, n + 1):
                M[r][c] -= f * M[i][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][c] * x[c] for c in range(i + 1, n))) / M[i][i]
    return x


def posterior(obs, target, P, rho):
    """obs {sport: (n, mean, var)}; returns (mean, sd) of the target sport's skill given all observed sports."""
    pt = P[target]
    O = [s for s in obs if s in P]
    if not O or pt['tau2'] <= 0:
        return pt['m'], math.sqrt(pt['tau2'])
    tau = {s: math.sqrt(P[s]['tau2']) for s in P}

    def cov(a, b):
        return P[a]['tau2'] if a == b else rho * tau[a] * tau[b]
    A = [[cov(a, b) + (wallet_var(obs[a][0], obs[a][2], P[a]['sigma2']) / obs[a][0] if a == b else 0.0) for b in O] for a in O]
    k = [cov(target, a) for a in O]
    y = [obs[a][1] - P[a]['m'] for a in O]
    x = solve(A, y)
    mean = pt['m'] + sum(ki * xi for ki, xi in zip(k, x))
    z = solve(A, k)
    var = max(pt['tau2'] - sum(ki * zi for ki, zi in zip(k, z)), 0.0)
    return mean, math.sqrt(var)


def p_pos(mean, sd):
    if sd <= 0:
        return 1.0 if mean > 0 else 0.0
    return 0.5 * math.erfc(-mean / (sd * math.sqrt(2)))


def tier_of(p):
    if p <= DULL_P:
        return 'dull'
    return next((t for t, c in TIERS if p >= c), None)


def old_labels(root=ROOT):
    """The scorecards' hard t >= 3 labels, for comparison: {wallet: 'sharp:<sport>' | 'dull'}. NBA record wins, as in sharp.wallets()."""
    lab = {}
    for s in ('nba', 'nfl', 'cfb'):
        try:
            j = json.load(open(os.path.join(root, 'data', FILES[s])))
        except (OSError, ValueError):
            continue
        for w in j.get('dull') or []:
            lab.setdefault(w, 'dull')
        for w in j.get('sharp') or []:
            if w not in lab:
                lab[w] = 'sharp:' + s
    return lab


def rank(data, P, rho, target, old=None):
    out = {}
    for w in set().union(*[set(d) for d in data.values()]):
        obs = {s: tuple(d[w]) for s, d in data.items() if w in d and s in P}
        if sum(a[0] for a in obs.values()) < 3 or target not in P:
            continue
        m, sd = posterior(obs, target, P, rho)
        p = p_pos(m, sd)
        out[w] = {'raw': {s: [a[0], round(a[1], 4)] for s, a in obs.items()}, 'post': round(m, 4), 'sd': round(sd, 4), 'p': round(p, 3), 'tier': tier_of(p), 'old': (old or {}).get(w)}
    return out


def holdout(data, P, rho, target='nba', min_n=1):
    """Rank `target` skill from the OTHER sports only; report the target record those wallets actually have, by tier."""
    others = {s: d for s, d in data.items() if s != target}
    Po = {s: v for s, v in P.items() if s != target}
    P2 = dict(Po)
    P2[target] = P[target]
    rows = []
    for w, a in data.get(target, {}).items():
        if a[0] < min_n:
            continue
        obs = {s: tuple(d[w]) for s, d in others.items() if w in d and d[w][0] >= 1 and s in Po}
        if not obs:
            continue
        m, sd = posterior(obs, target, P2, rho)
        nfl = obs.get('nfl')
        rows.append({'n': a[0], 'y': a[1], 'p': p_pos(m, sd), 'post': m, 'raw': (nfl[1] if nfl else None),
                     't': (nfl[1] / math.sqrt(nfl[2] / nfl[0]) if nfl and nfl[2] and nfl[0] >= 2 else None), 'nn': sum(x[0] for x in obs.values())})
    sig = math.sqrt(P[target]['sigma2'])

    def grp(sel, name):
        r = [x for x in rows if sel(x)]
        N = sum(x['n'] for x in r)
        return {'group': name, 'wallets': len(r), 'nba_games': N, 'mean': round(sum(x['n'] * x['y'] for x in r) / N, 4) if N else None,
                'se': round(sig / math.sqrt(N), 4) if N else None}
    res = [grp(lambda x: True, 'all wallets with NBA and other-sport data')]
    for t, c in TIERS:
        res.append(grp(lambda x, c=c: x['p'] >= c, f'posterior p >= {c} ({t}+)'))
    res.append(grp(lambda x: x['p'] <= DULL_P, f'posterior p <= {DULL_P} (dull)'))
    res.append(grp(lambda x: x['t'] is not None and x['t'] >= 3 and x['nn'] >= 10, 'old rule: other-sport t >= 3'))
    return res


def main(argv):
    target = next((a.split('=')[1] for a in argv if a.startswith('--sport=')), 'nba')
    data = load()
    P = fit(data)
    rho, k = estimate_rho(data, P)
    rho = float(next((a.split('=')[1] for a in argv if a.startswith('--rho=')), rho))   # sensitivity runs only; the weekly job never passes it
    ci = rho_ci(data, P, rho)
    R = rank(data, P, rho, target, old_labels())
    ho = holdout(data, P, rho, target)
    n_t = {}
    for v in R.values():
        n_t[str(v['tier'])] = n_t.get(str(v['tier']), 0) + 1
    out = {'generated': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(timespec='seconds'), 'target': target,
           'unit': 'mean closing-line value per game (relative), as in the scorecards', 'tiers': {t: c for t, c in TIERS} | {'dull': DULL_P},
           'params': {s: {k2: round(v, 6) if isinstance(v, float) else v for k2, v in p.items()} for s, p in P.items()},
           'rho': {'value': round(rho, 3), 'ci90': ci, 'pairs': k}, 'counts': n_t, 'holdout': ho,
           'wallets': dict(sorted(R.items(), key=lambda kv: -kv[1]['p']))}
    if '--dry' in argv:
        print(json.dumps({k2: v for k2, v in out.items() if k2 != 'wallets'}, indent=1))
        for w, v in list(out['wallets'].items())[:15]:
            print(w[:10], v)
        return
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    print(f'wrote {OUT}: {len(R)} wallets, tiers {n_t}, rho {rho:.2f} {ci} on {k} pairs')


if __name__ == '__main__':
    main(sys.argv[1:])
