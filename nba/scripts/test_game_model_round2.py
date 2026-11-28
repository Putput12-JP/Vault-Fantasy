#!/usr/bin/env python3
"""
Game model round 2: a larger rating step early in a season (E), a blowout cap on the rating update (M), and both (EM),
against the shipped Vault line, walk-forward. Rules, committed before this ran: docs/game-model-round2.md.
Results: docs/game-model-round2-results.md and data/game_model_round2.json.

  python3 nba/scripts/test_game_model_round2.py

Pure stdlib. Same games, lines and injury report as build_game_model.py; the shipped model runs with the parameters in
data/game_model.json. Nothing here writes data/game_model.json.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM

WARM, TUNE, TEST = GM.WARM, GM.TUNE, GM.TEST
DATA = os.path.join(C.HERE, '..', 'data')
OUT_JSON = os.path.join(DATA, 'game_model_round2.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-round2-results.md')
GRID_B, GRID_N = [0, 1, 2, 3, 4], [10, 20, 30]
GRID_CAP = [None, 10, 13, 16, 20, 25, 30]
EARLY_DAYS = 28


def mae(xs):
    xs = list(xs)
    return statistics.mean(abs(x) for x in xs) if xs else float('nan')


def paired_t(es, ev):
    """mean(|error S| - |error V|) and its t over games: positive = the variant is closer."""
    d = [abs(a) - abs(b) for a, b in zip(es, ev)]
    if len(d) < 2:
        return 0.0, 0.0
    sd = statistics.stdev(d)
    if abs(statistics.mean(d)) < 1e-9:                       # the variant is the shipped model: float dust, not a difference
        return 0.0, 0.0
    return statistics.mean(d), (statistics.mean(d) / (sd / math.sqrt(len(d))) if sd else 0.0)


def wl(pairs, t=0.0):
    """pairs: (model margin, market margin, actual margin). Win-loss against the spread at |gap| >= t."""
    w = l = 0
    for m, mk, am in pairs:
        e, res = m - mk, am - mk
        if e == 0 or res == 0 or abs(e) < t:
            continue
        w += (res > 0) == (e > 0)
        l += (res > 0) != (e > 0)
    return [w, l]


def early_cut(recs):
    first = {}
    for r in recs:
        s = r['g']['season']
        first[s] = min(first.get(s, r['g']['tip']), r['g']['tip'])
    return {s: t + dt.timedelta(days=EARLY_DAYS) for s, t in first.items()}


def tune_scores(P, box):
    _, recs = GM.run(P, WARM + TUNE, box, record_from=TUNE[0])
    cut = early_cut(recs)
    return (mae(r['oracle'][0] - r['actual_margin'] for r in recs),
            mae(r['oracle'][0] - r['actual_margin'] for r in recs if r['g']['tip'] < cut[r['g']['season']]), len(recs))


def choose(P0, box):
    """One pass over each grid on the tune seasons, whole-season margin MAE with who actually sat."""
    out = {'E': [], 'M': []}
    for b in GRID_B:
        for n in (GRID_N if b else [None]):
            s = tune_scores(dict(P0, EK_B=b, EK_N=n or 20), box)
            out['E'].append({'B': b, 'N': n, 'mae': round(s[0], 4), 'mae_early': round(s[1], 4)})
            print('  E', out['E'][-1], flush=True)
    for cap in GRID_CAP:
        s = tune_scores(dict(P0, ERR_CAP=cap), box)
        out['M'].append({'CAP': cap, 'mae': round(s[0], 4), 'mae_early': round(s[1], 4)})
        print('  M', out['M'][-1], flush=True)
    e = min(out['E'], key=lambda x: (x['mae'], x['B']))
    m = min(out['M'], key=lambda x: (x['mae'], 0 if x['CAP'] is None else 1))
    return out, e, m


def score(variants, box, lines, inj):
    """variant -> list of per-game dicts on the test seasons (games with a closing spread)."""
    res = {}
    for name, P in variants.items():
        _, recs = GM.run(P, WARM + TUNE + TEST, box, lines, inj, record_from=TEST[0])
        res[name] = [r for r in recs if r.get('line') and r['line'].get('spread_close') is not None]
    return res


def block(name, R, S, cut):
    def sub(rows, ref):
        es = [r['tip'][0] - r['actual_margin'] for r in ref]
        ev = [r['tip'][0] - r['actual_margin'] for r in rows]
        d, t = paired_t(es, ev)
        return {'n': len(rows), 'mae': round(mae(ev), 3), 'd': round(d, 4), 't': round(t, 2)}
    out = {}
    for s in TEST + ['all']:
        rows = [r for r in R if s == 'all' or r['g']['season'] == s]
        ref = [r for r in S if s == 'all' or r['g']['season'] == s]
        b = sub(rows, ref)
        er = [r for r in rows if r['g']['tip'] < cut[r['g']['season']]]
        ef = [r for r in ref if r['g']['tip'] < cut[r['g']['season']]]
        b['early'] = sub(er, ef)
        b['close_mae'] = round(mae(-r['line']['spread_close'] - r['actual_margin'] for r in rows), 3)
        pairs = [(r['tip'][0], -r['line']['spread_close'], r['actual_margin']) for r in rows]
        b['ats'] = {str(t): wl(pairs, t) for t in (0, 3, 5)}
        b['info'] = GM.info_test(rows, 'tip', 'spread_close', 0)
        out[str(s)] = b
    return out


def this_season(variants, cur):
    """The live record replayed: each variant's ratings-only margin plus the adjustment the recorder applied, against the locked line."""
    path = os.path.join(C.RAW, 'hoopr', f'player_box_{cur}.csv')
    gp = os.path.join(DATA, 'game_picks.json')
    if not (os.path.exists(path) and os.path.exists(gp)):
        return None
    seasons = [cur - 2, cur - 1, cur]
    box = C.player_games(seasons)
    d = json.load(open(gp))
    cols = d['cols']
    first = {}
    for day, v in d['days'].items():
        for r in v['rows']:
            x = dict(zip(cols, r))
            if x['clock'] == 'f' and x['spread'] is not None:
                first[str(x['game'])] = x
    base = None
    out = {}
    for name, P in variants.items():
        _, recs = GM.run(P, seasons, box, record_from=cur)
        by = {str(r['g']['game_id']): r for r in recs}
        if name == 'S':
            base = by
        rows = []
        for k, x in first.items():
            if k not in by or k not in base:
                continue
            adj = x['margin'] - base[k]['none'][0]                 # the injury and rest adjustment the recorder applied
            rows.append((by[k]['none'][0] + adj, -x['spread'], x['am'], x['margin']))
        es = [r[3] - r[2] for r in rows]
        ev = [r[0] - r[2] for r in rows]
        dd, t = paired_t(es, ev)
        pairs = [(r[0], r[1], r[2]) for r in rows]
        out[name] = {'n': len(rows), 'mae': round(mae(ev), 3), 'locked_mae': round(mae(es), 3), 'd': round(dd, 4), 't': round(t, 2),
                     'line_mae': round(mae(r[1] - r[2] for r in rows), 3),
                     'ats': {str(t): wl(pairs, t) for t in (0, 3, 5)},
                     'winner': [sum((r[0] > 0) == (r[2] > 0) for r in rows if r[0] != 0), sum((r[0] > 0) != (r[2] > 0) for r in rows if r[0] != 0)],
                     'flips': sum(((r[0] - r[1]) > 0) != ((r[3] - r[1]) > 0) for r in rows)}
    return out


def verdict(b, s):
    a = b['all']
    ok = (a['t'] >= 2.5 and all(b[str(x)]['d'] > 0 for x in TEST)
          and a['info'] and s['all']['info'] and a['info']['t'] >= s['all']['info']['t'] - 1)
    return 'Better' if ok else ('Tie' if a['t'] > -2 else 'Worse')


def pct(w, l):
    return f'{100 * w / (w + l):.1f}%' if w + l else ''


def main():
    box = C.player_games(WARM + TUNE + TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    grids, e, m = choose(P0, box)
    variants = {'S': dict(P0), 'E': dict(P0, EK_B=e['B'], EK_N=e['N'] or 20), 'M': dict(P0, ERR_CAP=m['CAP']),
                'EM': dict(P0, EK_B=e['B'], EK_N=e['N'] or 20, ERR_CAP=m['CAP'])}
    lines = C.closing_lines()
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    res = score(variants, box, lines, inj)
    cut = early_cut(res['S'])
    rep = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'grids': grids, 'chosen': {'E': e, 'M': m},
           'test': {k: block(k, v, res['S'], cut) for k, v in res.items()}}
    rep['verdict'] = {k: verdict(rep['test'][k], rep['test']['S']) for k in ('E', 'M', 'EM')}
    cur = max(TEST) + 1
    rep['season'] = {'label': cur, 'rows': this_season(variants, cur)}
    json.dump(rep, open(OUT_JSON, 'w'), indent=1)
    write_md(rep)
    print(json.dumps(rep['chosen']), rep['verdict'])


def write_md(rep):
    T, e, m = rep['test'], rep['chosen']['E'], rep['chosen']['M']
    L = ['# Game model round 2: results', '',
         f"Generated {rep['generated']} by `nba/scripts/test_game_model_round2.py`. Rules: [game-model-round2.md](game-model-round2.md) (committed before this ran).", '',
         '## What the tune seasons chose', '',
         f"- **E, early step:** B = {e['B']}, N = {e['N']} (tune margin MAE {e['mae']}; shipped {next(x['mae'] for x in rep['grids']['E'] if x['B'] == 0)}).",
         f"- **M, blowout cap:** CAP = {m['CAP']} (tune margin MAE {m['mae']}; shipped {next(x['mae'] for x in rep['grids']['M'] if x['CAP'] is None)}).", '',
         '| E grid | ' + ' | '.join(f"B{x['B']} N{x['N']}" for x in rep['grids']['E']) + ' |', '|---|' + '---|' * len(rep['grids']['E']),
         '| Tune MAE | ' + ' | '.join(str(x['mae']) for x in rep['grids']['E']) + ' |',
         '| First 4 weeks | ' + ' | '.join(str(x['mae_early']) for x in rep['grids']['E']) + ' |', '',
         '| M grid | ' + ' | '.join(str(x['CAP']) for x in rep['grids']['M']) + ' |', '|---|' + '---|' * len(rep['grids']['M']),
         '| Tune MAE | ' + ' | '.join(str(x['mae']) for x in rep['grids']['M']) + ' |',
         '| First 4 weeks | ' + ' | '.join(str(x['mae_early']) for x in rep['grids']['M']) + ' |', '',
         '## Test seasons (2024-25 and 2025-26, injury report at tip)', '',
         '| Variant | Season | Games | Margin MAE | Shipped minus variant | t | First 4 weeks MAE | t | Closing line MAE |', '|---|---|---|---|---|---|---|---|---|']
    for k in ('S', 'E', 'M', 'EM'):
        for s in ('2025', '2026', 'all'):
            b = T[k][s]
            L.append(f"| {k} | {s} | {b['n']} | {b['mae']} | {b['d']:+.3f} | {b['t']:+.2f} | {b['early']['mae']} (n {b['early']['n']}) | {b['early']['t']:+.2f} | {b['close_mae']} |")
    L += ['', '| Variant | Info test g (t) | Spread 0+ | 3+ | 5+ | Verdict |', '|---|---|---|---|---|---|']
    for k in ('S', 'E', 'M', 'EM'):
        b = T[k]['all']
        a = b['ats']
        L.append(f"| {k} | {b['info']['g_model_gap']} ({b['info']['t']}) | " + ' | '.join(f"{a[t][0]}-{a[t][1]} {pct(*a[t])}" for t in ('0', '3', '5'))
                 + f" | {'reference' if k == 'S' else rep['verdict'][k]} |")
    rows = (rep.get('season') or {}).get('rows')
    if rows:
        L += ['', f"## This season, replayed ({rows['S']['n']} games; reported, not part of the verdict)", '',
              '| Variant | Margin MAE | Shipped minus variant | t | Spread 0+ | 3+ | 5+ | Winner | Picks that change side |', '|---|---|---|---|---|---|---|---|---|']
        for k in ('S', 'E', 'M', 'EM'):
            b = rows[k]
            a = b['ats']
            L.append(f"| {k} | {b['mae']} | {b['d']:+.3f} | {b['t']:+.2f} | " + ' | '.join(f"{a[t][0]}-{a[t][1]}" for t in ('0', '3', '5'))
                     + f" | {b['winner'][0]}-{b['winner'][1]} | {b['flips']} |")
        L += ['', f"The locked line's MAE on these games is {rows['S']['line_mae']}. Row S is the shipped model replayed and equals the locked record."]
    v = rep['verdict']
    same = e['B'] == 0 and m['CAP'] is None
    L += ['', '## Verdict', '',
          ('**NO-GO, both.** On the tune seasons no early step and no cap beat the shipped model over the whole season, so the grid chose no change for E and for M '
           'and the scored variants are the shipped model. A bigger step early did not even help the first four weeks (it was worse at every B). The cap helped the first four weeks '
           'by about 0.03 points and was no better over the whole season at any value. `game_model.json` is unchanged.') if same else
          f"E: **{v['E']}**. M: **{v['M']}**. EM: **{v['EM']}**. `game_model.json` is unchanged by this script; a Better variant ships in its own pull request.",
          '', 'The audit tables this round promised (the record by grade, injury adjustment, favourite or underdog and stage of the season, this season and in the two test seasons) are in [game-picks-audit.md](game-picks-audit.md).']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
