#!/usr/bin/env python3
"""CFB week 7 retro: JP+ rates teams on success rate and explosiveness; ours is EPA per play only. Does adding those two ratings improve the live model, walk-forward 2022-25?

Pre-registered (nothing here is chosen by pick record):
  S   success rate per play (1st down gain >= 50% of the distance, 2nd >= 70%, 3rd/4th >= 100%), same filters as the EPA model (scrimmage plays, no kneels,
      no penalty-no-play, garbage time dropped), opponent- and home-adjusted by the same weekly ridge (ALPHA 300), prior = last season x 0.85
  X   explosiveness = EPA per SUCCESSFUL play (the isolated-PPA idea), same ridge, weighted by the number of successful plays
  Fit  on 2022-23 weeks 4+ only:  home margin = b0 + b1 * v2st + b2 * gap_S + b3 * gap_X  (HFA is inside v2st; b0 absorbs the league home residual)
       2024-25 is then read once: average miss, and 5+ point disagreements vs the ESPN close and open of the combined number.
Inputs: <dir>/base_rows.csv, <dir>/opens_hist.json, the sportsdataverse parquet files. Run: python3 scripts/cfb_week7_sr_study.py --dir /tmp/cfbstudy
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
from cfb_week7_study import cp, rec, fmt

EXTRA = ['season', 'game_id', 'seasonType', 'pos_team_id', 'def_pos_team_id', 'scrimmage_play', 'kneel_down', 'EPA', 'period', 'pos_score_diff_start',
         'penalty_no_play', 'start.down', 'start.distance', 'statYardage']


def metric_tables(d, tg):
    outS, outX = [], []
    for y in st.YEARS:
        p = pd.read_parquet(f'{d}/pbp_{y}.parquet', columns=EXTRA); p = p[p.seasonType == 2]
        s = p[p.scrimmage_play & ~p.kneel_down & ~p.penalty_no_play]
        s = s[s.pos_score_diff_start.abs() <= s.period.map(st.GARBAGE).fillna(22)]
        dn = s['start.down'].astype(float); ds = s['start.distance'].astype(float); gain = s.statYardage.astype(float)
        need = np.where(dn == 1, 0.5 * ds, np.where(dn == 2, 0.7 * ds, ds))
        s = s.assign(suc=((gain >= need) & dn.isin([1, 2, 3, 4])).astype(float), epa=s.EPA.clip(-3, 3)).dropna(subset=['epa'])
        k = ['game_id', 'pos_team_id', 'def_pos_team_id']
        a = s.groupby(k).agg(plays=('suc', 'size'), suc=('suc', 'sum')).reset_index()
        b = s[s.suc == 1].groupby(k).agg(plays=('epa', 'size'), epa_sum=('epa', 'sum')).reset_index()
        outS.append(a.assign(season=y)); outX.append(b.assign(season=y))
    S = pd.concat(outS); X = pd.concat(outX)
    S['epa'] = S.suc / S.plays; X['epa'] = X.epa_sum / X.plays
    base = tg.drop(columns=['epa_sum', 'plays', 'epa'])
    return [base.merge(M[['game_id', 'pos_team_id', 'def_pos_team_id', 'plays', 'epa']], on=['game_id', 'pos_team_id', 'def_pos_team_id']) for M in (S, X)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); a = ap.parse_args()
    d = pd.read_csv(os.path.join(a.dir, 'base_rows.csv')); op = json.load(open(os.path.join(a.dir, 'opens_hist.json')))
    d['open'] = d.game_id.map(lambda i: -op[str(i)]['so'] if str(i) in op else np.nan)
    tg, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir)
    tgS, tgX = metric_tables(a.dir, tg)
    gaps = []
    for T in (tgS, tgX):
        r = st.walk_forward(T, gm, fbs); r = r[r.season.isin([2022, 2023, 2024, 2025])].reset_index(drop=True)
        assert len(r) == len(d) and (r.hm.values == d.hm.values).all()
        hf = np.where(d.neutral, 0.0, 1.0); gaps.append((r.pred.values - st.HFA * hf) / st.K)
    d['gS'], d['gX'] = gaps
    q = d[d.week >= 4].dropna(subset=['mkt']).copy(); tune = q.season.isin([2022, 2023])
    A = np.c_[np.ones(len(q)), q.v2st, q.gS, q.gX]; y = q.hm.values
    b = np.linalg.lstsq(A[tune.values], y[tune.values], rcond=None)[0]; print('fit on 2022-23 weeks 4+: b0 %.2f  v2st %.3f  gapS %.1f  gapX %.1f' % tuple(b))
    q['comb'] = A @ b
    # also report each rating alone, rescaled on the tuning seasons, so a gain can be attributed
    for nm, col in (('S only', ['gS']), ('X only', ['gX'])):
        B = np.c_[np.ones(len(q)), q[col].values]; bb = np.linalg.lstsq(B[tune.values], y[tune.values], rcond=None)[0]; q[nm] = B @ bb
    for lab, m in (('tune 2022-23', tune), ('TEST 2024-25 (read once)', ~tune)):
        s = q[m]
        print('\n%s: %d games | miss v2st %.3f | combined %.3f | S only %.3f | X only %.3f | market close %.3f' % (lab, len(s), (s.hm - s.v2st).abs().mean(), (s.hm - s.comb).abs().mean(),
              (s.hm - s['S only']).abs().mean(), (s.hm - s['X only']).abs().mean(), (s.hm - s.mkt).abs().mean()))
        for line in ('mkt', 'open'):
            z = s.dropna(subset=[line]); row = []
            for col in ('v2st', 'comb', 'S only', 'X only'):
                e = z[col] - z[line]; c = z.hm - z[line]; sel = z[(e.abs() >= 5)]; row.append('%s %s' % (col, fmt(rec(sel, e[sel.index], c[sel.index]))))
            print('   5+ vs %-5s %s' % (line, ' | '.join(row)))
        e = s.comb - s.mkt; c = s.hm - s.mkt; x = np.c_[np.ones(len(s)), s.mkt, e]; print('   weight on the combined edge vs close: %.3f (v2st alone %.3f)' % (np.linalg.lstsq(x, s.hm, rcond=None)[0][2], np.linalg.lstsq(np.c_[np.ones(len(s)), s.mkt, s.v2st - s.mkt], s.hm, rcond=None)[0][2]))
    print('\nby season, 5+ vs close, v2st -> combined:')
    for yr in (2022, 2023, 2024, 2025):
        s = q[q.season == yr]; o = []
        for col in ('v2st', 'comb'):
            e = s[col] - s.mkt; c = s.hm - s.mkt; sel = s[e.abs() >= 5]; o.append(fmt(rec(sel, e[sel.index], c[sel.index])))
        print('  ', yr, ' -> '.join(o))
    q.to_csv(os.path.join(a.dir, 'sr_study_rows.csv'), index=False)


if __name__ == '__main__':
    sys.exit(main())
