#!/usr/bin/env python3
"""
Export the minutes GBM (build_minutes_gbm.py features, 300 trees x 15 leaves) as plain JSON and prove a pure-Python scorer
reproduces LightGBM exactly, so the shadow model needs no lightgbm at run time (the repo's cron jobs are stdlib Python).

  python3 nba/scripts/export_minutes_gbm.py [--fit-through 2026]   -> data/minutes_gbm.json (refits, then checks parity on 3,000 rows)

The file is fit on seasons 2023..--fit-through, INCLUDING the 2025-26 season by default, so it is a shipping artifact, not an
evaluation: all accuracy claims come from build_minutes_gbm.py's held-out seasons.

JSON: {features: [...], trees: [{f: [...], t: [...], l: [...], r: [...], v: [...]}], trained: {...}}
Node i: if f[i] >= 0, go l[i] when x[f[i]] <= t[i] else r[i]; if f[i] < 0, leaf with value v[i]. Prediction = sum of leaf values.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_minutes_gbm as G
import build_minutes_spread as SP

OUT = os.path.join(C.HERE, '..', 'data', 'minutes_gbm.json')


def flatten(node, f, t, l, r, v):
    i = len(f)
    f.append(-1); t.append(0.0); l.append(-1); r.append(-1); v.append(0.0)
    if 'split_feature' in node:
        assert node['decision_type'] == '<=', node['decision_type']
        f[i], t[i] = node['split_feature'], node['threshold']
        l[i] = flatten(node['left_child'], f, t, l, r, v)
        r[i] = flatten(node['right_child'], f, t, l, r, v)
    else:
        v[i] = node['leaf_value']
    return i


def predict(model, x):
    s = 0.0
    for tr in model['trees']:
        i = 0
        while tr['f'][i] >= 0:
            i = tr['l'][i] if x[tr['f'][i]] <= tr['t'][i] else tr['r'][i]
        s += tr['v'][i]
    return s


def main():
    import lightgbm as lgb
    through = int(sys.argv[sys.argv.index('--fit-through') + 1]) if '--fit-through' in sys.argv else 2026
    box = C.player_games(G.SEASONS)
    df = G.build_rows(box, MM.expected_margins(box))
    df = df[(df.y > 0) & (df.season <= through) & (df.season >= 2023)]
    X, y = df[SP.COLS], df.y
    gb = lgb.LGBMRegressor(**SP.MEAN_KW).fit(X, y)
    trees = []
    for t in gb.booster_.dump_model()['tree_info']:
        f, th, l, r, v = [], [], [], [], []
        flatten(t['tree_structure'], f, th, l, r, v)
        trees.append(dict(f=f, t=th, l=l, r=r, v=[round(x, 12) for x in v]))
    model = dict(features=SP.COLS, trees=trees, trained=dict(seasons=[2023, through], rows=len(df), params=SP.MEAN_KW))
    sample = df.sample(3000, random_state=1)
    ref = gb.predict(sample[SP.COLS])
    worst = max(abs(predict(model, row) - r) for row, r in zip(sample[SP.COLS].values.tolist(), ref))
    print(f'{len(trees)} trees, {sum(len(t["f"]) for t in trees):,} nodes; max |pure-python - LightGBM| over 3,000 rows = {worst:.2e}')
    assert worst < 1e-8, 'parity failed'
    json.dump(model, open(OUT, 'w'), separators=(',', ':'))
    print('wrote', OUT, f'{os.path.getsize(OUT) / 1024:.0f} KB')


if __name__ == '__main__':
    main()
