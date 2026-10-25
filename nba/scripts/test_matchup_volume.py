#!/usr/bin/env python3
"""
Matchup volume test, Stage 1. Rules: docs/matchup-volume-test.md (committed before this file existed). Nothing here changes pricing.

  python3 nba/scripts/test_matchup_volume.py          walk the prop model (about 6 min) + read the play-by-play, score once -> data/matchup_volume.json
  python3 nba/scripts/test_matchup_volume.py --cache  reuse the cached walk records

Needs raw/hoopr/pbp_2024.csv, pbp_2025.csv, pbp_2026.csv (python3 nba/scripts/fetch_hoopr.py --only-pbp 2024 2025 2026).
"""
import json, os, random, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_diet_defense as DD
import test_early_minutes_blend as EB       # boot()

OUT = os.path.join(HERE, '..', 'data', 'matchup_volume_corrected.json')
CACHE = os.environ.get('MATCHUP_CACHE', '/tmp/matchup_recs.json')
FIT, TEST, SEED = 2025, 2026, 7
MIN_GAMES, THIN_FGA, THIN_AST = 15, 200.0, 80.0
MIN_SHOTS, MIN_3SHARE, MIN_ASTS = 50.0, 0.05, 30.0
ZK = ['ra', 'paint', 'mid', 'c3', 'ab3']
AK = ['rim', 'smid', 'lmid', 'c3', 'arc3']
CLIP = (0.7, 1.3)
REAL_TEAM_GAMES = 20                    # a real team has played this many games (the All-Star game's teams have one); the page's file uses the same cut (MIN_TEAM_G)


def walk_records():
    if '--cache' in sys.argv and os.path.exists(CACHE):
        return json.load(open(CACHE))
    import build_prop_model_v3_full as F
    recs = F.walk_v2(F.inputs())
    slim = [{'gid': str(r['gid']), 'season': r['season'], 'aid': str(r['aid']), 'team': r['team'], 'pm': r['pm'], 'r3': r.get('r3'), 'y3pa': r['y3pa'],
             'mu3': r['mu']['3pm'], 'y3': r['y']['3pm'], 'mua': r['mu']['ast'], 'ya': r['y']['ast']} for r in recs if r['season'] in (FIT, TEST) and r['pm'] > 0]
    json.dump(slim, open(CACHE, 'w'), separators=(',', ':'))
    return slim


def read_pbp(season):
    """Shots and minutes per game, **real teams only**. The play-by-play carries the All-Star game as a regular-season game with invented teams
    (CAN, CHK, KEN, SHQ in 2024-25; STARS, STRIPES, WORLD in 2025-26); counted as defenses they distorted the league mean of the first run."""
    shots, maxp, _ = DD.read(os.path.join(DD.RAW, f'pbp_{season}.csv'))
    n = defaultdict(int)
    for s_ in shots:
        n[s_[4]] += 1
    games = defaultdict(set)
    for s_ in shots:
        games[s_[4]].add(s_[1])
    real = {t for t, g in games.items() if len(g) >= REAL_TEAM_GAMES}
    shots = [s_ for s_ in shots if s_[4] in real and s_[5] in real]
    return sorted(shots, key=lambda x: x[0]), {g: 48 + 5 * max(0, p - 4) for g, p in maxp.items()}


def season_totals(shots, mins):
    """Full-season per-team allowance per 48 and per-player counts: the prior for the next season."""
    allow, gm = defaultdict(lambda: defaultdict(float)), defaultdict(set)
    pz, pa = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    for (day, g, pid, name, team, opp, z, kind, aloc, aid_, aname, *_r) in shots:
        w = 48.0 / mins[g]
        allow[opp][('z', z)] += w
        gm[opp].add(g)
        pz[pid][z] += 1
        if aloc:
            allow[opp][('a', aloc)] += w
            pa[aid_][aloc] += 1
    rates = {t: {k: v / len(gm[t]) for k, v in d.items()} for t, d in allow.items()}
    return rates, pz, pa


def vs_tables(cur_allow, cur_g, prior_rates):
    """Per defense: vs league mean for each zone and assist location, and the opponent-only aggregates. None where there is no information yet."""
    teams = sorted(set(cur_g) | set(prior_rates or {}))
    rates = {}
    for t in teams:
        n = len(cur_g[t]) if t in cur_g else 0
        w = min(1.0, n / MIN_GAMES) if prior_rates else 1.0
        r = {}
        for key in [('z', k) for k in ZK] + [('a', k) for k in AK]:
            if not prior_rates and n < MIN_GAMES:
                r[key] = None
                continue
            new = cur_allow[t][key] / n if n else None
            old = (prior_rates.get(t) or {}).get(key) if prior_rates else None
            r[key] = new if old is None else old if new is None else w * new + (1 - w) * old
        r[('z3',)] = None if r[('z', 'c3')] is None or r[('z', 'ab3')] is None else r[('z', 'c3')] + r[('z', 'ab3')]
        r[('aall',)] = None if any(r[('a', k)] is None for k in AK) else sum(r[('a', k)] for k in AK)
        rates[t] = r
    keys = list(next(iter(rates.values())).keys()) if rates else []
    mean = {k: st.mean([v[k] for v in rates.values() if v[k] is not None] or [0.0]) for k in keys}
    return {t: {k: (r[k] / mean[k] - 1) if r[k] is not None and mean[k] else None for k in keys} for t, r in rates.items()}


def shares(cur, prior, thin, keys):
    cn = sum(cur.values()) if cur else 0.0
    kf = max(0.0, 1 - cn / thin) if prior else 0.0
    pn = sum(prior.values()) if prior else 0.0
    n = cn + kf * pn
    if n <= 0:
        return None, 0.0
    return {k: ((cur.get(k, 0.0) if cur else 0.0) + kf * (prior.get(k, 0.0) if prior else 0.0)) / n for k in keys}, n


def indices(season, recs, shots, mins, prior):
    """-> {(gid, aid): {'m3', 'ma', 'm3c', 'mac', 't3', 'ta'}} point in time (None = not defined)."""
    prior_rates, prior_pz, prior_pa = prior if prior else (None, {}, {})
    by_gid = defaultdict(list)
    for r in recs:
        if r['season'] == season:
            by_gid[r['gid']].append(r)
    day_of, teams_of, by_day = {}, defaultdict(set), defaultdict(list)
    for s_ in shots:
        day_of[s_[1]] = s_[0]
        teams_of[s_[1]].update((s_[4], s_[5]))
    for g, d in day_of.items():
        by_day[d].append(g)
    cur_allow, cur_g = defaultdict(lambda: defaultdict(float)), defaultdict(set)
    cur_pz, cur_pa = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    shots_day = defaultdict(list)
    for s_ in shots:
        shots_day[s_[0]].append(s_)
    rng = random.Random(SEED)
    out = {}
    for day in sorted(by_day):
        tab = vs_tables(cur_allow, cur_g, prior_rates)                                 # BEFORE the day's shots
        for g in by_day[day]:
            for r in by_gid.get(g, ()):
                opp = next(iter(teams_of[g] - {r['team']}), None)
                if opp is None or opp not in tab:
                    continue
                others = sorted(t for t in tab if t not in (opp, r['team']))
                ctl = rng.choice(others) if others else opp
                pid = r['aid']
                shz, nz = shares(cur_pz.get(pid), prior_pz.get(pid), THIN_FGA, ZK)
                sha, na = shares(cur_pa.get(pid), prior_pa.get(pid), THIN_AST, AK)
                rec = {}
                for tag, team in (('', opp), ('c', ctl)):
                    v = tab[team]
                    m3 = ma = None
                    if shz and nz >= MIN_SHOTS and v[('z', 'c3')] is not None and v[('z', 'ab3')] is not None:
                        s3 = shz['c3'] + shz['ab3']
                        if s3 >= MIN_3SHARE:
                            m3 = (shz['c3'] * v[('z', 'c3')] + shz['ab3'] * v[('z', 'ab3')]) / s3
                    if sha and na >= MIN_ASTS and all(v[('a', k)] is not None for k in AK):
                        ma = sum(sha[k] * v[('a', k)] for k in AK)
                    rec['m3' + tag], rec['ma' + tag] = m3, ma
                rec['t3'], rec['ta'] = tab[opp][('z3',)], tab[opp][('aall',)]
                out[(g, pid)] = rec
        for (d_, g, pid, name, team, opp, z, kind, aloc, aid_, aname, *_r) in shots_day[day]:
            w = 48.0 / mins[g]
            cur_allow[opp][('z', z)] += w
            cur_g[opp].add(g)
            cur_pz[pid][z] += 1
            if aloc:
                cur_allow[opp][('a', aloc)] += w
                cur_pa[aid_][aloc] += 1
    return out


def slope(rows):
    """Least squares through the origin: residual on projected x index."""
    num = sum(x * res for x, res in rows)
    den = sum(x * x for x, res in rows)
    return num / den if den else 0.0


def slope_t(items, draws=2000):
    """items: [(gid, x, res)] -> (beta, t) resampling games."""
    by = defaultdict(list)
    for g, x, res in items:
        by[g].append((x, res))
    gk = list(by)
    beta = slope([v for g in gk for v in by[g]])
    rng = random.Random(SEED)
    bs = []
    for _ in range(draws):
        bs.append(slope([v for g in rng.choices(gk, k=len(gk)) for v in by[g]]))
    sd = st.pstdev(bs)
    return beta, (beta / sd if sd else None), len(gk)


def evaluate(stat, rows, beta):
    """rows: dicts with p (projection of the volume), a (actual volume), idx, idxc, tidx, s_p, s_a (stat projection and actual), gid. Frozen beta."""
    mult = lambda i: min(CLIP[1], max(CLIP[0], 1 + beta * i))
    res = {}
    for name, key in (('matchup', 'idx'), ('control', 'idxc'), ('team_only_context', 'tidx')):
        vol, stt = defaultdict(list), defaultdict(list)
        for r in rows:
            m = mult(r[key])
            vol[r['gid']].append(abs(r['a'] - r['p']) - abs(r['a'] - r['p'] * m))
            stt[r['gid']].append(abs(r['s_a'] - r['s_p']) - abs(r['s_a'] - r['s_p'] * m))
        v, s_ = EB.boot(vol), EB.boot(stt)
        res[name] = {'vol_mae_gain': round(v['mean'], 5), 'vol_t': round(v['t'], 2) if v['t'] is not None else None,
                     'stat_mae_gain': round(s_['mean'], 5), 'stat_t': round(s_['t'], 2) if s_['t'] is not None else None, 'games': v['games'], 'rows': v['rows']}
    gids = sorted({r['gid'] for r in rows})
    half = set(gids[:len(gids) // 2])
    res['halves_vol_gain'] = [round(st.mean(abs(r['a'] - r['p']) - abs(r['a'] - r['p'] * mult(r['idx'])) for r in rows if (r['gid'] in half) == h), 5) for h in (True, False)]
    srt = sorted(rows, key=lambda r: r['idx'])
    q = len(srt) // 5
    res['quintile_mean_residual_pct'] = [round(100 * st.mean((r['a'] - r['p']) / max(r['p'], 0.5) for r in srt[i * q:(i + 1) * q]), 2) for i in range(5)]
    res['quintile_mean_index'] = [round(st.mean(r['idx'] for r in srt[i * q:(i + 1) * q]), 4) for i in range(5)]
    return res


def build_rows(recs, idx, stat):
    out = []
    for r in recs:
        f = idx.get((r['gid'], r['aid']))
        if not f:
            continue
        if stat == '3pm':
            if r['r3'] is None or f['m3'] is None or f['m3c'] is None or f['t3'] is None:
                continue
            p = r['pm'] * r['r3']
            out.append({'gid': r['gid'], 'p': p, 'a': r['y3pa'], 'idx': f['m3'], 'idxc': f['m3c'], 'tidx': f['t3'], 's_p': r['mu3'], 's_a': r['y3']})
        else:
            if f['ma'] is None or f['mac'] is None or f['ta'] is None:
                continue
            out.append({'gid': r['gid'], 'p': r['mua'], 'a': r['ya'], 'idx': f['ma'], 'idxc': f['mac'], 'tidx': f['ta'], 's_p': r['mua'], 's_a': r['ya']})
    return out


def main():
    recs = walk_records()
    print('walk records', len(recs), flush=True)
    P = {s: read_pbp(s) for s in (2024, 2025, 2026)}
    priors = {2025: None, 2026: season_totals(*P[2025])}                      # 2024-25 has no usable prior (2023-24 pbp has no coordinates)
    idx = {}
    for s in (FIT, TEST):
        idx.update(indices(s, recs, P[s][0], P[s][1], priors[s]))
    print('indexed rows', len(idx), flush=True)
    shot_teams = {t for s_ in (FIT, TEST) for sh in P[s_][0][:200000] for t in (sh[4], sh[5])}
    rec_teams = {r['team'] for r in recs}
    print('team abbreviations in the walk but not in the play-by-play:', sorted(rec_teams - shot_teams), flush=True)
    res = {'coverage': {}}
    for stat, key in (('3pm', 'volume=3PA'), ('ast', 'volume=assists')):
        fit_rows = build_rows([r for r in recs if r['season'] == FIT], idx, stat)
        test_rows = build_rows([r for r in recs if r['season'] == TEST], idx, stat)
        beta = slope([(r['p'] * r['idx'], r['a'] - r['p']) for r in fit_rows])
        b26, t26, g26 = slope_t([(r['gid'], r['p'] * r['idx'], r['a'] - r['p']) for r in test_rows])
        ev = evaluate(stat, test_rows, beta)
        n_all = {s: sum(1 for r in recs if r['season'] == s) for s in (FIT, TEST)}
        conds = {'beta_fit_positive': beta > 0,
                 'volume_gain_t_ge_2_5': (ev['matchup']['vol_t'] or 0) >= 2.5,
                 'control_not_t_ge_2_5': (ev['control']['vol_t'] or 0) < 2.5,
                 'own_slope_2025_26_positive_t_ge_2_5': b26 > 0 and (t26 or 0) >= 2.5,
                 'both_halves_positive': all(x > 0 for x in ev['halves_vol_gain']),
                 'stat_mae_not_worse': ev['matchup']['stat_mae_gain'] >= 0}
        res[stat] = {'volume': key, 'fit_rows': len(fit_rows), 'test_rows': len(test_rows), 'beta_fit_2024_25': round(beta, 4), 'beta_own_2025_26': round(b26, 4),
                     'beta_own_t': round(t26, 2) if t26 is not None else None, 'eval_2025_26': ev, 'conditions': conds, 'verdict': 'PASS' if all(conds.values()) else 'FAIL'}
        res['coverage'][stat] = {'fit_scored_of': [len(fit_rows), n_all[FIT]], 'test_scored_of': [len(test_rows), n_all[TEST]]}
    res['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    print(json.dumps(res, indent=1))
    if os.path.exists(OUT):
        print('The result file exists; not overwritten.')
    else:
        json.dump(res, open(OUT, 'w'), indent=1)


if __name__ == '__main__':
    main()
