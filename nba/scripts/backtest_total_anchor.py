#!/usr/bin/env python3
"""
Experiment A. Rules were fixed in nba/docs/game-model-experiments.md before this scores anything.

Price each Kalshi total strike from the sportsbook opening total plus a normal residual,
and bet only where that probability disagrees with the Kalshi 1pm price. Compare with the
shipped game model and with a price-only recalibration fit on the earlier half.

  python3 nba/scripts/backtest_total_anchor.py
Writes nba/docs/game-model-experiments-results.md (the anchor section) and
nba/data/total_anchor.json. Does not touch game_model.json or the paper bot.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_game_model as GM
import backtest_game_vs_kalshi as BK

OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model-experiments-results.md')
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'total_anchor.json')
PREF = {'DraftKings': 0, 'ESPN BET': 1}
THS = (0.04, 0.08, 0.12)


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def expit(z):
    z = max(-30, min(30, z))
    return 1 / (1 + math.exp(-z))


def opening_totals(seasons):
    """game_id -> {total, book}. DraftKings, else ESPN BET. Open only, sanity-bounded."""
    out = {}
    for s in seasons:
        path = os.path.join(C.RAW, 'espn_odds', f'games_{s}.jsonl')
        if not os.path.exists(path):
            continue
        for line in open(path):
            g = json.loads(line)
            best = None
            for L in g.get('lines') or []:
                name = L.get('provider') or ''
                if name not in PREF or 'Live' in name:
                    continue
                if best is None or PREF[name] < PREF[best['provider']]:
                    best = L
            if not best:
                continue
            raw = ((best.get('total') or {}).get('open') or {}).get('total')
            try:
                tot = float(raw)
            except (TypeError, ValueError):
                continue
            if not (150 <= tot <= 320):
                continue
            out[int(g['game_id'])] = {'total': tot, 'book': best['provider'], 'season': s}
    return out


def fit_sigma(opens):
    """Tune-season residual width. A season with under 80% opens is dropped. Never the test set."""
    by = defaultdict(list)
    seen = defaultdict(int)
    for g in C.games(GM.TUNE):
        seen[g['season']] += 1
        op = opens.get(g['game_id'])
        if not op:
            continue
        by[g['season']].append((g['hs'] + g['as']) - op['total'])
    used, detail = [], {}
    for s, n in sorted(seen.items()):
        k = len(by[s])
        detail[str(s)] = {'games': n, 'with_open': k, 'frac': round(k / n, 3) if n else 0}
        if n and k / n >= 0.80:
            used.append(s)
    errs = [e for s in used for e in by[s]]
    published = json.load(open(GM.OUT_JSON))['tune_mae'][1] * math.sqrt(math.pi / 2)
    if len(errs) < 500:
        return published, 'shipped tune_mae[1] * sqrt(pi/2)', detail, None
    mae = statistics.mean(abs(e) for e in errs)
    bias = statistics.mean(errs)
    return mae * math.sqrt(math.pi / 2), 'tune opening-total MAE * sqrt(pi/2), seasons ' + ','.join(str(s) for s in used), detail, {
        'n': len(errs), 'mae': mae, 'bias': bias, 'seasons': used}


def total_rows(by_gid, sig_model):
    """One row per Kalshi total strike, same filters as ladder_test."""
    mk, am, pre = BK.load('KXNBATOTAL')
    rows = []
    for t, m in mk.items():
        a, p = am.get(t), pre.get(t)
        r = by_gid.get((a or {}).get('game_id'))
        if not r or m['result'] not in ('yes', 'no') or m.get('floor_strike') is None:
            continue
        k1, k2 = BK.price(a, 'am'), BK.price(p, 'pretip')
        if k1 is None or k2 is None or not (0.05 < k1 < 0.95):
            continue
        g, x = r['g'], m['floor_strike']
        rows.append({'gid': g['game_id'], 'tip': g['tip'], 'season': g['season'],
                     'strike': x, 'model': 1 - BK.phi((x - r['am'][1]) / sig_model),
                     'mu': r['am'][1], 'k_am': k1, 'k_pre': k2,
                     'won': 1 if m['result'] == 'yes' else 0})
    rows.sort(key=lambda r: (r['tip'], r['gid'], r['strike']))
    return rows


def brier(rows, key):
    return statistics.mean((r[key] - r['won']) ** 2 for r in rows) if rows else None


def pick(rows, key, th):
    """(row, bet_yes) where |fair - price| >= th."""
    out = []
    for r in rows:
        e = r[key] - r['k_am']
        if abs(e) >= th:
            out.append((r, e > 0))
    return out


def money(sel):
    """One-contract ROI, profit per contract, equal-stake ROI, game-clustered z."""
    if not sel:
        return {'n': 0, 'games': 0, 'roi': None, 'profit_per_contract': None,
                'equal_stake_roi': None, 'roi_per_game': None, 'z': None}
    cost = ret = 0.0
    rets = []
    per = defaultdict(list)
    for r, yes in sel:
        px = r['k_am'] if yes else 1 - r['k_am']
        c = px + BK.fee(px)
        win = r['won'] if yes else 1 - r['won']
        profit = (1 - c) if win else -c
        cost += c
        ret += win
        rets.append(profit / c)
        per[r['gid']].append(profit / c)
    gm = [statistics.mean(v) for v in per.values()]
    z = None
    if len(gm) >= 2 and statistics.stdev(gm) > 0:
        z = statistics.mean(gm) / (statistics.stdev(gm) / math.sqrt(len(gm)))
    return {'n': len(sel), 'games': len(gm),
            'roi': (ret - cost) / cost if cost else None,
            'profit_per_contract': (ret - cost) / len(sel),
            'equal_stake_roi': statistics.mean(rets),
            'roi_per_game': statistics.mean(gm) if gm else None,
            'z': z}


def fit_price(rows):
    """y ~ a + w logit(price), Newton. Returns (a, w)."""
    b = [0.0, 1.0]
    for _ in range(25):
        g = [0.0, 0.0]
        H = [[1e-6, 0.0], [0.0, 1e-6]]
        for r in rows:
            x = [1.0, logit(r['k_am'])]
            p = expit(b[0] * x[0] + b[1] * x[1])
            for i in range(2):
                g[i] += (r['won'] - p) * x[i]
                for j in range(2):
                    H[i][j] += p * (1 - p) * x[i] * x[j]
        det = H[0][0] * H[1][1] - H[0][1] * H[1][0]
        step = [(H[1][1] * g[0] - H[0][1] * g[1]) / det, (H[0][0] * g[1] - H[1][0] * g[0]) / det]
        b = [b[0] + step[0], b[1] + step[1]]
        if max(abs(s) for s in step) < 1e-8:
            break
    return b


def apply_price(rows, coef):
    out = []
    a, w = coef
    for r in rows:
        q = dict(r)
        q['price_only'] = expit(a + w * logit(r['k_am']))
        out.append(q)
    return out


def fmt_pct(x):
    return '—' if x is None else f'{x * 100:+.1f}%'


def fmt_z(x):
    return '—' if x is None else f'{x:.2f}'


def cell(m):
    if not m or not m.get('n'):
        return '—'
    return f"{m['n']}, {m['games']}g, {fmt_pct(m['roi'])}, z {fmt_z(m['z'])}"


def judge(full, h1, h2, price_h2, model_h2, yes_h2, no_h2):
    def roi(m):
        return None if not m or not m.get('n') else m['roi']
    if roi(full) is None or roi(full) <= 0 or roi(h1) is None or roi(h1) <= 0 or roi(h2) is None or roi(h2) <= 0:
        why = 'full-sample ROI is not positive' if (roi(full) is None or roi(full) <= 0) else 'a time half is not positive'
        return 'NO-GO', why
    notes = []
    if h2['games'] < 50 or (h2.get('z') or -9) < 2:
        notes.append(f"second half is {h2['games']} games at z {fmt_z(h2.get('z'))}, needs 50+ and z >= 2")
    if price_h2 and price_h2.get('n', 0) >= 20:
        if roi(h2) <= roi(price_h2):
            notes.append(f"second half {fmt_pct(roi(h2))} does not beat price-only {fmt_pct(roi(price_h2))}")
    if model_h2 and roi(model_h2) is not None and roi(h2) < roi(model_h2):
        notes.append(f"second half {fmt_pct(roi(h2))} trails the model {fmt_pct(roi(model_h2))}")
    for lab, side in (('YES', yes_h2), ('NO', no_h2)):
        if side and side.get('n', 0) >= 20 and (roi(side) or 0) < 0:
            notes.append(f"second-half {lab} ROI is {fmt_pct(roi(side))}")
    if notes:
        return 'WATCH', '; '.join(notes)
    return 'GO', '8% bucket clears the pre-registered bar'


def implied_total(rows):
    """Strike where the 1pm price crosses 50%, interpolated. None if the ladder never crosses."""
    rows = sorted(rows, key=lambda r: r['strike'])
    for a, b in zip(rows, rows[1:]):
        if (a['k_am'] - 0.5) * (b['k_am'] - 0.5) <= 0 and a['k_am'] != b['k_am']:
            w = (a['k_am'] - 0.5) / (a['k_am'] - b['k_am'])
            return a['strike'] + w * (b['strike'] - a['strike'])
    return None


def bucket_block(rows, key):
    out = {}
    for th in THS:
        out[f'{th:.2f}'] = money(pick(rows, key, th))
    return out


def half_block(rows, key, th=0.08):
    """Full, first half, second half, plus YES/NO on the second half. Halves split the rows as given."""
    half = len(rows) // 2
    h1, h2 = rows[:half], rows[half:]
    sel = pick(h2, key, th)
    return {
        'full': money(pick(rows, key, th)),
        'h1': money(pick(h1, key, th)),
        'h2': money(sel),
        'yes_h2': money([x for x in sel if x[1]]),
        'no_h2': money([x for x in sel if not x[1]]),
        'h1_rows': h1, 'h2_rows': h2,
    }


def write_md(res):
    A = res['anchor']
    L = ['# Game-model experiments: results', '',
         f"Generated {res['generated']} by `nba/scripts/backtest_total_anchor.py` and, when present, `retune_game_model.py`.",
         'Rules, committed before either run: `nba/docs/game-model-experiments.md`.', '',
         '## Experiment A — sportsbook opening total as the Kalshi ladder anchor', '',
         f"**Verdict: {A['verdict']}.** {A['why']}", '',
         'The anchor is the DraftKings opening total, else ESPN BET. The close is not used. Pinnacle\'s tape on',
         '`nba-data` starts 2026-09-30 and covers none of these seasons. The distribution is a normal centered on',
         f"that open, sigma {A['sigma']:.2f} ({A['sigma_from']}).", '']
    if A.get('sigma_fit'):
        f = A['sigma_fit']
        L.append(f"Sigma sample: {f['n']} tune games, residual MAE {f['mae']:.3f}, mean actual−open {f['bias']:+.3f} (not used to shift the center).")
    L += ['', 'Opening-total coverage by season (a tune season under 80% is dropped from sigma):', '',
          '| Season | Games | With an open total | Share |', '|---|---|---|---|']
    for s, d in A['coverage'].items():
        L.append(f"| {s} | {d['games']} | {d['with_open']} | {d['frac']:.1%} |")
    L += ['', f"Common set: {A['n_common']:,} strikes in {A['games_common']:,} games that have both a 1pm Kalshi price and an opening total.",
          f"All Kalshi total strikes passing the usual filters, including games with no open: {A['n_all']:,} in {A['games_all']:,} games.",
          '', '### Brier (lower is better)', '',
          '| Set | Strikes | Anchor | Shipped model | Kalshi 1pm | Price-only (2nd half, fit on the 1st) |',
          '|---|---|---|---|---|---|']
    for lab in ('all', 'common', 'common 1st half', 'common 2nd half'):
        b = A['brier'][lab]
        po = f"{b['price_only']:.4f}" if b.get('price_only') is not None else '—'
        anc = f"{b['anchor']:.4f}" if b.get('anchor') is not None else '—'
        L.append(f"| {lab} | {b['n']} | {anc} | {b['model']:.4f} | {b['kalshi']:.4f} | {po} |")
    L += ['', '### ROI after fees, one contract per strike', '',
          'ROI is profit / dollars risked. z is game-clustered. The decision uses the 8% row only.', '',
          '| Edge | Anchor: strikes, games, ROI, z | Model | Price-only (2nd half only) |',
          '|---|---|---|---|']
    for th in THS:
        k = f'{th:.2f}'
        po = A['price_only_buckets'].get(k)
        L.append(f"| {th:.0%}+ | {cell(A['buckets']['anchor'][k])} | {cell(A['buckets']['model'][k])} | {cell(po)} |")
    L += ['', 'Profit per contract and equal-dollar-stake ROI are not the decision. They are here so the two',
          'conventions in the repo can both be read off the 8% bucket.', '',
          '| 8%+ | Profit per contract | Equal-stake ROI | One-contract ROI |', '|---|---|---|---|']
    for lab, m in (('Anchor, all', A['halves']['anchor']['full']),
                   ('Anchor, 1st half', A['halves']['anchor']['h1']),
                   ('Anchor, 2nd half', A['halves']['anchor']['h2']),
                   ('Model, all', A['halves']['model']['full']),
                   ('Model, 2nd half', A['halves']['model']['h2']),
                   ('Price-only, 2nd half', A['halves']['price_only']['h2'])):
        if not m or not m.get('n'):
            L.append(f"| {lab} | — | — | — |")
        else:
            L.append(f"| {lab} | {m['profit_per_contract']:+.4f} | {fmt_pct(m['equal_stake_roi'])} | {fmt_pct(m['roi'])} |")
    L += ['', '### Both halves at 8%, and the two sides', '',
          '| Slice | Anchor | Model |', '|---|---|---|',
          f"| 1st half | {cell(A['halves']['anchor']['h1'])} | {cell(A['halves']['model']['h1'])} |",
          f"| 2nd half | {cell(A['halves']['anchor']['h2'])} | {cell(A['halves']['model']['h2'])} |",
          f"| 2nd half YES | {cell(A['halves']['anchor']['yes_h2'])} | {cell(A['halves']['model']['yes_h2'])} |",
          f"| 2nd half NO | {cell(A['halves']['anchor']['no_h2'])} | {cell(A['halves']['model']['no_h2'])} |",
          '', f"Price-only coefficient fit on the first half: a = {A['price_coef'][0]:.3f}, w = {A['price_coef'][1]:.3f}.",
          '']
    d = A['drift']
    if d.get('mean') is None:
        L += ['Drift: no 1pm ladder crossed 50%, so there is no implied total to compare.', '']
    else:
        L += ['Drift, descriptive only: on games where the 1pm ladder crosses 50%, the interpolated strike minus the',
              f"opening total averages {d['mean']:+.2f} points (MAE {d['mae']:.2f}, {d['n']} games).", '']
    L += [
          '', 'The shipped model on every Kalshi total strike, not just games with an opening total, is the',
          'reproduction of the ladder already in `game-model.md`. It is a check that this run sees the same',
          'tape, not a second verdict.', '',
          '| | This run | Written 2026-09-30 |', '|---|---|---|',
          f"| Strikes / games | {A['published_check']['n']} / {A['published_check']['games']} | 11447 / 1301 |",
          f"| Brier model / 1pm / pre-tip | {A['published_check']['brier_model']:.4f} / {A['published_check']['brier_kalshi']:.4f} / {A['published_check']['brier_pre']:.4f} | 0.2188 / 0.2150 / 0.2108 |",
          f"| 8%+ strikes, games, ROI | {A['published_check']['n8']}, {A['published_check']['g8']}, {fmt_pct(A['published_check']['roi8'])} | 3987, 817, +1.9% |",
          '',
          'The September half table is a different column. Its +19.3% and +8.1% are ROI per game (each game\'s mean',
          'return on stake, then the mean across games), which is the mean inside the z above, not profit divided by',
          'dollars. On this tape the model\'s ROI per game at 8% is '
          f"{fmt_pct(A['halves']['model']['h1'].get('roi_per_game'))} then {fmt_pct(A['halves']['model']['h2'].get('roi_per_game'))}, "
          f"z {fmt_z(A['halves']['model']['h1'].get('z'))} then {fmt_z(A['halves']['model']['h2'].get('z'))}. "
          'The decision uses the one-contract ROI, the column that was about +2%.',
          '']
    gap = A.get('price_only_max_gap')
    if gap is not None:
        L += [f"Price-only's largest gap versus the 1pm price on the second half is {gap:.3f}. "
              'Where that is under 0.08, the 8% and 12% price-only rows are empty and the GO test treats that baseline as ROI 0.',
              '']
    return '\n'.join(L)


def main():
    opens = opening_totals(GM.TUNE + GM.TEST)
    sigma, sigma_from, cov, fit = fit_sigma(opens)
    # coverage of the test seasons too, for the table
    seen = defaultdict(int)
    got = defaultdict(int)
    for g in C.games(GM.TUNE + GM.TEST):
        seen[g['season']] += 1
        if g['game_id'] in opens:
            got[g['season']] += 1
    coverage = {str(s): {'games': seen[s], 'with_open': got[s],
                         'frac': round(got[s] / seen[s], 3) if seen[s] else 0} for s in sorted(seen)}

    shipped = json.load(open(GM.OUT_JSON))
    P = dict(GM.DEFAULT, **shipped['params'])
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    # CT is 0 in the shipped file, so the total does not use the injury report. Pass reports
    # when they exist so a non-zero CT would still be scored honestly; with CT 0 the total matches.
    inj = None
    if any(os.path.exists(os.path.join(C.RAW, 'injuries', f'reports_{s}.jsonl')) for s in GM.TEST):
        inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    _, recs = GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, inj=inj, record_from=GM.TEST[0])
    by_gid = {}
    for r in recs:
        if 'am' not in r and 'none' in r:
            r['am'] = r['none']
        by_gid[r['g']['game_id']] = r
    sig_model = shipped['tune_mae'][1] * math.sqrt(math.pi / 2)
    rows = total_rows(by_gid, sig_model)
    if not rows:
        raise SystemExit('No Kalshi total strikes. prices_am_KXNBATOTAL.jsonl or prices_KXNBATOTAL.jsonl is missing or empty.')
    for r in rows:
        op = opens.get(r['gid'])
        r['open'] = op['total'] if op else None
        r['anchor'] = (1 - BK.phi((r['strike'] - op['total']) / sigma)) if op else None
    common = [r for r in rows if r['anchor'] is not None]
    if len(common) < 200:
        raise SystemExit(f'only {len(common)} total strikes have an opening total; not scoring a verdict on that')
    half = len(common) // 2
    coef = fit_price(common[:half])
    priced = apply_price(common, coef)

    def brier_pack(rs, with_anchor=True, with_price=False):
        pack = {'n': len(rs), 'model': brier(rs, 'model'), 'kalshi': brier(rs, 'k_am')}
        if with_anchor and rs and rs[0].get('anchor') is not None:
            pack['anchor'] = brier(rs, 'anchor')
        if with_price:
            pack['price_only'] = brier(rs, 'price_only')
        return pack

    hA = half_block(common, 'anchor')
    hM = half_block(common, 'model')
    hP = half_block(priced, 'price_only')
    price_gap = max((abs(r['price_only'] - r['k_am']) for r in priced[half:]), default=None)
    verdict, why = judge(hA['full'], hA['h1'], hA['h2'], hP['h2'], hM['h2'], hA['yes_h2'], hA['no_h2'])

    # drift
    by_game = defaultdict(list)
    for r in common:
        by_game[r['gid']].append(r)
    gaps = []
    for gid, rs in by_game.items():
        imp = implied_total(rs)
        if imp is not None:
            gaps.append(imp - rs[0]['open'])
    drift = {'n': len(gaps),
             'mean': statistics.mean(gaps) if gaps else None,
             'mae': statistics.mean(abs(g) for g in gaps) if gaps else None}

    m8 = money(pick(rows, 'model', 0.08))
    anchor = {
        'verdict': verdict, 'why': why, 'sigma': sigma, 'sigma_from': sigma_from,
        'sigma_fit': ({k: (round(v, 4) if isinstance(v, float) else v) for k, v in fit.items()} if fit else None),
        'coverage': coverage,
        'n_common': len(common), 'games_common': len({r['gid'] for r in common}),
        'n_all': len(rows), 'games_all': len({r['gid'] for r in rows}),
        'brier': {
            'all': brier_pack(rows, with_anchor=False),
            'common': brier_pack(common),
            'common 1st half': brier_pack(priced[:half]),
            'common 2nd half': brier_pack(priced[half:], with_price=True),
        },
        'buckets': {'anchor': bucket_block(common, 'anchor'), 'model': bucket_block(common, 'model')},
        'price_only_buckets': bucket_block(priced[half:], 'price_only'),
        'halves': {'anchor': {k: v for k, v in hA.items() if k not in ('h1_rows', 'h2_rows')},
                   'model': {k: v for k, v in hM.items() if k not in ('h1_rows', 'h2_rows')},
                   'price_only': {k: v for k, v in hP.items() if k not in ('h1_rows', 'h2_rows')}},
        'price_coef': coef,
        'price_only_max_gap': price_gap,
        'drift': drift,
        'published_check': {
            'n': len(rows), 'games': len({r['gid'] for r in rows}),
            'brier_model': brier(rows, 'model'), 'brier_kalshi': brier(rows, 'k_am'),
            'brier_pre': brier(rows, 'k_pre'),
            'n8': m8['n'], 'g8': m8['games'], 'roi8': m8['roi'],
        },
    }
    # json-friendly
    def scrub(o):
        if isinstance(o, float):
            return None if math.isnan(o) else round(o, 6)
        if isinstance(o, dict):
            return {k: scrub(v) for k, v in o.items()}
        if isinstance(o, list):
            return [scrub(v) for v in o]
        return o
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'anchor': scrub(anchor)}
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    text = write_md(res)
    # Keep a retune section if one was already appended.
    if os.path.exists(OUT_MD) and '## Experiment B' in open(OUT_MD).read():
        old = open(OUT_MD).read()
        tail = old[old.index('## Experiment B'):]
        text = text + '\n' + tail
    open(OUT_MD, 'w').write(text + '\n')
    print(text)
    print('VERDICT', verdict)


if __name__ == '__main__':
    main()
