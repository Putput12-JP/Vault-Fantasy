#!/usr/bin/env python3
"""
Sharp Price: where informed money is on NBA game markets, from free public sources, and whether following it pays.

The rules are the Sharp Money watch's (scripts/fetch-sharp-money.mjs, studied in docs/retro/sharp-money-study.md),
ported so they run in the recorder on Actions next to everything else instead of on one laptop:
  Pinnacle      the market-making book. Its full ladder (main + alternate spreads and totals, moneyline, bet limits)
                is already in the recorder's day files, so its line history is rebuilt from them (pin_replay) and a
                fair price exists at ANY number a soft book hangs: power de-vig of Pinnacle's own price there.
  Polymarket    public trade tape with the account on every trade (poll_tapes -> snapshots/<day>/tape.jsonl).
                Accounts are labelled by their own record against the close (scripts/build_pm_wallets.py ->
                data/pm_wallets_<sport>.json): sharp in the NBA, or sharp in another sport when they have no NBA record
                (skill travels across sports, study section 3); usually-losing from the NBA scorecard.
  Kalshi        anonymous tape on the winner market; only the big tickets mean anything.
  Action        bets % vs money % and the opening line (already on the board, prop_board.game_markets).

Signals (one alert each, kept the first time it fires in snapshots/<day>/signals.json):
  steam    Pinnacle moved past STEAM within 30 minutes (needs a poll inside the previous 25 minutes, else the move
           cannot be timed and only shows on the chart)
  behind   a soft book or exchange priced 3%+ better than Pinnacle's fair at the SAME number (-300 to +300 only)
  sharp    sharp accounts put $1k+ on one side of a market within a 30-minute window
  cross    sharp accounts' 24-hour net on one team reached $25k
  whale    one $10k+ ticket (Polymarket or Kalshi)
  split    20+ points more of the money than of the bets on a side with at most half the bets
Per-prop signals (Player Props page, prop_signals): Pinnacle moving a player prop, sharp accounts trading a
Polymarket prop, heavy money on a Kalshi rung (contracts traded between two polls with the price moving; Kalshi's
tape cannot be filtered to props cheaply, so volume x price is the proxy). Their thresholds are NOT backtested: no
prop sharp history existed. They are logged and graded like the rest and the page says so.
Every alert is graded (grade_signals, from ledger.settle) on closing-line value: Pinnacle's last pre-tip fair at the
alert's number minus the fair when it fired (for behind: the price's EV at the closing fair), and on the final score.
The study's verdict stands until this season says otherwise: sharp accounts beat the close but copying them 30+ minutes
later does not, so these are context until a type earns it (50+ graded, CLV 2 SE above zero).
"""
import datetime as dt, glob, json, math, os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DATA = os.path.join(HERE, '..', '..', 'data')            # pm_wallets_*.json live in the repo's data/
STEAM = {'sp': 1.0, 'tot': 1.5, 'ml': 0.03}                  # NBA thresholds from the watch (points, win-prob points)
STEAM_WIN, GAP_MAX, STEAM_COOL = 30 * 60, 25 * 60, 3 * 3600
WHALE, SHARP_MIN, CROSS_AT = 10000, 1000, 25000
NOV_MIN = 1000                                                # dollars on one side of one Novig market in 30 minutes; a first guess, graded as type 'novig'
BEHIND_MIN, BEHIND_ALERT, BEHIND_MAX = 0.02, 0.03, 0.25
SPLIT_GAP, SPLIT_MAX_T = 20, 50
TAPE_MIN = {'pm': 100, 'kal': 500}                            # dollars; smaller trades are noise and bloat the file
TAPE_AHEAD_H = 48
SOFT = ['DraftKings', 'FanDuel', 'BetMGM', 'BetRivers', 'bet365', 'ESPN BET', 'Caesars']
GRADE_AFTER_S = 3 * 3600
# per-prop thresholds, chosen to be rare, not fitted: a full point on Pinnacle's line or 5 points of its no-vig chance at
# the same line within an hour; $500 of sharp-account money (props trade thinner than game lines); $2,000 traded on one
# Kalshi rung between two polls with the price moving 3 cents
P_LINE, P_PROB, P_WIN, P_SHARP, P_KAL_USD, P_KAL_MOVE = 1.0, 0.05, 3600, 500, 2000, 0.03
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
except Exception:  # pragma: no cover
    ET = dt.timezone(dt.timedelta(hours=-4))


# ── prices ───────────────────────────────────────────────────────────────────────────────────────
def am(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if x and abs(x) >= 100 else None


def imp(a):
    a = am(a)
    return None if a is None else (-a / (-a + 100) if a < 0 else 100 / (a + 100))


def payout(a):
    a = am(a)
    return None if a is None else (100 / -a if a < 0 else a / 100)


def devig(a, b):
    """Power de-vig (x^k + y^k = 1): keeps the favourite-longshot bias out of the fair price."""
    x, y = imp(a), imp(b)
    if not x or not y:
        return None
    lo, hi = 0.5, 3.0
    for _ in range(40):
        k = (lo + hi) / 2
        lo, hi = (k, hi) if x ** k + y ** k > 1 else (lo, k)
    return x ** ((lo + hi) / 2)


def kal_fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def r3(x):
    return None if x is None else round(x, 3)


def et_day(t):
    return dt.datetime.fromtimestamp(t, ET).date().isoformat()


def nick(name):
    return name.split()[-1].lower() if name else None


# ── accounts ─────────────────────────────────────────────────────────────────────────────────────
def wallets():
    """{'sharp': {wallet: sport it earned it in}, 'dull': set, 'rec': {wallet: [trades, avg vs close, t]}, n, generated}."""
    W = {'sharp': {}, 'dull': set(), 'rec': {}, 'n': 0, 'generated': None}
    for sport, f in (('nba', 'pm_wallets_nba.json'), ('nfl', 'pm_wallets.json'), ('cfb', 'pm_wallets_cfb.json')):
        try:
            j = json.load(open(os.path.join(REPO_DATA, f)))
        except (OSError, ValueError):
            continue
        if sport == 'nba':
            W['dull'] = set(j.get('dull') or [])
            W['n'], W['generated'] = len(j.get('wallets') or {}), j.get('generated')
        for w in j.get('sharp') or []:
            if w not in W['sharp'] and w not in W['dull']:          # the NBA record wins over another sport's
                W['sharp'][w] = sport
                a = (j.get('wallets') or {}).get(w)
                if a:
                    n, s, ss = a[0], a[1], a[2]
                    m = s / n
                    sd = math.sqrt(max(ss / n - m * m, 0))
                    W['rec'][w] = [n, round(m, 4), round(m / (sd / math.sqrt(n)), 1) if sd else 0, sport]
    return W


# ── trade tapes (recorder) ───────────────────────────────────────────────────────────────────────
def _tape_rows(dirs):
    for d in dirs:
        p = os.path.join(d, 'tape.jsonl')
        if os.path.exists(p):
            for line in open(p):
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def day_dirs(root, now, back=3):
    days = {(dt.datetime.fromtimestamp(now, ET).date() - dt.timedelta(days=i)).isoformat() for i in range(back + 1)}
    return sorted(d for d in glob.glob(os.path.join(root, 'snapshots', '20*')) if os.path.basename(d) in days)


def poll_tapes(root, day, slate, now, curl, parse_event, team):
    """Append new Polymarket and Kalshi trades on upcoming games' winner / spread / total markets to the day's
    tape.jsonl. Cursor = newest trade already saved for that market (first sight: 24 hours back)."""
    dirs = day_dirs(root, now, 1)
    seen, cur = set(), {}
    for r in _tape_rows(dirs):
        seen.add(r['id'])
        cur[r['k']] = max(cur.get(r['k'], 0), r['t'])
    tips = {(g['day'], team.get(g['home'], g['home'])): g['tip'] for g in slate.games if g['pre']}
    tips.update({(g['day'], g['home']): g['tip'] for g in slate.games if g['pre']})
    jobs = []
    props = []
    for k, m in (day.meta.get('polymarket') or {}).items():
        if not (m.get('cid') and m.get('start') and now < m['start'] <= now + TAPE_AHEAD_H * 3600):
            continue
        if m.get('type') in ('moneyline', 'spreads', 'totals'):
            jobs.append(('pm', k, m))
        elif m.get('type') in ('points', 'rebounds', 'assists', 'threes'):
            props.append((k, m))
    for i in range(0, len(props), 25):                  # player props: thin markets, so one request per 25 of them
        jobs.append(('pmb', [k for k, _ in props[i:i + 25]], {'cids': {m['cid']: k for k, m in props[i:i + 25]}}))
    for k, m in (day.meta.get('kalshi') or {}).items():
        if m.get('series') != 'KXNBAGAME':
            continue
        tip = next((tips.get((d, team.get(h, h))) for d, a, h in parse_event(m['event']) or [] if (d, team.get(h, h)) in tips), None)
        if tip and now < tip <= now + TAPE_AHEAD_H * 3600:
            jobs.append(('kal', k, m))

    def fetch(job):
        src, k, m = job
        if src == 'pmb':                                # batched props: the oldest cursor of the batch, dedup by id
            since, out = min([cur.get(x) or now - 86400 for x in k]), []
            for page in range(5):
                r = curl(f"https://data-api.polymarket.com/trades?market={','.join(m['cids'])}&takerOnly=true&limit=500&offset={page * 500}"
                         f"&filterType=CASH&filterAmount={TAPE_MIN['pm']}")
                if not isinstance(r, list) or not r:
                    break
                old = False
                for x in r:
                    kk = m['cids'].get(x.get('conditionId'))
                    if not kk or x.get('timestamp', 0) <= (cur.get(kk) or now - 86400):
                        old = old or x.get('timestamp', 0) <= since
                        continue
                    usd = (x.get('price') or 0) * (x.get('size') or 0)
                    if usd < TAPE_MIN['pm']:
                        continue
                    buy = x.get('side') == 'BUY'
                    oi = x.get('outcomeIndex') if buy else 1 - (x.get('outcomeIndex') or 0)
                    out.append({'t': x['timestamp'], 's': 'pm', 'k': kk, 'o': oi, 'usd': round(usd), 'px': round(x['price'] if buy else 1 - x['price'], 4),
                                'w': x.get('proxyWallet'), 'who': x.get('pseudonym') or x.get('name'), 'id': f"{(x.get('transactionHash') or '')[:18]}:{oi}:{round(x.get('size') or 0)}"})
                if old or len(r) < 500:
                    break
            return out
        since, out = cur.get(k) or now - 86400, []
        if src == 'pm':
            for page in range(10):
                r = curl(f"https://data-api.polymarket.com/trades?market={m['cid']}&takerOnly=true&limit=500&offset={page * 500}")
                if not isinstance(r, list) or not r:
                    break
                old = False
                for x in r:
                    if x.get('timestamp', 0) <= since:
                        old = True
                        continue
                    usd = (x.get('price') or 0) * (x.get('size') or 0)
                    if usd < TAPE_MIN['pm']:
                        continue
                    buy = x.get('side') == 'BUY'
                    oi = x.get('outcomeIndex') if buy else 1 - (x.get('outcomeIndex') or 0)
                    out.append({'t': x['timestamp'], 's': 'pm', 'k': k, 'o': oi, 'usd': round(usd), 'px': round(x['price'] if buy else 1 - x['price'], 4),
                                'w': x.get('proxyWallet'), 'who': x.get('pseudonym') or x.get('name'), 'id': f"{(x.get('transactionHash') or '')[:18]}:{oi}:{round(x.get('size') or 0)}"})
                if old or len(r) < 500:
                    break
        else:
            r = curl(f"https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker={k}&limit=1000&min_ts={since + 1}")
            for x in (r or {}).get('trades') or []:
                try:
                    ts = int(dt.datetime.fromisoformat(x['created_time'].replace('Z', '+00:00')).timestamp())
                    yes = x.get('taker_side') == 'yes'
                    px = float(x['yes_price_dollars'] if yes else x['no_price_dollars'])
                    n = float(x.get('count_fp') or x.get('count') or 0)
                except (KeyError, ValueError, TypeError):
                    continue
                if ts <= since or px * n < TAPE_MIN['kal']:
                    continue
                out.append({'t': ts, 's': 'kal', 'k': k, 'y': 1 if yes else 0, 'usd': round(px * n), 'px': round(px, 4), 'id': x.get('trade_id')})
        return out

    with ThreadPoolExecutor(6) as ex:
        got = [r for rows in ex.map(fetch, jobs) for r in rows]
    new = sorted((r for r in got if r['id'] not in seen), key=lambda r: r['t'])
    day.append('tape.jsonl', new)
    return len(jobs), len(new)


# ── Pinnacle history from the day files ──────────────────────────────────────────────────────────
def pin_replay(dirs, gmap, tips):
    """gmap {(ET day, home nickname): gid}, tips {gid: tip}. -> {gid: {'series': [[t, sp, spP, tot, oP, ml, [limits]]],
    'ladder': the last ladder before tip}}, plus every poll time (to tell a timed move from a gap)."""
    keys, polls, per_dir = {}, [], []
    for d in dirs:
        mp = os.path.join(d, 'meta.jsonl')
        if os.path.exists(mp):
            for line in open(mp):
                if '"src":"pinnacle"' not in line:
                    continue
                m = json.loads(line)
                if m.get('parent') or m.get('period') != 0 or m.get('type') not in ('spread', 'total', 'moneyline'):
                    continue
                home = next((n for a, n in m.get('teams') or [] if a == 'home'), None)
                gid = gmap.get((et_day(m['start']), nick(home))) if m.get('start') else None
                if gid:
                    keys[m['k']] = (gid, m['type'], str(m.get('side')).lower())
        pp = os.path.join(d, 'polls.jsonl')
        if os.path.exists(pp):
            for line in open(pp):
                if '"src":"pinnacle"' in line:
                    polls.append(json.loads(line)['t'])
        rows = []
        lp = os.path.join(d, 'pinnacle.jsonl')
        if os.path.exists(lp):
            for line in open(lp):
                r = json.loads(line)
                if r['k'] in keys:
                    rows.append(r)
        per_dir.append(sorted(rows, key=lambda r: r['t']))
    state, out = defaultdict(dict), {}
    for rows in per_dir:
        # a day's first poll re-records every live key but never deletes one that vanished overnight: start over
        first = True
        i = 0
        while i < len(rows):
            t, touched = rows[i]['t'], set()
            if first:
                state.clear()
                first = False
            while i < len(rows) and rows[i]['t'] == t:
                gid, typ, side = keys[rows[i]['k']]
                if t < tips.get(gid, 1e12):
                    v = rows[i]['v']
                    if v is None:
                        state[gid].pop((rows[i]['k'], typ, side), None)
                    else:
                        state[gid][(rows[i]['k'], typ, side)] = (v[0], v[1], v[2] if len(v) > 2 else None)
                    touched.add(gid)
                i += 1
            for gid in touched:
                flat = {(typ, side, v[0] if typ != 'moneyline' else None): v for (k, typ, side), v in state[gid].items()}
                s, lad = _snap_flat(flat)
                o = out.setdefault(gid, {'series': [], 'ladder': None})
                row = [t, s['sp'], s['spP'], s['tot'], s['oP'], s['ml'], s['lim']]
                if not o['series'] or o['series'][-1][1:] != row[1:]:
                    o['series'].append(row)
                o['ladder'] = lad
    return out, sorted(set(polls))


def _snap_flat(flat):
    """flat {(type, side, points): (points, price, limit)} -> _snap's result (a ladder has many numbers per side)."""
    sp, to, ml, lim = defaultdict(dict), defaultdict(dict), {}, {}
    for (typ, side, _), (pts, price, limit) in flat.items():
        if typ == 'moneyline':
            ml[side] = (price, limit)
        elif typ == 'spread' and pts is not None:
            sp[pts if side == 'home' else -pts][side] = (price, limit)
        elif typ == 'total' and pts is not None:
            to[pts][side] = (price, limit)
    lad = {'sp': {h: [s['home'][0], s['away'][0]] for h, s in sp.items() if 'home' in s and 'away' in s},
           'tot': {p: [s['over'][0], s['under'][0]] for p, s in to.items() if 'over' in s and 'under' in s},
           'ml': [ml['home'][0], ml['away'][0]] if 'home' in ml and 'away' in ml else None}
    main = lambda D: min(D, key=lambda x: abs((imp(D[x][0]) or 0) - (imp(D[x][1]) or 0)), default=None)
    ms, mt = main(lad['sp']), main(lad['tot'])
    s = {'sp': ms, 'spP': r3(devig(*lad['sp'][ms])) if ms is not None else None,
         'tot': mt, 'oP': r3(devig(*lad['tot'][mt])) if mt is not None else None,
         'ml': r3(devig(*lad['ml'])) if lad['ml'] else None,
         'lim': [sp[ms]['home'][1] if ms is not None else None, to[mt]['over'][1] if mt is not None else None,
                 ml['home'][1] if 'home' in ml else None]}
    return s, lad


def fair(lad, m, side, line=None):
    """Pinnacle's no-vig probability for `side` at `line` (spread: the HOME handicap; total: the total)."""
    if not lad:
        return None
    if m == 'ml':
        p = devig(*lad['ml']) if lad.get('ml') else None
        return None if p is None else (p if side == 'home' else 1 - p)
    L = lad.get(m) or {}
    row = L.get(line)
    if row is None:
        row = next((v for k, v in L.items() if abs(float(k) - float(line)) < 1e-9), None) if line is not None else None
    p = devig(*row) if row else None
    return None if p is None else (p if side in ('home', 'over') else 1 - p)


def level(s, m):
    """One number per market so moves compare: spread points toward home, total toward over, ML home win prob.
    A price change at the same number counts as 1/20 of a point (the watch's rule)."""
    if m == 'ml':
        return s[5]
    if m == 'sp':
        return None if s[1] is None or s[2] is None else -s[1] + (s[2] - 0.5) * 2.5
    return None if s[3] is None or s[4] is None else s[3] + (s[4] - 0.5) * 2.5


def steam_events(series, polls):
    """Pinnacle moves past STEAM within 30 minutes, at most one per market and side per 3 hours."""
    out, last = [], {}
    for i, cur in enumerate(series):
        t = cur[0]
        if not any(t - GAP_MAX <= p < t for p in polls):         # the move cannot be timed
            continue
        ref = next((s for s in reversed(series[:i]) if s[0] <= t - STEAM_WIN), series[0])
        if ref is cur:
            continue
        for m in ('sp', 'tot', 'ml'):
            a, b = level(ref, m), level(cur, m)
            if a is None or b is None or abs(b - a) < STEAM[m]:
                continue
            side = ('over' if b > a else 'under') if m == 'tot' else ('home' if b > a else 'away')
            if last.get((m, side), -1e12) > t - STEAM_COOL:
                continue
            last[(m, side)] = t
            line = cur[1] if m == 'sp' else cur[3] if m == 'tot' else None
            f = (cur[5] if side == 'home' else 1 - cur[5]) if m == 'ml' else \
                (cur[2] if side == 'home' else 1 - cur[2]) if m == 'sp' else (cur[4] if side == 'over' else 1 - cur[4])
            frm = ref[5] if m == 'ml' else ref[1] if m == 'sp' else ref[3]
            out.append({'t': t, 'type': 'steam', 'm': m, 'side': side, 'line': line, 'from': frm,
                        'to': cur[5] if m == 'ml' else line, 'size': round(abs(b - a), 3), 'fair': r3(f)})
    return out


def snap_at(series, t):
    return next((s for s in reversed(series) if s[0] <= t), None)


# ── the board's sharp block ──────────────────────────────────────────────────────────────────────
def build(board, day, root, now, team, parse_event, kal_vol=None):
    """board -> board['sharp'] = {games: {gid: {...}}, alerts: [...], accounts: {...}}, and the day's new alerts and
    each upcoming game's current ladder (the close, once it tips) saved in the day folders."""
    games = [g for g in board.get('games') or [] if g.get('tip')]
    if not games:
        return None
    W = wallets()
    gmap = {(g['day'], nick(g.get('home_name'))): str(g['id']) for g in games if g.get('home_name')}
    tips = {str(g['id']): g['tip'] for g in games}
    dirs = day_dirs(root, now, 3)
    pins, polls = pin_replay(dirs, gmap, tips)
    by_id = {str(g['id']): g for g in games}
    # tapes -> per game
    pmm, kmm = day.meta.get('polymarket') or {}, day.meta.get('kalshi') or {}
    pm_game = {}
    for k, m in pmm.items():
        if m.get('type') not in ('moneyline', 'spreads', 'totals'):
            continue
        p = (m.get('event') or '').split('-')
        if len(p) < 6:
            continue
        gid = next((str(g['id']) for g in games if g['day'] == '-'.join(p[3:6]) and g['home'] == team.get(p[2].upper(), p[2].upper())), None)
        if not gid:
            continue
        try:
            outs = json.loads(m.get('outcomes') or '[]')
        except ValueError:
            continue
        g = by_id[gid]
        mk = {'moneyline': 'ml', 'spreads': 'sp', 'totals': 'tot'}[m['type']]

        def side_of(oi, outs=outs, mk=mk, g=g):
            o = outs[oi] if 0 <= oi < len(outs) else None
            if mk == 'tot':
                return 'over' if str(o).lower() == 'over' else 'under'
            return 'home' if nick(o) == nick(g.get('home_name')) else 'away'
        line = m.get('line')
        pm_game[k] = (gid, mk, side_of, float(line) if line is not None else None)
    kal_game = {}
    for k, m in kmm.items():
        if m.get('series') != 'KXNBAGAME':
            continue
        code = k.rsplit('-', 1)[-1]
        tcode = team.get(code, code)
        for d, a, h in parse_event(m['event']) or []:
            g = next((x for x in games if x['day'] == d and x['home'] == team.get(h, h)), None)
            if g:
                kal_game[k] = (str(g['id']), 'home' if tcode == g['home'] else 'away')
    tape, nov_seen = defaultdict(list), set()
    for r in _tape_rows(day_dirs(root, now, 1)):
        if r['s'] == 'pm' and r['k'] in pm_game:
            gid, mk, side_of, line = pm_game[r['k']]
            if r['t'] < tips[gid]:
                cls = 'sharp' if r.get('w') in W['sharp'] else 'dull' if r.get('w') in W['dull'] else None
                tape[gid].append({'t': r['t'], 'v': 'Polymarket', 'm': mk, 'side': side_of(r['o']), 'usd': r['usd'], 'px': r['px'],
                                  'line': line, 'cls': cls, 'who': r.get('who'), 'w': r.get('w'), 'id': r['id']})
        elif r['s'] == 'nov' and r['g'] in tips and r['id'] not in nov_seen:
            nov_seen.add(r['id'])
            if r['t'] < tips[r['g']]:
                tape[r['g']].append({'t': r['t'], 'v': 'Novig', 'm': r['m'], 'side': r['side'], 'usd': r['usd'], 'px': r['px'],
                                     'line': r.get('line'), 'cls': None, 'id': r['id']})
        elif r['s'] == 'kal' and r['k'] in kal_game:
            gid, side = kal_game[r['k']]
            if r['t'] < tips[gid]:
                tape[gid].append({'t': r['t'], 'v': 'Kalshi', 'm': 'ml', 'side': side if r['y'] else ('away' if side == 'home' else 'home'),
                                  'usd': r['usd'], 'px': r['px'], 'line': None, 'cls': None, 'id': r['id']})
    out, alerts = {}, []
    for gid, g in by_id.items():
        P = pins.get(gid) or {'series': [], 'ladder': None}
        S, lad = P['series'], P['ladder']
        cur = S[-1] if S else None
        base = {'g': gid}
        # steam
        for e in steam_events(S, polls):
            e.update(base, id=f"{gid}:steam:{e['m']}:{e['side']}:{e['t']}")
            alerts.append(e)
        # behind Pinnacle: soft books at the same number, and the exchanges' asks on the winner
        behind = []
        if lad:
            for r in (g.get('mk') or {}).get('books') or []:
                book = r[0]
                if book not in SOFT:
                    continue
                cands = [('ml', 'home', None, r[4]), ('ml', 'away', None, r[5])]
                if r[1] is not None:
                    cands += [('sp', 'home', r[1], r[2]), ('sp', 'away', r[1], r[3])]
                if r[6] is not None:
                    cands += [('tot', 'over', r[6], r[7]), ('tot', 'under', r[6], r[8])]
                for m, side, line, price in cands:
                    a = am(price)
                    if a is None or not -300 <= a <= 300:
                        continue
                    f = fair(lad, m, side, line)
                    if f is None:
                        continue
                    ev = f * (1 + payout(a)) - 1
                    if BEHIND_MIN <= ev < BEHIND_MAX:
                        behind.append({'venue': book, 'm': m, 'side': side, 'line': line, 'price': int(a), 'fair': r3(f), 'ev': r3(ev)})
            fh = fair(lad, 'ml', 'home')
            for k, (kg, side) in kal_game.items():
                v = (day.last.get('kalshi') or {}).get(k)
                if kg != gid or not v or v[1] is None or fh is None or not 0 < v[1] < 1:
                    continue
                f = fh if side == 'home' else 1 - fh
                c = v[1] + kal_fee(v[1])
                if 1 / (1 + 300 / 100) <= c <= 0.75 and BEHIND_MIN <= f / c - 1 < BEHIND_MAX:
                    behind.append({'venue': 'Kalshi', 'm': 'ml', 'side': side, 'line': None, 'price': round(v[1], 3), 'fair': r3(f), 'ev': r3(f / c - 1)})
        behind.sort(key=lambda x: -x['ev'])
        for x in behind:
            if x['ev'] >= BEHIND_ALERT:
                alerts.append(dict(base, t=now, type='behind', **x, id=f"{gid}:behind:{x['venue']}:{x['m']}:{x['side']}:{x['line']}:{x['price']}"))
        # flow
        T = sorted(tape.get(gid, []), key=lambda x: x['t'])
        day_ago = now - 86400
        net = lambda xs: sum(x['usd'] if x['side'] == 'home' else -x['usd'] for x in xs)
        mlpm = [x for x in T if x['v'] == 'Polymarket' and x['m'] == 'ml' and x['t'] > day_ago]
        flow = {'sharp': net([x for x in mlpm if x['cls'] == 'sharp']), 'sharpN': sum(x['cls'] == 'sharp' for x in mlpm),
                'dull': net([x for x in mlpm if x['cls'] == 'dull']), 'all': net(mlpm), 'vol': sum(x['usd'] for x in mlpm),
                'kal': net([x for x in T if x['v'] == 'Kalshi' and x['t'] > day_ago]), 'kalVol': sum(x['usd'] for x in T if x['v'] == 'Kalshi' and x['t'] > day_ago),
                'nov': net([x for x in T if x['v'] == 'Novig' and x['m'] == 'ml' and x['t'] > day_ago]), 'novVol': sum(x['usd'] for x in T if x['v'] == 'Novig' and x['t'] > day_ago)}
        # sharp: sharp accounts' trades on one side within a 30-minute bucket
        groups = defaultdict(list)
        for x in T:
            if x['cls'] == 'sharp':
                groups[(x['m'], x['side'], x['t'] // 1800)].append(x)
        for (m, side, b), xs in groups.items():
            usd = sum(x['usd'] for x in xs)
            if usd < SHARP_MIN:
                continue
            t = max(x['t'] for x in xs)
            top = max(xs, key=lambda x: x['usd'])
            sn = snap_at(S, t)
            line = top['line']
            hl = (line if side == 'home' else -line) if m == 'sp' and line is not None else line
            f = fair_snap(sn, m, side, hl, lad if t >= (cur[0] if cur else 0) else None)
            alerts.append(dict(base, t=t, type='sharp', m=m, side=side, line=hl, usd=usd, n=len(xs), accts=len({x['w'] for x in xs}),
                               px=top['px'], who=top['who'], rec=W['rec'].get(top['w']), fair=r3(f), id=f"{gid}:sharp:{m}:{side}:{b}"))
        # novig: real money on one side of one Novig market within a 30-minute bucket (anonymous, so no account class)
        ng = defaultdict(list)
        for x in T:
            if x['v'] == 'Novig':
                ng[(x['m'], x['side'], x['line'], x['t'] // 1800)].append(x)
        for (m, side, line, b), xs in ng.items():
            usd = sum(x['usd'] for x in xs)
            if usd < NOV_MIN:
                continue
            t = max(x['t'] for x in xs)
            top = max(xs, key=lambda x: x['usd'])
            sn = snap_at(S, t)
            hl = (line if side == 'home' else -line) if m == 'sp' and line is not None else line
            f = fair_snap(sn, m, side, hl, lad if t >= (cur[0] if cur else 0) else None)
            alerts.append(dict(base, t=t, type='novig', m=m, side=side, line=hl, usd=usd, n=len(xs), px=top['px'], venue='Novig',
                               fair=r3(f), id=f"{gid}:novig:{m}:{side}:{line}:{b}"))
        # cross: sharp 24h net on the winner reached CROSS_AT (one per side)
        if abs(flow['sharp']) >= CROSS_AT:
            side = 'home' if flow['sharp'] > 0 else 'away'
            alerts.append(dict(base, t=now, type='cross', m='ml', side=side, line=None, usd=abs(flow['sharp']), n=flow['sharpN'],
                               crowd=flow['all'] - flow['sharp'], fair=r3(fair(lad, 'ml', side)), id=f"{gid}:cross:{side}"))
        # whale
        for x in T:
            if x['usd'] >= WHALE and x['v'] != 'Novig':
                sn = snap_at(S, x['t'])
                hl = (x['line'] if x['side'] == 'home' else -x['line']) if x['m'] == 'sp' and x['line'] is not None else x['line']
                alerts.append(dict(base, t=x['t'], type='whale', m=x['m'], side=x['side'], line=hl, usd=x['usd'], px=x['px'], venue=x['v'],
                                   cls=x['cls'], who=x.get('who'), fair=r3(fair_snap(sn, x['m'], x['side'], hl, None)), id=f"{gid}:whale:{x['id']}"))
        # split
        mk = g.get('mk') or {}
        for m_, key in (('sp', 'spread'), ('ml', 'moneyline'), ('tot', 'total')):
            v = (mk.get('splits') or {}).get(key)
            if not v or v[0] is None or v[1] is None:
                continue
            for side, b, mo in (('home' if m_ != 'tot' else 'over', v[0], v[1]), ('away' if m_ != 'tot' else 'under', 100 - v[0], 100 - v[1])):
                if mo - b >= SPLIT_GAP and b <= SPLIT_MAX_T:
                    line = cur[1] if m_ == 'sp' and cur else cur[3] if m_ == 'tot' and cur else None
                    moved = None
                    if len(S) > 1 and level(S[0], m_) is not None and level(cur, m_) is not None:
                        d = level(cur, m_) - level(S[0], m_)
                        moved = round(d if side in ('home', 'over') else -d, 3)
                    alerts.append(dict(base, t=now, type='split', m=m_, side=side, line=line, bets=b, money=mo, moved=moved,
                                       fair=r3(fair(lad, m_, side, line)), id=f"{gid}:split:{m_}:{side}"))
        tickets = [[x['t'], x['v'], x['m'], x['side'], x['usd'], x['px'], x['cls'], x.get('who'), x['line']]
                   for x in T if x['usd'] >= 5000 or (x['cls'] == 'sharp' and x['usd'] >= SHARP_MIN)][-12:]
        out[gid] = {'pin': thin(S, 60), 'lad': lad_json(lad), 'behind': behind[:8], 'flow': flow, 'tickets': tickets}
    # per-prop signals (Player Props): Pinnacle prop moves, sharp accounts on Polymarket props, heavy Kalshi rung flow
    pin_props, pkeys = {}, board.get('_pkeys') or {}
    if pkeys:
        pin_props = pin_prop_series(dirs, pkeys.get('pinnacle') or {}, tips)
        alerts += prop_signals(by_id, pkeys, pin_props, polls, _tape_rows(day_dirs(root, now, 1)), W, day, now, kal_vol or {})
    # first sighting wins: an alert keeps the time and fair price of the poll that first saw it
    saved = load_signals(dirs)
    for a in alerts:
        g = by_id[a['g']]
        a.update(tip=g['tip'], tday=et_day(g['tip']), home=g['home'], away=g['away'], hn=nick(g.get('home_name')))
    fresh = [a for a in alerts if a['id'] not in saved]
    save_signals(day.dir, fresh)
    save_close(root, by_id, pins, now, pin_props)
    every = {**saved, **{a['id']: a for a in fresh}}
    shown = sorted((a for a in every.values() if a['g'] in by_id and not a['type'].startswith('p_')), key=lambda a: -a['t'])[:300]
    per_prop = defaultdict(list)
    for a in sorted((a for a in every.values() if a['g'] in by_id and a['type'].startswith('p_')), key=lambda a: a['t']):
        per_prop[f"{a['pid']}|{a['stat']}"].append({k: v for k, v in a.items() if k not in ('g', 'tip', 'tday', 'home', 'away', 'hn', 'pid', 'stat')})
    return {'games': out, 'alerts': shown, 'props': dict(per_prop),
            'accounts': {'sharp': len(W['sharp']), 'nba_sharp': sum(1 for s in W['sharp'].values() if s == 'nba'), 'dull': len(W['dull']),
                         'scored': W['n'], 'generated': W['generated']}}


def fair_snap(sn, m, side, line, lad=None):
    """Fair at a past moment from the main-line series (exact when the number is Pinnacle's main line then)."""
    if lad is not None:
        f = fair(lad, m, side, line)
        if f is not None:
            return f
    if not sn:
        return None
    if m == 'ml':
        return None if sn[5] is None else (sn[5] if side == 'home' else 1 - sn[5])
    if m == 'sp' and line is not None and sn[1] is not None and abs(sn[1] - line) < 1e-9 and sn[2] is not None:
        return sn[2] if side == 'home' else 1 - sn[2]
    if m == 'tot' and line is not None and sn[3] is not None and abs(sn[3] - line) < 1e-9 and sn[4] is not None:
        return sn[4] if side == 'over' else 1 - sn[4]
    return None


def thin(S, n):
    if len(S) <= n:
        return S
    step = len(S) / (n - 1)
    return [S[int(i * step)] for i in range(n - 1)] + [S[-1]]


def lad_json(lad):
    if not lad:
        return None
    return {'sp': {str(k): v for k, v in sorted(lad['sp'].items())}, 'tot': {str(k): v for k, v in sorted(lad['tot'].items())}, 'ml': lad['ml']}


def load_signals(dirs):
    out = {}
    for d in dirs:
        p = os.path.join(d, 'signals.json')
        if os.path.exists(p):
            try:
                out.update(json.load(open(p)))
            except ValueError:
                pass
    return out


def save_signals(day_dir, fresh):
    if not fresh:
        return
    p = os.path.join(day_dir, 'signals.json')
    cur = json.load(open(p)) if os.path.exists(p) else {}
    cur.update({a['id']: a for a in fresh})
    json.dump(cur, open(p, 'w'), separators=(',', ':'))


def save_close(root, by_id, pins, now, pin_props=None):
    """Each upcoming game's ladder (and each player prop's main line), rewritten every poll until tip: the last write
    is Pinnacle's close."""
    per = defaultdict(dict)
    props = defaultdict(dict)
    for (pid, stat, gid), S in (pin_props or {}).items():
        if S and S[-1][2] is not None:
            props[gid][f'{pid}|{stat}'] = [S[-1][1], S[-1][2]]
    for gid, g in by_id.items():
        P = pins.get(gid)
        if now < g['tip'] and ((P and P['ladder'] and P['series']) or props.get(gid)):
            per[et_day(g['tip'])][gid] = {'t': P['series'][-1][0] if P and P['series'] else now, 'tip': g['tip'],
                                          'lad': lad_json(P['ladder']) if P and P['ladder'] else None, 'props': props.get(gid) or {}}
    for d, games in per.items():
        p = os.path.join(root, 'snapshots', d, 'pinclose.json')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        cur = json.load(open(p)) if os.path.exists(p) else {}
        cur.update(games)
        json.dump(cur, open(p, 'w'), separators=(',', ':'))


# ── per-prop signals ─────────────────────────────────────────────────────────────────────────────
def pin_prop_series(dirs, pin_keys, tips):
    """Pinnacle player props from the day files: {(pid, stat, gid): [[t, line, no-vig P(over), limit]]}. A prop is one
    Pinnacle special (matchup id) with Over / Under sides; the line moves within the same keys."""
    mids = {k.split('|')[0]: (v[0], v[1], v[3]) for k, v in pin_keys.items()}
    out, polls = {}, []
    state = defaultdict(dict)
    for d in dirs:
        lp = os.path.join(d, 'pinnacle.jsonl')
        if not os.path.exists(lp):
            continue
        rows = []
        for line in open(lp):
            r = json.loads(line)
            mid = r['k'].split('|')[0]
            if mid in mids:
                rows.append(r)
        rows.sort(key=lambda r: r['t'])
        first, i = True, 0
        while i < len(rows):                            # apply a whole poll before pricing: Over and Under move together
            t, touched = rows[i]['t'], set()
            if first:
                state.clear()
                first = False
            while i < len(rows) and rows[i]['t'] == t:
                r = rows[i]
                i += 1
                pid, stat, gid = mids[r['k'].split('|')[0]]
                side = r['k'].rsplit('|', 1)[-1]
                if t >= tips.get(gid, 1e12) or side not in ('Over', 'Under'):
                    continue
                st = state[(pid, stat, gid)]
                if r['v'] is None:
                    st.pop(side, None)
                else:
                    st[side] = r['v']
                touched.add((pid, stat, gid))
            for key in touched:
                st = state[key]
                if 'Over' in st and 'Under' in st and st['Over'][0] is not None:
                    row = [t, st['Over'][0], r3(devig(st['Over'][1], st['Under'][1])), st['Over'][2] if len(st['Over']) > 2 else None]
                    S = out.setdefault(key, [])
                    if not S or S[-1][1:3] != row[1:3]:
                        S.append(row)
    return out


def prop_signals(by_id, pkeys, pin_props, polls, tape, W, day, now, kal_vol):
    """-> alert dicts (type p_pin / p_acct / p_kal) for every prop on the board."""
    out = []
    # Pinnacle prop moves: a full point, or 5 points of no-vig chance at the same line, within an hour (timed moves only)
    for (pid, stat, gid), S in pin_props.items():
        last = {}
        for i, cur in enumerate(S):
            t = cur[0]
            if not any(t - GAP_MAX <= q < t for q in polls):
                continue
            ref = next((x for x in reversed(S[:i]) if x[0] <= t - P_WIN), S[0])
            if ref is cur or ref[2] is None or cur[2] is None:
                continue
            dl, dp = cur[1] - ref[1], cur[2] - ref[2]
            if abs(dl) >= P_LINE:
                side = 'over' if dl > 0 else 'under'
            elif dl == 0 and abs(dp) >= P_PROB:
                side = 'over' if dp > 0 else 'under'
            else:
                continue
            if last.get(side, -1e12) > t - STEAM_COOL:
                continue
            last[side] = t
            out.append({'g': gid, 'pid': pid, 'stat': stat, 'type': 'p_pin', 't': t, 'side': side, 'line': cur[1],
                        'from': [ref[1], ref[2]], 'to': [cur[1], cur[2]], 'lim': cur[3],
                        'fair': r3(cur[2] if side == 'over' else 1 - cur[2]), 'id': f"{gid}:p_pin:{pid}:{stat}:{side}:{t}"})
    def pin_at(key, t, line):                          # Pinnacle's fair at that moment, only if it was dealing that line then
        x = next((x for x in reversed(pin_props.get(key) or []) if x[0] <= t), None)
        return x[2] if x and x[1] == line else None
    # sharp accounts on Polymarket props, per 30-minute bucket
    W_ = W or {'sharp': {}, 'dull': set(), 'rec': {}}
    pm = pkeys.get('polymarket') or {}
    groups = defaultdict(list)
    for r in tape:
        if r.get('s') != 'pm' or r['k'] not in pm or r.get('w') not in W_['sharp']:
            continue
        pid, stat, line, gid = pm[r['k']]
        if gid not in by_id or r['t'] >= by_id[gid]['tip']:
            continue
        groups[(pid, stat, gid, line, 'over' if r['o'] == 0 else 'under', r['t'] // 1800)].append(r)
    for (pid, stat, gid, line, side, b), xs in groups.items():
        usd = sum(x['usd'] for x in xs)
        if usd < P_SHARP:
            continue
        top = max(xs, key=lambda x: x['usd'])
        t = max(x['t'] for x in xs)
        f = pin_at((pid, stat, gid), t, line)
        out.append({'g': gid, 'pid': pid, 'stat': stat, 'type': 'p_acct', 't': t, 'side': side, 'line': line, 'usd': usd, 'n': len(xs),
                    'accts': len({x['w'] for x in xs}), 'px': top['px'], 'who': top.get('who'), 'rec': W_['rec'].get(top['w']),
                    'fair': r3(f if side == 'over' else 1 - f) if f is not None else None, 'id': f"{gid}:p_acct:{pid}:{stat}:{line}:{side}:{b}"})
    # heavy Kalshi flow: contracts traded on one rung between two polls, with the price moving
    path = os.path.join(day.dir, 'kalvol.json')
    try:
        prev = json.load(open(path))
    except (OSError, ValueError):
        prev = {}
    kal, nxt = pkeys.get('kalshi') or {}, {}
    for k, (pid, stat, line, gid) in kal.items():
        v, q = kal_vol.get(k), (day.last.get('kalshi') or {}).get(k)
        if v is None or not q or q[0] is None or q[1] is None or gid not in by_id:
            continue
        mid = (q[0] + q[1]) / 2
        nxt[k] = [now, v, round(mid, 4)]
        pv = prev.get(k)
        if not pv or now - pv[0] > GAP_MAX or now >= by_id[gid]['tip']:
            continue
        dv, dm = v - pv[1], mid - pv[2]
        usd = dv * (mid + pv[2]) / 2
        if usd >= P_KAL_USD and abs(dm) >= P_KAL_MOVE:
            side = 'over' if dm > 0 else 'under'
            f = pin_at((pid, stat, gid), now, line)
            out.append({'g': gid, 'pid': pid, 'stat': stat, 'type': 'p_kal', 't': now, 'side': side, 'line': line, 'usd': round(usd),
                        'from': round(pv[2], 3), 'to': round(mid, 3), 'fair': r3(f if side == 'over' else 1 - f) if f is not None else None,
                        'id': f"{gid}:p_kal:{k}:{now}"})
    try:
        json.dump(nxt, open(path, 'w'), separators=(',', ':'))
    except OSError:
        pass
    return out


# ── grading (ledger.settle) ──────────────────────────────────────────────────────────────────────
def _lad(j):
    if not j:
        return None
    return {'sp': {float(k): v for k, v in (j.get('sp') or {}).items()}, 'tot': {float(k): v for k, v in (j.get('tot') or {}).items()}, 'ml': j.get('ml')}


def grade_prop(a, close_props, actual):
    """A player-prop signal: CLV against Pinnacle's closing no-vig chance when it closed at the same line; result from
    the box score (did the stat finish on the signal's side of its line)."""
    c = (close_props or {}).get(f"{a['pid']}|{a['stat']}")
    if c and a.get('close') is None and c[0] == a.get('line') and c[1] is not None:
        a['close'] = r3(c[1] if a['side'] == 'over' else 1 - c[1])
        if a.get('fair') is not None:
            a['clv'] = r3(a['close'] - a['fair'])
    if actual is not None and a.get('result') is None and a.get('line') is not None:
        d = (actual - a['line']) * (1 if a['side'] == 'over' else -1)
        a['result'] = 1 if d > 0 else -1 if d < 0 else 0


def pm_close_for(a):
    """Polymarket's chance for an alert's side at its number at tip (data/pm_closes.json, scripts/pm_archive.py from the
    Pendulum Flow orderbook archive, about 6 hours after tip). Matched by tip time and the home nickname."""
    global _PMC
    if _PMC is None:
        try:
            _PMC = [g for g in json.load(open(os.path.join(REPO_DATA, 'pm_closes.json'))).get('games', {}).values() if g.get('sport') == 'nba' and g.get('ml')]
        except (OSError, ValueError):
            _PMC = []
    hn = (a.get('hn') or '').lower()
    g = next((g for g in _PMC if abs(g['kickoff'] - a['tip']) < 3 * 3600 and hn in [o.lower() for o in g['ml']['outcomes']]), None)
    if not g:
        return None
    hi = [o.lower() for o in g['ml']['outcomes']].index(hn)
    def interp(pts, x):
        pts = sorted(pts)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return next((y for xx, y in pts if xx == x), None)
    if a['m'] == 'ml':
        ph = g['ml']['p'] if hi == 0 else 1 - g['ml']['p']
        return ph if a['side'] == 'home' else 1 - ph
    if a.get('line') is None:
        return None
    if a['m'] == 'sp':                               # alert line is the side's own handicap
        home_line = a['line'] if a['side'] == 'home' else -a['line']
        pts = [(r['line'], r['p']) if r['outcomes'][0].lower() == hn else (-r['line'], 1 - r['p']) for r in g.get('spreads', []) if r.get('line') is not None]
        c = interp(pts, home_line)
        return None if c is None else c if a['side'] == 'home' else 1 - c
    if a['m'] == 'tot':
        pts = [(r['line'], r['p'] if r['outcomes'][0] == 'Over' else 1 - r['p']) for r in g.get('totals', []) if r.get('line') is not None]
        o = interp(pts, a['line'])
        return None if o is None else o if a['side'] == 'over' else 1 - o
    return None


_PMC = None


def grade_alert(a, close, score):
    """In place: a['close'] (Pinnacle's closing fair at the alert's number), a['clv'], a['result'] (1 / -1 / 0)."""
    if close is not None and a.get('close') is None:
        f = fair(close, a['m'], a['side'], a.get('line'))
        if f is not None:
            a['close'] = r3(f)
            if a['type'] == 'behind':
                a['clv'] = r3(f * (1 + payout(a['price'])) - 1 if a['venue'] != 'Kalshi' else f / (a['price'] + kal_fee(a['price'])) - 1)
            elif a.get('fair') is not None:
                a['clv'] = r3(f - a['fair'])
    if a.get('pm_close') is None:                     # Polymarket's close lands about 6 hours after tip
        f = pm_close_for(a)
        if f is not None:
            a['pm_close'] = r3(f)
            if a['type'] == 'behind':
                a['pm_clv'] = r3(f * (1 + payout(a['price'])) - 1 if a['venue'] != 'Kalshi' else f / (a['price'] + kal_fee(a['price'])) - 1)
            elif a.get('fair') is not None:
                a['pm_clv'] = r3(f - a['fair'])
    if score and a.get('result') is None:
        h, w = score.get(a['home']), score.get(a['away'])
        if h is None or w is None:
            return
        if a['m'] == 'ml':
            d = (h - w) if a['side'] == 'home' else (w - h)
        elif a['m'] == 'sp' and a.get('line') is not None:
            d = (h + a['line'] - w) * (1 if a['side'] == 'home' else -1)
        elif a['m'] == 'tot' and a.get('line') is not None:
            d = (h + w - a['line']) * (1 if a['side'] == 'over' else -1)
        else:
            return
        a['result'] = 1 if d > 0 else -1 if d < 0 else 0


def grade_signals(root, now, prev, box, box_meta, rescan_days=4, keep=400, stat_of=None, games=None):
    """track.json 'signals': {'days': {tip day: {type: [n, graded, clv_sum, clv_sq, clv_pos, w, l, p, exp_sum]}},
    'recent': graded alerts, newest first}. Days outside the rescan window keep their totals. `games(gid)` -> False
    leaves a game's alerts out (ledger.py grades preseason apart from the season)."""
    prev = prev or {}
    days, recent = dict(prev.get('days') or {}), {a['id']: a for a in prev.get('recent') or []}
    since = (dt.datetime.fromtimestamp(now, ET).date() - dt.timedelta(days=rescan_days)).isoformat()
    alerts = {}
    for d in sorted(glob.glob(os.path.join(root, 'snapshots', '20*'))):
        if os.path.basename(d) >= since and os.path.exists(os.path.join(d, 'signals.json')):
            try:
                alerts.update(json.load(open(os.path.join(d, 'signals.json'))))
            except ValueError:
                pass
    if games:
        alerts = {k: a for k, a in alerts.items() if games(str(a['g']))}
    closes = {}
    for a in alerts.values():
        if now < a['tip'] + GRADE_AFTER_S:
            continue
        if a['tday'] not in closes:
            p = os.path.join(root, 'snapshots', a['tday'], 'pinclose.json')
            closes[a['tday']] = json.load(open(p)) if os.path.exists(p) else {}
        c = closes[a['tday']].get(a['g'])
        bx = box(root, a['g'])
        if bx is None:
            continue
        if a['type'].startswith('p_'):
            grade_prop(a, (c or {}).get('props'), stat_of(bx, a['pid'], a['stat']) if stat_of else None)
        else:
            grade_alert(a, _lad(c['lad']) if c and c.get('lad') else None, (box_meta(root, a['g']) or {}).get('score'))
        recent[a['id']] = a
    touched = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0, 0.0, 0, 0, 0, 0, 0.0, 0, 0.0, 0.0, 0]))
    for a in alerts.values():
        if a['tday'] < since:
            continue
        r = touched[a['tday']][a['type']]
        r[0] += 1
        if a.get('clv') is not None:
            r[1] += 1
            r[2] += a['clv']
            r[3] += a['clv'] ** 2
            r[4] += a['clv'] > 0
        if a.get('result') is not None:
            r[5 + {1: 0, -1: 1, 0: 2}[a['result']]] += 1
            r[8] += a.get('fair') or 0
        if a.get('pm_clv') is not None:              # [9..12]: the same CLV against Polymarket's close
            r[9] += 1
            r[10] += a['pm_clv']
            r[11] += a['pm_clv'] ** 2
            r[12] += a['pm_clv'] > 0
    for d, by in touched.items():
        days[d] = {t: [round(x, 4) if isinstance(x, float) else x for x in v] for t, v in by.items()}
    rec = sorted((a for a in recent.values() if a.get('clv') is not None or a.get('result') is not None), key=lambda a: -a['t'])[:keep]
    return {'days': days, 'recent': rec}
