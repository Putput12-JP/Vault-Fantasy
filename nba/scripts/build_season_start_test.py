#!/usr/bin/env python3
"""
Pre-registered test (docs/season-start-test.md): the game model's season start.

  current   shipped parameters
  R         roster carry: ROSTER_K chosen on the tune seasons' first 4 weeks (margin MAE, who actually sat)
  T         scoring level: base reset to last regular season's points per team, offense / defense re-centered,
            playoff games no longer move scoring

Scored on 2024-25 and 2025-26 with the injury report as of tip ('tip' mode), first 4 weeks and whole season, paired
bootstrap over games. -> data/season_start_test.json, docs/season-start-results.md
"""
import datetime as dt, json, os, random, statistics, sys
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_game_model as GM

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'season_start_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'season-start-results.md')
KS, WEEKS4, B = (0.25, 0.5, 0.75, 1.0, 1.25), 28, 1000


def early(recs):
    """game_id -> True if the game is within the first 28 days of its season."""
    start = {}
    for r in recs:
        s = r['g']['season']
        start[s] = min(start.get(s, r['g']['tip']), r['g']['tip'])
    return {r['g']['game_id']: (r['g']['tip'] - start[r['g']['season']]).days < WEEKS4 for r in recs}


def boot(base, var, idx, mode, keep):
    """MAE of each on the shared games passing keep, and var - base with a bootstrap SE over games."""
    b = {r['g']['game_id']: r for r in base}
    v = {r['g']['game_id']: r for r in var}
    act = 'actual_margin' if idx == 0 else 'actual_total'
    ids = [k for k in b if k in v and keep(k)]
    e = [(abs(b[k][mode][idx] - b[k][act]), abs(v[k][mode][idx] - v[k][act])) for k in ids]
    n = len(e)
    d = sum(y - x for x, y in e) / n
    rnd, ds = random.Random(11), []
    for _ in range(B):
        s = [e[rnd.randrange(n)] for _ in range(n)]
        ds.append(sum(y - x for x, y in s) / n)
    se = statistics.stdev(ds)
    return {'n': n, 'mae_current': round(sum(x for x, _ in e) / n, 3), 'mae_variant': round(sum(y for _, y in e) / n, 3),
            'diff': round(d, 3), 'se': round(se, 3), 'z': round(d / se, 2) if se else None}


def close_bias(recs, keep):
    d = [r['tip'][1] - r['line']['total_close'] for r in recs if keep(r['g']['game_id']) and (r.get('line') or {}).get('total_close')]
    return {'n': len(d), 'model_minus_close': round(statistics.mean(d), 2) if d else None,
            'share_under': round(sum(x < 0 for x in d) / len(d), 3) if d else None}


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}}

    # R: choose k on the tune seasons' first 4 weeks (who actually sat, as the model was tuned)
    for k in (0.0,) + KS:
        _, recs = GM.run(dict(P0, ROSTER_K=k), GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
        ea = early(recs)
        m = statistics.mean(abs(r['oracle'][0] - r['actual_margin']) for r in recs if ea[r['g']['game_id']])
        res['tune'][str(k)] = round(m, 4)
        print(f'tune k={k}: first-4-weeks margin MAE {m:.4f}', flush=True)
    k = min(KS, key=lambda x: res['tune'][str(x)])
    res['k'] = k

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])[1]
    cur, R, T = run(P0), run(dict(P0, ROSTER_K=k)), run(dict(P0, TOT_RESET=True))
    ea = early(cur)
    first_week = {r['g']['game_id']: r['g']['tip'] for r in cur}
    start = {}
    for r in cur:
        start[r['g']['season']] = min(start.get(r['g']['season'], r['g']['tip']), r['g']['tip'])
    wk1 = {r['g']['game_id']: (r['g']['tip'] - start[r['g']['season']]).days < 7 for r in cur}

    res['R'] = {'early': boot(cur, R, 0, 'tip', lambda g: ea.get(g)), 'season': boot(cur, R, 0, 'tip', lambda g: True)}
    res['T'] = {'early': boot(cur, T, 1, 'tip', lambda g: ea.get(g)), 'season': boot(cur, T, 1, 'tip', lambda g: True),
                'week1_close_bias': {'current': close_bias(cur, lambda g: wk1.get(g)), 'T': close_bias(T, lambda g: wk1.get(g))}}
    for name, recs in (('current', cur), ('R', R)):
        early_recs = [r for r in recs if ea.get(r['g']['game_id'])]
        res.setdefault('context', {})[name] = {'ats_close_early': GM.ats(early_recs, 'tip', 'spread_close', (0, 2, 4)),
                                               'info_close_season': GM.info_test(recs, 'tip', 'spread_close', 0)}
    for v in ('R', 'T'):
        e, s = res[v]['early'], res[v]['season']
        res[v]['verdict'] = 'GO' if (e['z'] is not None and e['diff'] < 0 and -e['z'] >= 2 and (s['z'] is None or s['z'] <= 2)) else 'NO-GO'
    print(json.dumps({v: res[v] for v in ('R', 'T')}, indent=1, default=str), flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=str)
    write_md(res)
    print(open(OUT_MD).read())


def write_md(res):
    row = lambda lab, x: f"| {lab} | {x['n']:,} | {x['mae_current']} | {x['mae_variant']} | {x['diff']:+} | {x['se']} | {x['z']} |"
    hdr = ['| Games | n | Current MAE | Variant MAE | Variant - current | SE | z |', '|---|---|---|---|---|---|---|']
    R, T = res['R'], res['T']
    wb = T['week1_close_bias']
    L = ['# Game model season start: results', '',
         f"Generated {res['generated']} by `nba/scripts/build_season_start_test.py`. Rules: [season-start-test.md](season-start-test.md) "
         '(committed before this ran). Test seasons 2024-25 and 2025-26, injury report as of tip; bootstrap over games.', '',
         f"## R, roster carry: **{R['verdict']}**", '',
         f"k = {res['k']} (tune first-4-weeks margin MAE: " + ', '.join(f"k {k}: {v}" for k, v in res['tune'].items()) + ').', '',
         'Margin, points:', ''] + hdr + [row('First 4 weeks', R['early']), row('Whole season', R['season'])] + [
         '', f"## T, scoring level: **{T['verdict']}**", '', 'Total, points:', ''] + hdr + [row('First 4 weeks', T['early']), row('Whole season', T['season'])] + [
         '', f"First week, model total minus closing total: current {wb['current']['model_minus_close']:+} ({wb['current']['share_under']:.0%} under), "
         f"T {wb['T']['model_minus_close']:+} ({wb['T']['share_under']:.0%} under), {wb['current']['n']} games.", '',
         'Either way the game model stays context only (it has never beaten the closing line).']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
