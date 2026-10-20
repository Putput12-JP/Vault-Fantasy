#!/usr/bin/env python3
"""
Rebuild who was on the floor, and what each player and team did while there, from ESPN plays
(raw/preseason/<season>/<game>.json, written by fetch_preseason.py).

process_game(g) -> (player_rows, team_rows, check)
  player_rows: one dict per player in the box: minutes and counting stats for the first half ('h1_') and the whole
               game ('g_'), the same counts for his TEAM while he was on the floor ('t1_' first half, for usage and
               assist share), plus the box score line for validation.
  team_rows:   one dict per team: first-half and whole-game points, possessions, shot mix (threes, pull-ups,
               assisted makes) for team-level reads.
  check:       whole-game rebuilt minutes vs box minutes (the validation gate in docs/preseason-signals-test.md).

Starters come from the box score; substitutions carry the lineup. Quarters are 12 minutes, overtimes 5.
"""
from collections import defaultdict


def secs(clock):
    if clock is None:
        return None
    if ':' in clock:
        m, s = clock.split(':')
        return int(m) * 60 + float(s)
    return float(clock)


def period_start(per):
    return (per - 1) * 720 if per <= 4 else 2880 + (per - 5) * 300


def period_len(per):
    return 720 if per <= 4 else 300


COUNT = ['fga', 'fgm', 'fg3a', 'fg3m', 'fta', 'ftm', 'tov', 'ast', 'reb', 'oreb', 'pts', 'stl', 'blk', 'pullup',
         'ast_made']


def new_counts():
    return {k: 0.0 for k in COUNT}


def classify(p):
    """Return a list of (athlete_slot, stat, amount) for one play. athlete_slot indexes p['ath'] (None = team)."""
    t = p['type'] or ''
    text = (p['text'] or '')
    out = []
    if t.startswith('Free Throw'):
        out.append((0, 'fta', 1))
        if p['score']:
            out += [(0, 'ftm', 1), (0, 'pts', 1)]
    elif p['shoot'] and t not in ('Substitution',):
        is3 = p.get('pts_att') == 3 or 'three point' in text.lower()
        out.append((0, 'fga', 1))
        if is3:
            out.append((0, 'fg3a', 1))
        if 'pullup' in t.lower():
            out.append((0, 'pullup', 1))
        if p['score']:
            v = p.get('val') or (3 if is3 else 2)
            out += [(0, 'fgm', 1), (0, 'pts', v)]
            if is3:
                out.append((0, 'fg3m', 1))
            if len(p['ath']) > 1:
                out.append((1, 'ast', 1))
                out.append((0, 'ast_made', 1))
        elif len(p['ath']) > 1 and 'block' in text.lower():
            out.append((1, 'blk', 1))
    elif t.endswith('Rebound'):
        out.append((0, 'reb', 1))
        if t.startswith('Offensive'):
            out.append((0, 'oreb', 1))
    elif t.endswith('Turnover') or t in ('Traveling', 'Offensive Charge'):
        out.append((0, 'tov', 1))
        if len(p['ath']) > 1 and 'steal' in text.lower():
            out.append((1, 'stl', 1))
    return out


def process_game(g):
    box = g['box']
    team_of = {b['id']: b['team'] for b in box}
    teams = sorted({b['team'] for b in box})
    on = {t: {b['id'] for b in box if b['team'] == t and b['starter']} for t in teams}
    starters_ok = all(len(on[t]) == 5 for t in teams)

    mins = defaultdict(lambda: [0.0, 0.0])                    # pid -> [first half s, whole game s]
    pc = defaultdict(lambda: {'h1': new_counts(), 'g': new_counts()})        # player's own counts
    tc = defaultdict(lambda: {'h1': new_counts(), 'g': new_counts()})        # team counts while he is on the floor
    tm = {t: {'h1': new_counts(), 'g': new_counts()} for t in teams}         # team totals
    tm_allowed = {t: {'h1': new_counts(), 'g': new_counts()} for t in teams}
    anomalies = 0
    last_t = 0.0

    plays = sorted(g['plays'], key=lambda p: int(p['seq']) if p['seq'] is not None else 0)
    for p in plays:
        per = p['per']
        rem = secs(p['clock'])
        if per is None or rem is None:
            continue
        t_abs = period_start(per) + (period_len(per) - rem)
        t_abs = max(t_abs, last_t)
        dt = t_abs - last_t
        if dt > 0:
            # time between events: credit the minutes to the period the span belongs to
            for tt in teams:
                for pid in on[tt]:
                    mins[pid][1] += dt
                    if t_abs <= 1440:
                        mins[pid][0] += dt
                    elif last_t < 1440:
                        mins[pid][0] += 1440 - last_t
            last_t = t_abs
        ty = p['type'] or ''
        if ty == 'Substitution':
            if len(p['ath']) >= 2:
                tid = p['team'] or team_of.get(p['ath'][0])
                pin, pout = p['ath'][0], p['ath'][1]
                if tid in on:
                    if pout not in on[tid]:
                        anomalies += 1
                    on[tid].discard(pout)
                    on[tid].add(pin)
                    team_of.setdefault(pin, tid)
            continue
        half = 'h1' if per <= 2 else None
        evs = classify(p)
        if not evs:
            continue
        ptid = p['team']
        for slot, stat, amt in evs:
            if slot >= len(p['ath']):
                continue
            pid = p['ath'][slot]
            tid = team_of.get(pid) or ptid
            if tid not in on:
                continue
            keys = ['g'] + ([half] if half else [])
            for k in keys:
                pc[pid][k][stat] += amt
            # team totals and what the team did while each teammate was on the floor
            if stat in ('fga', 'fg3a', 'fta', 'ftm', 'tov', 'ast', 'reb', 'oreb', 'pts', 'fgm', 'fg3m', 'pullup',
                        'ast_made'):
                for k in keys:
                    tm[tid][k][stat] += amt
                    other = [x for x in teams if x != tid]
                    if other:
                        tm_allowed[other[0]][k][stat] += amt
                    for mate in on[tid]:
                        tc[mate][k][stat] += amt
        # team-attributed plays with no athlete (team turnover, team rebound)
        if not p['ath'] and p['team'] in on:
            if ty.endswith('Turnover') or ty in ('Traveling', 'Offensive Charge'):
                keys = ['g'] + ([half] if half else [])
                for k in keys:
                    tm[p['team']][k]['tov'] += 1
                    other = [x for x in teams if x != p['team']]
                    if other:
                        tm_allowed[other[0]][k]['tov'] += 1
                    for mate in on[p['team']]:
                        tc[mate][k]['tov'] += 1

    prow = []
    errs = []
    for b in box:
        pid = b['id']
        st = b['stats']
        try:
            bm = float(st.get('minutes') or 0)
        except ValueError:
            bm = 0.0
        m1, mg = mins[pid][0] / 60, mins[pid][1] / 60
        if bm > 0 or mg > 0:
            errs.append(abs(mg - bm))
        r = {'game_id': g['id'], 'season': g['season'], 'date': g['date'][:10], 'team': b['team'], 'pid': pid,
             'name': b['name'], 'starter': b['starter'], 'box_min': bm, 'h1_min': m1, 'g_min': mg}
        for k in COUNT:
            r['h1_' + k] = pc[pid]['h1'][k]
            r['g_' + k] = pc[pid]['g'][k]
            r['t1_' + k] = tc[pid]['h1'][k]
        for k, bk in (('pts', 'points'), ('reb', 'rebounds'), ('ast', 'assists'), ('tov', 'turnovers'),
                      ('stl', 'steals'), ('blk', 'blocks')):
            try:
                r['box_' + k] = float(st.get(bk))
            except (TypeError, ValueError):
                r['box_' + k] = None
        for k, bk in (('fg', 'fieldGoalsMade-fieldGoalsAttempted'), ('fg3', 'threePointFieldGoalsMade-threePointFieldGoalsAttempted'),
                      ('ft', 'freeThrowsMade-freeThrowsAttempted')):
            v = st.get(bk)
            try:
                mk, at = v.split('-')
                r['box_' + k + 'm'], r['box_' + k + 'a'] = float(mk), float(at)
            except (AttributeError, ValueError):
                r['box_' + k + 'm'] = r['box_' + k + 'a'] = None
        prow.append(r)

    trow = []
    for t in teams:
        opp = [x for x in teams if x != t][0]
        r = {'game_id': g['id'], 'season': g['season'], 'date': g['date'][:10], 'team': t}
        for k in ('h1', 'g'):
            for s in COUNT:
                r[f'{k}_{s}'] = tm[t][k][s]
                r[f'{k}_opp_{s}'] = tm_allowed[t][k][s]
        trow.append(r)
    check = {'game_id': g['id'], 'season': g['season'], 'starters_ok': starters_ok, 'anomalies': anomalies,
             'n_err': len(errs), 'mae': sum(errs) / max(len(errs), 1), 'max_err': max(errs) if errs else 0}
    return prow, trow, check
