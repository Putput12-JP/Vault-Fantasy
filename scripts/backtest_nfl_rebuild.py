#!/usr/bin/env python3
"""Walk-forward backtest of an NFL spread model rebuild, graded against the CLOSING spread.

Each variant adds ONE term to the last, so every result is attributable:
  V0  base         team margin ratings + flat home field (the current model's shape)
  V1  + QB gap     each starting QB carries a rating; team rating = team part + QB part
  V2  + situation  ridge-fit rest / bye / division / dome / turf / wind / cold terms
  V3  + market     shrink the V2 gap toward the closing line by a fitted coefficient c

Rules that keep it honest:
  - A game is predicted BEFORE it updates any rating. Starters are the actual starters (known at kickoff, so the closing line knows them too).
  - Hyperparameters are chosen on 2006-2013 only. Situational and market coefficients are refit each season on earlier seasons only.
  - Graded 2014+ against nflverse spread_line at flat -110 (break-even 52.38%). Pushes are excluded.

  python3 scripts/backtest_nfl_rebuild.py [--games games.csv] [--out data/nfl_rebuild_backtest.json]

Stdlib only.
"""
import argparse, csv, io, json, math, os, ssl, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
ALIAS = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX'}
BREAKEVEN = 110 / 210
TEST_FROM = 2014
TUNE_TO = 2013
WARM_FROM = 2006
HFA = 2.0
CARRY_T, CARRY_Q = 0.72, 0.85
FEATS = ['bye_h', 'bye_a', 'short_h', 'short_a', 'div', 'dome', 'turf', 'wind15', 'cold']


def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def team(t): return ALIAS.get(t, t)


def load_games(path):
    if path and os.path.exists(path): text = open(path, encoding='utf-8').read()
    else:
        import urllib.request
        ctx = ssl.create_default_context()
        text = urllib.request.urlopen(urllib.request.Request(GAMES_URL, headers={'User-Agent': 'Mozilla/5.0'}), timeout=90, context=ctx).read().decode('utf-8')
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r['game_type'] != 'REG' or int(r['season']) < WARM_FROM: continue
        res, sp = fnum(r['result']), fnum(r['spread_line'])
        if res is None or sp is None: continue
        roof, surf = (r['roof'] or '').lower(), (r['surface'] or '').lower()
        temp, wind = fnum(r['temp']), fnum(r['wind'])
        hr, ar = fnum(r['home_rest']) or 7, fnum(r['away_rest']) or 7
        dome = roof in ('dome', 'closed')
        out.append(dict(season=int(r['season']), week=int(r['week']), gid=r['game_id'], h=team(r['home_team']), a=team(r['away_team']),
                        res=res, sp=sp, hq=r['home_qb_id'] or None, aq=r['away_qb_id'] or None,
                        x=[float(hr >= 10), float(ar >= 10), float(hr <= 5), float(ar <= 5), float(r['div_game'] == '1'), float(dome),
                           float('turf' in surf or surf in ('astroturf', 'fieldturf', 'sportturf', 'a_turf', 'astroplay', 'matrixturf')),
                           float(not dome and wind is not None and wind >= 15), float(not dome and temp is not None and temp <= 32)]))
    out.sort(key=lambda g: (g['season'], g['week'], g['gid']))
    return out


def run_ratings(games, K, KQ, repl, use_qb):
    """Walk forward. Returns per-game list of (V0 or V1 prediction) made before the game updates anything."""
    t, q = defaultdict(float), {}
    preds, season = [], None
    for g in games:
        if g['season'] != season:
            season = g['season']
            for k in t: t[k] *= CARRY_T
            for k in q: q[k] *= CARRY_Q
        qh = q.get(g['hq'], repl) if use_qb and g['hq'] else 0.0
        qa = q.get(g['aq'], repl) if use_qb and g['aq'] else 0.0
        pred = t[g['h']] + qh - t[g['a']] - qa + HFA
        preds.append(pred)
        err = g['res'] - pred
        t[g['h']] += K * err; t[g['a']] -= K * err
        if use_qb:
            if g['hq']: q[g['hq']] = qh + KQ * err
            if g['aq']: q[g['aq']] = qa - KQ * err
    return preds


def mae(games, preds, lo, hi):
    e = [abs(g['res'] - p) for g, p in zip(games, preds) if lo <= g['season'] <= hi]
    return sum(e) / len(e)


def ols(X, y, ridge):
    n, k = len(X[0]), len(X[0])
    A = [[sum(r[i] * r[j] for r in X) + (ridge if i == j else 0.0) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * yy for r, yy in zip(X, y)) for i in range(n)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(A[r][i])); A[i], A[piv] = A[piv], A[i]; b[i], b[piv] = b[piv], b[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n): A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    w = [0.0] * n
    for i in reversed(range(n)): w[i] = (b[i] - sum(A[i][c] * w[c] for c in range(i + 1, n))) / A[i][i]
    return w


def wilson(w, n, z=1.96):
    if not n: return [0, 0]
    p = w / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def grade(games, preds, lo, hi, thr):
    """Picks = games where model and closing spread differ by >= thr. Returns [wins, losses, pushes]."""
    w = l = p = 0
    for g, pr in zip(games, preds):
        if not lo <= g['season'] <= hi: continue
        gap = pr - g['sp']                       # + = model likes home more than the market does
        if abs(gap) < thr: continue
        cover = g['res'] - g['sp']
        if cover == 0: p += 1
        elif (cover > 0) == (gap > 0): w += 1
        else: l += 1
    return [w, l, p]


def summarize(games, preds, name, lo=TEST_FROM, hi=9999):
    out = dict(name=name, n=sum(1 for g in games if lo <= g['season'] <= hi),
               mae_model=round(mae(games, preds, lo, hi), 3), mae_market=round(mae(games, [g['sp'] for g in games], lo, hi), 3), bands={})
    for thr in (1.0, 1.5, 3.0, 5.0):
        w, l, p = grade(games, preds, lo, hi, thr); n = w + l
        out['bands'][str(thr)] = dict(record=[w, l], pushes=p, n=n, win_pct=round(w / n, 4) if n else None, ci95=wilson(w, n),
                                      roi_pct=round(100 * (w * (100 / 110) - l) / n, 2) if n else None)
    # slope of (actual - market) on (model - market): does the model add information beyond the close
    xs = [pr - g['sp'] for g, pr in zip(games, preds) if lo <= g['season'] <= hi]
    ys = [g['res'] - g['sp'] for g in games if lo <= g['season'] <= hi]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs); c = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = [(y - my) - c * (x - mx) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(r * r for r in resid) / (len(xs) - 2) / sxx)
    out['info_slope'] = dict(c=round(c, 3), se=round(se, 3), t=round(c / se, 2))
    out['by_season_3pt'] = {}
    for s in sorted({g['season'] for g in games if lo <= g['season'] <= hi}):
        w, l, _ = grade(games, preds, s, s, 3.0); out['by_season_3pt'][str(s)] = [w, l]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games'); ap.add_argument('--out', default=os.path.join(ROOT, 'data', 'nfl_rebuild_backtest.json'))
    a = ap.parse_args()
    games = load_games(a.games)
    print(f'{len(games)} regular-season games with a closing spread, {games[0]["season"]}-{games[-1]["season"]}')

    # tune on 2010-2013 only (ratings warm up from 2006)
    best = None
    for K in (0.045, 0.065):
        for KQ in (0.03, 0.06, 0.10):
            for repl in (-2.0, -1.0, 0.0):
                m = mae(games, run_ratings(games, K, KQ, repl, True), 2010, TUNE_TO)
                if best is None or m < best[0]: best = (m, K, KQ, repl)
    k0 = min((mae(games, run_ratings(games, K, 0, 0, False), 2010, TUNE_TO), K) for K in (0.045, 0.065, 0.085))
    print(f'tuned on 2010-{TUNE_TO}: V0 K={k0[1]} (MAE {k0[0]:.3f}); V1 K={best[1]} KQ={best[2]} repl={best[3]} (MAE {best[0]:.3f})')
    v0 = run_ratings(games, k0[1], 0, 0, False)
    v1 = run_ratings(games, best[1], best[2], best[3], True)

    # V2: situational terms, refit each season on earlier seasons' V1 residuals
    v2 = list(v1); coef_by_season = {}
    for s in sorted({g['season'] for g in games if g['season'] >= TEST_FROM}):
        tr = [(g['x'], g['res'] - p) for g, p in zip(games, v1) if 2008 <= g['season'] < s]
        w = ols([x for x, _ in tr], [y for _, y in tr], ridge=len(tr) * 0.02)
        coef_by_season[s] = dict(zip(FEATS, [round(c, 3) for c in w]))
        for i, g in enumerate(games):
            if g['season'] == s: v2[i] = v1[i] + sum(c * xv for c, xv in zip(w, g['x']))

    # V3: market regression, c refit each season on earlier seasons (clamped 0..1); ordering of picks is unchanged, so the info is in c and MAE
    v3 = list(v2); c_by_season = {}
    for s in sorted({g['season'] for g in games if g['season'] >= TEST_FROM}):
        tr = [(p - g['sp'], g['res'] - g['sp']) for g, p in zip(games, v2) if 2010 <= g['season'] < s]
        mx = sum(x for x, _ in tr) / len(tr); my = sum(y for _, y in tr) / len(tr)
        c = max(0.0, min(1.0, sum((x - mx) * (y - my) for x, y in tr) / sum((x - mx) ** 2 for x, _ in tr)))
        c_by_season[s] = round(c, 3)
        for i, g in enumerate(games):
            if g['season'] == s: v3[i] = g['sp'] + c * (v2[i] - g['sp'])

    # V3 shrinks every gap by the same c, so its picks are V2's picks: grade the bands on the raw V2 gap, report V3's MAE and slope on its own numbers
    r3 = summarize(games, v3, 'V3 + market regression')
    r2 = summarize(games, v2, 'V2 + situational')
    r3['bands'] = r2['bands']; r3['by_season_3pt'] = r2['by_season_3pt']
    r3['note'] = 'bands are V2 picks (a uniform shrink does not change which side or which games); MAE is the blended number'
    results = [summarize(games, v0, 'V0 base ratings'), summarize(games, v1, 'V1 + QB gap'), r2, r3]
    for r in results:
        print(f"\n{r['name']}: n={r['n']}  MAE model {r['mae_model']} vs market {r['mae_market']}  info slope c={r['info_slope']['c']} (se {r['info_slope']['se']}, t={r['info_slope']['t']})")
        for thr, b in r['bands'].items():
            print(f"  gap>={thr:>3}: {b['record'][0]}-{b['record'][1]} n={b['n']}  {b['win_pct']}  CI95 {b['ci95']}  ROI {b['roi_pct']}%")
    print('\nmarket-regression c by season:', c_by_season)
    json.dump(dict(generated_for='closing spread, flat -110, break-even 52.38%', test_from=TEST_FROM, tuned=dict(v0_K=k0[1], v1_K=best[1], v1_KQ=best[2], v1_repl=best[3]),
                   situational_coef=coef_by_season, market_c=c_by_season, results=results), open(a.out, 'w'), indent=1)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
