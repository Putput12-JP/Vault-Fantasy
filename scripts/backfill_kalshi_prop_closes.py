#!/usr/bin/env python3
"""Rebuild Kalshi prop closes for settled NFL props from the git history of data/kalshi_props.json.

data/kalshi_props.json is committed hourly, so every past week's Kalshi ladder is still in git. For each settled
prop in data/bet_results.json this finds the last commit made BEFORE that game's kickoff whose file still carries the
player's ladder for the same game, and writes it in the prop close tape format (books.Kalshi only):

    data/kalshi_prop_closes_backfill.json

Pinnacle and Novig have no history to replay (the prop feed keeps one consensus line, and the Novig file overwrites
itself), so this backfill can only test Kalshi against the consensus close. The live tape covers all three from here.

Matching a ladder to a game: Kalshi tickers carry the game date (KXNFLRECYDS-26OCT15SEADEN-...), and a week's file
holds only that week's slate, but a ladder can outlive its game for a few hours, so the ticker date must be within a
day of the kickoff's Eastern date.

  python3 scripts/backfill_kalshi_prop_closes.py [--since 2026-09-01] [--out PATH]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from prop_close_lib import nkey
from build_prop_close_tape import tape_key

ET = ZoneInfo('America/New_York')
MON = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
TICKER_DATE = re.compile(r'-(\d\d)([A-Z]{3})(\d\d)')


def git(*args):
    return subprocess.run(['git', '-C', ROOT, *args], capture_output=True, text=True, check=True).stdout


def ticker_date(tk):
    m = TICKER_DATE.search(tk or '')
    if not m or m.group(2) not in MON:
        return None
    return dt.date(2000 + int(m.group(1)), MON[m.group(2)], int(m.group(3)))


def snapshots(since):
    """[(epoch, {market: {nkey: [rows]}})] oldest first, one per commit that touched the file."""
    log = git('log', '--reverse', '--format=%H %ct', f'--since={since}', '--', 'data/kalshi_props.json').split('\n')
    out = []
    for line in filter(None, log):
        sha, ct = line.split()
        try:
            blob = json.loads(git('show', f'{sha}:data/kalshi_props.json'))
        except (subprocess.CalledProcessError, ValueError):
            continue
        t = dt.datetime.fromisoformat(blob['generated'].replace('Z', '+00:00')).timestamp() if blob.get('generated') else float(ct)
        out.append((t, blob.get('markets') or {}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='2026-09-01')
    ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'kalshi_prop_closes_backfill.json'))
    a = ap.parse_args()
    import settle_bets
    kickoffs = settle_bets.load_kickoffs()
    results = json.load(open(os.path.join(ROOT, 'data', 'bet_results.json')))['props']
    snaps = snapshots(a.since)
    print(f'{len(snaps)} Kalshi snapshots from git since {a.since}')
    props, missing_ko, no_ladder = {}, 0, 0
    for r in results:
        if (r.get('seasonType') or '').lower() == 'pre':
            continue
        ko = kickoffs.get((str(r['season']), str(r['week']), settle_bets.team_nfl(r.get('team'))))
        if not ko:
            missing_ko += 1
            continue
        key = tape_key(r['season'], r['pid'], r['market'], ko)
        if key in props:
            continue
        kt = dt.datetime.fromisoformat(ko.replace('Z', '+00:00'))
        kday = kt.astimezone(ET).date()
        nk, best = nkey(r.get('name')), None
        for t, markets in snaps:
            if t >= kt.timestamp():
                break
            rows = (markets.get(r['market']) or {}).get(nk)
            if not rows:
                continue
            d = ticker_date(rows[0].get('tk'))
            if d is None or abs((d - kday).days) > 1:
                continue
            best = (t, rows)
        if not best:
            no_ladder += 1
            continue
        props[key] = {'season': str(r['season']), 'pid': r['pid'], 'market': r['market'],
                      'name': r.get('name'), 'team': r.get('team'), 'commence': ko,
                      'books': {'Kalshi': {'t': int(best[0]), 'ladder': [[x['k'], x['fair'], x.get('oi'), x.get('spr')] for x in best[1] if x.get('fair') is not None]}},
                      'frozen': True, 'source': 'git-replay'}
    json.dump({'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'source': 'git-replay of data/kalshi_props.json',
               'props': props}, open(a.out, 'w'), separators=(',', ':'))
    print(f'wrote {len(props)} props to {a.out} (no kickoff {missing_ko}, no Kalshi ladder before kickoff {no_ladder})')


if __name__ == '__main__':
    main()
