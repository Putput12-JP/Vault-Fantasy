#!/usr/bin/env python3
"""Recorder watchdog. Reads the nba-data branch (snapshots/<day>/polls.jsonl, status.json) and reports what is wrong, as markdown in --out
(empty file = healthy); the workflow turns that into a GitHub issue.

  1. Sources: every source whose most recent MIN_FAILS polls ALL failed. A single bad poll never trips it: only a source that keeps failing does.
     'ledger' is one of those sources (the recorder logs one poll record for its shadow ledger and the settlement that follows it).
  2. Stale: the newest poll in status.json is older than STALE_H hours (the recorder is not running, or cannot push).
  3. Flags: every 'bad' flag the recorder itself raised in status.json (snapshot.write_flags: a game with no Minutes Lab or simulation rows, a game
     that tipped 8+ hours ago and is still not settled, a ledger failing for 3 polls).

Which days: the LAST TWO DAYS THAT HAVE A polls.jsonl. snapshots/ also holds folders for days that have not happened yet (the recorder writes a
game's closing prices under its tip day, up to 3 days ahead), and those hold no polls. Reading "the last two folders" read only those: from
2026-10-19 22:30 UTC on the watchdog saw no polls, said "recorder healthy", and the shadow ledger failed every poll for 27 hours before it spoke up.
"""
import json, subprocess, sys, time, datetime as dt

LINEUPS_FROM_UTC = 11   # see failing(): the lineups feed 403s until about 10:00 UTC
MIN_FAILS = 6          # ~1.5h at the 15 min cadence, 30 min inside 3h of a tip
STALE_H = 3            # newest poll older than this: the recorder is down (Data Health calls it Down after 6 h; GitHub's hourly tick is best-effort)
DAYS_READ = 2          # days with polls to read


def git(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True).stdout


def days_with_polls(names, has_polls, n=DAYS_READ):
    """The last n day folders (newest first, then returned oldest first) that hold polls.jsonl. has_polls(day) -> bool."""
    out = []
    for d in sorted((x for x in names if x[:2] == '20'), reverse=True):
        if has_polls(d):
            out.append(d)
            if len(out) == n:
                break
    return sorted(out)


def lineups_expected(status, now):
    """True when a game of today's ET date has not tipped yet, so NBA.com's lineup file should be up. The file is posted on the game day (about
    10:00 UTC), never the day before: on a day with no game, or once the day's last game has tipped, it answers 403 all day and that is not an outage."""
    from zoneinfo import ZoneInfo
    today = dt.datetime.fromtimestamp(now, ZoneInfo('America/New_York')).date().isoformat()
    return any(g.get('day') == today and g.get('tip', 0) > now for g in (status or {}).get('games') or [])


def failing(polls, min_fails=MIN_FAILS, lineups=True):
    """[(source, since, last error)] for every source whose last `min_fails` polls all failed. lineups=False leaves the lineups source out."""
    by = {}
    for p in sorted(polls, key=lambda p: p['t']):
        by.setdefault(p['src'], []).append(p)
    # NBA.com's lineup file does not exist until about 6am ET: the feed answers 403 every night, which is "not posted yet",
    # not an outage (it opened a data-failure issue on three nights running). Only count lineups polls from 11:00 UTC on.
    if 'lineups' in by and not lineups:
        del by['lineups']
    if 'lineups' in by:
        by['lineups'] = [r for r in by['lineups'] if dt.datetime.fromtimestamp(r['t'], dt.timezone.utc).hour >= LINEUPS_FROM_UTC]
        if not by['lineups']:
            del by['lineups']
    bad = []
    for src, rows in by.items():
        tail = rows[-min_fails:]
        if len(tail) == min_fails and not any(r.get('ok') for r in tail):
            since = tail[0]['t']
            for r in reversed(rows):
                if r.get('ok'):
                    break
                since = r['t']
            bad.append((src, since, tail[-1].get('err', '')))
    return bad


def behind(status, changed):
    """One line when the running recorder's commit is missing recorder code that main has, else ''. changed: files that differ between status['code'] and main."""
    files = [f for f in changed if f.startswith('nba/scripts/')]
    if not (status or {}).get('code') or not files:
        return ''
    return (f"\nThe recorder is running commit `{status['code'][:7]}`, which lacks {len(files)} recorder file(s) changed on main since "
            f"({', '.join(f.rsplit('/', 1)[-1] for f in files[:5])}). A merge reaches it only when its run hands off (up to 5.5 h) or the run is restarted.")


def report(bad, status, now, stale_h=STALE_H, behind_note=''):
    """Markdown for the issue, or '' when healthy. status: the parsed status.json or None."""
    md = []
    if bad:
        md.append('Sources failing on every one of their last %d polls:\n' % MIN_FAILS)
        for src, since, err in bad:
            md.append(f"- **{src}**: failing since {dt.datetime.fromtimestamp(since, dt.timezone.utc):%Y-%m-%d %H:%M} UTC. Last error: `{err[:300]}`")
    if status and status.get('t') and now - status['t'] > stale_h * 3600:
        md.append(f"\nThe newest poll is {int((now - status['t']) // 3600)} hours old ({dt.datetime.fromtimestamp(status['t'], dt.timezone.utc):%Y-%m-%d %H:%M} UTC). "
                  'The recorder is not running or cannot push. Check the `NBA snapshots` workflow.')
    flags = [f for f in (status or {}).get('flags') or [] if f.get('level') == 'bad' and f.get('kind') != 'ledger_failing']   # ledger_failing is the 'ledger' source above
    if flags:
        md.append('\nThe recorder raised these itself (Data Health, Needs attention):\n')
        md += [f"- {f.get('text', f.get('kind'))}" for f in flags]
    if md and behind_note:
        md.append(behind_note)
    if md:
        md.append('\nWhere to look: `nba/scripts/snapshot.py` (`curl`, the `src_*` pollers, `shadow`), `nba/scripts/ledger.py` (`log`, `settle`) and `nba/scripts/sharp.py` (`poll_tapes`). '
                  'Reproduce with `python3 nba/scripts/snapshot.py --dir=<nba-data checkout>` and fix the poller.')
    return '\n'.join(md)


def main():
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'watch.md'
    subprocess.run(['git', 'fetch', '-q', 'origin', 'nba-data'], check=False)
    names = git('ls-tree', '--name-only', 'origin/nba-data:snapshots').split()
    has = lambda d: subprocess.run(['git', 'cat-file', '-e', f'origin/nba-data:snapshots/{d}/polls.jsonl'], capture_output=True).returncode == 0
    days = days_with_polls(names, has)
    if not days:
        md = 'The watchdog found no day with a `polls.jsonl` on `nba-data` (the branch did not fetch, or the recorder has never run).'
        open(out, 'w').write(md)
        print(md)
        return
    polls = []
    for d in days:
        polls += [json.loads(l) for l in git('show', f'origin/nba-data:snapshots/{d}/polls.jsonl').splitlines() if l.strip()]
    try:
        status = json.loads(git('show', 'origin/nba-data:status.json') or 'null')
    except ValueError:
        status = None
    now = int(time.time())
    note = ''
    try:                                          # is the running recorder behind main? (informational: appended to an issue, never opens one alone)
        code = (status or {}).get('code')
        cmp = json.loads(subprocess.run(['gh', 'api', f'repos/{os.environ["GH_REPO"]}/compare/{code}...main', '--jq', '[.files[].filename]'], capture_output=True, text=True).stdout or '[]') if code and os.environ.get('GH_REPO') else []
        note = behind(status, cmp)
    except Exception:
        pass
    md = report(failing(polls, lineups=lineups_expected(status, now)), status, now, behind_note=note)
    if not md:
        open(out, 'w').close()
        print(f'recorder healthy (read {", ".join(days)}: {len(polls)} polls)')
        return
    open(out, 'w').write(md)
    print(md)


if __name__ == '__main__':
    main()
