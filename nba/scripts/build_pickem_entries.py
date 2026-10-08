#!/usr/bin/env python3
"""
Pick'em entries built from independent picks. Rules: docs/pickem-entries.md (committed before this ran).

  python3 nba/scripts/build_pickem_entries.py
Writes nba/data/pickem_entries.json and nba/docs/pickem-entries-results.md
"""
import csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM
import build_prop_model as P

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'pickem_entries.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'pickem-entries-results.md')
PAY = {2: 3.0, 3: 5.0, 4: 10.0, 5: 20.0, 6: 37.5}
SIZES = [2, 3, 4, 5, 6]
STRATS = ['S1', 'S2', 'S3']
PER_DAY = 3
NEAR_EVEN = '--run1' not in sys.argv      # run 1 (kept as the record) had no price restriction
MIN_FIT_ENTRIES, MIN_TEST_ENTRIES, MIN_TEST_DAYS, GO_Z, WATCH_Z = 100, 100, 40, 2.4, 1.65


def legs():
    """Every usable main-line leg: dict with season, day, game, player, market, line, over, pm (model chance of the over), pk (market no-vig)."""
    box = C.player_games(P.WARM + P.TUNE + P.TEST)
    inj = C.InjuryAsOf(P.TEST, C.player_index(box))
    margins = MM.expected_margins(box)
    mm = json.load(open(MM.OUT_JSON))
    casc = json.load(open(os.path.join(C.HERE, '..', 'data', 'usage_cascade.json')))['stats']
    tr = P.walk(P.WARM + P.TUNE, box, None, P.TUNE[0], 'oracle', margins, mm, casc)
    ratio = sum(r['min'] for r in tr) / sum(r['pred']['tip'][0] for r in tr)
    team_min = round(240.0 * ratio, 1)
    tr = P.walk(P.WARM + P.TUNE, box, None, P.TUNE[0], 'oracle', margins, mm, casc, team_min)
    V = P.fit_variance(tr)
    te = P.walk(P.WARM + P.TUNE + P.TEST, box, inj, P.TEST[0], 'report', margins, mm, casc, team_min)
    proj = {(r['gid'], r['aid']): r for r in te}
    print(f'projections: tune {len(tr):,}  test {len(te):,}', flush=True)
    rows = []
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'props_espn.csv'))):
        if r['kind'] != 'main' or r['played'] != '1' or r['market'] not in P.MARKETS:
            continue
        pr = proj.get((int(r['game_id']), int(r['athlete_id'])))
        if not pr:
            continue
        season = r['season']
        if season == '2025':
            line, opx, upx, clock = r['line_open'], r['over_px_open'], r['under_px_open'], 'open'
        elif season == '2026' and r['cur_is_pretip'] == '1':
            line, opx, upx, clock = r['line_cur'], r['over_px_cur'], r['under_px_cur'], 'tip'
        else:
            continue
        po, pu = P.am_prob(opx), P.am_prob(upx)
        if not line or po is None or pu is None or not (1.0 <= po + pu <= 1.15) or not (0.12 < po < 0.88 and 0.12 < pu < 0.88):
            continue
        if NEAR_EVEN and not (0.45 <= po / (po + pu) <= 0.55):      # run 2: only lines a pick'em app could post (see docs/pickem-entries.md, amendment)
            continue
        L, act = float(line), float(r['actual'])
        if act == L:
            continue
        mu = pr['pred'].get('am' if clock == 'open' else 'tip', pr['pred']['tip'])[1][r['market']]
        rows.append({'season': season, 'day': r['tip'][:10], 'game': r['game_id'], 'aid': r['athlete_id'], 'market': r['market'], 'line': L,
                     'over': act > L, 'pk': po / (po + pu), 'pm_raw': P.p_over(r['market'], mu, L, V)})
    cal = {}
    for m in P.MARKETS:
        cal[m] = P.pav([(x['pm_raw'], 1 if x['over'] else 0) for x in rows if x['season'] == '2025' and x['market'] == m])
    for x in rows:
        x['pm'] = P.apply_cal(cal[x['market']], x['pm_raw']) if x['season'] == '2026' else x['pm_raw']
    return rows, V


def entries_for(rows, strat, k):
    """-> list of (day, hit_all, n_active) for the greedy daily entries of size k."""
    by_day = defaultdict(list)
    for x in rows:
        by_day[x['day']].append(x)
    out = []
    for day, xs in sorted(by_day.items()):
        cand = []
        for x in xs:
            for over in (True, False):
                q = x['pm'] if over else 1 - x['pm']
                m = x['pk'] if over else 1 - x['pk']
                score = {'S1': q, 'S2': q - m, 'S3': m}[strat]
                cand.append((score, x, over))
        cand.sort(key=lambda c: -c[0])
        used_p, used_g, cur, day_p = set(), set(), [], set()
        made = 0
        for score, x, over in cand:
            if made >= PER_DAY:
                break
            if x['aid'] in used_p or x['aid'] in day_p or x['game'] in used_g:
                continue
            cur.append((0, x, over))
            used_p.add(x['aid'])
            used_g.add(x['game'])
            if len(cur) == k:
                out.append((day, cur))
                day_p |= used_p
                used_p, used_g, cur = set(), set(), []
                made += 1
    return out


def grade(entry):
    """Power entry: every pick must hit; a tie never happens here (ties are dropped), so a loss is any miss."""
    return all((x['over'] == over) for _, x, over in entry)


def cell(rows, strat, k):
    es = entries_for(rows, strat, k)
    per_day = defaultdict(list)
    hits = 0
    legs_n = legs_hit = 0
    for day, e in es:
        win = grade(e)
        per_day[day].append(PAY[k] - 1 if win else -1.0)
        hits += win
        for _, x, over in e:
            legs_n += 1
            legs_hit += x['over'] == over
    if not es:
        return None
    dm = [statistics.mean(v) for v in per_day.values()]
    se = statistics.stdev(dm) / math.sqrt(len(dm)) if len(dm) > 1 else 0
    roi = sum(sum(v) for v in per_day.values()) / len(es)
    return {'entries': len(es), 'days': len(dm), 'win': round(hits / len(es), 4), 'roi': round(roi, 4), 'z': round(statistics.mean(dm) / se, 2) if se else 0.0,
            'leg_hit': round(legs_hit / legs_n, 4), 'breakeven_leg': round(PAY[k] ** (-1 / k), 4)}


def shading(V):
    """Points of line shading (stat units) a pick needs over fair for its chance to reach each size's break-even, at a typical mean."""
    typical = {'pts': 20.0, 'reb': 6.0, 'ast': 5.0, '3pm': 2.0, 'pra': 32.0}
    out = {}
    for m, mu in typical.items():
        v0, v1, v2 = V[m][:3]
        sd = math.sqrt(max(0.25, v0 + v1 * mu + v2 * mu * mu))
        row = {'sd': round(sd, 2)}
        for k in SIZES:
            be = PAY[k] ** (-1 / k)
            # P(over L) for a Normal at the fair line is 50%; the line must sit z*sd below the median for chance `be`
            lo, hi = 0.0, 3.0
            for _ in range(40):
                z = (lo + hi) / 2
                if 0.5 * (1 + math.erf(z / math.sqrt(2))) < be:
                    lo = z
                else:
                    hi = z
            row[str(k)] = round(z * sd, 2)
        out[m] = row
    return out


def main():
    rows, V = legs()
    fit = [x for x in rows if x['season'] == '2025']
    test = [x for x in rows if x['season'] == '2026']
    print(f'legs: fit {len(fit):,}  test {len(test):,}', flush=True)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'cells': {}, 'selected': None, 'shading': shading(V), 'payouts': PAY}
    for strat in STRATS:
        for k in SIZES:
            res['cells'][f'{strat}/{k}'] = {'fit': cell(fit, strat, k), 'test': cell(test, strat, k)}
            print(strat, k, res['cells'][f'{strat}/{k}'], flush=True)
    elig = [(c['fit']['roi'], key) for key, c in res['cells'].items() if c['fit'] and c['fit']['entries'] >= MIN_FIT_ENTRIES]
    if elig:
        best = max(elig)[1]
        res['selected'] = best
        t = res['cells'][best]['test']
        v = 'NO-GO'
        if best.startswith('S3'):
            v = 'NO-GO'
        elif t and t['entries'] >= MIN_TEST_ENTRIES and t['days'] >= MIN_TEST_DAYS and t['roi'] > 0:
            days = sorted({d for d, _ in entries_for(test, best.split('/')[0], int(best.split('/')[1]))})
            mid = days[len(days) // 2]
            halves = [cell([x for x in test if (x['day'] < mid) == first], best.split('/')[0], int(best.split('/')[1])) for first in (True, False)]
            both = all(h and h['roi'] > 0 for h in halves)
            res['halves'] = halves
            if both:
                v = 'GO' if t['z'] >= GO_Z else 'WATCH' if t['z'] >= WATCH_Z else 'NO-GO'
        res['verdict'] = v
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    md = ['# Pick\'em entries on independent picks: results', '', f"Run {res['generated']}. Rules: docs/pickem-entries.md (frozen before this ran).", '',
          f"**Selected on 2024-25: {res['selected']}. Verdict: {res.get('verdict')}**", '',
          '| strategy / size | fit entries | fit win | fit ROI | fit leg hit | test entries | test win | test ROI | test z | test leg hit | break-even per leg |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for key, c in res['cells'].items():
        f, t = c['fit'] or {}, c['test'] or {}
        md.append(f"| {key} | {f.get('entries', '')} | {f.get('win', '')} | {f.get('roi', '')} | {f.get('leg_hit', '')} | {t.get('entries', '')} | {t.get('win', '')} | {t.get('roi', '')} | {t.get('z', '')} | {t.get('leg_hit', '')} | {(f or t).get('breakeven_leg', '')} |")
    md += ['', '## Line shading a pick needs (stat units, at a typical mean)', '', '| stat | sd | ' + ' | '.join(f'{k} picks' for k in SIZES) + ' |', '|---|---|' + '---|' * len(SIZES)]
    for m, r in res['shading'].items():
        md.append(f"| {m} | {r['sd']} | " + ' | '.join(str(r[str(k)]) for k in SIZES) + ' |')
    md += ['', 'S1 ranks by the model, S2 by model minus market, S3 by the market alone (baseline). ROI is per entry; the day is the unit for z.', '']
    open(OUT_MD, 'w').write('\n'.join(md))
    print('selected', res['selected'], res.get('verdict'))


if __name__ == '__main__':
    main()
