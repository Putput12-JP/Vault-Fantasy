#!/usr/bin/env python3
"""
Garbage-time RAPM on five seasons, scored once. Rules, committed before this ran: docs/rapm-history-g-prereg.md.
Results: docs/rapm-history-g-results.md and data/rapm_history_g_test.json.

  python3 nba/scripts/test_rapm_history_g.py

Needs raw/hoopr/pbp_2022..2026.csv (fetch_hoopr.py --only-pbp 2022 2023 for the first two). Reuses the stint builder, ridge fit and model
from test_rapm.py. Inside the shipped model, no retune. Nothing here writes game_model.json.
"""
import datetime as dt, json, os, pickle, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS
import test_rapm as T

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'rapm_history_g_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'rapm-history-g-results.md')
T.PBP_SEASONS = (2022, 2023, 2024, 2025, 2026)
T.CACHE = os.path.join(C.RAW, 'stints_espn_5.pkl')
DS, LAMS, CS, LAMBDAS_B = (0.5, 0.7, 0.85, 1.0), (3000.0, 10000.0), (0.5, 0.75, 1.0), (0.5, 1.0, 2.0)


def tune_mae(P, box, starts):
    _, recs = GM.run(P, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
    d = [abs(r['oracle'][0] - r['actual_margin']) for r in recs
         if r['g']['season'] in starts and r['g']['tip'] >= starts[r['g']['season']]]
    return statistics.mean(d), len(d)


def main():
    seasons = GM.WARM + GM.TUNE + GM.TEST
    box = C.player_games(seasons)
    if os.path.exists(T.CACHE):
        stints, stats = pickle.load(open(T.CACHE, 'rb'))
    else:
        stints, stats = T.build_stints(box)
        pickle.dump((stints, stats), open(T.CACHE, 'wb'))
    print('stints', stats, flush=True)
    games = C.games(seasons)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'stint_stats': stats, 'tune': {}}
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = T.RapmModel
    snaps = {}
    for d in DS:
        T.DECAY = d
        for lam in LAMS:
            snaps[(d, lam)] = T.snapshots(stints, 'G', lam, games)
            print('snapshots', d, lam, len(snaps[(d, lam)]), flush=True)
    starts = {s: min(g['tip'] for g in games if g['season'] == s) + dt.timedelta(days=28) for s in (2023, 2024)}
    T.RapmModel.SNAPS = {}
    res['tune']['S'], res['tune_n'] = tune_mae(dict(P0), box, starts)
    best, best5 = {}, {}
    for mode, grid in (('O', CS), ('B', LAMBDAS_B)):
        for d in DS:
            for lam in LAMS:
                for x in grid:
                    T.RapmModel.SNAPS = snaps[(d, lam)]
                    m, _ = tune_mae(dict(P0, RAPM=mode, **({'C': x} if mode == 'O' else {'LAM': x})), box, starts)
                    res['tune'][f'L{mode}|D={d}|lam={lam}|x={x}'] = round(m, 4)
                    cell = {'D': d, 'lam': lam, 'x': x, 'mae': m}
                    if mode not in best or m < best[mode]['mae']:
                        best[mode] = cell
                    if d == 0.5 and (mode not in best5 or m < best5[mode]['mae']):
                        best5[mode] = cell
        print('tune', mode, best[mode], 'shipped', round(res['tune']['S'], 4), flush=True)
    res['chosen'] = best
    res['chosen_d05'] = best5

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, seasons, box, lines, inj, record_from=GM.TEST[0])[1]
    T.RapmModel.SNAPS = {}
    cur = run(dict(P0))
    res['scores'] = {}
    jobs = [(f'GL{m}', best[m], m) for m in ('O', 'B')] + [(f'GL{m} at D 0.5 (exploratory)', best5[m], m) for m in ('O', 'B')]
    for name, c, mode in jobs:
        T.RapmModel.SNAPS = snaps[(c['D'], c['lam'])]
        recs = run(dict(P0, RAPM=mode, **({'C': c['x']} if mode == 'O' else {'LAM': c['x']})))
        blk = {'cell': c, 'whole': {'pooled': SS.boot(cur, recs, 0, 'tip', lambda k: True)}}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk['whole'][str(s)] = SS.boot(cur, recs, 0, 'tip', lambda k, sid=sid: k in sid)
        withl = [r for r in recs if (r.get('line') or {}).get('spread_close') is not None]
        withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
        blk['info_variant'] = GM.info_test(withl, 'tip', 'spread_close', 0)
        blk['info_shipped'] = GM.info_test(withc, 'tip', 'spread_close', 0)
        blk['close_mae'] = {'variant': T.mae_close(recs), 'shipped': T.mae_close(cur)}
        res['scores'][name] = blk
        print(name, json.dumps(blk['whole']), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=str)
    write_md(res)


def write_md(res):
    s = res['stint_stats']
    L = ['# Game model: garbage-time RAPM on five seasons, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_rapm_history_g.py`. Rules, committed before this ran: [rapm-history-g-prereg.md](rapm-history-g-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.', '',
         f"Stints, 2021-22 to 2025-26: {s['kept']} of {s['games']} games kept ({s['bad_sub']} dropped for a substitution that did not match the floor, {s['no_starters']} without five starters per team).", '',
         f"Chosen on 2022-23 and 2023-24 (games from 28 days in, n={res['tune_n']}; shipped tune MAE {res['tune']['S']:.4f}): " +
         ', '.join(f"GL{m} = {{D {c['D']}, lambda {c['lam']}, {'C' if m == 'O' else 'LAM'} {c['x']}, tune MAE {c['mae']:.4f}}}" for m, c in res['chosen'].items()) + '.', '',
         'Tune MAE by cell: ' + ', '.join(f'{k}: {v}' for k, v in res['tune'].items() if k != 'S') + '.', '']
    for name, blk in res['scores'].items():
        L += [f'## {name} (margin MAE, points)', '', f"Cell: {blk['cell']}.", '', '| Window | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|']
        for lab in ('2025', '2026', 'pooled'):
            b = blk['whole'][lab]
            L.append(f"| {lab} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
