#!/usr/bin/env python3
"""
Forward record for the steals and turnovers matchup term (docs/matchup-extras-wiring.md). The extra markets are priced only in the page and Python never projects them, so nothing else
records their projections against results. This does, for steals and turnovers only:

  log(board, now)  -> (rows, meta) for Day.record('xstat', ...), called by snapshot.py after each poll, games within TRACK_H of tip.
                      One row per player-game-stat, key  gid|pid|stat:  [minutes, mu0, mt]
                        minutes  tonight's projected minutes (the minutes model, pricing.game_minutes)
                        mu0      minutes x the player's Minutes Lab rate for the stat: the projection WITHOUT the matchup term
                        mt       the matchup term on it (stat units; 0 when the term is off)
  record(root, now, prev, rescan_days, games, L)  settles each final game from the box score and writes <root>/xstats/<tip ET day>.json:
                      {'day', 'cols': COLS, 'games': {gid: [matchup, tip]}, 'rows': [[pid, player, team, stat, minutes, mu0, mt, actual]]}
                      The LAST row before tip is the one scored. A player who did not play is void (not written, counted in the day's 'void').
  Returns {day: {'n': rows written, 'void': voided}} merged over prev.
The forward read (nba/scripts/score_xstat_forward.py) takes gain = |actual - mu0| - |actual - (mu0 + mt)|. Nothing here changes a price.
"""
import json as _json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

TRACK_H = 24
STATS = ('stl', 'tov')
BOXCOL = {'stl': 'steals', 'tov': 'turnovers'}
COLS = ['pid', 'player', 'team', 'stat', 'min', 'mu0', 'mt', 'actual']


def log(board, now):
    rows, meta = {}, {}
    if not board or not board.get('games'):
        return rows, meta
    import pricing as PX
    pr = PX.Pricer(example=bool(board.get('example')))
    if not pr.MM:
        return rows, meta
    status, outs, cache = PX.status_from_board(board), PX.outs_from_board(board), {}
    names = {p['id']: p['name'] for T in pr.D['teams'].values() for p in T['players']}
    names.update({int(k): v[0] for k, v in (board.get('players') or {}).items() if v})
    for g in board['games']:
        if not (now < g['tip'] <= now + TRACK_H * 3600) or g.get('season_type') == 1:
            continue
        for team in (g['away'], g['home']):
            try:
                gm = pr.game_minutes(team, g, status, cache)
            except Exception as ex:
                PX.row_error(f"xstat minutes {g['id']}|{team}", ex)
                continue
            for pid in gm:
                for s in STATS:
                    try:
                        x = pr.mu_extra(int(pid), s, g, cache, outs, team, status)
                        if not x:
                            continue
                        k = f"{g['id']}|{pid}|{s}"
                        rows[k] = [round(x['min'], 1), round(x['mu0'], 4), round(x['mt'], 4)]
                        meta[k] = {'game': str(g['id']), 'tip': g['tip'], 'matchup': f"{g['away']} @ {g['home']}", 'pid': int(pid), 'player': names.get(int(pid), str(pid)),
                                   'team': team, 'stat': s, 'kind': 'xstat'}
                    except Exception as ex:                                  # one player's failure never stops the recorder
                        PX.row_error(f"xstat {g['id']}|{pid}|{s}", ex)
    return rows, meta


def record(root, now, prev, rescan_days, games, L):
    out = dict(prev or {})
    since = L.tip_day(now - rescan_days * 86400)
    days = {}
    void = {}
    for k, x in L.load_src(root, 'xstat', since).items():
        m = x['meta']
        pre = [v for t, v in sorted(x['series'], key=lambda z: (z[0], z[1] is None)) if v is not None and m and t < m['tip']]
        if not m or not pre or L.tip_day(m['tip']) < since or now < m['tip'] + L.SETTLE_AFTER_S or (games and not games(str(m['game']))):
            continue
        bx = L.box(root, m['game'])
        if bx is None:
            continue
        day = L.tip_day(m['tip'])
        st = bx.get(int(m['pid']))
        actual = (st or {}).get(BOXCOL[m['stat']])
        if not st or (st.get('minutes') or 0) <= 0 or actual is None:
            void[day] = void.get(day, 0) + 1
            continue
        d = days.setdefault(day, {'games': {}, 'rows': []})
        d['games'][str(m['game'])] = [m['matchup'], m['tip']]
        v = pre[-1]
        d['rows'].append([int(m['pid']), m['player'], m['team'], m['stat'], v[0], v[1], v[2], actual])
    os.makedirs(os.path.join(root, 'xstats'), exist_ok=True)
    for day, d in days.items():
        d['rows'].sort(key=lambda r: (r[3], r[0]))
        with open(os.path.join(root, 'xstats', f'{day}.json'), 'w') as f:
            _json.dump({'day': day, 'cols': COLS, 'games': d['games'], 'rows': d['rows']}, f, separators=(',', ':'))
        out[day] = {'n': len(d['rows']), 'void': void.get(day, 0)}
    return out
