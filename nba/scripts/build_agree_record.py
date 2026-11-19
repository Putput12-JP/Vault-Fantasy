#!/usr/bin/env python3
"""Agree-count record for the NBA Game Lines signal board ("4 of 5 signals point to POR").

The page's board is a live read and is not stored. The five signals it shows each have a stored alert log
(snapshots/<day>/signals.json on the nba-data branch), so this rebuilds the agree count from those alerts:

  Pinnacle -> steam    Sharp accts -> sharp    Kalshi big -> whale (venue Kalshi)    Novig -> novig    Money -> split

Rule (written before the first read, context only, never a bet signal):
  - Only moneyline and spread alerts name a team. Totals are left out.
  - A signal's direction at time t is the team with more weight in that signal's alerts so far (weight = dollars when the
    alert stores them, else 1). A tie is no direction.
  - An agree event at level k is the first moment at least k signals point to the same team and none point to the other.
    Levels 3, 4 and 5 are nested, so a 5 is also a 4 and a 3. A game gets one event per level, before tip.
  - Graded on the final score (did the team win) against Pinnacle's closing no-vig moneyline for that team, and on
    closing-line value: closing fair minus the team's fair at the event, from the latest stored moneyline alert fair.
  - Not stored, so not invented: an event with no moneyline alert in the 2 hours before it has no CLV, and an event with no closing moneyline is left out of the graded count.

Differences from the page: the page reads cumulative state at a +-0.06 cut and these are alert thresholds, so a game the
page called 4 of 5 may be 3 here. This is the closest the stored data allows.

usage: build_agree_record.py <nba-data root> <out json>
"""
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import sharp  # noqa: E402

SIG = {'steam': 'Pinnacle', 'sharp': 'Sharp accts', 'whale': 'Kalshi big', 'novig': 'Novig', 'split': 'Money'}
LEVELS = (3, 4, 5)


def team_of(a):
    return a['home'] if a['side'] == 'home' else a['away']


def load_alerts(root):
    alerts = {}
    for f in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'signals.json'))):
        try:
            alerts.update(json.load(open(f)))
        except ValueError:
            pass
    return alerts


def usable(a):
    if a['type'] not in SIG or a.get('m') not in ('ml', 'sp') or a.get('side') not in ('home', 'away'):
        return False
    return a['type'] != 'whale' or a.get('venue') == 'Kalshi'


def events(alerts):
    """{game: {level: {t, team, sigs}}} first moment each level is reached before tip."""
    by = {}
    for a in alerts:
        if usable(a) and a['t'] < a['tip']:
            by.setdefault(a['g'], []).append(a)
    out = {}
    for g, rows in by.items():
        rows.sort(key=lambda a: (a['t'], a['id']))
        w = {s: {} for s in SIG}                              # signal -> team -> weight
        got = {}
        for a in rows:
            d = w[a['type']]
            d[team_of(a)] = d.get(team_of(a), 0) + (a.get('usd') or 1)
            dirs = {}
            for s, d in w.items():
                if d:
                    top = sorted(d.items(), key=lambda kv: -kv[1])
                    if len(top) == 1 or top[0][1] > top[1][1]:
                        dirs[s] = top[0][0]
            teams = set(dirs.values())
            if len(teams) != 1:
                continue
            n, team = len(dirs), next(iter(teams))
            for k in LEVELS:
                if n >= k and k not in got:
                    got[k] = {'t': a['t'], 'team': team, 'sigs': sorted(SIG[s] for s in dirs), 'home': a['home'], 'away': a['away'], 'tip': a['tip'], 'tday': a['tday']}
        if got:
            out[g] = got
    return out


FAIR_MAX_AGE_S = 2 * 3600       # an older moneyline alert is too stale to stand for the fair at the event: left out of CLV, never guessed


def event_fair(rows, team, t):
    """The team's moneyline fair at the event: the latest stored ml alert fair at or before it, no older than FAIR_MAX_AGE_S."""
    best = None
    for a in rows:
        if a.get('m') == 'ml' and a.get('fair') is not None and t - FAIR_MAX_AGE_S <= a['t'] <= t and a['side'] in ('home', 'away') and (best is None or a['t'] >= best[0]):
            best = (a['t'], a['fair'] if team_of(a) == team else 1 - a['fair'])
    return None if best is None else best[1]


def build(root):
    alerts = load_alerts(root)
    ev = events(alerts.values())
    rows = {}
    for a in alerts.values():
        rows.setdefault(a['g'], []).append(a)
    closes, res = {}, {}
    rec = {k: {'events': 0, 'graded': 0, 'wins': 0, 'exp': 0.0, 'clv_n': 0, 'clv_sum': 0.0, 'clv_pos': 0, 'sq': 0.0} for k in LEVELS}
    log = []
    for g, got in ev.items():
        any_ev = next(iter(got.values()))
        day = any_ev['tday']
        if day not in closes:
            p = os.path.join(root, 'snapshots', day, 'pinclose.json')
            closes[day] = json.load(open(p)) if os.path.exists(p) else {}
        c = closes[day].get(g)
        mp = os.path.join(root, 'results', f'{g}.meta.json')
        score = json.load(open(mp)).get('score') if os.path.exists(mp) else None
        for k, e in sorted(got.items()):
            r = rec[k]
            r['events'] += 1
            side = 'home' if e['team'] == e['home'] else 'away'
            cf = sharp.fair(sharp._lad(c['lad']), 'ml', side) if c and c.get('lad') and c['lad'].get('ml') else None
            h, w = (score or {}).get(e['home']), (score or {}).get(e['away'])
            won = None if h is None or w is None or h == w else (h > w) == (side == 'home')
            ef = event_fair(rows[g], e['team'], e['t'])
            clv = None if cf is None or ef is None else cf - ef
            if cf is not None and won is not None:
                r['graded'] += 1
                r['wins'] += won
                r['exp'] += cf
            if clv is not None:
                r['clv_n'] += 1
                r['clv_sum'] += clv
                r['sq'] += clv * clv
                r['clv_pos'] += clv > 0
            if k == 3 or len(e['sigs']) == k:
                log.append({'g': g, 'level': k, 't': e['t'], 'team': e['team'], 'game': f"{e['away']} @ {e['home']}", 'sigs': e['sigs'], 'close': sharp.r3(cf), 'fair': sharp.r3(ef), 'won': won, 'tday': day})
    out = {}
    for k, r in rec.items():
        g, n = r['graded'], r['clv_n']
        m = r['clv_sum'] / n if n else None
        se = math.sqrt(max(r['sq'] / n - m * m, 0) / n) if n > 1 else None
        wr = r['wins'] / g if g else None
        ex = r['exp'] / g if g else None
        out[str(k)] = {'events': r['events'], 'graded': g, 'wins': r['wins'], 'losses': g - r['wins'],
                       'win_pct': sharp.r3(wr), 'expected_pct': sharp.r3(ex), 'edge_pts': sharp.r3(None if wr is None else wr - ex),
                       'clv_n': n, 'clv_pts': sharp.r3(m), 'clv_se': sharp.r3(se), 'beat_close': sharp.r3(r['clv_pos'] / n if n else None)}
    days = sorted({a['tday'] for a in alerts.values()})
    return {'rule': 'docs/agree-record.md', 'levels': out, 'from': days[0] if days else None, 'through': days[-1] if days else None,
            'signals': SIG, 'recent': sorted(log, key=lambda x: -x['t'])[:60]}


if __name__ == '__main__':
    d = build(sys.argv[1])
    json.dump(d, open(sys.argv[2], 'w'), separators=(',', ':'))
    for k, v in d['levels'].items():
        print(k, v)
