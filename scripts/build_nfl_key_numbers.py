#!/usr/bin/env python3
"""NFL key numbers from real finals: how often a regular-season game ends on each margin and each total.

Source: nflverse games.csv (https://github.com/nflverse/nfldata, free, 1999 to now). Used by Sharp Money V2 to price a half-point move in win
probability: moving a spread across a 3 is worth far more than across a 2. Shares are of all regular-season games with a final score, by absolute margin
(spreads) and by total points (totals). Two windows are written so the page can say which one it used: all seasons, and the last 6 completed ones
(key-number weights drift: the 7 swung between 7% and 10%).

usage: build_nfl_key_numbers.py [--csv games.csv] [--out data/nfl_key_numbers.json]"""
import argparse, collections, csv, io, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'

ap = argparse.ArgumentParser()
ap.add_argument('--csv'); ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'nfl_key_numbers.json'))
a = ap.parse_args()
raw = open(a.csv, newline='').read() if a.csv else urllib.request.urlopen(URL, timeout=60).read().decode()
rows = [r for r in csv.DictReader(io.StringIO(raw)) if r['game_type'] == 'REG' and r['result'] not in ('', 'NA') and r['home_score'] not in ('', 'NA')]
seasons = sorted({int(r['season']) for r in rows})
# a season counts as completed only if it has the full 272 or 256 games; the current partial one is left out so its early weeks do not skew the window
full = [s for s in seasons if sum(1 for r in rows if int(r['season']) == s) >= 256]


def dist(rs, max_m=30):
    mc, tc = collections.Counter(), collections.Counter()
    for r in rs:
        mc[abs(int(float(r['result'])))] += 1
        tc[int(float(r['total']))] += 1
    n = len(rs)
    return dict(n=n, margin={str(k): round(mc[k] / n, 4) for k in range(0, max_m + 1)}, total={str(k): round(tc[k] / n, 4) for k in range(20, 71)})


recent = full[-6:]
out = dict(source=URL, generated_from_games=len(rows), all=dict(seasons=[seasons[0], seasons[-1]], **dist(rows)),
           recent=dict(seasons=[recent[0], recent[-1]], **dist([r for r in rows if int(r['season']) in recent])),
           note='share of regular-season games ending on exactly this absolute margin (spread) or total. A half-point move across a number is worth about that share in win probability.')
with open(a.out, 'w') as f:
    json.dump(out, f, indent=1)
for w in ('all', 'recent'):
    d = out[w]; print(w, d['seasons'], 'n', d['n'], 'margin 3/7/6/10/1/14:', [d['margin'][k] for k in ('3', '7', '6', '10', '1', '14')])
