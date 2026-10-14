#!/usr/bin/env python3
"""Prop close tape: the last pre-kickoff read of every book that prices an NFL player prop.

Why: the graded record only keeps a consensus close, so "does the Novig / Kalshi / Pinnacle close beat the others"
could not be answered per book. This keeps one entry per prop and refreshes each book's read until kickoff, then
freezes it. The last read before kickoff IS that book's close.

Inputs (all already produced by the Sharp Money job, so no new network calls):
  --feed    lineup-feed.json      priced quotes per book (Pinnacle, FanDuel, DraftKings, ...) and each prop's kickoff
  --kalshi  kalshi_props.json     P(over k) ladder per player and market
  --novig   novig_props.json      same shape, from the Novig order books
  --tape    prop_close_tape.json  read, updated in place, written back

Rules:
  - A book that is missing from this run keeps its last read (a thin response never wipes a close).
  - A prop past its kickoff is frozen: nothing new is written to it.
  - A book read stamped at or after kickoff is dropped (a live price is not a close).
  - A prop with no priced book and no ladder is not stored.
  - A tape file that exists but does not parse stops the run. It is never silently reset, because the tape is the
    only copy of the history.

  python3 scripts/build_prop_close_tape.py --feed F --kalshi K --novig N --tape T
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prop_close_lib import nkey

PRUNE_DAYS = 150
PICKEM = {'PrizePicks', 'Underdog Fantasy', 'Sleeper', 'Underdog', 'Fliff'}   # flat-priced apps carry no two-way price
STAMP = '%Y-%m-%dT%H:%M:%S'


def iso_s(s):
    """ISO-8601 'Z' string -> epoch seconds, or None."""
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def tape_key(season, pid, market, commence):
    """season|pid|market|kickoff date (UTC). Keyed on the game, never on the feed's week number: lineup-feed.json keeps
    last week's number until the Wednesday rollover while already carrying next week's games, and one prop would then
    live under two keys."""
    return f'{season}|{pid}|{market}|{str(commence)[:10]}'


def load(path, required=False):
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        if required:
            raise SystemExit(f'missing input: {path}')
        return None
    with open(path) as f:
        try:
            return json.load(f)
        except ValueError as e:
            raise SystemExit(f'{path} exists but does not parse ({e}); refusing to overwrite it')


def ladder_rows(rows, src):
    """Kalshi row {k, fair, oi, spr}; Novig row {k, fair, spr, depth, t}. Compact to lists, newest read time kept."""
    out, newest = [], None
    for r in rows or []:
        if r.get('k') is None or r.get('fair') is None:
            continue
        if src == 'Kalshi':
            out.append([r['k'], r['fair'], r.get('oi'), r.get('spr')])
        else:
            out.append([r['k'], r['fair'], r.get('spr'), r.get('depth')])
            if r.get('t'):
                newest = max(newest or 0, r['t'])
    return out, newest


def update(tape, feed, kalshi, novig, now):
    """Fold one run into the tape in place. Returns counts for the log line."""
    season = str(feed.get('season'))
    if (feed.get('season_type') or '').lower() == 'pre':
        return {'props': 0, 'skipped': 'preseason'}
    kal_t = iso_s((kalshi or {}).get('generated')) or now
    stats = {'props': 0, 'new': 0, 'frozen': 0, 'with_kalshi': 0, 'with_novig': 0, 'with_pinnacle': 0}
    for pid, rec in (feed.get('vegas_player_props') or {}).items():
        commence = iso_s(rec.get('commence'))
        if commence is None:
            continue
        for market, line in (rec.get('lines') or {}).items():
            key = tape_key(season, pid, market, rec.get('commence'))   # not the feed's `week`: it lags the schedule by days
            cur = tape['props'].get(key)
            if now >= commence:
                if cur:
                    cur['frozen'] = True
                    stats['frozen'] += 1
                continue
            reads = {}
            for q in line.get('quotes') or []:
                if q.get('book') in PICKEM or q.get('over') is None or q.get('under') is None or q.get('line') is None:
                    continue
                reads[q['book']] = {'line': q['line'], 'over': q['over'], 'under': q['under'], 't': int(now)}
            nk = nkey(rec.get('name'))
            kl, _ = ladder_rows((((kalshi or {}).get('markets') or {}).get(market) or {}).get(nk), 'Kalshi')
            if kl:
                reads['Kalshi'] = {'ladder': kl, 't': int(kal_t)}
            nl, nt = ladder_rows((((novig or {}).get('markets') or {}).get(market) or {}).get(nk), 'Novig')
            if nl:
                reads['Novig'] = {'ladder': nl, 't': int(nt or iso_s((novig or {}).get('generated')) or now)}
            reads = {b: r for b, r in reads.items() if r['t'] < commence}
            if not reads and not cur:
                continue
            if cur is None:
                cur = tape['props'][key] = {'season': season, 'pid': pid, 'market': market,
                                            'name': rec.get('name'), 'team': rec.get('team'),
                                            'commence': rec.get('commence'), 'books': {}}
                stats['new'] += 1
            cur['commence'] = rec.get('commence') or cur.get('commence')
            cur['books'].update(reads)
            stats['props'] += 1
            for b, tag in (('Kalshi', 'with_kalshi'), ('Novig', 'with_novig'), ('Pinnacle', 'with_pinnacle')):
                stats[tag] += b in cur['books']
    cutoff = now - PRUNE_DAYS * 86400
    for k in [k for k, v in tape['props'].items() if (iso_s(v.get('commence')) or now) < cutoff]:
        del tape['props'][k]
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed', required=True)
    ap.add_argument('--kalshi')
    ap.add_argument('--novig')
    ap.add_argument('--tape', required=True)
    ap.add_argument('--now', type=float, help='epoch seconds, for tests')
    a = ap.parse_args()
    now = a.now if a.now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    feed = load(a.feed, required=True)
    tape = load(a.tape) or {'props': {}}
    tape.setdefault('props', {})
    st = update(tape, feed, load(a.kalshi), load(a.novig), now)
    tape['generated'] = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime(STAMP) + 'Z'
    tmp = a.tape + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(tape, f, separators=(',', ':'))
    os.replace(tmp, a.tape)
    print('prop close tape:', json.dumps(st), f'total={len(tape["props"])}')


if __name__ == '__main__':
    main()
