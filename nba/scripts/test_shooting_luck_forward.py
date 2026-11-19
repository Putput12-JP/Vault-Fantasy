#!/usr/bin/env python3
"""
Frozen forward test of the shooting-luck variants. Rules: docs/shooting-luck-forward.md.

  python3 nba/scripts/test_shooting_luck_forward.py --freeze   write data/shooting_luck_frozen.json (once; commit it)
  python3 nba/scripts/test_shooting_luck_forward.py --check    frozen file unchanged since commit, shipped parameters unchanged
  python3 nba/scripts/test_shooting_luck_forward.py --read     score 2026-27 games tipped after the freeze (verdict only at 300 games)

Refresh the local box scores first (nba/scripts/fetch_hoopr.py) or the count will lag. Writes nba/data/shooting_luck_forward.json.
"""
import datetime as dt, hashlib, json, os, random, statistics, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import test_shooting_luck as SL

FROZEN = os.path.join(C.HERE, '..', 'data', 'shooting_luck_frozen.json')
OUT = os.path.join(C.HERE, '..', 'data', 'shooting_luck_forward.json')
BACKTEST = os.path.join(C.HERE, '..', 'data', 'shooting_luck_test.json')
SEASON, READ_AT, B = 2027, 300, 1000


def params_hash():
    p = json.load(open(GM.OUT_JSON))['params']
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]


def central_now():
    return subprocess.check_output(['date', '+%Y-%m-%dT%H:%M'], env=dict(os.environ, TZ='America/Chicago')).decode().strip()


def freeze():
    if os.path.exists(FROZEN):
        sys.exit('already frozen; refusing to overwrite')
    ch = json.load(open(BACKTEST))['chosen']
    out = {'frozen_at_central': central_now(), 'shipped_params_hash': params_hash(), 'M': ch['M'], 'T': ch['T'],
           'source': 'data/shooting_luck_test.json chosen on 2022-23 and 2023-24, backtest PR 509'}
    json.dump(out, open(FROZEN, 'w'), indent=1)
    print(json.dumps(out))


def check():
    rel = os.path.relpath(FROZEN, os.path.join(C.HERE, '..', '..'))
    root = os.path.join(C.HERE, '..', '..')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', rel], cwd=root).returncode:
        sys.exit('FAIL: frozen file differs from the commit')
    if subprocess.run(['git', 'ls-files', '--error-unmatch', rel], cwd=root, capture_output=True).returncode:
        sys.exit('FAIL: frozen file is not committed')
    if json.load(open(FROZEN))['shipped_params_hash'] != params_hash():
        sys.exit('FAIL: shipped model parameters changed since the freeze')
    print('OK: frozen file committed and unchanged; shipped parameters unchanged')


def boot_diff(base, var, idx, keep):
    act = 'actual_margin' if idx == 0 else 'actual_total'
    ids = [r['g']['game_id'] for r in base if keep(r)]
    b = {r['g']['game_id']: r for r in base}
    v = {r['g']['game_id']: r for r in var}
    e = [(abs(b[k]['none'][idx] - b[k][act]), abs(v[k]['none'][idx] - v[k][act])) for k in ids if k in v]
    n = len(e)
    if not n:
        return None
    d = sum(y - x for x, y in e) / n
    rnd, ds = random.Random(11), []
    for _ in range(B):
        s = [e[rnd.randrange(n)] for _ in range(n)]
        ds.append(sum(y - x for x, y in s) / n)
    se = statistics.stdev(ds) if n > 1 else None
    return {'n': n, 'mae_shipped': round(sum(x for x, _ in e) / n, 3), 'mae_variant': round(sum(y for _, y in e) / n, 3),
            'diff': round(d, 3), 'se': round(se, 3) if se else None, 't': round(d / se, 2) if se else None}


def read():
    check()
    fz = json.load(open(FROZEN))
    cut = fz['frozen_at_central'].replace('T', ' ')
    seasons = GM.WARM + GM.TUNE + GM.TEST + [SEASON]
    box = C.player_games(seasons)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = SL.LuckModel
    run = lambda P: GM.run(P, seasons, box, record_from=SEASON)[1]
    cur = run(dict(P0))
    var = {'M': run(dict(P0, LUCK='M', **fz['M'])), 'T': run(dict(P0, LUCK='T', **fz['T']))}
    reg = [r for r in cur if not r['g']['playoff']]
    fwd = [r for r in reg if str(r['g']['tip_et']) > cut]
    ids = [r['g']['game_id'] for r in fwd]
    half = {k: i < len(ids) // 2 for i, k in enumerate(ids)}
    res = {'read_at_central': central_now(), 'frozen_at_central': fz['frozen_at_central'], 'forward_games': len(fwd),
           'season_to_date_games': len(reg), 'last_game': str(reg[-1]['g']['tip_et']) if reg else None, 'scores': {}}
    for name, idx in (('M', 0), ('T', 1)):
        blk = {'to_date': boot_diff(reg, var[name], idx, lambda r: True)}
        if fwd:
            blk['forward'] = boot_diff(fwd, var[name], idx, lambda r: True)
            blk['first_half'] = boot_diff(fwd, var[name], idx, lambda r: half[r['g']['game_id']])
            blk['second_half'] = boot_diff(fwd, var[name], idx, lambda r: not half[r['g']['game_id']])
        res['scores'][name] = blk
    if len(fwd) >= READ_AT:
        res['verdict'] = {}
        for name in ('M', 'T'):
            b = res['scores'][name]
            ok = b['forward']['diff'] < 0 and b['forward']['t'] is not None and b['forward']['t'] <= -2 \
                and b['first_half']['diff'] < 0 and b['second_half']['diff'] < 0
            res['verdict'][name] = 'PASS' if ok else ('NO-GO' if b['forward']['diff'] >= 0 else 'KEEP READING to 600')
    else:
        res['verdict'] = f'no verdict: {len(fwd)} of {READ_AT} forward games scored'
    json.dump(res, open(OUT, 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    {'--freeze': freeze, '--check': check, '--read': read}.get(sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
