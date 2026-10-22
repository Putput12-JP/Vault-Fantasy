#!/usr/bin/env python3
"""CFB week 7 retro: our projections are too narrow (sd 8.2 against the market's 12.1; the final margin moves 1.45 points per point of ours). Does fixing the width, or a pick rule that
does not care about the width, make better picks?  The earlier K 90 retune only looked at a fixed 5-point threshold, which shrinks the pick set as the model widens, so it could not
separate "a wider model" from "fewer picks". Here every variant is compared at the SAME number of picks as the live rule, taking the largest |edge|.

Pre-registered variants (nothing tuned on picks):
  K70 / K90 / K110   the rating part of the margin scaled by K/70, home field and special teams unchanged
  z                  edge divided by the standard deviation of that season's model-minus-line edges so far (week-by-week, only earlier games), picks at the same count
  agree              v1 and v2+ST both at least 3 points from the line on the same side AND their average 5+
  v1                 the old model alone, same count
Groups: tune 2022-23, TEST 2024-25, 2026 weeks 4-7 live replay. Graded vs the ESPN close and the ESPN open, pushes dropped.
Run: python3 scripts/cfb_week7_scale_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfb_week7_study import rec, fmt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    hf = np.where(d.neutral, 0.0, 2.5)
    for k in (70, 90, 110): d['K%d' % k] = (d.v2 - hf) * k / 70 + hf + d.gap
    d = d[d.week >= 4].copy()
    groups = (('tune 22-23', d.season.isin([2022, 2023])), ('TEST 24-25', d.season.isin([2024, 2025])), ('2026 wk4-7', d.season == 2026))
    print('width of each model (sd of model minus close) and slope of (final minus close) on it, weeks 4+:')
    for lab, m in groups:
        s = d[m].dropna(subset=['mkt']); r = []
        for k in ('K70', 'K90', 'K110', 'v1'):
            e = s[k] - s.mkt; r.append('%s sd %.1f slope %.2f' % (k, e.std(), (e * (s.hm - s.mkt)).sum() / (e * e).sum()))
        print('  %-11s %s' % (lab, ' | '.join(r)))
    for ln in ('mkt', 'open'):
        print('\n=== matched count, 5+ rule of K70 sets the count; graded vs the ESPN %s ===' % ('close' if ln == 'mkt' else 'open'))
        for lab, m in groups:
            s = d[m].dropna(subset=[ln]).copy(); e70 = s.K70 - s[ln]; n = int((e70.abs() >= 5).sum()); c = s.hm - s[ln]; row = []
            def top(e, k=n):
                idx = e.abs().sort_values(ascending=False).index[:k]; return rec(s.loc[idx], e[idx], c[idx])
            row.append('K70 %s' % fmt(top(e70)))
            for k in ('K90', 'K110', 'v1'): row.append('%s %s' % (k, fmt(top(s[k] - s[ln]))))
            # z-score: scale each edge by the sd of K70 edges before this week in the same season (expanding), picks at the same count
            z = pd.Series(index=s.index, dtype=float)
            for (y, w), g in s.groupby(['season', 'week']):
                prev = s[(s.season == y) & (s.week < w)]; sd = (prev.K70 - prev[ln]).std() if len(prev) > 40 else e70.std(); z[g.index] = e70[g.index] / sd
            row.append('z %s' % fmt(top(z)))
            ev1, e2 = s.v1 - s[ln], e70; ag = ((np.sign(ev1) == np.sign(e2)) & (ev1.abs() >= 3) & (e2.abs() >= 3) & (((ev1 + e2) / 2).abs() >= 5)); sel = s[ag]
            row.append('agree %s (n=%d)' % (fmt(rec(sel, e2[sel.index], c[sel.index])), len(sel)))
            print('  %-11s n=%d  %s' % (lab, n, ' | '.join(row)))
    s = d[d.season >= 2024].dropna(subset=['mkt'])
    for k in ('K70', 'K90', 'K110'):
        x = np.c_[np.ones(len(s)), s.mkt, s[k] - s.mkt]; print('weight on edge vs close 2024-26 %s: %.3f | miss %.3f' % (k, np.linalg.lstsq(x, s.hm, rcond=None)[0][2], (s.hm - s[k]).abs().mean()))


if __name__ == '__main__':
    sys.exit(main())
