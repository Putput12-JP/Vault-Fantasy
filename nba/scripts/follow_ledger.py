#!/usr/bin/env python3
"""
Sharp follow shadow ledger (Sharp Price V2). Rules frozen in docs/sharp-follow-prereg.md BEFORE any follow was graded.

Question: if a bettor copied a Polymarket account's NBA game-market ticket, at what delay and with what kind of order would
the copy have beaten the closing price? Nothing here is a bet. It logs hypothetical copies from data the recorder already
stores (the trade tape, the Polymarket bid / ask quotes, the poll log) and grades them against the close. No price is
invented: an entry is a stored ask (or the wallet's own stored price) and a close is a stored mid, else the row stays empty.

An EVENT is the first ticket of $1,000 or more by one wallet on one outcome of one game market (moneyline, spread, total),
before tip. Each event is logged for three cohorts (frozen when first seen): sharp (wallet in the scorecard's sharp list),
dull (usually-losing list), other (control: everyone else). Each event gets these follows:
  tk2 tk5 tk15 tk60  taker: buy at the stored ask at the first successful Polymarket poll >= delay after the ticket
                     (skipped if that poll is more than LATE_S past the delay: the quote would be stale)
  mk                 maker: a resting bid at the wallet's own price, placed at the first poll after the ticket, filled the
                     first time a stored ask is at or below that price before tip (a LOWER bound on fills: quotes are
                     change-only, polled every 5 to 15 minutes)
Grade, once the game has tipped and a poll answered in the last 30 minutes before tip: close = mid of the last stored quote
at or before tip with a bid and an ask. clv = close / entry - 1 (the sharp-money study's metric). Maker attempts that never
fill count as 0 in `val` (the primary metric), so adverse selection cannot hide in the fill rate.

CLI:  follow_ledger.py --root nba-data [--now T] [--report]   (--report prints counts and, only after the first look, results)
"""
import datetime as dt, glob, hashlib, json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sharp import wallets, day_dirs, ET                       # noqa: E402

# ── frozen in docs/sharp-follow-prereg.md ───────────────────────────────────────────────────────
MIN_USD = 1000                                                # first ticket this size or larger is an event
DELAYS = (120, 300, 900, 3600)                                # taker delays, seconds
LATE_S = 20 * 60                                              # a poll later than delay + this is too stale to price a copy
CLOSE_WINDOW_S = 30 * 60                                      # a poll must have answered this close to tip to grade
GRADE_AFTER_S = 3 * 3600
TYPES = ('moneyline', 'spreads', 'totals')
FREEZE_T = 1792689710                                          # unix seconds the rules were committed; earlier events are backfill
FIRST_TIP = 1792537200                                        # 2026-10-20T23:00Z, the first regular-season tip; earlier games are preseason
LOOKBACK_DAYS = 3
FILE = 'follows.json'


def load_jsonl(dirs, name):
    for d in dirs:
        p = os.path.join(d, name)
        if os.path.exists(p):
            for line in open(p):
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def load_follows(dirs):
    rows, where = {}, {}
    for d in dirs:
        p = os.path.join(d, FILE)
        if os.path.exists(p):
            try:
                j = json.load(open(p))
            except ValueError:
                continue
            for i, r in j.items():
                rows[i], where[i] = r, d
    return rows, where


def eid(w, k, o):
    return hashlib.sha1(f'{w}|{k}|{o}'.encode()).hexdigest()[:16]


def side_quote(row, o):
    """(bid, ask) for outcome o from a stored first-outcome quote [bid, ask, last]."""
    bid, ask = row[0], row[1]
    if o == 0:
        return bid, ask
    return (None if ask is None else round(1 - ask, 4)), (None if bid is None else round(1 - bid, 4))


def quote_at(qs, t):
    """The stored quote in force at t. Rows are change-only, so the last row at or before t is the current quote."""
    last = None
    for r in qs:
        if r[0] <= t:
            last = r
        else:
            break
    return last


def poll_after(polls, t):
    return next((p for p in polls if p >= t), None)


def follow_entries(ev, qs, polls, tip):
    """Entries for one event from stored data only. Returns {method: [entry price, actual delay s]} and the maker fill."""
    T, o = ev['t'], ev['o']
    out = {}
    for d in DELAYS:
        P = poll_after(polls, T + d)
        if P is None or P > T + d + LATE_S or P >= tip:
            continue
        q = quote_at(qs, P)
        if not q:
            continue
        ask = side_quote(q[1:], o)[1]
        if ask:
            out[f'tk{d // 60}'] = [round(ask, 4), P - T]
    mk = None
    P0 = poll_after(polls, T + 1)
    if P0 is not None and P0 < tip:
        for r in qs:
            if r[0] <= P0 or r[0] >= tip:
                continue
            ask = side_quote(r[1:], o)[1]
            if ask is not None and ask <= ev['px']:
                mk = [ev['px'], r[0] - T]
                break
        out['mk'] = mk                                         # None = never filled before tip (a counted zero)
    return out


def close_mid(qs, polls, tip, o):
    last = max((p for p in polls if tip - CLOSE_WINDOW_S <= p <= tip), default=None)
    if last is None:
        return None
    q = quote_at(qs, last)
    if not q:
        return None
    bid, ask = side_quote(q[1:], o)
    return None if bid is None or ask is None else round((bid + ask) / 2, 4)


def grade(ev, close):
    """clv per follow and the primary `val` (unfilled maker attempts count as 0)."""
    ev['close'] = close
    g = {}
    for m, e in ev['f'].items():
        if m == 'mk':
            if e is None:
                g[m] = {'fill': 0, 'clv': None, 'val': 0.0}
            else:
                c = round(close / e[0] - 1, 4)
                g[m] = {'fill': 1, 'clv': c, 'val': c}
        else:
            c = round(close / e[0] - 1, 4)
            g[m] = {'fill': 1, 'clv': c, 'val': c}
    ev['res'] = g


def run(root, now, W=None):
    """Log new events, resolve entries, grade finished games. Returns {'new': n, 'graded': n}."""
    W = W or wallets()
    dirs = day_dirs(root, now, LOOKBACK_DAYS)
    if not dirs:
        return {'new': 0, 'graded': 0}
    rows, where = load_follows(dirs)
    meta = {}
    for r in load_jsonl(dirs, 'meta.jsonl'):
        if r.get('src') == 'polymarket' and r.get('type') in TYPES and r.get('start'):
            meta[r['k']] = r
    quotes = defaultdict(list)
    for r in list(load_jsonl(dirs, 'polymarket.jsonl')) + list(load_jsonl(dirs, 'fastpm.jsonl')):      # fast_poll.py adds a quote every minute
        if r.get('v'):                                          # a null quote means the market left the feed
            quotes[r['k']].append((r['t'], *r['v']))
    for qs in quotes.values():
        qs.sort(key=lambda x: x[0])
    polls = sorted({r['t'] for r in load_jsonl(dirs, 'polls.jsonl') if r.get('src') == 'polymarket' and r.get('ok')}
                   | {r['t'] for r in load_jsonl(dirs, 'fastpoll.jsonl') if r.get('qok')})
    gen = 0
    try:
        gen = dt.datetime.fromisoformat((W.get('generated') or '').replace('Z', '+00:00')).timestamp()
    except ValueError:
        pass
    first = {}
    tp = {}
    for name in ('tape.jsonl', 'tape_fast.jsonl'):                  # the same ticket can be in both: merge by id, keep the fast row's `f`
        for r in load_jsonl(dirs, name):
            if r.get('s') == 'pm' and r.get('w'):
                tp[r['id']] = {**tp.get(r['id'], {}), **r}
    tape = sorted(tp.values(), key=lambda r: r['t'])
    both = defaultdict(set)                                     # (wallet, market) -> outcomes it has bought so far
    new = 0
    today = os.path.join(root, 'snapshots', dt.datetime.fromtimestamp(now, ET).date().isoformat())
    for r in tape:
        m = meta.get(r['k'])
        if not m or r['t'] >= m['start'] or m['start'] < FIRST_TIP:
            continue
        key = (r['w'], r['k'], r['o'])
        if key in first:
            continue
        opp = (r['w'], r['k']) in both and (1 - r['o']) in both[(r['w'], r['k'])]
        both[(r['w'], r['k'])].add(r['o'])
        if r['usd'] < MIN_USD:
            continue
        first[key] = 1
        i = eid(*key)
        if i in rows:
            continue
        w = r['w']
        coh = 'sharp' if w in W['sharp'] else 'dull' if w in W['dull'] else 'other'
        rows[i], where[i] = {
            'id': i, 'w': w, 'who': r.get('who'), 'k': r['k'], 'o': r['o'], 'g': m.get('event'), 'type': m['type'], 'line': m.get('line'),
            't': r['t'], 'usd': r['usd'], 'px': r['px'], 'tip': m['start'], 'cohort': coh, 'lab': W['sharp'].get(w), 'hedge': bool(opp),
            'bf': bool(r['t'] < FREEZE_T or gen > m['start']), 'f': {}, 'seen': now, 'det': (r['f'] - r['t']) if r.get('f') else None}, today
        new += 1
    graded = 0
    for i, ev in rows.items():
        if ev.get('final'):
            continue
        qs = quotes.get(ev['k'], [])
        ev['f'] = follow_entries(ev, qs, polls, ev['tip'])       # deterministic from stored data: recomputed until the game is final
        if now >= ev['tip'] + GRADE_AFTER_S:
            ev['final'] = 1
            c = close_mid(qs, polls, ev['tip'], ev['o'])
            if c:
                grade(ev, c)
                graded += 1
    by_dir = defaultdict(dict)
    for i, ev in rows.items():
        by_dir[where[i]][i] = ev
    for d, j in by_dir.items():
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, FILE), 'w') as f:
            json.dump(j, f, separators=(',', ':'))
    return {'new': new, 'graded': graded}


def report(root, now, results=False):
    """Counts by cohort always. CLV only with results=True (not run before the pre-registered first look)."""
    rows, _ = load_follows(day_dirs(root, now, 400))
    by = defaultdict(lambda: {'events': 0, 'games': set(), 'graded': 0, 'bf': 0, 'hedge': 0})
    for ev in rows.values():
        b = by[ev['cohort']]
        b['events'] += 1
        b['games'].add(ev['g'])
        b['graded'] += 1 if ev.get('res') else 0
        b['bf'] += ev['bf']
        b['hedge'] += ev['hedge']
    for c, b in sorted(by.items()):
        print(f"{c:6} events {b['events']:5} games {len(b['games']):4} graded {b['graded']:5} backfill {b['bf']:4} hedged {b['hedge']:4}")
    if not results:
        return
    for c in ('sharp', 'dull', 'other'):
        for m in ('mk', 'tk2', 'tk5', 'tk15', 'tk60'):
            gm = defaultdict(list)
            for ev in rows.values():
                if ev['cohort'] == c and not ev['bf'] and not ev['hedge'] and m in (ev.get('res') or {}):
                    gm[ev['g']].append(ev['res'][m]['val'])
            xs = [sum(v) / len(v) for v in gm.values()]
            if len(xs) > 1:
                mu = sum(xs) / len(xs)
                sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))
                print(f"{c:6} {m:5} games {len(xs):4} mean {mu:+.4f} t {mu / (sd / math.sqrt(len(xs))) if sd else 0:+.2f}")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='nba-data')
    ap.add_argument('--now', type=int, default=None)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--results', action='store_true', help='print CLV; only after the pre-registered first look')
    a = ap.parse_args()
    now = a.now or int(dt.datetime.now().timestamp())
    if a.report:
        report(a.root, now, a.results)
    else:
        print(run(a.root, now))
