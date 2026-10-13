#!/usr/bin/env python3
"""Does sharp money add value in a narrower role? Chronological split (first 60% of games by kickoff = train, last 40% = held out).
Roles: (a) every first sharp alert, (b) only very large buys, (c) only very early buys, (d) tiebreaker when the bet signals tie between two sides.
Thresholds for (b) and (c) are fixed on the TRAIN rows only (top quartile) and then frozen for the held-out rows.
usage: sharp_role_backtest.py [--state state.json] [--out docs/signal-research-sharp.json]"""
import argparse, collections, json, os
from common import ROOT, load_state, stats, verdict

ap = argparse.ArgumentParser(); ap.add_argument('--state'); ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'signal-research-sharp.json'))
a = ap.parse_args()
S = load_state(a.state)
KIND = {'steam': 'line', 'split': 'money', 'behind': 'behind', 'sharp': 'sharp', 'cross': 'sharp'}
first = {}
for al in sorted(S['alerts'], key=lambda x: x.get('ts', 0)):
    k = KIND.get(al['type'])
    if not k or not al.get('m') or not al.get('side') or al.get('result') is None: continue
    key = (al['game'], al['m'], al['side'], k)
    if key in first: continue                      # first signal stands, same as the frozen ledger
    first[key] = al

def row(al):
    return dict(res=al['result'], fair=al.get('fair'), px=al.get('px') if al['type'] in ('sharp', 'cross') else None, clv=al.get('clv'),
                usd=al.get('usd') or 0, lead_h=(al['start'] - al['ts']) / 3600, start=al['start'], game=al['game'], m=al['m'], side=al['side'], sport=al.get('sport'))

sharp = [row(al) for (g, m, s, k), al in first.items() if k == 'sharp']
sharp.sort(key=lambda r: r['start'])
cut = sharp[int(len(sharp) * 0.6)]['start']
tr, te = [r for r in sharp if r['start'] < cut], [r for r in sharp if r['start'] >= cut]
q = lambda xs, p: sorted(xs)[int(len(xs) * p)]
usd_cut, early_cut = q([r['usd'] for r in tr], 0.75), q([r['lead_h'] for r in tr], 0.75)
res = dict(split_start=cut, train_alerts=len(tr), test_alerts=len(te), usd_cut=usd_cut, early_cut_hours=round(early_cut, 1), roles={})
def add(name, f):
    t, h = stats([r for r in tr if f(r)]), stats([r for r in te if f(r)])
    v, why = verdict(h)
    res['roles'][name] = dict(train=t, held_out=h, verdict=v, reasons=why)
add('all first sharp alerts', lambda r: True)
add(f'very large (usd >= {usd_cut}, train top quartile)', lambda r: r['usd'] >= usd_cut)
add(f'very early (>= {early_cut:.1f}h before kickoff, train top quartile)', lambda r: r['lead_h'] >= early_cut)
add('very large AND very early', lambda r: r['usd'] >= usd_cut and r['lead_h'] >= early_cut)
for sp in ('nfl', 'cfb', 'nba'): add(f'all, {sp}', lambda r, sp=sp: r['sport'] == sp)

# tiebreaker: both sides of one market have the same number (>=1) of bet signals; sharp backs exactly one side
bets = collections.defaultdict(lambda: collections.defaultdict(set)); shp = collections.defaultdict(set); info = {}
for (g, m, s, k), al in first.items():
    info[(g, m, s)] = al
    if k == 'sharp': shp[(g, m)].add(s)
    else: bets[(g, m)][s].add(k)
tb = []
for (g, m), sides in bets.items():
    if len(sides) != 2: continue
    ns = [len(v) for v in sides.values()]
    if ns[0] != ns[1] or len(shp.get((g, m), ())) != 1: continue
    s = next(iter(shp[(g, m)]))
    if s not in sides: continue
    tb.append(row(info[(g, m, s)]) | dict(res=info[(g, m, s)]['result']))
tb.sort(key=lambda r: r['start'])
c2 = tb[int(len(tb) * 0.6)]['start'] if tb else 0
res['tiebreaker'] = dict(cases=len(tb), train=stats([r for r in tb if r['start'] < c2]), held_out=stats([r for r in tb if r['start'] >= c2]))
v, why = verdict(res['tiebreaker']['held_out']); res['tiebreaker'].update(verdict=v, reasons=why)

# does adding sharp to a bet pick change its win rate (held out)? same game/market/side, >=1 bet signal, with vs without a sharp alert
rows = {}
for (g, m, s, k), al in first.items():
    if k != 'sharp': rows.setdefault((g, m, s), dict(kinds=set(), al=al))['kinds'].add(k)
cmp_ = {'with_sharp': [], 'without_sharp': []}
for (g, m, s), d in rows.items():
    r = row(d['al']); r['fair'] = d['al'].get('fair')
    (cmp_['with_sharp'] if (g, m, s) in {(a, b, c) for (a, b, c, kk) in first if kk == 'sharp'} else cmp_['without_sharp']).append(r)
for key in cmp_: cmp_[key] = [r for r in cmp_[key] if r['start'] >= cut]
res['bet_picks_held_out_by_sharp_presence'] = {k: stats(v) for k, v in cmp_.items()}
os.makedirs(os.path.dirname(a.out), exist_ok=True)
json.dump(res, open(a.out, 'w'), indent=1)
print(json.dumps({k: (v if k != 'roles' else {n: (d['held_out']['w'], d['held_out']['l'], d['held_out']['win'], d['held_out']['vs_fair'], d['held_out']['roi_stored_px'], d['held_out']['clv'], d['verdict']) for n, d in v.items()}) for k, v in res.items()}, indent=1, default=str))
