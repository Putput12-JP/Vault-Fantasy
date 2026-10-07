#!/usr/bin/env python3
"""
Steals, blocks, turnovers and steals + blocks ("stocks") for the prop board.

Same projection walk as build_prop_model.py (minutes model, per-minute rate shrunk to the position prior, no usage
cascade for these stats), run on these four markets only so the existing model's numbers are untouched:
  mean      = minutes x rate           (steals + blocks = sum of the two means)
  P(over)   = negative binomial; variance = v0 + v1*mean + v2*mean^2 fit on the tune seasons (2023-24)

What it can and cannot say (written down before anyone bets on it):
  * ESPN carries steals and blocks as MAIN lines for 2025-26 only (the 2024-25 rows are alternate ladders), so there is no
    prior season to fit a calibration or a market blend on, and turnovers / steals + blocks have no book history at all.
  * So every market here is NO-GO: priced and shown on the board, never a gated best bet. The report below scores the
    model against ESPN's 2025-26 closing lines (Brier, log loss, and a +EV bet's hit rate) so the table can say how it did.
  * Kalshi lists none of these four.

  python3 nba/scripts/build_prop_model_stocks.py
Writes nba/data/prop_model_stocks.json and nba/docs/prop-model-stocks.md
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as P

P.BASE = {'stl': ['steals'], 'blk': ['blocks'], 'tov': ['turnovers']}
P.COMBO = {'sb': ['stl', 'blk']}
P.MARKETS = list(P.BASE) + list(P.COMBO)
P.COUNT_MKTS = set(P.MARKETS)

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'prop_model_stocks.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'prop-model-stocks.md')


def p_over(mkt, mu, line, V):
    return P.p_over(mkt, mu, line, V)


def final_rates(box, seasons):
    """Each player's per-minute rate state after the last game played, the walk's own recurrence (position prior, then EWMA),
    so tonight's mean is minutes x rate exactly as in the backtest. The page reads it as the model state's `r`."""
    rt = {}
    prior = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for g in C.games(seasons):
        for r in box.get(g['game_id'], []):
            if not r['played'] or r['minutes'] <= 0:
                continue
            aid, m = r['athlete_id'], r['minutes']
            pos = MM.group(r['pos'])
            for st, cols in P.BASE.items():
                prior[pos][st][0] += P.sv(r, cols)
                prior[pos][st][1] += m
            p = rt.get(aid)
            if p is None:
                p = rt[aid] = {'n': 0, 'rate': {st: prior[pos][st][0] / max(1.0, prior[pos][st][1]) for st in P.BASE}}
            a = max(P.RATE_ALPHA, 1 / (p['n'] + 1 + P.PRIOR_GAMES))
            w = min(1.0, m / 20.0)
            for st, cols in P.BASE.items():
                p['rate'][st] += a * w * (P.sv(r, cols) / m - p['rate'][st])
            p['n'] += 1
    return {str(aid): {st: round(v, 5) for st, v in p['rate'].items()} for aid, p in rt.items()}


def main():
    box = C.player_games(P.WARM + P.TUNE + P.TEST)
    inj = C.InjuryAsOf(P.TEST, C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = {}                                            # no usage cascade for these stats
    team_min = json.load(open(P.OUT_JSON))['team_min']   # the existing fit: same rotation rescale
    tr = P.walk(P.WARM + P.TUNE, box, None, P.TUNE[0], 'oracle', margins, mm, casc, team_min)
    V = P.fit_variance(tr)
    print('variance fits', V, flush=True)
    te = P.walk(P.WARM + P.TUNE + P.TEST, box, inj, P.TEST[0], 'report', margins, mm, casc, team_min)
    proj = {(r['gid'], r['aid']): r for r in te}
    print(f'projections: tune {len(tr):,}  test {len(te):,}', flush=True)

    acc = {}
    for mkt in P.MARKETS:
        e = [r['pred']['tip'][1][mkt] - r['y'][mkt] for r in te]
        acc[mkt] = {'mae': round(statistics.mean(abs(x) for x in e), 3), 'bias': round(statistics.mean(e), 3),
                    'mean_actual': round(statistics.mean(r['y'][mkt] for r in te), 3), 'n': len(e)}

    # ESPN 2025-26 main lines at the pre-tip close: model chance vs the book's no-vig chance
    rows = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if r['kind'] != 'main' or r['played'] != '1' or r['market'] not in P.MARKETS or r['season'] != '2026' or r['cur_is_pretip'] != '1':
            continue
        pr = proj.get((int(r['game_id']), int(r['athlete_id'])))
        po, pu = P.am_prob(r['over_px_cur']), P.am_prob(r['under_px_cur'])
        if not pr or not r['line_cur'] or po is None or pu is None or not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
            continue
        L, act = float(r['line_cur']), float(r['actual'])
        if act == L:
            continue
        mu = pr['pred']['tip'][1][r['market']]
        rows[r['market']].append({'pm': p_over(r['market'], mu, L, V), 'pk': po / (po + pu), 'over': act > L, 'line': L,
                                  'over_px': r['over_px_cur'], 'under_px': r['under_px_cur'], 'gid': r['game_id']})
    espn = {}
    for mkt, rs in rows.items():
        def ll(key):
            return -statistics.mean(math.log(max(1e-4, x[key] if x['over'] else 1 - x[key])) for x in rs)
        br = lambda key: statistics.mean((x[key] - x['over']) ** 2 for x in rs)
        # bet whichever side the model likes by 3+ points, at the book's price: a plain look, not a gate
        n = w = 0
        profit = 0.0
        for x in rs:
            e = x['pm'] - x['pk']
            if abs(e) < 0.03:
                continue
            over = e > 0
            gain = P.am_payout(x['over_px'] if over else x['under_px'])
            win = x['over'] if over else not x['over']
            profit += gain if win else -1.0
            n += 1
            w += win
        espn[mkt] = {'n_rows': len(rs), 'games': len({x['gid'] for x in rs}), 'brier_model': round(br('pm'), 4), 'brier_market': round(br('pk'), 4),
                     'logloss_model': round(ll('pm'), 4), 'logloss_market': round(ll('pk'), 4),
                     'bets_3pt': n, 'win_3pt': round(w / n, 4) if n else None, 'roi_3pt': round(profit / n, 4) if n else None}
        print(mkt, espn[mkt], flush=True)

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'variance': V, 'accuracy': acc, 'espn_2026': espn,
           'verdict': {m: 'NO-GO' for m in P.MARKETS},
           'rates': final_rates(box, P.WARM + P.TUNE + P.TEST),
           'why': 'No prior season of main-line prices to fit a calibration or a market blend on (ESPN steals/blocks main lines start in 2025-26), '
                  'no book history for turnovers or steals + blocks, and Kalshi lists none of them. Shown on the board, never a gated best bet.'}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    md = ['# Steals, blocks, turnovers and steals + blocks', '',
          f"Generated {res['generated']}. Same walk-forward projection as `build_prop_model.py`; these markets only.", '',
          '## Verdict: NO-GO for all four', '', res['why'], '', '## Projection accuracy (2025-26, injury report 30 min pre-tip)', '',
          '| market | MAE | bias | mean actual | player-games |', '|---|---|---|---|---|']
    md += [f"| {m} | {a['mae']} | {a['bias']} | {a['mean_actual']} | {a['n']:,} |" for m, a in acc.items()]
    md += ['', '## Against ESPN 2025-26 closing lines (main lines only)', '',
           '| market | rows | games | Brier model | Brier market | log loss model | log loss market | bets at 3+ pts | win | ROI |', '|---|---|---|---|---|---|---|---|---|---|']
    md += [f"| {m} | {e['n_rows']:,} | {e['games']} | {e['brier_model']} | {e['brier_market']} | {e['logloss_model']} | {e['logloss_market']} | {e['bets_3pt']} | {e['win_3pt']} | {e['roi_3pt']} |" for m, e in espn.items()]
    md += ['', 'Variance fits (v0, v1, v2): ' + json.dumps(V), '']
    open(OUT_MD, 'w').write('\n'.join(md))
    print('wrote', OUT_JSON)


if __name__ == '__main__':
    main()
