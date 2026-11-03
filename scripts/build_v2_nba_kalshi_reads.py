#!/usr/bin/env python3
"""
Kalshi's quote at first sight for every NBA prop row in the three V2 ledgers -> data/v2_nba_kalshi_reads.json.

Rule C (sharp-money/v2/gates.js, GATES.NBA_FAIR_AGREE) plays an NBA prop only when Kalshi is quoting the line. Rows logged since the rule
shipped store that as first.price.kal; this file lets heldBack() re-score the rows logged before it, from the same raw recorder data the
board was built from (nba-data branch, snapshots/<day>/kalshi.jsonl and meta.jsonl, nba/scripts/snapshot.py).

A read counts only if it was stored AT OR BEFORE firstSeen (never after: that would use information the play did not have), on the
contract for this player, stat, line and game date. gates.js then needs a two-sided quote no wider than MAX_EXCH_SPREAD, the same test
the live board uses. No read is stored as null: Kalshi absent.

  python3 scripts/build_v2_nba_kalshi_reads.py      # reads origin/sharp-data and origin/nba-data via git (git fetch first)

Output: {v, cutoff, built, rows: {ledger id: [bid, ask, read time] | null}}. The bid and ask are for the Over (Kalshi's "N+" contract).
"""
import bisect, datetime as dt, json, os, re, subprocess, sys, time
from collections import defaultdict
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'v2_nba_kalshi_reads.json')
ET = ZoneInfo('America/New_York')            # Kalshi's event codes carry the game date in Eastern time
KAL = {'KXNBAPTS': 'pts', 'KXNBAREB': 'reb', 'KXNBAAST': 'ast', 'KXNBA3PT': '3pm', 'KXNBAPRA': 'pra', 'KXNBAPR': 'pr', 'KXNBAPA': 'pa', 'KXNBARA': 'ra'}
nk = lambda s: re.sub(r'[^a-z]', '', (s or '').lower().replace(' jr', '').replace(' iii', '').replace(' ii', ''))


def show(ref, path):
    p = subprocess.run(['git', '-C', ROOT, 'show', f'{ref}:{path}'], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def jsonl(text):
    for line in (text or '').splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            continue                          # a torn last line


def load_day(day, cache={}):
    """Kalshi reads and contract meta for one recorder day: {(name, stat, floor, date code): [(t, bid, ask)]}."""
    if day in cache:
        return cache[day]
    meta = {m['k']: m for m in jsonl(show('origin/nba-data', f'snapshots/{day}/meta.jsonl')) if m.get('src') == 'kalshi'}
    out = defaultdict(list)
    for r in jsonl(show('origin/nba-data', f'snapshots/{day}/kalshi.jsonl')):
        m = meta.get(r['k'])
        st = m and KAL.get(m.get('series'))
        if not st or m.get('floor') is None or not r.get('v'):
            continue
        key = (nk((m.get('sub') or '').split(':')[0]), st, float(m['floor']), m['event'].split('-')[1][:7])
        out[key].append((r['t'], r['v'][0], r['v'][1]))
    cache[day] = out
    return out


def main():
    rows = {}
    for f in ('v2_plays.json', 'v2_watch.json', 'v2_passed.json'):
        L = json.loads(show('origin/sharp-data', f) or '{"plays":{}}')
        for r in L['plays'].values():
            if r.get('sport') == 'nba' and r.get('kind') == 'prop' and r.get('prop'):
                rows[r['id']] = r
    out, n = {}, 0
    for id_, r in rows.items():
        P, t = r['prop'], r['firstSeen']
        start = dt.datetime.fromtimestamp(r['start'], ET)
        code = start.strftime('%y%b%d').upper()
        key = (nk(P['name']), P['mkt'], float(P['line']), code)
        hist = []
        for d in (start.date() - dt.timedelta(days=1), start.date()):   # lines post a day early
            hist += load_day(d.isoformat()).get(key, [])
        hist.sort()
        i = bisect.bisect_right([x[0] for x in hist], t) - 1
        v = hist[i] if i >= 0 else None
        if v and v[1] is not None and v[2] is not None:
            out[id_] = [v[1], v[2], v[0]]
            n += 1
        else:
            out[id_] = None
    cutoff = max((r['firstSeen'] for r in rows.values()), default=0)
    json.dump({'v': 1, 'cutoff': cutoff, 'built': int(time.time()), 'rows': dict(sorted(out.items()))}, open(OUT, 'w'), separators=(',', ':'))
    print(f'{len(rows)} NBA prop rows, {n} with a Kalshi read at first sight, {len(rows) - n} without; cutoff {cutoff}')


if __name__ == '__main__':
    sys.exit(main())
