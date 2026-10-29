#!/usr/bin/env python3
"""
Closing-line shadow: does the market move toward the minutes model's side? Rule frozen in docs/clv-shadow.md (written 2026-10-29, before any forward row).

For every recorded prop (psim, the Props Simulation record) seen at two different times on the SAME line with a price at both looks:
  first look  = the earliest psim row for the prop (p_exact = the model, p_price = the vig-free over chance in the price)
  last look   = the latest psim row (the pre-tip price)
  model side  = over if p_exact(first) > p_price(first), else under
  gap         = |p_exact(first) - p_price(first)|; the registered cohort is gap >= GAP
  CLV         = how far the price moved toward the model side, in probability points: (p1 - p0) for an over, (p0 - p1) for an under
Nothing here is a bet and nothing here changes a price. There is no stake or payout, so no profit number is quoted.

Sample split (never mixed): DISCOVERY = props first seen before FORWARD_FROM (the 2026-10-19..29 window the rule was found in, looked at several
ways, so descriptive only); FORWARD = first seen on or after FORWARD_FROM. The verdict reads FORWARD only.

Standard errors are clustered by game (props in one game share news and move together).

  python3 nba/scripts/clv_shadow.py --dir=nba-data [--out=nba/data/clv_shadow.json]
reads <dir>/snapshots/<day>/psim.jsonl and meta.jsonl (the 'held' tag). Stateless: the whole file is rebuilt from the records every run.
"""
import collections, glob, json, math, os, sys

GAP = 0.03                         # the registered cohort: model and price at least 3 points apart at the first look
FORWARD_FROM = '2026-10-30'        # first snapshot day that counts as forward
MIN_N, MIN_GAMES, Z_BAR = 500, 30, 2.0
STATS = ['pts', 'reb', 'ast', '3pm']


def load(root):
    held, first, last = set(), {}, {}
    for p in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'meta.jsonl'))):
        for ln in open(p):
            try:
                m = json.loads(ln)
            except ValueError:
                continue
            if m.get('src') == 'psim' and m.get('held'):
                held.add(m['k'])
    for p in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'psim.jsonl'))):
        day = p.split(os.sep)[-2]
        for ln in open(p):
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            if not o.get('v'):
                continue
            o['day'] = day
            k = o['k']
            if k not in first or o['t'] < first[k]['t']:
                first[k] = o
            if k not in last or o['t'] >= last[k]['t']:
                last[k] = o
    return held, first, last


def rows_from(held, first, last):
    out = []
    for k, l in last.items():
        f = first[k]
        fv, lv = f['v'], l['v']                      # [line, mu, p_exact, p_10k, p_50, p_price, price_src]
        if f['t'] == l['t'] or fv[0] != lv[0] or fv[5] is None or lv[5] is None:
            continue
        g, _, s = k.split('|')
        if s not in STATS:
            continue
        side = 1 if fv[2] > fv[5] else -1
        out.append(dict(k=k, g=g, s=s, day=f['day'], held=k in held, gap=abs(fv[2] - fv[5]), src=fv[6],
                        clv=side * (lv[5] - fv[5])))
    return out


def stat(rs):
    """n, games, mean CLV, game-clustered SE, z"""
    if not rs:
        return dict(n=0, games=0, clv=None, se=None, z=None)
    G = collections.defaultdict(list)
    for r in rs:
        G[r['g']].append(r['clv'])
    n = len(rs); mu = sum(r['clv'] for r in rs) / n
    se = math.sqrt(sum((sum(v) - mu * len(v)) ** 2 for v in G.values())) / n
    return dict(n=n, games=len(G), clv=round(mu, 5), se=round(se, 5), z=round(mu / se, 2) if se else None)


def verdict(st):
    if st['n'] < MIN_N or st['games'] < MIN_GAMES:
        return 'collecting'
    return 'works' if (st['clv'] > 0 and st['z'] is not None and st['z'] >= Z_BAR) else 'not shown'


def build(root):
    held, first, last = load(root)
    rs = rows_from(held, first, last)
    cohort = [r for r in rs if r['gap'] >= GAP]
    fwd = [r for r in cohort if r['day'] >= FORWARD_FROM]
    dis = [r for r in cohort if r['day'] < FORWARD_FROM]

    def split(pool):
        return dict(
            free=stat([r for r in pool if not r['held']]),
            held=stat([r for r in pool if r['held']]),
            by_stat={s: stat([r for r in pool if not r['held'] and r['s'] == s]) for s in STATS},
            by_gap={f'{lo:.2f}-{hi:.2f}': stat([r for r in pool if not r['held'] and lo <= r['gap'] < hi])
                    for lo, hi in [(GAP, .06), (.06, .10), (.10, 1.01)]},
            by_price_source={x: stat([r for r in pool if not r['held'] and r['src'] == x]) for x in sorted({r['src'] for r in pool})},
            by_day={d: stat([r for r in pool if not r['held'] and r['day'] == d]) for d in sorted({r['day'] for r in pool})},
        )
    fs = split(fwd)
    return {
        'rule': {'gap': GAP, 'forward_from': FORWARD_FROM, 'doc': 'nba/docs/clv-shadow.md',
                 'verdict_bar': f'free props, forward only: n >= {MIN_N}, games >= {MIN_GAMES}, CLV > 0 and z >= {Z_BAR}'},
        'verdict': verdict(fs['free']),
        'forward': fs,
        'discovery': split(dis),
        'props_seen_twice': len(rs),
    }


def main():
    a = dict(x.lstrip('-').split('=', 1) for x in sys.argv[1:] if '=' in x)
    root = a.get('dir', 'nba-data')
    out = a.get('out', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'clv_shadow.json'))
    res = build(root)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, 'w'), separators=(',', ':'))
    f, d = res['forward']['free'], res['discovery']['free']
    print(f"clv_shadow: forward n={f['n']} games={f['games']} clv={f['clv']} z={f['z']} -> {res['verdict']}; "
          f"discovery n={d['n']} games={d['games']} clv={d['clv']} z={d['z']}")


if __name__ == '__main__':
    main()
