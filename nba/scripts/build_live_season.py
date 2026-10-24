#!/usr/bin/env python3
"""
This season's live record for the What Works page: every settled regular-season shadow bet (the ledger's bets/<day>.json on the
nba-data branch), sliced by market, venue, edge type, edge size, stat and gate, with an honest standard error.

The Track Record cube counts each bet once, but the same player is priced at several books, apps and Kalshi rungs, and all of
them win or lose together. A cube row's standard error therefore treats thousands of bets as independent when they are a few
hundred player-nights. This file carries, per slice, the return per bet and its standard error with bets grouped by player-night
(one player in one game); the page builds its luck odds from that, not from the bet count.

Same bets, same rules as the cube (ledger.py): settled = win, loss or push, preseason left out, entry-price units. The totals
reproduce the cube's (check_against_cube prints any gap).

  python3 nba/scripts/build_live_season.py        # also called by build_data_health.py before it renders the app
"""
import json, math, os, subprocess, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ledger as L

ROOT = os.path.join(HERE, '..', '..')
DATA = os.path.join(HERE, '..', 'data')
BRANCH = 'origin/nba-data'
OUT = os.path.join(DATA, 'live_season.json')
MIN_SLICE = 1            # every slice is kept; the page decides how small is too small to read


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True).stdout


def load_bets():
    """Every settled regular-season bet on the branch, from bets/<day>.json (no checkout needed)."""
    out = []
    for name in sorted(git('ls-tree', '--name-only', f'{BRANCH}:bets').split()):
        if not name.endswith('.json'):
            continue
        try:
            day = json.loads(git('show', f'{BRANCH}:bets/{name}') or 'null') or []
        except json.JSONDecodeError:
            continue
        out += [b for b in day if not b.get('pre') and b.get('result') in ('win', 'loss', 'push')]
    return out


def side_of(b):
    return 'over' if b['side'] in ('Over', 'YES') else 'under'


def record(bs):
    """Record, return per bet, closing-price return, price move, the per-bet spread (sd) and the player-night clustered standard error (se) of the mean return."""
    n = len(bs)
    u = sum(b['pnl'] for b in bs)
    m = u / n
    nights = {}
    for b in bs:
        nights[(b['game'], b['pid'])] = nights.get((b['game'], b['pid']), 0.0) + (b['pnl'] - m)
    G = len(nights)
    se = math.sqrt(G / (G - 1) * sum(v * v for v in nights.values())) / n if G > 1 else None
    clv = [b['clv'] for b in bs if b.get('clv') is not None]
    sd = math.sqrt(sum((b['pnl'] - m) ** 2 for b in bs) / (n - 1)) if n > 1 else None
    return {'n': n, 'w': sum(b['result'] == 'win' for b in bs), 'l': sum(b['result'] == 'loss' for b in bs),
            'p': sum(b['result'] == 'push' for b in bs), 'u': round(u, 4), 'uc': round(sum(b['pnl_close'] for b in bs), 4),
            'sd': round(sd, 5) if sd is not None else None, 'se': round(se, 5) if se is not None else None, 'nights': G, 'games': len({b['game'] for b in bs}),
            'picks': len({(b['pid'], b['stat'], side_of(b)) for b in bs}),
            'clv': round(sum(clv) / len(clv), 5) if clv else None, 'clv_n': len(clv)}


def group(bs, keyf):
    g = {}
    for b in bs:
        g.setdefault(keyf(b), []).append(b)
    return g


def rows(bs, keyf, label, lo=MIN_SLICE):
    """[{**label(key), **record, gate}] for every slice with at least `lo` settled bets, biggest first."""
    out = []
    for k, v in group(bs, keyf).items():
        if len(v) < lo:
            continue
        gate = max(v, key=lambda b: b['tip'])['gate']          # the market's gate as of its latest bet
        out.append({**label(k), **record(v), 'gate': gate})
    return sorted(out, key=lambda r: -r['n'])


def ebin(b):
    return next(lab for hi, lab in L.EDGE_BINS if b['edge'] < hi)


def snapshot():
    subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'nba-data'], check=False)
    bs = load_bets()
    if not bs:
        return
    days = rows(bs, lambda b: L.tip_day(b['tip']), lambda k: {'day': k}, 1)
    days.sort(key=lambda r: r['day'])
    out = {'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'through': days[-1]['day'], 'first': days[0]['day'],
           'min_slice': MIN_SLICE, 'cluster': 'player-night (game and player)', 'total': record(bs), 'days': days,
           'market': rows(bs, lambda b: (L.family(b), b['stat'], side_of(b)), lambda k: {'venue': k[0], 'stat': k[1], 'side': k[2]}),
           'venue': rows(bs, L.family, lambda k: {'venue': k}),
           'etype': rows(bs, lambda b: b.get('etype', 'model'), lambda k: {'etype': k}),
           'ebin': rows(bs, ebin, lambda k: {'ebin': k}),
           'stat': rows(bs, lambda b: b['stat'], lambda k: {'stat': k}),
           'gate': rows(bs, lambda b: b['gate'], lambda k: {'gate': k})}
    json.dump(out, open(OUT, 'w'), separators=(',', ':'))
    t = out['total']
    print(f"live season: {t['n']:,} settled bets, {t['picks']:,} picks, {t['nights']} player-nights, {t['games']} games, "
          f"{t['u']:+.1f}u through {out['through']} -> data/live_season.json")
    check_against_cube(out)


def check_against_cube(out):
    """The cube is the Track Record's number; ours must agree on settled bets and units (the two snapshots can differ by a poll)."""
    try:                                                   # the branch's file is the one the bets files were written with; the local copy can be a poll older
        t = json.loads(git('show', f'{BRANCH}:track.json') or 'null') or json.load(open(os.path.join(DATA, 'track.json')))
    except (OSError, ValueError):
        return
    c = {k: i for i, k in enumerate(t['cube_cols'])}
    cube = t['cube']                               # the preseason cube is a separate field
    n = sum(r[c['w']] + r[c['l']] + r[c['p']] for r in cube)
    u = sum(r[c['units']] for r in cube)
    d = out['total']
    flag = '' if (n == d['n'] and abs(u - d['u']) < 0.05) else '  <- differs from the Track Record cube (a poll apart, or a rule drifted)'
    print(f"cube check: cube {n:,} settled {u:+.2f}u, here {d['n']:,} settled {d['u']:+.2f}u{flag}")


if __name__ == '__main__':
    snapshot()
