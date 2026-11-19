#!/usr/bin/env python3
"""
Stint RAPM, with and without garbage time, scored once. Rules, committed before this ran: docs/rapm-prereg.md.
Results: docs/rapm-results.md and data/rapm_test.json.

  python3 nba/scripts/test_rapm.py

Stints are rebuilt from the ESPN play-by-play on disk (raw/hoopr/pbp_2024..2026.csv); pure stdlib. Inside the shipped model
(data/game_model.json parameters, no retune). Nothing here writes game_model.json.
"""
import csv, datetime as dt, json, os, pickle, random, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM
import build_season_start_test as SS

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'rapm_test.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'rapm-results.md')
CACHE = os.path.join(C.RAW, 'stints_espn.pkl')
PBP_SEASONS = (2024, 2025, 2026)
LADDER = ((25, 540), (20, 360), (15, 180))
POSS_PER_SEC = 99.0 / 2880.0
DECAY, REFIT_DAYS, MIN_POSS = 0.5, 28, 300.0
LAMS, CS, LAMBDAS_B = (3000.0, 10000.0), (0.5, 0.75, 1.0), (0.5, 1.0, 2.0)


# ── stints from play-by-play ───────────────────────────────────────────────
def build_stints(box):
    """game_id -> list of (home5, away5, secs, home_pts, away_pts, late). Also validity stats."""
    games = {g['game_id']: g for g in C.games(PBP_SEASONS)}
    starters, team_of = {}, {}
    for gid, rows in box.items():
        if gid not in games:
            continue
        st = defaultdict(set)
        for r in rows:
            team_of[(gid, r['athlete_id'])] = r['team']
            if r['starter'] and r['played']:
                st[r['team']].add(r['athlete_id'])
        starters[gid] = st
    out, stats = {}, {'games': 0, 'kept': 0, 'bad_sub': 0, 'no_starters': 0}
    for s in PBP_SEASONS:
        f = open(os.path.join(C.RAW, 'hoopr', f'pbp_{s}.csv'), newline='')
        rd = csv.reader(f)
        h = {c: i for i, c in enumerate(next(rd))}
        ix = {k: h[k] for k in ('game_id', 'game_play_number', 'period_number', 'end_game_seconds_remaining', 'home_score',
                                'away_score', 'type_text', 'athlete_id_1', 'athlete_id_2')}
        global _IX
        _IX = ix
        cur_id, plays = None, []

        def flush():
            if cur_id is None or cur_id not in games:
                return
            stats['games'] += 1
            res = process_game(games[cur_id], plays, starters.get(cur_id), team_of, stats)
            if res is not None:
                out[cur_id] = res
                stats['kept'] += 1
        for r in rd:
            gid = int(r[ix['game_id']]) if r[ix['game_id']].isdigit() else r[ix['game_id']]
            if gid != cur_id:
                flush()
                cur_id, plays = gid, []
            plays.append(r)
        flush()
    return out, stats


def process_game(g, plays, st, team_of, stats):
    ix = _IX
    gid = g['game_id']
    if not st or len(st.get(g['home'], ())) != 5 or len(st.get(g['away'], ())) != 5:
        stats['no_starters'] += 1
        return None
    cur = {g['home']: set(st[g['home']]), g['away']: set(st[g['away']])}
    rows = []
    for r in plays:
        try:
            rows.append((int(r[ix['game_play_number']]), int(float(r[ix['period_number']])), float(r[ix['end_game_seconds_remaining']]),
                         float(r[ix['home_score']]), float(r[ix['away_score']]), r[ix['type_text']], r[ix['athlete_id_1']], r[ix['athlete_id_2']]))
        except ValueError:
            continue
    rows.sort(key=lambda x: x[0])
    stints, t0, s0, trig, ot = [], 0.0, (0.0, 0.0), False, False
    last = (0.0, 0.0)

    def close(el, hs, as_):
        nonlocal t0, s0
        secs = el - t0
        if secs > 0:
            stints.append((tuple(sorted(cur[g['home']])), tuple(sorted(cur[g['away']])), secs, hs - s0[0], as_ - s0[1], trig))
            t0, s0 = el, (hs, as_)
    for gp, p, secrem, hs, as_, typ, a1, a2 in rows:
        if p > 4:
            ot = True
            continue
        el = max(t0, 2880.0 - secrem)
        last = (hs, as_)
        if not trig and p == 4 and any(abs(hs - as_) >= L and secrem <= t for L, t in LADDER):
            close(el, hs, as_)
            trig = True
        if typ == 'Substitution':
            try:
                pin, pout = int(a1), int(a2)
            except ValueError:
                stats['bad_sub'] += 1
                return None
            tm = team_of.get((gid, pin))
            if tm not in cur or pout not in cur[tm] or pin in cur[tm]:
                stats['bad_sub'] += 1
                return None
            close(el, hs, as_)
            cur[tm].remove(pout)
            cur[tm].add(pin)
    close(2880.0, last[0], last[1])
    if ot:
        stints = [(a, b, c, d, e, False) for a, b, c, d, e, _ in stints]
    return stints


# ── ridge RAPM by conjugate gradient on the normal equations ───────────────
class Accum:
    def __init__(self):
        self.XtX = defaultdict(lambda: defaultdict(float))
        self.Xty = defaultdict(float)
        self.poss = defaultdict(float)

    def add(self, stints, filt):
        for home, away, secs, hp, ap, late in stints:
            if filt == 'G' and late:
                continue
            w = secs * POSS_PER_SEC
            if w < 0.5:
                continue
            y = 100.0 * (hp - ap) / w
            ids = [(a, 1.0) for a in home] + [(a, -1.0) for a in away] + [(0, 1.0)]
            for a, xa in ids:
                self.Xty[a] += w * xa * y
                row = self.XtX[a]
                for b, xb in ids:
                    row[b] += w * xa * xb
                if a != 0:
                    self.poss[a] += w

    def decay(self, f):
        for row in self.XtX.values():
            for k in row:
                row[k] *= f
        for k in self.Xty:
            self.Xty[k] *= f
        for k in self.poss:
            self.poss[k] *= f

    def solve(self, lam, x0):
        ids = [a for a in self.XtX]
        idx = {a: i for i, a in enumerate(ids)}
        n = len(ids)
        rows = [[(idx[b], v) for b, v in self.XtX[a].items()] for a in ids]
        pen = [0.0 if a == 0 else lam for a in ids]
        b = [self.Xty[a] for a in ids]
        x = [x0.get(a, 0.0) for a in ids]

        def mv(v):
            return [sum(val * v[j] for j, val in rows[i]) + pen[i] * v[i] for i in range(n)]
        r = [bi - ai for bi, ai in zip(b, mv(x))]
        pv = r[:]
        rs = sum(t * t for t in r)
        b2 = sum(t * t for t in b) or 1.0
        for _ in range(250):
            if rs < 1e-10 * b2:
                break
            Ap = mv(pv)
            al = rs / sum(u * v for u, v in zip(pv, Ap))
            x = [xi + al * u for xi, u in zip(x, pv)]
            r = [ri - al * u for ri, u in zip(r, Ap)]
            rn = sum(t * t for t in r)
            pv = [ri + (rn / rs) * u for ri, u in zip(r, pv)]
            rs = rn
        return {a: x[i] for i, a in enumerate(ids)}


def snapshots(stints, filt, lam, games):
    """gid -> {aid: (coef, possessions)}: the fit made right after that game, from games up to and including it."""
    acc, out, last_fit, season, coef, fresh = Accum(), {}, None, None, {}, False
    for g in games:
        if g['season'] != season:
            if season is not None:
                acc.decay(DECAY)
            season, last_fit = g['season'], None
        st = stints.get(g['game_id'])
        if st is None:
            continue
        acc.add(st, filt)
        fresh = True
        if fresh and (last_fit is None or (g['tip'] - last_fit).days >= REFIT_DAYS):
            coef = acc.solve(lam, coef)
            out[g['game_id']] = {a: (coef[a], acc.poss[a]) for a in coef if a != 0}
            last_fit, fresh = g['tip'], False
    return out


# ── the model ──────────────────────────────────────────────────────────────
class RapmModel(GM.Model):
    SNAPS = {}

    def __init__(self, P):
        super().__init__(P)
        self.cur = {}

    def rapm_value(self, p):
        e = self.cur.get(p.get('aid'))
        if not e or e[1] < MIN_POSS:
            return None
        return max(0.0, e[0]) * 0.99 * p['mpg'] / 48.0

    def value(self, p):
        mode = self.P.get('RAPM')
        base = super().value(p)
        if not mode:
            return base
        v = self.rapm_value(p)
        if mode == 'O':
            return base if v is None else v
        return base + self.P['LAM'] * (v or 0.0)

    def update(self, g, rows):
        oracle = super().update(g, rows)
        if self.P.get('RAPM'):
            for r in rows:
                p = self.pl.get(r['athlete_id'])
                if p is not None:
                    p['aid'] = r['athlete_id']
            sn = self.SNAPS.get(g['game_id'])
            if sn is not None:
                self.cur = sn
        return oracle


def tune_mae(P, box, since):
    _, recs = GM.run(P, GM.WARM + GM.TUNE, box, record_from=GM.TUNE[0])
    d = [abs(r['oracle'][0] - r['actual_margin']) for r in recs if r['g']['season'] == 2024 and r['g']['tip'] >= since]
    return statistics.mean(d), len(d)


def mae_close(recs):
    d = [(abs(r['tip'][0] - r['actual_margin']), abs(-r['line']['spread_close'] - r['actual_margin']))
         for r in recs if (r.get('line') or {}).get('spread_close') is not None]
    return {'model': round(statistics.mean(a for a, _ in d), 3), 'close': round(statistics.mean(b for _, b in d), 3), 'n': len(d)}


def minutes_check(stints, box):
    """Correlation of stint-derived minutes with box minutes over player-games, and the share of games kept."""
    xs, ys = [], []
    for gid, st in list(stints.items())[::5]:
        mins = defaultdict(float)
        for home, away, secs, *_ in st:
            for a in home + away:
                mins[a] += secs / 60.0
        for r in box.get(gid, []):
            if r['played'] and r['athlete_id'] in mins:
                xs.append(mins[r['athlete_id']]); ys.append(r['minutes'])
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    return round(cov / (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5, 4), len(xs)


def main():
    seasons = GM.WARM + GM.TUNE + GM.TEST
    box = C.player_games(seasons)
    if os.path.exists(CACHE):
        stints, stats = pickle.load(open(CACHE, 'rb'))
    else:
        stints, stats = build_stints(box)
        pickle.dump((stints, stats), open(CACHE, 'wb'))
    print('stints', stats, flush=True)
    mc = minutes_check(stints, box)
    print('minutes corr', mc, flush=True)
    games = C.games(seasons)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'stint_stats': stats, 'minutes_corr': mc, 'tune': {}}
    P0 = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    GM.Model = RapmModel
    snaps = {}
    for filt in ('A', 'G'):
        for lam in LAMS:
            snaps[(filt, lam)] = snapshots(stints, filt, lam, games)
            print('snapshots', filt, lam, len(snaps[(filt, lam)]), flush=True)
    first24 = min(g['tip'] for g in games if g['season'] == 2024)
    since = first24 + dt.timedelta(days=28)
    RapmModel.SNAPS = {}
    res['tune']['S'], res['tune_n'] = tune_mae(dict(P0), box, since)
    picks = {}
    for filt in ('A', 'G'):
        for mode, grid in (('O', [(l, c) for l in LAMS for c in CS]), ('B', [(l, m) for l in LAMS for m in LAMBDAS_B])):
            best = None
            for lam, x in grid:
                RapmModel.SNAPS = snaps[(filt, lam)]
                P = dict(P0, RAPM=mode, **({'C': x} if mode == 'O' else {'LAM': x}))
                m, _ = tune_mae(P, box, since)
                res['tune'][f'{filt}{mode}|lam={lam}|x={x}'] = round(m, 4)
                print('tune', filt, mode, lam, x, round(m, 4), 'shipped', round(res['tune']['S'], 4), flush=True)
                if best is None or m < best[0]:
                    best = (m, lam, x)
            picks[filt + mode] = {'lam': best[1], 'x': best[2]}
    res['chosen'] = picks
    print('chosen', picks, flush=True)

    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    run = lambda P: GM.run(P, seasons, box, lines, inj, record_from=GM.TEST[0])[1]
    RapmModel.SNAPS = {}
    cur = run(dict(P0))
    res['scores'] = {}
    for name, pk in picks.items():
        filt, mode = name[0], name[1]
        RapmModel.SNAPS = snaps[(filt, pk['lam'])]
        recs = run(dict(P0, RAPM=mode, **({'C': pk['x']} if mode == 'O' else {'LAM': pk['x']})))
        blk = {'whole': {'pooled': SS.boot(cur, recs, 0, 'tip', lambda k: True)}}
        for s in GM.TEST:
            sid = {r['g']['game_id'] for r in cur if r['g']['season'] == s}
            blk['whole'][str(s)] = SS.boot(cur, recs, 0, 'tip', lambda k, sid=sid: k in sid)
        withl = [r for r in recs if (r.get('line') or {}).get('spread_close') is not None]
        withc = [r for r in cur if (r.get('line') or {}).get('spread_close') is not None]
        blk['info_variant'] = GM.info_test(withl, 'tip', 'spread_close', 0)
        blk['info_shipped'] = GM.info_test(withc, 'tip', 'spread_close', 0)
        blk['close_mae'] = {'variant': mae_close(recs), 'shipped': mae_close(cur)}
        res['scores'][name] = blk
        print(name, json.dumps(blk['whole']), flush=True)
        print('   info', blk['info_variant'], 'shipped', blk['info_shipped'], flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1, default=str)
    write_md(res)


def write_md(res):
    s = res['stint_stats']
    L = ['# Game model: stint RAPM and garbage time, results', '',
         f"Generated {res['generated']} by `nba/scripts/test_rapm.py`. Rules, committed before this ran: [rapm-prereg.md](rapm-prereg.md). "
         'Test seasons 2024-25 and 2025-26, injury report as of tip, paired bootstrap over games. Shipped parameters otherwise, no retune.', '',
         f"Stint validity: {s['kept']} of {s['games']} games kept ({s['bad_sub']} dropped for a substitution that did not match the floor, {s['no_starters']} without five starters per team). "
         f"Correlation of stint-derived minutes with box-score minutes: {res['minutes_corr'][0]} over {res['minutes_corr'][1]} player-games.", '',
         f"Chosen on 2023-24 (games from 28 days in, n={res['tune_n']}; shipped tune MAE {res['tune']['S']:.4f}): " +
         ', '.join(f"{k} = {v}" for k, v in res['chosen'].items()) + '.', '',
         'Tune MAE: ' + ', '.join(f'{k}: {v}' for k, v in res['tune'].items() if k != 'S') + '.', '',
         'Variants: A = all stints, G = garbage stints removed; O = replace the player value, B = add to it.', '']
    for name, blk in res['scores'].items():
        L += [f'## {name} (margin MAE, points)', '', '| Window | n | Shipped | Variant | Variant - shipped | SE | z |', '|---|---|---|---|---|---|---|']
        for lab in ('2025', '2026', 'pooled'):
            b = blk['whole'][lab]
            L.append(f"| {lab} | {b['n']} | {b['mae_current']} | {b['mae_variant']} | {b['diff']} | {b['se']} | {b['z']} |")
        L += ['', f"Against the close: {blk['close_mae']}. Information test vs the close: variant {blk['info_variant']}; shipped {blk['info_shipped']}.", '']
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
