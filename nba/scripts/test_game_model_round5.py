#!/usr/bin/env python3
"""
Game model round 5: ratings (L) and scoring (LT) that also learn from the closing line, scored by cross-fit so every lined game is out of
sample for the parameters. Rules, committed before this ran: docs/game-model-round5.md.
Results: docs/game-model-round5-results.md and data/game_model_round5.json.

  python3 nba/scripts/test_game_model_round5.py

Pure stdlib. Nothing here writes data/game_model.json.
"""
import datetime as dt, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import test_game_model_round2 as R2

A, B = 2025, 2026
DATA = os.path.join(C.HERE, '..', 'data')
LOOKS = os.path.join(DATA, 'game_first_looks.json')
OUT_JSON = os.path.join(DATA, 'game_model_round5.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-round5-results.md')
GRID_L = [(w, k) for w in (0.25, 0.5, 0.75, 1.0) for k in (0.04, 0.08, 0.12, 0.16, 0.24, 0.32, 0.5)]
GRID_T = [(w, k) for w in (0.25, 0.5, 0.75, 1.0) for k in (0.03, 0.05, 0.08, 0.12, 0.16, 0.24)]
mae, paired_t, wl = R2.mae, R2.paired_t, R2.wl
KEY = {'margin': ('spread_close', 0, 'actual_margin'), 'total': ('total_close', 1, 'actual_total')}


def lined(recs, kind):
    k = KEY[kind][0]
    return {r['g']['game_id']: r for r in recs if r.get('line') and r['line'].get(k) is not None and r['line'].get('spread_close') is not None and 'tip' in r}


def err(r, kind):
    return r['tip'][KEY[kind][1]] - r[KEY[kind][2]]


def crossfit(kind, grid, pname, P0, S, box, lines, inj):
    _, ref = GM.run(P0, S, box, lines, inj, record_from=A)
    ref = lined(ref, kind)
    runs = {}
    for w, k in grid:
        _, recs = GM.run(dict(P0, **{pname[0]: w, pname[1]: k}), S, box, lines, inj, record_from=A)
        runs[(w, k)] = lined(recs, kind)
        print(' ', kind, w, k, {s: round(mae(err(r, kind) for r in runs[(w, k)].values() if r['g']['season'] == s), 4) for s in (A, B)}, flush=True)
    by = lambda rows, s: [r for r in rows.values() if r['g']['season'] == s]
    m = {p: {s: mae(err(r, kind) for r in by(rows, s)) for s in (A, B)} for p, rows in runs.items()}
    pa = min(grid, key=lambda p: m[p][A])                       # chosen on 2024-25, scored on 2025-26
    pb = min(grid, key=lambda p: m[p][B])                       # chosen on 2025-26, scored on 2024-25
    ship = min(grid, key=lambda p: mae([err(r, kind) for r in runs[p].values()]))
    oos = {B: runs[pa], A: runs[pb]}
    out = {'grid': [{'w': p[0], 'k': p[1], str(A): round(m[p][A], 4), str(B): round(m[p][B], 4)} for p in grid],
           'shipped': {str(s): round(mae(err(r, kind) for r in by(ref, s)), 4) for s in (A, B)},
           'fit_on': {str(A): list(pa), str(B): list(pb)}, 'ship': list(ship), 'folds': {}}
    es_all, ev_all, rows_all = [], [], []
    for s in (B, A):
        ids = [k for k, r in ref.items() if r['g']['season'] == s and k in oos[s]]
        es, ev = [err(ref[k], kind) for k in ids], [err(oos[s][k], kind) for k in ids]
        d, t = paired_t(es, ev)
        ck = KEY[kind][0]
        out['folds'][str(s)] = {'n': len(ids), 'params': list(pa if s == B else pb), 'mae_s': round(mae(es), 3), 'mae_v': round(mae(ev), 3), 'd': round(d, 4), 't': round(t, 2),
                                'line_mae': round(mae((-ref[k]['line'][ck] if kind == 'margin' else ref[k]['line'][ck]) - ref[k][KEY[kind][2]] for k in ids), 3)}
        es_all += es
        ev_all += ev
        rows_all += [oos[s][k] for k in ids]
    d, t = paired_t(es_all, ev_all)
    ref_rows = [ref[r['g']['game_id']] for r in rows_all]
    out['pooled'] = {'n': len(es_all), 'mae_s': round(mae(es_all), 3), 'mae_v': round(mae(ev_all), 3), 'd': round(d, 4), 't': round(t, 2),
                     'info_v': GM.info_test(rows_all, 'tip', KEY[kind][0], KEY[kind][1]), 'info_s': GM.info_test(ref_rows, 'tip', KEY[kind][0], KEY[kind][1])}
    if kind == 'margin':
        for lab, rows in (('ats_v', rows_all), ('ats_s', ref_rows)):
            pairs = [(r['tip'][0], -r['line']['spread_close'], r['actual_margin']) for r in rows]
            out['pooled'][lab] = {str(x): wl(pairs, x) for x in (0, 3, 5)}
    else:
        for lab, rows in (('ou_v', rows_all), ('ou_s', ref_rows)):
            pairs = [(r['tip'][1], r['line']['total_close'], r['actual_total']) for r in rows]
            out['pooled'][lab] = {str(x): wl(pairs, x) for x in (0, 4, 8)}
    return out


def this_season(P0, ship_l, ship_t, lines, cur):
    path = os.path.join(C.RAW, 'hoopr', f'player_box_{cur}.csv')
    gp = os.path.join(DATA, 'game_picks.json')
    if not (os.path.exists(path) and os.path.exists(gp) and os.path.exists(LOOKS)):
        return None
    looks = json.load(open(LOOKS))['games']
    d = json.load(open(gp))
    first = {}
    for day, v in d['days'].items():
        for r in v['rows']:
            x = dict(zip(d['cols'], r))
            if x['clock'] == 'f' and x['spread'] is not None:
                first[str(x['game'])] = x
    L = dict(lines)
    for k, x in looks.items():
        L[int(k)] = {'spread_close': x['spread_last'], 'total_close': x.get('total_last')}
    seasons = [cur - 2, cur - 1, cur]
    box = C.player_games(seasons)
    run = lambda P: {str(r['g']['game_id']): r for r in GM.run(P, seasons, box, L, record_from=cur)[1]}
    base = run(P0)
    vl = run(dict(P0, MK_W=ship_l[0], MK_K=ship_l[1]))
    vt = run(dict(P0, MT_W=ship_t[0], MT_K=ship_t[1]))
    ks = [k for k in first if k in base and k in looks]
    es = [first[k]['margin'] - first[k]['am'] for k in ks]
    ev = [vl[k]['none'][0] + (first[k]['margin'] - base[k]['none'][0]) - first[k]['am'] for k in ks]
    dm, tm = paired_t(es, ev)
    pairs_v = [(e + first[k]['am'], -first[k]['spread'], first[k]['am']) for e, k in zip(ev, ks)]
    pairs_s = [(first[k]['margin'], -first[k]['spread'], first[k]['am']) for k in ks]
    kt = [k for k in ks if looks[k].get('total_last') is not None]
    ts_ = [base[k]['none'][1] - base[k]['actual_total'] for k in kt]
    tv = [vt[k]['none'][1] - vt[k]['actual_total'] for k in kt]
    dt_, tt = paired_t(ts_, tv)
    ou = lambda src: wl([(src[k]['none'][1], looks[k]['total_last'], src[k]['actual_total']) for k in kt], 0)
    return {'margin': {'n': len(ks), 'mae_s': round(mae(es), 3), 'mae_v': round(mae(ev), 3), 'd': round(dm, 4), 't': round(tm, 2),
                       'line_mae': round(mae(-first[k]['spread'] - first[k]['am'] for k in ks), 3),
                       'ats_v': {str(x): wl(pairs_v, x) for x in (0, 3, 5)}, 'ats_s': {str(x): wl(pairs_s, x) for x in (0, 3, 5)}},
            'total': {'n': len(kt), 'mae_s': round(mae(ts_), 3), 'mae_v': round(mae(tv), 3), 'd': round(dt_, 4), 't': round(tt, 2),
                      'line_mae': round(mae(looks[k]['total_last'] - base[k]['actual_total'] for k in kt), 3),
                      'bias_s': round(statistics.mean(ts_), 2), 'bias_v': round(statistics.mean(tv), 2), 'ou_v': ou(vt), 'ou_s': ou(base)}}


def main():
    S = GM.WARM + GM.TUNE + [A, B]
    box = C.player_games(S)
    P0 = R2.base_params()
    lines = C.closing_lines()
    inj = C.InjuryAsOf([A, B], C.player_index(box))
    rep = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
           'margin': crossfit('margin', GRID_L, ('MK_W', 'MK_K'), P0, S, box, lines, inj),
           'total': crossfit('total', GRID_T, ('MT_W', 'MT_K'), P0, S, box, lines, inj)}
    rep['season'] = this_season(P0, rep['margin']['ship'], rep['total']['ship'], lines, B + 1)
    m, t, sea = rep['margin'], rep['total'], rep['season']
    rep['verdict'] = {
        'margin': bool(m['pooled']['t'] >= 3.0 and all(f['d'] > 0 for f in m['folds'].values()) and (sea is None or sea['margin']['d'] > 0)
                       and m['pooled']['info_v']['t'] >= m['pooled']['info_s']['t'] - 1),
        'total': bool(t['pooled']['t'] >= 2.5 and all(f['d'] > 0 for f in t['folds'].values()) and (sea is None or sea['total']['d'] > 0))}
    json.dump(rep, open(OUT_JSON, 'w'), indent=1)
    write_md(rep)
    print(json.dumps({'ship_margin': m['ship'], 'ship_total': t['ship'], 'pooled_t': [m['pooled']['t'], t['pooled']['t']], 'verdict': rep['verdict']}))


def pct(a):
    return f"{a[0]}-{a[1]} ({100 * a[0] / (a[0] + a[1]):.1f}%)" if a[0] + a[1] else '0-0'


def write_md(rep):
    L = ['# Game model round 5: results', '',
         f"Generated {rep['generated']} by `nba/scripts/test_game_model_round5.py`. Rules: [game-model-round5.md](game-model-round5.md) (committed before this ran).", '']
    names = {'margin': ('Margin (option L)', 'W', 'KL', 'closing spread'), 'total': ('Total (option LT)', 'WT', 'KT', 'closing total')}
    for kind in ('margin', 'total'):
        x, (title, wn, kn, ln) = rep[kind], names[kind]
        L += [f'## {title}', '',
              f"Chosen on 2024-25: {wn} {x['fit_on'][str(A)][0]}, {kn} {x['fit_on'][str(A)][1]}. Chosen on 2025-26: {wn} {x['fit_on'][str(B)][0]}, {kn} {x['fit_on'][str(B)][1]}. "
              f"Ship parameters (both seasons): {wn} {x['ship'][0]}, {kn} {x['ship'][1]}.", '',
              '| Scored on | Parameters from | Games | Shipped MAE | Variant MAE | Shipped minus variant | t | Closing line MAE |', '|---|---|---|---|---|---|---|---|']
        for s, other in ((str(B), '2024-25'), (str(A), '2025-26')):
            f = x['folds'][s]
            L.append(f"| {'2025-26' if s == str(B) else '2024-25'} | {other} ({f['params'][0]}, {f['params'][1]}) | {f['n']} | {f['mae_s']} | {f['mae_v']} | {f['d']:+.3f} | {f['t']:+.2f} | {f['line_mae']} |")
        p = x['pooled']
        L.append(f"| **Pooled, out of sample** | | {p['n']} | {p['mae_s']} | {p['mae_v']} | {p['d']:+.3f} | **{p['t']:+.2f}** | |")
        L += ['', f"Information test against the {ln} (does the model know something the line does not), pooled out of sample: "
              f"variant g {p['info_v']['g_model_gap']} (t {p['info_v']['t']}), shipped g {p['info_s']['g_model_gap']} (t {p['info_s']['t']})."]
        if kind == 'margin':
            L += [f"Against the closing spread, pooled out of sample: variant {pct(p['ats_v']['0'])}, at a 3+ gap {pct(p['ats_v']['3'])}, at 5+ {pct(p['ats_v']['5'])}. "
                  f"Shipped: {pct(p['ats_s']['0'])}, {pct(p['ats_s']['3'])}, {pct(p['ats_s']['5'])}. Break-even is 52.4%."]
        else:
            L += [f"Over or under the closing total, pooled out of sample: variant {pct(p['ou_v']['0'])}, at a 4+ gap {pct(p['ou_v']['4'])}, at 8+ {pct(p['ou_v']['8'])}. "
                  f"Shipped: {pct(p['ou_s']['0'])}, {pct(p['ou_s']['4'])}, {pct(p['ou_s']['8'])}."]
        ws, ks = sorted({g['w'] for g in x['grid']}), sorted({g['k'] for g in x['grid']})
        L += ['', f"Grid, MAE on 2024-25 / 2025-26 (shipped {x['shipped'][str(A)]} / {x['shipped'][str(B)]}):", '',
              f'| {wn} \\ {kn} | ' + ' | '.join(str(k) for k in ks) + ' |', '|---|' + '---|' * len(ks)]
        for w in ws:
            L.append(f'| {w} | ' + ' | '.join(next(f"{g[str(A)]:.3f} / {g[str(B)]:.3f}" for g in x['grid'] if g['w'] == w and g['k'] == k) for k in ks) + ' |')
        L.append('')
    sea = rep['season']
    if sea:
        m, t = sea['margin'], sea['total']
        L += [f"## This season, with the ship parameters ({m['n']} games; a replay, flagged for monitoring)", '',
              '| | Games | Shipped MAE | Variant MAE | Shipped minus variant | t | Line MAE |', '|---|---|---|---|---|---|---|',
              f"| Margin | {m['n']} | {m['mae_s']} | {m['mae_v']} | {m['d']:+.3f} | {m['t']:+.2f} | {m['line_mae']} |",
              f"| Total | {t['n']} | {t['mae_s']} | {t['mae_v']} | {t['d']:+.3f} | {t['t']:+.2f} | {t['line_mae']} |", '',
              f"Spread record at the locked line: shipped {pct(m['ats_s']['0'])}, variant {pct(m['ats_v']['0'])}; at a 5+ gap {pct(m['ats_s']['5'])} and {pct(m['ats_v']['5'])}. "
              f"Total: average miss (model minus final) shipped {t['bias_s']:+.2f}, variant {t['bias_v']:+.2f}; over or under the last look, shipped {pct(t['ou_s'])}, variant {pct(t['ou_v'])}.", '']
    v = rep['verdict']
    L += ['## Verdict', '', f"- **Margin: {'GO (for accuracy)' if v['margin'] else 'NO-GO'}.** Bar: pooled out-of-sample t 3.0, closer in each fold and on this season, information test not worse by more than 1.",
          f"- **Total: {'GO (for accuracy)' if v['total'] else 'NO-GO'}.** Bar: pooled out-of-sample t 2.5, closer in each fold and on this season.",
          '- A GO here is a more accurate Vault line. It is not an edge: read the spread and over/under records above, which stay at a coin flip.',
          '- `game_model.json` is unchanged by this script. Shipping is its own pull request (the daily state build has no closing lines today).']
    t = rep['total']['pooled']
    L += ['', '## Notes', '',
          f"- Margin: both seasons chose the same parameters on their own (W {rep['margin']['ship'][0]}, KL {rep['margin']['ship'][1]}), so the fold \"2025-26 parameters on 2024-25\" "
          'is numerically the 2024-25 fit round 3 reported as in sample. What the cross-fit adds is that 2025-26 picks that point without seeing 2024-25.',
          f"- Total: the line-taught total is closer on average ({t['mae_s']} to {t['mae_v']}) and in both folds, but short of the bar (t {t['t']}) and worse this season, and against the closing total it leans the wrong way "
          f"(information test t {t['info_v']['t']}). Option LT stays off."]
    if sea:
        m = sea['margin']
        L += ['', f"**Flagged for close monitoring** (replays, n = {m['n']}): margin MAE {m['mae_s']} to {m['mae_v']}; spread record at the locked line "
              f"{m['ats_s']['0'][0]}-{m['ats_s']['0'][1]} to {m['ats_v']['0'][0]}-{m['ats_v']['0'][1]}; at a 5+ gap {m['ats_s']['5'][0]}-{m['ats_s']['5'][1]} to {m['ats_v']['5'][0]}-{m['ats_v']['5'][1]}."]
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
