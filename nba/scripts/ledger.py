#!/usr/bin/env python3
"""
Shadow ledger: every prop edge the Player Props page shows, logged as it happens, settled from the box score.
Nothing here is a real bet. It is how a signal earns GO on this season's games (docs/PLAN.md: promote a market only
when live results agree with the backtest).

Logging (called by snapshot.py after each poll, from the same board the page reads):
  - pricing.py prices every candidate exactly as the page does (Minutes Lab minutes with Outs applied, prop model v2,
    calibration, market blend, fees, gates).
  - A candidate is TRACKED from the first poll its edge reaches EDGE_MIN (3%, the backtest's threshold), for games
    tipping within TRACK_H hours, and then recorded every time its price, fair or edge changes until tip, whether or
    not the edge lasts. Stored as source 'ledger' in the day folder: snapshots/<day>/ledger.jsonl (change-only, like
    prices) with meta.jsonl describing each key.
  - Key: game|player|stat|venue|book|side|line.  Value: [price, fair, edge, gate, projection, minutes].

Settling (settle(), same job, each poll): for games that tipped 3+ hours ago, ESPN's box score (cached under
results/<game>.json). One shadow bet per key, 1 unit:
  entry  the first poll it reached 3% (the price a live bettor could have taken then)
  close  the last poll before tip (closest to the backtest's clock: Kalshi 30-minute pre-tip VWAP)
  Kalshi YES wins if the stat is over the rung's floor line; cost = price + taker fee (0.07 p (1-p), rounded up).
  Books: over / under the line, American odds, a whole-number landing on the line is a push.
  Player did not play: void (books refund; Kalshi's own rule may differ, noted on the page).
  CLV = the same side's price at close minus at entry, in probability points (positive = the market came to us).
Writes track.json at the recorder root: every bet plus summaries by gate and by signal, with each GO / WATCH signal's
2025-26 backtest result next to it.
"""
import datetime as dt, glob, json, math, os, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pricing as PX
from nba_common import et

TRACK_H = 24                 # only games tipping within this many hours are logged
SETTLE_AFTER_S = 3 * 3600    # a game is checked for a final score this long after tip
SUMMARY = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={}'
STAT_COL = {'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists'], '3pm': ['threePointFieldGoalsMade'],
            'pra': ['points', 'rebounds', 'assists'], 'pr': ['points', 'rebounds'], 'pa': ['points', 'assists'],
            'ra': ['rebounds', 'assists']}


# ── logging ──────────────────────────────────────────────────────────────────────────────────
def log(day, board, now):
    """-> (rows, meta) for Day.record('ledger', ...). Tracked keys that are missing now (tipped, delisted) are recorded
    as gone by Day.record itself."""
    if not board or not board.get('props'):
        return {}, {}
    tracked = set((day.last.get('ledger') or {}).keys())
    games = {str(g['id']): g for g in board.get('games', [])}
    rows, meta = {}, {}
    for c in PX.price_board(board):
        g = games.get(c['gid'])
        if not g or not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        k = f"{c['gid']}|{c['p']}|{c['s']}|{c['venue']}|{c['bk']}|{c['side']}|{c['line']}"
        if k not in tracked and c['edge'] < PX.EDGE_MIN:
            continue
        rows[k] = [round(c['price'], 4) if isinstance(c['price'], float) else c['price'], round(c['fair'], 4), round(c['edge'], 4), c['g'], round(c['mu'], 2), round(c['min'], 1)]
        P = board['players'].get(str(c['p'])) or board['players'].get(c['p']) or [str(c['p']), c['team']]
        meta[k] = {'game': c['gid'], 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': c['p'], 'player': P[0],
                   'team': P[1], 'stat': c['s'], 'venue': c['venue'], 'book': c['bk'], 'side': c['side'], 'line': c['line']}
    return rows, meta


# ── settling ─────────────────────────────────────────────────────────────────────────────────
def curl_json(url):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '30', url], capture_output=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def box(root, gid):
    """{athlete_id: {stat: value} or None (did not play)} once the game is final, cached; None if not final yet."""
    path = os.path.join(root, 'results', f'{gid}.json')
    if os.path.exists(path):
        return {int(k): v for k, v in json.load(open(path)).items()}
    d = curl_json(SUMMARY.format(gid))
    try:
        if not d['header']['competitions'][0]['status']['type']['completed']:
            return None
    except (KeyError, IndexError, TypeError):
        return None
    out = {}
    for team in (d.get('boxscore') or {}).get('players', []):
        for block in team.get('statistics', [])[:1]:
            keys = block.get('keys') or []
            for a in block.get('athletes', []):
                aid = int(a['athlete']['id'])
                if a.get('didNotPlay') or not a.get('stats'):
                    out[aid] = None
                    continue
                v = {}
                for key, raw in zip(keys, a['stats']):
                    for part, name in zip(raw.split('-'), key.split('-')):
                        try:
                            v[name] = float(part)
                        except ValueError:
                            pass
                out[aid] = v
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    return out


def cost(venue, price):
    """Probability-scale cost of the side, fee included (what a win must beat)."""
    if venue == 'kalshi':
        return price + PX.k_fee(price)
    return PX.am_p(price)


def profit(venue, price, won):
    """Per 1 unit risked."""
    if won is None:
        return 0.0
    if venue == 'kalshi':
        c = price + PX.k_fee(price)
        return (1 - c) / c if won else -1.0
    a = float(price)
    return (a / 100 if a > 0 else 100 / -a) if won else -1.0


def outcome(side, line, y):
    """True win / False loss / None push."""
    if y == line:
        return None
    over = y > line
    return over if side in ('Over', 'YES') else not over


def load_ledger(root, since=None):
    """key -> {'meta', 'series': [(t, v)]} across day folders from `since` (YYYY-MM-DD) on; a game can span two."""
    L = defaultdict(lambda: {'meta': None, 'series': []})
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if since and os.path.basename(d) < since:
            continue
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if '"src":"ledger"' not in line:          # meta.jsonl holds every source; skip the parse
                    continue
                r = json.loads(line)
                L[r['k']]['meta'] = {k: v for k, v in r.items() if k not in ('k', 'src')}
        lp = os.path.join(d, 'ledger.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                r = json.loads(line)
                L[r['k']]['series'].append((r['t'], r['v']))
    for x in L.values():
        x['series'].sort(key=lambda z: z[0])
    return L


def backtest_refs():
    """Each GO / WATCH signal's 2025-26 out-of-sample result, for the page to compare against."""
    import render_app
    return (render_app.pricing() or {}).get('backtest') or {}


def summarize(bets, keyf):
    groups = defaultdict(list)
    for b in bets:
        groups[keyf(b)].append(b)
    out = {}
    for k, bs in groups.items():
        done = [b for b in bs if b['result'] in ('win', 'loss', 'push')]
        pnl = [b['pnl'] for b in done]
        pnl_c = [b['pnl_close'] for b in done if b.get('pnl_close') is not None]
        clv = [b['clv'] for b in bs if b.get('clv') is not None]
        n = len(pnl)
        sd = math.sqrt(sum((x - sum(pnl) / n) ** 2 for x in pnl) / (n - 1)) if n > 1 else None
        out[k] = {'bets': len(bs), 'settled': n, 'open': sum(b['result'] == 'open' for b in bs), 'void': sum(b['result'] == 'void' for b in bs),
                  'w': sum(b['result'] == 'win' for b in bs), 'l': sum(b['result'] == 'loss' for b in bs), 'p': sum(b['result'] == 'push' for b in bs),
                  'units': round(sum(pnl), 3), 'roi': round(sum(pnl) / n, 4) if n else None,
                  'roi_close': round(sum(pnl_c) / len(pnl_c), 4) if pnl_c else None,
                  'z': round(sum(pnl) / n / (sd / math.sqrt(n)), 2) if sd else None,
                  'clv': round(sum(clv) / len(clv), 4) if clv else None, 'games': len({b['game'] for b in done}),
                  'edge': round(sum(b['edge'] for b in bs) / len(bs), 4)}
    return out


def bet_from(k, m, series):
    """One shadow bet from a ledger key's history, or None if it never reached EDGE_MIN before tip."""
    pre = [(t, v) for t, v in series if v is not None and t < m['tip']]
    ent = next(((t, v) for t, v in pre if v[2] >= PX.EDGE_MIN), None)
    if not ent:
        return None
    (te, ve), (tc, vc) = ent, pre[-1]
    ce, cc = cost(m['venue'], ve[0]), cost(m['venue'], vc[0])
    return {'k': k, 'game': m['game'], 'tip': m['tip'], 'matchup': m['matchup'], 'pid': m['pid'], 'player': m['player'],
            'team': m['team'], 'stat': m['stat'], 'venue': m['venue'], 'book': m['book'], 'side': m['side'], 'line': m['line'],
            'gate': ve[3], 't': te, 'price': ve[0], 'fair': ve[1], 'edge': ve[2], 'mu': ve[4], 'min': ve[5],
            't_close': tc, 'price_close': vc[0], 'fair_close': vc[1], 'edge_close': vc[2],
            'clv': round(cc - ce, 4) if ce is not None and cc is not None else None,
            'result': 'open', 'actual': None, 'pnl': None, 'pnl_close': None}


def grade(b, root, now):
    """Settle an open bet in place once its game is final."""
    if b['result'] != 'open' or now < b['tip'] + SETTLE_AFTER_S:
        return
    bx = box(root, b['game'])
    if bx is None:
        return
    st = bx.get(int(b['pid']))
    if st is None:
        b['result'] = 'void'
        return
    y = sum(st.get(c, 0) for c in STAT_COL[b['stat']])
    won = outcome(b['side'], float(b['line']), y)
    b.update(actual=y, result='push' if won is None else 'win' if won else 'loss',
             pnl=round(profit(b['venue'], b['price'], won), 4), pnl_close=round(profit(b['venue'], b['price_close'], won), 4))


def settle(root, now=None, rescan_days=3):
    """Settle what is settleable and write track.json. Bets whose games are more than a day past tip come from the
    previous track.json; only the last few day folders are re-read (a key is logged within TRACK_H of its tip).
    Returns the number of bets."""
    now = now or int(time.time())
    path = os.path.join(root, 'track.json')
    prev = {b['k']: b for b in (json.load(open(path)).get('bets', []) if os.path.exists(path) else [])}
    since = et(dt.datetime.fromtimestamp(now - rescan_days * 86400, dt.timezone.utc)).date().isoformat()
    fresh = {}
    for k, x in load_ledger(root, since).items():
        if x['meta'] and x['series']:
            b = bet_from(k, x['meta'], x['series'])
            if b:
                old = prev.get(k)
                if old and old['t'] < b['t']:          # the entry was logged before the rescan window: keep it
                    b.update({f: old[f] for f in ('t', 'price', 'fair', 'edge', 'gate', 'mu', 'min')})
                    ce, cc = cost(b['venue'], b['price']), cost(b['venue'], b['price_close'])
                    b['clv'] = round(cc - ce, 4) if ce is not None and cc is not None else None
                fresh[k] = b
    bets = {**prev, **fresh}
    for b in bets.values():
        grade(b, root, now)
    bets = sorted(bets.values(), key=lambda b: (b['tip'], b['player'], b['stat'], b['line']))
    track = {'t': now, 'edge_min': PX.EDGE_MIN, 'n': len(bets),
             'by_gate': summarize(bets, lambda b: b['gate']),
             'by_signal': summarize(bets, lambda b: f"{b['stat']}|{b['venue']}|{b['side'] if b['venue'] == 'kalshi' else b['side'].lower()}"),
             'by_day': summarize([b for b in bets if b['result'] != 'open'],
                                 lambda b: et(dt.datetime.fromtimestamp(b['tip'], dt.timezone.utc)).date().isoformat() + '|' + b['gate']),
             'backtest': backtest_refs(), 'bets': bets}
    with open(path, 'w') as f:
        json.dump(track, f, separators=(',', ':'))
    return len(bets)
