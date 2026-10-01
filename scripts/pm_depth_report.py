#!/usr/bin/env python3
"""
How much a Polymarket NFL market can actually fill: dollars resting within 1 cent of the best price, by market type
and time before kickoff, from the Pendulum Flow orderbook archive's full book snapshots (archive.pendulumflow.com,
CC BY 4.0). The live caps come from the recorder's own order-book reads each poll; this is the reference for what
"deep" and "thin" mean, and the evidence for treating Polymarket player props as a signal, not a place to bet.

For every market of the Sunday 1 PM ET slots of NFL weeks 1-3: the last book snapshot before kickoff minus 24 h, 6 h
and 1 h. Depth to buy = dollars on the asks within 1c of the best ask, for both outcome tokens (each is a way to bet).
-> docs/pm-depth-nfl.md, data/pm_depth_nfl.json

Usage: python3 scripts/pm_depth_report.py   (needs duckdb + pytz, like pm_archive.py)
"""
import datetime as dt, json, os, statistics as S, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import pm_archive as PA

SLOTS = ['2026-09-13T17:00:00Z', '2026-09-20T17:00:00Z', '2026-09-27T17:00:00Z']
OFFSETS = (24, 6, 1)
GROUPS = {'moneyline': 'Moneyline', 'spreads': 'Spreads (every line)', 'totals': 'Totals (every line)', 'first_half_spreads': '1st-half spreads',
          'team_totals': 'Team totals', 'anytime_touchdowns': 'Anytime touchdown', 'receptions': 'Receptions', 'receiving_yards': 'Receiving yards',
          'rushing_yards': 'Rushing yards', 'passing_yards': 'Passing yards'}


def markets(slot):
    """Every market (all types) of the events kicking off at this slot: cid -> (type, both tokens)."""
    t = PA.ts(slot)
    out = {}
    for closed in ('true', 'false'):
        for off in range(0, 1000, 100):
            E = PA.curl_json(f'https://gamma-api.polymarket.com/events?series_id={PA.SERIES["nfl"]}&closed={closed}&limit=100&offset={off}'
                             f'&end_date_min={PA.iso(t - 60)}&end_date_max={PA.iso(t + 60)}') or []
            for e in E:
                for m in e.get('markets') or []:
                    try:
                        toks = [hex(int(x))[2:].zfill(64) for x in json.loads(m['clobTokenIds'])]
                    except Exception:
                        continue
                    out[m['conditionId'].lower()[2:]] = (m.get('sportsMarketType') or 'other', toks)
            if len(E) < 100:
                break
    return out


def depth_at(c, t, cids):
    """{token: $ within 1c of the best ask} from the last book snapshot in the hour before t."""
    rows = PA.query(c, t - 3600, 'book', "lower(hex(asset_id)), epoch_ms(timestamp), asks", cids, before=t) or []
    last = {}
    for a, tm, asks in rows:
        if a not in last or tm > last[a][0]:
            last[a] = (tm, asks)
    out = {}
    for a, (_, asks) in last.items():
        lv = [(float(x['price']), float(x['size'])) for x in asks or []]
        if lv:
            ba = min(p for p, _ in lv)
            out[a] = sum(p * z for p, z in lv if p <= ba + 0.01 + 1e-9)
    return out


def main():
    jobs = []
    for slot in SLOTS:
        M = markets(slot)
        for h in OFFSETS:
            jobs.append((slot, h, M))
    print(f'{len(jobs)} snapshots to read', flush=True)

    def one(j):
        slot, h, M = j
        t = int(PA.ts(slot)) - h * 3600
        c = PA.con()
        d = depth_at(c, t, sorted(M))
        res = defaultdict(list)
        for cid, (typ, toks) in M.items():
            for tok in toks:
                res[typ].append(d.get(tok, 0.0))           # no book = nothing to fill
        print(f'  {slot} -{h}h: {len(d)} books', flush=True)
        return h, res
    agg = defaultdict(lambda: defaultdict(list))
    with ThreadPoolExecutor(4) as ex:
        for h, res in ex.map(one, jobs):
            for typ, v in res.items():
                agg[typ][h] += v
    out, L = {}, ['# How deep Polymarket NFL markets are', '',
                  'Dollars resting within 1 cent of the best price, per way to bet (each outcome token), for every market of the Sunday 1 PM ET '
                  'slots of NFL weeks 1-3, from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0). '
                  'Built by scripts/pm_depth_report.py. The app caps live stakes from the recorder\'s own order-book reads each poll; this table is '
                  'the reference for what those numbers usually are.', '',
                  '| Market | Ways to bet | Median 24 h out | Median 6 h out | Median 1 h out | Share with $100+ (1 h) | Share with $1,000+ (1 h) |',
                  '|---|---|---|---|---|---|---|']
    for typ, nm in GROUPS.items():
        if typ not in agg:
            continue
        a = agg[typ]
        one_h = a.get(1, [])
        med = {h: S.median(a[h]) if a.get(h) else None for h in OFFSETS}
        out[typ] = {'n': len(one_h), 'median': med, 'p100': S.fmean([v >= 100 for v in one_h]) if one_h else None,
                    'p1000': S.fmean([v >= 1000 for v in one_h]) if one_h else None}
        f = lambda v: '' if v is None else f'${v:,.0f}'
        L.append(f"| {nm} | {len(one_h):,} | {f(med[24])} | {f(med[6])} | {f(med[1])} | {out[typ]['p100']:.0%} | {out[typ]['p1000']:.0%} |")
    L += ['', 'A way to bet with $0 has no order book at all within 1 cent, or none in that hour. Player props are a signal at most: '
          'their order books rarely hold enough to place a real stake.', '']
    open(os.path.join(ROOT, 'docs', 'pm-depth-nfl.md'), 'w').write('\n'.join(L) + '\n')
    json.dump({'generated': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': PA.CREDIT, 'slots': SLOTS, 'by_type': out},
              open(os.path.join(ROOT, 'data', 'pm_depth_nfl.json'), 'w'), indent=1)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
