#!/usr/bin/env python3
"""Candidate replacements for the third bet signal, each tested on held-out games (chronological: first 60% by kickoff trains, last 40% is held out;
no threshold is tuned, the cut-offs below are fixed before looking).
  1. Pinnacle line move from the first logged number to 3h before kickoff, followed at the post-move number
  2. CFB model edge against the first posted spread (opening-line edge)
  3. Injury / rest news (data check only)
  4. Polymarket exchange price cheaper than Pinnacle fair on the moneyline
usage: candidate_signals.py [--state state.json] [--out docs/signal-research-candidates.json]"""
import argparse, collections, json, math, os
from common import ROOT, load_state, stats, verdict

ap = argparse.ArgumentParser(); ap.add_argument('--state'); ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'signal-research-candidates.json'))
a = ap.parse_args()
S = load_state(a.state)
HRS = 3 * 3600
out = {}

def split(rows, key='start'):
    rows = sorted(rows, key=lambda r: r[key])
    if len(rows) < 5: return rows, []
    c = rows[int(len(rows) * 0.6)][key]
    return [r for r in rows if r[key] < c], [r for r in rows if r[key] >= c]

def pack(rows, min_n=100):
    tr, te = split(rows)
    t, h = stats(tr), stats(te)
    v, why = verdict(h, min_n)
    return dict(train=t, held_out=h, verdict=v, reasons=why)

# 1. line move from open
mv = []
for key, g in S['games'].items():
    pin, fin, meta = g.get('pin') or [], g.get('final'), g.get('meta') or {}
    if len(pin) < 2 or not fin or not meta.get('start'): continue
    st = meta['start']; pre = [p for p in pin if p['ts'] <= st - HRS]
    if not pre or pre[0] is pin[-1]: continue
    o, t, c = pin[0], pre[-1], [p for p in pin if p['ts'] <= st][-1]
    if t['ts'] == o['ts']: continue
    if o.get('sp') is not None and t.get('sp') is not None and abs(t['sp'] - o['sp']) >= 1.0:
        home = t['sp'] < o['sp']                       # the home line got more negative: money moved the number toward home
        d = fin['home'] + t['sp'] - fin['away']; r = d if home else -d
        fair = t.get('spP') if home else (None if t.get('spP') is None else 1 - t['spP'])
        clv = (t['sp'] - c['sp']) if home else (c['sp'] - t['sp']) if c.get('sp') is not None else None
        mv.append(dict(res=1 if r > 0 else -1 if r < 0 else 0, fair=fair, px=None, clv=clv, start=st, m='sp', sport=meta.get('sport')))
    if o.get('tot') is not None and t.get('tot') is not None and abs(t['tot'] - o['tot']) >= 1.0:
        over = t['tot'] > o['tot']; d = fin['home'] + fin['away'] - t['tot']; r = d if over else -d
        clv = (c['tot'] - t['tot']) if over else (t['tot'] - c['tot']) if c.get('tot') is not None else None   # points of line value against the close
        mv.append(dict(res=1 if r > 0 else -1 if r < 0 else 0, fair=None, px=None, clv=clv, start=st, m='tot', sport=meta.get('sport')))
out['line_move_from_open'] = dict(note='first logged Pinnacle number to the last snapshot 3h+ before kickoff, move >= 1 point, follow the move at the post-move number. Open = first number we logged, not the true open.',
                                  all=pack(mv), spread_only=pack([r for r in mv if r['m'] == 'sp']))

# 2. CFB opening-line edge
cm = json.load(open(os.path.join(ROOT, 'data', 'cfb_model.json')))
oc = cm.get('open_check') or {}
gm = [g for g in oc.get('games', []) if g.get('result') in ('W', 'L', 'P')]
rows = [dict(res={'W': 1, 'L': -1, 'P': 0}[g['result']], fair=None, px=None, clv=g.get('clv'), start=g['week'] * 10 + 0, week=g['week']) for g in gm]
tr, te = split(rows, 'week')
bt = json.load(open(os.path.join(ROOT, 'data', 'cfb_model_backtest.json')))
out['cfb_open_edge'] = dict(
    note='this season, model 5+ point edge vs the first spread, graded vs the open. No stored price, so the only test is win rate against the usual -110 break-even (52.38%, an assumption) plus stored CLV in points.',
    train=stats(tr), held_out=stats(te), breakeven=0.5238,
    historical_backtest=dict(vs_open=(bt.get('opening_lines') or {}).get('vs_open'), vs_close=(bt.get('opening_lines') or {}).get('vs_close'),
                             caveat='2022-2025 combined; the model was tuned on 2022-2023, so the 2022-2023 share of this record is in-sample and cannot be split out from the stored totals.'))
h = out['cfb_open_edge']['held_out']; n = h['w'] + h['l']
zb = (h['w'] - n * 0.5238) / math.sqrt(n * 0.5238 * 0.4762) if n else None
out['cfb_open_edge']['z_vs_breakeven'] = None if zb is None else round(zb, 2)
out['cfb_open_edge']['verdict'] = 'LEAVE OUT' if (n < 100 or zb is None or zb < 1.64) else 'ADD'
out['cfb_open_edge']['reasons'] = [x for x in [f'held-out decisions {n} < 100' if n < 100 else None, f'win rate not significantly above break-even (z {out["cfb_open_edge"]["z_vs_breakeven"]})' if zb is None or zb < 1.64 else None,
                                              'the open is the number books post with small limits, so it is not reliably bettable'] if x]

# 3. injury / rest
inj = json.load(open(os.path.join(ROOT, 'data', 'nflverse_injuries.json')))
out['injury_rest_news'] = dict(players=len(inj), has_timestamps=any(isinstance(v, dict) and ('ts' in v or 'date' in v or 'updated' in v) for v in inj.values()),
                               verdict='NOT TESTABLE', reasons=['data/nflverse_injuries.json is a single current snapshot (status and designation only). With no history of when a status changed, an injury signal cannot be placed before a line move or a result.',
                                                               'no schedule-rest table is stored either'])

# 4. Polymarket price cheaper than Pinnacle fair, moneyline
pmrows = []
for key, g in S['games'].items():
    pin, fin, meta, pm = g.get('pin') or [], g.get('final'), g.get('meta') or {}, g.get('pm') or []
    if not pin or not fin or not meta.get('start') or fin['home'] == fin['away']: continue
    st = meta['start']
    for side in ('home', 'away'):
        tr_ = [x for x in pm if x.get('m') == 'ml' and x.get('side') == side and st - 24 * 3600 <= x['ts'] <= st - HRS and x.get('usd')]
        if len(tr_) < 3: continue
        usd = sum(x['usd'] for x in tr_); px = sum(x['px'] * x['usd'] for x in tr_) / usd
        tl = max(x['ts'] for x in tr_); snap = [p for p in pin if p['ts'] <= tl]
        if not snap or snap[-1].get('ml') is None: continue
        fair = snap[-1]['ml'] if side == 'home' else 1 - snap[-1]['ml']
        if fair - px >= 0.02:                              # fixed 2-point gap, not tuned
            win = (fin['home'] > fin['away']) == (side == 'home')
            pmrows.append(dict(res=1 if win else -1, fair=fair, px=px, clv=None, start=st, sport=meta.get('sport')))
out['polymarket_cheaper_than_pinnacle'] = dict(note='ML only. Polymarket volume-weighted price on a side, trades 3h to 24h before kickoff (3+ trades), at least 2 points under the Pinnacle fair probability from the last snapshot at or before the last such trade. ROI uses that stored exchange price before fees.',
                                               **pack(pmrows))
out['kalshi_vs_model'] = dict(verdict='NOT TESTABLE', reasons=['Kalshi game prices in the stored ledger are trade tapes only, not a price history joined to the model for finished games. The kb-data branch (Kalshi vs books gap loop) was not examined here.',
                                                               'data/pm_vs_books.json (the stored Polymarket-vs-books study) reports lead=false'])
pv = json.load(open(os.path.join(ROOT, 'data', 'pm_vs_books.json')))
out['kalshi_vs_model']['pm_vs_books_stored'] = dict(lead=pv.get('lead'), bets={k: {x: v.get(x) for x in ('n', 'games', 'w', 'l', 'roi', 'clv')} for k, v in (pv.get('bets') or {}).items()})
os.makedirs(os.path.dirname(a.out), exist_ok=True)
json.dump(out, open(a.out, 'w'), indent=1)
def brief(d): return {k: d[k] for k in ('n', 'w', 'l', 'win', 'vs_fair', 'z_vs_fair', 'roi_stored_px', 'clv', 'clv_n') if k in d}
for k, v in out.items():
    print('==', k, v.get('verdict'))
    for part in ('train', 'held_out'):
        if part in v: print(' ', part, brief(v[part]))
    for part in ('all', 'spread_only'):
        if part in v: print(' ', part, v[part]['verdict'], 'train', brief(v[part]['train']), 'test', brief(v[part]['held_out']))
    print(' ', v.get('reasons'))
