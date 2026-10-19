#!/usr/bin/env python3
"""Daily append-only copy of the Sharp Money ledgers, so no single bad publish can erase the graded history.

The live ledgers are carried forward run to run and published to `sharp-data`, which is force-pushed as ONE commit. That is fine for the page, but
each ledger then has exactly one copy. This writes the ledgers into a checkout of the ordinary (never force-pushed) `sharp-history` branch, where
the git history is the append-only log.

Ledgers:
  prop_plays.json        every prop board call, first sight to settlement (keyed by id)
  picks_ledger.json      the graded bet-signal picks and the dropped sharp-only reads, taken from data.json (keyed game|market|side)
  ev_alert_history.json  every graded +EV alert (keyed by key)
  prop_close_tape.json   every book's last read before kickoff (keyed season|pid|market|date)
  v2_plays.json          every Sharp Money V2 play, written once at first sight and frozen (keyed by pick), then settled

Guard (nothing is written if any check fails, exit code 2, and the previous snapshot stays as it was):
  - an id in the previous snapshot must still exist, except tape entries older than the tape's own 150-day prune
  - a settled play/pick (won, lost, push, void, or result 1/-1/0) must not go back to open
  - a V2 play's first-sight record (`first`, `firstSeen`, `start`) must not change once written

usage: snapshot_sharp_ledgers.py --src DIR_WITH_SHARP_DATA_FILES --dest CHECKOUT_OF_sharp-history [--today YYYY-MM-DD]"""
import argparse, datetime as dt, json, os, sys

TAPE_PRUNE_DAYS = 150
FROZEN = ('first', 'firstSeen', 'start')      # what a V2 play looked like when it was first seen
LEDGERS = ('prop_plays.json', 'picks_ledger.json', 'ev_alert_history.json', 'prop_close_tape.json', 'v2_plays.json')
MAY_BE_EMPTY = ('v2_plays.json',)     # a forward log starts with no rows; the four older ledgers are never empty


def load(path):
    with open(path) as f:
        return json.load(f)


def picks_ledger(data):
    return dict(ts=data.get('ts'), picks=data.get('picks') or [], sharpContext=data.get('sharpContext') or [])


def pick_id(p):
    return '|'.join(str(p.get(k)) for k in ('game', 'm', 'side', 'hline', 'line'))


def ids_of(name, doc):
    """{id: settled?} for one ledger."""
    if name in ('prop_plays.json', 'v2_plays.json'):
        return {k: v.get('status') in ('won', 'lost', 'push', 'void') for k, v in (doc.get('plays') or {}).items()}
    if name == 'picks_ledger.json':
        out = {}
        for part in ('picks', 'sharpContext'):
            for p in doc.get(part) or []:
                out[part[0] + ':' + pick_id(p)] = p.get('result') in (1, -1, 0)
        return out
    if name == 'ev_alert_history.json':
        return {e.get('key') or e.get('id'): e.get('result') in (1, -1, 0) for e in doc.get('entries') or []}
    if name == 'prop_close_tape.json':
        return {k: bool(v.get('frozen')) for k, v in (doc.get('props') or {}).items()}
    raise ValueError(name)


def tape_old(key, today):
    """True if a tape key (season|pid|market|YYYY-MM-DD) is old enough that the tape's own prune may have dropped it."""
    try:
        d = dt.date.fromisoformat(key.rsplit('|', 1)[1])
    except (ValueError, IndexError):
        return False
    return (today - d).days > TAPE_PRUNE_DAYS


def check(name, old, new, today):
    """Problems moving from the previous snapshot to this one (empty list = safe to write)."""
    a, b = ids_of(name, old), ids_of(name, new)
    bad = []
    lost = [k for k in a if k not in b and not (name == 'prop_close_tape.json' and tape_old(k, today))]
    if lost:
        bad.append(f'{name}: {len(lost)} ids in the previous snapshot are missing now, e.g. {lost[:3]}')
    back = [k for k in a if a[k] and k in b and not b[k]]
    if back:
        bad.append(f'{name}: {len(back)} settled rows went back to open, e.g. {back[:3]}')
    if name == 'v2_plays.json':
        old_p, new_p = old.get('plays') or {}, new.get('plays') or {}
        moved = [k for k in old_p if k in new_p and any(old_p[k].get(f) != new_p[k].get(f) for f in FROZEN)]
        if moved:
            bad.append(f'{name}: {len(moved)} plays changed their first-sight record, e.g. {moved[:3]}')
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True); ap.add_argument('--dest', required=True); ap.add_argument('--today')
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    docs = {}
    for n in LEDGERS:
        src = os.path.join(a.src, 'data.json' if n == 'picks_ledger.json' else n)
        if not os.path.exists(src):
            print(f'::warning::{src} missing, snapshot of {n} skipped')
            continue
        d = load(src)
        docs[n] = picks_ledger(d) if n == 'picks_ledger.json' else d
        if not ids_of(n, docs[n]) and n not in MAY_BE_EMPTY:
            sys.exit(f'{n} is empty: refusing to snapshot an empty ledger')
    problems = []
    for n, new in docs.items():
        prev = os.path.join(a.dest, n)
        if os.path.exists(prev):
            problems += check(n, load(prev), new, today)
    if problems:
        print('::error::snapshot refused, the ledgers lost history:\n' + '\n'.join(problems))
        sys.exit(2)
    for n, d in docs.items():
        tmp = os.path.join(a.dest, n + '.tmp')
        with open(tmp, 'w') as f:
            json.dump(d, f, separators=(',', ':'))
        os.replace(tmp, os.path.join(a.dest, n))
    print('snapshot written: ' + ', '.join(f'{n} ({len(ids_of(n, d))})' for n, d in docs.items()))


if __name__ == '__main__':
    main()
