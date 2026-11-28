#!/usr/bin/env python3
"""
Early-season K and pace, scored once. Rules, committed before this ran: docs/early-k-pace-prereg.md.
Results: docs/early-k-pace-results.md and data/early_k_pace_test.json.

  python3 nba/scripts/test_early_k_pace.py

All variants run inside the shipped model (data/game_model.json parameters, no retune). Nothing here writes game_model.json.
  E  rating step K x EM for a team's first EN regular season games of a season (EM, EN chosen on the tune seasons' first 28 days)
  P  rating update on the margin scaled to league-average pace
  Q  predicted points scaled by matchup pace over league pace
"""
import datetime as dt, json, os, random, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'early_k_pace_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'early-k-pace-results.md')
EM_GRID, EN_GRID = (1.5, 2.0, 3.0, 4.0), (10, 20, 30)
PACE_STEP, PACE_CARRY = 0.10, 0.5


def possessions(rows, g):
    """Average of the two teams' possession estimates from the player rows, or None if the rows do not split into both teams."""
    t = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for r in rows:
        x = t[r['team']]
        x[0] += r['field_goals_attempted']; x[1] += r['free_throws_attempted']; x[2] += r['offensive_rebounds']; x[3] += r['turnovers']
    if g['home'] not in t or g['away'] not in t:
        return None
    est = [t[k][0] + 0.44 * t[k][1] - t[k][2] + t[k][3] for k in (g['home'], g['away'])]
    p = (est[0] + est[1]) / 2
    return p if p > 60 else None


class Model2(GM.Model):
    def __init__(self, P):
        super().__init__(P)
        self.ng = defaultdict(int)       # team -> regular season games this season
        self.dev = defaultdict(float)    # team -> pace deviation from league (possessions)
        self.lp, self.lpn = 99.0, 0

    def new_season(self, s, roster=None):
        if self.season is not None and s != self.season:
            self.ng.clear()
            for t in self.dev:
                self.dev[t] *= PACE_CARRY
        super().new_season(s, roster)

    def predict(self, g, miss_h, miss_a):
        margin, total, ph, pa = super().predict(g, miss_h, miss_a)
        if self.P.get('Q'):
            s = (self.lp + (self.dev[g['home']] + self.dev[g['away']]) / 2) / self.lp
            ph, pa = ph * s, pa * s
            total = ph + pa
        return margin, total, ph, pa

    def update(self, g, rows):
        P = self.P
        poss = possessions(rows, g)
        played = {r['athlete_id'] for r in rows if r['played']}
        oracle = {}
        for t in (g['home'], g['away']):
            for a in self.rotation(t, g['tip']):
                if a not in played:
                    oracle[a] = 1.0
        mh, ma = self.missing(g['home'], g['tip'], oracle), self.missing(g['away'], g['tip'], oracle)
        margin, total, ph, pa = self.predict(g, mh, ma)
        actual = g['hs'] - g['as']
        if P.get('PADJ') and poss:
            actual = actual * (self.lp / poss)
        err = actual - margin
        kh = P['K'] * (P['EM'] if self.ng[g['home']] < P.get('EN', 0) and not g['playoff'] else 1.0)
        ka = P['K'] * (P['EM'] if self.ng[g['away']] < P.get('EN', 0) and not g['playoff'] else 1.0)
        self.R[g['home']] += kh * err
        self.R[g['away']] -= ka * err
        eh, ea = g['hs'] - ph, g['as'] - pa
        self.O[g['home']] += P['KP'] * eh
        self.D[g['away']] -= P['KP'] * eh
        self.O[g['away']] += P['KP'] * ea
        self.D[g['home']] -= P['KP'] * ea
        self.base += 0.002 * (eh + ea) / 2
        if not g['playoff']:
            self.pts[0] += g['hs'] + g['as']
            self.pts[1] += 2
            self.ng[g['home']] += 1
            self.ng[g['away']] += 1
        if not g['neutral'] and not g['playoff']:
            self.hfa_n += 1
            self.hfa += (g['hs'] - g['as'] - (margin - self.hfa) - self.hfa) / min(self.hfa_n, 1500)
        if poss:
            self.lpn += 1
            self.lp += (poss - self.lp) / min(self.lpn, 3000)
            for t in (g['home'], g['away']):
                self.dev[t] += PACE_STEP * ((poss - self.lp) - self.dev[t])
        al = P['ALPHA']
        for r in rows:
            if not r['played']:
                continue
            p = self.pl.get(r['athlete_id'])
            gs, m = C.game_score(r), r['minutes']
            if p is None:
                self.pl[r['athlete_id']] = {'mpg': m, 'gs': gs, 'n': 1, 'team': r['team'], 'last': g['tip'], 's': self.season}
            else:
                a = max(al, 1 / (p['n'] + 1))
                p['mpg'] += a * (m - p['mpg'])
                p['gs'] += a * (gs - p['gs'])
                p['n'] += 1
                p['team'], p['last'], p['s'] = r['team'], g['tip'], self.season
        self.team_last[g['home']] = self.team_last[g['away']] = g['tip']
        return oracle


def mae_vs_close(recs, mode, idx, keep=lambda gid: True):
    key, sign, act = ('spread_close', -1, 'actual_margin') if idx == 0 else ('total_close', 1, 'actual_total')
    d = [abs(r[mode][idx] - r[act]) for r in recs if keep(r['g']['game_id']) and (r.get('line') or {}).get(key) is not None]
    m = [abs(sign * r['line'][key] - r[act]) for r in recs if keep(r['g']['game_id']) and (r.get('line') or {}).get(key) is not None]
    return (round(statistics.mean(d), 3), round(statistics.mean(m), 3), len(d)) if d else None


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = Model2
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}}

    # E: choose (EM, EN) on the tune seasons' first 28 days, who actually sat
    for em in (1.0,) + EM_GRID:
        for en in ((0,) if em == 1.0 else EN_GRID):
            _, recs = GM.run(dict(P0, EM=em, EN=en), GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
            ea = SS.early(recs)
            m = statistics.mean(abs(r['oracle'][0] - r['actual_margin']) for r in recs if ea[r['g']['game_id']])
            res['tune'][f'{em}|{en}'] = round(m, 4)
            print(f'tune EM={em} EN={en}: first-28-days margin MAE {m:.4f}', flush=True)
    best = min((k for k in res['tune'] if not k.startswith('1.0|')), key=lambda k: res['tune'][k])
    em, en = float(best.split('|')[0]), int(best.split('|')[1])
    res['em'], res['en'] = em, en
    print('chosen', em, en, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])[1]
    base = dict(P0, EM=1.0, EN=0)
    cur = run(base)
    var = {'E': (run(dict(base, EM=em, EN=en)), 0), 'P': (run(dict(base, PADJ=True)), 0), 'Q': (run(dict(base, Q=True)), 1)}
    ea = SS.early(cur)
    res['scores'] = {}
    for name, (recs, idx) in var.items():
        blk = {}
        for label, keep in (('first28', lambda k: ea[k]), ('whole', lambda k: True)):
            blk[label] = {}
            blk[label]['pooled'] = SS.boot(cur, recs, idx, 'tip', keep)
            for s in GM.TEST:
                sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
                blk[label][str(s)] = SS.boot(cur, recs, idx, 'tip', lambda k, sid=sid, kp=keep: k in sid and kp(k))
        blk['vs_close_whole'] = {'variant': mae_vs_close(recs, 'tip', idx), 'shipped': mae_vs_close(cur, 'tip', idx)}
        withl = [r for r in recs if (r.get('line') or {}).get('spread_close') is not None]
        withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
        key, i = ('spread_close', 0) if idx == 0 else ('total_close', 1)
        blk['info_variant'] = GM.info_test(withl, 'tip', key, i)
        blk['info_shipped'] = GM.info_test(withc, 'tip', key, i)
        res['scores'][name] = blk
        print(name, json.dumps({k: blk[k] for k in ('first28', 'whole')}), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)


def write_md(res):
    L = ['# Game model: early-season K and pace, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_early_k_pace.py`. Rules, committed before this ran: [early-k-pace-prereg.md](early-k-pace-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters, no retune.', '',
         f"E chosen on the tune seasons' first 28 days: K x {res['em']} for a team's first {res['en']} games.", '',
         'Tune grid (first-28-days margin MAE, who actually sat): ' + ', '.join(f'{k}: {v}' for k, v in res['tune'].items()), '']
    what = {'E': 'margin', 'P': 'margin', 'Q': 'total'}
    for name, blk in res['scores'].items():
        L += [f'## {name} ({what[name]} MAE, points)', '', '| Window | Season | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|---|']
        for w in ('first28', 'whole'):
            for s in ('2025', '2026', 'pooled'):
                b = blk[w][s]
                L.append(f"| {w} | {s} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close (whole, games with a line): variant, close, n = {blk['vs_close_whole']['variant']}; shipped = {blk['vs_close_whole']['shipped']}.",
              f"Information test against the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
