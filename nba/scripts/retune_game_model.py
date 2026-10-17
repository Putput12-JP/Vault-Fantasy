#!/usr/bin/env python3
"""
Experiment B. Rules were fixed in nba/docs/game-model-experiments.md before this searches.

Widens the four grids that sat on the boundary, and tunes C on the 1pm injury report
when the tune seasons are actually covered. Writes the before/after numbers. Replaces
data/game_model.json only when the pre-registered ship rule passes, and even then does
not touch the paper bot.

  python3 nba/scripts/retune_game_model.py
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_game_model as GM
import backtest_game_vs_kalshi as BK
from backfill_kalshi import TEAM

OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-experiments-results.md')
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'game_model_retune.json')
EDGE_PARAMS = ('K', 'REP', 'ALPHA', 'CT')


def date_coverage(inj, seasons):
    """Share of game dates with a snapshot at or before 1pm ET."""
    have = set()
    if inj is not None:
        for (day, _), reps in inj.snap.items():
            if any(t <= day + 'T13:00' for t in reps):
                have.add(day)
    out = {}
    for s in seasons:
        dates = {g['tip_et'].strftime('%Y-%m-%d') for g in C.games([s])}
        k = sum(1 for d in dates if d in have)
        out[str(s)] = {'dates': len(dates), 'covered': k, 'frac': (k / len(dates) if dates else 0)}
    return out


def game_coverage(inj, seasons):
    have = set()
    if inj is not None:
        for (day, _), reps in inj.snap.items():
            if any(t <= day + 'T13:00' for t in reps):
                have.add(day)
    out = {}
    for s in seasons:
        gs = C.games([s])
        k = sum(1 for g in gs if g['tip_et'].strftime('%Y-%m-%d') in have)
        out[str(s)] = {'games': len(gs), 'covered': k, 'frac': (k / len(gs) if gs else 0)}
    return out


def paired(old, new):
    """old/new: gid -> error (lower is better). t > 0 means new is closer."""
    gids = sorted(set(old) & set(new))
    d = [old[g] - new[g] for g in gids]
    level = {'n': len(d),
             'old': statistics.mean(old[g] for g in gids) if gids else None,
             'new': statistics.mean(new[g] for g in gids) if gids else None}
    if len(d) < 50:
        return dict(level, mean=(statistics.mean(d) if d else None), se=None, t=None, measured=False)
    mu = statistics.mean(d)
    sd = statistics.stdev(d)
    if sd == 0:
        t = 0.0 if abs(mu) < 1e-12 else (1e6 if mu > 0 else -1e6)
        return dict(level, mean=mu, se=0.0, t=t, measured=True)
    se = sd / math.sqrt(len(d))
    return dict(level, mean=mu, se=se, t=mu / se, measured=True)


def abs_err(recs, which, idx, only=None):
    """which is 'am' or 'none'. idx 0 margin, 1 total. only: game ids that have a closing line."""
    out = {}
    for r in recs:
        if which not in r:
            continue
        gid = r['g']['game_id']
        if only is not None and gid not in only:
            continue
        actual = r['actual_margin'] if idx == 0 else r['actual_total']
        out[gid] = abs(r[which][idx] - actual)
    return out


def games_with_close(seasons):
    """Games whose DraftKings (else ESPN BET) close spread parsed. None if the odds file is missing."""
    pref = {'DraftKings': 0, 'ESPN BET': 1}
    ids, missing = set(), False
    for s in seasons:
        path = os.path.join(C.RAW, 'espn_odds', f'games_{s}.jsonl')
        if not os.path.exists(path):
            missing = True
            continue
        for line in open(path):
            g = json.loads(line)
            best = None
            for L in g.get('lines') or []:
                name = L.get('provider') or ''
                if name not in pref or 'Live' in name:
                    continue
                if best is None or pref[name] < pref[best['provider']]:
                    best = L
            if not best:
                continue
            try:
                float(((best.get('home') or {}).get('close') or {}).get('spread'))
            except (TypeError, ValueError):
                continue
            ids.add(int(g['game_id']))
    return None if missing and not ids else ids


def have_kalshi(series):
    return all(os.path.exists(os.path.join(BK.RAW_K, f'{kind}_{series}.jsonl'))
               for kind in ('markets', 'prices_am', 'prices'))


def ladder_brier(series, by_gid, sig_m, sig_t):
    """gid -> mean squared error of that model's 1pm probability. Same filters as the Kalshi backtest."""
    if not have_kalshi(series):
        return None
    mk, am, pre = BK.load(series)
    per = defaultdict(list)
    for t, m in mk.items():
        a, p = am.get(t), pre.get(t)
        r = by_gid.get((a or {}).get('game_id'))
        if not r or m.get('result') not in ('yes', 'no'):
            continue
        k1 = BK.price(a, 'am')
        won = 1 if m['result'] == 'yes' else 0
        g = r['g']
        if series == 'KXNBAGAME':
            if k1 is None or not (0.02 < k1 < 0.98) or BK.price(p, 'pretip') is None:
                continue
            team = TEAM.get(t.rsplit('-', 1)[1], t.rsplit('-', 1)[1])
            if team not in (g['home'], g['away']) or 'am' not in r:
                continue
            margin = r['am'][0] if team == g['home'] else -r['am'][0]
            prob = BK.phi(margin / sig_m)
        else:
            if m.get('floor_strike') is None or k1 is None or BK.price(p, 'pretip') is None or not (0.05 < k1 < 0.95):
                continue
            x = m['floor_strike']
            if series == 'KXNBASPREAD':
                if 'am' not in r:
                    continue
                team = t.rsplit('-', 1)[1].rstrip('0123456789')
                team = TEAM.get(team, team)
                if team not in (g['home'], g['away']):
                    continue
                mu = r['am'][0] if team == g['home'] else -r['am'][0]
                prob = 1 - BK.phi((x - mu) / sig_m)
            else:
                mu = r['am'][1] if 'am' in r else (r['none'][1] if abs(r.get('_ct') or 0) < 1e-12 else None)
                if mu is None:
                    continue
                prob = 1 - BK.phi((x - mu) / sig_t)
        per[g['game_id']].append((prob - won) ** 2)
    return per


def brier_pair(old_per, new_per):
    """Game-paired t, plus the strike-weighted Brier the existing table quotes."""
    old = {g: statistics.mean(v) for g, v in old_per.items()}
    new = {g: statistics.mean(v) for g, v in new_per.items()}
    out = paired(old, new)
    gids = set(old) & set(new)

    def sw(per):
        xs = [e for g in gids for e in per[g]]
        return statistics.mean(xs) if xs else None

    out['old_strike'] = sw(old_per)
    out['new_strike'] = sw(new_per)
    out['strikes'] = sum(len(old_per[g]) for g in gids)
    return out


def decide(cmp, newP):
    """Returns (ship, accuracy_ok, reasons)."""
    reasons, blocks = [], []

    def t_of(name):
        m = cmp.get(name) or {}
        return m.get('t') if m.get('measured') else None

    sp, tot = t_of('spread_mae'), t_of('total_mae')
    if sp is None or tot is None:
        reasons.append('spread MAE or total MAE was not measured')
    else:
        if not (sp >= 2 or tot >= 2):
            reasons.append(f'neither spread nor total improved by 2 SE (t {sp:.2f}, {tot:.2f})')
        if sp <= -2 or tot <= -2:
            reasons.append(f'a margin got worse by 2 SE (spread {sp:.2f}, total {tot:.2f})')
    for name, lab in (('brier_ml', 'moneyline Brier'), ('brier_spread', 'spread-ladder Brier'),
                      ('brier_total', 'total-ladder Brier')):
        t = t_of(name)
        if t is None:
            reasons.append(f'{lab} was not measured')
        elif t <= -2:
            reasons.append(f'{lab} got worse (t {t:.2f})')
    accuracy_ok = not reasons
    edge = [k for k in EDGE_PARAMS if k in GM.on_edge(newP, GM.GRID)]
    if edge:
        blocks.append('still on the widened grid edge: ' + ', '.join(edge))
    if abs(newP.get('CT') or 0) > 1e-12:
        blocks.append('CT is not 0, and the paper bot stops trading NBA totals when CT is not 0')
    return (accuracy_ok and not blocks), accuracy_ok, reasons + blocks


def fmt(x, nd=3):
    if x is None:
        return '—'
    return f'{x:.{nd}f}'


def write_section(res):
    R = res['retune']
    L = ['## Experiment B — widened grids, and C on the injury report', '',
         f"**Verdict: {R['verdict']}.** {R['why']}", '',
         '### The edge check', '',
         f"Shipped parameters on an endpoint of the old grid: {', '.join(R['old_edge']) or 'none'}.",
         f"The four named in the rules are {', '.join(EDGE_PARAMS)}. "
         + ('All four are on that edge.' if set(EDGE_PARAMS) <= set(R['old_edge']) else 'The check does not match the rules; see the list.'),
         '',
         '### Did the tune seasons have a 1pm report?', '',
         'A season counts when 80% of its game dates have a snapshot at or before 1pm. C is retuned on the',
         'report only when both tune seasons count.', '',
         '| Season | Game dates | With a 1pm-or-earlier report | Share |', '|---|---|---|---|']
    for s, d in R['tune_dates'].items():
        L.append(f"| {s} | {d['dates']} | {d['covered']} | {d['frac']:.1%} |")
    L += ['', f"C objective: **{R['c_objective']}.**", '']
    if R.get('test_games'):
        L += ['Test-season games with a 1pm-or-earlier report (spread MAE and the margin Briers need 80%):', '',
              '| Season | Games | Covered | Share |', '|---|---|---|---|']
        for s, d in R['test_games'].items():
            L.append(f"| {s} | {d['games']} | {d['covered']} | {d['frac']:.1%} |")
        L.append('')
    L += ['### Parameters', '',
          '| Param | Shipped | After the widened search | On the new edge? |', '|---|---|---|---|']
    for k in GM.GRID:
        edge = 'yes' if k in R['new_edge'] else ''
        L.append(f"| {k} | {R['old_params'][k]} | {R['new_params'][k]} | {edge} |")
    L += ['', 'Tune-season oracle MAE is the search objective (in sample, not the ship test).', '',
          f"| | Margin | Total |", '|---|---|---|',
          f"| Shipped | {fmt(R['tune_old'][0])} | {fmt(R['tune_old'][1])} |",
          f"| Widened | {fmt(R['tune_new'][0])} | {fmt(R['tune_new'][1])} |", '']
    L += ['### Test seasons: MAE and Kalshi 1pm Brier', '',
          'MAE is points, mean absolute error on the paired games that have a closing spread. Brier is',
          'strike-weighted, the same average the existing Kalshi table uses; t is the paired difference of',
          'each game\'s mean squared error, so a long ladder counts as one game. Positive t means the widened',
          'parameters are closer. "Not measured" fails the ship rule.', '',
          '| Metric | Shipped | Widened | Games | t |', '|---|---|---|---|---|']
    for key, lab in (('spread_mae', 'Spread MAE, 1pm report'), ('total_mae', 'Total MAE'),
                     ('brier_ml', 'Kalshi 1pm Brier, moneyline'),
                     ('brier_spread', 'Kalshi 1pm Brier, spread ladder'),
                     ('brier_total', 'Kalshi 1pm Brier, total ladder')):
        m = R['cmp'].get(key) or {}
        nd = 4 if key.startswith('brier') else 3
        old = m.get('old_strike', m.get('old'))
        new = m.get('new_strike', m.get('new'))
        if not m.get('measured') and old is None:
            L.append(f"| {lab} | not measured | not measured | {m.get('n', 0)} | — |")
        else:
            L.append(f"| {lab} | {fmt(old, nd)} | {fmt(new, nd)} | {m.get('n', 0)} | {fmt(m.get('t'), 2)} |")
    if R.get('unmeasured'):
        L += ['', 'Why a row is missing:']
        for line in R['unmeasured']:
            L.append(f'- {line}')
    L += ['', '### Paper bot', '', R['paper_bot'], '']
    return '\n'.join(L)


def upsert(section):
    if os.path.exists(OUT_MD) and '## Experiment A' in open(OUT_MD).read():
        old = open(OUT_MD).read()
        if '## Experiment B' in old:
            old = old[:old.index('## Experiment B')]
        open(OUT_MD, 'w').write(old.rstrip() + '\n\n' + section + '\n')
    else:
        head = ['# Game-model experiments: results', '',
                f"Retune section generated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}.",
                'Rules: `nba/docs/game-model-experiments.md`.', '']
        open(OUT_MD, 'w').write('\n'.join(head) + '\n' + section + '\n')


def main():
    shipped = json.load(open(GM.OUT_JSON))
    oldP = dict(GM.DEFAULT, **shipped['params'])
    old_edge = GM.on_edge(oldP, GM.OLD_GRID)
    print('old edge', old_edge, flush=True)

    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    idx = C.player_index(box)
    tune_inj = None
    tune_files = [os.path.join(C.RAW, 'injuries', f'reports_{s}.jsonl') for s in GM.TUNE]
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in tune_files):
        tune_inj = C.InjuryAsOf(GM.TUNE, idx)
    test_inj = None
    test_files = [os.path.join(C.RAW, 'injuries', f'reports_{s}.jsonl') for s in GM.TEST]
    if all(os.path.exists(p) and os.path.getsize(p) > 0 for p in test_files):
        test_inj = C.InjuryAsOf(GM.TEST, idx)

    tune_dates = date_coverage(tune_inj, GM.TUNE)
    c_on = tune_inj is not None and all(d['frac'] >= 0.80 for d in tune_dates.values())
    c_objective = '1pm injury report, tune games on a covered date' if c_on else 'who actually sat (reports do not cover both tune seasons)'
    print('C objective:', c_objective, {s: round(d['frac'], 3) for s, d in tune_dates.items()}, flush=True)

    trace = []
    newP, new_tune = GM.tune(box, c_on_report=c_on, inj=tune_inj, start=oldP, trace=trace)
    # Shipped tune MAE, recomputed with this code so the pair matches.
    _, old_recs_tune = GM.run(oldP, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
    old_tune = (GM.mae([r['oracle'][0] - r['actual_margin'] for r in old_recs_tune]),
                GM.mae([r['oracle'][1] - r['actual_total'] for r in old_recs_tune]))

    # Test predictions. Margin at 1pm needs the report. Total needs it only when CT != 0.
    def predict(P, inj):
        _, recs = GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, inj=inj, record_from=GM.TEST[0])
        for r in recs:
            r['_ct'] = P['CT']
        return recs

    old_recs = predict(oldP, test_inj)
    new_recs = predict(newP, test_inj)
    test_games = game_coverage(test_inj, GM.TEST)
    pooled_n = sum(d['games'] for d in test_games.values())
    pooled_k = sum(d['covered'] for d in test_games.values())
    reports_ok = pooled_n and pooled_k / pooled_n >= 0.80 and test_inj is not None

    unmeasured = []
    cmp = {}
    lined = games_with_close(GM.TEST)
    if reports_ok:
        cmp['spread_mae'] = paired(abs_err(old_recs, 'am', 0, lined), abs_err(new_recs, 'am', 0, lined))
    else:
        cmp['spread_mae'] = {'n': pooled_k, 'measured': False, 'old': None, 'new': None, 't': None}
        frac = (pooled_k / pooled_n) if pooled_n else 0
        unmeasured.append(f'Spread MAE: 1pm reports cover {pooled_k} of {pooled_n} test games ({frac:.1%}); need 80%.')

    def total_source(recs, P):
        if abs(P['CT']) < 1e-12:
            return abs_err(recs, 'none', 1, lined)
        if not recs or 'am' not in recs[0]:
            return {}
        return abs_err(recs, 'am', 1, lined)

    if abs(oldP['CT']) < 1e-12 and abs(newP['CT']) < 1e-12:
        cmp['total_mae'] = paired(total_source(old_recs, oldP), total_source(new_recs, newP))
    elif reports_ok:
        cmp['total_mae'] = paired(total_source(old_recs, oldP), total_source(new_recs, newP))
    else:
        cmp['total_mae'] = {'n': 0, 'measured': False, 'old': None, 'new': None, 't': None}
        unmeasured.append('Total MAE: CT is not 0 and the 1pm reports do not cover 80% of test games.')

    sig = lambda tune, i: tune[i] * math.sqrt(math.pi / 2)
    published_tune = shipped['tune_mae']
    # Margin markets need the 1pm margin, which is the report path.
    # The shipped model's sigma is the published tune MAE (what the live bot uses).
    # The candidate's sigma is the tune MAE of the search, which never saw the test seasons.
    for key, series, kind in (('brier_ml', 'KXNBAGAME', 'margin'),
                              ('brier_spread', 'KXNBASPREAD', 'margin'),
                              ('brier_total', 'KXNBATOTAL', 'total')):
        if not have_kalshi(series):
            cmp[key] = {'n': 0, 'measured': False, 'old': None, 'new': None, 't': None}
            unmeasured.append(f'{series}: Kalshi market or 1pm price file is not on disk.')
            continue
        if kind == 'margin' and not reports_ok:
            cmp[key] = {'n': 0, 'measured': False, 'old': None, 'new': None, 't': None}
            unmeasured.append(f'{series}: needs the 1pm margin, and the reports do not cover 80% of test games.')
            continue
        if kind == 'total' and (abs(oldP['CT']) > 1e-12 or abs(newP['CT']) > 1e-12) and not reports_ok:
            cmp[key] = {'n': 0, 'measured': False, 'old': None, 'new': None, 't': None}
            unmeasured.append(f'{series}: CT is not 0 and the reports do not cover the test games.')
            continue

        def view(recs, P, kind=kind):
            out = {}
            for r in recs:
                rr = dict(r)
                if kind == 'total' and abs(P['CT']) < 1e-12:
                    rr['am'] = rr['none']
                out[r['g']['game_id']] = rr
            return out

        old_b = ladder_brier(series, view(old_recs, oldP), sig(published_tune, 0), sig(published_tune, 1))
        new_b = ladder_brier(series, view(new_recs, newP), sig(new_tune, 0), sig(new_tune, 1))
        cmp[key] = brier_pair(old_b, new_b)

    same = all(abs(oldP[k] - newP[k]) < 1e-12 for k in GM.GRID)
    ship, accuracy_ok, reasons = decide(cmp, newP)
    if same:
        ship = False
        reasons = ['the widened search did not move a parameter'] + reasons
    if ship:
        verdict, why = 'SHIP', 'every clause of the ship rule holds; game_model.json is updated'
    elif accuracy_ok and not ship:
        verdict, why = 'NOT SHIPPED', 'accuracy cleared and a block remains: ' + '; '.join(reasons)
    else:
        verdict, why = 'NOT SHIPPED', '; '.join(reasons) if reasons else 'the ship rule failed'

    changed = [k for k in GM.GRID if abs(oldP[k] - newP[k]) > 1e-12]
    if ship:
        paper = ('Shipped. `scripts/paper_bot/signals/nba_total.py` reads `game_model.json` through the daily '
                 'model state: ratings (K, CARRY, REP, ALPHA, KP, B2B, C) and sigma from tune_mae. '
                 f"Parameters that moved: {', '.join(changed) or 'none'}. CT stays 0, so the bot still trades "
                 'and does not need an injury report. The next model-state build will change its projected total '
                 'and its sigma wherever tune_mae moved.')
    elif any(abs(newP[k] - oldP[k]) > 1e-12 for k in GM.GRID):
        ct_note = ''
        if abs(newP['CT']) > 1e-12:
            ct_note = (' The candidate CT is not 0. Shipping it would make `nba_total.py` refuse every NBA total, '
                       'because that bot does not read injury reports. It was not shipped.')
        paper = ('Not shipped, so the bot\'s inputs do not change. Had these parameters shipped, the daily model '
                 f"state would rebuild ratings from {', '.join(changed)} and sigma from the new tune MAE." + ct_note)
    else:
        paper = ('Not shipped and no parameter moved, so `scripts/paper_bot/signals/nba_total.py` keeps the same '
                 'projected total, the same sigma, and CT at 0.')

    if ship:
        apply_ship(newP, new_tune)

    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),
           'retune': {
               'verdict': verdict, 'why': why, 'shipped_file': ship,
               'old_edge': old_edge, 'new_edge': GM.on_edge(newP, GM.GRID),
               'c_objective': c_objective,
               'tune_dates': tune_dates, 'test_games': test_games,
               'old_params': {k: oldP[k] for k in GM.GRID},
               'new_params': {k: newP[k] for k in GM.GRID},
               'tune_old': list(old_tune), 'tune_new': list(new_tune),
               'trace': trace, 'cmp': cmp, 'unmeasured': unmeasured, 'paper_bot': paper,
           }}

    def scrub(o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return None
            return round(o, 6)
        if isinstance(o, dict):
            return {str(k): scrub(v) for k, v in o.items()}
        if isinstance(o, list):
            return [scrub(v) for v in o]
        return o

    res = scrub(res)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    upsert(write_section(res))
    print(open(OUT_MD).read().split('## Experiment B')[-1])
    print('VERDICT', verdict)


def apply_ship(newP, new_tune):
    """Replace the shipped parameters, then rebuild the game-model page from them.
    The Kalshi section is regenerated by the existing backtest so it matches the new fit.
    Only called when the ship rule has already passed."""
    prev = json.load(open(GM.OUT_JSON))
    for k in prev['params']:
        if k in newP:
            prev['params'][k] = newP[k]
    prev['tune_mae'] = [new_tune[0], new_tune[1]]
    prev['retune_shipped'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(prev, open(GM.OUT_JSON, 'w'), indent=1)
    # Rebuild the accuracy page with the frozen params. Keep any experiment pointer out of
    # this file; game-model.md is the model's own page and the backtest appends to it.
    GM.main(['--no-tune'])
    # The backtest appends the Kalshi section for whatever parameters are now shipped.
    # Its closing verdict sentence is still the September wording; the caller checks it
    # against the new table before leaving it in the doc.
    BK.main()


if __name__ == '__main__':
    main()
