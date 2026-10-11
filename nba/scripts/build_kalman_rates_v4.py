#!/usr/bin/env python3
"""
Rates v4 candidate: swap rates v3's volume EWMAs for a local-level Kalman filter (talent = random walk, each game a
noisy observation whose noise shrinks with minutes). Percentages (2P%, 3P%, FT%) keep v3's decayed makes + prior
attempts, which is already a shrinkage estimator. Everything else is v3's harness unchanged: same tune/test seasons
(2022-24 / 2025-26), same position-average prior, scored given TRUE minutes so only the per-minute rates move.

Per component c and player: state mean m, variance P (per-minute rate)
  start    m = position average, P0 = r / 240           (about v3's 8-game warm-up at 30 minutes)
  new szn  P += qoff                                     (offseason drift)
  game     P += q;  K = P / (P + r / minutes);  m += K (y - m);  P *= (1 - K)
(q, r, qoff) are chosen per component on the tune seasons from a grid scaled by the component's variance.

  python3 nba/scripts/build_kalman_rates_v4.py
Writes data/rates_v4_candidate.json and docs/rates-v4-kalman.md. Pre-registered pass rule: lower test RMSE than v3 on
at least 3 of 4 stats AND no stat worse by more than 0.2%.
"""
import itertools, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_rates_v3 as BR

SEASONS, TUNE, TEST = BR.SEASONS, BR.TUNE, BR.TEST
VOL, PCT = BR.VOL, BR.PCT
Q_F, R_F, QO_F = (0.0003, 0.001, 0.004, 0.012), (3.0, 8.0, 15.0, 50.0), (0.01, 0.05, 0.2)
GRID = list(itertools.product(Q_F, R_F, QO_F))
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'rates_v4_candidate.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'rates-v4-kalman.md')
P0_DIV = 240.0


def kupdate(m, P, y, mins, q, r):
    P += q
    K = P / (P + r / mins)
    return m + K * (y - m), P * (1 - K)


class KRates(BR.Rates):
    """v3's Rates with Kalman volume components. alpha = {comp: (q, r, qoff)}."""

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
                v = {c: self.prior_rate(pos, c) for c in VOL}
                p = self.pl[aid] = {'n': 0, 'pos': pos, 'v': v, 'mk': {c: 0.0 for c in PCT}, 'at': {c: 0.0 for c in PCT},
                                    'P': {c: self.alpha[c][1] / P0_DIV for c in VOL}, 'szn': r.get('season')}
            for c, f in VOL.items():
                q, rr, qo = self.alpha[c]
                if r.get('season') != p['szn']:
                    p['P'][c] += qo
                p['v'][c], p['P'][c] = kupdate(p['v'][c], p['P'][c], f(r) / m, m, q, rr)
            p['szn'] = r.get('season')
            for c, (mk, at) in PCT.items():
                d = self.pct[c][0]
                p['mk'][c] = p['mk'][c] * (1 - d) + mk(r)
                p['at'][c] = p['at'][c] * (1 - d) + at(r)
            p['n'] += 1


def tune_kalman(box):
    """Per volume component, pick (q, r, qoff) minimising squared error of m * rate on tune seasons (given true minutes)."""
    # scale: variance of per-minute rate across player-games
    sums = {c: [0.0, 0.0, 0.0] for c in VOL}
    for g in C.games(SEASONS[:3]):
        for r in box.get(g['game_id'], []):
            if r['played'] and r['minutes'] >= 4:
                for c, f in VOL.items():
                    x = f(r) / r['minutes']
                    s = sums[c]
                    s[0] += 1; s[1] += x; s[2] += x * x
    var = {c: s[2] / s[0] - (s[1] / s[0]) ** 2 for c, s in sums.items()}
    st = {}
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    err = {c: [0.0] * len(GRID) for c in VOL}
    n = 0
    for g in C.games(SEASONS[:3]):
        for r in box.get(g['game_id'], []):
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m, pos = r['athlete_id'], r['minutes'], MM.group(r['pos'])
            p = st.get(aid)
            if p and g['season'] in TUNE and p['n'] >= 5:
                n += 1
                for c, f in VOL.items():
                    y = f(r)
                    for i, (m_, _) in enumerate(p['s'][c]):
                        err[c][i] += (m * m_ - y) ** 2
            for c, f in VOL.items():
                prior[pos][c][0] += f(r)
                prior[pos][c][1] += m
            if p is None:
                p = st[aid] = {'n': 0, 'szn': g['season'],
                               's': {c: [(prior[pos][c][0] / prior[pos][c][1], GRID[i][1] * var[c] / P0_DIV) for i in range(len(GRID))] for c in VOL}}
            newszn = g['season'] != p['szn']
            for c, f in VOL.items():
                x = f(r) / m
                row = p['s'][c]
                for i, (qf, rf, qof) in enumerate(GRID):
                    mm, PP = row[i]
                    if newszn:
                        PP += qof * var[c]
                    row[i] = kupdate(mm, PP, x, m, qf * var[c], rf * var[c])
            p['szn'] = g['season']
            p['n'] += 1
    best = {}
    for c in VOL:
        i = min(range(len(GRID)), key=lambda i: err[c][i])
        qf, rf, qof = GRID[i]
        best[c] = (qf * var[c], rf * var[c], qof * var[c])
        print(f'  {c:5s} tuned q={qf} r={rf} qoff={qof} (x var)   tune RMSE {math.sqrt(err[c][i] / n):.4f}', flush=True)
    return best


def main():
    box = C.player_games(SEASONS)
    for g in C.games(SEASONS):                       # stamp each row with its season (the offseason gap needs it)
        for r in box.get(g['game_id'], []):
            r['season'] = g['season']
    alpha_v3, pct, _ = BR.tune(box)
    print('v3 learning rates', alpha_v3, flush=True)
    base = BR.evaluate(box, alpha_v3, pct)
    print('tuning Kalman on', TUNE, flush=True)
    kp = tune_kalman(box)
    BR.Rates = KRates
    kal = BR.evaluate(box, kp, pct)
    stats = list(base)
    L = ['# Rates v4 candidate: Kalman volume rates vs rates v3', '',
         f'Tuned on {TUNE}, tested on {TEST} (given true minutes). v1 = one EWMA; v3 = per-component EWMA; v4 = v3 with Kalman volume.', '',
         '| Stat | Player-games | RMSE v1 | RMSE v3 | RMSE v4 | v4 vs v3 | MAE v3 | MAE v4 | Bias v3 | Bias v4 |', '|---|---|---|---|---|---|---|---|---|---|']
    wins = worse = 0
    for s in stats:
        v3, v4 = base[s]['v3'], kal[s]['v3']
        gain = 100 * (1 - v4['rmse'] / v3['rmse'])
        wins += gain > 0
        worse += gain < -0.2
        L.append(f"| {s} | {base[s]['n']:,} | {base[s]['v1']['rmse']:.4f} | {v3['rmse']:.4f} | {v4['rmse']:.4f} | {gain:+.2f}% | {v3['mae']:.4f} | {v4['mae']:.4f} | {v3['bias']:+.4f} | {v4['bias']:+.4f} |")
    verdict = 'PASS' if wins >= 3 and worse == 0 else 'FAIL'
    L += ['', f'Pre-registered rule: v4 beats v3 on >= 3 of 4 stats and no stat is worse by more than 0.2%. Result: **{verdict}** ({wins} of 4 better, {worse} materially worse).', '']
    open(OUT_MD, 'w').write('\n'.join(L))
    json.dump({'verdict': verdict, 'kalman': {c: dict(q=v[0], r=v[1], qoff=v[2]) for c, v in kp.items()}, 'v3': base, 'v4': kal},
              open(OUT_JSON, 'w'), indent=1)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
