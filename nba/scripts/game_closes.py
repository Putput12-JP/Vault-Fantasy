#!/usr/bin/env python3
"""
Closing spreads for the game model's line-taught ratings (build_game_model option L, docs/game-model-round5-results.md).

The ratings move toward each finished game's closing spread as well as its final, so the daily state build needs every walked game's
closing spread. data/game_closes.json holds them: {'games': {game id: home spread at the close}}.

  history      2024-25 and 2025-26, the closing spread the backtest used (raw/tables/game_lines.csv: DraftKings, else ESPN BET). Written
               once with --seed on a machine that has raw/tables; raw/ is not in the repo.
  this season  the Game Picks record's last look before tip (DraftKings first, game_pick_record.BOOK_ORDER), from the nba-data branch's
               gpicks/ folder and the rebuilt first days (data/game_picks_backfill.json). Added by load() each run and kept, so a later
               season still has them.

  load()  -> {int game id: {'spread_close': x}}, the shape build_game_model.run reads. A game with no closing spread is simply absent and
             updates from its final alone, as the backtest does for a game with no line.

  python3 nba/scripts/game_closes.py            # refresh from the record, print the counts
  python3 nba/scripts/game_closes.py --seed     # also (re)write the two history seasons from raw/tables/game_lines.csv
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'game_closes.json')


def _read():
    if os.path.exists(OUT):
        try:
            return {str(k): float(v) for k, v in (json.load(open(OUT)).get('games') or {}).items()}
        except (OSError, ValueError):
            return {}
    return {}


def _write(games):
    json.dump({'what': 'home spread at the close per game id; see scripts/game_closes.py', 'games': dict(sorted(games.items()))},
              open(OUT, 'w'), separators=(',', ':'))


def from_record(fetch=True):
    """{game id: closing home spread} from the Game Picks record: the close-clock row of every settled game, live rows over rebuilt ones."""
    import subprocess
    import build_game_picks as BG
    import game_pick_record as G
    bf = os.path.join(DATA, 'game_picks_backfill.json')
    b = json.load(open(bf)) if os.path.exists(bf) else {}
    if b and b.get('cols') != G.COLS:
        b = {}
    if fetch:
        subprocess.run(['git', '-C', BG.ROOT, 'fetch', '-q', 'origin', 'nba-data'], check=False)
    days = BG.merge(BG.live_days(), b.get('days'))
    snap = os.path.join(DATA, 'game_picks.json')                # the last snapshot, so a failed fetch still has yesterday's record
    if os.path.exists(snap):
        s = json.load(open(snap))
        if s.get('cols') == G.COLS:
            days = BG.merge(days, {d: v for d, v in s['days'].items() if d not in days})
    i, out = {c: G.COLS.index(c) for c in ('game', 'clock', 'spread')}, {}
    for d in days.values():
        for r in d['rows']:
            if r[i['clock']] == 'c' and r[i['spread']] is not None:
                out[str(r[i['game']])] = float(r[i['spread']])
    return out


def load(fetch=True, save=True):
    games = _read()
    n0 = len(games)
    try:
        games.update(from_record(fetch))
    except Exception as ex:                                     # the state build must not fail on the record: last night's games then learn from their finals alone
        print(f'game closes: record not read ({ex}); using the {n0} stored')
    if save and len(games) != n0:
        _write(games)
    print(f'game closes: {len(games)} games ({len(games) - n0} new)')
    return {int(k): {'spread_close': v} for k, v in games.items()}


def seed(seasons=(2025, 2026)):
    import nba_common as C
    lines, games = C.closing_lines(), _read()
    ids = {g['game_id'] for g in C.games(list(seasons))}
    n = 0
    for gid in ids:
        ln = lines.get(gid)
        if ln and ln.get('spread_close') is not None:
            games[str(gid)] = float(ln['spread_close'])
            n += 1
    _write(games)
    print(f'game closes: seeded {n} games from raw/tables/game_lines.csv for seasons {list(seasons)}')


if __name__ == '__main__':
    if '--seed' in sys.argv:
        seed()
    load()
