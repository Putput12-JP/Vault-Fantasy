#!/usr/bin/env python3
"""Write the walk-forward record of the CURRENT model under the CURRENT pick rule (cfb_model.pick_ok) into data/cfb_model_backtest.json, 2022-2025, graded against ESPN's close.

The page quotes this file as "what the test says". It still held the v1-era numbers (5+ point picks, favorites included). The rows come from scripts/cfb_week7_base_rows.py (the live
v2 + special teams model replayed week by week with only earlier games); nothing is refit here. The previous per-season numbers stay under picks_wk4_all_edges for the record.
Run: python3 scripts/cfb_pickrule_backtest.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_model as cm


def rec(z, keep):
    e = z.v2st - z.mkt; c = z.hm - z.mkt; m = keep & (c != 0); w = int(((c[m] * np.sign(e[m])) > 0).sum()); return [w, int(m.sum()) - w]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); d = d[(d.season <= 2025) & (d.week >= cm.PICK_MIN_WEEK)].dropna(subset=['mkt']).copy()
    d['ok'] = [cm.pick_ok(r.v2st - r.mkt, r.week, r.mkt) for r in d.itertuples()]
    d['all'] = (d.v2st - d.mkt).abs() >= cm.PICK_EDGE
    back = json.load(open(cm.BACKTEST))
    for y in (2022, 2023, 2024, 2025):
        z = d[d.season == y]; s = back['seasons'][str(y)]
        s.setdefault('picks_wk4_all_edges', s['picks_wk4']); s['picks_wk4'] = rec(z, z.ok); s['picks_wk4_with_favorites'] = rec(z, z['all'])
    back['combined'].setdefault('picks_wk4_all_edges', back['combined']['picks_wk4']); back['combined']['picks_wk4'] = rec(d, d.ok); back['combined']['picks_wk4_with_favorites'] = rec(d, d['all'])
    back['model'] = 'v2 prior + special teams (the live model), replayed week by week'; back['pick_rule'] = cm.PICK_RULE
    back['rule_note'] = "Picks on the favorite are not official picks and are left out of this record."
    json.dump(back, open(cm.BACKTEST, 'w'), indent=1); print(json.dumps(back['combined']))


if __name__ == '__main__':
    main()
