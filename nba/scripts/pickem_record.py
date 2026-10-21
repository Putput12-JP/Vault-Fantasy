#!/usr/bin/env python3
"""
Pick'em of the Night record: the best slip of every size (2 to 6 picks) on every app, built the way the page builds it and settled from the box score.

The page (Pick'em of the Night, ppLegs / ppBuild in ui/projections.template.html) builds one slip per size and app: the picks the market says are most
likely, one player per team. This module logs the legs it would use and, after the games, rebuilds the slips and scores them. Nothing here is a bet and
nothing changes a price: it is a record of what the page would have told you to look at.

  log(board, now)   -> (rows, meta) for Day.record('pkn', ...), called by snapshot.py after each poll, for games within ledger.TRACK_H of tip.
                       leg row    gid|pid|stat|app|line   [line, 1 if the side is over else 0, market chance of the side, model chance of the side]
                       slate row  gid|slate               [number of legs]    (one per game, so the day's first tip is known even if the game has no legs)
  record(...)       -> per tip day: every slip, settled (called by ledger.settle).

Rules, fixed here before any result (the page's rules ported line for line; docs/pickem-night-record.md):
  * Legs: a pick'em line the board can price, with a consensus chance from the other venues (no consensus, no leg); the side is the one the consensus
    likes (over at 50% or more); a line more than 40% away from the projection is dropped; a priced line (Underdog, Sleeper) must sit near even money
    (44% to 56%) on the chosen side; Out, Doubtful, Questionable and Inactive players are never in a slip; a prop held by the roster guard, a stale
    source or a returning player is never in a slip.
  * Slip: legs sorted by market chance, highest first, one player per team, the first n. Pays the standard multiple (PAYS), joint chance = the product of the
    legs' chances, average per $1 = pays x joint - 1, call Lean at EDGE_MIN or more, else Pass. Every slip is tracked, Pass included, because the page shows Pass slips.
  * Lock: the day's slate is locked at the first tip of the tip day. Each leg is taken as of its last record before that moment, so a slip is what a
    player entering one slip for the night would have seen. A leg that was withdrawn before the lock is not in the slate.
  * Settle: when every leg's game is final. Any leg lost = lost; else any leg landed on its line = push; else won; a player who did not play voids the slip.
    Profit per $1 staked: won = pays - 1, lost = -1, push and void = 0 (the page's rule).
  * "Best app" is not stored: it is the app with the highest average per $1 for that size, chosen from the stored slips.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

PAYS = {2: 3, 3: 5, 4: 10, 5: 20, 6: 37.5}         # standard Power Play multiples, as the page's PP_PAYS
APPS = ['PrizePicks', 'Underdog', 'Sleeper']
CORE = ['pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra']
BAD_STATUS = ('Out', 'Doubtful', 'Questionable', 'Inactive')
MIN_PX, MAX_PX = .44, .56                           # a priced line must sit near even money on the chosen side
FAR = .40                                           # a line this far from the projection is a different minutes situation


def legs_from_board(board, now):
    """Every leg the page would put in a slip: [{pid, name, team, stat, app, line, over, p, pm, gid, tip}]."""
    import pricing as PX
    if not board or not board.get('games') or not board.get('props'):
        return []
    import ledger
    games = {str(g['id']): g for g in board['games'] if now < g['tip'] <= now + ledger.TRACK_H * 3600}
    if not games or not any(e.get('pk') for e in board['props'] if str(e['g']) in games):
        return []
    status = PX.status_from_board(board)
    rows = [r for r in PX.price_board({**board, 'props': [e for e in board['props'] if str(e['g']) in games and e.get('pk') and e['s'] in CORE]})
            if r['venue'] == 'pickem']
    by = {}
    for r in rows:
        by.setdefault((r['p'], r['s'], r['gid'], r['bk'], r['line']), {})[r['side']] = r
    out = []
    for (pid, stat, gid, app, line), sides in by.items():
        ov, un = sides.get('Over'), sides.get('Under')
        if not ov or not un or ov.get('hold') or ov.get('cons') is None or ov['fair'] is None:
            continue
        if status.get(int(pid)) in BAD_STATUS:
            continue
        if ov['mu'] > 0 and abs(line - ov['mu']) / ov['mu'] > FAR:
            continue
        over = ov['cons'] >= .5
        c = ov if over else un
        px = PX.am_p(c['price']) if c.get('price') is not None else None
        if px is not None and not (MIN_PX <= px <= MAX_PX):
            continue
        P = (board.get('players') or {}).get(str(pid)) or (board.get('players') or {}).get(pid)
        out.append({'pid': int(pid), 'name': P[0] if P else str(pid), 'team': ov['team'], 'stat': stat, 'app': app, 'line': line, 'over': over,
                    'p': c['cons'], 'pm': c['fair'], 'gid': gid, 'tip': games[gid]['tip']})
    return out


def log(board, now):
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    import ledger
    for g in board['games']:
        if now < g['tip'] <= now + ledger.TRACK_H * 3600:
            k = f"{g['id']}|slate"
            rows[k] = [0]
            meta[k] = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'kind': 'slate'}
    for L in legs_from_board(board, now):
        k = f"{L['gid']}|{L['pid']}|{L['stat']}|{L['app']}|{L['line']}"
        rows[k] = [L['line'], 1 if L['over'] else 0, round(L['p'], 4), round(L['pm'], 4)]
        meta[k] = {'game': L['gid'], 'tip': L['tip'], 'pid': L['pid'], 'player': L['name'], 'team': L['team'], 'stat': L['stat'], 'app': L['app'], 'kind': 'leg'}
    for g in board['games']:                      # the slate row carries how many legs the game has, so a quiet game is visible
        k = f"{g['id']}|slate"
        if k in rows:
            rows[k] = [sum(1 for m in meta.values() if m['kind'] == 'leg' and m['game'] == str(g['id']))]
    return rows, meta


def build(legs, n, pay):
    """The page's ppBuild: best n legs by market chance, one player per team. None when there are not n different teams."""
    pool = sorted(legs, key=lambda l: -l['p'])
    used, pick = set(), []
    for l in pool:
        if l['team'] in used:
            continue
        used.add(l['team']); pick.append(l)
        if len(pick) == n:
            break
    if len(pick) < n:
        return None
    joint = 1.0
    for l in pick:
        joint *= l['p']
    return pick, joint, pay * joint - 1


def record(root, now, prev, rescan_days, games, L):
    """Per tip day: every slip of every size and app, built from the legs as of the day's first tip and settled from the box score. L is the ledger
    module, passed in because ledger imports this module. Days outside the rescan window are kept."""
    import pricing as PX
    days = dict(prev or {})
    since = L.tip_day(now - rescan_days * 86400)
    by_day = {}
    for k, x in L.load_src(root, 'pkn', since).items():
        m = x['meta']
        if not m or (games and not games(str(m['game']))):
            continue
        by_day.setdefault(L.tip_day(m['tip']), []).append((k, m, sorted(x['series'])))
    for day, items in by_day.items():
        lock = min(m['tip'] for k, m, s in items)
        if now < lock:
            continue
        legs = []
        for k, m, series in items:
            if m['kind'] != 'leg':
                continue
            pre = [(t, v) for t, v in series if t < lock]
            if not pre or pre[-1][1] is None:
                continue
            line, over, p, pm = pre[-1][1]
            legs.append({'pid': m['pid'], 'name': m['player'], 'team': m['team'], 'stat': m['stat'], 'app': m['app'], 'line': line, 'over': bool(over),
                         'p': p, 'pm': pm, 'gid': m['game'], 'tip': m['tip']})
        slips = []
        for n, pay in PAYS.items():
            for app in APPS:
                b = build([l for l in legs if l['app'] == app], n, pay)
                if not b:
                    continue
                pick, joint, ev = b
                res_legs, final = [], True
                for l in pick:
                    bx = L.box(root, l['gid']) if now >= l['tip'] + L.SETTLE_AFTER_S else None
                    if bx is None:
                        final = False
                        break
                    st = bx.get(int(l['pid']))
                    if not st:
                        res_legs.append([l, None, 'D'])
                        continue
                    y = sum(st.get(c, 0) for c in L.STAT_COL[l['stat']])
                    r = 'P' if y == l['line'] else 'W' if (y > l['line']) == l['over'] else 'L'
                    res_legs.append([l, y, r])
                if not final:
                    continue
                rs = [r for _, _, r in res_legs]
                res = 'void' if 'D' in rs else 'lost' if 'L' in rs else 'push' if 'P' in rs else 'won'
                slips.append({'n': n, 'app': app, 'pay': pay, 'joint': round(joint, 4), 'ev': round(ev, 4), 'call': 'lean' if ev >= PX.EDGE_MIN else 'pass',
                              'res': res, 'pl': round(pay - 1, 4) if res == 'won' else -1 if res == 'lost' else 0,
                              'legs': [[l['pid'], l['name'], l['team'], l['stat'], l['line'], 'o' if l['over'] else 'u', l['p'], l['pm'], y, r] for l, y, r in res_legs]})
        if slips:
            days[day] = {'lock': lock, 'slips': slips}
    return days
