#!/usr/bin/env python3
"""
data/game_ctx.json: each team's final score and pre-game spread for every game, so the prop detail chart can filter a player's
game log by result (won / lost, blowout / close finish) and by the line (favoured / underdog). The page fetches it on the
detail view only, so it adds nothing to the first load.

  {"t": <written>, "cols": ["pts", "opp", "spread"],
   "g": {"<team>": {"<day>": [team points, opponent points, team spread or null]}}}

  day      days since 1970-01-01, the game's US Eastern date (the same key as gamelogs.json rows)
  spread   that team's closing spread, negative = favoured. Stored numbers only, never filled in:
             past seasons   raw/tables/game_lines.csv (build_backtest_tables.py): DraftKings close, else ESPN BET
             this season    data/game_picks.json: the `close` clock (last DraftKings line the recorder saw before tip)

raw/ is local only, so CI cannot rebuild past seasons: when game_lines.csv is missing the past seasons already in
game_ctx.json are kept as they are, and only this season is rebuilt from game_picks.json.

  python3 nba/scripts/build_game_ctx.py            # also run by build_data_health.py after build_game_picks
"""
import csv, datetime as dt, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import nba_common as C

DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'game_ctx.json')
LINES = os.path.join(HERE, '..', 'raw', 'tables', 'game_lines.csv')
EPOCH = dt.date(1970, 1, 1)
PREF = {'DraftKings': 0, 'ESPN BET': 1}


def dnum(day_iso):
    return (dt.date.fromisoformat(day_iso[:10]) - EPOCH).days


def put(g, home, away, day, hs, as_, spread):
    """Both teams' rows for one game. spread is the HOME spread (negative = home favoured) or None."""
    g.setdefault(home, {})[str(day)] = [hs, as_, spread]
    g.setdefault(away, {})[str(day)] = [as_, hs, -spread if spread is not None else None]


def past(g):
    """Past seasons from game_lines.csv, one book per game (DraftKings first). -> number of games, or None without the file."""
    if not os.path.exists(LINES):
        return None
    try:                                                    # only seasons the game logs reach (they keep a player's last 100 games)
        first = min(r[1] for rows in json.load(open(os.path.join(DATA, 'gamelogs.json')))['players'].values() for r in rows)
    except (OSError, ValueError, KeyError):
        first = 0
    best = {}
    for r in csv.DictReader(open(LINES)):
        if int(r['season']) < first or not r['home_score'] or not r['away_score']:
            continue
        cur = best.get(r['game_id'])
        rank = PREF.get(r['book'], 9) if r['spread_close'] else 10
        if cur is None or rank < cur[0]:
            best[r['game_id']] = (rank, r)
    for rank, r in best.values():
        day = (C.et(C.utc(r['tip'])).date() - EPOCH).days
        sp = float(r['spread_close']) if rank < 9 else None
        put(g, r['home'], r['away'], day, int(float(r['home_score'])), int(float(r['away_score'])), sp)
    return len(best)


def current(g):
    """This season from game_picks.json: final scores from its games, the home spread from the `close` row. -> number of games."""
    gp = json.load(open(os.path.join(DATA, 'game_picks.json')))
    cols = gp['cols']; ci, si = cols.index('clock'), cols.index('spread')
    n = 0
    for day, v in gp.get('days', {}).items():
        close = {r[0]: r[si] for r in v.get('rows', []) if r[ci] == 'c'}
        for gid, m in v.get('games', {}).items():
            _, _, away, home, as_, hs = m[:6]
            if as_ is None or hs is None:
                continue                                    # not final yet
            sp = close.get(gid)
            put(g, home, away, dnum(day), int(hs), int(as_), float(sp) if sp is not None else None)
            n += 1
    return n


def first_day_current():
    gp = json.load(open(os.path.join(DATA, 'game_picks.json')))
    return dnum(min(gp['days'])) if gp.get('days') else None


def build():
    g = {}
    np = past(g)
    if np is None:                                          # CI: keep the past seasons we already have
        try:
            old = json.load(open(OUT)).get('g', {})
        except (OSError, ValueError):
            old = {}
        cut = first_day_current()
        for team, days in old.items():
            for d, row in days.items():
                if cut is None or int(d) < cut:
                    g.setdefault(team, {})[d] = row
    nc = current(g)
    return g, np, nc


def write():
    g, np, nc = build()
    if not g:
        return None
    try:
        old = json.load(open(OUT)).get('g')
    except (OSError, ValueError):
        old = None
    if g != old:
        tmp = OUT + '.tmp'
        json.dump({'t': int(time.time()), 'cols': ['pts', 'opp', 'spread'], 'g': g}, open(tmp, 'w'), separators=(',', ':'))
        os.replace(tmp, OUT)
    return np, nc, sum(len(v) for v in g.values())


if __name__ == '__main__':
    print('past games %s, this season %s, team rows %s' % write())
