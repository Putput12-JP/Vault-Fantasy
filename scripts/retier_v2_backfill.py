#!/usr/bin/env python3
"""Re-tier data/v2_backfill.json under the strict gates (sharp-money/v2/gates.js MIN_PRICE and EARLY_H).

A backfilled play whose stored first-sight price is under 55%, or that was first seen 48h or more before the game, is a Pass now, so it moves
from `plays` to `passed`. Nothing is recomputed: price, result, units, CLV and first-sight fields are copied as stored. Only the id prefix (bfp|play| to
bfp|pass|, bf|play| to bf|pass|) and `first.why` change. Idempotent: a second run moves nothing. The moved ids are listed under `retiered` so the old
record can be reproduced.

usage: retier_v2_backfill.py [--file data/v2_backfill.json]"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_PRICE, EARLY_H = 0.55, 48


def fails(p):
    """The gates a stored play fails at first sight: [] if it still qualifies."""
    out = []
    px = (p.get('first') or {}).get('price') or {}
    if px.get('p') is not None and px['p'] < MIN_PRICE:
        out.append('price')
    hrs = (p['start'] - p['firstSeen']) / 3600 if p.get('start') is not None and p.get('firstSeen') is not None else p.get('hoursEarly')
    if hrs is not None and hrs >= EARLY_H:
        out.append('early')
    return out


def retier(B):
    """Move failing plays to passed in place. Returns the list of moved {from, to, gates}."""
    moved = []
    for pid in list(B.get('plays', {})):
        p = B['plays'][pid]
        g = fails(p)
        if not g:
            continue
        new = pid.replace('|play|', '|pass|', 1)
        q = dict(p, id=new)
        q['first'] = dict(p['first'], why=('price under 55%' if 'price' in g else '') + (' and ' if len(g) == 2 else '') + ('called 48h or more out' if 'early' in g else ''))
        B['passed'][new] = q
        del B['plays'][pid]
        moved.append({'from': pid, 'to': new, 'gates': g})
    if moved:
        B.setdefault('retiered', []).extend(moved)
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default=os.path.join(ROOT, 'data', 'v2_backfill.json'))
    a = ap.parse_args()
    with open(a.file) as f:
        B = json.load(f)
    moved = retier(B)
    with open(a.file + '.tmp', 'w') as f:
        json.dump(B, f, indent=1)
    os.replace(a.file + '.tmp', a.file)
    print('moved %d play(s) to passed; %d plays left' % (len(moved), len(B['plays'])))


if __name__ == '__main__':
    main()
