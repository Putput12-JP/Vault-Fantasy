#!/usr/bin/env python3
"""
Current state of prop model v2 for the page: what the stacker's features read, as of the last final game.

Walks every game from WARM_FROM through today with exactly the updates build_prop_model_v2.py uses
(update_after), then exports, for the teams and rostered players:
  teams    pace and scoring (EWMA), last game time (back-to-backs), defense factor by position group x stat
  players  minutes volatility, shooting-built points and 3PM per minute, season-to-date sums
Also a snapshot taken just before the example board's game (data/prop_board.json), so the example is priced
with only what was known that morning.

  python3 nba/scripts/build_model_state.py
Writes data/model_state.json. Needs raw/hoopr for the seasons walked (fetch_hoopr.py).
"""
import copy, datetime as dt, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model_v2 as V2
import build_prop_model as V1
import build_minutes_model_v3 as M3
import build_game_model as GM
from build_prop_model import BASE

DATA = os.path.join(C.HERE, '..', 'data')
WARM = 2          # seasons of history before the current one
keep_roster = set()
names = {}        # athlete id -> name, from the box scores walked (players off the current rosters need one too)


def export(ctx, rt, ms, keep, season, base=False, asof=None, m3=None):
    teams = {}
    for t in set(ctx.pace) | set(ctx.pts):
        teams[t] = {'pace': round(ctx.pace.get(t, 0), 3), 'pts': round(ctx.pts.get(t, 0), 3),
                    'last': int(ctx.last[t].timestamp()) if t in ctx.last else None,
                    'def': {pos: {s: round(ctx.opp_factor(t, pos, s), 4) for s in BASE} for pos in ('G', 'F', 'C')}}
    players = {}
    # the minutes model's rotation reaches back ROT_DAYS: players off the roster who played for a team recently count
    if asof is not None:
        recent = {a for a, p in ms.pl.items() if p['last'] >= asof - dt.timedelta(days=MM.ROT_DAYS + 3)}
        if m3:
            recent |= {a for a, p in m3.pl.items() if p['last'] >= asof - dt.timedelta(days=MM.ROT_DAYS + 3)}
        keep = set(keep) | recent
    for aid in keep:
        sr = ctx.struct_rates(aid)
        z = ctx.szn.get(aid)
        players[aid] = {'sdm': round((ctx.vol.get(aid, 36.0)) ** 0.5, 3),
                        # example only: minutes (EWMA) and rates that morning, the example's base (live uses the Minutes Lab)
                        'min': round(ms.pl[aid]['m'], 1) if base and aid in ms.pl else None,
                        'rate': {s: round(rt[aid]['rate'][s], 5) for s in BASE} if base and aid in rt else None,
                        'sr': [round(sr[0], 5), round(sr[1], 5)] if sr else None,
                        'szn': {'season': z['season'], 'M': round(z['M'], 1), 'S': {s: round(z['S'][s], 1) for s in BASE}} if z and z['M'] else None,
                        # the backtest's own minutes and rate state (tonight's minutes are computed from these, as in
                        # build_prop_model_v2.walk): [EWMA minutes, start rate, position group, team, last game, games]
                        'ms': [ms.pl[aid]['m'], ms.pl[aid]['st'], ms.pl[aid]['pos'], ms.pl[aid]['team'], int(ms.pl[aid]['last'].timestamp()),
                               ms.pl[aid]['n']] if aid in ms.pl else None,
                        'r': dict(rt[aid]['rate']) if aid in rt else None, 'pg': dict(rt[aid]['pg']) if aid in rt else None,
                        'nm': names.get(aid),
                        # minutes model v3's state (shadow): [EWMA minutes, start rate, position, team, last game,
                        # minutes as a starter, minutes off the bench, started last game, team game index, games since return]
                        'm3': m3_row(m3.pl[aid]) if m3 and aid in m3.pl else None}
        if players[aid]['ms'] is None and players[aid]['m3'] is None and aid not in keep_roster:
            players.pop(aid)
    return {'season': season, 'lg_pace': round(ctx.lg_pace or 0, 3), 'teams': teams, 'players': players,
            'team_last': {t: int(v.timestamp()) for t, v in ms.team_last.items()},
            'm3_games': dict(m3.tg) if m3 else None}


def m3_row(p):
    return [p['m'], p['st'], p['pos'], p['team'], int(p['last'].timestamp()), p.get('ms'), p.get('mb'), p.get('st_last'),
            p.get('idx'), p.get('since')]


def game_state(box, seasons, cur):
    """The game model (build_game_model.py, context only: it does not beat the closing line) as of today, for the
    Slate page's Vault line: team ratings carried into the new season, home edge, league base, each player's value
    for the availability adjustment, and how often each injury status actually sits."""
    gm = json.load(open(GM.OUT_JSON))
    m, _ = GM.run(gm['params'], seasons, box)
    if m.season is not None and cur != m.season:              # the season-start carry the backtest applies
        m.new_season(cur)
    rates = gm.get('status_play_rates') or {}
    tune = gm.get('tune_mae') or [10.53, 14.61]               # as backtest_game_vs_kalshi.py: Normal sigma from the tune MAE
    lim = max(m.team_last.values()) - dt.timedelta(days=60) if m.team_last else None
    return {'R': {t: round(v, 3) for t, v in m.R.items()}, 'O': {t: round(v, 3) for t, v in m.O.items()},
            'D': {t: round(v, 3) for t, v in m.D.items()}, 'base': round(m.base, 3), 'hfa': round(m.hfa, 3),
            'P': {k: gm['params'][k] for k in ('C', 'CT', 'B2B', 'REP', 'ROT_MIN', 'ROT_DAYS')},
            'p_out': {'Out': 1.0, **{s: round(1 - r, 4) for s, r in rates.items()}},
            'players': {str(a): [round(p['gs'], 3), round(p['mpg'], 2), p['team'], int(p['last'].timestamp())]
                        for a, p in m.pl.items() if p['mpg'] >= gm['params']['ROT_MIN'] and (lim is None or p['last'] >= lim)},
            'team_last': {t: int(v.timestamp()) for t, v in m.team_last.items()},
            'sd_margin': round(tune[0] * (3.14159265 / 2) ** 0.5, 2), 'sd_total': round(tune[1] * (3.14159265 / 2) ** 0.5, 2),
            'season': cur}


def main():
    proj = json.load(open(os.path.join(DATA, 'player_projections.json')))
    cur = int(proj['season'][:4]) + 1
    seasons = [s for s in range(cur - WARM, cur + 1) if os.path.exists(os.path.join(C.RAW, 'hoopr', f'player_box_{s}.csv'))]
    keep = {p['id'] for t in proj['teams'].values() for p in t['players']}
    global keep_roster
    keep_roster = keep
    ex_gid = None
    pb = os.path.join(DATA, 'prop_board.json')
    if os.path.exists(pb):
        ex = (json.load(open(pb)).get('example') or {}).get('games') or []
        ex_gid = int(ex[0]['id']) if ex else None
    box = C.player_games(seasons)
    ms, ctx, rt = MM.State(json.load(open(MM.OUT_JSON))['alpha']), V2.Context(), {}
    mv3 = json.load(open(os.path.join(DATA, 'minutes_model_v3.json')))
    m3 = M3.State(mv3['alpha'], mv3['a_new'], mv3['new_n'])
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    example, last_day, n = None, None, 0
    for g in C.games(seasons):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['game_id'] == ex_gid:
            example = export(ctx, rt, ms, keep, g['season'], base=True, asof=g['tip'], m3=m3)
            example['asof'] = g['tip_et'].strftime('%Y-%m-%d')
        V2.update_after(g, rows, rt, prior, ms, ctx)
        m3.update(g, rows)
        names.update({r['athlete_id']: r['name'] for r in rows if r.get('name')})
        last_day, n = g['tip_et'].strftime('%Y-%m-%d'), n + 1
    live = export(ctx, rt, ms, keep, cur, asof=max(ms.team_last.values()) if ms.team_last else None, m3=m3)
    live['asof'] = last_day
    game = game_state(box, seasons, cur)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(DATA, 'usage_cascade.json')))['stats']
    pv3 = json.load(open(os.path.join(DATA, 'minutes_v3_pricing.json')))
    out = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'seasons': seasons,
           'games': n, 'live': live, 'example': example, 'game': game,
           # minutes model v2 as the backtest ran it: weights in MM.FEATURES order, team total, rotation rule, usage cascade
           'minutes': {'features': MM.FEATURES, 'beta': [mm['beta'][f] for f in MM.FEATURES],
                       'team_min': json.load(open(V1.OUT_JSON))['team_min'], 'rot_min': MM.ROT_MIN, 'rot_days': MM.ROT_DAYS,
                       'cascade': {s: {'use': c['use'], 'beta': c['beta']} for s, c in casc.items() if s in BASE}},
           # minutes model v3 as the shadow (docs/minutes-v3-pricing.md): weights without and with confirmed starters,
           # each fitted team total from that test, the return-from-absence rule
           'minutes_v3': {'features': M3.FEATURES, 'beta': [mv3['beta'][f] for f in M3.FEATURES],
                          'beta_starters': [mv3['beta_hindsight_starters'][f] for f in M3.FEATURES],
                          'team_min': pv3['team_min_m3'], 'team_min_starters': pv3['team_min_m3s'],
                          'return_missed': M3.RETURN_MISSED, 'rot_min': MM.ROT_MIN, 'rot_days': MM.ROT_DAYS}}
    path = os.path.join(DATA, 'model_state.json')
    json.dump(out, open(path, 'w'), separators=(',', ':'))
    print(f"walked {n:,} games {seasons}; state through {last_day}; example snapshot "
          f"{'as of ' + example['asof'] if example else 'none'} -> data/model_state.json ({os.path.getsize(path) // 1000} KB)")


if __name__ == '__main__':
    main()
