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
  - Key: game|player|stat|venue|book|side|line.  Value: [price, fair, edge, gate, projection, minutes, consensus,
    consensus edge, consensus gate]. A candidate is tracked when EITHER edge reaches 3%: the model's (fair from our
    projection blended with the price) or the consensus engine's (consensus.py: every other venue moved to this line).
    Each bet records which one triggered it (etype model / gap / both), so the Track Record can compare them.

Settling (settle(), same job, each poll): for games that tipped 3+ hours ago, ESPN's box score (cached under
results/<game>.json). One shadow bet per key, 1 unit:
  entry  the first poll it reached 3% (the price a live bettor could have taken then)
  close  the last poll before tip (closest to the backtest's clock: Kalshi 30-minute pre-tip VWAP)
  Kalshi YES wins if the stat is over the rung's floor line; cost = price + taker fee (0.07 p (1-p), rounded up).
  Books: over / under the line, American odds, a whole-number landing on the line is a push.
  Player did not play: void (books refund; Kalshi's own rule may differ, noted on the page).
  CLV = the same side's price at close minus at entry, in probability points (positive = the market came to us).
Pick'em lines are logged too (venue 'pickem'): a flat line (PrizePicks) is settled as one pick at the flex
break-even price (PK_BE, about -119), a priced line (Underdog, Sleeper) at its own price.

Storage, sized for a season of 100k+ bets:
  bets/<tip ET date>.json   every bet for games tipping that day (only recent days are rewritten)
  track.json                the cube (one row per tip day x stat x venue x book x side x gate x edge bucket with
                            counts, units, sum of squares, CLV sums; every market the page can filter or group),
                            the latest bets, and the GO / WATCH backtest results. Small enough to read every poll.
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
        if k not in tracked and c['edge'] < PX.EDGE_MIN and (c.get('gap') is None or c['gap'] < PX.EDGE_MIN):
            continue
        rows[k] = [round(c['price'], 4) if isinstance(c['price'], float) else c['price'], round(c['fair'], 4), round(c['edge'], 4), c['g'], round(c['mu'], 2), round(c['min'], 1),
                   c.get('cons'), round(c['gap'], 4) if c.get('gap') is not None else None, c.get('gap_g', 'no-go'), ','.join(c.get('types') or [])]
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
    out, starters = {}, []
    for team in (d.get('boxscore') or {}).get('players', []):
        for block in team.get('statistics', [])[:1]:
            keys = block.get('keys') or []
            for a in block.get('athletes', []):
                aid = int(a['athlete']['id'])
                if a.get('starter'):
                    starters.append(aid)
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
    try:                                          # final score and starters, for the Minutes Lab's record
        comp = d['header']['competitions'][0]
        score = {c['team']['abbreviation']: float(c.get('score') or 0) for c in comp['competitors']}
    except (KeyError, IndexError, TypeError, ValueError):
        score = {}
    json.dump({'score': score, 'starters': starters}, open(os.path.join(root, 'results', f'{gid}.meta.json'), 'w'), separators=(',', ':'))
    return out


def box_meta(root, gid):
    path = os.path.join(root, 'results', f'{gid}.meta.json')
    return json.load(open(path)) if os.path.exists(path) else {}


# ── the Minutes Lab's record: tonight's projected minutes against the box score ─────────────────
def minutes_log(board, now):
    """Every player's projected minutes for games within TRACK_H, as live pricing computes them (pricing.py
    game_minutes, the backtest's path) -> (rows, meta) for Day.record('minutes', ...). Value: [minutes, recent avg]."""
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    pr = PX.Pricer(example=bool(board.get('example')))
    if not pr.MM:
        return rows, meta
    status, cache = PX.status_from_board(board), {}
    names = {int(k): v.get('nm') for k, v in pr.state['players'].items() if v.get('nm')}
    names.update({x['id']: x['name'] for T in pr.D['teams'].values() for x in T['players']})
    names.update({int(k): v[0] for k, v in (board.get('players') or {}).items()})
    fives = board.get('starters') or {}
    for g in board['games']:
        if not (now < g['tip'] <= now + TRACK_H * 3600):
            continue
        for team in (g['away'], g['home']):
            five = fives.get(team)
            v3 = pr.game_minutes_v3(team, g, status, cache, starters=five)       # shadow, never priced
            for pid, G in pr.game_minutes(team, g, status, cache).items():
                k = f"{g['id']}|{pid}"
                rows[k] = [round(G['min'], 2), round((pr.state['players'].get(str(pid)) or {}).get('ms', [0])[0], 2),
                           round(v3[pid], 2) if pid in v3 else None, 1 if five else 0]
                meta[k] = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': pid,
                           'player': names.get(pid, str(pid)), 'team': team}
    return rows, meta


def load_src(root, src, since):
    """key -> {'meta', 'series'} for one logged source across day folders from `since` on."""
    L = defaultdict(lambda: {'meta': None, 'series': []})
    tag = f'"src":"{src}"'
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if os.path.basename(d) < since:
            continue
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if tag in line:
                    r = json.loads(line)
                    L[r['k']]['meta'] = {k: v for k, v in r.items() if k not in ('k', 'src')}
        lp = os.path.join(d, f'{src}.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                r = json.loads(line)
                L[r['k']]['series'].append((r['t'], r['v']))
    return L


def wire_record(root, now, prev, rescan_days=3):
    """The Injury Wire's season record: per ET day, per venue, per kind of news (inj / five / inactive), the quotes
    affected, how many moved before tip, and each change's first-move time in seconds (-1 = never moved before tip).
    Read from snapshots/<day>/wire.json (snapshot.save_wire); days older than the rescan window are kept as they were."""
    days = dict(prev or {})
    since = tip_day(now - rescan_days * 86400)
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        day = os.path.basename(d)
        path = os.path.join(d, 'wire.json')
        if day < since or not os.path.exists(path):
            continue
        try:
            events = json.load(open(path)).values()
        except ValueError:
            continue
        rec = {}
        for e in events:
            for venue, (n, m, med, first) in (e[7] or {}).items():
                r = rec.setdefault(venue, {}).setdefault(e[1], {'n': 0, 'm': 0, 'f': []})
                r['n'] += n
                r['m'] += m
                r['f'].append(int(first) if first is not None else -1)
        days[day] = rec
    return days


def minutes_record(root, now, prev, rescan_days=3):
    """Per tip day: projected minutes (last value before tip) against the box score. Players who did not play are
    counted apart (books void their props; the backtest scored players who played). Days already final are kept."""
    days = dict(prev or {})
    since = tip_day(now - rescan_days * 86400)
    per_day = defaultdict(list)
    for k, x in load_src(root, 'minutes', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series']) if v is not None and m and t < m['tip']]
        if not m or not pre or now < m['tip'] + SETTLE_AFTER_S:
            continue
        bx = box(root, m['game'])
        if bx is None:
            continue
        meta = box_meta(root, m['game'])
        st = bx.get(int(m['pid']))
        actual = st.get('minutes', 0.0) if st else 0.0
        reason = ''
        if not st:
            reason = 'did not play'
        else:
            sc = meta.get('score') or {}
            if len(sc) == 2:
                margin = abs(list(sc.values())[0] - list(sc.values())[1])
                if margin >= 20:
                    reason = f'blowout ({int(margin)} pts)'
            if st.get('fouls', 0) >= 5:
                reason = f"foul trouble ({int(st['fouls'])} fouls)"
        v3 = pre[-1][2] if len(pre[-1]) > 2 else None
        per_day[tip_day(m['tip'])].append([m['player'], m['team'], m['matchup'], round(pre[-1][0], 1), round(actual, 1), reason,
                                           round(v3, 1) if v3 is not None else None, pre[-1][3] if len(pre[-1]) > 3 else 0])
    for d, rows in per_day.items():
        played = [r for r in rows if r[5] != 'did not play']
        err = [r[3] - r[4] for r in played]
        both = [r for r in played if r[6] is not None]                 # the shadow: v3 on the same players
        e2, e3 = [r[3] - r[4] for r in both], [r[6] - r[4] for r in both]
        days[d] = {'n': len(played), 'dnp': len(rows) - len(played),
                   'mae': round(sum(abs(e) for e in err) / len(err), 2) if err else None,
                   'bias': round(sum(err) / len(err), 2) if err else None,
                   'miss8': sum(abs(e) >= 8 for e in err),
                   'v3': {'n': len(both), 'starters': sum(r[7] for r in both),
                          'mae_v2': round(sum(abs(e) for e in e2) / len(e2), 3) if e2 else None,
                          'mae_v3': round(sum(abs(e) for e in e3) / len(e3), 3) if e3 else None,
                          'miss8_v2': sum(abs(e) >= 8 for e in e2), 'miss8_v3': sum(abs(e) >= 8 for e in e3)},
                   'worst': sorted(rows, key=lambda r: -abs(r[3] - r[4]))[:12]}
    return days


def cost(venue, price):
    """Probability-scale cost of the side, fee included (what a win must beat)."""
    if venue == 'kalshi':
        return price + PX.k_fee(price)
    if venue == 'pickem' and price is None:
        return PX.PK_BE
    return PX.am_p(price)


def profit(venue, price, won):
    """Per 1 unit risked: a win returns (1 - cost) / cost (the same as American odds for a book price)."""
    if won is None:
        return 0.0
    c = cost(venue, price)
    return (1 - c) / c if won else -1.0


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


EDGE_BINS = [(0.05, '3-5%'), (0.08, '5-8%'), (0.12, '8-12%'), (9, '12%+')]
CUBE_COLS = ['day', 'stat', 'venue', 'book', 'side', 'gate', 'ebin', 'etype', 'bets', 'open', 'void', 'w', 'l', 'p',
             'units', 'units_sq', 'units_close', 'clv_sum', 'clv_n', 'edge_sum']


def family(b):
    """Kalshi / Sportsbooks / Polymarket / Pick'em."""
    return 'kalshi' if b['venue'] == 'kalshi' else 'pickem' if b['venue'] == 'pickem' else 'polymarket' if b['book'] == 'Polymarket' else 'book'


TYPE_COLS = ['type', 'venue', 'stat', 'side', 'bets', 'open', 'w', 'l', 'p', 'units', 'units_sq', 'units_close', 'clv_sum', 'clv_n']


def type_rows(bets):
    """Every bet counted once under each of its edge types (news, stale, ladder, gap, model), all time."""
    agg = {}
    for b in bets:
        side = 'over' if b['side'] in ('Over', 'YES') else 'under'
        for t in b.get('types') or ['model']:
            r = agg.setdefault((t, family(b), b['stat'], side), [0] * 10)
            r[0] += 1
            r[1] += b['result'] == 'open'
            r[2] += b['result'] == 'win'
            r[3] += b['result'] == 'loss'
            r[4] += b['result'] == 'push'
            if b['result'] in ('win', 'loss', 'push'):
                r[5] += b['pnl']
                r[6] += b['pnl'] ** 2
                r[7] += b['pnl_close']
            if b.get('clv') is not None:
                r[8] += b['clv']
                r[9] += 1
    return {k: v for k, v in agg.items()}


def tip_day(ts):
    return et(dt.datetime.fromtimestamp(ts, dt.timezone.utc)).date().isoformat()


def cube_rows(bets):
    """Aggregate bets into cube rows (CUBE_COLS)."""
    agg = {}
    for b in bets:
        ebin = next(l for hi, l in EDGE_BINS if b['edge'] < hi)
        side = 'over' if b['side'] in ('Over', 'YES') else 'under'
        k = (tip_day(b['tip']), b['stat'], family(b), b['book'], side, b['gate'], ebin, b.get('etype', 'model'))
        r = agg.setdefault(k, [0] * 12)
        r[0] += 1
        r[1] += b['result'] == 'open'
        r[2] += b['result'] == 'void'
        r[3] += b['result'] == 'win'
        r[4] += b['result'] == 'loss'
        r[5] += b['result'] == 'push'
        if b['result'] in ('win', 'loss', 'push'):
            r[6] += b['pnl']
            r[7] += b['pnl'] ** 2
            r[8] += b['pnl_close']
        if b.get('clv') is not None:
            r[9] += b['clv']
            r[10] += 1
        r[11] += b['edge']
    return [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in sorted(agg.items())]


GATE_RANK = {'go': 0, 'watch': 1, 'no-go': 2}


def gap_of(v):
    return v[7] if len(v) > 7 else None


def triggers(v):
    """Which edges reached EDGE_MIN in a ledger value: ['model'], ['gap'] or both."""
    return [t for t, x in (('model', v[2]), ('gap', gap_of(v))) if x is not None and x >= PX.EDGE_MIN]


def bet_from(k, m, series):
    """One shadow bet from a ledger key's history, or None if it never reached EDGE_MIN before tip."""
    pre = [(t, v) for t, v in series if v is not None and t < m['tip']]
    ent = next(((t, v) for t, v in pre if triggers(v)), None)
    if not ent:
        return None
    (te, ve), (tc, vc) = ent, pre[-1]
    ce, cc = cost(m['venue'], ve[0]), cost(m['venue'], vc[0])
    trig = triggers(ve)
    gate = min((ve[3] if 'model' in trig else 'no-go', ve[8] if 'gap' in trig else 'no-go'), key=lambda g: GATE_RANK[g])
    etype = 'both' if len(trig) == 2 else trig[0]
    return {'k': k, 'game': m['game'], 'tip': m['tip'], 'matchup': m['matchup'], 'pid': m['pid'], 'player': m['player'],
            'team': m['team'], 'stat': m['stat'], 'venue': m['venue'], 'book': m['book'], 'side': m['side'], 'line': m['line'],
            'gate': gate, 'etype': etype, 't': te, 'price': ve[0], 'fair': ve[1], 'edge': max(ve[2], gap_of(ve) or -1) if 'gap' in trig else ve[2],
            'model_edge': ve[2], 'cons': ve[6] if len(ve) > 6 else None, 'gap_edge': gap_of(ve), 'mu': ve[4], 'min': ve[5],
            'types': [x for x in (ve[9] if len(ve) > 9 else '').split(',') if x] or [{'model': 'model', 'gap': 'gap', 'both': 'gap'}[etype]],
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


def settle(root, now=None, rescan_days=3, keep_recent=600):
    """Settle what is settleable; rewrite bets/<day>.json for the days touched and their cube rows in track.json.
    Only the last `rescan_days` of ledger folders are re-read (a key is logged within TRACK_H of its tip), plus the
    bet files of those days and of any day that still has open bets. Returns the number of bets in the record."""
    now = now or int(time.time())
    tpath, bdir = os.path.join(root, 'track.json'), os.path.join(root, 'bets')
    track = json.load(open(tpath)) if os.path.exists(tpath) else {}
    if 'cube' not in track:                       # the first format kept every bet in track.json: move them to files
        old = track.get('bets') or []
        track = {'cube': [], 'open_days': sorted({tip_day(b['tip']) for b in old}), 'n': 0}
        for d in track['open_days']:
            os.makedirs(bdir, exist_ok=True)
            json.dump([b for b in old if tip_day(b['tip']) == d], open(os.path.join(bdir, f'{d}.json'), 'w'), separators=(',', ':'))
    since = tip_day(now - rescan_days * 86400)
    fresh = {}
    for k, x in load_ledger(root, since).items():
        if x['meta'] and x['series']:
            b = bet_from(k, x['meta'], x['series'])
            if b:
                fresh[k] = b
    days = {tip_day(b['tip']) for b in fresh.values()} | set(track.get('open_days') or [])
    changed = {}
    for d in sorted(days):
        path = os.path.join(bdir, f'{d}.json')
        prev = {b['k']: b for b in (json.load(open(path)) if os.path.exists(path) else [])}
        cur = dict(prev)
        for k, b in fresh.items():
            if tip_day(b['tip']) != d:
                continue
            old = prev.get(k)
            if old and old['t'] < b['t']:              # entry logged before the rescan window: keep it
                b.update({f: old[f] for f in ('t', 'price', 'fair', 'edge', 'gate', 'mu', 'min')})
                ce, cc = cost(b['venue'], b['price']), cost(b['venue'], b['price_close'])
                b['clv'] = round(cc - ce, 4) if ce is not None and cc is not None else None
            if old and old['result'] != 'open':
                b.update({f: old[f] for f in ('result', 'actual', 'pnl', 'pnl_close')})
            cur[k] = b
        for b in cur.values():
            grade(b, root, now)
        changed[d] = sorted(cur.values(), key=lambda b: (b['tip'], b['player'], b['stat'], b['line']))
    os.makedirs(bdir, exist_ok=True)
    for d, bs in changed.items():
        json.dump(bs, open(os.path.join(bdir, f'{d}.json'), 'w'), separators=(',', ':'))
    cube = [r for r in track.get('cube', []) if r[0] not in changed]
    for bs in changed.values():
        cube += cube_rows(bs)
    cube.sort()
    # edge-type totals: kept per tip day so only the days touched are recomputed
    tday = {d: v for d, v in (track.get('types_by_day') or {}).items() if d not in changed}
    for d, bs in changed.items():
        tday[d] = [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in type_rows(bs).items()]
    tot = {}
    for rows in tday.values():
        for r in rows:
            t = tot.setdefault(tuple(r[:4]), [0] * 10)
            for i, x in enumerate(r[4:]):
                t[i] += x
    types = [list(k) + [round(x, 4) if isinstance(x, float) else x for x in v] for k, v in sorted(tot.items())]
    recent = {b['k']: b for b in track.get('bets', [])}
    for bs in changed.values():
        recent.update({b['k']: b for b in bs})
    recent = sorted(recent.values(), key=lambda b: (b['tip'], b['player'], b['stat'], b['line']))[-keep_recent:]
    open_days = sorted(d for d, bs in changed.items() if any(b['result'] == 'open' for b in bs))
    n = sum(r[CUBE_COLS.index('bets')] for r in cube)
    minutes_days = minutes_record(root, now, track.get('minutes_days'), rescan_days)
    wire_days = wire_record(root, now, track.get('wire_days'), rescan_days)
    track = {'t': now, 'edge_min': PX.EDGE_MIN, 'pk_be': PX.PK_BE, 'n': n, 'cube_cols': CUBE_COLS, 'cube': cube, 'minutes_days': minutes_days, 'wire_days': wire_days,
             'type_cols': TYPE_COLS, 'types': types, 'types_by_day': tday,
             'open_days': open_days, 'bets': recent, 'backtest': backtest_refs()}
    with open(tpath, 'w') as f:
        json.dump(track, f, separators=(',', ':'))
    return n
