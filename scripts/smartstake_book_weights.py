"""B2: fit per-book consensus weights from the SmartStake tape against settled NBA props. EXPERIMENT ONLY.

  python3 scripts/smartstake_book_weights.py            # run on the current tape (needs `git fetch` for origin/nba-data)
  python3 scripts/smartstake_book_weights.py --selftest # synthetic check that the fitter recovers known weights

The question: does a consensus whose book weights are FIT beat the hand-set nba/scripts/consensus.py WEIGHTS
(Pinnacle 3.0, everything else 1.5)? Pinnacle is not on SmartStake, so it comes from the recorder's own Pinnacle player-prop
series (origin/nba-data snapshots) and stays fixed at 3.0; every other book's weight is fit RELATIVE to it, from a grid.

Rows: every (player, stat, game) where Pinnacle and at least one SmartStake book hold a two-sided main line at the last
pre-start pass. Each book in turn is the venue being judged; the consensus is built from the OTHER books at that book's line
(consensus.implied_mean, prop model v2 shape, no minutes term). Fit and score reuse build_consensus.evaluate: weights are
chosen on the first half by tip time (log loss), blends fit on the first half, bets (3% edge) scored on the second.
The 'model' column in evaluate is the HAND-WEIGHTED consensus, so 'LL cons' vs 'LL model' is fitted vs hand-set.

Ship rule (existing, unchanged): GO needs second-half ROI > 0, z >= 2 and 50+ games. Reported as 'n of 50' games.
Forward-only: 2026-27 box scores are not on sportsdataverse, so grading uses the recorder's results/ files; until games
settle this prints counts only. Output: data/smartstake/book_weights.json (gitignored).
"""
import json, math, os, random, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartstake_bt_lib as L
sys.path.insert(0, str(L.ROOT / 'nba' / 'scripts'))
import consensus as CE
import build_consensus as B

GRID = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
PIN_W = 3.0
HAND = lambda book: CE.WEIGHTS.get(book, 1.5)
MIN_ROWS = 60
OUT = L.SS / 'book_weights.json'


def cons_for(stat, quotes, w, V, skip):
    qs = [(ln, p, PIN_W if bk == 'Pinnacle' else w(bk)) for bk, ln, p in quotes if bk != skip]
    return qs


def predict(stat, quotes, w, V, skip, line):
    qs = cons_for(stat, quotes, w, V, skip)
    if not qs or sum(1 for q in qs if q[2] > 0) < 1:
        return None
    mu = CE.implied_mean(stat, qs, V)
    return None if mu is None else CE.p_over(stat, mu, line, V)


def fit_weights(rows, V, books):
    """Coordinate descent on the grid: minimise log loss of the leave-one-book-out consensus over `rows`. Pinnacle fixed."""
    w = {b: 1.5 for b in books}

    def loss(wd):
        tot = n = 0
        for r in rows:
            p = predict(r['stat'], r['quotes'], lambda b: wd.get(b, 1.5), V, r['book'], r['line'])
            if p is not None:
                tot += B.ll(p, r['y']); n += 1
        return tot / n if n else 9
    best = loss(w)
    for _ in range(3):
        moved = False
        for b in books:
            for g in GRID:
                if g == w[b]:
                    continue
                t = dict(w); t[b] = g
                l = loss(t)
                if l < best - 1e-6:
                    best, w, moved = l, t, True
        if not moved:
            break
    return w, best


def build_rows(V):
    q, passes = L.tape_close()
    mp = L.main_pairs(q)
    ev = L.resolve_games(q)
    pins = L.pinnacle_close(L.snapshot_days())
    pid = L.player_ids()
    meta = {}
    for (e, *_), qq in q.items():
        meta.setdefault(e, qq)
    units = defaultdict(list)
    for (e, who, st, bk), (ln, p, o, u) in mp.items():
        if bk in ('prizepicks',) or st not in V:
            continue
        units[(e, who, st)].append((L.BOOK_NAME.get(bk, bk), ln, p, o, u))
    cnt = dict(passes=passes, quotes=len(q), units=len(units), games_on_tape=len({k[0] for k in units}), games_matched=0,
               units_with_pinnacle=0, units_graded=0, no_player_id=0, push_dropped=0)
    rows = []
    for (e, who, st), bks in units.items():
        m = meta[e]
        tip = int(L.datetime.fromisoformat(m['starts_at'].replace('Z', '+00:00')).timestamp())
        pin = pins.get((tip, m['home'].lower(), L.name_key(who), st))
        if not pin:
            continue
        cnt['units_with_pinnacle'] += 1
        quotes = [('Pinnacle', pin[0], pin[1])] + [(b, ln, p) for b, ln, p, _, _ in bks]
        g = ev.get(e)
        pk = pid.get(L.name_key(who))
        if not pk:
            cnt['no_player_id'] += 1
        box = L.settled(g[0]) if g else None
        act = L.actual(box, pk, st) if (box and pk) else None
        if act is None:
            continue
        for b, ln, p, o, u in bks:
            if act == ln:
                cnt['push_dropped'] += 1
                continue
            others = [x for x in quotes if x[0] != b]
            if len(others) < 2:
                continue
            rows.append({'stat': st, 'book': b, 'line': ln, 'price': p, 'y': act > ln, 'tip': tip, 'gid': g[0], 'quotes': quotes,
                         'over_px': o, 'under_px': u, 'dist': min(abs(x[1] - ln) for x in others)})
        cnt['units_graded'] += 1
    cnt['games_matched'] = len({g[0] for g in ev.values()})
    return rows, cnt


def run(rows, cnt, V):
    out = {'asof': L.datetime.now(L.timezone.utc).isoformat(timespec='minutes'), 'counts': cnt, 'hand': {'Pinnacle': PIN_W, 'default': 1.5}}
    games = len({r['gid'] for r in rows})
    out['graded_rows'], out['graded_games'] = len(rows), games
    if len(rows) < MIN_ROWS:
        out['status'] = f'not graded: {len(rows)} settled rows (need {MIN_ROWS}); {games} of 50 games'
        return out
    rows = sorted(rows, key=lambda r: r['tip'])
    half = len(rows) // 2
    books = sorted({r['book'] for r in rows})
    w, fit_ll = fit_weights(rows[:half], V, books)
    hand_ll = statistics.mean(B.ll(predict(r['stat'], r['quotes'], HAND, V, r['book'], r['line']) or .5, r['y']) for r in rows[:half])
    out['fit_weights'] = {'Pinnacle': PIN_W, **w}
    out['fit_half'] = {'rows': half, 'll_fitted': round(fit_ll, 5), 'll_hand': round(hand_ll, 5)}
    for r in rows:
        r['cons_fit'] = predict(r['stat'], r['quotes'], lambda b: w.get(b, 1.5), V, r['book'], r['line'])
        r['cons_hand'] = predict(r['stat'], r['quotes'], HAND, V, r['book'], r['line'])
    rows = [r for r in rows if r['cons_fit'] is not None and r['cons_hand'] is not None]

    def bets(r, fair):
        o = []
        po, pu = L.am_prob(r['over_px']), L.am_prob(r['under_px'])
        pay = lambda a: a / 100 if a > 0 else 100 / -a
        if fair - po >= B.EDGE:
            o.append(('Over', pay(r['over_px']) if r['y'] else -1.0))
        if (1 - fair) - pu >= B.EDGE:
            o.append(('Under', pay(r['under_px']) if not r['y'] else -1.0))
        return o
    res = {}
    for label, c, m in (('fitted', 'cons_fit', 'cons_hand'), ('hand', 'cons_hand', 'cons_fit')):
        rr = [dict(r, cons=r[c], model=r[m]) for r in rows]
        e = B.evaluate(rr, label, bets, fair_keys=(('consensus', ['cons']),))
        res[label] = {'logloss': e['logloss'], 'test_n': e['test_n'], 'bets': e['bets']['consensus']}
        res[label]['verdict'] = {s: B.verdict(v) for s, v in e['bets']['consensus'].items()}
        res[label]['games_of_50'] = {s: f"{v.get('games', 0)} of 50" for s, v in e['bets']['consensus'].items()}
    out['second_half'] = res
    out['note'] = 'A fitted weight set is an improvement only if its second-half ROI/CLV > 0 at z >= 2 over 50+ games; sample sizes above.'
    return out


def selftest():
    """Synthetic: books quote noisy versions of a true mean; weight on the least noisy book should come out highest."""
    V = json.load(open(L.ROOT / 'nba' / 'data' / 'prop_model_v2.json'))['variance']['v2']
    rnd, rows = random.Random(7), []
    noise = {'Pinnacle': .1, 'DraftKings': .15, 'FanDuel': .15, 'Fanatics': 1.2}
    for i in range(400):
        mu = rnd.uniform(14, 28)
        sd = math.sqrt(V['pts'][0] + V['pts'][1] * mu + V['pts'][2] * mu * mu)
        y_val = rnd.gauss(mu, sd)
        qs = []
        for b, s in noise.items():
            ln = round(mu + rnd.gauss(0, s)) + .5
            qs.append((b, ln, min(.97, max(.03, CE.p_over('pts', mu + rnd.gauss(0, s * 2), ln, V)))))
        for b in ('DraftKings', 'FanDuel', 'Fanatics'):
            ln, p = next((x[1], x[2]) for x in qs if x[0] == b)
            rows.append({'stat': 'pts', 'book': b, 'line': ln, 'y': y_val > ln, 'quotes': qs})
    w, ll = fit_weights(rows[:600], V, ['DraftKings', 'FanDuel', 'Fanatics'])
    print('SYNTHETIC selftest (not a result): fitted', w, 'log loss', round(ll, 4), '; Fanatics was made the noisiest book')


if __name__ == '__main__':
    V = json.load(open(L.ROOT / 'nba' / 'data' / 'prop_model_v2.json'))['variance']['v2']
    if '--selftest' in sys.argv:
        selftest(); sys.exit()
    rows, cnt = build_rows(V)
    out = run(rows, cnt, V)
    L.SS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'second_half'}, indent=1))
    for lab, r in (out.get('second_half') or {}).items():
        print(lab, r['logloss'], r['bets'], r['verdict'], r['games_of_50'])
    print('->', OUT)
