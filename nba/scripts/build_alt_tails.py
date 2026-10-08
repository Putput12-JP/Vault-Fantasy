#!/usr/bin/env python3
"""
Edge test 3: alternate-line tails. Rules are frozen in docs/edge-tests-r2.md (committed before this ran).

Bet $1 on the over at every ESPN alternate rung, bucketed by the price's implied chance.
  fit  2024-25  open price        select buckets: >= 1,000 bets, ROI > 0, z >= 1.5
  test 2025-26  pre-tip close     GO: selected, >= 300 bets, >= 40 games, ROI > 0, z >= 2.4, both halves of the season positive
                                  WATCH: z >= 1.65 with the same sample

  python3 nba/scripts/build_alt_tails.py
Writes nba/data/alt_tails.json and nba/docs/alt-tails-results.md
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
from build_prop_model import am_prob, am_payout

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'alt_tails.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'alt-tails-results.md')
BUCKETS = [(.02, .10), (.10, .20), (.20, .35), (.35, .50), (.50, .65), (.65, .80), (.80, .95)]
FIT_N, FIT_Z = 1000, 1.5
TEST_N, TEST_GAMES, GO_Z, WATCH_Z = 300, 40, 2.4, 1.65


def bucket_of(p):
    for lo, hi in BUCKETS:
        if lo <= p < hi or (hi == .95 and p == hi):
            return f'{lo:.2f}-{hi:.2f}'
    return None


def stats(rows):
    """rows: [(game, profit)]. Game is the unit: mean profit per bet within a game, then z across games."""
    if not rows:
        return None
    per = defaultdict(list)
    for g, pr in rows:
        per[g].append(pr)
    gm = [statistics.mean(v) for v in per.values()]
    se = statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 1 else 0
    roi = sum(pr for _, pr in rows) / len(rows)
    return {'bets': len(rows), 'games': len(gm), 'roi': round(roi, 4), 'z': round(statistics.mean(gm) / se, 2) if se else 0.0,
            'hit': None}


def load():
    fit, test = defaultdict(list), defaultdict(list)    # bucket -> [(game, profit, market, day)]
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if r['kind'] != 'alt' or r['played'] != '1' or not r['actual']:
            continue
        if r['season'] == '2025':
            px, dest = r['over_px_open'], fit
        elif r['season'] == '2026' and r['cur_is_pretip'] == '1':
            px, dest = r['over_px_cur'], test
        else:
            continue
        p = am_prob(px)
        line = float(r['line_open'] if r['season'] == '2025' else r['line_cur'] or 0)
        b = p is not None and bucket_of(p)
        if not b:
            continue
        win = float(r['actual']) > line
        dest[b].append((r['game_id'], am_payout(px) if win else -1.0, r['market'], r['tip'][:10]))
    return fit, test


def main():
    fit, test = load()
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'buckets': {}, 'selected': [], 'verdict': {}}
    for lo, hi in BUCKETS:
        k = f'{lo:.2f}-{hi:.2f}'
        f = stats([(g, p) for g, p, _, _ in fit.get(k, [])])
        t = stats([(g, p) for g, p, _, _ in test.get(k, [])])
        sel = bool(f and f['bets'] >= FIT_N and f['roi'] > 0 and f['z'] >= FIT_Z)
        res['buckets'][k] = {'fit': f, 'test': t, 'selected': sel}
        if sel:
            res['selected'].append(k)
    for k in res['selected']:
        rows = test.get(k, [])
        days = sorted({d for _, _, _, d in rows})
        mid = days[len(days) // 2] if days else None
        halves = [stats([(g, p) for g, p, _, d in rows if (d < mid) == first]) for first in (True, False)] if mid else [None, None]
        t = res['buckets'][k]['test']
        ok_sample = t and t['bets'] >= TEST_N and t['games'] >= TEST_GAMES
        both = all(h and h['roi'] > 0 for h in halves)
        v = 'NO-GO'
        if ok_sample and t['roi'] > 0 and both:
            v = 'GO' if t['z'] >= GO_Z else 'WATCH' if t['z'] >= WATCH_Z else 'NO-GO'
        res['verdict'][k] = {'verdict': v, 'halves': halves}
    if not res['selected']:
        res['overall'] = 'NO-GO: no bucket qualified on the fit season (2024-25)'
    else:
        res['overall'] = ', '.join(f'{k}: {v["verdict"]}' for k, v in res['verdict'].items())
    # per market, descriptive only
    per = defaultdict(lambda: defaultdict(list))
    for k, rows in test.items():
        for g, p, m, _ in rows:
            per[m][k].append((g, p))
    res['per_market_test'] = {m: {k: stats(v) for k, v in sorted(b.items())} for m, b in sorted(per.items())}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    md = ['# Alternate-line tails: results', '', f"Run {res['generated']}. Rules: docs/edge-tests-r2.md, test 3 (frozen before this ran).", '',
          f"**Verdict: {res['overall']}**", '', '| price bucket | fit bets | fit ROI | fit z | selected | test bets | test games | test ROI | test z | verdict |', '|---|---|---|---|---|---|---|---|---|---|']
    for k, b in res['buckets'].items():
        f, t = b['fit'] or {}, b['test'] or {}
        md.append(f"| {k} | {f.get('bets', '')} | {f.get('roi', '')} | {f.get('z', '')} | {'yes' if b['selected'] else 'no'} | {t.get('bets', '')} | {t.get('games', '')} | {t.get('roi', '')} | {t.get('z', '')} | {res['verdict'].get(k, {}).get('verdict', '')} |")
    md += ['', 'ROI is per $1 on the over at the alternate rung; the game is the unit for z. Per-market rows (2025-26) are in data/alt_tails.json and are descriptive only.', '']
    open(OUT_MD, 'w').write('\n'.join(md))
    print(json.dumps({k: {'fit': b['fit'], 'test': b['test'], 'sel': b['selected']} for k, b in res['buckets'].items()}, indent=0)[:3000])
    print(res['overall'])


if __name__ == '__main__':
    main()
