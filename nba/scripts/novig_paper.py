#!/usr/bin/env python3
"""
Novig paper trading (docs/novig-paper-trading.md, rules written before any order).

A simulator: it places no order on Novig and needs no Novig key. After each recorder poll it looks at Novig's public player-prop books
(novig.py -> board['novig']), prices each rung with the same projection the Props page uses, and "places" a paper order where our fair
chance beats the price by EDGE_MIN. Fills come from Novig's public trade tape. Each order is settled from the box score. Nothing here
touches money; it answers whether the maker idea works on Novig before any real order exists.

  log(day, board, now)  -> (rows, meta) for Day.record('novig_paper', ...) after each poll (snapshot.py). One row per order key
                           game|player|stat|line|side; the row is rewritten when its status changes, so the day file holds its history.
  record(...)           -> per tip day, every order settled against the box score (called by ledger.settle)

An order (buy `side` of one rung, `stake` dollars, limit price p):
  maker   our limit p sits below the best ask: the order rests until tip (it may sit below the best bid: it then fills only if sellers come down to it). It fills when a printed execution on that rung traded at our price
          or better. Two fill assumptions are recorded, never mixed:  touch (a trade at p or better)  and  thru (a trade at least 1 cent
          better than p: it must have traded through us, so we were not just queued at the back). The tape shows executions of $25 and up
          only, so fills are undercounted, not overcounted.
  taker   the best ask is already at or below p: filled at the ask at once (depth permitting; stakes are a few dollars).
  A maker fill is priced at OUR limit, not at the better price that printed (an exchange matches the resting order at its own price); the printed price is
  kept in the row for diagnosis only.
  Every order also records the ask at placement, so "what a market order would have paid" is available for the maker-vs-taker comparison.
Fee: Novig's schedule is NOT confirmed. FEE_ON_PROFIT is a placeholder (a share of winnings paid on a win) applied to every number shown;
results store gross profit too, so a confirmed fee can be applied afterwards without re-running anything.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pricing as PX

SRC = 'novig_paper'
EDGE_MIN = 0.03                  # fair chance minus break-even chance, after the placeholder fee (the ledger's threshold)
STAKE = 5.0                      # dollars per paper order, inside the planned micro-stake range of $1 to $5
FEE_ON_PROFIT = 0.02             # PLACEHOLDER until Novig's fee schedule is confirmed (share of winnings paid on a win)
TRACK_H = 24                     # only games tipping within this many hours
MAX_ORDERS_PER_PROP = 4          # one order per rung side, at most this many per player-stat, so a ladder does not become 20 correlated bets
TICK = 0.01
STATS = ('pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra')   # the stats with a validated projection and book blend; extra markets are never traded
STAT_BOX = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['threePointFieldGoalsMade'], 'pra': ['points', 'rebounds', 'assists'],
            'pr': ['points', 'rebounds'], 'pa': ['points', 'assists'], 'ra': ['rebounds', 'assists']}


def breakeven(p, fee=FEE_ON_PROFIT):
    """The win chance needed to break even paying p for a $1 contract when `fee` of the profit is paid on a win."""
    return p / (p + (1 - p) * (1 - fee))


def limit_for(fair, fee=FEE_ON_PROFIT, edge=EDGE_MIN):
    """Highest whole-cent price at which fair - breakeven(price) >= edge, or None."""
    p = math.floor(fair * 100 + 1e-9) / 100
    while p >= TICK:
        if fair - breakeven(p, fee) >= edge - 1e-12:
            return round(p, 2)
        p = round(p - TICK, 2)
    return None


def over_price(tape_row, over_idx=0):
    """A tape row's execution price expressed as the OVER outcome's price (a trade at x on one outcome is 1 - x on the other)."""
    return tape_row['px'] if tape_row.get('o') == over_idx else 1 - tape_row['px']


def log(day, board, now, pricer=None):
    """Place and update paper orders for games tipping within TRACK_H. -> (rows, meta)."""
    rows, meta = {}, {}
    nv = (board or {}).get('novig') or {}
    if not board or not nv.get('props') or not board.get('games'):
        return rows, meta
    pr = pricer or PX.Pricer(example=bool(board.get('example')))
    if not pr.MM:
        return rows, meta
    games = {str(g['id']): g for g in board['games']}
    status, outs, cache = PX.status_from_board(board), PX.outs_from_board(board), {}
    prev = dict((day.last.get(SRC) or {}) if day is not None else {})
    pmeta = (day.meta.get(SRC) or {}) if day is not None else {}
    tape = nv.get('tape') or []
    for k, v in prev.items():                                   # keep every existing order in the poll's rows (Day.record drops keys that go missing)
        rows[k] = v
        if k in pmeta:
            meta[k] = {kk: vv for kk, vv in pmeta[k].items() if kk not in ('k', 'src')}
    # 1. fills for open orders, from executions printed after the order was placed
    for k, v in prev.items():
        m = meta.get(k)
        if not m or v[0] != 'open' or now >= m['tip']:
            continue
        side_over = m['side'] == 'Over'
        t0, price = v[1], v[2]
        for t in tape:
            if str(t.get('m')) != str(m['mid']) or t['t'] <= t0 or t['t'] >= m['tip']:
                continue
            px = over_price(t) if side_over else 1 - over_price(t)       # price of OUR outcome in that execution
            if v[8] is None and px <= price + 1e-9:                      # touch
                v = list(v); v[8], v[9] = t['t'], round(px, 3)
            if v[10] is None and px <= price - TICK + 1e-9:              # thru
                v = list(v); v[10], v[11] = t['t'], round(px, 3)
        rows[k] = v
    # 2. new orders
    for key, N in (nv['props'] or {}).items():
        s, g = N.get('s'), games.get(str(N.get('g')))
        if s not in STATS or not g or not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        P = (board.get('players') or {}).get(str(N['p'])) or (board.get('players') or {}).get(N['p'])
        team = P[1] if P else None
        mm = pr.mu_for(N['p'], s, g, cache, outs, team, status)
        if not mm or not (mm['min'] > 0):
            continue
        if pr.roster_hold(mm['team'], g, status, cache, mm.get('src')):          # new rosters and preseason rotations are never traded
            continue
        bc = pr.PR['book'].get(s)
        if not bc:
            continue
        made = sum(1 for k2 in rows if k2.startswith(f"{g['id']}|{N['p']}|{s}|"))
        for L in sorted(N.get('lad') or [], key=lambda x: abs((x.get('mid') if x.get('mid') is not None else .5) - .5)):      # rungs nearest 50% first: that is where the liquidity is
            line, mid = L.get('k'), L.get('mid')
            if mid is None or line is None or (line * 2) % 2 != 1 or made >= MAX_ORDERS_PER_PROP:     # only half-lines: no push; only a real two-sided quote is a price
                continue
            pm = pr.cal(s, pr.p_over_raw(s, mm['mu'], line, mm['extra']))
            fair_o = PX.blend(bc, min(.99, max(.01, mid)), pm)
            for side, fair, bid, ask in (('Over', fair_o, L['bid'][0], L['ask'][0]), ('Under', 1 - fair_o, L['bid'][1], L['ask'][1])):
                k = f"{g['id']}|{N['p']}|{s}|{line}|{side}"
                if k in rows or made >= MAX_ORDERS_PER_PROP:
                    continue
                p = limit_for(fair)
                if p is None:
                    continue
                if ask is not None and ask <= p + 1e-9:
                    kind, price, fill_t, fill_px = 'taker', ask, now, ask                  # marketable: pay the ask now
                else:
                    kind, price, fill_t, fill_px = 'maker', p, None, None                  # rests at our price, below fair; fills only if sellers come down to it
                made += 1
                rows[k] = ['filled' if kind == 'taker' else 'open', now, round(price, 3), kind, round(fair, 4), round(fair - breakeven(price), 4), STAKE,
                           ask, fill_t, fill_px, fill_t if kind == 'taker' else None, fill_px if kind == 'taker' else None, round(mid, 4), L.get('depth')]
                meta[k] = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': N['p'], 'stat': s, 'line': line,
                           'side': side, 'mid': L['id'], 'team': mm['team'], 'player': (P[0] if P else str(N['p'])), 'pre': g.get('season_type') == 1}
    return rows, meta


# row layout: 0 status, 1 placed t, 2 limit/fill price, 3 kind, 4 fair, 5 edge at placement (after fee), 6 stake $, 7 ask at placement,
#             8 touch fill t, 9 touch fill px, 10 thru fill t, 11 thru fill px, 12 mid at placement, 13 depth at placement


def pnl(side, line, actual, price, stake, fee=FEE_ON_PROFIT):
    """Dollars won or lost on a filled paper order, and the gross figure without the fee. None if it pushed (half-lines never do)."""
    won = actual > line if side == 'Over' else actual < line
    contracts = stake / price
    gross = contracts * (1 - price) if won else -stake
    return round(gross * (1 - fee) if won else gross, 4), round(gross, 4)


def record(root, now, prev, rescan_days, games, L):
    """Per tip day: each order settled. Fill assumptions kept separate. L is the ledger module (box, load_src, tip_day, SETTLE_AFTER_S)."""
    days = dict(prev or {})
    since = L.tip_day(now - rescan_days * 86400)
    per_day = {}
    for k, x in L.load_src(root, SRC, since).items():
        m = x['meta']
        series = [v for t, v in sorted(x['series']) if v is not None and m and t <= m['tip']]
        if not m or not series or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        v = series[-1]
        bx = L.box(root, m['game'])
        if bx is None:
            continue
        st = bx.get(int(m['pid']))
        actual = None if not st else sum(st.get(c, 0) for c in STAT_BOX[m['stat']])
        o = {'k': k, 'tip': m['tip'], 'matchup': m['matchup'], 'player': m['player'], 'team': m['team'], 'stat': m['stat'], 'line': m['line'], 'side': m['side'],
             'kind': v[3], 'placed': v[1], 'limit': v[2], 'fair': v[4], 'edge': v[5], 'stake': v[6], 'ask': v[7], 'mid': v[12], 'actual': actual,
             'touch': None, 'thru': None, 'ask_pnl': None}
        if actual is None:
            o['void'] = True                                        # did not play: refunded
        else:
            if v[8] is not None:
                o['touch'] = list(pnl(m['side'], m['line'], actual, v[2], v[6]))      # a resting order fills at ITS price, not the better price that printed
            if v[10] is not None:
                o['thru'] = list(pnl(m['side'], m['line'], actual, v[2], v[6]))
            if v[7] is not None and 0 < v[7] < 1:                   # what taking the ask at placement would have made
                o['ask_pnl'] = list(pnl(m['side'], m['line'], actual, v[7], v[6]))
        per_day.setdefault(L.tip_day(m['tip']), []).append(o)
    for d, os_ in per_day.items():
        days[d] = sorted(os_, key=lambda o: (o['tip'], o['player'], o['stat'], o['line']))
    return days


if __name__ == '__main__':
    print(f"edge {EDGE_MIN}, stake ${STAKE}, placeholder fee {FEE_ON_PROFIT:.0%} of winnings")
    for f in (.40, .50, .60):
        print(f"fair {f:.2f}: break-even at 50c {breakeven(.5):.4f}, limit {limit_for(f)}")
