#!/usr/bin/env python3
"""
Three-point shooting luck, scored once. Rules, committed before this ran: docs/shooting-luck-prereg.md.
Results: docs/shooting-luck-results.md and data/shooting_luck_test.json.

  python3 nba/scripts/test_shooting_luck.py

Inside the shipped model (data/game_model.json parameters, no retune). Nothing here writes game_model.json.
  M  rating update learns from margin - L x (luck home - luck away)
  T  offense / defense / scoring-level updates learn from points - L x own luck
luck = 3 x (3PM - 3PA x the team's own shrunk pre-game three-point rate)
"""
import datetime as dt, json, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'shooting_luck_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'shooting-luck-results.md')
CARRY = 0.5
GRID = [(l, k0) for l in (0.25, 0.5, 0.75, 1.0) for k0 in (300, 1000)]


class LuckModel(GM.Model):
    def __init__(self, P):
        super().__init__(P)
        self.tb = defaultdict(lambda: [0.0, 0.0])   # team -> [3PM, 3PA]
        self.lg = [0.0, 0.0]

    def new_season(self, s, roster=None):
        if self.season is not None and s != self.season:
            for v in self.tb.values():
                v[0] *= CARRY; v[1] *= CARRY
        super().new_season(s, roster)

    def rate(self, t):
        lg = self.lg[0] / self.lg[1] if self.lg[1] else 0.36
        k0 = self.P['K0']
        m, a = self.tb[t]
        return (m + k0 * lg) / (a + k0)

    def update(self, g, rows):
        P = self.P
        mode = P.get('LUCK')
        shots = defaultdict(lambda: [0.0, 0.0])
        for r in rows:
            shots[r['team']][0] += r['three_point_field_goals_made']
            shots[r['team']][1] += r['three_point_field_goals_attempted']
        ok = g['home'] in shots and g['away'] in shots
        luck = {}
        if mode and ok:
            for t in (g['home'], g['away']):
                luck[t] = 3.0 * (shots[t][0] - shots[t][1] * self.rate(t))
        oracle = super().update(g, rows)
        if luck:
            L = P['L']
            if mode == 'M':
                d = -P['K'] * L * (luck[g['home']] - luck[g['away']])
                self.R[g['home']] += d
                self.R[g['away']] -= d
            elif mode == 'T':
                dh, da = -L * luck[g['home']], -L * luck[g['away']]
                self.O[g['home']] += P['KP'] * dh
                self.D[g['away']] -= P['KP'] * dh
                self.O[g['away']] += P['KP'] * da
                self.D[g['home']] -= P['KP'] * da
                self.base += 0.002 * (dh + da) / 2
        if ok:
            for t in (g['home'], g['away']):
                self.tb[t][0] += shots[t][0]
                self.tb[t][1] += shots[t][1]
                self.lg[0] += shots[t][0]
                self.lg[1] += shots[t][1]
        return oracle


def tune_mae(P, box, idx):
    _, recs = GM.run(P, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
    act = 'actual_margin' if idx == 0 else 'actual_total'
    return statistics.mean(abs(r['oracle'][idx] - r[act]) for r in recs)


def mae_close(recs, idx):
    key, sign, act = ('spread_close', -1, 'actual_margin') if idx == 0 else ('total_close', 1, 'actual_total')
    d = [(abs(r['tip'][idx] - r[act]), abs(sign * r['line'][key] - r[act])) for r in recs if (r.get('line') or {}).get(key) is not None]
    return {'model': round(statistics.mean(a for a, _ in d), 3), 'close': round(statistics.mean(b for _, b in d), 3), 'n': len(d)}


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = LuckModel
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}}
    for idx, mode in ((0, 'M'), (1, 'T')):
        res['tune'][f'{mode}|S'] = round(tune_mae(dict(P0), box, idx), 4)
        for l, k0 in GRID:
            res['tune'][f'{mode}|L={l}|K0={k0}'] = round(tune_mae(dict(P0, LUCK=mode, L=l, K0=k0), box, idx), 4)
            print('tune', mode, l, k0, res['tune'][f'{mode}|L={l}|K0={k0}'], 'shipped', res['tune'][f'{mode}|S'], flush=True)
    pick = {}
    for mode in ('M', 'T'):
        k = min((k for k in res['tune'] if k.startswith(mode + '|L=')), key=lambda k: res['tune'][k])
        pick[mode] = dict(zip(('L', 'K0'), (float(x.split('=')[1]) for x in k.split('|')[1:])))
    res['chosen'] = pick
    print('chosen', pick, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])[1]
    cur = run(dict(P0))
    ea = SS.early(cur)
    var = {'M': (run(dict(P0, LUCK='M', **pick['M'])), 0, 'spread_close'), 'T': (run(dict(P0, LUCK='T', **pick['T'])), 1, 'total_close')}
    res['scores'] = {}
    for name, (recs, idx, key) in var.items():
        blk = {'whole': {'pooled': SS.boot(cur, recs, idx, 'tip', lambda k: True)}, 'first28': {'pooled': SS.boot(cur, recs, idx, 'tip', lambda k: ea[k])}}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk['whole'][str(s)] = SS.boot(cur, recs, idx, 'tip', lambda k, sid=sid: k in sid)
            blk['first28'][str(s)] = SS.boot(cur, recs, idx, 'tip', lambda k, sid=sid: k in sid and ea[k])
        withl = [r for r in recs if (r.get('line') or {}).get(key) is not None]
        withc = [r for r in cur if (r.get('line') or {}).get(key) is not None]
        blk['info_variant'] = GM.info_test(withl, 'tip', key, idx)
        blk['info_shipped'] = GM.info_test(withc, 'tip', key, idx)
        blk['close_mae'] = {'variant': mae_close(recs, idx), 'shipped': mae_close(cur, idx)}
        res['scores'][name] = blk
        print(name, json.dumps({k: blk[k] for k in ('whole', 'first28')}), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)


def write_md(res):
    L = ['# Game model: three-point shooting luck, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_shooting_luck.py`. Rules, committed before this ran: [shooting-luck-prereg.md](shooting-luck-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.', '',
         f"Chosen on the tune seasons: M = {res['chosen']['M']}; T = {res['chosen']['T']}. Tune MAE (all games, who actually sat): " +
         ', '.join(f'{k}: {v}' for k, v in res['tune'].items()) + '.', '']
    what = {'M': 'margin', 'T': 'total'}
    for name, blk in res['scores'].items():
        L += [f'## {name} ({what[name]} MAE, points)', '', '| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|---|']
        for w in ('whole', 'first28'):
            for s in ('2025', '2026', 'pooled'):
                b = blk[w][s]
                L.append(f"| {w} | {s} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
