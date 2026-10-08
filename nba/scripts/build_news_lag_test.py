#!/usr/bin/env python3
"""
Edge test 1: news lag. Rules: docs/edge-tests-r2.md (written and amended before any regular-season data existed).

Reads data/track.json's cube (ledger.py): shadow bets tagged `news` (an edge exists and the price is older than news seen in
the last 3 hours) against `model`-only bets (same edge threshold, no news tag). The day is the unit (the cube has no game id).
Regular-season record only; the preseason record is ignored.

  python3 nba/scripts/build_news_lag_test.py
Writes nba/data/news_lag_test.json and nba/docs/news-lag-test-results.md
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
DOCS = os.path.join(HERE, '..', 'docs')
MIN_BETS, MIN_DAYS, GO_Z, GO_Z_CLV, WATCH_Z = 150, 25, 2.4, 2.0, 1.65


def zscore(xs):
    if len(xs) < 2:
        return 0.0
    se = statistics.stdev(xs) / math.sqrt(len(xs))
    return round(statistics.mean(xs) / se, 2) if se else 0.0


def group(rows, cols, pick):
    ix = {c: i for i, c in enumerate(cols)}
    days = defaultdict(lambda: [0, 0.0, 0.0, 0])           # day -> [settled bets, units, clv sum, clv n]
    for r in rows:
        if not pick(r[ix['etype']]):
            continue
        n = r[ix['w']] + r[ix['l']] + r[ix['p']]
        d = days[r[ix['day']]]
        d[0] += n
        d[1] += r[ix['units']]
        d[2] += r[ix['clv_sum']]
        d[3] += r[ix['clv_n']]
    return days


def summarize(days):
    ds = sorted(days)
    bets = sum(days[d][0] for d in ds)
    roi_d = [days[d][1] / days[d][0] for d in ds if days[d][0]]
    clv_d = [days[d][2] / days[d][3] for d in ds if days[d][3]]
    half = len(ds) // 2
    halves = [sum(days[d][1] for d in part) / max(1, sum(days[d][0] for d in part)) for part in (ds[:half], ds[half:])] if half else [None, None]
    return {'bets': bets, 'days': len(ds), 'roi': round(sum(days[d][1] for d in ds) / bets, 4) if bets else None, 'z_roi': zscore(roi_d),
            'clv': round(statistics.mean(clv_d), 4) if clv_d else None, 'z_clv': zscore(clv_d), 'halves': [None if h is None else round(h, 4) for h in halves]}


def verdict(s):
    if s['bets'] < MIN_BETS or s['days'] < MIN_DAYS:
        return f"too early: {s['bets']} settled bets over {s['days']} days (needs {MIN_BETS} over {MIN_DAYS})"
    both = all(h is not None and h > 0 for h in s['halves'])
    if s['roi'] > 0 and both and s['clv'] is not None and s['clv'] > 0:
        if s['z_roi'] >= GO_Z and s['z_clv'] >= GO_Z_CLV:
            return 'GO'
        if s['z_roi'] >= WATCH_Z:
            return 'WATCH'
    return 'NO-GO'


def main():
    t = json.load(open(os.path.join(DATA, 'track.json')))
    cols, cube = t['cube_cols'], t.get('cube') or []
    news = summarize(group(cube, cols, lambda e: 'news' in (e or '').split(',')))
    model = summarize(group(cube, cols, lambda e: (e or '') == 'model'))
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'news': news, 'model_only': model, 'verdict': verdict(news)}
    json.dump(res, open(os.path.join(DATA, 'news_lag_test.json'), 'w'), indent=1)
    md = ['# News lag: results', '', f"Run {res['generated']}. Rules: docs/edge-tests-r2.md, test 1.", '', f"**Verdict: {res['verdict']}**", '',
          '| group | settled bets | days | ROI | z (ROI) | mean CLV | z (CLV) | first half | second half |', '|---|---|---|---|---|---|---|---|---|']
    for name, s in (('news', news), ('model only', model)):
        md.append(f"| {name} | {s['bets']} | {s['days']} | {s['roi']} | {s['z_roi']} | {s['clv']} | {s['z_clv']} | {s['halves'][0]} | {s['halves'][1]} |")
    md += ['', 'ROI is units per settled bet; CLV is against Pinnacle\'s close. The day is the unit for z.', '']
    open(os.path.join(DOCS, 'news-lag-test-results.md'), 'w').write('\n'.join(md))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
