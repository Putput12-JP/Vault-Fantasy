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
    qk = defaultdict(list)          # (team, game id) -> [(venue, source, key)]: every prop quote, for the Injury Wire
    pkeys = {'kalshi': {}, 'pinnacle': {}, 'polymarket': {}}   # source key -> [pid, stat, ...]: Sharp Price's per-prop signals

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
        pkeys['kalshi'][k] = [pid, stat, m['floor'], str(g['id'])]
        qk[(R.info[pid][1], str(g['id']))].append(('Kalshi', 'kalshi', k))

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
            if r['type'] in ESPN_MKT and r['athlete_id'] in R.info and g:
                qk[(R.info[r['athlete_id']][1], str(g['id']))].append((r['_book'], 'espn', r['_k']))
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
        qk[(R.info[pid][1], str(g['id']))] += [('Pinnacle', 'pinnacle', ko), ('Pinnacle', 'pinnacle', ku)]
        pkeys['pinnacle'][ko] = [pid, stat, 'Over', str(g['id'])]
        pkeys['pinnacle'][ku] = [pid, stat, 'Under', str(g['id'])]

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
            qk[(R.info[pid][1], str(g['id']))].append(('Polymarket', 'polymarket', k))
        if pid:
            pkeys['polymarket'][k] = [pid, stat, float(m['line']), str(g['id'])]

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
        qk[(R.info[pid][1], str(g['id']))].append(('PrizePicks', 'prizepicks', k))
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
        qk[(R.info[pid][1], str(g['id']))].append(('Underdog', 'underdog', k))
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
        qk[(R.info[pid][1], str(g['id']))].append(('Sleeper', 'sleeper', k))

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
    gm = game_markets(games, last, meta, gkey, nicks, when)
    return {'t': now, 'outs': outs, 'news': news, 'starters': starters, 'wire': wire_events,
            'games': [dict({k: g.get(k) for k in ('id', 'day', 'tip', 'away', 'home', 'season_type', 'away_name', 'home_name')}, **glines.get(str(g['id']), {}), mk=gm.get(str(g['id'])))
                                for g in games],
            'players': players, 'props': sorted(props.values(), key=lambda e: (e['g'], e['p'], e['s'])), 'unmapped': dict(unmapped),
            '_pkeys': pkeys}                    # internal: Sharp Price joins per-prop signals on it; dropped before the board is written


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


AN_BOOK = {15: 'Consensus', 30: 'Open', 68: 'DraftKings', 69: 'FanDuel', 75: 'BetMGM', 71: 'BetRivers', 79: 'bet365'}


def _median_cross(pts):
    """[(x, P(value > x))] -> x where P crosses 0.5 (linear between the two rungs around it), or None."""
    pts = sorted(pts)
    for (x0, p0), (x1, p1) in zip(pts, pts[1:]):
        if p0 >= 0.5 >= p1 and p0 != p1:
            return round(x0 + (p0 - 0.5) / (p0 - p1) * (x1 - x0), 1)
    return None


def game_markets(games, last, meta, gkey, nicks, when=None):
    """game id -> {books: [[book, home spread, home px, away px, home ml, away ml, total, over px, under px, changed]],
    splits: {spread|total|moneyline: [bets %, money %] for the home / over side}, open: {spread, total},
    kalshi: {win (home), spread (home, implied by the ladder), total (implied)}, poly: {win (home), total, over}}.
    Books from Action Network (seven books incl. consensus and open), ESPN where Action lacks the book, Pinnacle."""
    W = lambda src, *ks: max([t for t in ((when or {}).get(src, {}).get(k) for k in ks) if t] or [None])
    et_day = lambda t: dt.datetime.fromtimestamp(t, ET).date().isoformat() if t else None
    out = defaultdict(lambda: {'books': {}, 'splits': {}, 'open': {}, 'kalshi': {}, 'poly': {}})
    row = lambda: [None] * 9 + [None]
    # Action Network
    for k, v in (last.get('action') or {}).items():
        m = meta.get('action', {}).get(k) or {}
        g = gkey.get((et_day(m.get('start')), TEAM.get(m.get('home'), m.get('home'))))
        if not g:
            continue
        o = out[str(g['id'])]
        book, typ, side = AN_BOOK.get(m.get('book'), str(m.get('book'))), m.get('type'), str(m.get('side') or '')
        r = o['books'].setdefault(book, row())
        home = side.startswith('home')
        if typ == 'spread':
            if home:
                r[0], r[1] = num(v[0]), fmt_am(v[1])
            elif side.startswith('away'):
                r[2] = fmt_am(v[1])
        elif typ == 'moneyline' and (home or side.startswith('away')):
            r[3 if home else 4] = fmt_am(v[1])
        elif typ == 'total':
            if side == 'over':
                r[5], r[6] = num(v[0]), fmt_am(v[1])
            elif side == 'under':
                r[7] = fmt_am(v[1])
        r[9] = max([x for x in (r[9], W('action', k)) if x is not None] or [None])
        if (v[2] or v[3]) and (home or side == 'over') and typ in ('spread', 'total', 'moneyline'):   # 0 / 0 = not reported
            o['splits'][typ] = [v[2], v[3]]
        if book == 'Open' and typ == 'spread' and home:
            o['open']['spread'] = num(v[0])
        if book == 'Open' and typ == 'total' and side == 'over':
            o['open']['total'] = num(v[0])
    # ESPN (DraftKings / ESPN BET) where Action does not carry the book
    for k, v in (last.get('espn') or {}).items():
        if not k.endswith('|game'):
            continue
        m = meta.get('espn', {}).get(k) or {}
        gid = k.split('|')[0]
        if gid not in {str(g['id']) for g in games}:
            continue
        r = out[gid]['books'].setdefault(m.get('book', 'ESPN'), row())        # Action first; ESPN fills its gaps
        e = [num(v[0]), fmt_am(v[1]), fmt_am(v[2]), fmt_am(v[3]), fmt_am(v[4]), num(v[5]), fmt_am(v[6]), fmt_am(v[7])]
        for i, x in enumerate(e):
            if r[i] is None:
                r[i] = x
        r[9] = max([x for x in (r[9], W('espn', k)) if x is not None] or [None])
    # Pinnacle: main lines (the spread / total pair priced closest to even), moneyline
    pin = defaultdict(lambda: defaultdict(dict))
    for k, v in (last.get('pinnacle') or {}).items():
        m = meta.get('pinnacle', {}).get(k)
        if not m or m.get('parent') or m.get('period') != 0 or m.get('type') not in ('total', 'spread', 'moneyline'):
            continue
        home = next((n for a_, n in m.get('teams') or [] if a_ == 'home'), None)
        g = gkey.get((et_day(m['start']), nicks.get(nick(home))))
        side = str(m.get('side')).lower()
        if g:                     # one key per line from the home side: home -2 / away +2 pair, never home +2
            pt = num(v[0])
            pin[str(g['id'])][(m['type'], -pt if side == 'away' and pt is not None else pt)][side] = (v, k)
    for gid, mk in pin.items():
        r = row()
        best = lambda typ, a, b: min(((key, s) for key, s in mk.items() if key[0] == typ and a in s and b in s),
                                     key=lambda x: abs(am_prob(x[1][a][0][1]) - am_prob(x[1][b][0][1])), default=None)
        sp, to = best('spread', 'home', 'away'), best('total', 'over', 'under')
        ml = next((s for key, s in mk.items() if key[0] == 'moneyline' and 'home' in s and 'away' in s), None)
        ks = []
        if sp:
            r[0], r[1], r[2] = num(sp[1]['home'][0][0]), fmt_am(sp[1]['home'][0][1]), fmt_am(sp[1]['away'][0][1])
            ks += [sp[1]['home'][1], sp[1]['away'][1]]
        if ml:
            r[3], r[4] = fmt_am(ml['home'][0][1]), fmt_am(ml['away'][0][1])
            ks += [ml['home'][1], ml['away'][1]]
        if to:
            r[5], r[6], r[7] = num(to[1]['over'][0][0]), fmt_am(to[1]['over'][0][1]), fmt_am(to[1]['under'][0][1])
            ks += [to[1]['over'][1], to[1]['under'][1]]
        r[9] = W('pinnacle', *ks)
        out[gid]['books']['Pinnacle'] = r
    # Kalshi: winner, and the spread / total ladders turned into the line they imply
    lad = defaultdict(lambda: {'win': [], 'margin': [], 'total': []})
    for k, v in (last.get('kalshi') or {}).items():
        m = meta.get('kalshi', {}).get(k) or {}
        if m.get('series') not in ('KXNBAGAME', 'KXNBASPREAD', 'KXNBATOTAL') or not tight(v):
            continue
        g = next((gkey[(d, TEAM.get(h, h))] for d, a_, h in parse_event(m['event']) or [] if (d, TEAM.get(h, h)) in gkey), None)
        if not g:
            continue
        mid, L = (v[0] + v[1]) / 2, lad[str(g['id'])]
        code = re.sub(r'\d+$', '', k.rsplit('-', 1)[-1])
        team = TEAM.get(code, code)
        if m['series'] == 'KXNBAGAME':
            if team in (g['home'], g['away']):
                L['win'].append(mid if team == g['home'] else 1 - mid)
        elif m['series'] == 'KXNBASPREAD' and m.get('floor') is not None:
            f = float(m['floor'])
            L['margin'].append((f, mid) if team == g['home'] else (-f, 1 - mid))      # P(home margin > x)
        elif m['series'] == 'KXNBATOTAL' and m.get('floor') is not None:
            L['total'].append((float(m['floor']), mid))
    for gid, L in lad.items():
        mm = _median_cross(L['margin'])
        out[gid]['kalshi'] = {'win': round(sum(L['win']) / len(L['win']), 4) if L['win'] else None,
                              'spread': -mm if mm is not None else None, 'total': _median_cross(L['total'])}
    # Polymarket: moneyline and total (first outcome's price; the slug is nba-<away>-<home>-date)
    for k, v in (last.get('polymarket') or {}).items():
        m = meta.get('polymarket', {}).get(k) or {}
        if m.get('type') not in ('moneyline', 'totals') or not tight(v):
            continue
        p = (m.get('event') or '').split('-')
        if len(p) < 6:
            continue
        home = TEAM.get(p[2].upper(), p[2].upper())
        g = gkey.get(('-'.join(p[3:6]), home))
        if not g:
            continue
        mid = (v[0] + v[1]) / 2
        try:
            first = json.loads(m.get('outcomes') or '[]')[0]
        except (ValueError, IndexError):
            continue
        po = out[str(g['id'])]['poly']
        if m['type'] == 'moneyline':
            po['win'] = round(mid if nick(first) == nicks_rev(g, 'home') else 1 - mid, 4)
        elif str(first).lower() == 'over' and m.get('line') is not None:
            po['total'], po['over'] = float(m['line']), round(mid, 4)
    return {gid: dict(o, books=[[b] + r for b, r in o['books'].items()]) for gid, o in out.items()}


def nicks_rev(g, side):
    return nick(g.get(side + '_name'))


def tight(v, width=0.10):
    """A two-sided quote worth reading as a probability: both sides, at most 10 cents wide. Thin preseason markets
    sit at 13c / 87c placeholders, whose midpoint (50%) says nothing."""
    return v and v[0] is not None and v[1] is not None and 0 < v[0] <= v[1] < 1 and v[1] - v[0] <= width + 1e-9


def am_prob(x):
    x = num(x)
    return 0.5 if x is None or x == 0 else (100 / (x + 100) if x > 0 else -x / (-x + 100))


def injury_wire(wire, qk, R, games, nicks):
    """Today's injury and lineup changes for teams on the board, each with how fast every venue moved that team's
    player props afterwards: [t, kind, team, pid, who, before, after, {venue: [quotes, moved, median s, first s]}].
    kind: 'inj' (injury report status change), 'five' (NBA.com starting five confirmed), 'inactive'. Times are when
    the recorder first saw the change (polls every 5 to 15 minutes); a move is any change to a quote after that and
    before the team's next tip, including the book pulling it, so other news can move a quote too. Each event ends
    with [.., game id, tip]."""
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
        # the news matters for the team's next game: only that game's quotes, only moves before its tip (the recorder
        # removes a game's quotes at tip, which is not a reaction)
        nxt_g = min((g for g in games if e[2] in (g['away'], g['home']) and g['tip'] > e[0]), key=lambda g: g['tip'], default=None)
        if not nxt_g:
            continue
        react = {}
        for venue, src, key in qk.get((e[2], str(nxt_g['id'])), []):
            r = react.setdefault(venue, [0, 0, []])
            r[0] += 1
            nxt = [x for x in hist.get(src, {}).get(key, []) if e[0] < x < nxt_g['tip']]
            if nxt:
                r[1] += 1
                r[2].append(min(nxt) - e[0])
        out.append(e + [{v: [n, m, sorted(l)[len(l) // 2] if l else None, min(l) if l else None] for v, (n, m, l) in react.items()},
                        str(nxt_g['id']), nxt_g['tip']])
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
