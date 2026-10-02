#!/usr/bin/env python3
"""
Pre-registered test (docs/moved-players-test.md): should a player on a new team count toward its minutes from his
first game with it?

  v2     shipped: a player counts once he has played for the team (build_prop_model_v2.walk)
  v2mv   the same walk with moved=True: a dressed player whose minutes history is from another team counts too,
         with the team minutes target re-tuned on 2023-24 by minutes v3's ratio method

Measures (2025-26, player-games both rules project): minutes MAE on new-arrival team-games and on all team-games, with
a paired bootstrap over games; the moved players' own minutes under v2mv (report only); every signal's verdict from
build_prop_model_v3_full.compare.

  python3 nba/scripts/build_moved_players_test.py
Writes data/moved_players_test.json and docs/moved-players-results.md.
"""
import datetime as dt, json, os, random, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model_v2 as V2
import build_prop_model_v3_full as F

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'moved_players_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'moved-players-results.md')
TEST, B = 2025, 1000


def walk_mv(I):
    run = lambda tm: V2.walk(I['box'], I['inj'], I['margins'], I['mm'], I['casc'], tm, I['lines'], moved=True)[0]
    recs = run(I['team_min'])
    tune = [r for r in recs if r['season'] in (2023, 2024) and r['pm'] > 0]
    ratio = sum(r['min'] for r in tune) / sum(r['pm'] for r in tune)
    tm = round(I['team_min'] * ratio, 1)
    print(f'v2mv: team target {I["team_min"]} -> {tm}', flush=True)
    return (run(tm) if abs(ratio - 1) > 0.003 else recs), tm


def paired(a, b, sel):
    """MAE of each rule on the shared player-games passing sel, and the difference (v2mv - v2) with a bootstrap SE over
    games. a, b: {(gid, aid): rec}."""
    keys = [k for k in a if k in b and sel(a[k], b[k])]
    by = defaultdict(list)
    for k in keys:
        by[k[0]].append((abs(a[k]['pm'] - a[k]['min']), abs(b[k]['pm'] - b[k]['min'])))
    games = list(by)
    tot = lambda gs: (sum(x for g in gs for x, _ in by[g]), sum(y for g in gs for _, y in by[g]), sum(len(by[g]) for g in gs))
    sa, sb, n = tot(games)
    rnd, diffs = random.Random(7), []
    for _ in range(B):
        gs = [games[rnd.randrange(len(games))] for _ in games]
        xa, xb, m = tot(gs)
        diffs.append((xb - xa) / m)
    d, se = (sb - sa) / n, statistics.stdev(diffs)
    return {'n': n, 'games': len(games), 'mae_v2': round(sa / n, 3), 'mae_v2mv': round(sb / n, 3), 'diff': round(d, 3),
            'se': round(se, 3), 'z': round(d / se, 2) if se else None}


def main():
    I = F.inputs()
    r2 = V2.walk(I['box'], I['inj'], I['margins'], I['mm'], I['casc'], I['team_min'], I['lines'])[0]
    rmv, tm = walk_mv(I)
    a = {(r['gid'], r['aid']): r for r in r2 if r['season'] == TEST}
    b = {(r['gid'], r['aid']): r for r in rmv if r['season'] == TEST}
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'team_min': {'v2': I['team_min'], 'v2mv': tm}}
    res['new_arrival'] = paired(a, b, lambda x, y: y['na'])
    res['all'] = paired(a, b, lambda x, y: True)
    mv = [r for r in b.values() if r['mv']]
    res['movers'] = {'n': len(mv), 'mae': round(statistics.mean(abs(r['pm'] - r['min']) for r in mv), 3) if mv else None,
                     'bias': round(statistics.mean(r['pm'] - r['min'] for r in mv), 3) if mv else None}
    # how far each rule stretches returning teammates in new-arrival games (projected minus actual, signed)
    na = [k for k in a if k in b and b[k]['na'] and not b[k]['mv']]
    res['teammate_bias'] = {'v2': round(statistics.mean(a[k]['pm'] - a[k]['min'] for k in na), 3) if na else None,
                            'v2mv': round(statistics.mean(b[k]['pm'] - b[k]['min'] for k in na), 3) if na else None}
    na_ok = res['new_arrival']['z'] is not None and res['new_arrival']['diff'] < 0 and -res['new_arrival']['z'] >= 2
    all_ok = res['all']['z'] is None or res['all']['z'] <= 2
    res['minutes_verdict'] = 'GO' if na_ok and all_ok else 'NO-GO'
    print('minutes:', json.dumps({k: res[k] for k in ('new_arrival', 'all', 'movers', 'teammate_bias', 'minutes_verdict')}), flush=True)
    sig = F.compare(r2, {'v2mv': rmv}, None)
    res['verdict'] = sig['verdict']
    res['kalshi_bias'] = sig['kalshi_bias']
    res['minutes_shared'] = sig.get('minutes')
    gos = [m for m, v in sig['verdict']['v2'].items() if v.startswith('GO')]
    res['signals'] = {m: {'v2': sig['verdict']['v2'][m], 'v2mv': sig['verdict']['v2mv'][m],
                          'live': sig['verdict']['v2'][m] if res['minutes_verdict'] != 'GO' else
                          ('GO' if sig['verdict']['v2mv'][m].startswith('GO') else 'WATCH')} for m in gos}
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=str)
    write_md(res)
    print(open(OUT_MD).read())


def write_md(res):
    na, al, mv, tb = res['new_arrival'], res['all'], res['movers'], res['teammate_bias']
    L = ['# Players on a new team: results', '',
         f"Generated {res['generated']} by `nba/scripts/build_moved_players_test.py`. Rules: [moved-players-test.md](moved-players-test.md) "
         '(committed before this ran). Tested on 2025-26; MAE in minutes, lower is better; bootstrap over games.', '',
         f"**Minutes rule: {res['minutes_verdict']}**", '',
         '| Player-games | n | games | v2 MAE | v2mv MAE | v2mv - v2 | SE | z |', '|---|---|---|---|---|---|---|---|',
         f"| New-arrival team-games | {na['n']:,} | {na['games']:,} | {na['mae_v2']} | {na['mae_v2mv']} | {na['diff']:+} | {na['se']} | {na['z']} |",
         f"| All team-games | {al['n']:,} | {al['games']:,} | {al['mae_v2']} | {al['mae_v2mv']} | {al['diff']:+} | {al['se']} | {al['z']} |", '',
         f"Returning teammates in new-arrival games, projected minus actual: v2 {tb['v2']:+} min, v2mv {tb['v2mv']:+} min.",
         f"The moved players themselves under v2mv (v2 does not project their first game): {mv['n']:,} player-games, MAE {mv['mae']}, bias {mv['bias']:+}.",
         f"Team minutes target: v2 {res['team_min']['v2']}, v2mv {res['team_min']['v2mv']}.", '',
         '## Signals', '', '| Signal | v2 | v2mv | Live after this test |', '|---|---|---|---|']
    L += [f"| {m} | {v['v2']} | {v['v2mv']} | {v['live']} |" for m, v in res['signals'].items()]
    L += ['', 'Signals follow the inputs: if the minutes rule ships, a GO signal that is not GO under v2mv moves to WATCH.']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
