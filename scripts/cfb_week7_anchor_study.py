#!/usr/bin/env python3
"""CFB week 7 retro, the finding that explains our picks: 80 of our 2026 5+ picks were almost entirely PRIOR-led. For the average 5+ pick the preseason prior sat 10.6 points from the line and the
in-season move (live minus prior-only) pointed 2.1 the other way. And the final margin does not follow the prior at all: final minus close regressed on (prior minus close) and the in-season move
gives weights -0.02 and +0.28 in 2026. The information is in how teams have performed this season, not in where the preseason model disagrees with the market.

Candidate: a market-anchored number that discounts the prior disagreement and keeps the in-season move:   pred = close + a * (prior_only - close) + b * (live - prior_only)
(live: a = 1, b = 1 gives the live number; the live model is NOT this form, so a = 1, b = 1 is only a reference row).
Pre-registered: a in (0, 0.1, 0.2, 0.3, 0.5, 1.0), b in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5); both chosen on 2022-23 by the AVERAGE MISS only, then read once on 2024-25 and on 2026 weeks 4-7.
Picks: 5+ from the close (a pick needs |pred - close| >= 5 is meaningless once the form is anchored, so picks are compared at the SAME COUNT as the live 5+ rule, largest |pred - close|), and at
the same count among picks the live rule makes too ("overlap"). Graded vs the ESPN close and open, pushes dropped. The open grade uses the open as the anchor in the same way.
Run: python3 scripts/cfb_week7_anchor_study.py --dir /tmp/cfbstudy   (needs cause_rows.csv)
"""
import argparse, itertools, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfb_week7_study import rec, fmt

AS = (0.0, 0.1, 0.2, 0.3, 0.5, 1.0); BS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    q = pd.read_csv(os.path.join(a.dir, 'cause_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    q['open'] = q.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan); q = q.dropna(subset=['mkt']).copy()
    tune = q.season.isin([2022, 2023]); groups = (('tune 22-23', tune), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    def anchored(al, b, ln, s=q): return s[ln] + al * (s.p0 - s[ln]) + b * s.move
    res = sorted((float((q[tune].hm - anchored(al, b, 'mkt', q[tune])).abs().mean()), al, b) for al, b in itertools.product(AS, BS))
    print('best 5 on 2022-23 by miss:'); [print('  miss %.3f a %.1f b %.2f' % r) for r in res[:5]]
    _, al, b = res[0]; q['anc'] = anchored(al, b, 'mkt'); q['anc_open'] = anchored(al, b, 'open')
    print('\nchosen a %.1f b %.2f' % (al, b))
    for lab, m in groups:
        s = q[m]; print('  %-11s miss live %.3f | anchored %.3f | close %.3f' % (lab, (s.hm - s.v2st).abs().mean(), (s.hm - s.anc).abs().mean(), (s.hm - s.mkt).abs().mean()))
    for ln, col in (('mkt', 'anc'), ('open', 'anc_open')):
        print('\n=== picks vs the ESPN %s, same count as the live 5+ rule ===' % ('close' if ln == 'mkt' else 'open'))
        for lab, m in groups:
            s = q[m].dropna(subset=[ln]); c = s.hm - s[ln]; el = s.v2st - s[ln]; n = int((el.abs() >= 5).sum()); ea = s[col] - s[ln]
            live = s[el.abs() >= 5]; idx = ea.abs().sort_values(ascending=False).index[:n]
            both = [i for i in idx if i in set(live.index) and np.sign(el[i]) == np.sign(ea[i])]; only_a = [i for i in idx if i not in set(live.index)]
            print('  %-11s n=%d  live %s | anchored %s | in both %s | anchored only %s' % (lab, n, fmt(rec(live, el[live.index], c[live.index])), fmt(rec(s.loc[idx], ea[idx], c[idx])), fmt(rec(s.loc[both], ea[both], c[both])), fmt(rec(s.loc[only_a], ea[only_a], c[only_a]))))
    print('\nby season vs close (same count): live -> anchored')
    for y in (2022, 2023, 2024, 2025, 2026):
        s = q[q.season == y]; c = s.hm - s.mkt; el = s.v2st - s.mkt; n = int((el.abs() >= 5).sum()); ea = s.anc - s.mkt; idx = ea.abs().sort_values(ascending=False).index[:n]; live = s[el.abs() >= 5]
        print('  %d n=%d %s -> %s' % (y, n, fmt(rec(live, el[live.index], c[live.index])), fmt(rec(s.loc[idx], ea[idx], c[idx]))))
    q.to_csv(os.path.join(a.dir, 'anchor_rows.csv'), index=False)


if __name__ == '__main__':
    sys.exit(main())
