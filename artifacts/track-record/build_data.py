#!/usr/bin/env python3
"""Rebuild data.json for the Vault Track Record artifact from origin/main.
Usage: python3 artifacts/track-record/build_data.py [--local] [--out=DIR]
--local reads the working copy instead (preview before a push; never publish from it).
Fetches origin/main, reads data/bet_results.json + data/edge_scoreboard.json from
the pushed tree (never the working copy), and writes data.json next to this file."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
_o = [a[6:] for a in sys.argv if a.startswith('--out=')]
OUT = os.path.join(_o[0], 'data.json') if _o else os.path.join(HERE, 'data.json')
if _o: os.makedirs(_o[0], exist_ok=True)
if '--local' in sys.argv:
    show = lambda p: json.load(open(os.path.join(REPO, p)))
else:
    subprocess.run(['git', '-C', REPO, 'fetch', '-q', 'origin', 'main'], check=True)
    show = lambda p: json.loads(subprocess.run(['git', '-C', REPO, 'show', 'origin/main:' + p],
                                               capture_output=True, text=True, check=True).stdout)
d, es = show('data/bet_results.json'), show('data/edge_scoreboard.json')
r = lambda x, n=4: None if x is None else round(x, n)
props = [[p['week'], p['name'], p['team'], p['pos'], p['opp'], p['market'], p['side'], p['line_close'],
          r(p['proj'], 2), p['actual'], 1 if p['push'] else 0, p['won_close'], r(p['clv_line'], 2),
          p['beat_close'], r(p['p_model']), r(p['p_market']), p.get('grade_flat', p['grade']),
          p.get('hist_n'), r(p.get('p_hist')), p.get('side_hist'), p.get('won_hist'),
          p.get('close_over'), p.get('close_under'), p.get('open_over'), p.get('open_under'), (p['grade'] if 'grade_flat' in p else p.get('grade_px')),
          # grade-rule test (2026-09-26): old coin-flip boost, market-anchored
          # shadow, and both rules on the ALT side (the card Vault does not lean)
          p.get('grade_boost'), p.get('grade_mkt'), p.get('grade_alt'), p.get('grade_mkt_alt'), p.get('won_alt'),
          # Vault team-total lean (2026-09-26 fade-the-lean shadow)
          p.get('vault_team_lean'),
          # per-book prices (2026-09-26): +EV-by-book filter on the Track Record
          p.get('books_open'), p.get('books_close'), p.get('books_open_src')] for p in d['props']]
# Best Bets rows (2026-09-27): every play that reached the live Best Bets top-N
# plus every locked-card play, graded at the line + price it POSTED with
# (settle_bets.py -> best_bets_record.json). Same column layout as props, plus
# bb ('card' | 'bb'), bpx (posted price), bbk (book). The model/market columns
# come from the ledger row for that prop, flipped when the play took the other
# side. Voids and pending plays are left out, like the ledger rows.
try:
    rec = show('data/best_bets_record.json')
except Exception:
    rec = {}
led = {(str(p['season']), p['week'], str(p.get('pid')), p['market']): p for p in d['props']}
card_keys = {c['key'] for c in rec.get('picks') or []}
plays = {c['key']: c for c in (rec.get('shadow_picks') or [])}
plays.update({c['key']: c for c in rec.get('picks') or []})
flip = lambda x: None if x is None else 1 - x
bbrows = []
for k, c in plays.items():
    if c.get('result') not in ('W', 'L', 'P'):
        continue
    L = led.get((str(c['season']), c['week'], str(c.get('pid')), c['market'])) or {}
    same = L.get('side') == c['side']
    bbrows.append([c['week'], c['name'], c.get('team'), c.get('pos'), c.get('opp'), c['market'], c['side'], c['line'],
                   r(c.get('proj') if c.get('proj') is not None else L.get('proj'), 2), c.get('actual'),
                   1 if c['result'] == 'P' else 0, 1 if c['result'] == 'W' else 0 if c['result'] == 'L' else None,
                   r(c.get('clv_line'), 2), None if c.get('beat_close') is None else (1 if c['beat_close'] else 0),
                   r(c.get('prob')), r(L.get('p_market') if same else flip(L.get('p_market'))), c.get('grade'),
                   None, None, None, None,
                   L.get('close_over'), L.get('close_under'), L.get('open_over'), L.get('open_under'), c.get('grade'),
                   None, None, None, None, None, L.get('vault_team_lean'),
                   L.get('books_open'), L.get('books_close'), L.get('books_open_src'),
                   'card' if k in card_keys else 'bb', c.get('price'), c.get('book')])
games = [{k: (r(v) if isinstance(v, float) else v) for k, v in g.items()
          if k not in ('kind', 'season', 'p_home', 'y_home', 'vault_winhome')}
         for g in d['games'] if g.get('market') != 'final']
mk = {k: {'bias': r(v.get('proj_bias'), 2), 'mae': r(v.get('proj_mae'), 2),
          'll_model': r(v.get('model_logloss')), 'll_mkt': r(v.get('market_logloss'))}
      for k, v in es['markets'].items()}
json.dump({'generated': d['generated'], 'built': int(time.time()), 'meta': d['meta'],
           'pcols': 'week,name,team,pos,opp,market,side,line,proj,actual,push,won,clv,beat,pm,pk,grade,hn,ph,sh,wh,co,cu,oo,ou,gpx,gb,gmk,ga,gma,wa,vtl,bo,bc,bs'.split(','),
           'props': props, 'games': games, 'mk': mk, 'bb': bbrows}, open(OUT, 'w'), separators=(',', ':'))
wk = max((p[0] for p in props), default=None)
print(f"data.json: {len(props)} props, {len(games)} games, through week {wk}, generated {d['generated']}")
