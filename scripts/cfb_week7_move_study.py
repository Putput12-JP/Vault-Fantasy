#!/usr/bin/env python3
"""CFB week 7 retro, candidate fix: the in-season update is too timid. The cause study found that the final margin keeps moving in the direction of (live minus prior-only): the slope is
+0.27 on 2022-23, +0.38 on 2024-25 and +0.58 in 2026. So split the margin in two and scale the parts separately:

    pred = hfa + cp * (prior_only - hfa) + cm * (live - prior_only)       hfa = 2.5 at a home site, 0 at a neutral one

Live is cp = cm = 1. Pre-registered: cp in 0.8..1.2 step 0.05 and cm in 0.8..2.0 step 0.1 are searched on 2022-23 by the AVERAGE MISS only (never by pick record), the pair is then read once on
2024-25 and on the 2026 weeks 4-7 live replay. Picks are compared at the same count as the live 5+ rule (largest |edge|) against the ESPN close and open, and per season.
Run: python3 scripts/cfb_week7_move_study.py --dir /tmp/cfbstudy   (needs cause_rows.csv from cfb_week7_cause_study.py)
"""
import argparse, itertools, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfb_week7_study import rec, fmt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    q = pd.read_csv(os.path.join(a.dir, 'cause_rows.csv')); hf = np.where(q.neutral, 0.0, 2.5); q['hf'] = hf
    tune = q.season.isin([2022, 2023])
    def pred(cp, cm, s=q): return s.hf + cp * (s.p0 - s.hf) + cm * (s.v2st - s.p0)
    res = sorted((float((q[tune].hm - pred(cp, cm, q[tune])).abs().mean()), cp, cm) for cp, cm in itertools.product(np.arange(0.8, 1.201, 0.05), np.arange(0.8, 2.001, 0.1)))
    print('best 5 on 2022-23 by miss:'); [print('  miss %.3f cp %.2f cm %.2f' % r) for r in res[:5]]
    for cp_only in (1.0,):
        r1 = min(r for r in res if abs(r[1] - cp_only) < 1e-9); print('best with cp fixed at 1.0: miss %.3f cm %.2f' % (r1[0], r1[2]))
    _, cp, cm = res[0]; q['new'] = pred(cp, cm); q['cm_only'] = pred(1.0, min(r for r in res if abs(r[1] - 1.0) < 1e-9)[2])
    groups = (('tune 22-23', tune), ('TEST 24-25', q.season.isin([2024, 2025])), ('2026 wk4-7', q.season == 2026))
    print('\nchosen cp %.2f cm %.2f' % (cp, cm))
    for lab, m in groups:
        s = q[m]; print('  %-11s miss live %.3f | new %.3f | cm-only %.3f | close %.3f | sd of edge vs close: live %.1f new %.1f' % (lab, (s.hm - s.v2st).abs().mean(), (s.hm - s.new).abs().mean(), (s.hm - s.cm_only).abs().mean(), (s.hm - s.mkt).abs().mean(), (s.v2st - s.mkt).std(), (s.new - s.mkt).std()))
    for ln in ('mkt', 'open'):
        print('\n=== 5+ rule, graded vs the ESPN %s; "matched" = same count as live 5+ ===' % ('close' if ln == 'mkt' else 'open'))
        for lab, m in groups:
            s = q[m].dropna(subset=[ln]); c = s.hm - s[ln]; row = []; n = int(((s.v2st - s[ln]).abs() >= 5).sum())
            for k in ('v2st', 'new', 'cm_only'):
                e = s[k] - s[ln]; sel = s[e.abs() >= 5]; idx = e.abs().sort_values(ascending=False).index[:n]
                row.append('%s: 5+ %s | matched %s' % (k, fmt(rec(sel, e[sel.index], c[sel.index])), fmt(rec(s.loc[idx], e[idx], c[idx]))))
            print('  %-11s n=%d  %s' % (lab, n, '\n              '.join(row)))
    print('\nby season, 5+ vs close, live -> new (miss live -> new)')
    for y in (2022, 2023, 2024, 2025, 2026):
        s = q[q.season == y].dropna(subset=['mkt']); c = s.hm - s.mkt; row = []
        for k in ('v2st', 'new'):
            e = s[k] - s.mkt; sel = s[e.abs() >= 5]; row.append(fmt(rec(sel, e[sel.index], c[sel.index])))
        print('  %d %s -> %s   (%.2f -> %.2f)' % (y, row[0], row[1], (s.hm - s.v2st).abs().mean(), (s.hm - s.new).abs().mean()))
    s = q[q.week >= 4]; s26 = q[(q.season == 2026) & (q.week == 7)]; print('\n2026 week 7 only: miss live %.2f new %.2f close %.2f' % ((s26.hm - s26.v2st).abs().mean(), (s26.hm - s26.new).abs().mean(), (s26.hm - s26.mkt).abs().mean()))
    q.to_csv(os.path.join(a.dir, 'move_rows.csv'), index=False)


if __name__ == '__main__':
    sys.exit(main())
