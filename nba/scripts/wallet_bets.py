#!/usr/bin/env python3
"""
Polymarket wallet bets: what each ranked wallet normally bets, whether a bigger-than-normal bet does better, and how each
bet finished. Read by the Wallets page through follow_ledger.build_board. Stored data only, no number is invented.

A BET is everything one wallet bought of one outcome of one game market (moneyline, spread, total) before tip. Its price
is the stored fills' dollar-weighted price, so shares = sum(usd / px), a win pays one dollar a share, ROI is before fees.
A wallet's NORMAL is the median of its bets, so "size vs normal" is bet / normal. The tape keeps fills of $100 or more, so
a normal here is the usual size among bets of $100 or more.

A bet settles from the stored final score (results/<espn game>.meta.json). The score's game is found from the ESPN game rows
in meta.jsonl by the two teams and the tip time, never by game number, because ESPN numbers do not follow the calendar.
First-half markets and props are left out: no half score is stored.

The store (root/wallet_bets.json) is rebuilt from the tape and meta rows of the last LOOKBACK_DAYS on every poll, and
widened to FIRST_DAYS when the file does not exist yet, so a new store backfills itself. Fills only ever add, so a rebuilt
bet keeps the larger of its stored and rebuilt totals and a bet whose early fills have left the window is not cut down.

CLI:  wallet_bets.py --root nba-data [--back N]   rebuild the store (N days back) and print the pooled size table
"""
import json, os, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sharp import day_dirs                                       # noqa: E402

FILE = 'wallet_bets.json'
TYPES = ('moneyline', 'spreads', 'totals')
LOOKBACK_DAYS = 3
FIRST_DAYS = 45
KEEP_DAYS = 150
TIP_SLACK_S = 2 * 3600                                           # an ESPN tip and a Polymarket start for one game agree to within this
MIN_BETS_NORMAL = 5                                              # a wallet needs this many bets before it has a "normal"
MIN_BUCKET = 15                                                  # a size row under this many settled bets is too few to read (the Accounts page's cut)
BUCKETS = (('Smaller (under 0.7x)', 0, 0.7), ('About normal', 0.7, 1.5), ('Bigger (1.5x to 3x)', 1.5, 3), ('Much bigger (3x+)', 3, 1e9))
BIG = 1.5
# Polymarket slug codes that differ from ESPN's
ESPN = {'sas': 'SA', 'nyk': 'NY', 'gsw': 'GS', 'nop': 'NO', 'uta': 'UTAH', 'was': 'WSH', 'pho': 'PHX', 'brk': 'BKN'}


def espn_abbr(code):
    return ESPN.get(code, code.upper())


def lines(dirs, name, needle):
    """Parsed rows of `name` in each day folder whose raw line holds `needle` (the meta files are ~10 MB a day: skip the parse)."""
    for d in dirs:
        p = os.path.join(d, name)
        if not os.path.exists(p):
            continue
        for line in open(p):
            if needle in line:
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def update(root, now, wallets, back=None):
    """Rebuild the store from the last `back` days. `wallets` is the set of ranked wallets to keep bets for."""
    path = os.path.join(root, FILE)
    try:
        S = json.load(open(path))
    except (OSError, ValueError):
        S = None
    dirs = day_dirs(root, now, back or (LOOKBACK_DAYS if S else FIRST_DAYS))
    S = S or {'m': {}, 'g': {}, 'b': {}}
    for r in lines(dirs, 'meta.jsonl', '"src":"polymarket"'):
        if r.get('type') in TYPES and r.get('start'):
            try:
                outs = json.loads(r['outcomes'])
            except (ValueError, KeyError, TypeError):
                continue
            S['m'][r['k']] = [r.get('event'), r['type'], r.get('line'), outs, r['start']]
    for r in lines(dirs, 'meta.jsonl', '|game"'):
        if r.get('src') == 'espn' and r.get('home') and r.get('away') and r.get('tip') and str(r.get('k', '')).endswith('|game'):
            S['g'][f"{r['away']}|{r['home']}|{r['tip']}"] = str(r['game'])
    got = {}
    for name in ('tape.jsonl', 'tape_fast.jsonl'):               # the same fill can be in both: merge by id
        for r in lines(dirs, name, '"s":"pm"'):
            if r.get('s') == 'pm' and r.get('w') in wallets and r.get('k') in S['m'] and r['t'] < S['m'][r['k']][4] and r.get('px'):
                got[r['id']] = r
    agg = defaultdict(lambda: [0.0, 0.0])
    for r in got.values():
        a = agg[f"{r['w']}|{r['k']}|{r['o']}"]
        a[0] += r['usd']
        a[1] += r['usd'] / r['px']
    for k, (usd, sh) in agg.items():
        old = S['b'].get(k)
        if old is None or usd >= old[0]:
            S['b'][k] = [round(usd, 2), round(sh, 3)]
    cut = now - KEEP_DAYS * 86400
    S['m'] = {k: v for k, v in S['m'].items() if v[4] >= cut}
    S['g'] = {k: v for k, v in S['g'].items() if int(k.rsplit('|', 1)[1]) >= cut}
    S['b'] = {k: v for k, v in S['b'].items() if k.split('|')[1] in S['m']}
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(S, f, separators=(',', ':'))
    os.replace(tmp, path)
    return S


def load(root):
    try:
        return json.load(open(os.path.join(root, FILE)))
    except (OSError, ValueError):
        return None


def score_of(root, S, mk):
    """(away points, home points) of a market's game, or None until the final score is stored."""
    p = (mk[0] or '').split('-')
    if len(p) < 3 or p[0] != 'nba':
        return None
    away, home = espn_abbr(p[1]), espn_abbr(p[2])
    gids = {S['g'][k] for k in S['g'] if k.startswith(f'{away}|{home}|') and abs(int(k.rsplit('|', 1)[1]) - mk[4]) <= TIP_SLACK_S}
    if len(gids) != 1:
        return None
    try:
        sc = json.load(open(os.path.join(root, 'results', f'{next(iter(gids))}.meta.json'))).get('score') or {}
    except (OSError, ValueError):
        return None
    return (sc[away], sc[home]) if away in sc and home in sc else None


def moneylines(S):
    """{event: [away team, home team]} as Polymarket names them on the moneyline (it lists the away team first)."""
    return {m[0]: m[3] for m in S['m'].values() if m[1] == 'moneyline'}


def settle(root, S, k, o, ml=None):
    """1 won, -1 lost, 0 push, None not settled (no final score stored, or the spread's side cannot be told)."""
    mk = S['m'].get(k)
    sc = score_of(root, S, mk) if mk else None
    if sc is None:
        return None
    a, h = sc
    typ, line, outs = mk[1], mk[2], mk[3]
    if typ == 'moneyline':
        d = (a - h) if o == 0 else (h - a)
    elif typ == 'totals':
        if line is None:
            return None
        d = (a + h - line) if o == 0 else (line - a - h)
    else:
        mlo = (ml or moneylines(S)).get(mk[0])
        if line is None or not mlo or outs[0] not in mlo:
            return None
        m0 = ((a - h) if outs[0] == mlo[0] else (h - a)) + line   # the named team's margin after its spread; outcome 0 is that team
        d = m0 if o == 0 else -m0
    return 1 if d > 0 else -1 if d < 0 else 0


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if not n else xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def bucket(x):
    return next(i for i, (_, lo, hi) in enumerate(BUCKETS) if lo <= x < hi)


def summarize(root, S):
    """({wallet: {norm, n, open, rec, bk, res}}, pooled). bk = per size bucket [settled, won, staked, profit]; rec = [settled, won, lost,
    staked, profit] over every settled bet; res = {'market|outcome': 1/-1/0} for the settled ones. Bets in a market the wallet also bought
    the other side of are left out of all of it: a hedge has no win or loss."""
    if not S:
        return {}, None
    ml = moneylines(S)
    by = defaultdict(dict)
    for key, (usd, sh) in S['b'].items():
        w, k, o = key.split('|')
        by[w][(k, int(o))] = (usd, sh)
    out = {}
    pool = {'big': [0, 0, 0.0, 0.0], 'rest': [0, 0, 0.0, 0.0], 'wallets': 0}
    cache = {}
    for w, bets in by.items():
        solo = {kk: v for kk, v in bets.items() if (kk[0], 1 - kk[1]) not in bets}
        norm = median([v[0] for v in solo.values()]) if len(solo) >= MIN_BETS_NORMAL else None
        rec, bk, opn, res = [0, 0, 0, 0.0, 0.0], [[0, 0, 0.0, 0.0] for _ in BUCKETS], 0, {}
        for (k, o), (usd, sh) in solo.items():
            if (k, o) not in cache:
                cache[(k, o)] = settle(root, S, k, o, ml)
            r = cache[(k, o)]
            if r is None:
                opn += 1
                continue
            res[f'{k}|{o}'] = r
            pnl = (sh - usd) if r > 0 else -usd if r < 0 else 0.0
            if r:
                rec[0] += 1
                rec[1 if r > 0 else 2] += 1
                rec[3] += usd
                rec[4] += pnl
            if norm:
                b = bk[bucket(usd / norm)]
                b[0] += 1
                b[1] += r > 0
                b[2] += usd
                b[3] += pnl
                if r:
                    g = pool['big' if usd / norm >= BIG else 'rest']
                    g[0] += 1
                    g[1] += r > 0
                    g[2] += usd
                    g[3] += pnl
        if norm:
            pool['wallets'] += 1
        out[w] = {'norm': round(norm) if norm else None, 'n': len(solo), 'open': opn, 'rec': [rec[0], rec[1], rec[2], round(rec[3]), round(rec[4])],
                  'bk': [[b[0], b[1], round(b[2]), round(b[3])] for b in bk], 'res': res, 'bets': {f'{k}|{o}': v[0] for (k, o), v in bets.items()}}
    for g in ('big', 'rest'):
        pool[g] = [pool[g][0], pool[g][1], round(pool[g][2]), round(pool[g][3])]
    return out, pool


def ticket(summ, w, k, o):
    """{'res': 1 / -1 / 0 / None, 'tot': all they bought of that side, 'x': tot vs the wallet's normal or None} for one ticket of the follow ledger."""
    s = (summ or {}).get(w)
    if not s:
        return {'res': None, 'tot': None, 'x': None}
    key = f'{k}|{o}'
    usd = s['bets'].get(key)
    return {'res': s['res'].get(key), 'tot': round(usd) if usd else None, 'x': round(usd / s['norm'], 1) if usd and s['norm'] else None}


if __name__ == '__main__':
    a = sys.argv[1:]
    root = a[a.index('--root') + 1] if '--root' in a else '.'
    back = int(a[a.index('--back') + 1]) if '--back' in a else None
    S = update(root, time.time(), set(json.load(open(os.path.join(HERE, '..', '..', 'data', 'pm_wallet_rank.json')))['wallets']), back)
    out, pool = summarize(root, S)
    print(len(S['m']), 'markets', len(S['g']), 'games', len(S['b']), 'bets', len(out), 'wallets')
    print(json.dumps(pool))
