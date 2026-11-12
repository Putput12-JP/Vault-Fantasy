#!/usr/bin/env python3
"""Reopen Sharp Money V2 game rows that were voided only because no final score was stored, once a final is stored.

scripts/track-v2-plays.mjs voids a game row (kind book or exch) 72h after tip when data/exchange_edge_results.json has no final for it, and a
void is never looked at again. Until Nov 12 2026 scripts/backfill_edge_results.py could not match ESPN's short NBA codes (SA, GS, NY, NO, UTAH),
so every NBA game with the Spurs, Warriors, Knicks, Pelicans or Jazz that the live feed missed went void instead of being graded.

This sets such a row back to open, stamped regraded {from: 'void', at}, and the track-v2-plays.mjs run right after it settles the row from the
stored final with its own arithmetic. A game row is only ever voided for a missing final, so a void game row with a final stored is always this
case. Prop rows are not touched. Run it after the results backfill and before track-v2-plays.mjs:

  python3 scripts/reopen_v2_game_voids.py --dir sharp-out [--results data/exchange_edge_results.json]
"""
import argparse
import json
import os
import time

FILES = ('v2_plays.json', 'v2_watch.json', 'v2_passed.json')


def reopen(ledger, results, now):
    n = 0
    for p in (ledger.get('plays') or {}).values():
        gk = (p.get('game') or {}).get('gk')
        if p.get('status') == 'void' and p.get('kind') in ('book', 'exch') and gk in results and not p.get('regraded'):
            p['status'] = 'open'
            p.pop('settledAt', None)
            p.pop('units', None)
            p['regraded'] = {'from': 'void', 'at': int(now)}
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--results', default=os.path.join(os.path.dirname(__file__), '..', 'data', 'exchange_edge_results.json'))
    a = ap.parse_args()
    try:
        results = json.load(open(a.results))
    except (OSError, ValueError):
        return
    now = time.time()
    for f in FILES:
        fp = os.path.join(a.dir, f)
        if not os.path.exists(fp):
            continue
        L = json.load(open(fp))            # a ledger that does not parse stops here; it is never replaced
        n = reopen(L, results, now)
        if n:
            json.dump(L, open(fp, 'w'), separators=(',', ':'))
            print(f'{f}: {n} game rows voided for a missing final reopened; settled from the stored final this run')


if __name__ == '__main__':
    main()
