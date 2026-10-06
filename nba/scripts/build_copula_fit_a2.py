#!/usr/bin/env python3
"""
Game Simulation v2, step A2: the corrected dependence test in docs/copula-fit-a2.md.

  python3 nba/scripts/build_copula_fit_a2.py --freeze   fit on 2024-25 + 2025-26 (opening prices) and write data/copula_frozen.json
                                                         and docs/copula-freeze.md. Commit before the first 2026-27 regular-season tip.
  python3 nba/scripts/build_copula_fit_a2.py --check    verify the committed freeze (commit time vs the first tip, file unchanged)

The holdout test (--test) is written once regular-season games have settled; it refuses to run unless --check passes.
"""
import hashlib, json, math, os, subprocess, sys
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_copula_fit as C

ROOT = os.path.join(HERE, '..')
FROZEN = os.path.join(ROOT, 'data', 'copula_frozen.json')
ND = NormalDist()
GATE_PTS = 0.005          # after the shift, mean(over hit - p') must be within 0.5 points of zero, per stat
FIRST_TIP_UTC = '2026-10-20T23:00:00+00:00'   # fallback; test mode reads the real first regular-season tip from nba-data


def shift_fit(legs_s):
    """b minimizing the log loss of outcomes under p' = Phi(Phi^-1(p) - b)"""
    z = [(ND.inv_cdf(p), y) for p, y in legs_s]

    def loss(b):
        t = 0.0
        for h, y in z:
            q = min(max(ND.cdf(h - b), 1e-9), 1 - 1e-9)
            t -= math.log(q if y else 1 - q)
        return t
    lo, hi, gr = -0.6, 0.6, (math.sqrt(5) - 1) / 2
    a, b = hi - gr * (hi - lo), lo + gr * (hi - lo)
    fa, fb = loss(a), loss(b)
    for _ in range(50):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - gr * (hi - lo); fa = loss(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + gr * (hi - lo); fb = loss(b)
    return (lo + hi) / 2


def freeze():
    G = {}
    for s in (2025, 2026):
        G.update(C.legs(s, 'open'))
    by = defaultdict(list)
    for L in G.values():
        for a in L:
            by[a[2]].append((a[3], a[4]))
    b = {s: shift_fit(v) for s, v in by.items()}
    before = {s: sum(y - p for p, y in v) / len(v) for s, v in by.items()}
    after = {s: sum(y - ND.cdf(ND.inv_cdf(p) - b[s]) for p, y in v) / len(v) for s, v in by.items()}
    gate_ok = all(abs(x) <= GATE_PTS for x in after.values())
    # calibrated legs
    Gc = {gid: [(a[0], a[1], a[2], ND.cdf(ND.inv_cdf(a[3]) - b[a[2]]), a[4]) for a in L] for gid, L in G.items()}
    P = C.collect(Gc)
    fits = {}
    for f, games in P.items():
        rho, se = C.fit(games)
        fits[f] = {'n': sum(len(g) for g in games.values()), 'games': len(games), 'rho_hat': rho, 'se': se}
    tau2 = {}
    for rel in ('self', 'team', 'opp'):
        v = [x for f, x in fits.items() if f[0] == rel]
        tau2[rel] = max(0.0, sum(x['rho_hat'] ** 2 for x in v) / len(v) - sum(x['se'] ** 2 for x in v) / len(v))
    fams = []
    for f, x in sorted(fits.items()):
        t2 = tau2[f[0]]
        w = t2 / (t2 + x['se'] ** 2) if t2 + x['se'] ** 2 > 0 else 0.0
        fams.append({'rel': f[0], 'a': f[1], 'b': f[2], 'n': x['n'], 'games': x['games'], 'rho_hat': round(x['rho_hat'], 5), 'se': round(x['se'], 5),
                     'weight': round(w, 4), 'rho': round(x['rho_hat'] * w, 5)})
    body = {'rules': 'docs/copula-fit-a2.md', 'fit_seasons': ['2024-25', '2025-26'], 'games': len(G), 'legs': sum(len(v) for v in G.values()),
            'shift': {s: round(x, 5) for s, x in sorted(b.items())},
            'over_bias_before': {s: round(x, 5) for s, x in sorted(before.items())}, 'over_bias_after': {s: round(x, 5) for s, x in sorted(after.items())},
            'gate_ok': gate_ok, 'tau2': {k: round(v, 6) for k, v in tau2.items()}, 'families': fams}
    body['fingerprint'] = hashlib.sha256(json.dumps({k: body[k] for k in ('shift', 'families')}, sort_keys=True).encode()).hexdigest()
    return body


def write(body):
    json.dump(body, open(FROZEN, 'w'), indent=1)
    L = ['# Game Simulation v2, step A2: frozen model', '', 'Rules: docs/copula-fit-a2.md. Fitted on 2024-25 and 2025-26 opening prices and frozen before the 2026-27 holdout exists. '
         'The numbers below are the whole model; `data/copula_frozen.json` is the file the test checks.', '',
         f"- Fit set: {body['games']} games, {body['legs']:,} legs. Fingerprint `{body['fingerprint'][:16]}`.",
         f"- Fit-set gate (mean over hit minus price within 0.5 points after the shift, every stat): **{'passed' if body['gate_ok'] else 'FAILED, do not commit'}**.", '',
         '| Stat | Shift b | Over bias before | After |', '|---|---|---|---|']
    for s in body['shift']:
        L.append(f"| {C.SL[s]} | {body['shift'][s]:+.3f} | {body['over_bias_before'][s] * 100:+.1f} pts | {body['over_bias_after'][s] * 100:+.1f} pts |")
    L += ['', f"Spread of true correlations by group (tau^2): same player {body['tau2']['self']:.5f}, teammates {body['tau2']['team']:.5f}, opponents {body['tau2']['opp']:.5f}.", '',
          '| Family | Pairs | rho hat | SE | Weight | Frozen rho |', '|---|---|---|---|---|---|']
    for f in sorted(body['families'], key=lambda f: -abs(f['rho'])):
        L.append(f"| {C.name((f['rel'], f['a'], f['b']))} | {f['n']:,} | {f['rho_hat']:+.3f} | {f['se']:.3f} | {f['weight']:.2f} | {f['rho']:+.3f} |")
    open(os.path.join(ROOT, 'docs', 'copula-freeze.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


def check():
    rel = 'nba/data/copula_frozen.json'
    repo = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--', rel], capture_output=True, text=True, cwd=repo).stdout.strip()
    ts = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', rel], capture_output=True, text=True, cwd=repo).stdout.strip()
    if not ts or dirty:
        print('FAIL: the frozen file is not committed unchanged'); return False
    from datetime import datetime
    first = datetime.fromisoformat(FIRST_TIP_UTC).timestamp()
    ok = int(ts) < first
    print(('OK' if ok else 'FAIL') + f': last commit of {rel} at {datetime.utcfromtimestamp(int(ts)).isoformat()}Z, first tip {FIRST_TIP_UTC}')
    return ok


if __name__ == '__main__':
    if '--freeze' in sys.argv:
        write(freeze())
    elif '--check' in sys.argv:
        sys.exit(0 if check() else 1)
    elif '--test' in sys.argv:
        sys.exit('The holdout test is written once regular-season games have settled; it will refuse to run unless --check passes.')
    else:
        sys.exit(__doc__)
