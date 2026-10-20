#!/usr/bin/env python3
"""
Section D of docs/preseason-signals-test.md: the live read. Descriptive, not tested.

Fits the minutes and rate models on 2023-24 to 2025-26 (all three seasons), projects what the 2026-27 preseason
changes for each veteran (delta vs a last-season-only projection), and lines it up with the recorder's board
(origin/nba-live board.json, passed as a path). Also the team-level three-point-share carry the thread cites.

  nba/.venv/bin/python nba/scripts/build_preseason_live.py BOARD.json
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_preseason_signals as B
import build_preseason_market as M

LIVE = 2027


def main():
    board = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else None
    d, pre, bad = B.build_table()
    P, T, _ = B.load_pre()
    rs26 = B.agg_rs(B.load_rs(2026))
    ps = pre[pre.season == LIVE].set_index('pid')
    te = ps.join(rs26.add_prefix('L_'), how='left')
    te = te[(te.box_min >= 40)]
    tr = d[(d.L_min >= 400) & (d.box_min >= 40)]
    te_v = te[te.L_min >= 400].copy()
    te_v = te_v.reset_index()
    te_v, coefs = M.project_with(tr, te_v)
    te_v = te_v.set_index('pid')
    out = {'coefs': coefs, 'n_vets': int(len(te_v))}
    # ---- who the preseason says moved (minutes)
    te_v['d_min'] = te_v.M1 - te_v.M0
    cols = ['name', 'team', 'n', 'starts', 'h1_min', 'mpg_1h', 'L_mpg', 'M0', 'M1', 'd_min', 'd_pts', 'd_reb', 'd_ast', 'd_3pm']
    movers_min = te_v.reindex(te_v.d_min.abs().sort_values(ascending=False).index)[cols].head(20).round(2)
    # ---- rate movers (largest |delta| in the five stat projections, relative to last-season level)
    out['movers_minutes'] = movers_min.reset_index().to_dict('records')
    rows = []
    if board:
        names = board['players']
        by = {}
        for pr in board['props']:
            if pr['s'] not in ('pts', 'reb', 'ast', '3pm', 'pra'):
                continue
            lines = [b[1] for b in pr.get('books', []) if b[1] is not None]
            if not lines:
                continue
            by.setdefault((str(pr['p']), pr['s']), []).append((float(np.median(lines)), pr['g']))
        gmap = {g['id']: g for g in board['games']}
        for (pid, st), lst in by.items():
            if pid not in te_v.index:
                continue
            line, gid = lst[0]
            r = te_v.loc[pid]
            dl = r['d_' + st]
            rows.append({'player': r['name'], 'team': r['team'], 'stat': st, 'line': line, 'delta': float(dl),
                         'rel': float(dl / line), 'mu0': float(r['mu0_' + st]), 'M0': float(r.M0), 'M1': float(r.M1),
                         'pre_games': int(r.n), 'h1_min': float(r.h1_min), 'starts': int(r.starts),
                         'game_day': gmap.get(gid, {}).get('day')})
    live = pd.DataFrame(rows)
    if len(live):
        live = live.sort_values('rel', key=np.abs, ascending=False)
        out['live_flags'] = live.head(40).round(3).to_dict('records')
        out['live_rows'] = int(len(live))
        out['top_third_cut'] = 0.1029
    # ---- team three-point share: does preseason 3PA share carry into the season? (90 team-seasons)
    t = T.copy()
    t = t.groupby(['season', 'team']).agg(h1_fg3a=('h1_fg3a', 'sum'), h1_fga=('h1_fga', 'sum'), g=('game_id', 'nunique')).reset_index()
    t['share'] = t.h1_fg3a / t.h1_fga
    rsT = {}
    for y in (2023, 2024, 2025, 2026):
        tb = pd.read_csv(os.path.join(B.RAW, 'hoopr', f'team_box_{y}.csv'), low_memory=False)
        tb = tb[tb.season_type == 2]
        g = tb.groupby('team_id').agg(a=('three_point_field_goals_attempted', 'sum'), f=('field_goals_attempted', 'sum'))
        rsT[y] = (g.a / g.f)
    t['team'] = t.team.astype(int)
    t['rs'] = [rsT[s].get(tm) if s in rsT else np.nan for s, tm in zip(t.season, t.team)]
    t['last'] = [rsT[s - 1].get(tm) if (s - 1) in rsT else np.nan for s, tm in zip(t.season, t.team)]
    tt = t[(t.season.isin([2024, 2025, 2026])) & t.rs.notna() & t['last'].notna()].copy()
    out['team_3pa'] = {'n': int(len(tt)), 'corr_level': float(np.corrcoef(tt.share, tt.rs)[0, 1]),
                       'corr_change': float(np.corrcoef(tt.share - tt['last'], tt.rs - tt['last'])[0, 1])}
    # Orlando and the biggest team risers this preseason
    cur = t[t.season == LIVE].copy()
    cur['last'] = [rsT[2026].get(tm) for tm in cur.team]
    cur['chg'] = cur.share - cur['last']
    out['team_3pa_live_top'] = cur.sort_values('chg', ascending=False).head(6)[['team', 'g', 'share', 'last', 'chg']].round(3).to_dict('records')
    with open(os.path.join(B.DATA, 'preseason_live.json'), 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print('team 3PA share carry:', out['team_3pa'])
    print('live top team risers (3PA share 1H preseason vs last RS):', out['team_3pa_live_top'])
    print('\nminutes movers (preseason says early-season minutes differ from last-season-only):')
    print(movers_min.to_string())
    if len(live):
        print('\nlive flags vs tonight/next-days lines (rel = delta / line; top-third cut was 0.103):')
        print(live.head(30).round(2).to_string(index=False))
        print('rows at or above the cut:', int((live.rel.abs() >= 0.1029).sum()), 'of', len(live))


if __name__ == '__main__':
    main()
