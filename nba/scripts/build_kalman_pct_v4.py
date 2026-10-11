#!/usr/bin/env python3
"""
Rates v4, step 2: Kalman filter on the shooting PERCENTAGES (2P%, 3P%, FT%), plus a paired significance test.

v3 estimates a percentage as decayed makes plus k attempts at the position average. Here the percentage is a talent
that drifts as a random walk; each game is a binomial observation (noise p(1-p)/attempts), so a 12-attempt night
moves the estimate less than a 25-attempt night by construction.
  start    m = position average so far, P0 = p(1-p) / k0
  new szn  P += qoff
  game     P += q;  K = P / (P + p(1-p)/att);  m += K (made/att - m);  P *= (1 - K)
(q, qoff, k0) per percentage are chosen on the tune seasons by held-out log-likelihood (same criterion as v3).

Four models are scored on the same player-games (2025-26, given TRUE minutes), so the errors pair up:
  v3        EWMA volume + decayed-makes percentages
  vol_k     Kalman volume (build_kalman_rates_v4.py) + v3 percentages
  pct_k     v3 volume + Kalman percentages
  both_k    Kalman volume + Kalman percentages
Paired t-stat = mean(e_v3^2 - e_model^2) / its standard error. Pass rule (set before running): a model beats v3 on >= 3 of
4 stats, none worse by > 0.2% RMSE, AND |t| >= 2 on at least 2 stats.

  python3 nba/scripts/build_kalman_pct_v4.py
Writes docs/rates-v4-kalman-pct.md.
"""
import itertools, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_rates_v3 as BR
import build_kalman_rates_v4 as KV

SEASONS, TUNE, TEST = BR.SEASONS, BR.TUNE, BR.TEST
VOL, PCT, V1_STATS = BR.VOL, BR.PCT, BR.V1_STATS
Q_G, QO_G, K0_G = (0.0, 2e-5, 1e-4, 5e-4, 2e-3), (0.0, 2e-4, 1e-3, 4e-3), (25, 50, 100, 200)
GRID = list(itertools.product(Q_G, QO_G, K0_G))
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'rates-v4-kalman-pct.md')
PMIN, PMAX = 0.03, 0.97


def pupdate(m, P, M, A, q, qoff_pending):
    """One binomial Kalman step; returns (m, P)."""
    P += q + qoff_pending
    p = min(PMAX, max(PMIN, m))
    K = P / (P + p * (1 - p) / A)
    return m + K * (M / A - m), P * (1 - K)


class Model(BR.Rates):
    """v3 Rates with switchable Kalman volume (alpha[c] = (q, r, qoff)) and/or Kalman percentages (pk[c] = (q, qoff, k0))."""

    def __init__(self, alpha, pct, vol_k=False, pk=None):
        super().__init__(alpha, pct)
        self.vol_k, self.pk = vol_k, pk

    def comps(self, aid):
        out = super().comps(aid)
        if out and self.pk:
            for c in PCT:
                out[c] = self.pl[aid]['pm'][c]
        return out

    def update(self, rows):
        for r in rows:
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m, pos = r['athlete_id'], r['minutes'], MM.group(r['pos'])
            for c, f in VOL.items():
                self.prior[pos][c][0] += f(r)
                self.prior[pos][c][1] += m
            for c, (mk, at) in PCT.items():
                self.prior[pos][c][0] += mk(r)
                self.prior[pos][c][1] += at(r)
            p = self.pl.get(aid)
            if p is None:
                p = self.pl[aid] = {'n': 0, 'pos': pos, 'szn': r.get('season'),
                                    'v': {c: self.prior_rate(pos, c) for c in VOL},
                                    'mk': {c: 0.0 for c in PCT}, 'at': {c: 0.0 for c in PCT},
                                    'P': {c: (self.alpha[c][1] / KV.P0_DIV if self.vol_k else 0.0) for c in VOL},
                                    'pm': {c: self.prior_pct(pos, c) for c in PCT},
                                    'pP': {c: (0.0) for c in PCT}}
                if self.pk:
                    for c in PCT:
                        pr = p['pm'][c]
                        p['pP'][c] = pr * (1 - pr) / self.pk[c][2]
            new_szn = r.get('season') != p['szn']
            for c, f in VOL.items():
                if self.vol_k:
                    q, rr, qo = self.alpha[c]
                    if new_szn:
                        p['P'][c] += qo
                    p['v'][c], p['P'][c] = KV.kupdate(p['v'][c], p['P'][c], f(r) / m, m, q, rr)
                else:
                    w = min(1.0, m / 20.0)
                    a = max(self.alpha[c], 1 / (p['n'] + 1 + BR.PRIOR_GAMES))
                    p['v'][c] += a * w * (f(r) / m - p['v'][c])
            for c, (mk, at) in PCT.items():
                M, A = mk(r), at(r)
                d = self.pct[c][0]
                p['mk'][c] = p['mk'][c] * (1 - d) + M
                p['at'][c] = p['at'][c] * (1 - d) + A
                if self.pk and A > 0:
                    q, qo, _ = self.pk[c]
                    p['pm'][c], p['pP'][c] = pupdate(p['pm'][c], p['pP'][c], M, A, q, qo if new_szn else 0.0)
            p['szn'] = r.get('season')
            p['n'] += 1


def tune_pct(box):
    """Per percentage, the (q, qoff, k0) maximising held-out binomial log-likelihood on the tune seasons."""
    st, prior = {}, defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    ll = {c: [0.0] * len(GRID) for c in PCT}
    for g in C.games(SEASONS[:3]):
        for r in box.get(g['game_id'], []):
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, pos = r['athlete_id'], MM.group(r['pos'])
            p = st.get(aid)
            for c, (mk, at) in PCT.items():
                A, M = at(r), mk(r)
                if A <= 0:
                    continue
                pr = prior[pos][c][0] / prior[pos][c][1] if prior[pos][c][1] else 0.4
                if p is None:
                    p = st[aid] = {'szn': g['season'], 'n': 0, 's': {}}
                row = p['s'].get(c)
                if row is None:
                    row = p['s'][c] = [(pr, pr * (1 - pr) / GRID[i][2]) for i in range(len(GRID))]
                new = g['season'] != p['szn']
                if g['season'] in TUNE and p['n'] >= 5:
                    for i in range(len(GRID)):
                        qq = min(0.999, max(0.001, row[i][0]))
                        ll[c][i] += M * math.log(qq) + (A - M) * math.log(1 - qq)
                for i, (q, qo, _) in enumerate(GRID):
                    row[i] = pupdate(row[i][0], row[i][1], M, A, q, qo if new else 0.0)
            for c, (mk, at) in PCT.items():
                prior[pos][c][0] += mk(r)
                prior[pos][c][1] += at(r)
            if p:
                p['szn'] = g['season']
                p['n'] += 1
    best = {}
    for c in PCT:
        i = max(range(len(GRID)), key=lambda i: ll[c][i])
        best[c] = GRID[i]
        print(f'  {c:3s} tuned q={GRID[i][0]} qoff={GRID[i][1]} k0={GRID[i][2]}', flush=True)
    return best


def evaluate(box, models):
    """Per-player-game squared errors for each model on TEST, aligned across models. Returns {model: {stat: [e^2,...]}}."""
    err = {k: defaultdict(list) for k in models}
    seen = defaultdict(int)
    for g in C.games(SEASONS):
        rows = box.get(g['game_id'], [])
        if g['season'] == TEST:
            for r in rows:
                if not r['played'] or r['minutes'] <= 0 or seen[r['athlete_id']] < 5:
                    continue
                m = r['minutes']
                for k, M in models.items():
                    s3 = M.stat_rates(r['athlete_id'])
                    if not s3:
                        break
                else:
                    for k, M in models.items():
                        s3 = M.stat_rates(r['athlete_id'])
                        for s, cols in V1_STATS.items():
                            err[k][s].append((m * s3[s] - sum(r[c] for c in cols)) ** 2)
        for M in models.values():
            M.update(rows)
        for r in rows:
            if r['played'] and r['minutes'] > 0:
                seen[r['athlete_id']] += 1
    return err


def main():
    box = C.player_games(SEASONS)
    for g in C.games(SEASONS):
        for r in box.get(g['game_id'], []):
            r['season'] = g['season']
    alpha_v3, pct, _ = BR.tune(box)
    print('tuning Kalman volume', flush=True)
    kv = KV.tune_kalman(box)
    print('tuning Kalman percentages', flush=True)
    pk = tune_pct(box)
    models = {'v3': Model(alpha_v3, pct), 'vol_k': Model(kv, pct, vol_k=True),
              'pct_k': Model(alpha_v3, pct, pk=pk), 'both_k': Model(kv, pct, vol_k=True, pk=pk)}
    err = evaluate(box, models)
    stats = list(V1_STATS)
    L = [f'# Rates v4 step 2: Kalman percentages, with paired significance', '',
         f'Tuned on {TUNE}, tested on {TEST}, given true minutes. t = paired mean(e_v3^2 - e_model^2) / s.e.; |t| >= 2 is real.', '',
         '| Stat | n | RMSE v3 | vol_k | pct_k | both_k | t vol_k | t pct_k | t both_k |', '|---|---|---|---|---|---|---|---|---|']
    summary = {k: [0, 0, 0, 0] for k in ('vol_k', 'pct_k', 'both_k')}        # better, materially worse, t>=2, stats affected
    for s in stats:
        base = err['v3'][s]
        n = len(base)
        row = [s, f'{n:,}', f'{math.sqrt(sum(base) / n):.4f}']
        ts = []
        for k in ('vol_k', 'pct_k', 'both_k'):
            e = err[k][s]
            rm = math.sqrt(sum(e) / n)
            d = [b - x for b, x in zip(base, e)]
            sd = statistics.stdev(d)
            t = statistics.mean(d) / (sd / math.sqrt(n)) if sd > 0 else 0.0     # sd 0: model leaves this stat untouched
            gain = 100 * (1 - rm / math.sqrt(sum(base) / n))
            summary[k][0] += gain > 0
            summary[k][1] += gain < -0.2
            summary[k][2] += t >= 2
            summary[k][3] += sd > 0
            row.append(f'{rm:.4f} ({gain:+.2f}%)')
            ts.append(f'{t:+.2f}')
        L.append('| ' + ' | '.join(row + ts) + ' |')
    L += ['', 'Pass rule: better than v3 on >= 3 of 4 stats, none worse by > 0.2%, and t >= 2 (better direction) on >= 2 stats.',
          'Amended before reading any result, after the first run crashed: pct_k only changes points and 3PM (rebounds and assists',
          'are identical by construction), so for pct_k the rule is: better on both affected stats, none worse, t >= 2 on at least one.', '']
    for k, (b, w, tt, aff) in summary.items():
        ok = (b == 2 and w == 0 and tt >= 1) if aff == 2 else (b >= 3 and w == 0 and tt >= 2)
        L.append(f'- **{k}**: better on {b} of {aff} affected stats, materially worse on {w}, significant on {tt} -> **{"PASS" if ok else "FAIL"}**')
    L.append('')
    open(OUT_MD, 'w').write('\n'.join(L))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
