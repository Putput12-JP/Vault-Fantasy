#!/usr/bin/env python3
"""Round 2: rate teams on efficiency (net EPA per game from nflverse team weekly stats) instead of only the final score, which carries turnover and fumble luck.
Same rules as round 1: choose on 2010-2019, judge once on the 2020+ holdout against the closing spread. Live model holdout MAE 10.005, close 9.745.

  python3 scripts/explore_nfl_rebuild2.py --games games.csv --team-dir DIR   # DIR holds tw{season}.csv = stats_team_week_{season}.csv
"""
import argparse, csv, itertools, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_nfl_rebuild as B
import explore_nfl_rebuild as E


def load_epa(d):
    """(season, week, team) -> (net offensive EPA, turnovers lost)."""
    out = {}
    for y in range(B.WARM_FROM, 2027):
        p = os.path.join(d, f'tw{y}.csv')
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if r['season_type'] != 'REG': continue
            f = lambda k: B.fnum(r.get(k)) or 0.0
            out[(int(r['season']), int(r['week']), B.team(r['team']))] = (f('passing_epa') + f('rushing_epa'), f('passing_interceptions') + f('sack_fumbles_lost') + f('rushing_fumbles_lost') + f('receiving_fumbles_lost'))
    return out


def attach(games, epa):
    n = 0
    for g in games:
        h, a = epa.get((g['season'], g['week'], g['h'])), epa.get((g['season'], g['week'], g['a']))
        g['em'] = (h[0] - a[0]) if h and a else None
        g['to_diff'] = (a[1] - h[1]) if h and a else 0.0
        n += g['em'] is not None
    return n


def engine(games, K, b, s, m=0.0, KQ=0.03, repl=-1.0, use_qb=False, carry=0.6, hfa=2.0):
    """Update target = (1-b)*score margin + b*(s * net EPA margin), then (1-m)*that + m*close."""
    t, q, season = defaultdict(float), {}, None
    preds = []
    for g in games:
        if g['season'] != season:
            season = g['season']
            for k in t: t[k] *= carry
            for k in q: q[k] *= B.CARRY_Q
        qh = q.get(g['hq'], repl) if use_qb and g['hq'] else 0.0
        qa = q.get(g['aq'], repl) if use_qb and g['aq'] else 0.0
        pred = t[g['h']] + qh - t[g['a']] - qa + hfa
        preds.append(pred)
        eff = s * g['em'] + hfa if g['em'] is not None else g['res']       # EPA margin already includes home advantage in the raw score, so put it back on the same footing
        base = (1 - b) * g['res'] + b * eff
        err = (1 - m) * base + m * g['sp'] - pred
        t[g['h']] += K * err; t[g['a']] -= K * err
        if use_qb:
            if g['hq']: q[g['hq']] = qh + KQ * err
            if g['aq']: q[g['aq']] = qa - KQ * err
    return preds


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--games'); ap.add_argument('--team-dir', required=True)
    a = ap.parse_args(); games = B.load_games(a.games)
    print(f"{attach(games, load_epa(a.team_dir))} of {len(games)} games have EPA")
    # scale: regress final margin on net EPA margin using 2006-2009 only (before any tuning window)
    xs = [g['em'] for g in games if g['season'] <= 2009 and g['em'] is not None]; ys = [g['res'] for g in games if g['season'] <= 2009 and g['em'] is not None]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys); s = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    print(f'EPA margin to points scale s={s:.3f} (fit 2006-2009)')
    print('refs holdout 2020+: live 10.005, close', round(B.mae(games, [g['sp'] for g in games], *E.HOLD), 3), '\n')
    grid = list(itertools.product((0.045, 0.065, 0.085), (0.0, 0.3, 0.5, 0.7, 1.0), (0.0, 0.2, 0.4)))
    res = []
    for K, b, m in grid:
        p = engine(games, K, b, s, m=m); res.append((B.mae(games, p, *E.TUNE), K, b, m))
    res.sort(); print('top 5 on tune (K, b = EPA weight, m = market weight):')
    for r in res[:5]: print(f'  MAE {r[0]:.3f}  K={r[1]} b={r[2]} m={r[3]}')
    _, K, b, m = res[0]
    p = engine(games, K, b, s, m=m)
    print('\nchosen:', K, b, m); print(' ', E.line(games, p, 'EPA-informed TUNE', *E.TUNE)[1]); print(' ', E.line(games, p, 'EPA-informed HOLDOUT', *E.HOLD)[1])
    p0 = engine(games, K, 0.0, s, m=m); print(' ', E.line(games, p0, 'same K,m, scores only HOLDOUT', *E.HOLD)[1])
    for b2 in (0.3, 0.5, 0.7, 1.0):
        print(' ', E.line(games, engine(games, K, b2, s, m=m), f'  b={b2} HOLDOUT', *E.HOLD)[1])
    q = [(B.mae(games, engine(games, K, b, s, m=m, KQ=KQ, repl=r, use_qb=True), *E.TUNE), KQ, r) for KQ in (0.03, 0.06) for r in (-1.0, -2.0)]
    q.sort(); _, KQ, r = q[0]; pq = engine(games, K, b, s, m=m, KQ=KQ, repl=r, use_qb=True)
    print(f'\n+ QB (KQ={KQ}, repl={r}) tuned on 2010-19'); print(' ', E.line(games, pq, 'EPA + QB TUNE', *E.TUNE)[1]); print(' ', E.line(games, pq, 'EPA + QB HOLDOUT', *E.HOLD)[1])
    n = sum(1 for g in games if g['season'] >= 2020)
    print(f"\nSUMMARY holdout 2020+ (n={n}): live 10.005 | EPA-informed {B.mae(games, p, *E.HOLD):.3f} | EPA+QB {B.mae(games, pq, *E.HOLD):.3f} | close {B.mae(games, [g['sp'] for g in games], *E.HOLD):.3f}")


if __name__ == '__main__':
    main()
