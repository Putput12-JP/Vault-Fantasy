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
  polymarket  NBA events (game markets and player props): best bid / ask / last per market, fee rate in meta
  injuries    official NBA injury report, parsed; one row per player status change
  prizepicks  PrizePicks NBA board (partner API; the public host 403s servers): line per projection, with its
              odds_type (standard / demon / goblin) in meta. Flat payout, so the line is the price.
  underdog    Underdog Pick'em NBA lines: line plus each side's fantasy price (American) and payout multiplier
  sleeper     Sleeper Picks NBA lines: line plus each side's payout multiplier (decimal price)
  lineups     NBA.com daily lineups: each listed player's starting slot, Expected / Confirmed, active / inactive,
              so the log shows when each team's five went from Expected to Confirmed

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
from collections import defaultdict
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
                names = {c['homeAway']: c['team'].get('displayName') for c in comp['competitors']}
                for c in comp['competitors']:          # abbreviation -> nickname, the join key across venues
                    self.nick[c['team']['abbreviation']] = nick(c['team'].get('displayName'))
                tip = iso(e['date'])
                pre = e['status']['type']['state'] == 'pre' and now < tip <= self.ahead
                g = {'id': e['id'], 'day': day.isoformat(), 'tip': tip, 'away': side.get('away'), 'home': side.get('home'),
                     'pre': pre, 'season_type': e['season']['type'], 'away_name': names.get('away'), 'home_name': names.get('home')}
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
KAL_SIZE = {}     # ticker -> [yes bid size, yes ask size]: contracts at the best prices. Board only (changes every
                  # poll; logging it would multiply the day files), so capacity is live, not historical.
KAL_VOL = {}      # ticker -> contracts traded, all time: Sharp Price diffs it poll to poll for heavy prop flow
PM_DEPTH = {}     # Polymarket market id -> [$ to buy the first outcome, $ to buy the second] within 1c of the best price,
                  # from the CLOB order books. Board only, like KAL_SIZE: what a stake can actually fill right now.


def pm_depth(tokens):
    """{market id: first-outcome token} -> PM_DEPTH. One POST per 100 books (clob.polymarket.com/books, free, keyless).
    The first outcome's book holds both sides: its asks fill a buy of that outcome, its bids a buy of the other one."""
    PM_DEPTH.clear()
    ids = list(tokens.items())
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        body = json.dumps([{'token_id': t} for _, t in chunk])
        try:
            p = subprocess.run(['curl', '-s', '--max-time', '30', '-X', 'POST', 'https://clob.polymarket.com/books', '-H', 'Content-Type: application/json', '-d', body],
                               capture_output=True, text=True)
            books = {b.get('asset_id'): b for b in json.loads(p.stdout or '[]')}
        except (ValueError, OSError):
            continue
        for k, t in chunk:
            b = books.get(t)
            if not b:
                continue
            asks = [(float(x['price']), float(x['size'])) for x in b.get('asks') or []]
            bids = [(float(x['price']), float(x['size'])) for x in b.get('bids') or []]
            ba, bb = min((a for a, _ in asks), default=None), max((a for a, _ in bids), default=None)
            yes = sum(a * z for a, z in asks if a <= ba + 0.01 + 1e-9) if ba is not None else 0
            no = sum((1 - a) * z for a, z in bids if a >= bb - 0.01 - 1e-9) if bb is not None else 0
            PM_DEPTH[k] = [round(yes), round(no)]


def src_kalshi(slate):
    rows, meta = {}, {}
    KAL_SIZE.clear()
    KAL_VOL.clear()
    for s in PROP_SERIES + GAME_SERIES:
        cur = ''
        while True:
            d = curl(f'{KAL}/markets?series_ticker={s}&status=open&limit=1000' + (f'&cursor={cur}' if cur else ''))
            for m in d.get('markets', []):
                if slate.kalshi_started(m['event_ticker']):
                    continue
                k = m['ticker']
                rows[k] = [num(m.get('yes_bid_dollars')), num(m.get('yes_ask_dollars'))]
                KAL_SIZE[k] = [num(m.get('yes_bid_size_fp')), num(m.get('yes_ask_size_fp'))]
                KAL_VOL[k] = num(m.get('volume_fp'))
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
    rows, meta, tok0 = {}, {}, {}
    for e in curl(f'https://gamma-api.polymarket.com/events?series_id={PM_SERIES}&closed=false&limit=500'):
        for m in e.get('markets', []):
            start = iso(m.get('gameStartTime', '').replace(' ', 'T').replace('+00', '+00:00') if m.get('gameStartTime') else e.get('endDate'))
            if m.get('closed') or not start or start <= slate.now or start > slate.ahead:
                continue
            k = str(m['id'])
            rows[k] = [num(m.get('bestBid')), num(m.get('bestAsk')), num(m.get('lastTradePrice'))]
            fs = m.get('feeSchedule') or {}
            try:
                tok0[k] = json.loads(m.get('clobTokenIds') or '[]')[0]
            except (ValueError, IndexError):
                pass
            meta[k] = {'event': e.get('slug'), 'q': m.get('question'), 'type': m.get('sportsMarketType'),
                       'line': m.get('line'), 'outcomes': m.get('outcomes'), 'start': start, 'cid': m.get('conditionId'),
                       'fee': fs.get('rate') if m.get('feesEnabled') else 0}   # taker fee per share = rate x p x (1 - p)
    pm_depth(tok0)
    return rows, meta


def src_lineups(slate):
    """NBA.com's daily lineups file (fetch_lineups.py) for each ET day with a game tipping within 36 h.
    Key 'YYYY-MM-DD|TEAM|player' -> [slot or '', Expected / Confirmed, Active / Inactive]. Pre-tip games only."""
    from fetch_lineups import URL, team_abbr
    rows, meta = {}, {}
    days = sorted({g['day'] for g in slate.games if g['pre'] and g['tip'] - slate.now < 36 * 3600})
    for day in days:
        d = curl(URL.format(day.replace('-', '')))
        pre = {(g['day'], t) for g in slate.games if g['pre'] for t in (g['away'], g['home'])}
        for gm in d.get('games', []):
            for side in ('homeTeam', 'awayTeam'):
                t = gm.get(side) or {}
                team = team_abbr(t.get('teamAbbreviation'))
                if (day, team) not in pre:
                    continue
                for p in t.get('players') or []:
                    k = f"{day}|{team}|{p.get('playerName')}"
                    rows[k] = [p.get('position') or '', p.get('lineupStatus') or '', p.get('rosterStatus') or '']
                    meta[k] = {'day': day, 'team': team, 'player': p.get('playerName'), 'nba_id': p.get('personId'),
                               'nba_game': gm.get('gameId')}
    return rows, meta


# ── pick'em apps ──────────────────────────────────────────────────────────────────────────────
UA_HDR = ['User-Agent: Mozilla/5.0', 'Accept: application/json']
PP = 'https://partner-api.prizepicks.com/projections?league_id=7&per_page=250&single_stat=true&page={}'
UD = 'https://api.underdogfantasy.com/v1/over_under_lines?sport_id=NBA'
SL = 'https://api.sleeper.com/lines/available?dynamic=true&include_preseason=true'
SL_SPORT = 'nba'
_sleeper_players = {}


def team_code(c):
    c = (c or '').upper()
    return TEAM.get(c, c)


def pre_teams(slate):
    return {t for g in slate.games if g['pre'] for t in (g['away'], g['home'])}


def src_prizepicks(slate):
    rows, meta = {}, {}
    inc, page, pages = {}, 1, 1
    data = []
    while page <= min(pages, 20):
        d = curl(PP.format(page), UA_HDR)
        data += d.get('data', [])
        inc.update({(i['type'], i['id']): i['attributes'] for i in d.get('included', [])})
        pages = (d.get('meta') or {}).get('total_pages') or 1
        page += 1
    for x in data:
        a, rel = x['attributes'], x.get('relationships') or {}
        start = iso(a.get('start_time'))
        if a.get('status') != 'pre_game' or a.get('in_game') or not start or not (slate.now < start <= slate.ahead):
            continue
        pl = inc.get(('new_player', ((rel.get('new_player') or {}).get('data') or {}).get('id')), {})
        if pl.get('combo'):
            continue
        rows[x['id']] = [num(a.get('line_score')), num(a.get('flash_sale_line_score'))]
        meta[x['id']] = {'player': pl.get('name'), 'team': team_code(pl.get('team')), 'stat': a.get('stat_type'),
                         'odds': a.get('odds_type'), 'dur': ((rel.get('duration') or {}).get('data') or {}).get('id'),
                         'start': start, 'opp': team_code(a.get('description'))}
    return rows, meta


def src_underdog(slate):
    d = curl(UD, UA_HDR)
    rows, meta = {}, {}
    team, start = {}, {}
    for g in d.get('games', []) + d.get('solo_games', []):
        ab = (g.get('abbreviated_title') or '').split(' @ ')
        if len(ab) == 2:
            team[g.get('away_team_id')], team[g.get('home_team_id')] = team_code(ab[0]), team_code(ab[1])
        start[g['id']] = iso(g.get('scheduled_at'))
    players = {p['id']: p for p in d.get('players', [])}
    apps = {a['id']: a for a in d.get('appearances', [])}
    for l in d.get('over_under_lines', []):
        ast = (l.get('over_under') or {}).get('appearance_stat') or {}
        app = apps.get(ast.get('appearance_id'))
        t0 = start.get(app.get('match_id')) if app else None
        if l.get('status') != 'active' or l.get('live_event') or not t0 or not (slate.now < t0 <= slate.ahead):
            continue
        side = {o.get('choice'): o for o in l.get('options', [])}
        px = lambda o: ((((o or {}).get('odds') or {}).get('fantasy') or {}).get('american')) or (o or {}).get('american_price')
        hi, lo = side.get('higher'), side.get('lower')
        rows[l['id']] = [num(l.get('stat_value')), px(hi), px(lo), num((hi or {}).get('payout_multiplier')),
                         num((lo or {}).get('payout_multiplier'))]
        p = players.get(app.get('player_id')) or {}
        meta[l['id']] = {'player': f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(), 'team': team.get(p.get('team_id')),
                         'stat': ast.get('stat'), 'kind': l.get('line_type'), 'start': t0}
    return rows, meta


def src_sleeper(slate):
    if not _sleeper_players:        # once per process: Sleeper ids -> name, team, ESPN id
        for pid, p in curl('https://api.sleeper.app/v1/players/nba').items():
            _sleeper_players[pid] = {'name': p.get('full_name'), 'team': p.get('team'), 'espn': p.get('espn_id')}
    teams = pre_teams(slate)
    rows, meta = {}, {}
    for l in curl(SL, UA_HDR):
        if l.get('sport') != SL_SPORT or l.get('subject_type') != 'player' or l.get('game_status') != 'pre_game':
            continue
        side = {o.get('outcome'): o for o in l.get('options', [])}
        o = side.get('over') or side.get('under')
        tm = team_code((o or {}).get('subject_team'))
        if not o or tm not in teams:
            continue
        k = f"{l['subject_id']}|{l.get('wager_type')}|{l.get('line_type')}"
        rows[k] = [num(o.get('outcome_value')), num((side.get('over') or {}).get('payout_multiplier')),
                   num((side.get('under') or {}).get('payout_multiplier'))]
        sp = _sleeper_players.get(str(l['subject_id']), {})
        meta[k] = {'player': sp.get('name'), 'team': tm, 'espn': sp.get('espn'), 'stat': l.get('wager_type'),
                   'kind': l.get('line_type'), 'game': l.get('game_id')}
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
WIRE_SRC = ('injuries', 'lineups')


class Day:
    def __init__(self, root, day):
        self.dir = os.path.join(root, 'snapshots', day)
        os.makedirs(self.dir, exist_ok=True)
        self.last, self.known = {}, set()
        self.meta, self.first = defaultdict(dict), defaultdict(dict)   # what each key is; its first value today
        self.when = defaultdict(dict)                                   # when each key last changed (epoch s)
        self.hist = defaultdict(lambda: defaultdict(list))              # every change time per key today (Injury Wire)
        self.t0 = {}                                                    # first poll today per source: its rows are the
                                                                        # starting state, not news
        self.log = defaultdict(list)                                    # injuries / lineups: (t, key, before, after)
        for f in os.listdir(self.dir):
            src = f[:-6]
            if f == 'meta.jsonl':
                for r in map(json.loads, open(os.path.join(self.dir, f))):
                    self.known.add((r['src'], r['k']))
                    self.meta[r['src']][r['k']] = r
            elif f.endswith('.jsonl') and f not in ('polls.jsonl', 'tape.jsonl'):   # tape: trades, not a change log
                last, first, when = self.last.setdefault(src, {}), self.first[src], self.when[src]
                for line in open(os.path.join(self.dir, f)):
                    r = json.loads(line)
                    when[r['k']] = r['t']
                    self.hist[src][r['k']].append(r['t'])
                    self.t0.setdefault(src, r['t'])
                    if src in WIRE_SRC:
                        self.log[src].append((r['t'], r['k'], last.get(r['k']), r['v']))
                    if r['v'] is None:
                        last.pop(r['k'], None)
                    else:
                        last[r['k']] = r['v']
                        first.setdefault(r['k'], r['v'])

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
        for r in out:
            self.when[src][r['k']] = t
            self.hist[src][r['k']].append(t)
            if src in WIRE_SRC:
                self.log[src].append((t, r['k'], last.get(r['k']), r['v']))
        if out:
            self.t0.setdefault(src, t)
        self.append('meta.jsonl', [{'k': k, 'src': src, **m} for k, m in meta.items() if (src, k) not in self.known])
        self.known |= {(src, k) for k in meta}
        self.meta[src].update(meta)
        for k, v in rows.items():
            self.first[src].setdefault(k, v)
        self.last[src] = dict(rows)
        return len(out)


def poll(root):
    now = int(time.time())
    slate = Slate(now)
    day = Day(root, dt.datetime.fromtimestamp(now, ET).date().isoformat())
    sources = [('kalshi', src_kalshi), ('espn', src_espn), ('pinnacle', src_pinnacle), ('action', src_action),
               ('polymarket', src_polymarket), ('injuries', Injuries(day.dir)), ('lineups', src_lineups),
               ('prizepicks', src_prizepicks), ('underdog', src_underdog), ('sleeper', src_sleeper)]
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
    t0 = time.time()                                    # trade tapes: Polymarket accounts, Kalshi big tickets (sharp.py)
    rec = {'t': int(t0), 'src': 'tape', 'ok': True}
    try:
        import sharp
        from prop_board import TEAM as BTEAM
        rec['n'], rec['chg'] = sharp.poll_tapes(root, day, slate, int(t0), curl, parse_event, BTEAM)
    except Exception as e:
        rec.update(ok=False, err=str(e)[:200])
        traceback.print_exc(limit=1)
    rec['s'] = round(time.time() - t0, 1)
    polls.append(rec)
    print(f"  tape       {'ok ' if rec['ok'] else 'ERR'} markets={rec.get('n', '-')} new={rec.get('chg', '-')} {rec['s']}s {rec.get('err', '')}", flush=True)
    day.append('polls.jsonl', polls)
    write_status(root, day, slate, polls, metas)
    board = write_board(root, day, slate)
    shadow(root, day, board, now, polls)
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
    # pick'em apps: [0, lines], joined on team (and start time when the app gives one)
    by_team = defaultdict(list)
    for key, g in games.items():
        for t in (g['away'], g['home']):
            by_team[t].append((g['tip'], key))
    for src in ('prizepicks', 'underdog', 'sleeper'):
        for k, m in (metas.get(src) or {}).items():
            c = by_team.get(m.get('team'))
            if c and (src != 'prizepicks' or m.get('odds') == 'standard'):
                add(src, min(c, key=lambda x: abs(x[0] - (m.get('start') or x[0])))[1], True)
    # lineups: [teams whose five is Confirmed, starters listed]
    team_game = {(g['day'], t): (g['day'], slate.nick.get(g['home'])) for g in slate.games if g['pre'] for t in (g['away'], g['home'])}
    conf = defaultdict(dict)
    for k, v in day.last.get('lineups', {}).items():
        d_, team, _ = k.split('|', 2)
        key = team_game.get((d_, team))
        if key in games and v[0]:
            games[key]['cov'].setdefault('lineups', [0, 0])[1] += 1
            conf[key][team] = conf[key].get(team, True) and v[1] == 'Confirmed'
    for key, teams in conf.items():
        games[key]['cov']['lineups'][0] = sum(teams.values())
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


BOARD = os.path.join(os.environ.get('RUNNER_TEMP') or os.path.join(os.path.dirname(__file__), '..', 'raw'), 'nba_board.json')


def write_board(root, day, slate):
    """Props board for the page (prop_board.py). Kept off nba-data: it is derived, and changes every poll."""
    try:
        from prop_board import build
        proj = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'player_projections.json')))
        board = build([g for g in slate.games if g['pre']], day.last, day.meta, day.first, proj, slate.now, sizes=KAL_SIZE, pm_depth=PM_DEPTH, when=day.when,
                      wire=(day.hist, day.log, day.t0))
        try:                                            # Sharp Price: Pinnacle history, tapes, signals (sharp.py)
            import sharp
            from prop_board import TEAM as BTEAM
            board['sharp'] = sharp.build(board, day, root, slate.now, BTEAM, parse_event, kal_vol=KAL_VOL)
        except Exception:
            traceback.print_exc(limit=2)
        board.pop('_pkeys', None)
        with open(BOARD, 'w') as f:
            json.dump(board, f, separators=(',', ':'))
        save_wire(day, board.get('wire') or [], slate.now)
        try:                                            # each prop's close, for My bets (ledger.closes_record)
            import ledger
            ledger.close_log(root, board, slate.now)
        except Exception:
            traceback.print_exc(limit=2)
        print(f"  board      {len(board['props'])} player-stat markets, unmapped {board['unmapped']}", flush=True)
        return board
    except Exception:
        traceback.print_exc(limit=2)
        return None


def save_wire(day, events, now):
    """Keep today's Injury Wire in the day folder (snapshots/<day>/wire.json): every event with its venue reactions,
    updated each poll until its game tips, then frozen (after tip the game leaves the board). Settlement turns the
    days into the season's venue record (ledger.wire_record)."""
    path = os.path.join(day.dir, 'wire.json')
    try:
        kept = json.load(open(path)) if os.path.exists(path) else {}
    except ValueError:
        kept = {}
    for e in events:
        k = f"{e[0]}|{e[1]}|{e[2]}|{e[3] or e[4]}"
        if k not in kept or now < kept[k][-1]:                     # before tip: the latest reactions win
            kept[k] = e
    with open(path, 'w') as f:
        json.dump(kept, f, separators=(',', ':'))


def shadow(root, day, board, now, polls):
    """Shadow ledger (ledger.py): log every 3%+ edge the page would show, then settle finished games -> track.json."""
    rec = {'t': now, 'src': 'ledger', 'ok': True}
    try:
        import ledger
        if board is not None:                    # no board = unknown, not "every edge is gone"
            rows, meta = ledger.log(day, board, now)
            rec.update(n=len(rows), chg=day.record('ledger', now, rows, meta))
            mrows, mmeta = ledger.minutes_log(board, now)      # the Minutes Lab's record
            rec['minutes'] = len(mrows)
            day.record('minutes', now, mrows, mmeta)
        rec['bets'] = ledger.settle(root, now)
    except Exception as e:
        rec.update(ok=False, err=str(e)[:200])
        traceback.print_exc(limit=2)
    day.append('polls.jsonl', [rec])
    print(f"  ledger     {'ok ' if rec['ok'] else 'ERR'} tracked={rec.get('n', '-')} chg={rec.get('chg', '-')} bets={rec.get('bets', '-')} {rec.get('err', '')}", flush=True)


def push_board(root):
    """Force-push board.json as a single parentless commit to nba-live: always one file, no history."""
    if not os.path.exists(BOARD):
        return
    git = ['git', '-C', root]
    blob = subprocess.run(git + ['hash-object', '-w', BOARD], capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(git + ['mktree'], input=f'100644 blob {blob}\tboard.json\n', capture_output=True, text=True).stdout.strip()
    c = subprocess.run(git + ['commit-tree', tree, '-m', 'nba live board'], capture_output=True, text=True).stdout.strip()
    if c and subprocess.run(git + ['push', '-q', '--force', 'origin', f'{c}:refs/heads/nba-live']).returncode != 0:
        print('board push failed', flush=True)


def commit(root):
    push_board(root)
    git = ['git', '-C', root]
    subprocess.run(git + ['add', '-A', 'snapshots', 'status.json'] + [p for p in ('track.json', 'results', 'bets') if os.path.exists(os.path.join(root, p))], check=True)
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
