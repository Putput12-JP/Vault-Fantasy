#!/usr/bin/env python3
"""
What would the record look like if the picks were ranked by confidence, or given letter grades? Descriptive, not a test and not a model change.

Reads the shipped game model's walk-forward records on the two test seasons (build_game_model.run: the same games, closing lines and injury report as the
published backtest), and asks, for definitions fixed before the numbers were read:

  Spread picks, confidence = the edge in points: |model margin + home spread|. Grades by absolute edge: A = 5 or more, B = 3 to 5, C = under 3
  (the same buckets the Track Record already shows; nothing is tuned). Also the top 1, 2 and 3 picks of each day by edge.
  Winner picks, confidence = the model's chance for the side it picks. Grades by that chance: A = 70% or more, B = 60 to 70%, C = under 60%.
  Also the top 3 picks of each day by that chance, and how often the market favourite wins on the same games.

Each spread rank is scored against the CLOSING spread (the conservative number: our picks lock 4 hours before tip, much closer to the close than to
the untimestamped ESPN open) and, as an optimistic bound, the opening spread. Break-even at -110 is 52.4%. Win rates are quoted with Wilson intervals.
No units are computed for the history: closing prices are not stored for every game, and a price is never inferred.

  python3 nba/scripts/analyze_pick_grades.py        # writes nba/data/pick_grades.json and nba/docs/pick-grades.md
"""
import json, math, os, statistics, sys, datetime as dt
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nba_common as C
import build_game_model as GM

OUT_JSON = os.path.join(C.HERE, '..', 'data', 'pick_grades.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'pick-grades.md')
BE = 110 / 210


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def wilson(w, n):
    if not n:
        return None
    z, p = 1.96, w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - m) / d, 4), round((c + m) / d, 4)]


def tally(rows):
    """rows: [(won: bool | None)] -> {'n', 'w', 'l', 'p', 'win', 'ci'}; None = push."""
    w = sum(1 for r in rows if r is True)
    l = sum(1 for r in rows if r is False)
    n = w + l
    return {'n': n, 'w': w, 'l': l, 'p': sum(1 for r in rows if r is None), 'win': round(w / n, 4) if n else None, 'ci': wilson(w, n)}


def ats_result(margin, spread, actual):
    """(edge, won) for a home spread: edge > 0 means the model takes the home side. won None on a push."""
    e = margin + spread
    if e == 0:
        return None
    cover = actual + spread
    if cover == 0:
        return abs(e), None
    return abs(e), (cover > 0) == (e > 0)


def main():
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    gm = json.load(open(GM.OUT_JSON))
    P = dict(GM.DEFAULT, **gm['params'])
    sd = gm['tune_mae'][0] * math.sqrt(math.pi / 2)
    lines = C.closing_lines()
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    _, recs = GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, lines, inj, record_from=GM.TEST[0])
    games = []
    for r in recs:
        L = r.get('line') or {}
        if L.get('spread_close') is None:
            continue
        m = r['tip'][0]
        games.append({'day': r['g']['tip_et'].strftime('%Y-%m-%d'), 'season': r['g']['season'], 'margin': m, 'act': r['actual_margin'],
                      'close': L['spread_close'], 'open': L.get('spread_open'), 'p': phi(m / sd)})
    out = {'games': len(games), 'sd': round(sd, 2), 'seasons': {}}
    for label, sel in [(str(s), lambda g, s=s: g['season'] == s) for s in GM.TEST] + [('pooled', lambda g: True)]:
        G = [g for g in games if sel(g)]
        blk = {'games': len(G), 'ats': {}, 'winner': {}}
        for line in ('close', 'open'):
            res = []
            for g in G:
                if g[line] is None:
                    continue
                x = ats_result(g['margin'], g[line], g['act'])
                if x:
                    res.append((g, x[0], x[1]))
            rank = {}
            rank['all'] = tally([w for _, _, w in res])
            for name, lo, hi in (('A: edge 5+', 5, 99), ('B: edge 3 to 5', 3, 5), ('C: edge under 3', 0, 3)):
                rank[name] = tally([w for _, e, w in res if lo <= e < hi])
            for n in (1, 2, 3):
                pick = []
                byday = defaultdict(list)
                for g, e, w in res:
                    byday[g['day']].append((e, w))
                for d, xs in byday.items():
                    if len(xs) >= n:
                        pick += [w for e, w in sorted(xs, key=lambda t: -t[0])[:n]]
                rank[f'top {n} per day'] = tally(pick)
            blk['ats'][line] = rank
        # winner picks
        wl = []
        for g in G:
            if g['margin'] == 0 or g['act'] == 0:
                continue
            side_home = g['margin'] > 0
            p = g['p'] if side_home else 1 - g['p']
            pm = phi(-g['close'] / sd)                                # the market's chance for the home team, from the closing spread through the same normal
            g['pm_side'] = pm if side_home else 1 - pm
            wl.append((g, p, side_home == (g['act'] > 0)))
        W = {'all': tally([w for _, _, w in wl]), 'predicted': round(statistics.mean(p for _, p, _ in wl), 4) if wl else None,
             'market_p': round(statistics.mean(g['pm_side'] for g, _, _ in wl), 4) if wl else None}
        for name, lo, hi in (('A: 70% or more', .7, 1.01), ('B: 60 to 70%', .6, .7), ('C: under 60%', .5, .6)):
            sub = [(g, p, w) for g, p, w in wl if lo <= p < hi]
            W[name] = {**tally([w for _, _, w in sub]), 'predicted': round(statistics.mean(p for _, p, _ in sub), 4) if sub else None,
                       'market_p': round(statistics.mean(g['pm_side'] for g, _, _ in sub), 4) if sub else None}
        byday = defaultdict(list)
        for g, p, w in wl:
            byday[g['day']].append((p, w, g['pm_side'], p - g['pm_side']))
        for n in (1, 3):
            sel = [x for d, xs in byday.items() if len(xs) >= n for x in sorted(xs, key=lambda t: -t[0])[:n]]
            W[f'top {n} per day'] = {**tally([x[1] for x in sel]), 'predicted': round(statistics.mean(x[0] for x in sel), 4), 'market_p': round(statistics.mean(x[2] for x in sel), 4)}
        # value: ranked by how far the model's chance sits above the market's for the same side
        sel = [x for d, xs in byday.items() if len(xs) >= 3 for x in sorted(xs, key=lambda t: -t[3])[:3]]
        W['top 3 per day by value (model chance minus market chance)'] = {**tally([x[1] for x in sel]), 'predicted': round(statistics.mean(x[0] for x in sel), 4), 'market_p': round(statistics.mean(x[2] for x in sel), 4)}
        fav = [(g['close'] < 0) == (g['act'] > 0) for g in G if g['close'] not in (0, None) and g['act'] != 0]
        W['market favourite'] = tally(fav)
        agree = [w for g, p, w in wl if g['close'] and ((g['margin'] > 0) == (g['close'] < 0))]
        disagree = [w for g, p, w in wl if g['close'] and ((g['margin'] > 0) != (g['close'] < 0))]
        W['agrees with the market favourite'] = tally(agree)
        W['disagrees with the market favourite'] = tally(disagree)
        blk['winner'] = W
        out['seasons'][label] = blk
    out['generated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(out, open(OUT_JSON, 'w'), indent=1)
    print(json.dumps({k: {n: (v['n'], v['win']) for n, v in b['ats']['close'].items()} for k, b in out['seasons'].items() if k == 'pooled'}, indent=1))
    print(json.dumps({n: (v['n'], v['win'], v.get('predicted'), v.get('market_p')) for n, v in out['seasons']['pooled']['winner'].items() if isinstance(v, dict)}, indent=1))
    return out


if __name__ == '__main__':
    main()
