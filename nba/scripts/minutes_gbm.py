#!/usr/bin/env python3
"""
Minutes GBM: shared state, features and scorer (stdlib only). One definition used by the training walk
(build_minutes_gbm.py), the daily state job (build_model_state.py) and live pricing (pricing.py), so the model sees
the same numbers everywhere. Background: docs/reverse-engineering-targets.md items 8-10.

State per player (exported as a list, order = PLAYER_FIELDS):
  ew1, ew2, ew3   minutes EWMAs at 0.1 / 0.2 / 0.4 (learning rate floored at 1/(n+1) while the sample is thin)
  lastm, last_start, st, n   last game's minutes and role, starter-rate EWMA, games
  h               last five games' minutes
  team, last (unix), pos
State per team: the last 12 game tip times (unix).

features() is a pure function of that state plus tonight's context, in COLS order. The model file data/minutes_gbm.json
holds 300 trees (scripts/export_minutes_gbm.py proves a match with LightGBM to 1e-11).
"""
import json, math, os
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, '..', 'data', 'minutes_gbm.json')
ALPHAS = (0.1, 0.2, 0.4)
ROT_MIN, ROT_DAYS = 10.0, 21
COLS = ['ew1', 'ew2', 'ew3', 'last', 'm5', 'st', 'was_start', 'rest', 'g7', 'home', 'days_off', 'vs', 'vo', 'absm', 'b2b',
        'pos_g', 'pos_c', 'sd5', 'n', 'sgnm', 'n_out']
PLAYER_FIELDS = ['ew1', 'ew2', 'ew3', 'lastm', 'last_start', 'st', 'n', 'h', 'team', 'last', 'pos']
DAY = 86400.0


def new_player(minutes, starter, team, tip, pos):
    return {'ew': [minutes] * 3, 'n': 1, 'team': team, 'last': tip, 'pos': pos, 'st': 1.0 if starter else 0.0,
            'lastm': minutes, 'last_start': 1.0 if starter else 0.0, 'h': deque([minutes], maxlen=5)}


def update_player(p, minutes, starter, team, tip, pos):
    p['ew'] = [e + max(al, 1 / (p['n'] + 1)) * (minutes - e) for e, al in zip(p['ew'], ALPHAS)]
    p['st'] += max(0.2, 1 / (p['n'] + 1)) * ((1.0 if starter else 0.0) - p['st'])
    p['lastm'], p['last_start'] = minutes, 1.0 if starter else 0.0
    p['h'].append(minutes)
    p['n'] += 1
    p['team'], p['last'], p['pos'] = team, tip, pos


def export_player(p):
    """List for model_state.json (tip as unix seconds). NOT rounded: a rounded EWMA can flip a split threshold and move a projection by half a minute."""
    return [p['ew'][0], p['ew'][1], p['ew'][2], p['lastm'], p['last_start'], p['st'],
            p['n'], list(p['h']), p['team'], int(p['last']), p['pos']]


def from_export(row):
    return {'ew': [row[0], row[1], row[2]], 'lastm': row[3], 'last_start': row[4], 'st': row[5], 'n': row[6], 'h': list(row[7]),
            'team': row[8], 'last': row[9], 'pos': row[10]}


def team_context(tips, tip):
    """(b2b, games in last 7 days, rest days) from a team's recent tip times (unix seconds), as the training walk computes them."""
    last = tips[-1] if tips else None
    b2b = 1.0 if last is not None and tip - last < 30 * 3600 else 0.0
    g7 = sum(1 for t in tips if tip - t < 7 * DAY)
    rest = min(10.0, (tip - last) / DAY) if last is not None else 5.0
    return b2b, g7, rest


def rotation(players, team, tip):
    """{aid: player} on `team` with a 10+ minute EWMA (ew2) who played within ROT_DAYS of `tip`."""
    lim = tip - ROT_DAYS * DAY
    return {a: p for a, p in players.items() if p['team'] == team and p['ew'][1] >= ROT_MIN and p['last'] >= lim}


def features(p, aid, rot, out, tip, ctx, home, margin, grp):
    """Feature vector in COLS order. rot: rotation(); out: set of rotation ids ruled out; ctx: team_context();
    margin: expected HOME margin (positive = home favoured) or None; grp: 'G' / 'F' / 'C'."""
    b2b, g7, rest = ctx
    vs = sum(q['ew'][1] for a, q in rot.items() if a in out and a != aid and q['pos'] == grp)
    vo = sum(q['ew'][1] for a, q in rot.items() if a in out and a != aid and q['pos'] != grp)
    h = list(p['h'])
    m5 = sum(h) / len(h)
    sd5 = math.sqrt(sum((x - m5) ** 2 for x in h) / len(h))
    return [p['ew'][0], p['ew'][1], p['ew'][2], p['lastm'], m5, p['st'], p['last_start'], rest, g7, home,
            min(60.0, (tip - p['last']) / DAY), vs, vo, abs(margin) if margin is not None else 6.0, b2b,
            1.0 if grp == 'G' else 0.0, 1.0 if grp == 'C' else 0.0, sd5, min(p['n'], 200),
            (margin if home else -margin) if margin is not None else 0.0, len(out)]


_MODEL = None


def load_model(path=MODEL_PATH):
    global _MODEL
    if _MODEL is None and os.path.exists(path):
        _MODEL = json.load(open(path))
        assert _MODEL['features'] == COLS, 'minutes_gbm.json was exported with different features'
    return _MODEL


def predict(x, model=None):
    model = model or load_model()
    if not model:
        return None
    s = 0.0
    for tr in model['trees']:
        i = 0
        f, t, l, r = tr['f'], tr['t'], tr['l'], tr['r']
        while f[i] >= 0:
            i = l[i] if x[f[i]] <= t[i] else r[i]
        s += tr['v'][i]
    return s


class Walk:
    """Chronological state for the daily job: feed every game's rows through update(); export() gives the live state."""

    def __init__(self):
        self.pl, self.team_tips = {}, {}

    def update(self, g, rows, group):
        tip = g['tip'].timestamp()
        for r in rows:
            if not r['played']:
                continue
            a, pos = r['athlete_id'], group(r['pos'])
            p = self.pl.get(a)
            if p is None:
                self.pl[a] = new_player(r['minutes'], r['starter'], r['team'], tip, pos)
            else:
                update_player(p, r['minutes'], r['starter'], r['team'], tip, pos)
        for t in (g['home'], g['away']):
            tips = self.team_tips.setdefault(t, [])
            tips.append(tip)
            del tips[:-12]

    def export(self, asof, keep_days=300, keep=()):  # offseason: everyone's last game is months old, and the state must carry over
        lim = asof - keep_days * DAY                 # keep: current roster ids, never dropped (a star who missed a whole season is still on it)
        return {'players': {str(a): export_player(p) for a, p in self.pl.items() if p['last'] >= lim or a in keep},
                'team_tips': {t: [int(x) for x in v] for t, v in self.team_tips.items()}}
