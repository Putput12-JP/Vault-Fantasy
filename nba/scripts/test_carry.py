#!/usr/bin/env python3
"""
Roster-continuity carry at season start, scored once. Rules, committed before this ran: docs/carry-prereg.md.
Results: docs/carry-results.md and data/carry_test.json.

  python3 nba/scripts/test_carry.py

Inside the shipped model (data/game_model.json parameters, no retune). Nothing here writes game_model.json.
After a team's 3rd game of a season its rating is corrected by (f - CARRY) x (its rating at the end of last season),
f = clip(a + b x (continuity - 0.5), 0.05, 0.95); continuity = share of last season's team minutes played by players
who played for the team in its first 3 games. Games 1 to 3 use the shipped carry.
"""
import datetime as dt, json, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'carry_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'carry-results.md')
GRID = [(a, b) for a in (0.4, 0.5, 0.6) for b in (0.0, 0.3, 0.6, 1.0)]


class CarryModel(GM.Model):
    def __init__(self, P):
        super().__init__(P)
        self.mins = defaultdict(lambda: defaultdict(float))
        self.R0, self.prev = {}, None
        self.ng = defaultdict(int)
        self.first3 = defaultdict(set)
        self.conts = {}

    def new_season(self, s, roster=None):
        if self.season is not None and s != self.season:
            self.R0 = dict(self.R)
            self.prev = self.season
            self.ng.clear()
            self.first3.clear()
        super().new_season(s, roster)

    def update(self, g, rows):
        oracle = super().update(g, rows)
        if g['playoff']:
            return oracle
        for r in rows:
            if r['played']:
                self.mins[self.season][(r['team'], r['athlete_id'])] += r['minutes']
        for t in (g['home'], g['away']):
            self.ng[t] += 1
            if self.ng[t] <= 3:
                self.first3[t] |= {r['athlete_id'] for r in rows if r['played'] and r['team'] == t}
            if self.ng[t] == 3 and self.P.get('CC') and self.prev is not None and t in self.R0:
                last = self.mins[self.prev]
                tot = sum(v for (tm, _), v in last.items() if tm == t)
                if tot > 0:
                    kept = sum(v for (tm, a), v in last.items() if tm == t and a in self.first3[t])
                    cont = kept / tot
                    a_, b_ = self.P['CC']
                    f = min(0.95, max(0.05, a_ + b_ * (cont - 0.5)))
                    self.R[t] += (f - self.P['CARRY']) * self.R0[t]
                    self.conts[(self.season, t)] = round(cont, 3)
        return oracle


def mae_close(recs):
    d = [(abs(r['tip'][0] - r['actual_margin']), abs(-r['line']['spread_close'] - r['actual_margin']))
         for r in recs if (r.get('line') or {}).get('spread_close') is not None]
    return {'model': round(statistics.mean(a for a, _ in d), 3), 'close': round(statistics.mean(b for _, b in d), 3), 'n': len(d)}


def main():
    seasons = GM.WARM + GM.TUNE + GM.TEST
    box = C.player_games(seasons)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = CarryModel
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}}

    def tune(P):
        _, recs = GM.run(P, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
        ea = SS.early(recs)
        return statistics.mean(abs(r['oracle'][0] - r['actual_margin']) for r in recs if ea[r['g']['game_id']])
    res['tune']['S'] = round(tune(dict(P0)), 4)
    for a, b in GRID:
        res['tune'][f'a={a}|b={b}'] = round(tune(dict(P0, CC=(a, b))), 4)
        print('tune', a, b, res['tune'][f'a={a}|b={b}'], 'S', res['tune']['S'], flush=True)
    k = min((k for k in res['tune'] if k != 'S'), key=lambda k: res['tune'][k])
    a, b = [float(x.split('=')[1]) for x in k.split('|')]
    res['chosen'] = {'a': a, 'b': b}
    print('chosen', a, b, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, seasons, box, lines, inj, record_from=GM.TEST[0])
    _, cur = run(dict(P0))
    m_cc, rec = run(dict(P0, CC=(a, b)))
    ea = SS.early(cur)
    blk = {}
    for label, keep in (('first28', lambda k: ea[k]), ('whole', lambda k: True)):
        blk[label] = {'pooled': SS.boot(cur, rec, 0, 'tip', keep)}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk[label][str(s)] = SS.boot(cur, rec, 0, 'tip', lambda k, sid=sid, kp=keep: k in sid and kp(k))
    withl = [r for r in rec if (r.get('line') or {}).get('spread_close') is not None]
    withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
    blk['info_variant'] = GM.info_test(withl, 'tip', 'spread_close', 0)
    blk['info_shipped'] = GM.info_test(withc, 'tip', 'spread_close', 0)
    blk['close_mae'] = {'variant': mae_close(rec), 'shipped': mae_close(cur)}
    cont = {s: sorted(v for (ss, _), v in m_cc.conts.items() if ss == s) for s in GM.TEST}
    blk['continuity'] = {str(s): {'n': len(v), 'min': v[0], 'median': v[len(v) // 2], 'max': v[-1]} for s, v in cont.items() if v}
    res['scores'] = blk
    print(json.dumps({k: blk[k] for k in ('first28', 'whole', 'continuity')}), flush=True)
    print('info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=str)
    write_md(res)


def write_md(res):
    L = ['# Game model: roster-continuity carry, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_carry.py`. Rules, committed before this ran: [carry-prereg.md](carry-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.', '',
         f"Chosen on the first 28 days of 2022-23 and 2023-24: a = {res['chosen']['a']}, b = {res['chosen']['b']}. Tune margin MAE (first 28 days, who actually sat): " +
         ', '.join(f'{k}: {v}' for k, v in res['tune'].items()) + '.', '']
    blk = res['scores']
    L += ['## CC (margin MAE, points)', '', '| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|---|']
    for w in ('first28', 'whole'):
        for s in ('2025', '2026', 'pooled'):
            b = blk[w][s]
            L.append(f"| {w} | {s} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
    L += ['', f"Continuity by season (teams, min / median / max): {blk['continuity']}.",
          f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
