#!/usr/bin/env python3
"""Recorder watchdog. Reads the nba-data branch (snapshots/<day>/polls.jsonl) and finds every source whose most
recent MIN_FAILS polls ALL failed. Writes the report to --out as markdown (empty file = healthy); the workflow
turns that into a GitHub issue. A single bad poll never trips it: only a source that keeps failing does."""
import json, subprocess, sys, datetime as dt

MIN_FAILS = 6          # ~1.5h at the 15 min cadence, 30 min inside 3h of a tip


def git(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True).stdout


def main():
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'watch.md'
    subprocess.run(['git', 'fetch', '-q', 'origin', 'nba-data'], check=False)
    days = sorted(l.rsplit('/', 1)[-1] for l in git('ls-tree', '--name-only', 'origin/nba-data:snapshots').split() if l[:2] == '20')
    polls = []
    for d in days[-2:]:
        polls += [json.loads(l) for l in git('show', f'origin/nba-data:snapshots/{d}/polls.jsonl').splitlines() if l.strip()]
    by = {}
    for p in sorted(polls, key=lambda p: p['t']):
        by.setdefault(p['src'], []).append(p)
    bad = []
    for src, rows in by.items():
        tail = rows[-MIN_FAILS:]
        if len(tail) == MIN_FAILS and not any(r.get('ok') for r in tail):
            since = tail[0]['t']
            for r in reversed(rows):
                if r.get('ok'):
                    break
                since = r['t']
            bad.append((src, since, tail[-1].get('err', '')))
    if not bad:
        open(out, 'w').close()
        print('recorder healthy')
        return
    md = ['Sources failing on every one of their last %d polls:\n' % MIN_FAILS]
    for src, since, err in bad:
        md.append(f"- **{src}**: failing since {dt.datetime.fromtimestamp(since, dt.timezone.utc):%Y-%m-%d %H:%M} UTC. Last error: `{err[:300]}`")
    md.append('\nWhere to look: `nba/scripts/snapshot.py` (`curl`, the `src_*` pollers) and `nba/scripts/sharp.py` (`poll_tapes`). '
              'Reproduce with `python3 nba/scripts/snapshot.py --dir=<nba-data checkout>` and fix the poller.')
    open(out, 'w').write('\n'.join(md))
    print('\n'.join(md))


main()
