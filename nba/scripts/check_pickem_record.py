#!/usr/bin/env python3
"""Check for pickem_record.record: lock at the day's first tip, a withdrawn leg is left out, one player per team, settle rules. Run: python3 nba/scripts/check_pickem_record.py"""
import os, sys, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pickem_record as PR

t1, t2 = 1000000, 1003600
def leg(gid, pid, team, stat, line, over, p, tip):
    return (f'{gid}|{pid}|{stat}|Underdog|{line}', {'kind': 'leg', 'game': gid, 'tip': tip, 'pid': pid, 'player': f'P{pid}', 'team': team, 'stat': stat, 'app': 'Underdog'},
            [(tip - 5000, [line, over, p, .5]), (tip - 100, [line, over, p, .5])])
src = {k: {'meta': m, 'series': s} for k, m, s in [leg('g1', 1, 'A', 'pts', 20.5, 1, .6, t1), leg('g1', 2, 'B', 'reb', 5.5, 0, .58, t1), leg('g2', 3, 'C', 'ast', 4.5, 1, .55, t2),
                                                    leg('g2', 4, 'D', 'pts', 10.5, 1, .7, t2), leg('g2', 5, 'D', 'reb', 3.5, 1, .9, t2)]}
k, m, s = leg('g2', 6, 'C', 'pts', 9.5, 1, .95, t2)
src[k] = {'meta': m, 'series': s + [(t1 - 50, None)]}                   # withdrawn before the lock: never in a slip
box = {'g1': {1: {'points': 25}, 2: {'rebounds': 7}}, 'g2': {3: {'assists': 5}, 4: {'points': 12}, 5: {'rebounds': 2}}}
L = types.SimpleNamespace(tip_day=lambda t: 'd', load_src=lambda r, s, since: src, box=lambda r, g: box[g], SETTLE_AFTER_S=0,
                          STAT_COL={'pts': ['points'], 'reb': ['rebounds'], 'ast': ['assists']})
out = PR.record('x', t2 + 10, None, 3, None, L)['d']['slips']
two = next(s for s in out if s['n'] == 2)
assert [l[0] for l in two['legs']] == [5, 1], two['legs']               # best by chance, player 4 skipped (team D already used), withdrawn leg 6 absent
assert two['res'] == 'lost' and two['pl'] == -1 and abs(two['joint'] - .54) < 1e-9
assert not PR.record('x', t1 - 10, None, 3, None, L), 'a day is not scored before its first tip'
assert not any(s['n'] > 4 for s in out), 'only four different teams exist'
print('ok')
