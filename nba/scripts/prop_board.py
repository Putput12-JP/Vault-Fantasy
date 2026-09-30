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
  {t, games: [{id, day, tip, away, home, season_type}], players: {pid: [name, team, injury status]},
   props: [{p, s, g, kal: [[line, bid, ask, open_mid]], books: [[book, line, over, under, open_line, open_over]]}],
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


def build(games, last, meta, first, proj, now):
    """games: pre-tip slate games; last/meta/first: {src: {key: value}} current rows, their metadata and the
    first value seen today."""
    R = Roster(proj)
    gkey = {(g['day'], g['home']): g for g in games}
    nicks = {}
    for g in games:
        for side in ('away', 'home'):
            if g.get(side + '_name'):
                nicks[nick(g[side + '_name'])] = g[side]
    by_id = {str(g['id']): g for g in games}
    props, players, unmapped = {}, {}, defaultdict(int)

    def entry(pid, stat, g):
        name, team = R.info[pid]
        players[pid] = [name, team, None]
        return props.setdefault((pid, stat), {'p': pid, 's': stat, 'g': g['id'], 'kal': [], 'books': []})

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
        entry(pid, stat, g)['kal'].append([m['floor'], v[0], v[1], om])

    # ESPN (DraftKings): rebuild the backfill's row shape so prop_markets() assigns over/under the audited way
    per_game = defaultdict(list)
    for k, v in (last.get('espn') or {}).items():
        m = meta.get('espn', {}).get(k)
        if not m or k.endswith('|game'):
            continue
        per_game[str(m['game'])].append({'type': m['type'], 'athlete_id': m['athlete_id'], 'provider_id': int(k.split('|')[1]),
                                         'open_line': m['open_line'], 'open_px': m['open_px'], 'ord': m['ord'],
                                         'cur_line': v[0], 'cur_px': v[1], 'last_updated': None, '_book': m['book']})
    for gid, rows in per_game.items():
        g = by_id.get(gid)
        book = {r['provider_id']: r['_book'] for r in rows}
        for mk in prop_markets({'props': rows}):
            pid = mk['athlete_id']
            if mk['market'] not in PRICED:
                continue
            if not g or pid not in R.info or mk['kind'] != 'main':
                unmapped['espn'] += mk['kind'] == 'main'
                continue
            entry(pid, mk['market'], g)['books'].append(
                [book.get(mk['provider_id'], 'ESPN'), mk['cur_line'], mk['over_cur'], mk['under_cur'], mk['line'], mk['over_open']])

    # Pinnacle: "Jalen Brunson (Points)" specials with Over / Under sides
    pin = defaultdict(dict)
    for k, v in (last.get('pinnacle') or {}).items():
        m = meta.get('pinnacle', {}).get(k)
        if not m or not m.get('parent') or m.get('side') not in ('Over', 'Under'):
            continue
        pin[m['matchup']][m['side']] = (v, m, (first.get('pinnacle') or {}).get(k))
    for mid, sides in pin.items():
        if 'Over' not in sides or 'Under' not in sides:
            continue
        (ov, m, fo), (uv, _, _) = sides['Over'], sides['Under']
        mt = re.match(r'^(.*?)\s*\((.*)\)\s*$', m.get('desc') or '')
        home = next((n for a, n in m.get('teams') or [] if a == 'home'), None)
        g = gkey.get((dt.datetime.fromtimestamp(m['start'], ET).date().isoformat(), nicks.get(nick(home))))
        stat = mt and pin_stat(mt.group(2))
        pid = g and stat and R.find(mt.group(1), (g['away'], g['home']))
        if not pid:
            unmapped['pinnacle'] += 1
            continue
        entry(pid, stat, g)['books'].append(['Pinnacle', ov[0], fmt_am(ov[1]), fmt_am(uv[1]),
                                              fo[0] if fo else None, fmt_am(fo[1]) if fo else None])

    # injury report: current status per player on tonight's teams
    inj = {}
    for k, v in (last.get('injuries') or {}).items():
        _, team, player = k.split('|', 2)
        pid = R.find(player, [g[s] for g in games for s in ('away', 'home') if nick(team) == nick(g.get(s + '_name'))])
        if pid:
            inj[pid] = v[0]
    for pid in players:
        players[pid][2] = inj.get(pid)

    for e in props.values():
        e['kal'].sort()
    return {'t': now, 'games': [{k: g[k] for k in ('id', 'day', 'tip', 'away', 'home', 'season_type')} for g in games],
            'players': players, 'props': sorted(props.values(), key=lambda e: (e['g'], e['p'], e['s'])), 'unmapped': dict(unmapped)}


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
    props, players = {}, {}

    def entry(pid, stat, r):
        players[pid] = [R.info[pid][0], r['team'], None]   # the team he played for that night
        return props.setdefault((pid, stat), {'p': pid, 's': stat, 'g': gid, 'kal': [], 'books': []})
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
    for e in props.values():
        e['kal'].sort()
    return {'t': tip - 1800, 'example': True, 'games': [g], 'players': players,
            'props': sorted(props.values(), key=lambda e: (e['p'], e['s'])), 'unmapped': {}}


def main():
    root = os.path.abspath(os.path.join(HERE, '..', '..'))
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    subprocess.run(['git', '-C', root, 'fetch', '-q', 'origin', 'nba-live'], check=False)
    p = subprocess.run(['git', '-C', root, 'show', 'origin/nba-live:board.json'], capture_output=True, text=True)
    live = json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
    out = {'live': live, 'example': example(proj), 'repo': 'Putput12-JP/Vault-Fantasy', 'branch': 'nba-live'}
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
