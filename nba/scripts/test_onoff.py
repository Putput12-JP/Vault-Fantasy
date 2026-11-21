#!/usr/bin/env python3
"""
On/off player value in the injury adjustment, scored once. Rules, committed before this ran: docs/onoff-prereg.md.
Results: docs/onoff-results.md and data/onoff_test.json.

  python3 nba/scripts/test_onoff.py

Box-score on/off only (plus-minus and minutes), accumulated strictly from past games. Inside the shipped model (data/game_model.json
parameters, no retune). Nothing here writes game_model.json.
  O  player value = shrunk on/off swing x minutes / 48          (C, K0 tuned on the tune seasons)
  B  player value = shipped value + LAM x on/off value          (LAM, K0 tuned on the tune seasons; C stays shipped)
"""
import datetime as dt, json, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'onoff_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'onoff-results.md')
CARRY = 0.5
O_GRID = [(c, k0) for c in (0.25, 0.5, 0.75, 1.0, 1.5) for k0 in (200, 500, 1000)]
B_GRID = [(lam, k0) for lam in (0.5, 1, 2, 4) for k0 in (200, 500, 1000)]


class OOModel(GM.Model):
    def new_season(self, s, roster=None):
        if self.season is not None and s != self.season:
            for p in self.pl.values():
                if 'oo' in p:
                    p['oo'] = [x * CARRY for x in p['oo']]
        super().new_season(s, roster)

    def oo_value(self, p):
        a = p.get('oo')
        if not a:
            return 0.0
        pm, m_on, off, m_off = a
        k0 = self.P['K0']
        swing = 48 * pm / (m_on + k0) - 48 * off / (m_off + k0)
        return max(0.0, swing) * p['mpg'] / 48.0

    def value(self, p):
        mode = self.P.get('OO')
        if mode == 'O':
            return self.oo_value(p)
        base = super().value(p)
        if mode == 'B':
            return base + self.P['LAM'] * self.oo_value(p)
        return base

    def update(self, g, rows):
        oracle = super().update(g, rows)
        if self.P.get('OO'):
            margin = {g['home']: g['hs'] - g['as'], g['away']: g['as'] - g['hs']}
            tmin = defaultdict(float)
            for r in rows:
                tmin[r['team']] += r['minutes']
            for r in rows:
                if not r['played'] or r['team'] not in margin:
                    continue
                p = self.pl.get(r['athlete_id'])
                if p is None:
                    continue
                m_off = tmin[r['team']] / 5.0 - r['minutes']
                if m_off < 0:
                    continue
                a = p.setdefault('oo', [0.0, 0.0, 0.0, 0.0])
                a[0] += r['plus_minus']; a[1] += r['minutes']
                a[2] += margin[r['team']] - r['plus_minus']; a[3] += m_off
        return oracle


def tune_mae(P, box):
    _, recs = GM.run(P, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
    return statistics.mean(abs(r['oracle'][0] - r['actual_margin']) for r in recs)


def mae_close(recs):
    d = [(abs(r['tip'][0] - r['actual_margin']), abs(-r['line']['spread_close'] - r['actual_margin']))
         for r in recs if (r.get('line') or {}).get('spread_close') is not None]
    return {'model': round(statistics.mean(a for a, _ in d), 3), 'close': round(statistics.mean(b for _, b in d), 3), 'n': len(d)}


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = OOModel
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}}
    res['tune']['S'] = round(tune_mae(dict(P0), box), 4)
    print('tune shipped', res['tune']['S'], flush=True)
    for c, k0 in O_GRID:
        res['tune'][f'O|C={c}|K0={k0}'] = round(tune_mae(dict(P0, OO='O', C=c, K0=k0), box), 4)
        print('tune O', c, k0, res['tune'][f'O|C={c}|K0={k0}'], flush=True)
    for lam, k0 in B_GRID:
        res['tune'][f'B|LAM={lam}|K0={k0}'] = round(tune_mae(dict(P0, OO='B', LAM=lam, K0=k0), box), 4)
        print('tune B', lam, k0, res['tune'][f'B|LAM={lam}|K0={k0}'], flush=True)
    bo = min((k for k in res['tune'] if k.startswith('O|')), key=lambda k: res['tune'][k])
    bb = min((k for k in res['tune'] if k.startswith('B|')), key=lambda k: res['tune'][k])
    res['chosen'] = {'O': bo, 'B': bb}
    c_o, k0_o = [float(x.split('=')[1]) for x in bo.split('|')[1:]]
    lam_b, k0_b = [float(x.split('=')[1]) for x in bb.split('|')[1:]]
    print('chosen', bo, bb, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])[1]
    cur = run(dict(P0))
    var = {'O': run(dict(P0, OO='O', C=c_o, K0=k0_o)), 'B': run(dict(P0, OO='B', LAM=lam_b, K0=k0_b))}
    active = {r['g']['game_id'] for r in cur if abs(r['tip'][0] - r['none'][0]) > 1e-9}
    res['injury_games'] = len(active)
    res['scores'] = {}
    for name, recs in var.items():
        blk = {'whole': {'pooled': SS.boot(cur, recs, 0, 'tip', lambda k: True)}}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk['whole'][str(s)] = SS.boot(cur, recs, 0, 'tip', lambda k, sid=sid: k in sid)
        blk['injury_games'] = SS.boot(cur, recs, 0, 'tip', lambda k: k in active)
        withl = [r for r in recs if (r.get('line') or {}).get('spread_close') is not None]
        withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
        blk['info_variant'] = GM.info_test(withl, 'tip', 'spread_close', 0)
        blk['info_shipped'] = GM.info_test(withc, 'tip', 'spread_close', 0)
        blk['close_mae'] = {'variant': mae_close(recs), 'shipped': mae_close(cur)}
        res['scores'][name] = blk
        print(name, json.dumps({k: blk[k] for k in ('whole', 'injury_games')}), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)


def write_md(res):
    L = ['# Game model: on/off player value, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_onoff.py`. Rules, committed before this ran: [onoff-prereg.md](onoff-prereg.md). "
         'Box-score on/off, test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.', '',
         f"Chosen on the tune seasons: O = {res['chosen']['O']}; B = {res['chosen']['B']}. Tune margin MAE (all games, who actually sat): " +
         ', '.join(f'{k}: {v}' for k, v in res['tune'].items()) + '.',
         f"Games where the shipped injury adjustment is active at tip: {res['injury_games']} of the test games.", '']
    for name, blk in res['scores'].items():
        L += [f'## {name} (margin MAE, points)', '', '| Window | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|']
        for lab, b in (('2025', blk['whole']['2025']), ('2026', blk['whole']['2026']), ('pooled', blk['whole']['pooled']),
                       ('exploratory: injury adjustment active', blk['injury_games'])):
            L.append(f"| {lab} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
