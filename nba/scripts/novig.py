"""Novig exchange flow for NBA: public order books + trade tape, no key needed.

Novig (docs.novig.com) is a peer-to-peer sports exchange. Its public REST reads (cached ~5s at the edge) give every
market's resting orders and executions, anonymous like Kalshi's. This module turns them into what Vault shows:

  per game   moneyline / main spread / main total: bid, ask, no-vig fair, depth $, resting $, recent flow
  per prop   one ladder per (player, stat): strike, over bid/ask/mid, depth $, flow
  tape       big executions (>= TAPE_MIN dollars), newest first

Units: one contract pays 1 cent, so a resting order's dollars = price * qty / 100. A price is a probability.
A bid on outcome A at p is the same liquidity as an ask on outcome B at 1 - p (the book is keyed by outcome).

Rate limits are per IP at the edge and per throttle on the server, so everything goes through one paced client that
honours Retry-After and a per-poll request budget. Game lines rotate by WHOLE GAME (the moneyline and every spread and total strike
of a game are read in one poll, or the game keeps its last complete read with its age); props rotate by market.

  poll(games, root, now) -> board['novig']      (snapshot.py / prop_board call this)
  python3 nba/scripts/novig.py                  (live smoke test against production, prints a summary)
"""
import json, os, re, subprocess, sys, time

HOST = os.environ.get('NOVIG_PUBLIC_HOST', 'https://api.novig.com') + '/v3/public'
BUDGET = int(os.environ.get('NOVIG_BUDGET', '220'))     # requests per poll for the game lines: whole games only (a game is ~48 books plus the trades of the books that changed)
PROP_BUDGET = int(os.environ.get('NOVIG_PROP_BUDGET', '80'))   # requests per poll for player props, on top of BUDGET: the lines alone use all of BUDGET
                                                       # (about 45 markets a game, a book and a trades call each), so props never got a request
CARRY_MAX_S = int(os.environ.get('NOVIG_CARRY_MAX_S', '7200'))   # a game not read this poll keeps its last complete read this long, then it is dropped rather than shown stale
LINE_KINDS = ('MONEY', 'SPREAD', 'TOTAL')
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
        self.cur, self.tape, self.rot, self.vol, self.seq, self.games = {}, [], 0, {}, {}, {}
        if self.path and os.path.exists(self.path):
            try:
                d = json.load(open(self.path))
                self.cur, self.tape, self.rot, self.vol, self.seq = d.get('cur', {}), d.get('tape', []), d.get('rot', 0), d.get('vol', {}), d.get('seq', {})
                self.games = d.get('games', {})
            except (ValueError, OSError):
                pass

    def save(self, now):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        keep = [t for t in self.tape if t['t'] > now - 36 * 3600][-TAPE_KEEP:]
        self.tape = keep
        with open(self.path, 'w') as f:
            json.dump({'cur': self.cur, 'tape': keep, 'rot': self.rot, 'vol': self.vol, 'seq': self.seq, 'games': self.games}, f, separators=(',', ':'))


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


def main_line(xs):
    """The main line of a COMPLETE ladder: the strike whose quote sits nearest 50%. Strikes with no two-sided quote have no
    mid and cannot be the main line. A tie goes to the deeper book, then the smaller number, so it never depends on the
    order the API listed the strikes in. Never call this on a partial ladder: a cut-short read of BOS @ DET (strikes listed
    6.5, 5.5, 4.5 ... first, the true main is 1.5) picks 4.5."""
    ys = [x for x in xs if x.get('mid') is not None]
    return min(ys, key=lambda x: (round(abs(x['mid'] - 0.5), 4), -x['depth'], x['k'] if x['k'] is not None else 0)) if ys else None


GAME_KEEP = ('event', 'tip', 'asof', 'lines', 'tc', 'ml', 'main_spread', 'main_total', 'rest', 'depth', 'tr', 'usd')   # what a carried game remembers


def poll(games, root, now, roster_find=None):
    """games: pre-tip slate games (id, away, home, away_name, home_name, tip). roster_find(name, teams) -> player id.
    Returns {'asof', 'games': {gid: {...}}, 'props': {'pid|stat': {...}}, 'tape': [...], 'budget': n, 'used': n, 'rotation': {...}}.

    Game lines are read a WHOLE GAME at a time: the moneyline plus every spread and total strike, oldest read first. A game
    is published only from a complete read; a game not reached this poll keeps its last complete result with its age
    (`asof`, `age`, `fresh`), and a game whose read came up short keeps the old one too. main_spread / main_total are chosen
    from a complete ladder only."""
    st = State(root)
    t0 = time.time()
    clock = lambda: now + (time.time() - t0)              # `now` is the poll's start; reads take minutes, so a game's age is measured at the time it finished
    soon = [g for g in games if now < g['tip'] <= now + AHEAD_H * 3600]
    events = pages('/catalog/events?league=NBA&status=OPEN_PREGAME,OPEN_INGAME&limit=200')
    emap = match_events(soon, events)
    used = [0]
    pused = [0]                                           # prop requests: counted apart from the lines so a big slate of lines cannot starve them

    def b_get(path):                                      # a prop request, against PROP_BUDGET
        if pused[0] >= PROP_BUDGET:
            return None
        pused[0] += 1
        return get(path)

    out = {'asof': int(now), 'games': {}, 'props': {}, 'tape': [], 'fresh': [], 'budget': BUDGET}
    lines, props = {}, []                                 # gid -> [(market, kind)] for the lines; (game, market, kind) for the props
    for g in soon:
        e = emap.get(str(g['id']))
        if not e:
            continue
        gid = str(g['id'])
        mks = pages(f"/catalog/markets?event={e['eventId']}&limit=1000")
        out['games'][gid] = {'event': e['eventId'], 'ml': None, 'spreads': [], 'totals': [], 'main_spread': None, 'main_total': None,
                             'n': len(mks), 'rest': 0, 'depth': 0, 'tr': 0, 'usd': 0, 'fresh': False, 'asof': None, 'age': None, 'lines': 0}
        lines[gid] = []
        for mk in mks:
            kind = market_kind(mk)
            if not kind or mk.get('status') != 'OPEN':
                continue
            if kind in LINE_KINDS:
                lines[gid].append((mk, kind))
            else:
                props.append((g, mk, kind))

    def shape(mk, book):
        r = read_book(mk, book) if book else None
        if r:
            r['id'] = mk['marketId']
            r['k'] = float(mk['strike']) if mk.get('strike') not in (None, '') else None
            r['o'] = [team_name(o['name']) for o in mk['outcomes']]
        return r

    def apply_trades(g, mk, kind, r, tr):
        """Executions after the market's cursor -> the tape, the cursor, the running volume. Returns (tickets, dollars)."""
        gid, mid_ = str(g['id']), mk['marketId']
        since = st.cur.get(mid_) or int((now - 3 * 3600) * 1000)    # first sight looks back 3 hours
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
        return mk_n, mk_usd

    def read_game(g, gid):
        """Every line market of one game: all the books first (they are what a complete ladder needs), then the trades of the
        books that changed, with whatever budget is left. -> (result, short) where result is None unless every book came back."""
        got, bad = [], []
        for mk, kind in lines[gid]:
            used[0] += 1                                  # a game the budget admitted is read in full: its books were reserved when it was chosen
            book = get(f"/catalog/markets/{mk['marketId']}/book")
            r = shape(mk, book)
            (got if r else bad).append((mk, kind, r, book) if r else (mk, kind))
        for mk, kind in list(bad):                        # one more try for any book that failed (a timeout is not a missing strike)
            used[0] += 1
            book = get(f"/catalog/markets/{mk['marketId']}/book")
            r = shape(mk, book)
            if r:
                bad.remove((mk, kind))
                got.append((mk, kind, r, book))
        tc, usd = 0, 0.0
        for mk, kind, r, book in got:
            mid_ = mk['marketId']
            changed = st.seq.get(mid_) != book.get('seq')  # an unchanged book has no new executions: skip the trades call
            tr = None
            if changed and used[0] < BUDGET:
                tr = get(f"/catalog/markets/{mid_}/trades?limit=100")
                used[0] += 1
                tc += 1
            if not changed or tr is not None:
                st.seq[mid_] = book.get('seq')            # a trades call that was skipped for budget is retried next read, not lost
            usd += apply_trades(g, mk, kind, r, tr)[1]
        if bad:
            return None, len(bad)
        res = {'event': out['games'][gid]['event'], 'tip': g['tip'], 'asof': int(clock()), 'lines': len(lines[gid]), 'tc': tc,
               'ml': None, 'spreads': [], 'totals': [], 'rest': 0, 'depth': 0, 'tr': 0, 'usd': usd}
        for mk, kind, r, book in got:
            res['rest'] += r['rest']
            res['depth'] += r['depth']
            res['tr'] += r['tr']
            if kind == 'MONEY':
                r['team'] = team_name(mk.get('description'))
                res['ml'] = r
            elif kind == 'SPREAD':
                res['spreads'].append(r)
            else:
                res['totals'].append(r)
        for k in ('spreads', 'totals'):
            res['main_' + k[:-1]] = main_line(res[k])
            res[k] = sorted(res[k], key=lambda x: x['k'] if x['k'] is not None else 0)
        return res, 0

    # lines: whole games, the one read longest ago first (never read first, then by tip). A game starts only if the budget
    # covers its books plus the trades calls it needed last time; the first game of a poll always starts.
    gmap = {str(g['id']): g for g in soon}
    order = sorted(lines, key=lambda gid: ((st.games.get(gid) or {}).get('asof') or 0, gmap[gid]['tip']))
    fresh_gids, short = [], {}
    for gid in order:
        nl = len(lines[gid])
        if not nl:
            continue
        est = min(nl, (st.games.get(gid) or {}).get('tc', nl))
        if used[0] and BUDGET - used[0] < nl + est:
            continue
        res, bad = read_game(gmap[gid], gid)
        if res:
            st.games[gid] = {k: res[k] for k in GAME_KEEP}
            gout = out['games'][gid]
            gout.update({k: v for k, v in res.items() if k != 'tip'})
            gout['fresh'] = True
            fresh_gids.append(gid)
        else:
            short[gid] = bad
    for gid, gout in out['games'].items():
        if gid in fresh_gids:
            gout['age'] = 0
            continue
        keep = st.games.get(gid)
        if gid in short:
            gout['short'] = short[gid]                    # books that never came back: this game kept its previous complete read
        if keep and clock() - keep['asof'] <= CARRY_MAX_S:
            gout.update({k: keep[k] for k in GAME_KEEP if k != 'tip'})
            gout['tr'], gout['usd'] = 0, 0                # new trades since the last read are not known for a game not read this poll
            gout['age'] = int(clock() - keep['asof'])
    for gid in [k for k, v in st.games.items() if v.get('tip', 0) < now - 6 * 3600]:
        del st.games[gid]                                 # a game that tipped long ago has nothing left to carry

    # props: rotate so every prop is seen within a few polls (unchanged)
    if props:
        k = st.rot % len(props)
        props = props[k:] + props[:k]
    for g, mk, kind in props:
        if pused[0] >= PROP_BUDGET:
            break                                         # the props are last in the queue
        gid = str(g['id'])
        book = b_get(f"/catalog/markets/{mk['marketId']}/book")
        r = shape(mk, book)
        if not r:
            continue
        mid_ = mk['marketId']
        changed = st.seq.get(mid_) != book.get('seq')
        st.seq[mid_] = book.get('seq')
        tr = None
        if changed and pused[0] < PROP_BUDGET:
            tr = b_get(f"/catalog/markets/{mid_}/trades?limit=100")
        apply_trades(g, mk, kind, r, tr)
        m = re.match(r'(.+?)\s+[\d.]+\s+[A-Z_]+$', mk.get('description') or '')
        pid = roster_find(m.group(1), (g['away'], g['home'])) if (m and roster_find) else None
        key = f"{pid}|{STAT[kind]}" if pid else None
        if key:
            p = out['props'].setdefault(key, {'p': pid, 's': STAT[kind], 'g': g['id'], 'lad': []})
            p['lad'].append(r)
    st.rot += max(1, pused[0] // 2)                       # the rotation walks the props only; the lines rotate by game
    for gout in out['games'].values():
        for k in ('usd', 'rest', 'depth'):
            gout[k] = round(gout[k])
    ages = {gid: g['age'] for gid, g in out['games'].items()}
    held = [a for gid, a in ages.items() if a is not None and gid not in fresh_gids]
    out['rotation'] = {'read': len(fresh_gids), 'carried': len(held), 'none': sum(1 for a in ages.values() if a is None), 'short': len(short),
                       'games': len(ages), 'oldest_age': max(held, default=None), 'ages': ages}
    out['tape'] = sorted(st.tape, key=lambda x: -x['t'])[:60]
    out['used'] = used[0] + pused[0]
    out['budget'] = BUDGET + PROP_BUDGET
    ro = out['rotation']
    print(f"  novig lines: read {ro['read']} of {ro['games']} games this poll, {ro['carried']} carried (oldest {ro['oldest_age'] or 0}s), "
          f"{ro['none']} with no complete read, {ro['short']} short; {used[0]}/{BUDGET} line requests", flush=True)
    st.save(now)
    return out


def quotes(out, games):
    """board['novig'] -> (rows, meta) for Day.record('novig', ...): one key per game market, the HOME / OVER side's
    [bid, ask, depth to the nearest $250], so a price change is a row and a depth wobble is not. Keys carry the strike,
    so a main line that moves is a new key. This is the price history the Backtest Lab needs to test Novig as a fair price."""
    by_id = {str(g['id']): g for g in games}
    rows, meta = {}, {}
    for gid, g in (out.get('games') or {}).items():
        gm = by_id.get(gid)
        if not gm:
            continue
        for kind, x in (('ml', g.get('ml')), ('sp', g.get('main_spread')), ('tot', g.get('main_total'))):
            if not x or not x.get('o'):
                continue
            first = x['o'][0]
            lead = first.lower().startswith('over') if kind == 'tot' else first.split(' ')[0] == gm['home']
            i = 0 if lead else 1                                   # the home / over outcome
            line = x['k'] if kind == 'tot' else None
            if kind == 'sp':
                try:
                    n = float(first.split(' ')[1])
                    line = n if lead else -n                       # the home handicap
                except (IndexError, ValueError):
                    continue
            key = f"{gid}|{kind}" + (f"|{line}" if line is not None else '')
            rows[key] = [x['bid'][i], x['ask'][i], int(round(x['depth'] / 250.0)) * 250]
            meta[key] = {'g': gid, 'm': kind, 'line': line, 'mid': x['id']}
    return rows, meta


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
