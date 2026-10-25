#!/usr/bin/env python3
"""
Rotation-aware minutes. Rules: docs/rotation-minutes-test.md (committed before this file existed). Nothing here changes pricing.

  python3 nba/scripts/test_rotation_minutes.py          walk the prop model (about 6 min), fit on 2022-23..2024-25, score 2025-26 once -> data/rotation_minutes.json
  python3 nba/scripts/test_rotation_minutes.py --cache  reuse the cached walk (same numbers)

Per game state (close <10, middle 10-19, blowout 20+ final margin): P(plays), P(rotation | plays), minutes given rotation, minutes of non-rotation players who play.
Candidate C mixes the three states by the pre-game blowout probability; control B is one model with the blowout probability as a feature; baseline A is the walk's pm.
"""
import json, math, os, random, statistics as st, sys
from collections import defaultdict, deque
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lean_search_nba as LS          # fit() = ridge logistic by Newton; sig()
import test_early_minutes_blend as EB  # boot()

OUT = os.path.join(HERE, '..', 'data', 'rotation_minutes.json')
CACHE = os.environ.get('ROTATION_CACHE', '/tmp/rotation_pool.json')
FIT_SEASONS, PLAYS_SEASONS, TEST = (2023, 2024, 2025), (2025,), 2026
ROT_CUT, SD_MARGIN, LAM, ITERS = 12.0, 13.2, 1.0, 12
STATS = ['pts', 'reb', 'ast', '3pm']
STATES = ('close', 'middle', 'blowout')


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def state_of(fm):
    return 0 if fm < 10 else (1 if fm < 20 else 2)


def pis(e):
    """P(final |margin| in each bucket) for margin ~ Normal(e, SD_MARGIN)."""
    e = 0.0 if e is None else e
    cdf = lambda x: phi((x - e) / SD_MARGIN)
    p10 = cdf(10) - cdf(-10)
    p20 = cdf(20) - cdf(-20)
    return [p10, p20 - p10, 1 - p20]


# ── data ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def walk_data():
    if '--cache' in sys.argv and os.path.exists(CACHE):
        return json.load(open(CACHE))
    import build_prop_model_v2 as V2
    import build_prop_model_v3_full as F
    I = F.inputs()
    pool = []
    recs = V2.walk(I['box'], I['inj'], I['margins'], I['mm'], I['casc'], I['team_min'], I['lines'], pool=pool)[0]
    slim = [{'gid': int(r['gid']), 'aid': r['aid'], 'mu': {s: r['mu'][s] for s in STATS}, 'y': {s: r['y'][s] for s in STATS}} for r in recs if r['season'] >= TEST - 1]
    out = {'pool': pool, 'recs': slim}
    json.dump(out, open(CACHE, 'w'), separators=(',', ':'))
    return out


def add_history(pool):
    """Per-row last-3 minutes minus EWMA, team games since he last played, rank in the pool by EWMA; team game number. Chronological, state before the game."""
    import nba_common as C
    import build_prop_model_v2 as V2
    box = C.player_games(V2.SEASONS)
    by_gid = defaultdict(list)
    for r in pool:
        by_gid[r['gid']].append(r)
    last3, last_idx, tgc = defaultdict(lambda: deque(maxlen=3)), {}, defaultdict(int)
    for g in C.games(V2.SEASONS):
        rows = by_gid.get(g['game_id'])
        brows = box.get(g['game_id'], [])
        if not brows:
            continue
        if rows:
            groups = defaultdict(list)
            for r in rows:
                groups[r['team']].append(r)
            for team, rs in groups.items():
                for rank, r in enumerate(sorted(rs, key=lambda q: -q['m']), 1):
                    r['rank'] = rank
                for r in rs:
                    h = last3[r['aid']]
                    r['d3'] = (sum(h) / len(h) - r['m']) if h else 0.0
                    li = last_idx.get((g['season'], r['aid'], team))
                    r['gap'] = min(10, tgc[(g['season'], team)] - li) if li is not None else (0 if tgc[(g['season'], team)] < 3 else 10)   # no appearance yet this season: neutral in the first 3 team games
                    r['k'] = tgc[(g['season'], team)] + 1
                    r['size'] = len(rs)
        for r in brows:
            if r['played']:
                last3[r['athlete_id']].append(r['minutes'])
                last_idx[(g['season'], r['athlete_id'], r['team'])] = tgc[(g['season'], r['team'])] + 1
        for team in {r['team'] for r in brows}:
            tgc[(g['season'], team)] += 1
    # the "gap" counts team games since his last appearance: tgc is the count before this game, li the index of his last game
    return pool


# ── features and small models (stdlib) ───────────────────────────────────────────────────────────────────────────────────────

def xs_common(r):
    return [1.0, r['m'] / 48.0, r['st'], min(r['n'], 30) / 30.0, r['rank'] / 10.0, 1.0 if r['rank'] > 8 else 0.0, r['d3'] / 10.0, r['gap'] / 10.0,
            min(r['last_days'], 30) / 30.0, r['vs'] / 48.0, r['vo'] / 48.0, r['nout'] / 5.0, r['b2b'], r['home']]


def xs_min(r):
    return [1.0, r['m'] / 48.0, r['st'], r['vs'] / 48.0, r['vo'] / 48.0, r['d3'] / 10.0, r['b2b'], r['home'], r['rank'] / 10.0, r['nout'] / 5.0]


def xs_b(r):
    p20 = pis(r['e'])[2]
    return xs_common(r) + [p20, p20 * r['rank'] / 10.0, p20 * r['st']]


def logit_fit(rows, xf, yf):
    D = [{'x': xf(r), 'y': yf(r)} for r in rows]
    return LS.fit(D, lambda d: d['x'], lam=LAM, it=ITERS)


def lp(w, x):
    return LS.sig(sum(a * b for a, b in zip(w, x)))


def ols(rows, xf, yf, ridge=1e-6):
    X = [xf(r) for r in rows]; y = [yf(r) for r in rows]; k = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (ridge if i == j else 0.0) for j in range(k)] + [sum(x[i] * v for x, v in zip(X, y))] for i in range(k)]
    for i in range(k):
        piv = max(range(i, k), key=lambda q: abs(A[q][i])); A[i], A[piv] = A[piv], A[i]
        for j in range(i + 1, k):
            f = A[j][i] / A[i][i]
            for c in range(i, k + 1):
                A[j][c] -= f * A[i][c]
    w = [0.0] * k
    for i in reversed(range(k)):
        w[i] = (A[i][k] - sum(A[i][j] * w[j] for j in range(i + 1, k))) / A[i][i]
    return w


def fit_set(rows_all, rows_plays_train, xf_p, xf_r, xf_m, name):
    """Models for one set of rows: P(plays) (on the plays-season rows), P(rot | plays), minutes given rotation, g = mean minutes of non-rotation players who played."""
    played = [r for r in rows_all if r['played']]
    rot = [r for r in played if r['min'] >= ROT_CUT]
    non = [r for r in played if r['min'] < ROT_CUT]
    print(f'  fitting {name}: pool {len(rows_plays_train)} (plays), played {len(played)}, rotation {len(rot)}', flush=True)
    return {'wp': logit_fit(rows_plays_train, xf_p, lambda r: 1 if r['played'] else 0),
            'wr': logit_fit(played, xf_r, lambda r: 1 if r['min'] >= ROT_CUT else 0),
            'wm': ols(rot, xf_m, lambda r: r['min']),
            'g': st.mean(r['min'] for r in non) if non else 3.0}


def predict(M, r, xf_p, xf_r, xf_m):
    """(P(plays), P(rot | plays), E[min | plays]) for one row under one model set."""
    pp, pr = lp(M['wp'], xf_p(r)), lp(M['wr'], xf_r(r))
    mu = max(ROT_CUT, sum(a * b for a, b in zip(M['wm'], xf_m(r))))
    return pp, pr, pr * mu + (1 - pr) * M['g']


def rescale(preds, T):
    """preds: [(P(plays), cond minutes)] for one team-game pool -> conditional minutes after the pool's unconditional total is set to T."""
    tot = sum(p * m for p, m in preds)
    f = T / tot if tot > 0 and len(preds) >= 7 else 1.0
    return [min(48.0, f * p * m / max(p, 1e-3)) for p, m in preds]


# ── scoring ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def gain_stats(items, val):
    by = defaultdict(list)
    for it in items:
        by[it['gid']].append(val(it))
    if len(by) < 5:
        return None
    b = EB.boot(by)
    return {'gain': round(b['mean'], 4), 't': round(b['t'], 2) if b['t'] is not None else None, 'ci95': [round(x, 4) for x in b['ci']], 'games': b['games'], 'rows': b['rows']}


def main():
    data = walk_data()
    pool = data['pool']
    add_history(pool)
    pool = [r for r in pool if 'rank' in r and r['pm'] >= 0]
    print('pool rows', len(pool), 'seasons', sorted({r['season'] for r in pool}), flush=True)
    train = [r for r in pool if r['season'] in FIT_SEASONS]
    test = [r for r in pool if r['season'] == TEST]
    plays_train = [r for r in train if r['season'] in PLAYS_SEASONS]
    # mean actual team total (pool players) on the fit seasons
    tt = defaultdict(float)
    for r in train:
        tt[(r['gid'], r['team'])] += r['min']
    T = st.mean(tt.values())
    # per-state model sets
    sets = []
    for s in range(3):
        rs = [r for r in train if state_of(r['fm']) == s]
        sets.append(fit_set(rs, [r for r in plays_train if state_of(r['fm']) == s], xs_common, xs_common, xs_min, STATES[s]))
    B = fit_set(train, plays_train, xs_b, xs_b, xs_min, 'single (control B)')
    # predict test season by team-game pool
    groups = defaultdict(list)
    for r in test:
        groups[(r['gid'], r['team'])].append(r)
    for key, rs in groups.items():
        pr_state = [[predict(sets[s], r, xs_common, xs_common, xs_min) for r in rs] for s in range(3)]
        pi = [pis(rs[0]['e']) for _ in rs]
        # mixture: P(plays), P(rot|plays), minutes|plays all mixed by pi
        mixp = [sum(pi[i][s] * pr_state[s][i][0] for s in range(3)) for i in range(len(rs))]
        mixr = [sum(pi[i][s] * pr_state[s][i][1] for s in range(3)) for i in range(len(rs))]
        mixm = [sum(pi[i][s] * pr_state[s][i][2] for s in range(3)) for i in range(len(rs))]
        cm = rescale(list(zip(mixp, mixm)), T)
        bp = [predict(B, r, xs_b, xs_b, xs_min) for r in rs]
        bm = rescale([(p, m) for p, _, m in bp], T)
        for i, r in enumerate(rs):
            r['C'], r['B'], r['p_rot'], r['p_plays'] = cm[i], bm[i], mixr[i], mixp[i]
        ts = state_of(rs[0]['fm'])                                           # state-conditional accuracy: the game's true state known (context only)
        sp_all = rescale([(pr_state[ts][j][0], pr_state[ts][j][2]) for j in range(len(rs))], T)
        for i, r in enumerate(rs):
            r['S'] = sp_all[i]
    played = [r for r in test if r['played'] and r['pm'] > 0]
    res = {'T': round(T, 2), 'fit_rows': len(train), 'plays_rows': len(plays_train), 'test_pool_rows': len(test), 'test_played_rows': len(played),
           'test_games': len({r['gid'] for r in played})}
    for r in played:
        r['gA'] = abs(r['min'] - r['pm']) - abs(r['min'] - r['C'])
        r['gB'] = abs(r['min'] - r['pm']) - abs(r['min'] - r['B'])
        r['gCB'] = abs(r['min'] - r['B']) - abs(r['min'] - r['C'])
    res['mae'] = {'A': round(st.mean(abs(r['min'] - r['pm']) for r in played), 4), 'C': round(st.mean(abs(r['min'] - r['C']) for r in played), 4),
                  'B': round(st.mean(abs(r['min'] - r['B']) for r in played), 4), 'S_true_state': round(st.mean(abs(r['min'] - r['S']) for r in played), 4)}
    res['primary'] = gain_stats(played, lambda r: r['gA'])
    cuts = {'a_rotation_player_out': lambda r: r['nout'] >= 1, 'b_lopsided_pregame': lambda r: abs(r['e'] or 0) > 8, 'c_rank_9_to_12': lambda r: 9 <= r['rank'] <= 12,
            'd_starters_in_blowouts': lambda r: r['st'] >= 0.5 and r['fm'] >= 20, 'e_first_15_team_games': lambda r: r['k'] <= 15}
    res['cuts'] = {k: gain_stats([r for r in played if f(r)], lambda r: r['gA']) for k, f in cuts.items()}
    res['context'] = {'B_vs_A': gain_stats(played, lambda r: r['gB']), 'C_vs_B': gain_stats(played, lambda r: r['gCB']),
                      'S_vs_A_true_state': gain_stats(played, lambda r: abs(r['min'] - r['pm']) - abs(r['min'] - r['S'])),
                      'share_p_plays_under_half': round(sum(1 for r in test if r['p_plays'] < .5) / len(test), 4)}
    # props
    rec = {(x['gid'], x['aid']): x for x in data['recs']}
    R = [(r, rec[(r['gid'], r['aid'])]) for r in played if (r['gid'], r['aid']) in rec]
    mae = {s: st.mean(abs(x['y'][s] - x['mu'][s]) for _, x in R) for s in STATS}
    by, per = defaultdict(list), {}
    for s in STATS:
        eo, en = [], []
        for r, x in R:
            mun = x['mu'][s] * r['C'] / r['pm']
            eo.append(abs(x['y'][s] - x['mu'][s])); en.append(abs(x['y'][s] - mun))
            by[r['gid']].append((eo[-1] - en[-1]) / mae[s])
        per[s] = {'mae_old': round(st.mean(eo), 4), 'mae_new': round(st.mean(en), 4), 'better': st.mean(en) <= st.mean(eo)}
    b = EB.boot(by)
    res['props'] = {'pooled_gain': round(b['mean'], 5), 't': round(b['t'], 2) if b['t'] is not None else None, 'games': b['games'], 'per_stat': per}
    # calibration of P(rotation | plays)
    bands = [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]
    cal = {}
    for lo, hi in bands:
        sel = [r for r in played if lo <= r['p_rot'] < hi]
        if sel:
            cal[f'{int(lo*100)}-{min(100,int(hi*100))}'] = {'n': len(sel), 'predicted': round(st.mean(r['p_rot'] for r in sel), 4), 'actual': round(st.mean(1 if r['min'] >= ROT_CUT else 0 for r in sel), 4)}
    res['calibration'] = cal
    P, cu = res['primary'], res['cuts']
    conds = {'primary_t_ge_2_5': bool(P and P['t'] is not None and P['t'] >= 2.5),
             'all_five_cuts_positive': all(v and v['gain'] > 0 for v in cu.values()),
             'cuts_a_and_c_t_ge_2_5': all(cu[k] and cu[k]['t'] is not None and cu[k]['t'] >= 2.5 for k in ('a_rotation_player_out', 'c_rank_9_to_12')),
             'no_cut_t_le_minus_2_5': all(not (v and v['t'] is not None and v['t'] <= -2.5) for v in cu.values()),
             'props_t_ge_2_5': bool(res['props']['t'] is not None and res['props']['t'] >= 2.5),
             'no_stat_worse': all(v['better'] for v in per.values()),
             'calibration_within_4': all(abs(v['predicted'] - v['actual']) <= 0.04 for v in cal.values() if v['n'] >= 100)}
    res['conditions'] = conds
    res['verdict'] = 'PASS' if all(conds.values()) else 'FAIL'
    res['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    print(json.dumps(res, indent=1))
    json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
