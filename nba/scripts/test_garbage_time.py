#!/usr/bin/env python3
"""
Garbage-time capping, scored once. Rules, committed before this ran: docs/garbage-time-prereg.md.
Results: docs/garbage-time-results.md and data/garbage_time_test.json.

  python3 nba/scripts/test_garbage_time.py

Inside the shipped model (data/game_model.json parameters, no retune); only the margin the rating update learns from changes.
  G1  actual margin clipped to +/- C (C chosen on the tune seasons)
  G2  margin at the first 4th-quarter play with lead >= 25 (<= 9:00 left), >= 20 (<= 6:00) or >= 15 (<= 3:00); else final
"""
import csv, datetime as dt, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'garbage_time_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'garbage-time-results.md')
MARGINS = os.path.join(C.HERE, '..', 'data', 'garbage_time_margins.json')
CAPS = (10, 12, 15, 20, 25)
LADDER = ((25, 540), (20, 360), (15, 180))


def garbage_margins():
    """game_id -> margin (home - away) at the garbage-time trigger, for games that reach it in regulation. Cached."""
    if os.path.exists(MARGINS):
        return {int(k): v for k, v in json.load(open(MARGINS)).items()}
    out, ot = {}, set()
    for s in (2024, 2025, 2026):
        f = open(os.path.join(C.RAW, 'hoopr', f'pbp_{s}.csv'), newline='')
        rd = csv.reader(f)
        h = {c: i for i, c in enumerate(next(rd))}
        gi, pi, si, hi, ai = h['game_id'], h['period_number'], h['end_game_seconds_remaining'], h['home_score'], h['away_score']
        best = {}
        for r in rd:
            try:
                gid, p, sec = int(r[gi]), int(float(r[pi])), float(r[si])
                hs, as_ = float(r[hi]), float(r[ai])
            except ValueError:
                continue
            if p > 4:
                ot.add(gid)
                continue
            if p != 4:
                continue
            lead = abs(hs - as_)
            if any(lead >= L and sec <= t for L, t in LADDER):
                if gid not in best or sec > best[gid][0]:
                    best[gid] = (sec, hs - as_)
        for gid, (_, m) in best.items():
            if gid not in ot:
                out[gid] = m
        print('pbp', s, len(best), flush=True)
    out = {g: m for g, m in out.items() if g not in ot}
    json.dump({str(k): v for k, v in out.items()}, open(MARGINS, 'w'))
    return out


class GModel(GM.Model):
    def update(self, g, rows):
        oracle = super().update(g, rows)
        P = self.P
        actual = g['hs'] - g['as']
        adj = actual
        if P.get('CAP'):
            adj = max(-P['CAP'], min(P['CAP'], actual))
        elif P.get('G2'):
            adj = P['G2'].get(g['game_id'], actual)
        d = P['K'] * (adj - actual)
        self.R[g['home']] += d
        self.R[g['away']] -= d
        return oracle


def split_mae(base, var, ids):
    return SS.boot(base, var, 0, 'tip', lambda k: k in ids)


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    gm = garbage_margins()
    GM.Model = GModel
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'params': P0, 'tune': {}, 'g2_games': len(gm)}

    for cap in (None,) + CAPS:
        _, recs = GM.run(dict(P0, CAP=cap), GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
        m = statistics.mean(abs(r['oracle'][0] - r['actual_margin']) for r in recs)
        res['tune'][str(cap)] = round(m, 4)
        print(f'tune cap={cap}: margin MAE {m:.4f}', flush=True)
    cap = min(CAPS, key=lambda c: res['tune'][str(c)])
    res['cap'] = cap
    print('chosen cap', cap, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])[1]
    cur = run(dict(P0))
    var = {'G1': run(dict(P0, CAP=cap)), 'G2': run(dict(P0, G2=gm))}
    big = sorted(abs(r['actual_margin']) for r in cur)
    cut = big[int(len(big) * 0.9)]
    blow = {r['g']['game_id'] for r in cur if abs(r['actual_margin']) >= cut}
    rest = {r['g']['game_id'] for r in cur} - blow
    res['blowout_cut'] = cut
    res['scores'] = {}
    for name, recs in var.items():
        blk = {'whole': {'pooled': SS.boot(cur, recs, 0, 'tip', lambda k: True)}}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk['whole'][str(s)] = SS.boot(cur, recs, 0, 'tip', lambda k, sid=sid: k in sid)
        blk['blowout_decile'] = split_mae(cur, recs, blow)
        blk['rest'] = split_mae(cur, recs, rest)
        withl = [r for r in recs if (r.get('line') or {}).get('spread_close') is not None]
        withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
        blk['info_variant'] = GM.info_test(withl, 'tip', 'spread_close', 0)
        blk['info_shipped'] = GM.info_test(withc, 'tip', 'spread_close', 0)
        blk['close_mae'] = {'variant': mae_close(recs), 'shipped': mae_close(cur)}
        res['scores'][name] = blk
        print(name, json.dumps({k: blk[k] for k in ('whole', 'blowout_decile', 'rest')}), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)


def mae_close(recs):
    d = [(abs(r['tip'][0] - r['actual_margin']), abs(-r['line']['spread_close'] - r['actual_margin']))
         for r in recs if (r.get('line') or {}).get('spread_close') is not None]
    return {'model': round(statistics.mean(a for a, _ in d), 3), 'close': round(statistics.mean(b for _, b in d), 3), 'n': len(d)}


def write_md(res):
    L = ['# Game model: garbage-time capping, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_garbage_time.py`. Rules, committed before this ran: [garbage-time-prereg.md](garbage-time-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters, no retune.', '',
         f"G1 cap chosen on the tune seasons: {res['cap']} points. Tune margin MAE by cap: " + ', '.join(f'{k}: {v}' for k, v in res['tune'].items()) + '.',
         f"G2: {res['g2_games']} games reach the garbage-time state in the play-by-play (2023-24 to 2025-26).", '']
    for name, blk in res['scores'].items():
        L += [f'## {name} (margin MAE, points)', '', '| Window | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|']
        for lab, b in (('2025', blk['whole']['2025']), ('2026', blk['whole']['2026']), ('pooled', blk['whole']['pooled']),
                       (f"exploratory: |margin| >= {res['blowout_cut']:.0f}", blk['blowout_decile']), ('exploratory: the rest', blk['rest'])):
            L.append(f"| {lab} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
