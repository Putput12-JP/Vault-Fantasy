#!/usr/bin/env python3
"""
Prop correlation audit, step 1: dump the v2 model's pregame over-probabilities for every settled ESPN main-line prop leg.

READ-ONLY with respect to the model: it imports build_prop_model_v2 and replays the front of its main() unchanged (same walk,
same stacker, same variance fit, same calibration on the 2024-25 open lines) and writes one row per leg instead of a summary.
Nothing in data/ or on the page is touched.

  python3 nba/scripts/prop_corr_extract.py OUT.json

  season 2025 rows = 2024-25 opening lines (the model was FIT on this season: in-sample)
  season 2026 rows = 2025-26 pre-tip closing lines (the model never saw them: out-of-sample)
"""
import csv, json, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as V1
import build_prop_model_v2 as V2
from build_prop_model import MARKETS, am_prob, pav, apply_cal


def main(out):
    box = C.player_games(V2.SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    team_min = json.load(open(V1.OUT_JSON))['team_min']
    lines = C.closing_lines()
    recs, ctx = V2.walk(box, inj, margins, mm, casc, team_min, lines)
    fit0 = [r for r in recs if r['season'] == V2.FIT and r['pm'] > 0]
    ratio = sum(r['min'] for r in fit0) / sum(r['pm'] for r in fit0)
    if abs(ratio - 1) > 0.003:
        team_min = round(team_min * ratio, 1)
        recs, ctx = V2.walk(box, inj, margins, mm, casc, team_min, lines)
    fit = [r for r in recs if r['season'] == V2.FIT]
    stk = V2.fit_stacker(fit)
    mf = lambda r: V2.mu2(r, stk)
    V = V2.fit_var(fit, mf, True)
    by = {(r['gid'], r['aid']): r for r in recs}

    legs = []
    for row in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if row['kind'] != 'main' or row['played'] != '1' or row['market'] not in MARKETS:
            continue
        r = by.get((int(row['game_id']), int(row['athlete_id'])))
        if not r:
            continue
        act = float(row['actual'])
        for clock, line, opx, upx in (('open', row['line_open'], row['over_px_open'], row['under_px_open']),
                                      ('close', row['line_cur'], row['over_px_cur'], row['under_px_cur'])):
            if clock == 'close' and row['cur_is_pretip'] != '1':
                continue
            if (row['season'], clock) not in (('2025', 'open'), ('2026', 'close')):
                continue
            po, pu = am_prob(opx), am_prob(upx)
            if not line or po is None or pu is None or not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
                continue
            L = float(line)
            if act == L:
                continue
            legs.append({'season': int(row['season']), 'clock': clock, 'gid': int(row['game_id']), 'aid': int(row['athlete_id']),
                         'team': r['team'], 'mkt': row['market'], 'L': L, 'pk': po / (po + pu), 'over': 1 if act > L else 0,
                         'mu': mf(r)[row['market']], 'min': r['min'], 'pmin': r['pm'], 'sdm': r['sdm'], 'st': r['st'],
                         'spread': r['spread'], 'pos': r['pos'], 'na': r['na'], 'mv': r['mv'],
                         'ex': (V2.minrate(r, row['market']) * r['sdm']) ** 2, 'act': act})
    cal = {}
    for mkt in MARKETS:
        pts = [(V2.p_over(mkt, l['mu'], l['L'], V, l['ex']), l['over']) for l in legs if l['mkt'] == mkt and l['season'] == 2025]
        cal[mkt] = pav(pts)
    for l in legs:
        l['pm'] = apply_cal(cal[l['mkt']], V2.p_over(l['mkt'], l['mu'], l['L'], V, l['ex']))
        l['pm_raw'] = V2.p_over(l['mkt'], l['mu'], l['L'], V, l['ex'])
    json.dump(legs, open(out, 'w'))
    print(len(legs), 'legs ->', out)


if __name__ == '__main__':
    main(sys.argv[1])
