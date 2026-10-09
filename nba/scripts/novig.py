"""Novig exchange flow for NBA: public order books + trade tape, no key needed.

Novig (docs.novig.com) is a peer-to-peer sports exchange. Its public REST reads (cached ~5s at the edge) give every
market's resting orders and executions, anonymous like Kalshi's. This module turns them into what Vault shows:

  per game   moneyline / main spread / main total: bid, ask, no-vig fair, depth $, resting $, recent flow
  per prop   one ladder per (player, stat): strike, over bid/ask/mid, depth $, flow
  tape       big executions (>= TAPE_MIN dollars), newest first

Units: one contract pays 1 cent, so a resting order's dollars = price * qty / 100. A price is a probability.
A bid on outcome A at p is the same liquidity as an ask on outcome B at 1 - p (the book is keyed by outcome).

Rate limits are per IP at the edge and per throttle on the server, so everything goes through one paced client that
honours Retry-After and a per-poll request budget; markets rotate so a big slate is covered over a few polls.

  poll(games, root, now) -> board['novig']      (snapshot.py / prop_board call this)
  python3 nba/scripts/novig.py                  (live smoke test against production, prints a summary)
"""
import json, os, re, subprocess, sys, time

HOST = os.environ.get('NOVIG_PUBLIC_HOST', 'https://api.novig.com') + '/v3/public'
BUDGET = int(os.environ.get('NOVIG_BUDGET', '220'))     # requests per poll
PACE_S = 0.35                                          # gap between requests (~3/s)
TAPE_MIN = 25                                          # dollars; smaller executions are noise
TAPE_KEEP = 300
SIG_MIN = 250                                          # dollars; a ticket this size is saved to the day's tape for Sharp Price
AHEAD_H = 48
CLOSE = 0.03                                           # depth counts orders within 3 cents of the best price
TIGHT = 0.10                                           # a quote wider than this says nothing about the fair price

STAT = {'POINTS': 'pts', 'REBOUNDS': 'reb', 'ASSISTS': 'ast', 'THREE_POINTERS_MADE': '3pm',
        'POINTS_REBOUNDS_ASSISTS': 'pra', 'POINTS_REBOUNDS': 'pr', 'POINTS_ASSISTS': 'pa',
        'REBOUNDS_ASSISTS': 'ra', 'STEALS': 'stl', 'BLOCKS': 'blk'}

_last = 0.0
_pause_until = 0.0


def get(path, tries=3):
    """One paced GET -> parsed JSON or None. 429 waits out Retry-After; anything else non-200 is a miss."""
    global _last, _pause_until
    for _ in range(tries):
        wait = max(_last + PACE_S, _pause_until) - time.time()
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        p = subprocess.run(['curl', '-s', '-m', '20', '-D', '/dev/stderr', '-w', '\n%{http_code}', HOST + path],
                           capture_output=True, text=True)
        out, hdr = p.stdout, p.stderr
        code = out.rsplit('\n', 1)[-1].strip() if out else ''
        if code == '200':
            try:
                return json.loads(out.rsplit('\n', 1)[0])
            except ValueError:
                return None
        if code == '429':
            m = re.search(r'retry-after:\s*(\d+)', hdr, re.I)
            _pause_until = time.time() + (int(m.group(1)) if m else 3) + 0.5
            continue
        return None
    return None


def pages(path, key='items', cap=6):
    out, after = [], None
    for _ in range(cap):
        d = get(path + (f'&after={after}' if after else ''))
        if not d:
            break
        out += d.get(key) or []
        after = d.get('next')
        if not after or not d.get(key):
            break
    return out


TEAM = {'GSW': 'GS', 'NYK': 'NY', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH', 'PHO': 'PHX', 'BRK': 'BKN'}   # same table as prop_board.TEAM: Novig's codes -> the slate's


def team_name(name):
    """'SAS -8.5' -> 'SA -8.5': the leading team code in the slate's spelling. Over / Under pass through."""
    t = (name or '').split(' ', 1)
    return ' '.join([TEAM.get(t[0], t[0])] + t[1:])


def nick(s):
    return re.sub(r'[^a-z]', '', (s or '').lower())


def dollars(price, qty):
    return float(price) * qty / 100.0


def game_side(g, kind, on, strike):
    """A ticket on a game market -> the Sharp Price convention: m ('ml' | 'sp' | 'tot'), side ('home' | 'away' | 'over' |
    'under') and line (the HOME handicap for a spread, the number for a total). {} for anything else (props, 1H markets)."""
    if kind == 'TOTAL':
        return {'m': 'tot', 'side': 'over' if on.lower().startswith('over') else 'under', 'line': strike}
    team = on.split(' ')[0]
    if team not in (g['home'], g['away']):
        return {}
    side = 'home' if team == g['home'] else 'away'
    if kind == 'MONEY':
        return {'m': 'ml', 'side': side, 'line': None}
    if kind == 'SPREAD':
        try:
            n = float(on.split(' ')[1])
        except (IndexError, ValueError):
            return {}
        return {'m': 'sp', 'side': side, 'line': n if side == 'home' else -n}
    return {}


def read_book(mk, book):
    """Two-outcome market -> {a, b: outcome names, bid: [bidA, bidB], ask: [askA, askB], mid, depth, rest}.
    bid on A at p is liquidity to buy B at 1-p, so A's ask is 1 - best bid on B."""
    outs = [o['outcomeId'] for o in mk['outcomes']]
    if len(outs) != 2:
        return None
    orders = book.get('orders') or {}
    L = [sorted(orders.get(o) or [], key=lambda x: -float(x['price'])) for o in outs]
    best = [float(l[0]['price']) if l else None for l in L]
    depth = [sum(dollars(x['price'], x['qty']) for x in l if best[i] - float(x['price']) <= CLOSE + 1e-9) for i, l in enumerate(L) if l]
    ask = [(1 - best[1]) if best[1] is not None else None, (1 - best[0]) if best[0] is not None else None]
    bid = best
    mid = None
    if bid[0] is not None and ask[0] is not None and 0 < bid[0] <= ask[0] < 1 and ask[0] - bid[0] <= TIGHT + 1e-9:
        mid = round((bid[0] + ask[0]) / 2, 4)
    return {'bid': [None if b is None else round(b, 3) for b in bid], 'ask': [None if a is None else round(a, 3) for a in ask],
            'mid': mid, 'depth': round(sum(depth)), 'rest': round(sum(dollars(x['price'], x['qty']) for l in L for x in l)),
            'lv': [len(l) for l in L]}


def market_kind(mk):
    t = mk.get('marketType')
    if t in ('MONEY', 'SPREAD', 'TOTAL'):
        return t
    return t if t in STAT else None


class State:
    """Trade cursors and the rolling tape, kept in <root>/novig/state.json so a restarted poll resumes cleanly."""

    def __init__(self, root):
        self.path = os.path.join(root, 'novig', 'state.json') if root else None
        self.cur, self.tape, self.rot, self.vol, self.seq = {}, [], 0, {}, {}
        if self.path and os.path.exists(self.path):
            try:
                d = json.load(open(self.path))
                self.cur, self.tape, self.rot, self.vol, self.seq = d.get('cur', {}), d.get('tape', []), d.get('rot', 0), d.get('vol', {}), d.get('seq', {})
            except (ValueError, OSError):
                pass

    def save(self, now):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        keep = [t for t in self.tape if t['t'] > now - 36 * 3600][-TAPE_KEEP:]
        self.tape = keep
        with open(self.path, 'w') as f:
            json.dump({'cur': self.cur, 'tape': keep, 'rot': self.rot, 'vol': self.vol, 'seq': self.seq}, f, separators=(',', ':'))


def match_events(games, events):
    """slate game id -> Novig event, by team nicknames in 'Away @ Home'."""
    out = {}
    for e in events:
        m = re.match(r'(.+?) @ (.+)', e.get('description') or '')
        if not m:
            continue
        a, h = nick(m.group(1)), nick(m.group(2))
        for g in games:
            ga, gh = nick(g.get('away_name')), nick(g.get('home_name'))
            if ga and gh and (ga == a and gh == h) and abs(g['tip'] - e['startsTs'] / 1000) < 6 * 3600:
                out[str(g['id'])] = e
    return out


def poll(games, root, now, roster_find=None):
    """games: pre-tip slate games (id, away, home, away_name, home_name, tip). roster_find(name, teams) -> player id.
    Returns {'asof', 'games': {gid: {...}}, 'props': {'pid|stat': {...}}, 'tape': [...], 'budget': n, 'used': n}."""
    st = State(root)
    soon = [g for g in games if now < g['tip'] <= now + AHEAD_H * 3600]
    events = pages('/catalog/events?league=NBA&status=OPEN_PREGAME,OPEN_INGAME&limit=200')
    emap = match_events(soon, events)
    used = [0]

    def b_get(path):
        if used[0] >= BUDGET:
            return None
        used[0] += 1
        return get(path)

    out = {'asof': int(now), 'games': {}, 'props': {}, 'tape': [], 'fresh': [], 'budget': BUDGET}
    queue = []                                            # (priority, game, market): lines first, then rotating props
    meta = {}
    for g in soon:
        e = emap.get(str(g['id']))
        if not e:
            continue
        mks = pages(f"/catalog/markets?event={e['eventId']}&limit=1000")
        meta[str(g['id'])] = e
        gout = out['games'].setdefault(str(g['id']), {'event': e['eventId'], 'ml': None, 'spreads': [], 'totals': [],
                                                       'n': len(mks), 'rest': 0, 'depth': 0, 'tr': 0, 'usd': 0})
        for mk in mks:
            kind = market_kind(mk)
            if not kind or mk.get('status') != 'OPEN':
                continue
            queue.append((0 if kind in ('MONEY', 'SPREAD', 'TOTAL') else 1, g, mk, kind))
    lines = [q for q in queue if q[0] == 0]
    props = [q for q in queue if q[0] == 1]
    if props:                                             # rotate so every prop is seen within a few polls
        k = st.rot % len(props)
        props = props[k:] + props[:k]
    for pri, g, mk, kind in lines + props:
        if used[0] >= BUDGET:
            break
        gid = str(g['id'])
        book = b_get(f"/catalog/markets/{mk['marketId']}/book")
        if not book:
            continue
        r = read_book(mk, book)
        if not r:
            continue
        r['id'] = mk['marketId']
        r['k'] = float(mk['strike']) if mk.get('strike') not in (None, '') else None
        r['o'] = [team_name(o['name']) for o in mk['outcomes']]
        gout = out['games'][gid]
        gout['rest'] += r['rest']
        gout['depth'] += r['depth']
        # trades since the cursor; first sight looks back 3 hours
        mid_ = mk['marketId']
        since = st.cur.get(mid_) or int((now - 3 * 3600) * 1000)
        changed = st.seq.get(mid_) != book.get('seq')      # an unchanged book has no new executions: skip the trades call
        st.seq[mid_] = book.get('seq')
        tr = None
        if changed and used[0] < BUDGET:
            tr = get(f"/catalog/markets/{mid_}/trades?limit=100")
            used[0] += 1
        newest = since
        outcome_idx = {o['outcomeId']: i for i, o in enumerate(mk['outcomes'])}
        mk_usd = mk_n = 0
        for t in (tr or {}).get('items') or []:
            if t['ts'] <= since:
                continue
            newest = max(newest, t['ts'])
            usd = dollars(t['price'], t['qty'])
            mk_usd += usd
            mk_n += 1
            if usd >= TAPE_MIN:
                on = team_name(mk['outcomes'][outcome_idx.get(t['outcomeId'], 0)]['name'])
                row = {'t': t['ts'] // 1000, 'g': gid, 'm': mid_, 'kd': kind, 'k': r['k'], 'd': mk.get('description'),
                       'o': outcome_idx.get(t['outcomeId']), 'on': on, 'px': float(t['price']), 'usd': round(usd, 2), 'id': t['tradeId'][:18]}
                row.update(game_side(g, kind, on, r['k']))
                st.tape.append(row)
                if usd >= SIG_MIN and 'side' in row:
                    out['fresh'].append(row)
        st.cur[mid_] = newest
        st.vol[mid_] = round(st.vol.get(mid_, 0) + mk_usd, 2)
        r['vol'] = st.vol[mid_]
        r['tr'] = mk_n
        gout['tr'] += mk_n
        gout['usd'] += mk_usd
        if kind == 'MONEY':
            r['team'] = team_name(mk.get('description'))
            gout['ml'] = r
        elif kind == 'SPREAD':
            gout['spreads'].append(r)
        elif kind == 'TOTAL':
            gout['totals'].append(r)
        else:
            m = re.match(r'(.+?)\s+[\d.]+\s+[A-Z_]+$', mk.get('description') or '')
            pid = roster_find(m.group(1), (g['away'], g['home'])) if (m and roster_find) else None
            key = f"{pid}|{STAT[kind]}" if pid else None
            if key:
                p = out['props'].setdefault(key, {'p': pid, 's': STAT[kind], 'g': g['id'], 'lad': []})
                p['lad'].append(r)
    st.rot += max(1, used[0] // 2)
    for gid, gout in out['games'].items():                # the main line = the strike whose quote sits nearest 50%
        for k in ('spreads', 'totals'):
            xs = [x for x in gout[k] if x.get('mid') is not None]
            gout['main_' + k[:-1]] = min(xs, key=lambda x: abs(x['mid'] - 0.5)) if xs else None
        gout['usd'] = round(gout['usd'])
        gout['rest'] = round(gout['rest'])
        gout['depth'] = round(gout['depth'])
        for k in ('spreads', 'totals'):                   # keep the page payload small: the ladder near the main line
            gout[k] = sorted(gout[k], key=lambda x: x['k'] if x['k'] is not None else 0)
    out['tape'] = sorted(st.tape, key=lambda x: -x['t'])[:60]
    out['used'] = used[0]
    st.save(now)
    return out


if __name__ == '__main__':
    now = time.time()
    ev = pages('/catalog/events?league=NBA&status=OPEN_PREGAME&limit=50')
    games = []
    for i, e in enumerate(ev[:3]):
        m = re.match(r'(.+?) @ (.+)', e['description'])
        games.append({'id': i, 'away': m.group(1)[:3].upper(), 'home': m.group(2)[:3].upper(), 'away_name': m.group(1),
                      'home_name': m.group(2), 'tip': e['startsTs'] / 1000})
    r = poll(games, None, now)
    for gid, g in r['games'].items():
        gm = games[int(gid)]
        ml = g['ml']
        print(f"{gm['away_name']} @ {gm['home_name']}: {g['n']} mkts, resting ${g['rest']:,}, depth ${g['depth']:,}, {g['tr']} trades ${g['usd']:,}")
        if ml:
            print('   ML', ml['o'], 'bid', ml['bid'], 'ask', ml['ask'], 'mid', ml['mid'], 'depth', ml['depth'])
        for k in ('main_spread', 'main_total'):
            x = g.get(k)
            if x:
                print('  ', k, x['o'], x['k'], 'bid', x['bid'], 'ask', x['ask'], 'mid', x['mid'], 'depth', x['depth'])
    print('used', r['used'], 'of', r['budget'], 'props mapped', len(r['props']), 'tape', len(r['tape']))
