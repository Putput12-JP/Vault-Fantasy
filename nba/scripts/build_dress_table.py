#!/usr/bin/env python3
"""P(a projected rotation candidate dresses | his projected minutes), from the as-of candidates of the v2 walk.
Why: team_min (264.9) is the total for players who dress, so the candidate list carries about 1.3 players per team who will
not. The Game Simulation used to shrink everyone's minutes and stats by one factor (240 / sum); starters then read about 9%
low. With this table the simulation drops likely non-dressers instead. docs/leakage-audit-2026-10-06.md, addendum 13.
Fit on the FIT season (2024-25), checked on 2025-26, written to data/dress_table.json.   python3 nba/scripts/build_dress_table.py"""
import os, sys, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C, build_prop_model_v2 as V2
import build_prop_model as V1
BINS = [0, 5, 10, 15, 20, 25, 30, 35, 60]
def main():
    box = C.player_games(V2.SEASONS); inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = V2.MM.expected_margins(box); mm = json.load(open(V2.MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    dress = []
    V2.walk(box, inj, margins, mm, casc, V2.team_min(), C.closing_lines(), dress=dress)
    def table(season):
        out = []
        for lo, hi in zip(BINS, BINS[1:]):
            xs = [p for s, m, p in dress if s == season and lo <= m < hi]
            out.append((lo, hi, len(xs), sum(xs) / len(xs) if xs else None))
        return out
    fit, test = table(V2.FIT), table(V2.TEST)
    print('proj min   fit 2024-25 (n, P)      test 2025-26 (n, P)')
    for a, b in zip(fit, test): print(f'{a[0]:3d}-{a[1]:<3d}   {a[2]:6d} {a[3]:.3f}          {b[2]:6d} {b[3]:.3f}')
    # per team-game: sum of projected minutes x P(dress) over the candidates, vs 240 (test season)
    P = lambda m: next(p for lo, hi, n, p in fit if lo <= m < hi)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'fit_season': V2.FIT, 'team_min': V2.team_min(),
           'bins': [[hi, round(p, 4)] for lo, hi, n, p in fit], 'test': [[hi, round(p, 4), n] for lo, hi, n, p in test],
           'note': 'bins: [upper bound of projected minutes, P(dress)]; a candidate with projected minutes m uses the first bin with m < upper'}
    json.dump(res, open(os.path.join(C.HERE, '..', 'data', 'dress_table.json'), 'w'), indent=1)
    print('wrote data/dress_table.json')
if __name__ == '__main__': main()
