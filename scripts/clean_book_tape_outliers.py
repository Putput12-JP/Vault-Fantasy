#!/usr/bin/env python3
"""One-off repair of the stored book tape (data/book_tape/<sport>/*.jsonl).

Action Network sometimes gave one book (BetMGM almost always) another period's total or spread, e.g. a 115.5 total on a 232 game, and the
tape recorded it as that book's line. The chart drew a spike to it and the Y axis stretched to fit. The collectors now drop such a line at
ingestion (fetch-sharp-money.mjs, prop_board.py game_markets); this removes the ones already stored.

A US book's total is dropped when it is more than 15% off the game's consensus total at that time, and its spread when it is more than 10
points off the consensus spread. Consensus is the latest Consensus row at or before the row; no Consensus row yet = left alone, so nothing is
judged against a number that was not known. Only the bad vector is removed (ml and the other vector stay); a row left with nothing is deleted.
Pinnacle, Consensus, Open, Novig and Kalshi rows are never touched. Idempotent.
usage: clean_book_tape_outliers.py [--dry]"""
import collections, glob, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KEEP = ('Pinnacle', 'Consensus', 'Open', 'Novig', 'Kalshi')


def game_key(r):
    return r.get('gk') or (r['away'], r['home'], r['start'])


def clean(path, dry):
    rows = []
    for line in open(path):
        try:
            rows.append(json.loads(line))
        except ValueError:
            rows.append(line)                           # a torn line is kept as it is
    ref = {}                                            # game -> (consensus total, consensus spread), updated in file order (rows are in time order)
    n_tot = n_sp = n_gone = 0
    out = []
    for r in rows:
        if not isinstance(r, dict) or 'book' not in r:
            out.append(r)
            continue
        k = game_key(r)
        if r['book'] == 'Consensus':
            cur = ref.get(k, (None, None))
            ref[k] = ((r['tot'][0] if r.get('tot') else cur[0]), (r['sp'][0] if r.get('sp') else cur[1]))
        elif r['book'] not in KEEP and k in ref:
            ct, cs = ref[k]
            if r.get('tot') and ct is not None and abs(r['tot'][0] - ct) > 0.15 * ct:
                r['tot'] = None
                n_tot += 1
            if r.get('sp') and cs is not None and abs(r['sp'][0] - cs) > 10:
                r['sp'] = None
                n_sp += 1
            if not r.get('ml') and not r.get('sp') and not r.get('tot'):
                n_gone += 1
                continue
        out.append(r)
    if (n_tot or n_sp) and not dry:
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            for r in out:
                f.write((json.dumps(r, separators=(',', ':')) if isinstance(r, dict) else r.rstrip('\n')) + '\n')
        os.replace(tmp, path)
    return n_tot, n_sp, n_gone


if __name__ == '__main__':
    dry = '--dry' in sys.argv
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'book_tape', '*', '*.jsonl'))):
        t, s, g = clean(p, dry)
        if t or s:
            print(f"{os.path.relpath(p, ROOT)}: {t} totals and {s} spreads dropped, {g} empty rows deleted")
