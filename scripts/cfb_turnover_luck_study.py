#!/usr/bin/env python3
"""CFB model: does taking turnover luck out of the ratings improve the v2 + special teams model? Walk-forward 2022-2025.

The offense and defense ratings are built from EPA per play, and a turnover is a big EPA swing that is partly luck: a fumble is lost about half the time
whoever fumbles it, and part of an interception is a tipped ball. Three luck-neutral versions of the same ratings, each rebuilt end to end (v1 walk-forward
for the targets, the v2 regression prior, the special teams layer), compared with the current model:

  F     every fumble play (a fumble happened) is given the league average EPA of fumble plays, instead of its actual EPA (lost or kept)
  FI    F, and every interception or incompletion is given the league average EPA of that class, so a pick is no worse than any other incompletion
  FI50  F, and interceptions/incompletions at half way between their actual EPA and the class average (part of an interception is skill)

League-wide averages are pooled over 2021-2025 (two scalars, no team information). Nothing is tuned: the three variants are fixed here. The decision rule is
the one used for every other add-on: the average miss on the untouched 2024-25 seasons must improve by about 0.05 and the pick records must not get worse.

Run: python3 scripts/cfb_turnover_luck_study.py [--dir /tmp/cfbstudy]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_v2_st_study as sts
import cfb_v2_prior_study as v2

EXTRA = ['fumble_vec', 'int', 'completion', 'pass_attempt', 'sack']


def v2_walk(tg, gm, fbs, finals):
    """the v2 regression prior (fit only on EARLIER seasons) walked forward week by week, as in cfb_v2_st_study.py"""
    tab = {}
    for y in range(2022, 2026):
        t = v2.features(y, finals[y - 1], fbs[y])
        t['t_o'] = t.team.map(lambda x: finals[y][0].get(x, 0.0)); t['t_d'] = t.team.map(lambda x: finals[y][1].get(x, 0.0)); tab[y] = t

    def prior_fn(y, _):
        if y <= 2022: return ({}, {})
        train = pd.concat([tab[k] for k in range(2022, y)]); X = train[v2.FEATS].values
        bo, bd = v2.ridge(X, train.t_o.values, v2.LAM), v2.ridge(X, train.t_d.values, v2.LAM)
        cur = tab[y]; Xc = np.c_[np.ones(len(cur)), cur[v2.FEATS].values]
        return (dict(zip(cur.team, Xc @ bo)), dict(zip(cur.team, Xc @ bd)))
    return st.walk_forward(tg, gm, fbs, prior_fn=prior_fn)


def score(df, col, mask, label):
    s = df[mask & (df.week >= 4)]; q = s.dropna(subset=['mkt'])
    X = np.c_[np.ones(len(q)), q.mkt, q[col] - q.mkt]; b = np.linalg.lstsq(X, q.hm, rcond=None)[0][2]
    wc, lc = sts.picks(s, col, 'mkt'); wo, lo = sts.picks(s, col, 'open')
    print(f'  {label:36s} miss {np.abs(q.hm - q[col]).mean():.3f} | weight on edge {b:.2f} | 5+ vs close {wc}-{lc} ({wc / max(wc + lc, 1) * 100:.1f}%) | 5+ vs open {wo}-{lo} ({wo / max(wo + lo, 1) * 100:.1f}%)')


def scrimmage(d):
    """per season: the scrimmage plays that st.load keeps (garbage time dropped, EPA capped), with the luck flags and the game info"""
    out = {}
    for y in st.YEARS:
        p = pd.read_parquet(f'{d}/pbp_{y}.parquet', columns=st.COLS + EXTRA); p = p[p.seasonType == 2]
        s = p[p.scrimmage_play & ~p.kneel_down & ~p.penalty_no_play]
        s = s[s.pos_score_diff_start.abs() <= s.period.map(st.GARBAGE).fillna(22)]
        out[y] = s.assign(epa=s.EPA.clip(-3, 3))
    return out


def tg_from(plays, gm, adjust):
    tgs = []
    for y, s in plays.items():
        s = s.copy(); s['epa'] = adjust(s)
        a = s.groupby(['game_id', 'pos_team_id', 'def_pos_team_id']).agg(plays=('epa', 'size'), epa_sum=('epa', 'sum')).reset_index(); a['season'] = y; tgs.append(a)
    tg = pd.concat(tgs).merge(gm[['game_id', 'week', 'homeTeamId', 'neutral_site']], on='game_id')
    tg['home_off'] = np.where(tg.neutral_site == True, 0, np.where(tg.pos_team_id == tg.homeTeamId, 1, -1)); tg['epa'] = tg.epa_sum / tg.plays
    return tg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='/tmp/cfbstudy'); ap.add_argument('--opens', default='/tmp/cfbstudy/opens_hist.json'); a = ap.parse_args()
    tg0, gm = st.load(a.dir); fbs = st.fbs_sets(gm, a.dir); YEARS = [2022, 2023, 2024, 2025]
    plays = scrimmage(a.dir); allp = pd.concat(plays.values())
    fum = allp.fumble_vec == True
    cls = ~fum & ((allp['int'] == True) | ((allp.pass_attempt == True) & (allp.completion != True) & (allp.sack != True)))
    E_f, E_c = float(allp.epa[fum].mean()), float(allp.epa[cls].mean())
    print(f'fumble plays: n={int(fum.sum())}, league average EPA {E_f:+.3f}; interception/incompletion plays: n={int(cls.sum())}, '
          f'interception share {float((allp["int"][cls] == True).mean()):.3f}, average EPA {E_c:+.3f}')

    def adj(mode):
        def f(s):
            e = s.epa.copy(); fm = s.fumble_vec == True
            if mode in ('F', 'FI', 'FI50'): e[fm] = E_f
            if mode in ('FI', 'FI50'):
                c = ~fm & ((s['int'] == True) | ((s.pass_attempt == True) & (s.completion != True) & (s.sack != True)))
                e[c] = E_c if mode == 'FI' else 0.5 * s.epa[c] + 0.5 * E_c
            return e
        return f
    order = [o for o in sts.game_order(gm, fbs, st.YEARS) if o[0] in YEARS]; ids = [o[1] for o in order]
    cols = {}
    for mode in ('base', 'F', 'FI', 'FI50'):
        tg = tg_from(plays, gm, adj(mode)); finals = {}; st.walk_forward(tg, gm, fbs, finals=finals)
        r = v2_walk(tg, gm, fbs, finals); r = r[r.season.isin(YEARS)].reset_index(drop=True); assert len(r) == len(order)
        cols[mode] = r; print('built', mode, flush=True)
    r0 = cols['base']
    df = pd.DataFrame(dict(game_id=ids, season=r0.season, week=r0.week, hm=r0.hm, mkt=r0.mkt))
    op = json.load(open(a.opens)); df['open'] = df.game_id.map(lambda i: -op[str(i)]['so'] if op.get(str(i)) and op[str(i)]['so'] is not None else np.nan)
    sts.order_weeks = dict(zip(df.game_id, df.week)); stg = sts.st_games(a.dir, YEARS)
    gap = sts.st_walk(order, stg, YEARS, sts.LAM, sts.CARRY); g = df.game_id.map(gap).fillna(0.0)
    for mode in cols: df[mode] = cols[mode].pred.values + sts.WEIGHT * g.values
    tune = df.season.isin([2022, 2023]).values
    for lab, mask in (('TUNE 2022-23', tune), ('TEST 2024-25 (read once)', ~tune), ('ALL 2022-25', np.ones(len(df), bool))):
        print(f'\n== {lab}  (weeks 4+)')
        for mode, name in (('base', 'current (v2 + special teams)'), ('F', 'fumbles luck-neutral'), ('FI', 'fumbles + interceptions luck-neutral'), ('FI50', 'fumbles + half of interceptions')):
            score(df, mode, mask, name)
    df.to_csv(os.path.join(a.dir, 'turnover_luck_rows.csv'), index=False)


if __name__ == '__main__':
    main()
