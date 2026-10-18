#!/usr/bin/env python3
"""CFB week 7 retro: do any of the pick filters the 2026 misses suggest hold up on 2022-25? Every variant is fixed BEFORE the run, nothing is tuned.

Rows: <dir>/base_rows.csv (scripts/cfb_week7_base_rows.py, the live v2 + special teams model walk-forward) with ESPN opens from <dir>/opens_hist.json
(scripts/cfb_week7_fetch_opens.py). Weeks 4+, 5+ point disagreements, graded against the ESPN open and the ESPN close, pushes dropped.
Read: tune = 2022-23, test = 2024-25, then each season alone. The 2026 weeks 4-7 live board (data/cfb_scoreboard.json, 212 games) is the out-of-sample read.
A variant is only worth shipping if it beats the base rule on BOTH tune and test by more than 2 standard errors of the difference.

Variants (fixed in advance, from what the week 7 slate showed):
  base        |edge| >= 5                                   the live rule
  cap10       5 <= |edge| < 10                             huge disagreements are rating artifacts?
  cap8        5 <= |edge| < 8
  huge10      |edge| >= 10                                 the mirror: are the tails the whole signal?
  nofav21     base, and the game's line is under 21 points  big spreads are noisy in the margin
  p4only      base, and both teams are Power 4 / Notre Dame
  g5any       base, and at least one team is outside the Power 4
  pickfav     base, and the model's side is the favourite (it is MORE bullish on the favourite than the line)
  pickdog     base, and the model's side is the underdog (LESS bullish on the favourite)
  ens         |avg(v1, v2st) - line| >= 5                  the old and new model averaged
  wk6plus     base, weeks 6+ only                          more in-season data under the ratings
Run: python3 scripts/cfb_week7_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd

P4 = {'ACC', 'Big Ten', 'Big 12', 'SEC', 'FBS Independents'}      # Independents trimmed to Notre Dame below


def cp(w, n):
    from scipy.stats import beta
    if n == 0: return (None, None)
    return (beta.ppf(0.025, w, n - w + 1) if w else 0.0, beta.ppf(0.975, w + 1, n - w) if w < n else 1.0)


def rec(df, e, c):
    m = (c != 0) & df.index.isin(e.index); b = df[m]; w = int(((c[m] * np.sign(e[m])) > 0).sum()); n = int(m.sum()); lo, hi = cp(w, n)
    return w, n - w, (w / n if n else float('nan')), lo, hi


def fmt(r): return '%d-%d (%.1f%%)' % (r[0], r[1], r[2] * 100) if r[0] + r[1] else '-'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    t = pd.read_csv(os.path.join(a.dir, 'teams.csv'), encoding='latin-1')
    conf = dict(zip(t.team_id.astype(int), t.conference)); nm = dict(zip(t.team_id.astype(int), t.school if 'school' in t else t.nickname))
    def p4(i): return conf.get(i) in P4 and not (conf.get(i) == 'FBS Independents' and nm.get(i) != 'Notre Dame')
    d['hp4'] = d.home_id.map(p4); d['ap4'] = d.away_id.map(p4)
    d = d[d.week >= 4].copy()
    variants = {}
    def add(name, pred_col, line_col, mask_fn):
        variants[name] = (pred_col, line_col, mask_fn)
    out = []
    for line in ('open', 'mkt'):
        q = d.dropna(subset=[line]).copy(); q['e'] = q.v2st - q[line]; q['c'] = q.hm - q[line]; q['ens'] = (q.v1 + q.v2st) / 2; q['ee'] = q.ens - q[line]
        ae = q.e.abs(); base = ae >= 5
        fav_bull = np.sign(q.e) == np.sign(q[line])          # edge and line point the same way: the model's side is the favourite
        V = {'base': base, 'cap10': base & (ae < 10), 'cap8': base & (ae < 8), 'huge10': ae >= 10, 'nofav21': base & (q[line].abs() < 21),
             'p4only': base & q.hp4 & q.ap4, 'g5any': base & ~(q.hp4 & q.ap4), 'pickdog': base & ~fav_bull, 'pickfav': base & fav_bull, 'wk6plus': base & (q.week >= 6)}
        print('\n=== graded against the ESPN %s, weeks 4+, %d games ===' % ('open' if line == 'open' else 'close', len(q)))
        print('%-9s %-22s %-22s %-22s %s' % ('variant', 'tune 2022-23', 'TEST 2024-25', 'all 4 seasons', 'by season (22 23 24 25)'))
        for k in list(V) + ['ens']:
            if k == 'ens': e = q.ee; m = e.abs() >= 5
            else: e = q.e; m = V[k]
            row = []
            for ys in ([2022, 2023], [2024, 2025], [2022, 2023, 2024, 2025]):
                s = q[m & q.season.isin(ys)]; row.append(rec(s, e[s.index], q.c[s.index]))
            per = ' '.join('%d-%d' % rec(q[m & (q.season == y)], e[q[m & (q.season == y)].index], q.c[q[m & (q.season == y)].index])[:2] for y in (2022, 2023, 2024, 2025))
            print('%-9s %-22s %-22s %-22s %s' % (k, fmt(row[0]), fmt(row[1]), fmt(row[2]), per)); out.append(dict(line=line, variant=k, tune=row[0][:3], test=row[1][:3], all=row[2][:5]))
    # the 2026 live read, same filters, from the scoreboard (open only)
    sbp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cfb_scoreboard.json')
    if os.path.exists(sbp):
        g = pd.DataFrame(json.load(open(sbp))['games']); g['e'] = g.ours - g.open; g['c'] = g.actual - g.open; ae = g.e.abs(); b = ae >= 5
        fb = np.sign(g.e) == np.sign(g.open)
        L = {'base': b, 'cap10': b & (ae < 10), 'cap8': b & (ae < 8), 'huge10': ae >= 10, 'nofav21': b & (g.open.abs() < 21), 'pickdog': b & ~fb, 'pickfav': b & fb, 'wk6plus': b & (g.week >= 6)}
        print('\n=== 2026 live board, weeks 4-7, vs the open (%d games) ===' % len(g))
        for k, m in L.items(): print('%-9s %s' % (k, fmt(rec(g[m], g.e[m], g.c[m]))))
        for wk in (4, 5, 6, 7):
            for k in ('pickfav', 'pickdog'): m = L[k] & (g.week == wk); print('  week %d %-8s %s' % (wk, k, fmt(rec(g[m], g.e[m], g.c[m]))))
    json.dump(out, open(os.path.join(a.dir, 'week7_study_out.json'), 'w'), default=float)


if __name__ == '__main__':
    sys.exit(main())
