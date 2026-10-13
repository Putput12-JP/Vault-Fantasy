"""Reproducible backtest of the JP+ totals line: walk 2021-2025 with cfb_model.totals_walk_forward (in-season league level, ridges refit each week on
earlier weeks only), then grade weeks 4+ of 2023-2025 against the Bovada open total and measure CLV against the Bovada close.

  python3 scripts/cfb_totals_backtest.py --dir /path/with/pbp_YYYY.parquet+sched_YYYY.parquet+teams.csv --lines /path/with/lines_2023.json lines_2024.json lines_2025.json [--json out.json]

The lines files are CollegeFootballData /lines dumps (one game per element, `lines` = per-provider list with overUnder and overUnderOpen); they are large
and are not committed. Prints the dict that goes into cfb_model.TOT_BACKTEST."""
import argparse, json, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfb_efficiency_study as st
import cfb_model as cm

SEASONS = (2023, 2024, 2025)


def bovada(lines_dir, seasons=SEASONS):
    """game id -> (Bovada open, Bovada close); only games with a stored Bovada open"""
    out = {}
    for y in seasons:
        for g in json.load(open(os.path.join(lines_dir, f'lines_{y}.json'))):
            for l in g.get('lines') or []:
                if l['provider'] == 'Bovada' and l.get('overUnderOpen') is not None: out[g['id']] = (float(l['overUnderOpen']), None if l.get('overUnder') is None else float(l['overUnder']))
    return out


def record(df, t):
    """W-L-P against the open, under share, CLV mean and z for picks with |edge| >= t"""
    d = df[df.edge.abs() >= t]; sg = np.sign(d.edge); r = (d.total - d.op) * sg
    w, l = int((r > 0).sum()), int((r < 0).sum()); n = w + l
    c = ((d.cl - d.op) * sg).dropna(); sd = float(c.std(ddof=1)) if len(c) > 1 else 0.0
    return dict(n=int(len(d)), open=[w, l], pushed=int((r == 0).sum()), pct=round(w / n, 4) if n else None, z=round((w / n - 0.5) / math.sqrt(0.25 / n), 2) if n else None,
                clv=round(float(c.mean()), 3), clv_n=int(len(c)), clv_z=round(float(c.mean()) / (sd / math.sqrt(len(c))), 2) if len(c) > 2 and sd > 0 else None,
                under_share=round(float((d.edge < 0).mean()), 3) if len(d) else None)


def run(d, lines_dir):
    tt, gm = cm.totals_load(d, st.YEARS); fbs = st.fbs_sets(gm, d)
    res = cm.totals_walk_forward(tt, gm, fbs, st.YEARS)
    B = bovada(lines_dir)
    res['op'] = res.game_id.map(lambda g: B.get(g, (np.nan, np.nan))[0]); res['cl'] = res.game_id.map(lambda g: B.get(g, (np.nan, np.nan))[1])
    x = res[res.season.isin(SEASONS) & (res.week >= cm.PICK_MIN_WEEK) & res.op.notna()].copy()
    x['edge'] = x.model_total - x.op
    return res, x


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', required=True); ap.add_argument('--lines', required=True); ap.add_argument('--json'); a = ap.parse_args()
    res, x = run(a.dir, a.lines)
    r3, r5 = record(x, 3), record(x, 5)
    out = dict(seasons='2023-2025', n3=r3['n'], open3=r3['open'], clv3=r3['clv'], clv3_z=r3['clv_z'], under3=r3['under_share'],
               n5=r5['n'], open5=r5['open'], clv5=r5['clv'], clv5_z=r5['clv_z'], under5=r5['under_share'], games=int(len(x)),
               mae_open=round(float((x.total - x.op).abs().mean()), 3), mae_model=round(float((x.total - x.model_total).abs().mean()), 3),
               note='Bovada open total, weeks 4+, in-season league level, model fit on 2022 only (scripts/cfb_totals_backtest.py)')
    print(json.dumps(dict(summary=out, edge3=r3, edge5=r5), indent=1))
    if a.json: json.dump(out, open(a.json, 'w'), indent=1)
    return res, x


if __name__ == '__main__':
    main()
