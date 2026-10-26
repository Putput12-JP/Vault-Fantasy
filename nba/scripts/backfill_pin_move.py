#!/usr/bin/env python3
"""Add the `move` field (sharp.pin_move) to every stored 'behind' alert that lacks one, from the Pinnacle series in the
snapshot folders, cut at the alert's own time so it shows what was known then. Idempotent. A game whose Pinnacle rows are
gone, an alternate number, or a market with no earlier row keeps move = None: nothing is guessed.
usage: backfill_pin_move.py <data root, the folder that holds snapshots/> [--dry]"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sharp

CONSISTENT = 0.02            # rebuilt Pinnacle chance must match the alert's stored fair to 2 points


def main(root, dry=False):
    paths = sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'signals.json')))
    done = filled = 0
    for p in paths:
        sig = json.load(open(p))
        todo = [a for a in sig.values() if a['type'] == 'behind' and 'move' not in a]
        if not todo:
            continue
        day = os.path.basename(os.path.dirname(p))
        dirs = sorted(d for d in glob.glob(os.path.join(root, 'snapshots', '20*')) if os.path.basename(d) <= day)[-4:]
        gmap = {(a['tday'], a['hn']): a['g'] for a in todo if a.get('tday') and a.get('hn')}
        tips = {a['g']: a['tip'] for a in todo if a.get('tip')}
        pins, _ = sharp.pin_replay(dirs, gmap, tips)
        for a in todo:
            S = [r for r in (pins.get(a['g']) or {}).get('series', []) if r[0] <= a['t']]
            a['move'] = sharp.pin_move(S, a['m'], a['side'], a['line'])
            if a['move'] and abs(a['move']['p1'] - a['fair']) > CONSISTENT:   # the rebuilt row is not the price the alert used: drop, don't guess
                a['move'] = None
            done += 1
            filled += a['move'] is not None
        if not dry:
            json.dump(sig, open(p, 'w'), separators=(',', ':'))
    print(f'{done} behind alerts checked, {filled} got a move, {done - filled} left None')


if __name__ == '__main__':
    main(sys.argv[1], '--dry' in sys.argv)
