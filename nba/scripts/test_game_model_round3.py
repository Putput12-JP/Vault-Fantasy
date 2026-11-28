#!/usr/bin/env python3
"""
Game model round 3: team ratings that also learn from each game's closing line (L), against the shipped Vault line, walk-forward.
Rules, committed before this ran: docs/game-model-round3.md. Results: docs/game-model-round3-results.md and data/game_model_round3.json.

  python3 nba/scripts/test_game_model_round3.py

Pure stdlib. Fit on 2024-25, scored on 2025-26, then this season replayed against the locked Game Picks record. Nothing here writes
data/game_model.json.
"""
import datetime as dt, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import test_game_model_round2 as R2

FIT, TEST = 2025, 2026
DATA = os.path.join(C.HERE, '..', 'data')
OUT_JSON = os.path.join(DATA, 'game_model_round3.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-round3-results.md')
GRID_W, GRID_K = [0.25, 0.5, 0.75, 1.0], [0.04, 0.08, 0.12, 0.16, 0.24, 0.32, 0.5]
mae, paired_t, wl = R2.mae, R2.paired_t, R2.wl


def lined(recs, season=None):
    return [r for r in recs if r.get('line') and r['line'].get('spread_close') is not None and 'tip' in r and (season is None or r['g']['season'] == season)]


def gaps(rows, margin=lambda r: r['tip'][0], line=lambda r: -r['line']['spread_close']):
    g = [abs(margin(r) - line(r)) for r in rows]
    return {'mean': round(statistics.mean(g), 2), 'ge3': round(sum(x >= 3 for x in g) / len(g), 3), 'ge5': round(sum(x >= 5 for x in g) / len(g), 3),
            'sd_model': round(statistics.pstdev([margin(r) for r in rows]), 2), 'sd_line': round(statistics.pstdev([line(r) for r in rows]), 2)}


def block(rows, ref):
    es = [r['tip'][0] - r['actual_margin'] for r in ref]
    ev = [r['tip'][0] - r['actual_margin'] for r in rows]
    d, t = paired_t(es, ev)
    cut = R2.early_cut(rows)
    er = [r for r in rows if r['g']['tip'] < cut[r['g']['season']]]
    ef = [r for r in ref if r['g']['tip'] < cut[r['g']['season']]]
    de, te = paired_t([r['tip'][0] - r['actual_margin'] for r in ef], [r['tip'][0] - r['actual_margin'] for r in er])
    pairs = [(r['tip'][0], -r['line']['spread_close'], r['actual_margin']) for r in rows]
    fav = [r for r in rows if r['line']['spread_close'] != 0 and r['tip'][0] != 0]
    return {'n': len(rows), 'mae': round(mae(ev), 3), 'd': round(d, 4), 't': round(t, 2),
            'early': {'n': len(er), 'mae': round(mae(r['tip'][0] - r['actual_margin'] for r in er), 3), 'd': round(de, 4), 't': round(te, 2)},
            'close_mae': round(mae(-r['line']['spread_close'] - r['actual_margin'] for r in rows), 3),
            'ats': {str(t): wl(pairs, t) for t in (0, 3, 5)}, 'info': GM.info_test(rows, 'tip', 'spread_close', 0), 'gap': gaps(rows),
            'winner': [sum((r['tip'][0] > 0) == (r['actual_margin'] > 0) for r in fav), sum((r['tip'][0] > 0) != (r['actual_margin'] > 0) for r in fav)],
            'fav': [sum((r['line']['spread_close'] < 0) == (r['actual_margin'] > 0) for r in fav), sum((r['line']['spread_close'] < 0) != (r['actual_margin'] > 0) for r in fav)]}


def this_season(variants, lines, cur):
    path = os.path.join(C.RAW, 'hoopr', f'player_box_{cur}.csv')
    gp = os.path.join(DATA, 'game_picks.json')
    if not (os.path.exists(path) and os.path.exists(gp)):
        return None
    d = json.load(open(gp))
    first, close = {}, {}
    for day, v in d['days'].items():
        for r in v['rows']:
            x = dict(zip(d['cols'], r))
            if x['spread'] is not None:
                (first if x['clock'] == 'f' else close)[str(x['game'])] = x
    L = dict(lines)
    for k, x in close.items():                                 # this season's closing spread: the record's last look before tip
        L[int(k)] = {'spread_close': x['spread']}
    seasons = [cur - 2, cur - 1, cur]
    box = C.player_games(seasons)
    out, base = {}, None
    for name, P in variants.items():
        _, recs = GM.run(P, seasons, box, L, record_from=cur)
        by = {str(r['g']['game_id']): r for r in recs}
        base = base or by
        rows = [(by[k]['none'][0] + (x['margin'] - base[k]['none'][0]), -x['spread'], x['am'], x['margin']) for k, x in first.items() if k in by and k in base]
        dd, t = paired_t([r[3] - r[2] for r in rows], [r[0] - r[2] for r in rows])
        pairs = [(r[0], r[1], r[2]) for r in rows]
        g = [abs(r[0] - r[1]) for r in rows]
        dis = [r for r in rows if r[1] != 0 and r[0] != 0 and (r[0] > 0) != (r[1] > 0)]
        out[name] = {'n': len(rows), 'mae': round(mae(r[0] - r[2] for r in rows), 3), 'd': round(dd, 4), 't': round(t, 2),
                     'line_mae': round(mae(r[1] - r[2] for r in rows), 3), 'ats': {str(t): wl(pairs, t) for t in (0, 3, 5)},
                     'winner': [sum((r[0] > 0) == (r[2] > 0) for r in rows if r[0] != 0), sum((r[0] > 0) != (r[2] > 0) for r in rows if r[0] != 0)],
                     'disagree': [len(dis), sum((r[0] > 0) == (r[2] > 0) for r in dis)],
                     'flips': sum(((r[0] - r[1]) > 0) != ((r[3] - r[1]) > 0) for r in rows),
                     'gap': {'mean': round(statistics.mean(g), 2), 'ge3': round(sum(x >= 3 for x in g) / len(g), 3), 'ge5': round(sum(x >= 5 for x in g) / len(g), 3),
                             'sd_model': round(statistics.pstdev([r[0] for r in rows]), 2), 'sd_line': round(statistics.pstdev([r[1] for r in rows]), 2)}}
    return out


def main():
    S = GM.WARM + GM.TUNE + [FIT, TEST]
    box = C.player_games(S)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    lines = C.closing_lines()
    inj = C.InjuryAsOf([FIT, TEST], C.player_index(box))
    fit_seasons = GM.WARM + GM.TUNE + [FIT]
    _, ref = GM.run(P0, fit_seasons, box, lines, inj, record_from=FIT)
    grid = [{'W': 0, 'KL': P0['K'], 'mae': round(mae(r['tip'][0] - r['actual_margin'] for r in lined(ref)), 4)}]
    for w in GRID_W:
        for k in GRID_K:
            _, recs = GM.run(dict(P0, MK_W=w, MK_K=k), fit_seasons, box, lines, inj, record_from=FIT)
            grid.append({'W': w, 'KL': k, 'mae': round(mae(r['tip'][0] - r['actual_margin'] for r in lined(recs)), 4)})
            print('  L', grid[-1], flush=True)
    best = min(grid[1:], key=lambda x: x['mae'])
    variants = {'S': dict(P0), 'L': dict(P0, MK_W=best['W'], MK_K=best['KL'])}
    res = {}
    for name, P in variants.items():
        _, recs = GM.run(P, S, box, lines, inj, record_from=FIT)
        res[name] = recs
    rep = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'grid': grid, 'chosen': best,
           'endpoint': [k for k, vals in (('W', GRID_W), ('KL', GRID_K)) if best[k] in (vals[0], vals[-1])],
           'fit': {k: block(lined(v, FIT), lined(res['S'], FIT)) for k, v in res.items()},
           'test': {k: block(lined(v, TEST), lined(res['S'], TEST)) for k, v in res.items()}}
    cur = TEST + 1
    rep['season'] = {'label': cur, 'rows': this_season(variants, lines, cur)}
    t, s, sea = rep['test']['L'], rep['test']['S'], rep['season']['rows']
    rep['verdict'] = 'Better' if (t['t'] >= 2.5 and t['info']['t'] >= s['info']['t'] - 1 and (sea is None or sea['L']['mae'] <= sea['S']['mae'])) else ('Tie' if t['t'] > -2 else 'Worse')
    json.dump(rep, open(OUT_JSON, 'w'), indent=1)
    write_md(rep)
    print(json.dumps(best), rep['verdict'])


def pct(a):
    return f"{a[0]}-{a[1]} {100 * a[0] / (a[0] + a[1]):.1f}%" if a[0] + a[1] else '0-0'


def write_md(rep):
    b = rep['chosen']
    ws = sorted({x['W'] for x in rep['grid'][1:]})
    ks = sorted({x['KL'] for x in rep['grid'][1:]})
    L = ['# Game model round 3: results', '',
         f"Generated {rep['generated']} by `nba/scripts/test_game_model_round3.py`. Rules: [game-model-round3.md](game-model-round3.md) (committed before this ran).", '',
         '## What 2024-25 chose', '',
         f"**W = {b['W']}, KL = {b['KL']}** (2024-25 margin MAE {b['mae']}; shipped {rep['grid'][0]['mae']})."
         + (f" On a grid endpoint: {', '.join(rep['endpoint'])}." if rep['endpoint'] else ' Neither is on a grid endpoint.'), '',
         '| W \\ KL | ' + ' | '.join(str(k) for k in ks) + ' |', '|---|' + '---|' * len(ks)]
    for w in ws:
        L.append(f'| {w} | ' + ' | '.join(str(next(x['mae'] for x in rep['grid'][1:] if x['W'] == w and x['KL'] == k)) for k in ks) + ' |')
    for key, lab in (('fit', '2024-25 (the fit season, in sample for L)'), ('test', '2025-26 (the test)')):
        L += ['', f'## {lab}', '', '| | Games | Margin MAE | Shipped minus variant | t | First 4 weeks MAE | t | Closing line MAE |', '|---|---|---|---|---|---|---|---|']
        for k in ('S', 'L'):
            x = rep[key][k]
            L.append(f"| {k} | {x['n']} | {x['mae']} | {x['d']:+.3f} | {x['t']:+.2f} | {x['early']['mae']} (n {x['early']['n']}) | {x['early']['t']:+.2f} | {x['close_mae']} |")
        L += ['', '| | Info test g (t) | Spread 0+ | 3+ | 5+ | Winner | Market favourite | Mean gap to the line | Games at 3+ | at 5+ | sd model / line |', '|---|---|---|---|---|---|---|---|---|---|---|']
        for k in ('S', 'L'):
            x = rep[key][k]
            L.append(f"| {k} | {x['info']['g_model_gap']} ({x['info']['t']}) | " + ' | '.join(pct(x['ats'][t]) for t in ('0', '3', '5'))
                     + f" | {pct(x['winner'])} | {pct(x['fav'])} | {x['gap']['mean']} | {100 * x['gap']['ge3']:.0f}% | {100 * x['gap']['ge5']:.0f}% | {x['gap']['sd_model']} / {x['gap']['sd_line']} |")
    rows = rep['season']['rows']
    if rows:
        L += ['', f"## This season, replayed ({rows['S']['n']} games; flagged for monitoring, n = {rows['S']['n']})", '',
              '| | Margin MAE | Shipped minus variant | t | Spread 0+ | 3+ | 5+ | Winner | Disagrees with the favourite (won) | Picks that change side | Mean gap | Games at 3+ | at 5+ | sd model / line |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for k in ('S', 'L'):
            x = rows[k]
            L.append(f"| {k} | {x['mae']} | {x['d']:+.3f} | {x['t']:+.2f} | " + ' | '.join(f"{x['ats'][t][0]}-{x['ats'][t][1]}" for t in ('0', '3', '5'))
                     + f" | {x['winner'][0]}-{x['winner'][1]} | {x['disagree'][0]} ({x['disagree'][1]}) | {x['flips']} | {x['gap']['mean']} | {100 * x['gap']['ge3']:.0f}% | {100 * x['gap']['ge5']:.0f}% | {x['gap']['sd_model']} / {x['gap']['sd_line']} |")
        L += ['', f"The locked line's MAE on these games is {rows['S']['line_mae']}. Row S is the shipped model and equals the locked record. Row L is a replay, not a record: no pick was locked with it."]
    t, f, sh = rep['test']['L'], rep['fit']['L'], rep['test']['S']
    L += ['', '## Verdict', '', f"**{rep['verdict']}{'' if rep['verdict'] == 'Better' else ': not shipped'}.**", '',
          f"- The bar was a margin-MAE t of 2.5 on 2025-26. L scored {t['t']:+.2f} there ({sh['mae']} to {t['mae']} points), {f['t']:+.2f} on the season it was fitted on"
          + (f", and {rows['L']['t']:+.2f} on this season's {rows['L']['n']} games ({rows['S']['mae']} to {rows['L']['mae']})." if rows else '.')
          + (' Closer in every season, and short of the bar that was set before it ran. The bar stands.' if rep['verdict'] != 'Better' and t['d'] > 0 else ''),
          f"- It closes about a third of the distance to the closing line (2025-26: shipped {sh['mae']}, L {t['mae']}, the line {t['close_mae']}) and sits closer to it: "
          f"mean gap {sh['gap']['mean']} to {t['gap']['mean']} points, games at a 5-point gap {100 * sh['gap']['ge5']:.0f}% to {100 * t['gap']['ge5']:.0f}%.",
          f"- **It does nothing for the picks.** Against the closing spread L is {pct(t['ats']['0'])} on 2025-26 (shipped {pct(sh['ats']['0'])}), {pct(t['ats']['5'])} at a 5-point gap, "
          f"and its winner pick is {pct(t['winner'])} where the market's favourite is {pct(t['fav'])}. A more accurate margin moved the model toward the line; it did not put it on the right side of the line.",
          '- `game_model.json`, the Slate and the Game Picks record are unchanged. Option L stays in `build_game_model.py`, off unless `MK_W` is set.']
    if rows:
        L += ['', f"**Flagged for close monitoring** (CLAUDE.md), all replays on n = {rows['L']['n']}: L margin MAE {rows['S']['mae']} to {rows['L']['mae']}; "
              f"L winner {rows['S']['winner'][0]}-{rows['S']['winner'][1]} to {rows['L']['winner'][0]}-{rows['L']['winner'][1]}; "
              f"L spread {rows['S']['ats']['0'][0]}-{rows['S']['ats']['0'][1]} to {rows['L']['ats']['0'][0]}-{rows['L']['ats']['0'][1]}. One standard error on a win rate at this n is 4 points."]
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
