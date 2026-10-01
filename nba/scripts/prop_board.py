#!/usr/bin/env python3
"""
The player-props board: every venue's current prop quotes, matched to our player ids, one entry per
player x stat. Pricing (model, blended fair price, edge) happens in the page, so a minutes edit in the
Minutes Lab reprices the board without a rebuild.

Built two ways:
  live      snapshot.py calls build() after every poll and force-pushes board.json to the `nba-live`
            branch (one commit, no history: the prices themselves are already in nba-data)
  page      python3 nba/scripts/prop_board.py   fetches that board.json for the artifact snapshot and
            builds the EXAMPLE board (last season's final game at its pre-tip prices) from raw/tables,
            writes data/prop_board.json and re-renders the page

Board shape (compact, it ships in the page):
  {t, games: [{id, day, tip, away, home, season_type}], players: {pid: [name, team, injury status, lineup]},
   (players also carry [.., injury changed at, lineup changed at]; outs = [[pid, team, status]] everyone Out, Doubtful or inactive tonight;
    news = [[t, pid, name, team, 'inj' | 'lu', status]] newest first; book / Kalshi / pick'em rows end with their last
    change time)
   lineup = NBA.com: 'S' confirmed starter, 's' expected starter, 'B' confirmed bench, 'b' expected bench, 'X' inactive,
   props: [{p, s, g, kal: [[line, bid, ask, open_mid, bid_size, ask_size]],   sizes = contracts at the best price books: [[book, line, over, under, open_line, open_over]],
            pk: [[app, line, over, under, open_line]]}],     books include Polymarket (fee in); pk = pick'em apps
   unmapped: {venue: count}}
Kalshi rung "25+" is YES iff stat > 24.5, so its line is the floor strike, same convention as a book line.
"""
import csv, datetime as dt, json, os, re, subprocess, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from nba_common import name_key
from build_backtest_tables import ESPN_MKT, prop_markets
from backfill_kalshi import parse_event

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
KAL_STAT = {'KXNBAPTS': 'pts', 'KXNBAREB': 'reb', 'KXNBAAST': 'ast', 'KXNBA3PT': '3pm',
            'KXNBAPRA': 'pra', 'KXNBAPR': 'pr', 'KXNBAPA': 'pa', 'KXNBARA': 'ra'}
PIN_STAT = [(r'pts\s*\+\s*rebs?\s*\+\s*asts?|points.*rebounds.*assists', 'pra'), (r'pts\s*\+\s*rebs?|points.*rebounds', 'pr'),
            (r'pts\s*\+\s*asts?|points.*assists', 'pa'), (r'rebs?\s*\+\s*asts?|rebounds.*assists', 'ra'),
            (r'3|three', '3pm'), (r'point', 'pts'), (r'rebound', 'reb'), (r'assist', 'ast')]
PRICED = {'pts', 'reb', 'ast', '3pm', 'pra', 'pr', 'pa', 'ra'}   # what the prop model can price
PM_STAT = {'points': 'pts', 'rebounds': 'reb', 'assists': 'ast', 'threes': '3pm'}
PP_STAT = {'Points': 'pts', 'Rebounds': 'reb', 'Assists': 'ast', '3-PT Made': '3pm', 'Pts+Rebs+Asts': 'pra',
           'Pts+Rebs': 'pr', 'Pts+Asts': 'pa', 'Rebs+Asts': 'ra'}
UD_STAT = {'points': 'pts', 'rebounds': 'reb', 'assists': 'ast', 'three_points_made': '3pm', 'pts_rebs_asts': 'pra',
           'pts_rebs': 'pr', 'pts_asts': 'pa', 'rebs_asts': 'ra'}
SL_STAT = {'points': 'pts', 'rebounds': 'reb', 'assists': 'ast', 'threes_made': '3pm', 'pts_reb_ast': 'pra',
           'pts_reb': 'pr', 'pts_ast': 'pa', 'reb_ast': 'ra'}
TEAM = {'GSW': 'GS', 'NYK': 'NY', 'SAS': 'SA', 'NOP': 'NO', 'UTA': 'UTAH', 'WAS': 'WSH', 'PHO': 'PHX', 'BRK': 'BKN'}


def nick(name):
    return name.split()[-1].lower() if name else None


class Roster:
    """Our player ids by name, scoped to a team when we know it (two players can share a name key)."""

    def __init__(self, proj):
        self.by_key, self.info = defaultdict(list), {}
        for team, t in proj['teams'].items():
            for p in t['players']:
                self.by_key[name_key(p['name'])].append((p['id'], team))
                self.info[p['id']] = (p['name'], team)

    def find(self, name, teams=()):
        c = self.by_key.get(name_key(name), [])
        scoped = [pid for pid, tm in c if tm in teams]
        if len(scoped) == 1:
            return scoped[0]
        return c[0][0] if len(c) == 1 else None


def pin_stat(label):
    label = (label or '').lower()
    for pat, s in PIN_STAT:
        if re.search(pat, label):
            return s
    return None


def build(games, last, meta, first, proj, now, sizes=None, when=None, wire=None):
    """games: pre-tip slate games; last/meta/first: {src: {key: value}} current rows, their metadata and the
    first value seen today."""
    R = Roster(proj)
    W = lambda src, *keys: max([t for t in ((when or {}).get(src, {}).get(k) for k in keys) if t] or [None])   # last change
    gkey = {(g['day'], g['home']): g for g in games}
    nicks = {}
    for g in games:
        for side in ('away', 'home'):
            if g.get(side + '_name'):
                nicks[nick(g[side + '_name'])] = g[side]
    by_id = {str(g['id']): g for g in games}
    props, players, unmapped = {}, {}, defaultdict(int)
    qk = defaultdict(list)          # team -> [(venue, source, key)]: every prop quote, for the Injury Wire's reaction times

    def entry(pid, stat, g):
        name, team = R.info[pid]
        players[pid] = [name, team, None, None]
        return props.setdefault((pid, stat), {'p': pid, 's': stat, 'g': g['id'], 'kal': [], 'books': [], 'pk': []})

    def team_game(team, start=None):
        """Tonight's game for a team (the one nearest `start` when a team has two on the slate)."""
        c = [g for g in games if team in (g['away'], g['home'])]
        return min(c, key=lambda g: abs(g['tip'] - (start or g['tip']))) if c else None

    # Kalshi ladders
    for k, v in (last.get('kalshi') or {}).items():
        m = meta.get('kalshi', {}).get(k)
        stat = KAL_STAT.get((m or {}).get('series'))
        if not stat:
            continue
        g = next((gkey[(d, TEAM.get(h, h))] for d, a, h in parse_event(m['event']) or [] if (d, TEAM.get(h, h)) in gkey), None)
        pid = g and R.find((m.get('sub') or m.get('title') or '').split(':')[0], (g['away'], g['home']))
        if not pid or m.get('floor') is None:
            unmapped['kalshi'] += 1
            continue
        f = (first.get('kalshi') or {}).get(k)
        om = round((f[0] + f[1]) / 2, 3) if f and f[0] is not None and f[1] is not None else None
        sz = (sizes or {}).get(k) or [None, None]
        entry(pid, stat, g)['kal'].append([m['floor'], v[0], v[1], om, sz[0], sz[1], W('kalshi', k)])
        qk[R.info[pid][1]].append(('Kalshi', 'kalshi', k))

    # ESPN (DraftKings): rebuild the backfill's row shape so prop_markets() assigns over/under the audited way
    per_game = defaultdict(list)
    for k, v in (last.get('espn') or {}).items():
        m = meta.get('espn', {}).get(k)
        if not m or k.endswith('|game'):
            continue
        per_game[str(m['game'])].append({'type': m['type'], 'athlete_id': m['athlete_id'], 'provider_id': int(k.split('|')[1]),
                                         'open_line': m['open_line'], 'open_px': m['open_px'], 'ord': m['ord'],
                                         'cur_line': v[0], 'cur_px': v[1], 'last_updated': None, '_book': m['book'], '_t': W('espn', k), '_k': k})
    for gid, rows in per_game.items():
        g = by_id.get(gid)
        book = {r['provider_id']: r['_book'] for r in rows}
        tmk = defaultdict(int)                            # (book, athlete, market) -> last change of any of its rows
        for r in rows:
            if r['type'] in ESPN_MKT and r['athlete_id'] in R.info:
                qk[R.info[r['athlete_id']][1]].append((r['_book'], 'espn', r['_k']))
            if r['type'] in ESPN_MKT and r['_t']:
                kk = (r['provider_id'], r['athlete_id'], ESPN_MKT[r['type']][0])
                tmk[kk] = max(tmk[kk], r['_t'])
        for mk in prop_markets({'props': rows}):
            pid = mk['athlete_id']
            if mk['market'] not in PRICED:
                continue
            if not g or pid not in R.info or mk['kind'] != 'main':
                unmapped['espn'] += mk['kind'] == 'main'
                continue
            entry(pid, mk['market'], g)['books'].append(
                [book.get(mk['provider_id'], 'ESPN'), mk['cur_line'], mk['over_cur'], mk['under_cur'], mk['line'], mk['over_open'],
                 tmk.get((mk['provider_id'], mk['athlete_id'], mk['market'])) or None])

    # Pinnacle: "Jalen Brunson (Points)" specials with Over / Under sides
    pin = defaultdict(dict)
    for k, v in (last.get('pinnacle') or {}).items():
        m = meta.get('pinnacle', {}).get(k)
        if not m or not m.get('parent') or m.get('side') not in ('Over', 'Under'):
            continue
        pin[m['matchup']][m['side']] = (v, m, (first.get('pinnacle') or {}).get(k), k)
    for mid, sides in pin.items():
        if 'Over' not in sides or 'Under' not in sides:
            continue
        (ov, m, fo, ko), (uv, _, _, ku) = sides['Over'], sides['Under']
        mt = re.match(r'^(.*?)\s*\((.*)\)\s*$', m.get('desc') or '')
        home = next((n for a, n in m.get('teams') or [] if a == 'home'), None)
        g = gkey.get((dt.datetime.fromtimestamp(m['start'], ET).date().isoformat(), nicks.get(nick(home))))
        stat = mt and pin_stat(mt.group(2))
        pid = g and stat and R.find(mt.group(1), (g['away'], g['home']))
        if not pid:
            unmapped['pinnacle'] += 1
            continue
        entry(pid, stat, g)['books'].append(['Pinnacle', ov[0], fmt_am(ov[1]), fmt_am(uv[1]),
                                              fo[0] if fo else None, fmt_am(fo[1]) if fo else None, W('pinnacle', ko, ku)])
        qk[R.info[pid][1]] += [('Pinnacle', 'pinnacle', ko), ('Pinnacle', 'pinnacle', ku)]

    # Polymarket player props: YES = over the line. Priced like a book: over = YES ask, under = 1 - YES bid, each
    # plus the taker fee (rate x p x (1 - p) per share), as American odds so the page treats it like any book.
    for k, v in (last.get('polymarket') or {}).items():
        m = meta.get('polymarket', {}).get(k) or {}
        stat = PM_STAT.get(m.get('type'))
        if not stat or m.get('line') is None:
            continue
        p = (m.get('event') or '').split('-')              # nba-<away>-<home>-YYYY-MM-DD
        tm = [TEAM.get(x.upper(), x.upper()) for x in p[1:3]] if len(p) >= 6 else []
        g = next((team_game(t, m.get('start')) for t in tm if team_game(t, m.get('start'))), None)
        pid = g and R.find((m.get('q') or '').split(':')[0], (g['away'], g['home']))
        if not pid:
            unmapped['polymarket'] += 1
            continue
        bid, ask = v[0], v[1]
        fee = lambda x: (m.get('fee') or 0) * x * (1 - x)
        o = prob_am(ask + fee(ask)) if ask and 0 < ask < 1 else None
        u = prob_am(1 - bid + fee(1 - bid)) if bid and 0 < bid < 1 else None
        f = (first.get('polymarket') or {}).get(k)
        if o and u:
            entry(pid, stat, g)['books'].append(['Polymarket', float(m['line']), o, u, float(m['line']) if f else None,
                                                  prob_am(f[1] + fee(f[1])) if f and f[1] and 0 < f[1] < 1 else None, W('polymarket', k)])
            qk[R.info[pid][1]].append(('Polymarket', 'polymarket', k))

    # pick'em apps -> e['pk'] = [app, line, over price, under price, first line today]. PrizePicks standard lines only
    # (demon / goblin are alternate lines at other payouts) and it pays flat, so its prices are None.
    for k, v in (last.get('prizepicks') or {}).items():
        m = meta.get('prizepicks', {}).get(k) or {}
        stat = PP_STAT.get(m.get('stat'))
        if not stat or m.get('odds') != 'standard' or v[0] is None:
            continue
        g = team_game(m.get('team'), m.get('start'))
        pid = g and R.find(m.get('player'), [m.get('team')])
        if not pid:
            unmapped['prizepicks'] += 1
            continue
        f = (first.get('prizepicks') or {}).get(k)
        entry(pid, stat, g)['pk'].append(['PrizePicks', v[0], None, None, f[0] if f else None, W('prizepicks', k)])
        qk[R.info[pid][1]].append(('PrizePicks', 'prizepicks', k))
    for k, v in (last.get('underdog') or {}).items():
        m = meta.get('underdog', {}).get(k) or {}
        stat = UD_STAT.get(m.get('stat'))
        if not stat or v[0] is None:
            continue
        g = team_game(m.get('team'), m.get('start'))
        pid = g and R.find(m.get('player'), [m.get('team')])
        if not pid:
            unmapped['underdog'] += 1
            continue
        f = (first.get('underdog') or {}).get(k)
        entry(pid, stat, g)['pk'].append(['Underdog', v[0], v[1], v[2], f[0] if f else None, W('underdog', k)])
        qk[R.info[pid][1]].append(('Underdog', 'underdog', k))
    for k, v in (last.get('sleeper') or {}).items():
        m = meta.get('sleeper', {}).get(k) or {}
        stat = SL_STAT.get(m.get('stat'))
        if not stat or v[0] is None:
            continue
        g = team_game(m.get('team'))
        espn = int(m['espn']) if str(m.get('espn') or '').isdigit() else None
        pid = espn if espn in R.info else g and R.find(m.get('player'), [m.get('team')])
        if not pid or not g:
            unmapped['sleeper'] += 1
            continue
        f = (first.get('sleeper') or {}).get(k)
        entry(pid, stat, g)['pk'].append(['Sleeper', v[0], dec_am(v[1]), dec_am(v[2]), f[0] if f else None, W('sleeper', k)])
        qk[R.info[pid][1]].append(('Sleeper', 'sleeper', k))

    # injury report: current status per player on tonight's teams
    inj, news = {}, []
    for k, v in (last.get('injuries') or {}).items():
        _, team, player = k.split('|', 2)
        pid = R.find(player, [g[s] for g in games for s in ('away', 'home') if nick(team) == nick(g.get(s + '_name'))])
        if pid:
            inj[pid] = (v[0], W('injuries', k))
            news.append([W('injuries', k), pid, R.info[pid][0], R.info[pid][1], 'inj', v[0]])
    # NBA.com lineups: starting slot, Expected / Confirmed, Active / Inactive
    lu = {}
    for k, v in (last.get('lineups') or {}).items():
        _, team, player = k.split('|', 2)
        pid = R.find(player, [team])
        if pid:
            code = 'X' if v[2] == 'Inactive' else ('S' if v[0] else 'B') if v[1] == 'Confirmed' else ('s' if v[0] else 'b')
            lu[pid] = (code, W('lineups', k))
            if code in ('S', 'X'):
                news.append([W('lineups', k), pid, R.info[pid][0], team, 'lu', code])
    for pid in players:
        players[pid][2], it = inj.get(pid, (None, None))
        players[pid][3], lt = lu.get(pid, (None, None))
        players[pid] += [it, lt]
    # everyone ruled out tonight, with or without props (books pull an Out player's props, but his teammates still
    # need his minutes): [pid, team]. pricing.py and the page apply these before anything else.
    # [pid, team, status]: Out and Doubtful from the injury report (the minutes model counts both as out, as the
    # backtest did), Inactive from NBA.com. The Lab's minutes rebalance uses Out and Inactive only.
    outs = {pid: (R.info[pid][1], st.split()[0].capitalize()) for pid, (st, _) in inj.items()
            if st and st.lower().startswith(('out', 'doubt'))}
    outs.update({pid: (R.info[pid][1], 'Inactive') for pid, (c, _) in lu.items() if c == 'X'})
    outs = sorted([pid, t, s_] for pid, (t, s_) in outs.items())

    for e in props.values():
        e['kal'].sort()
    glines = game_lines(games, last, meta, gkey, nicks)
    # confirmed starting fives (minutes v3's starters-known weights use them): {team: [pid x 5]}
    five = defaultdict(list)
    for pid, (c, _) in lu.items():
        if c == 'S':
            five[R.info[pid][1]].append(pid)
    starters = {t: sorted(v) for t, v in five.items() if len(v) == 5}
    news = sorted((n for n in news if n[0] and (n[4] == 'lu' or (n[5] or '').lower().startswith(('out', 'doubt', 'quest')))), reverse=True)[:60]
    wire_events = injury_wire(wire, qk, R, games, nicks) if wire else []
    return {'t': now, 'outs': outs, 'news': news, 'starters': starters, 'wire': wire_events,
            'games': [dict({k: g[k] for k in ('id', 'day', 'tip', 'away', 'home', 'season_type')}, **glines.get(str(g['id']), {}))
                                for g in games],
            'players': players, 'props': sorted(props.values(), key=lambda e: (e['g'], e['p'], e['s'])), 'unmapped': dict(unmapped)}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def game_lines(games, last, meta, gkey, nicks):
    """game id -> {total, spread (home, negative = home favoured), line_from}: the market's game environment,
    which prop model v2 reads. DraftKings via ESPN first, Pinnacle's main line otherwise."""
    out = {}
    for k, v in (last.get('espn') or {}).items():
        if k.endswith('|game') and num(v[5]) is not None and num(v[0]) is not None:
            out.setdefault(k.split('|')[0], {'total': num(v[5]), 'spread': num(v[0]), 'line_from': (meta.get('espn', {}).get(k) or {}).get('book', 'ESPN')})
    pin = defaultdict(dict)
    for k, v in (last.get('pinnacle') or {}).items():
        m = meta.get('pinnacle', {}).get(k)
        if not m or m.get('parent') or m.get('period') != 0 or m.get('type') not in ('total', 'spread'):
            continue
        home = next((n for a, n in m.get('teams') or [] if a == 'home'), None)
        g = gkey.get((dt.datetime.fromtimestamp(m['start'], ET).date().isoformat(), nicks.get(nick(home))))
        if not g:
            continue
        if m['type'] == 'total' and str(m.get('side')).lower() == 'over':
            pin[str(g['id'])]['total'] = num(v[0])
        if m['type'] == 'spread' and str(m.get('side')).lower() == 'home':
            pin[str(g['id'])]['spread'] = num(v[0])
    for gid, d in pin.items():
        if gid not in out and d.get('total') is not None and d.get('spread') is not None:
            out[gid] = dict(d, line_from='Pinnacle')
    return out


def injury_wire(wire, qk, R, games, nicks):
    """Today's injury and lineup changes for teams on the board, each with how fast every venue moved that team's
    player props afterwards: [t, kind, team, pid, who, before, after, {venue: [quotes, moved, median s, first s]}].
    kind: 'inj' (injury report status change), 'five' (NBA.com starting five confirmed), 'inactive'. Times are when
    the recorder first saw the change (polls every 5 to 15 minutes); a move is any change to a quote after that,
    including the book pulling it, so other news can move a quote too."""
    hist, log, t0 = wire
    teams = {g[s] for g in games for s in ('away', 'home')}
    events = []
    for t, k, before, after in log.get('injuries', []):
        if t <= t0.get('injuries', 0):
            continue                                       # the day's first report is the starting state
        _, team_name, player = k.split('|', 2)
        pid = R.find(player, [g[s] for g in games for s in ('away', 'home') if nick(team_name) == nick(g.get(s + '_name'))])
        b, a = (before or [None])[0], (after or [None])[0]
        if not pid or b == a or R.info[pid][1] not in teams:
            continue
        events.append([t, 'inj', R.info[pid][1], pid, R.info[pid][0], b, a or 'removed'])
    fives = defaultdict(list)
    for t, k, before, after in log.get('lineups', []):
        if t <= t0.get('lineups', 0) or not after:
            continue
        _, team, player = k.split('|', 2)
        if team not in teams:
            continue
        if after[1] == 'Confirmed' and after[0] and (not before or before[1] != 'Confirmed'):
            fives[(t, team)].append(player)
        if after[2] == 'Inactive' and (not before or before[2] != 'Inactive'):
            pid = R.find(player, [team])
            events.append([t, 'inactive', team, pid, R.info[pid][0] if pid else player, before[2] if before else None, 'Inactive'])
    for (t, team), who in fives.items():
        events.append([t, 'five', team, None, ', '.join(who), 'Expected', 'Confirmed'])
    out = []
    for e in sorted(events, key=lambda x: -x[0])[:150]:
        react = {}
        for venue, src, key in qk.get(e[2], []):
            r = react.setdefault(venue, [0, 0, []])
            r[0] += 1
            nxt = [x for x in hist.get(src, {}).get(key, []) if x > e[0]]
            if nxt:
                r[1] += 1
                r[2].append(min(nxt) - e[0])
        out.append(e + [{v: [n, m, sorted(l)[len(l) // 2] if l else None, min(l) if l else None] for v, (n, m, l) in react.items()}])
    return out


def prob_am(p):
    """Cost of $1 payout (fee included) -> American odds string."""
    if not p or not 0 < p < 1:
        return None
    return fmt_am(-round(100 * p / (1 - p)) if p >= .5 else round(100 * (1 - p) / p))


def dec_am(d):
    """Decimal payout multiplier (total return) -> American odds string."""
    return prob_am(1 / d) if d and d > 1 else None


def fmt_am(x):
    if x is None:
        return None
    x = int(x)
    return f'+{x}' if x > 0 else str(x)


try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
except Exception:  # pragma: no cover
    ET = dt.timezone(dt.timedelta(hours=-4))


# ── page build: live snapshot + example ─────────────────────────────────────────────────────────
def example(proj):
    """Last season's final game at its pre-tip prices, for showing how the board works before props list.
    Kalshi: the last trade before tip stands in for bid and ask (the backfill has trades, not the book)."""
    tab = os.path.join(HERE, '..', 'raw', 'tables')
    if not os.path.exists(os.path.join(tab, 'props_kalshi.csv')):
        return None
    R = Roster(proj)
    kal = list(csv.DictReader(open(os.path.join(tab, 'props_kalshi.csv'))))
    gid = max(kal, key=lambda r: int(r['tip_ts']))['game_id']
    kal = [r for r in kal if r['game_id'] == gid]
    tip = int(kal[0]['tip_ts'])
    teams = sorted({r['team'] for r in kal})
    home = TEAM.get(kal[0]['ticker'].split('-')[1][-3:], kal[0]['ticker'].split('-')[1][-3:])
    away = next(t for t in teams if t != home)
    g = {'id': gid, 'day': dt.datetime.fromtimestamp(tip, ET).date().isoformat(), 'tip': tip, 'away': away, 'home': home, 'season_type': 3}
    for r in csv.DictReader(open(os.path.join(tab, 'game_lines.csv'))):
        if r['game_id'] == gid and r['total_close'] and r['spread_close']:
            g.update(total=float(r['total_close']), spread=float(r['spread_close']), line_from=r['book'])
            break
    props, players = {}, {}

    def entry(pid, stat, r):
        players[pid] = [R.info[pid][0], r['team'], None, None]   # the team he played for that night
        return props.setdefault((pid, stat), {'p': pid, 's': stat, 'g': gid, 'kal': [], 'books': [], 'pk': []})
    for r in kal:
        pid = int(r['athlete_id'])
        px = r['yes_last_pretip'] or r['yes_vwap30_pretip']
        if pid in R.info and px:
            entry(pid, r['market'], r)['kal'].append([float(r['strike']), float(px), float(px), None])
    for r in csv.DictReader(open(os.path.join(tab, 'props_espn.csv'))):
        if r['game_id'] != gid or r['kind'] != 'main' or r['market'] not in PRICED or int(r['athlete_id'] or 0) not in R.info:
            continue
        pre = r['cur_is_pretip'] == '1'
        line, o, u = (r['line_cur'], r['over_px_cur'], r['under_px_cur']) if pre else (r['line_open'], r['over_px_open'], r['under_px_open'])
        if o and u:
            entry(int(r['athlete_id']), r['market'], r)['books'].append(
                ['DraftKings' if r['book_id'] == '100' else 'ESPN BET', float(line), o, u, float(r['line_open']), r['over_px_open']])
    lpath = os.path.join(tab, 'lineups.csv')             # that night's confirmed lineups (fetch_lineups.py --backfill)
    if os.path.exists(lpath):
        day = g['day'].replace('-', '')
        for r in csv.DictReader(open(lpath)):
            pid = R.find(r['player'], [r['team']]) if r['day'] == day and r['team'] in (home, away) else None
            if pid in players:
                players[pid][3] = 'X' if r['roster'] == 'Inactive' else ('S' if r['slot'] else 'B') if r['status'] == 'Confirmed' else ('s' if r['slot'] else 'b')
    for e in props.values():
        e['kal'].sort()
    five = defaultdict(list)
    for pid, P in players.items():
        if P[3] == 'S':
            five[P[1]].append(pid)
    return {'t': tip - 1800, 'example': True, 'starters': {t: sorted(v) for t, v in five.items() if len(v) == 5}, 'games': [g], 'players': players,
            'props': sorted(props.values(), key=lambda e: (e['p'], e['s'])), 'unmapped': {}}


def main():
    root = os.path.abspath(os.path.join(HERE, '..', '..'))
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    subprocess.run(['git', '-C', root, 'fetch', '-q', 'origin', 'nba-live'], check=False)
    p = subprocess.run(['git', '-C', root, 'show', 'origin/nba-live:board.json'], capture_output=True, text=True)
    live = json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
    ex = example(proj)
    prev = os.path.join(DATA, 'prop_board.json')
    if ex is None and os.path.exists(prev):              # no local archive (e.g. the daily job): keep the last example
        ex = json.load(open(prev)).get('example')
    out = {'live': live, 'example': ex, 'repo': 'Putput12-JP/Vault-Fantasy', 'branch': 'nba-live'}
    json.dump(out, open(os.path.join(DATA, 'prop_board.json'), 'w'), separators=(',', ':'))
    for k in ('live', 'example'):
        b = out[k]
        print(f"{k}: " + (f"{len(b['props'])} player-stat markets, {len(b['players'])} players, "
                          f"{sum(len(e['kal']) for e in b['props'])} Kalshi rungs, {sum(len(e['books']) for e in b['props'])} book lines, "
                          f"unmapped {b['unmapped']}" if b else 'none'))
    import render_app
    render_app.render()


if __name__ == '__main__':
    main()
