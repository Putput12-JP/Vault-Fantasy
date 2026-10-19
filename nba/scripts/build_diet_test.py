#!/usr/bin/env python3
"""
Pre-registered test (CourtAI teardown, step 3): does the shot-diet matchup score add anything to the v2 projection beyond the market?

Feature (the Slate page's SHOTS number, built point in time): for a player-game on day D, sum over the zones that held up from the
prior season's first half to its second (build_diet_defense.py's weak-zone cut) of
    share of the player's own shots from that zone  x  how far the opponent's shots allowed per 48 in that zone sit above the league mean.
Everything uses shots from days BEFORE D only; the prior season is blended in exactly as the page does it (a defense's weight on the
current season = its games / 15; a player's prior-season shots weigh 1 - his current shots / 200, floored at 0). Fewer than 50 effective
shots: the feature is 0 (no information).

Candidates, on identical player-games and prices, each with stacker, spread and line calibration refit on 2024-25 as every earlier
candidate was; test 2025-26:
  v2d      v2 plus ONE extra stacker column per stat: projected mean x the diet score. Nothing else changes.
  v2d_ctl  CONTROL: the same column, but the defense is a random other team (fixed seed). Any gain here is an artifact of adding a
           column, not of the matchup. It is never eligible to ship.

Rule, fixed before this ran. The diet score is a PRICING input only if ALL of these hold on 2025-26:
  1. v2d keeps every v2 GO signal at GO with out-of-sample ROI at least v2's (build_prop_model_v3.choose).
  2. v2d has the lower out-of-sample blended Kalshi log loss than v2 on at least 3 of the 4 Kalshi stats (pts, reb, ast, 3pm).
  3. The control does NOT meet 2 (fewer than 3 of 4 stats better than v2).
Otherwise the score stays a display-only fact on the Slate page. The result is reported either way.

  python3 nba/scripts/fetch_hoopr.py --only-pbp 2024 2025 2026   # raw/hoopr/pbp_<season>.csv (~290 MB each)
  python3 nba/scripts/build_diet_test.py
Writes data/diet_test.json and docs/diet-test.md.

RUN 1 WAS VOID, and the rule above did not change. hoopR's 2023-24 ESPN play-by-play carries coordinates for only 7 games (1,267 shots), so
the 2024-25 FIT season had no usable prior: every zone read as weak, the column was all zeros, its coefficient was exactly 0, and v2d was
v2 by construction (the saved first-run output said "v2 stays", which is not a result). Fix, applied to the fit season only: with no full
prior season the weak-zone cut is skipped (all five zones) and a defense counts only after 15 games (before that its vs-league value is 0).
The 2025-26 TEST season keeps the full definition (prior = 2024-25, which has coordinates for all 1,234 games).
"""
import copy, json, os, random, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_prop_model_v2 as V2
import build_prop_model_v3 as A
import build_prop_model_v3_full as F
import build_diet_defense as DD
from build_prop_model import BASE

SENS = '--no-prior' in sys.argv      # sensitivity run, NOT the pre-registered one: the same definition in the fit and test seasons (no prior blend, all zones)
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'diet_test_noprior.json' if SENS else 'diet_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'diet-test-noprior.md' if SENS else 'diet-test.md')
ZK = [k for k, _ in DD.ZONES]
SEASONS = [2024, 2025, 2026]                    # pbp seasons needed: 2024 is the prior for the 2024-25 fit season
SEED = 7


def load():
    out = {}
    for s in SEASONS:
        p = os.path.join(DD.RAW, f'pbp_{s}.csv')
        if not os.path.exists(p):
            sys.exit(f'missing {p}: python3 nba/scripts/fetch_hoopr.py --only-pbp {" ".join(map(str, SEASONS))}')
        shots, maxp, season = DD.read(p)
        out[s] = {'shots': sorted(shots, key=lambda x: x[0]), 'maxp': maxp}
    return out


def weak_zones(A0):
    """Zones whose team ranking did not carry from the first to the second half of the (prior) season."""
    teams = [t for (t, h) in A0['gms'] if h is None]
    bad = set()
    for k in ZK:
        a = {t: DD.rate(A0, t, 0, 'zone', k) for t in teams}
        b = {t: DD.rate(A0, t, 1, 'zone', k) for t in teams}
        a, b = {t: v for t, v in a.items() if v is not None}, {t: v for t, v in b.items() if v is not None}
        r = DD.spearman(a, b)
        if r is None or r < 0.36:
            bad.add(k)
    return bad


def season_feature(shots, maxp, prior, weak):
    """Walk one season's shots by day, snapshotting before each day's shots. -> (score(gid, aid, opp), meta gid -> [day, {teams}], tables day -> team -> zone vs league)."""
    mins = {g: 48 + 5 * max(0, p - 4) for g, p in maxp.items()}
    meta = defaultdict(lambda: [None, set()])
    for (day, g, pid, name, team, opp, *_r) in shots:
        meta[g][0] = day
        meta[g][1].update((team, opp))
    byday = defaultdict(list)
    for g, (day, tms) in meta.items():
        byday[day].append(g)
    cur_allow = defaultdict(lambda: defaultdict(float))
    cur_g = defaultdict(set)
    cur_pl = defaultdict(lambda: [0, defaultdict(int)])
    prior_pl = prior['pl'] if prior else {}
    P_teams = sorted(t for (t, h) in prior['gms'] if h is None) if prior else []
    day_snaps = {}
    use = [k for k in ZK if k not in weak]

    def vs_table():
        t_all = sorted(set(cur_g) | set(P_teams))
        rates = {}
        for t in t_all:
            n = len(cur_g[t]) if t in cur_g else 0
            w = min(1.0, n / DD.MIN_GAMES) if prior else 1.0
            r = {}
            for k in ZK:
                if not prior and n < DD.MIN_GAMES:                       # no prior season: too early to say anything about this defense
                    r[k] = None
                    continue
                new = cur_allow[t][('zone', k)] / n if n else None
                old = DD.rate(prior, t, None, 'zone', k) if prior else None
                r[k] = new if old is None else old if new is None else w * new + (1 - w) * old
            rates[t] = r
        mean = {k: statistics.mean([v[k] for v in rates.values() if v[k] is not None] or [0.0]) for k in ZK}
        return {t: {k: (r[k] / mean[k] - 1) if r[k] is not None and mean[k] else 0.0 for k in ZK} for t, r in rates.items()}

    shots_by_day = defaultdict(list)
    for s_ in shots:
        shots_by_day[s_[0]].append(s_)
    tables = {}
    for day in sorted(byday):
        tables[day] = vs_table()                                          # snapshot BEFORE the day's shots
        # share vectors needed on this day are computed from the counters as they stand now
        day_snaps[day] = {pid: share(cur_pl.get(pid), prior_pl.get(pid)) for pid in set(list(cur_pl) + list(prior_pl))}
        for (d_, g, pid, name, team, opp, z, *_r) in shots_by_day[day]:
            w = 48.0 / mins[g]
            cur_allow[opp][('zone', z)] += w
            cur_g[opp].add(g)
            cur_pl[pid][0] += 1
            cur_pl[pid][1][z] += 1

    def score(gid, aid, opp):
        d = meta[gid][0]
        sh = day_snaps[d].get(aid)
        vs = tables[d].get(opp)
        if not sh or vs is None:
            return 0.0
        return sum(sh[k] * vs[k] for k in use)
    return score, meta, tables


def share(c, o):
    cn = c[0] if c else 0
    kf = max(0.0, 1 - cn / DD.THIN_FGA) if o else 0.0
    n = cn + kf * (o['n'] if o else 0)
    if n < DD.MIN_FGA_PLAYER:
        return None
    return {k: ((c[1][k] if c else 0) + kf * (o['zone'][k] if o else 0)) / n for k in ZK}


def build_features(P, recs):
    """-> {(gid, aid): (score, control_score)} for the 2025 and 2026 seasons, plus coverage counts."""
    aggs = {s: DD.aggregate(P[s]['shots'], P[s]['maxp']) for s in P}
    out, cov = {}, defaultdict(lambda: [0, 0])
    rng = random.Random(SEED)
    for s in (2025, 2026):
        prior = aggs[s - 1] if aggs[s - 1]['games'] >= DD.FULL_SEASON_GAMES and not SENS else None      # run 1: 2023-24 has no coordinates
        weak = weak_zones(prior) if prior else set()
        score, meta, tables = season_feature(P[s]['shots'], P[s]['maxp'], prior, weak)
        print(f'season {s}: weak zones {sorted(weak) or "none"}', flush=True)
        for r in recs:
            if r['season'] != s:
                continue
            cov[s][1] += 1
            m = meta.get(str(r['gid']))
            if not m or r['team'] not in m[1]:
                continue
            opp = next(iter(m[1] - {r['team']}), None)
            if opp is None:
                continue
            day = m[0]
            teams = sorted(t for t in tables[day] if t not in (opp, r['team']))
            ctl = rng.choice(teams) if teams else opp
            out[(r['gid'], r['aid'])] = (score(str(r['gid']), str(r['aid']), opp), score(str(r['gid']), str(r['aid']), ctl))
            cov[s][0] += 1
    return out, {s: v for s, v in cov.items()}


def with_feature(recs, feats, idx):
    out = []
    for r in recs:
        f = feats.get((r['gid'], r['aid']))
        d = f[idx] if f else 0.0
        r2 = dict(r)
        r2['x'] = {s: r['x'][s][:-1] + [r['mu'][s] * d] + [r['x'][s][-1]] for s in BASE}
        out.append(r2)
    return out


HEAD = ['# Shot diet score vs v2: pre-registered test', '',
        'Generated {generated} by `nba/scripts/build_diet_test.py`. Fit on 2024-25, tested on 2025-26,',
        '{n_test:,} identical player-games and prices for every model.', '',
        'Run 1 was void (no usable prior season for the fit year, so the column was zero); see the script docstring. The pre-registered result is run 2 (diet-test.md); this file is the --no-prior SENSITIVITY run: the fit and test seasons share one definition (current season only, all five zones, a defense counts after 15 games).' if SENS else 'Run 1 was void (no usable prior season for the fit year, so the column was zero); see the script docstring. This is run 2, same rule.', '',
        '- **v2**: shipped. **v2d**: v2 plus one stacker column per stat, projected mean x the point-in-time shot diet score (zones that held up',
        '  from the prior season\'s first half to its second). **v2d_ctl**: the control, same column with a random other team\'s defense.', '',
        'Rule (fixed before running): the score becomes a pricing input only if v2d keeps every v2 GO at GO with ROI at least v2\'s, AND its',
        'out-of-sample blended Kalshi log loss beats v2\'s on at least 3 of 4 stats, AND the control does not. Otherwise it stays display-only.']
FOOT = ['Coverage (player-games with a diet score / all): {coverage}. Related: [courtai-teardown.md](courtai-teardown.md), [prop-model-v3-full.md](prop-model-v3-full.md).']


def main():
    I = F.inputs()
    recs = F.walk_v2(I)
    P = load()
    feats, cov = build_features(P, recs)
    cand = {'v2d': with_feature(recs, feats, 0), 'v2d_ctl': with_feature(recs, feats, 1)}
    res = F.compare(recs, cand, None)
    sd = statistics.pstdev([v[0] for v in feats.values()])
    res['diet_sd'] = round(sd, 4)
    res['coverage'] = {str(s): f'{a:,} / {b:,}' for s, (a, b) in cov.items()}
    # rule, as written in the docstring
    k4 = ['pts', 'reb', 'ast', '3pm']
    better = lambda nm: sum(res['kalshi'][m][nm]['blend_oos_logloss'] < res['kalshi'][m]['v2']['blend_oos_logloss'] for m in k4)
    keep = dict(res, names=['v2', 'v2d'])
    res['rule'] = {'1_keeps_gos': A.choose(keep) == 'v2d', '2_v2d_better_stats': better('v2d'), '3_control_better_stats': better('v2d_ctl')}
    res['pricing_input'] = res['rule']['1_keeps_gos'] and res['rule']['2_v2d_better_stats'] >= 3 and res['rule']['3_control_better_stats'] < 3
    res['ship'] = 'v2d' if res['pricing_input'] else 'v2 (diet score stays display-only)'
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    F.write_md(res, HEAD, FOOT, OUT_MD)
    extra = ['', '## The diet column in the stacker (fit on 2024-25)', '',
             f"Score sd {res['diet_sd']} (a fraction: 0.01 = one percent more shots than average in his spots). Coefficient is on projected mean x score; t is the fit-season t.", '',
             '| Stat | v2d coef (t) | control coef (t) |', '|---|---|---|']
    for s in BASE:
        a, b = res['stacker']['v2d'][s], res['stacker']['v2d_ctl'][s]
        extra.append(f"| {s} | {a['beta'][-2]:+.3f} ({a['t'][-2]}) | {b['beta'][-2]:+.3f} ({b['t'][-2]}) |")
    extra += ['', '## Rule', '', f"1. v2d keeps every v2 GO at GO with ROI at least v2's: **{res['rule']['1_keeps_gos']}**.",
              f"2. v2d beats v2's blended Kalshi log loss on {res['rule']['2_v2d_better_stats']} of 4 stats (need 3).",
              f"3. The control beats v2 on {res['rule']['3_control_better_stats']} of 4 stats (must be under 3).", '',
              f"**Result: {res['ship']}.**", '']
    open(OUT_MD, 'a').write('\n'.join(extra))
    print(open(OUT_MD).read())


if __name__ == '__main__':
    main()
