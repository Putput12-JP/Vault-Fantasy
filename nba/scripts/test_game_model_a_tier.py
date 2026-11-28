#!/usr/bin/env python3
"""
Game Picks A tier: pre-registered subgroup test. Rules, fixed before any score: docs/game-model-a-tier.md. Results: docs/game-model-a-tier-results.md.

  python3 nba/scripts/test_game_model_a_tier.py [--games FILE] [--first FILE] [--lock FILE] [--out FILE]

--games  per-game history dump (season, day, am_res, am, tip, sp_open, sp_close); built from the raw data by build_game_model.run when absent.
--first  this season's 4-hour-lock rows (for the news part); --lock the lineup-lock rows (data/game_picks.json). Pure stdlib.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
DATA = os.path.join(HERE, '..', 'data')
BE = 110 / 210
A_EDGE, EARLY_DAYS, SD = 5.0, 28, 13.19
RULES = ['S0 all A, followed', 'S1 all A, faded', 'S2 A takes the underdog', 'S3 A takes the favourite', 'S4 A with news part >= 1', 'S5 A with news part < 1',
         'S6 A after day 28', 'S7 A in the first 28 days', 'S8 A with edge >= 7', 'S9 A home picks', 'S10 A away picks']


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def one_sided_z(w, n):
    return (w / n - BE) / math.sqrt(BE * (1 - BE) / n) if n else 0.0


def make_game(res, L, model, news, day_n):
    """A candidate game. res: final home margin; L: home margin implied by the line; model: model home margin; news: |late news part| or None; day_n: days into the season."""
    edge = model - L
    if abs(edge) < 1e-9:
        return None
    home = edge > 0
    spread_taken = -L if home else L                      # the spread the picked side takes (negative = favourite)
    cover = (res - L) * (1 if home else -1)               # > 0: the pick covers
    return {'edge': abs(edge), 'home': home, 'dog': spread_taken > 0, 'news': news, 'day_n': day_n, 'cover': cover}


def rule_games(games, rule):
    """(wins, losses) for a rule over candidate games; pushes skipped. Faded: the other side."""
    sel = {'S0': lambda g: True, 'S1': lambda g: True, 'S2': lambda g: g['dog'], 'S3': lambda g: not g['dog'],
           'S4': lambda g: g['news'] is not None and g['news'] >= 1, 'S5': lambda g: g['news'] is not None and g['news'] < 1,
           'S6': lambda g: g['day_n'] >= EARLY_DAYS, 'S7': lambda g: g['day_n'] < EARLY_DAYS, 'S8': lambda g: g['edge'] >= 7,
           'S9': lambda g: g['home'], 'S10': lambda g: not g['home']}[rule.split()[0]]
    w = l = 0
    for g in games:
        if g['edge'] < A_EDGE or not sel(g) or g['cover'] == 0:
            continue
        win = (g['cover'] > 0) != (rule.startswith('S1 '))
        w += win; l += not win
    return w, l


def history(path):
    if path and os.path.exists(path):
        raw = json.load(open(path))
    else:
        import build_game_model as B, nba_common as C
        box = C.player_games(B.WARM + B.TUNE + B.TEST)
        P = dict(B.DEFAULT, **json.load(open(B.OUT_JSON))['params'])
        _, recs = B.run(P, B.WARM + B.TUNE + B.TEST, box, C.closing_lines(), C.InjuryAsOf(B.TEST, C.player_index(box)), record_from=B.TEST[0])
        raw = [{'season': r['g']['season'], 'day': r['g']['tip_et'].strftime('%Y-%m-%d'), 'am_res': r['actual_margin'], 'am': r['am'][0], 'tip': r['tip'][0],
                'sp_close': (r.get('line') or {}).get('spread_close')} for r in recs]
    import datetime as dt
    first = {}
    for r in raw:
        first[r['season']] = min(first.get(r['season'], r['day']), r['day'])
    out = {}
    for r in raw:
        if r['sp_close'] is None:
            continue
        n = (dt.date.fromisoformat(r['day']) - dt.date.fromisoformat(first[r['season']])).days
        g = make_game(float(r['am_res']), -float(r['sp_close']), float(r['tip']), abs(float(r['tip']) - float(r['am'])), n)
        if g:
            out.setdefault(r['season'], []).append(g)
    return out


def rows_of(path):
    sys.path.insert(0, HERE)
    import game_pick_record as G
    out = {}
    for day, x in json.load(open(path))['days'].items():
        for r in x['rows']:
            o = dict(zip(G.COLS, r)); o['day'] = day
            if o['clock'] == 'f':
                out[o['game']] = o
    return out


def forward(first_path, lock_path):
    import datetime as dt
    lock = rows_of(lock_path)
    first = rows_of(first_path) if first_path and os.path.exists(first_path) else {}
    start = dt.date(2026, 10, 20)
    out = []
    for k, o in lock.items():
        if o['spread'] is None or o['am'] is None:
            continue
        news = abs(o['margin'] - first[k]['margin']) if k in first else None
        g = make_game(float(o['am']), -float(o['spread']), float(o['margin']), news, (dt.date.fromisoformat(o['day']) - start).days)
        if g:
            out.append(g)
    return out, lock


def winner_a(lock):
    """Forward winner A: record and units at the stored moneyline, cover rate of the same teams on the spread, and the price-aware cut (model chance above the spread-implied one by 3+)."""
    rows = [o for o in lock.values() if o['ml_side'] and o['ml_res'] in ('W', 'L') and o['p_home'] is not None]
    A = [o for o in rows if (o['p_home'] if o['ml_side'] == 'H' else 1 - o['p_home']) >= 0.7]

    def summ(S):
        w = sum(o['ml_res'] == 'W' for o in S); u = [o['ml_units'] for o in S if o['ml_units'] is not None]
        cov = [(float(o['am']) + o['spread'] > 0) if o['ml_side'] == 'H' else (float(o['am']) + o['spread'] < 0) for o in S if o['spread'] is not None and float(o['am']) + o['spread'] != 0]
        return {'n': len(S), 'w': w, 'l': len(S) - w, 'units': round(sum(u), 2), 'priced': len(u), 'cover_w': sum(cov), 'cover_n': len(cov)}
    pa = []
    for o in A:
        p = o['p_home'] if o['ml_side'] == 'H' else 1 - o['p_home']
        m = phi(-o['spread'] / SD) if o['ml_side'] == 'H' else 1 - phi(-o['spread'] / SD)       # the chance the spread implies for the same team
        if p - m >= 0.03:
            pa.append(o)
    return {'all A': summ(A), 'A with model chance 3+ over the spread-implied': summ(pa)}


def main(argv):
    arg = lambda f, d=None: argv[argv.index(f) + 1] if f in argv else d
    hist = history(arg('--games'))
    fwd, lock = forward(arg('--first'), arg('--lock', os.path.join(DATA, 'game_picks.json')))
    seasons = sorted(hist)
    out = {'seasons': seasons, 'rules': {}}
    for r in RULES:
        d, c = rule_games(hist[seasons[0]], r), rule_games(hist[seasons[1]], r)
        pw, pn = d[0] + c[0], sum(d) + sum(c)
        f = rule_games(fwd, r)
        out['rules'][r] = {'discovery': d, 'confirm': c, 'pooled_z': round(one_sided_z(pw, pn), 2), 'forward': f,
                           'pass': bool(sum(d) >= 60 and sum(c) >= 60 and d[0] / sum(d) >= BE and c[0] / sum(c) >= BE and one_sided_z(pw, pn) >= 2.6)}
    out['winner_a'] = winner_a(lock)
    print(json.dumps(out, indent=1))
    if arg('--out'):
        json.dump(out, open(arg('--out'), 'w'))
    return out


if __name__ == '__main__':
    main(sys.argv[1:])
