"""B3: alternate-rung ladders from the SmartStake tape, one mean and one variance scalar per player-stat. EXPERIMENT ONLY.

  python3 scripts/smartstake_alt_ladders.py

smartstake_props.py keeps only each book's main line (alternates are ~80% of the tape and it drops them). This sibling keeps
them. Per (game, player, stat) it pools every usable rung across books:
  two-sided   a book quoting over AND under at the same line: de-vigged, exact
  exchange    Kalshi / Polymarket / Novig / ProphetX single price: taken as the chance (fee not removed; flagged, biased high)
  skipped     one-sided sportsbook alternates (cannot be de-vigged; counted, never guessed)
and fits the mean mu and a variance scalar s (variance = s x prop model v2's shape) by least squares in log-odds with
consensus.implied_mean over a grid of s. Prior art: nba/scripts/build_alt_tails.py (ESPN over-only ladders, frozen NO-GO, no
de-vig possible). This is a different test set (two-sided and exchange rungs), not a rerun.

Reports now, no outcomes needed: ladder counts, fitted s by stat, and a held-out-tail check (fit without the highest and lowest rung,
predict them; s fitted vs s=1). Once games settle: log loss of the fitted ladder against actual results, fitted-s vs s=1, by game
(ship rule shape as elsewhere: second half ROI/CLV > 0, z >= 2, 50+ games; here the unit is a paired log-loss gain, 'n of 50').
Output: data/smartstake/alt_ladders.json (gitignored; terms forbid publishing anything derived).
"""
import json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartstake_bt_lib as L
sys.path.insert(0, str(L.ROOT / 'nba' / 'scripts'))
import consensus as CE

S_GRID = [round(0.5 * 1.08 ** i, 3) for i in range(0, 33)]      # 0.5 .. 5.8, geometric; a fit on the top edge is flagged, not trusted
MIN_RUNGS = 4
OUT = L.SS / 'alt_ladders.json'


def scaled(V, stat, s):
    return {stat: [x * s for x in V[stat]]}


def sse(stat, qs, V, s):
    Vs = scaled(V, stat, s)
    mu = CE.implied_mean(stat, qs, Vs)
    if mu is None:
        return None, None
    return sum((CE.lg(CE.p_over(stat, mu, ln, Vs)) - CE.lg(p)) ** 2 for ln, p, _ in qs), mu


def fit(stat, qs, V):
    best = None
    for s in S_GRID:
        e, mu = sse(stat, qs, V, s)
        if e is not None and (best is None or e < best[0]):
            best = (e, mu, s)
    return best


def ladders(quotes):
    """{(event, player, stat): {line: [(book, p_over, kind)]}} from two-sided rungs and exchange single prices."""
    by = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    skipped = defaultdict(int)
    for (e, who, st, bk, ln, side, alt), q in quotes.items():
        by[(e, who, st)][ln][bk][side] = q['odds']
    out = defaultdict(lambda: defaultdict(list))
    for k, lines in by.items():
        for ln, books in lines.items():
            for bk, s in books.items():
                name = L.BOOK_NAME.get(bk, bk)
                if 'over' in s and 'under' in s:
                    out[k][ln].append((name, L.devig(s['over'], s['under']), 'two'))
                elif bk in L.EXCHANGES:
                    o = s.get('over', s.get('yes'))
                    if o is not None:
                        out[k][ln].append((name, L.am_prob(o), 'exch'))
                    elif 'under' in s:
                        out[k][ln].append((name, 1 - L.am_prob(s['under']), 'exch'))
                else:
                    skipped[bk] += 1
    return out, dict(skipped)


def lg_err(stat, mu, s, V, ln, p):
    return abs(CE.lg(CE.p_over(stat, mu, ln, scaled(V, stat, s))) - CE.lg(p))


def main():
    V = json.load(open(L.ROOT / 'nba' / 'data' / 'prop_model_v2.json'))['variance']['v2']
    q, passes = L.tape_close()
    lad, skipped = ladders(q)
    ev = L.resolve_games(q)
    pid = L.player_ids()
    meta = {}
    for (e, *_), qq in q.items():
        meta.setdefault(e, qq)
    cnt = dict(passes=passes, quotes=len(q), player_stats=len(lad), games=len({k[0] for k in lad}), one_sided_book_alternates_skipped=sum(skipped.values()),
              ladders_fit=0, rungs_used=0, graded_ladders=0)
    per_stat = defaultdict(lambda: {'s': [], 'sse1': 0.0, 'sse_fit': 0.0, 'tail_fit': [], 'tail_s1': [], 'n': 0})
    graded = defaultdict(list)             # game -> [ll(s=1) - ll(fitted s)] per rung, positive = fitted better
    for (e, who, st), lines in lad.items():
        if st not in V:
            continue
        qs = [(ln, p, 1.0) for ln, rs in lines.items() for _, p, _ in rs if 0.02 < p < 0.98]
        if len({x[0] for x in qs}) < MIN_RUNGS:
            continue
        e1, _ = sse(st, qs, V, 1.0)
        best = fit(st, qs, V)
        if best is None or e1 is None:
            continue
        sse_fit, mu, s = best
        st_ = per_stat[st]
        st_['s'].append(s); st_['sse1'] += e1; st_['sse_fit'] += sse_fit; st_['n'] += 1
        cnt['ladders_fit'] += 1; cnt['rungs_used'] += len(qs)
        srt = sorted(qs)
        if len({x[0] for x in qs}) >= 5:                        # held-out tails: refit without the outermost rungs, predict them
            inner = srt[1:-1]
            b = fit(st, inner, V)
            _, mu1 = sse(st, inner, V, 1.0)
            if b and mu1:
                for ln, p, _ in (srt[0], srt[-1]):
                    st_['tail_fit'].append(lg_err(st, b[1], b[2], V, ln, p)); st_['tail_s1'].append(lg_err(st, mu1, 1.0, V, ln, p))
        g = ev.get(e)
        box = L.settled(g[0]) if g else None
        pk = pid.get(L.name_key(who))
        act = L.actual(box, pk, st) if (box and pk) else None
        if act is not None:
            cnt['graded_ladders'] += 1
            _, mu1 = sse(st, qs, V, 1.0)
            for ln, p, _ in qs:
                if act == ln:
                    continue
                y = act > ln
                ll = lambda m, ss: -math.log(max(1e-6, min(1 - 1e-6, CE.p_over(st, m, ln, scaled(V, st, ss)) if y else 1 - CE.p_over(st, m, ln, scaled(V, st, ss)))))
                graded[g[0]].append(ll(mu1, 1.0) - ll(mu, s))
    res = {'asof': L.datetime.now(L.timezone.utc).isoformat(timespec='minutes'), 'counts': cnt, 'skipped_by_book': skipped, 'by_stat': {}}
    for st, d in sorted(per_stat.items()):
        r = {'ladders': d['n'], 'at_grid_top': sum(1 for x in d['s'] if x >= S_GRID[-1] * 0.999), 'at_grid_bottom': sum(1 for x in d['s'] if x <= S_GRID[0] * 1.001), 's_median': round(statistics.median(d['s']), 2), 's_mean': round(statistics.mean(d['s']), 2),
             'sse_s1': round(d['sse1'], 3), 'sse_fitted': round(d['sse_fit'], 3)}
        if d['tail_fit']:
            r['tail_abs_logit_err'] = {'n': len(d['tail_fit']), 'fitted_s': round(statistics.mean(d['tail_fit']), 4), 's_eq_1': round(statistics.mean(d['tail_s1']), 4)}
        res['by_stat'][st] = r
    if graded:
        gm = [statistics.mean(v) for v in graded.values()]
        se = statistics.stdev(gm) / math.sqrt(len(gm)) if len(gm) > 1 else None
        res['graded'] = {'games': len(gm), 'games_of_50': f'{len(gm)} of 50', 'mean_ll_gain_per_rung': round(statistics.mean(gm), 5),
                         'z': round(statistics.mean(gm) / se, 2) if se else None, 'rungs': sum(len(v) for v in graded.values())}
    else:
        res['graded'] = 'none: no settled games yet (0 of 50)'
    L.SS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print('->', OUT)


if __name__ == '__main__':
    main()
