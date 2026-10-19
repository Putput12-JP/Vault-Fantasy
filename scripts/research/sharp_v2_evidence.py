#!/usr/bin/env python3
"""Evidence for Sharp Money V2: what the stored Top Reads picks and the prop board calls actually did.

Reads the live ledger from the sharp-data branch (data.json = graded bet-signal picks, prop_plays.json = graded prop calls), or from --data / --plays.
Every slice is scored by the same rule as docs/signal-research.md (scripts/research/common.py): chronological split by kickoff (first 60% train, last 40%
held out), a slice earns a place only if it clears the admission rule on the held-out rows. Nothing here estimates a price. ROI uses a stored price,
CLV uses a stored closing value.

It also audits the prop CLV: the stored CLV is closeFair / calledPrice - 1, where closeFair comes from the SAME fair source that made the call, so it
repeats the call's own edge. The audit splits CLV into (edge claimed at the call) + (drift of the fair after the call) and checks the close
against what happened.

usage: sharp_v2_evidence.py [--data data.json] [--plays prop_plays.json] [--out docs/sharp-v2-evidence.json]"""
import argparse, collections, json, math, os, subprocess
from common import ROOT, stats, verdict

ap = argparse.ArgumentParser()
ap.add_argument('--data'); ap.add_argument('--plays')
ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'sharp-v2-evidence.json'))
a = ap.parse_args()


def branch_file(name):
    return json.loads(subprocess.run(['git', '-C', ROOT, 'show', 'origin/sharp-data:' + name], capture_output=True, check=True).stdout)


D = json.load(open(a.data)) if a.data else branch_file('data.json')
PP = json.load(open(a.plays)) if a.plays else branch_file('prop_plays.json')
r3 = lambda x: None if x is None else round(x, 3)


def am_prob(am):
    """American price -> the cost of one unit of win probability (stored price only; None if there is no price)."""
    if am is None: return None
    return -am / (-am + 100) if am < 0 else 100 / (am + 100)


def split(rows):
    rows = sorted(rows, key=lambda r: r['start'])
    if len(rows) < 5: return rows, []
    c = rows[int(len(rows) * 0.6)]['start']
    return [r for r in rows if r['start'] < c], [r for r in rows if r['start'] >= c]


def pack(rows, min_n=100):
    """All rows, then train / held-out and the admission verdict on the held-out rows."""
    tr, te = split(rows)
    allr, t, h = stats(rows), stats(tr), stats(te)
    v, why = verdict(h, min_n)
    return dict(all=allr, train=t, held_out=h, verdict=v, reasons=why)


def by(rows, key, min_n=1):
    g = collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    return {str(k): pack(v) for k, v in sorted(g.items(), key=lambda x: str(x[0])) if len(v) >= min_n}


# ---------- 1. Top Reads picks ----------
picks = []
for p in D['picks']:
    if p.get('result') not in (1, -1, 0): continue
    picks.append(dict(res=p['result'], fair=p.get('fair'), px=am_prob(p.get('price')), clv=p.get('clv'), start=p['start'], sport=p['sport'], m=p['m'],
                      kinds=sorted(p.get('kinds') or []), nk=len(p.get('kinds') or []), conflict=bool(p.get('conflict')), model=p.get('model'),
                      key=(p['game'], p['m'], p['side'])))
top = dict(
    n_graded=len(picks),
    overall=pack(picks),
    by_signal_count=by(picks, lambda r: r['nk']),
    by_kinds=by(picks, lambda r: '+'.join(r['kinds'])),
    by_conflict=by(picks, lambda r: 'both sides flagged' if r['conflict'] else 'one side'),
    by_sport=by(picks, lambda r: r['sport']),
    by_market=by(picks, lambda r: r['m']),
    by_sport_market=by(picks, lambda r: r['sport'] + ':' + r['m']),
)
# Stored units (flat 1u at the stored price) exist on only part of the picks, and a few long-shot winners can carry the total.
priced = [p for p in D['picks'] if p.get('result') in (1, -1, 0) and p.get('units') is not None]
wins = sorted([p['units'] for p in priced if p['units'] > 0], reverse=True)
tot_u = sum(p['units'] for p in priced)
top['units_concentration'] = dict(
    graded=len(picks), priced=len(priced), total_units=r3(tot_u), top1_win_units=r3(wins[0]) if wins else None,
    top5_win_units=r3(sum(wins[:5])), units_without_top5=r3(tot_u - sum(wins[:5])), units_without_top10=r3(tot_u - sum(wins[:10])),
    priced_by_kind={k: [sum(1 for p in priced if '+'.join(sorted(p['kinds'])) == k), sum(1 for p in D['picks'] if p.get('result') in (1, -1, 0) and '+'.join(sorted(p['kinds'])) == k)]
                    for k in sorted({'+'.join(sorted(p['kinds'])) for p in D['picks']})})
# the dropped sharp-only reads, for the record: context only, never a pick
sc = [dict(res=p['result'], fair=p.get('fair'), px=am_prob(p.get('price')), clv=p.get('clv'), start=p['start']) for p in D.get('sharpContext', []) if p.get('result') in (1, -1, 0)]
top['sharp_only_context'] = pack(sc) if sc else None
nogo = [r for r in picks if not r['conflict']]
top['without_contradictions'] = pack(nogo)

# ---------- 2. Prop board calls ----------
plays = [p for p in PP['plays'].values() if p.get('status') in ('won', 'lost', 'push')]
rows = []
for p in plays:
    c = p['called']
    rows.append(dict(res=1 if p['status'] == 'won' else -1 if p['status'] == 'lost' else 0, fair=c.get('fair'), px=c.get('p'), clv=p.get('clv'), start=p['start'],
                     ev=c.get('ev'), kind=c.get('kind'), src=c.get('src'), fair_src=c.get('fairSrc'), mkt=p['label'], side=p['side'], shifted=bool(p.get('shifted')),
                     big=bool(p.get('big')), lead_h=(p['start'] - p['firstSeen']) / 3600, close=p.get('closeFair'), pos=p.get('pos')))
ev_b = lambda e: '<5%' if e < .05 else '5-10%' if e < .10 else '10-15%' if e < .15 else '15%+'
ld_b = lambda h: '<2h' if h < 2 else '2-12h' if h < 12 else '12-48h' if h < 48 else '48h+'
props = dict(
    n_graded=len(rows),
    overall=pack(rows),
    by_displayed_ev=by(rows, lambda r: ev_b(r['ev'])),
    by_hours_before_kickoff=by(rows, lambda r: ld_b(r['lead_h'])),
    by_price_kind=by(rows, lambda r: r['kind']),
    by_fair_source=by(rows, lambda r: r['fair_src']),
    by_called_source=by(rows, lambda r: r['src']),
    by_market=by(rows, lambda r: r['mkt']),
    by_market_side=by(rows, lambda r: r['mkt'] + ' ' + r['side']),
    by_position=by(rows, lambda r: r['pos']),
    by_shifted_line=by(rows, lambda r: 'moved line' if r['shifted'] else 'same line'),
    by_big_edge=by(rows, lambda r: 'big (10%+)' if r['big'] else 'normal'),
)

# ---------- 3. Prop CLV audit ----------
au = [r for r in rows if r['res'] != 0 and r['close'] is not None and r['fair'] is not None and r['px']]
mean = lambda xs: sum(xs) / len(xs)
n = len(au)
hit = mean([1 if r['res'] > 0 else 0 for r in au])
edge_at_call = mean([r['fair'] / r['px'] - 1 for r in au])                  # what the call claimed
clv = mean([r['close'] / r['px'] - 1 for r in au])                           # what the tracker stores as CLV
drift = mean([r['close'] - r['fair'] for r in au])                           # fair after the call minus fair at the call, probability points
mclose = mean([r['close'] for r in au]); mpx = mean([r['px'] for r in au]); mfair = mean([r['fair'] for r in au])
var = sum(r['close'] * (1 - r['close']) for r in au)
z_close = (sum(1 for r in au if r['res'] > 0) - sum(r['close'] for r in au)) / math.sqrt(var)
brier = lambda f: mean([(f(r) - (1 if r['res'] > 0 else 0)) ** 2 for r in au])
cal = collections.defaultdict(list)
for r in au: cal[min(int(r['close'] * 20) / 20, 0.65)].append(r)
audit = dict(
    n=n, hit=r3(hit), mean_price=r3(mpx), mean_fair_at_call=r3(mfair), mean_close_fair=r3(mclose),
    edge_claimed_at_call=r3(edge_at_call), stored_clv=r3(clv), fair_drift_prob_pts=r3(drift * 100), clv_minus_edge=r3(clv - edge_at_call),
    hit_minus_close_fair_pts=r3((hit - mclose) * 100), z_hit_vs_close_fair=r3(z_close),
    brier_close_fair=r3(brier(lambda r: r['close'])), brier_price=r3(brier(lambda r: r['px'])), brier_coin=0.25,
    share_clv_positive=r3(mean([1 if r['close'] > r['px'] else 0 for r in au])),
    calibration=[dict(close_fair_from=r3(k), n=len(v), mean_close_fair=r3(mean([x['close'] for x in v])), hit=r3(mean([1 if x['res'] > 0 else 0 for x in v]))) for k, v in sorted(cal.items())],
    reading=('Stored CLV is closeFair / price - 1 and closeFair is the same fair source that raised the call. If the fair does not move, CLV equals the edge the call '
             'claimed, so it cannot confirm that edge. The fair drifted against the calls, and the calls won less often than the close said they should.'),
)
out = dict(generated_from=dict(picks=len(D['picks']), prop_calls=len(PP['plays']), data_ts=D.get('ts')), top_reads=top, props=props, prop_clv_audit=audit)
os.makedirs(os.path.dirname(a.out), exist_ok=True)
json.dump(out, open(a.out, 'w'), indent=1)


def line(k, v):
    s = v['all']; h = v['held_out']
    f = lambda x, p=1: '-' if x is None else (f'{x * 100:+.{p}f}%')
    return (f"{k:<34} {s['w']:>3}-{s['l']:<3} {('%.1f%%' % (s['win'] * 100)) if s['win'] is not None else '-':>6}  roi {f(s['roi_stored_px']):>7} (n={s['roi_n']:<3}) clv {f(s['clv']):>7} (n={s['clv_n']:<3}) "
            f"held-out n={h['w'] + h['l']:<3} {v['verdict']}")


for sect, name in ((top, 'TOP READS'), (props, 'PROPS')):
    print('=====', name, sect['n_graded'])
    for k, v in sect.items():
        if k == 'n_graded': continue
        if v is None: continue
        if 'all' in v: print(line(k, v)); continue
        print('--', k)
        for kk, vv in v.items(): print('  ', line(kk, vv))
print('===== PROP CLV AUDIT'); print(json.dumps({k: v for k, v in audit.items() if k not in ('calibration', 'reading')}, indent=1))
