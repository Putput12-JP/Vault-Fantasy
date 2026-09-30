#!/usr/bin/env python3
"""
Live price + injury recorder. The data advantage in docs/differentiation.md §4: an honest,
timestamped record of every venue's pre-tip price, which no free archive has.

One poll reads every free source, drops anything whose game has tipped (pre-game only), and
appends ONLY what changed since the last poll:

  kalshi      every open NBA player-prop and game market: yes bid / ask
              (the trade tape is downloadable later, the order book is not, so we keep the book)
  espn        ESPN core odds per upcoming game (DraftKings etc.): game line + every player prop
  pinnacle    guest API: main lines, team totals, player props, with bet limits
  action      Action Network scoreboard: 7 books + bets % / money % splits
  polymarket  NBA game events: best bid / ask / last per market
  injuries    official NBA injury report, parsed; one row per player status change

Layout (under --dir, the nba-data branch; one folder per ET game day, self-contained):
  snapshots/YYYY-MM-DD/<source>.jsonl  {"t": epoch, "k": key, "v": [...]}   v null = market gone
  snapshots/YYYY-MM-DD/meta.jsonl      {"k", "src", ...}  what a key is, written the first time it is seen that day
  snapshots/YYYY-MM-DD/polls.jsonl     {"t", "src", "ok", "n", "chg", "s", "err"}  every poll, so "price at time X"
                                       = last change before X, trusted only if polls around X succeeded
The price at any time is the last row for that key at or before it. A day file restarts with a full
snapshot, so no state lives outside the day folder.

  python3 nba/scripts/snapshot.py --dir nba-data                   # one poll
  python3 nba/scripts/snapshot.py --dir nba-data --loop --commit   # poll through today's game window
                                   [--max-minutes 330]             # then print handoff (GitHub 6h job cap)
Game window: 9am ET until the last tip of the day. Every 5 min inside 3h of a tip, else every 15.
Injury parsing needs pdfplumber (pip install pdfplumber); without it that source is skipped.
"""
import datetime as dt, json, os, subprocess, sys, time, traceback
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from backfill_espn_odds import game_lines, props as espn_props, CORE
from backfill_kalshi import PROP_SERIES, GAME_SERIES, TEAM as KTEAM, parse_event

ET = ZoneInfo('America/New_York')
KAL = 'https://api.elections.kalshi.com/trade-api/v2'
PIN = 'https://guest.api.arcadia.pinnacle.com/0.1'
PIN_HDR = ['X-API-Key: CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R', 'Referer: https://www.pinnacle.com/']  # Pinnacle's public web-client key
SCORE = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'
AN_BOOKS = '15,30,68,69,75,71,79'   # consensus, open, DK, FD, MGM, BetRivers, bet365
PM_SERIES = 10345
PM_GAME_TYPES = {'moneyline', 'spreads', 'totals', 'basketball_team_to_score_first', 'basketball_odd_even'}
TEAM = {**KTEAM, 'GSW': 'GS', 'NYK': 'NY', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH', 'PHO': 'PHX', 'BRK': 'BKN'}
INJ = 'https://ak-static.cms.nba.com/referee/injury/Injury-Report_'
ESPN_SKIP = {59}                    # ESPN Bet Live Odds: in-game prices
AHEAD_H = 72                        # record games tipping within 3 days (skips futures like season wins)
FAST_S, SLOW_S, FAST_WITHIN_H, WINDOW_START_ET = 300, 900, 3, 9


def curl(url, headers=(), tries=2, raw=False):
    """ESPN 403s urllib, so everything goes through curl. Raises after `tries` failures."""
    # No custom user agent by default: ESPN 403s anything Mozilla-like that is not a real browser.
    cmd = ['curl', '-s', '--compressed', '--max-time', '30', '-w', '\n%{http_code}']
    for h in headers:
        cmd += ['-H', h]
    err = ''
    for i in range(tries):
        p = subprocess.run(cmd + [url], capture_output=True)
        body, _, code = p.stdout.rpartition(b'\n')
        code = code.decode()
        if code == '200':
            return body if raw else json.loads(body)
        err = f'HTTP {code or "timeout"}'
        if code in ('403', '404'):
            break
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f'{err} {url[:100]}')


def iso(s):
    return int(dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()) if s else None


def num(x):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return None


def nick(name):
    """'Portland Trail Blazers' / 'LA Clippers' / 'Los Angeles Clippers' -> 'blazers' / 'clippers'. Unique per team."""
    return (name or '').split()[-1].lower() if name else None


# ── what is on today: ESPN scoreboard ────────────────────────────────────────────────────────
class Slate:
    """Games from yesterday..tomorrow (ET). `pre` = has not tipped; `started` = keys to exclude."""

    def __init__(self, now):
        self.now = now
        self.ahead = now + AHEAD_H * 3600
        self.games, self.started, self.nick = [], set(), {}
        today = dt.datetime.fromtimestamp(now, ET).date()
        for off in range(-1, AHEAD_H // 24 + 1):   # yesterday (late tips) through the look-ahead
            day = today + dt.timedelta(days=off)
            d = curl(f'{SCORE}?dates={day:%Y%m%d}')
            for e in d.get('events', []):
                comp = e['competitions'][0]
                side = {c['homeAway']: c['team']['abbreviation'] for c in comp['competitors']}
                for c in comp['competitors']:          # abbreviation -> nickname, the join key across venues
                    self.nick[c['team']['abbreviation']] = nick(c['team'].get('displayName'))
                tip = iso(e['date'])
                pre = e['status']['type']['state'] == 'pre' and now < tip <= self.ahead
                g = {'id': e['id'], 'day': day.isoformat(), 'tip': tip, 'away': side.get('away'), 'home': side.get('home'),
                     'pre': pre, 'season_type': e['season']['type']}
                self.games.append(g)
                if not pre:
                    self.started.add((g['day'], g['away'], g['home']))

    def kalshi_started(self, event_ticker):
        return any(k in self.started for k in parse_event(event_ticker) or [])

    def next_tip(self):
        tips = [g['tip'] for g in self.games if g['pre']]
        return min(tips) if tips else None

    def window(self):
        """(in game window, seconds to next poll). Window = 9am ET .. last tip of the ET day."""
        et_now = dt.datetime.fromtimestamp(self.now, ET)
        today = et_now.date().isoformat()
        left = [g['tip'] for g in self.games if g['pre'] and g['day'] == today]
        if not left or et_now.hour < WINDOW_START_ET:
            return False, None
        nxt = self.next_tip()
        return True, FAST_S if nxt - self.now <= FAST_WITHIN_H * 3600 else SLOW_S


# ── sources: each returns ({key: value list}, {key: meta}) ───────────────────────────────────
def src_kalshi(slate):
    rows, meta = {}, {}
    for s in PROP_SERIES + GAME_SERIES:
        cur = ''
        while True:
            d = curl(f'{KAL}/markets?series_ticker={s}&status=open&limit=1000' + (f'&cursor={cur}' if cur else ''))
            for m in d.get('markets', []):
                if slate.kalshi_started(m['event_ticker']):
                    continue
                k = m['ticker']
                rows[k] = [num(m.get('yes_bid_dollars')), num(m.get('yes_ask_dollars'))]
                meta[k] = {'series': s, 'event': m['event_ticker'], 'title': m.get('title'), 'sub': m.get('yes_sub_title'),
                           'floor': m.get('floor_strike'), 'close': m.get('close_time')}
            cur = d.get('cursor')
            if not cur or not d.get('markets'):
                break
    return rows, meta


def src_espn(slate):
    rows, meta = {}, {}
    for g in slate.games:
        if not g['pre']:
            continue
        eid = g['id']
        d = curl(f'{CORE}/events/{eid}/competitions/{eid}/odds')
        for item in d.get('items', []):
            gl = game_lines(item)
            pid = gl['provider_id']
            if pid in ESPN_SKIP:
                continue
            h, a, t = gl['home']['current'], gl['away']['current'], gl['total']['current']
            k = f'{eid}|{pid}|game'
            rows[k] = [h['spread'], h['spread_px'], a['spread_px'], h['ml'], a['ml'], t['total'], t['over_px'], t['under_px']]
            meta[k] = {'game': eid, 'book': gl['provider'], 'away': g['away'], 'home': g['home'], 'tip': g['tip'],
                       'v': 'home_spread,home_px,away_px,home_ml,away_ml,total,over_px,under_px'}
            pb = (item.get('propBets') or {}).get('$ref')
            if pb:
                for r in espn_props(pb):
                    k = f"{eid}|{pid}|{r['athlete_id']}|{r['type_id']}|{r['ord']}"
                    rows[k] = [r['cur_line'], r['cur_px']]
                    meta[k] = {'game': eid, 'book': gl['provider'], 'athlete_id': r['athlete_id'], 'type': r['type'],
                               'ord': r['ord'], 'open_line': r['open_line'], 'open_px': r['open_px']}
    return rows, meta


def src_pinnacle(slate):
    matchups = {m['id']: m for m in curl(f'{PIN}/leagues/487/matchups', PIN_HDR)}
    rows, meta = {}, {}
    for mk in curl(f'{PIN}/leagues/487/markets/straight', PIN_HDR):
        m = matchups.get(mk['matchupId'])
        if not m or m.get('isLive') or (m.get('type') == 'special' and not m.get('parent')):
            continue                      # specials without a parent game are futures (playoffs, season wins)
        start = iso(m.get('startTime'))
        if not start or start <= slate.now or start > slate.ahead:
            continue
        limit = next((x['amount'] for x in mk.get('limits') or [] if x.get('type') == 'maxRiskStake'), None)
        names = {p.get('id'): p.get('name') for p in m.get('participants') or []}
        for p in mk.get('prices') or []:
            side = p.get('designation') or names.get(p.get('participantId')) or p.get('participantId')
            k = f"{mk['matchupId']}|{mk['key']}|{side}"
            rows[k] = [p.get('points'), p.get('price'), limit]
            meta[k] = {'matchup': mk['matchupId'], 'parent': (m.get('parent') or {}).get('id'), 'start': start,
                       'type': mk['type'], 'period': mk.get('period'), 'side': side,
                       'desc': (m.get('special') or {}).get('description'),
                       'teams': [(p.get('alignment'), p.get('name')) for p in (m.get('parent') or m).get('participants') or []]}
    return rows, meta


def src_action(slate):
    rows, meta = {}, {}
    days = sorted({g['day'] for g in slate.games if g['pre']})
    for day in days:
        d = curl(f"https://api.actionnetwork.com/web/v2/scoreboard/nba?bookIds={AN_BOOKS}&date={day.replace('-', '')}&periods=event",
                 ['User-Agent: Mozilla/5.0'])
        for g in d.get('games', []):
            start = iso(g.get('start_time'))
            if g.get('status') != 'scheduled' or not start or start <= slate.now:
                continue
            teams = {t['id']: t.get('abbr') for t in g.get('teams', [])}
            for book, per in (g.get('markets') or {}).items():
                for mtype, outs in ((per or {}).get('event') or {}).items():
                    for o in outs or []:
                        if o.get('is_live'):
                            continue
                        side = o.get('side')
                        if mtype == 'team_total' or (side in ('home', 'away') and o.get('team_id')):
                            side = f"{side}:{teams.get(o.get('team_id'), o.get('team_id'))}"
                        bi = o.get('bet_info') or {}
                        k = f"{g['id']}|{book}|{mtype}|{side}"
                        rows[k] = [o.get('value'), o.get('odds'), (bi.get('tickets') or {}).get('percent'),
                                   (bi.get('money') or {}).get('percent')]
                        meta[k] = {'game': g['id'], 'book': int(book), 'type': mtype, 'side': side, 'start': start,
                                   'away': teams.get(g.get('away_team_id')), 'home': teams.get(g.get('home_team_id')),
                                   'v': 'line,odds,bets_pct,money_pct'}
    return rows, meta


def src_polymarket(slate):
    rows, meta = {}, {}
    for e in curl(f'https://gamma-api.polymarket.com/events?series_id={PM_SERIES}&closed=false&limit=500'):
        for m in e.get('markets', []):
            start = iso(m.get('gameStartTime', '').replace(' ', 'T').replace('+00', '+00:00') if m.get('gameStartTime') else e.get('endDate'))
            if m.get('closed') or not start or start <= slate.now or start > slate.ahead:
                continue
            k = str(m['id'])
            rows[k] = [num(m.get('bestBid')), num(m.get('bestAsk')), num(m.get('lastTradePrice'))]
            meta[k] = {'event': e.get('slug'), 'q': m.get('question'), 'type': m.get('sportsMarketType'),
                       'line': m.get('line'), 'outcomes': m.get('outcomes'), 'start': start, 'cid': m.get('conditionId')}
    return rows, meta


class Injuries:
    """Latest official report. Filenames are the ET slot, every 15 min: Injury-Report_2026-10-20_05_30PM.pdf.
    A missing file is a 403 on this CDN, so walk back from now until one exists or we reach the one we have."""
    BACK_SLOTS = 8

    def __init__(self, day_dir):
        self.last = None
        path = os.path.join(day_dir, 'polls.jsonl')
        if os.path.exists(path):
            for line in open(path):
                r = json.loads(line)
                if r.get('src') == 'injuries' and r.get('report'):
                    self.last = r['report']

    def __call__(self, slate):
        try:
            from fetch_injury_reports import parse
        except ImportError:
            raise RuntimeError('pdfplumber not installed')
        if not any(g['pre'] and g['tip'] - slate.now < 36 * 3600 for g in slate.games):
            return None, {'report': 'no games'}      # no report is posted; don't knock on the CDN
        et_now = dt.datetime.fromtimestamp(slate.now, ET)
        slot = et_now.replace(minute=et_now.minute - et_now.minute % 15, second=0, microsecond=0)
        for i in range(self.BACK_SLOTS):
            s = slot - dt.timedelta(minutes=15 * i)
            name = f"{s:%Y-%m-%d}_{s.hour % 12 or 12:02d}_{s:%M%p}"
            if name == self.last:
                return None, {'report': name}          # nothing newer: keep previous rows as they are
            try:
                pdf = curl(INJ + name + '.pdf', raw=True, tries=1)
            except RuntimeError:
                time.sleep(1.0)                        # Akamai blocks bursts
                continue
            tmp = os.path.join(os.environ.get('RUNNER_TEMP', '/tmp'), 'nba_injury.pdf')
            open(tmp, 'wb').write(pdf)
            rows, meta = {}, {}
            for r in parse(tmp):
                k = f"{r['game_date']}|{r['team']}|{r['player']}"
                rows[k] = [r['status'], r['reason']]
                meta[k] = {'game_date': r['game_date'], 'tip_et': r['tip_et'], 'matchup': r['matchup'], 'team': r['team'],
                           'player': r['player']}
            self.last = name
            return (rows, meta), {'report': name}
        return None, {'report': None}


# ── day folder: diff against the last value per key ─────────────────────────────────────────
class Day:
    def __init__(self, root, day):
        self.dir = os.path.join(root, 'snapshots', day)
        os.makedirs(self.dir, exist_ok=True)
        self.last, self.known = {}, set()
        for f in os.listdir(self.dir):
            src = f[:-6]
            if f == 'meta.jsonl':
                self.known = {(r['src'], r['k']) for r in map(json.loads, open(os.path.join(self.dir, f)))}
            elif f.endswith('.jsonl') and f != 'polls.jsonl':
                last = self.last.setdefault(src, {})
                for line in open(os.path.join(self.dir, f)):
                    r = json.loads(line)
                    if r['v'] is None:
                        last.pop(r['k'], None)
                    else:
                        last[r['k']] = r['v']

    def append(self, name, recs):
        if recs:
            with open(os.path.join(self.dir, name), 'a') as f:
                for r in recs:
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')

    def record(self, src, t, rows, meta):
        last = self.last.setdefault(src, {})
        out = [{'t': t, 'k': k, 'v': v} for k, v in rows.items() if last.get(k) != v]
        out += [{'t': t, 'k': k, 'v': None} for k in last if k not in rows]
        self.append(src + '.jsonl', out)
        self.append('meta.jsonl', [{'k': k, 'src': src, **m} for k, m in meta.items() if (src, k) not in self.known])
        self.known |= {(src, k) for k in meta}
        self.last[src] = dict(rows)
        return len(out)


def poll(root):
    now = int(time.time())
    slate = Slate(now)
    day = Day(root, dt.datetime.fromtimestamp(now, ET).date().isoformat())
    sources = [('kalshi', src_kalshi), ('espn', src_espn), ('pinnacle', src_pinnacle), ('action', src_action),
               ('polymarket', src_polymarket), ('injuries', Injuries(day.dir))]
    polls, metas = [], {}
    for name, fn in sources:
        t0 = time.time()
        rec = {'t': int(t0), 'src': name, 'ok': True}
        try:
            got = fn(slate)
            if name == 'injuries':
                got, extra = got
                rec.update(extra)
            if got is not None:
                rows, meta = got
                rec['n'] = len(rows)
                rec['chg'] = day.record(name, int(t0), rows, meta)
                metas[name] = meta
        except Exception as e:  # one dead source must not stop the others
            rec.update(ok=False, err=str(e)[:200])
            traceback.print_exc(limit=1)
        rec['s'] = round(time.time() - t0, 1)
        polls.append(rec)
        print(f"  {name:10s} {'ok ' if rec['ok'] else 'ERR'} n={rec.get('n', '-')} chg={rec.get('chg', '-')} "
              f"{rec['s']}s {rec.get('err', '') or rec.get('report') or ''}", flush=True)
    day.append('polls.jsonl', polls)
    write_status(root, day, slate, polls, metas)
    games = ', '.join(f"{g['away']}@{g['home']}" for g in slate.games if g['pre'] and g['day'] == day.dir[-10:])
    print(f"{dt.datetime.fromtimestamp(now, ET):%Y-%m-%d %H:%M ET} polled. today pre-tip: {games or 'none'}", flush=True)
    return slate


# ── status.json: what the Data Health page reads ──────────────────────────────────────────────
def coverage(slate, day, metas):
    """Per upcoming game, markets per venue as [game markets, player props]. Venues name teams differently
    (ESPN abbreviations, Kalshi / Action / Polymarket codes, full names), so everything joins on the home team's
    nickname plus the ET date."""
    games = {}
    for g in slate.games:
        if g['pre']:
            g = {k: g[k] for k in ('id', 'day', 'tip', 'away', 'home', 'season_type')}
            g['cov'] = {}
            games[(g['day'], slate.nick.get(g['home']))] = g
    code_nick = lambda c: slate.nick.get(TEAM.get(c.upper(), c.upper()))
    et_day = lambda t: dt.datetime.fromtimestamp(t, ET).date().isoformat() if t else None

    def add(src, key, prop):
        g = games.get(key)
        if g:
            c = g['cov'].setdefault(src, [0, 0])
            c[1 if prop else 0] += 1

    by_id = {g['id']: k for k, g in games.items()}
    for k, m in (metas.get('kalshi') or {}).items():
        for d_, a, h in parse_event(m['event']) or []:
            if (d_, slate.nick.get(h)) in games:
                add('kalshi', (d_, slate.nick.get(h)), m['series'] in PROP_SERIES)
                break
    for k, m in (metas.get('espn') or {}).items():
        add('espn', by_id.get(m['game']), not k.endswith('|game'))
    for k, m in (metas.get('pinnacle') or {}).items():
        home = next((n for a, n in m.get('teams') or [] if a == 'home'), None)
        add('pinnacle', (et_day(m['start']), nick(home)), bool(m.get('parent')))
    for k, m in (metas.get('action') or {}).items():
        add('action', (et_day(m['start']), code_nick(m.get('home') or '')), False)
    for k, m in (metas.get('polymarket') or {}).items():
        p = (m.get('event') or '').split('-')          # nba-<away>-<home>-YYYY-MM-DD
        if len(p) >= 6:
            add('polymarket', ('-'.join(p[3:6]), code_nick(p[2])), (m.get('type') or 'moneyline') not in PM_GAME_TYPES)
    for k in day.last.get('injuries', {}):             # report rows persist between reports, so read current state
        gd, team, _ = k.split('|', 2)
        try:
            d_ = dt.datetime.strptime(gd, '%m/%d/%Y').date().isoformat()
        except ValueError:
            continue
        for key, g in games.items():
            if key[0] == d_ and nick(team) in (slate.nick.get(g['home']), slate.nick.get(g['away'])):
                g['cov'].setdefault('injuries', [0, 0])[0] += 1
    return sorted(games.values(), key=lambda g: g['tip'])


def write_status(root, day, slate, polls, metas):
    live, wait = slate.window()
    snap = os.path.join(root, 'snapshots')
    days = sorted(d for d in os.listdir(snap) if d[:2] == '20')
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(snap) for f in fs)
    run = os.environ.get('GITHUB_RUN_ID')
    status = {
        't': slate.now, 'window': {'live': live, 'next_s': wait},
        'run': f"{os.environ.get('GITHUB_SERVER_URL')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{run}" if run else None,
        'sources': {p['src']: p for p in polls},
        'games': coverage(slate, day, metas),
        'storage': {'days': len(days), 'first': days[0] if days else None, 'bytes': size},
    }
    with open(os.path.join(root, 'status.json'), 'w') as f:
        json.dump(status, f, separators=(',', ':'))


def commit(root):
    git = ['git', '-C', root]
    subprocess.run(git + ['add', '-A', 'snapshots', 'status.json'], check=True)
    if subprocess.run(git + ['diff', '--cached', '--quiet']).returncode == 0:
        return
    stamp = dt.datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')
    subprocess.run(git + ['commit', '-q', '-m', f'nba snapshots {stamp} [skip ci]'], check=True)
    for _ in range(4):
        if subprocess.run(git + ['push', '-q']).returncode == 0:
            return
        subprocess.run(git + ['pull', '-q', '--rebase'])
    print('push failed; will retry with the next poll', flush=True)


def main(argv):
    args = {a.split('=')[0].lstrip('-'): (a.split('=', 1)[1] if '=' in a else True) for a in argv}
    root = os.path.abspath(args.get('dir', os.path.join(os.path.dirname(__file__), '..', 'raw', 'snapshots_local')))
    global AHEAD_H
    AHEAD_H = int(args.get('ahead-h', AHEAD_H))
    stop_at = time.time() + float(args.get('max-minutes', 330)) * 60
    while True:
        slate = poll(root)
        if args.get('commit'):
            commit(root)
        if not args.get('loop'):
            return
        live, wait = slate.window()
        if not live:
            print('outside the game window, done', flush=True)
            return
        if time.time() + wait > stop_at:
            print('HANDOFF', flush=True)
            if os.environ.get('GITHUB_OUTPUT'):
                open(os.environ['GITHUB_OUTPUT'], 'a').write('handoff=true\n')
            return
        time.sleep(max(30, wait - (time.time() - slate.now)))


if __name__ == '__main__':
    main(sys.argv[1:])
