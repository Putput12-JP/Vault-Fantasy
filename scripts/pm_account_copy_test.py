#!/usr/bin/env python3
"""
Sharp Polymarket accounts: the pre-registered copy test in docs/pm-accounts-copy-test.md.

  1. games + trades   NFL weeks 1-3 and college football from Aug 22 (the archive's high-grade era): every $1k+ taker
                      trade on the full-game moneyline before kickoff, with the account (build_pm_wallets.game_record).
  2. labels           data/pm_wallets.json with every test game's trades taken back out, so an account is judged only
                      on games before the test window (same sharp / usually-losing rule as the scorecard).
  3. quotes           the archive's best bid / ask for the token bought, only in the hours each trade needs (its own
                      hour through 2 hours later, and kickoff), cached per hour.
  4. measures         copy at the ask d minutes later vs the close (verdict at 15 minutes), markouts, spread paid,
                      and each account's measured speed -> docs/pm-accounts-copy-results.md, data/pm_account_speed.json

Usage: python3 scripts/pm_account_copy_test.py --cache <dir> [--nfl 2026-10-01:2026-10-28 --cfb 2026-09-29:2026-10-27 --tag retest]
(needs duckdb + pytz, like pm_archive.py). Defaults are the first run's windows; the declared re-test passes its own.
"""
import argparse, bisect, datetime as dt, gzip, json, math, os, random, statistics as S, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import build_pm_wallets as BW
import pm_archive as PA

WINDOW = {'nfl': ('2026-09-10', '2026-09-30'), 'cfb': ('2026-08-22', '2026-09-29')}
COPY_D = (2, 5, 10, 15, 30, 60)
MARK_D = (1, 5, 15, 30, 60, 120)
PRIMARY, MAX_COPY_SPREAD, MAX_CLOSE_SPREAD = 15, 0.05, 0.10
B = 2000


def load_games(cache):
    """Every test game: slug, sport, start, moneyline cid + tokens, $1k+ taker trades [wallet, ts, outcomeIndex, side, price, size]."""
    p = os.path.join(cache, 'games.json')
    if os.path.exists(p):
        return json.load(open(p))
    out = []
    for sport, (a, b) in WINDOW.items():
        BW.set_sport(sport)
        evs = [e for e in BW.closed_games() if a <= BW.GAME_RE.match(e['slug']).group(1) < b]
        print(f'{sport}: {len(evs)} closed games in window', flush=True)

        def one(e):
            g = BW.game_record(e)
            if not g:
                return None
            ms = [m for m in e.get('markets') or [] if m.get('sportsMarketType') == 'moneyline']
            ml = max(ms, key=lambda m: float(m.get('volumeNum') or 0)) if ms else None
            if not ml:
                return None
            g.update(sport=sport, cid=ml['conditionId'].lower()[2:], tokens=[hex(int(x))[2:].zfill(64) for x in json.loads(ml['clobTokenIds'])])
            return g
        with ThreadPoolExecutor(6) as ex:
            out += [g for g in ex.map(one, evs) if g and g['big']]
    json.dump(out, open(p, 'w'))
    return out


def labels(games):
    """NFL scorecard minus the test games' own trades -> {wallet: 'sharp' | 'dull'}."""
    BW.set_sport('nfl')
    sc = json.load(open(BW.OUT))
    W, done = {w: list(a) for w, a in sc['wallets'].items()}, set(sc.get('processed') or [])
    T = {}
    for g in games:
        if g['sport'] == 'nfl' and g['slug'] in done:
            BW.add_game(T, g)
    for w, t in T.items():
        if w in W:
            W[w] = [W[w][i] - t[i] for i in range(4)]
    lab = {}
    for w, a in W.items():
        c, _ = BW.classify(a)
        if c:
            lab[w] = c
    return lab, sum(1 for g in games if g['sport'] == 'nfl' and g['slug'] in done)


def trades(games, lab):
    """One row per account, game and side bought (its first $1k+ trade): token index bought, price paid, time."""
    rows = []
    for g in games:
        seen = set()
        for w, ts, oi, side, p, size in sorted(g['big'], key=lambda x: x[1]):
            if not (0.02 < p < 0.98):
                continue
            k, q = (oi, p) if side == 'BUY' else (1 - oi, 1 - p)
            if (w, k) in seen:
                continue
            seen.add((w, k))
            rows.append({'g': g['slug'], 'sport': g['sport'], 'start': g['start'], 'cid': g['cid'], 'tok': g['tokens'][k], 'w': w,
                         'grp': lab.get(w, 'other'), 't': ts, 'paid': q, 'usd': p * size})
    return rows


def quotes(rows, games, cache):
    """{(cid, token): sorted [(ms, bid, ask)]} from the hours the trades need."""
    need = defaultdict(set)
    for r in rows:
        for h in range(int(r['t'] // 3600) - 1, int((min(r['start'], r['t'] + 7200)) // 3600) + 1):
            need[h * 3600].add(r['cid'])
    for g in games:
        for h in (int(g['start'] // 3600) - 1, int(g['start'] // 3600)):
            need[h * 3600].add(g['cid'])
    hours = sorted(t for t in need if t >= PA.V3_START.timestamp())
    print(f'quotes: {len(hours)} hours, {sum(len(v) for v in need.values())} market-hours', flush=True)

    def one(t):
        p = os.path.join(cache, f'bba_{PA.iso(t)[:13]}.json.gz')
        if os.path.exists(p):
            return json.load(gzip.open(p, 'rt'))
        c = PA.con()
        rows_ = PA.query(c, t, 'best_bid_ask', "lower(hex(market)), lower(hex(asset_id)), epoch_ms(timestamp), best_bid, best_ask", sorted(need[t]))
        if rows_ is None:
            return []
        out = [[m, a, tm, float(b) if b is not None else None, float(k) if k is not None else None] for m, a, tm, b, k in rows_]
        with gzip.open(p, 'wt') as f:
            json.dump(out, f)
        return out
    Q = defaultdict(list)
    with ThreadPoolExecutor(8) as ex:
        for i, rs in enumerate(ex.map(one, hours)):
            for m, a, tm, b, k in rs:
                Q[(m, a)].append((tm, b, k))
            if i % 100 == 0:
                print(f'  {i}/{len(hours)} hours', flush=True)
    for k in Q:
        Q[k].sort()
    return Q


def at(Q, cid, tok, t):
    """Prevailing (bid, ask) for the token at unix time t: the last quote at or before t, within the hour before."""
    L = Q.get((cid, tok))
    if not L:
        return None
    i = bisect.bisect_right(L, (t * 1000, 9, 9)) - 1
    if i < 0 or L[i][0] < (t - 3600) * 1000:
        return None
    return L[i][1], L[i][2]


def mid(q):
    return None if not q or q[0] is None or q[1] is None or q[1] < q[0] else (q[0] + q[1]) / 2


def boot_se(byg, fn):
    keys, rnd, vals = list(byg), random.Random(11), []
    for _ in range(B):
        smp = [x for _ in keys for x in byg[rnd.choice(keys)]]
        if smp:
            vals.append(fn(smp))
    return S.pstdev(vals) if len(vals) > 10 else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--gather-only', action='store_true')
    ap.add_argument('--nfl'); ap.add_argument('--cfb'); ap.add_argument('--tag', default='')
    a = ap.parse_args()
    for k in ('nfl', 'cfb'):
        if getattr(a, k):
            WINDOW[k] = tuple(getattr(a, k).split(':'))
    sfx = f'-{a.tag}' if a.tag else ''
    os.makedirs(a.cache, exist_ok=True)
    games = load_games(a.cache)
    lab, n_removed = labels(games)
    rows = trades(games, lab)
    from collections import Counter
    print(f"{len(games)} games ({Counter(g['sport'] for g in games)}), {len(rows)} first trades; groups {Counter(r['grp'] for r in rows)}; "
          f"labels: {Counter(lab.values())}, {n_removed} NFL test games taken out of the scorecard", flush=True)
    if a.gather_only:
        return
    Q = quotes(rows, games, a.cache)
    # close per game token: the mid at kickoff
    for r in rows:
        r['close'] = (lambda q: mid(q) if q and q[1] - q[0] <= MAX_CLOSE_SPREAD else None)(at(Q, r['cid'], r['tok'], r['start'] - 1))
        q0 = at(Q, r['cid'], r['tok'], r['t'])
        r['mid0'] = mid(q0)
        for d in COPY_D:
            t = r['t'] + d * 60
            q = at(Q, r['cid'], r['tok'], t) if t < r['start'] else None
            r[f'copy{d}'] = (r['close'] / q[1] - 1) if q and r['close'] and q[1] and 0 < q[1] < 1 and q[1] - q[0] <= MAX_COPY_SPREAD else None
        for d in MARK_D:
            t = r['t'] + d * 60
            m = mid(at(Q, r['cid'], r['tok'], t)) if t < r['start'] else None
            r[f'mk{d}'] = m / r['paid'] - 1 if m else None
        r['mkclose'] = r['close'] / r['paid'] - 1 if r['close'] else None
    sharp = [r for r in rows if r['grp'] == 'sharp']
    res = {}
    for d in COPY_D:
        X = [r for r in sharp if r[f'copy{d}'] is not None]
        byg = defaultdict(list)
        for r in X:
            byg[r['g']].append(r[f'copy{d}'])
        m = S.fmean([r[f'copy{d}'] for r in X]) if X else None
        res[d] = {'n': len(X), 'games': len(byg), 'mean': m, 'se': boot_se(byg, S.fmean) if X else None,
                  'nfl': S.fmean([r[f'copy{d}'] for r in X if r['sport'] == 'nfl']) if any(r['sport'] == 'nfl' for r in X) else None,
                  'cfb': S.fmean([r[f'copy{d}'] for r in X if r['sport'] == 'cfb']) if any(r['sport'] == 'cfb' for r in X) else None}
    P = res[PRIMARY]
    go = P['mean'] is not None and P['se'] == P['se'] and P['mean'] > 0 and P['mean'] >= 2 * P['se']
    curve = {}
    for grp in ('sharp', 'dull', 'other'):
        G = [r for r in rows if r['grp'] == grp]
        curve[grp] = {'n': len(G), 'spread_paid': S.fmean([r['paid'] / r['mid0'] - 1 for r in G if r['mid0']]) if any(r['mid0'] for r in G) else None,
                      **{f'mk{d}': (lambda v: S.fmean(v) if v else None)([r[f'mk{d}'] for r in G if r[f'mk{d}'] is not None]) for d in MARK_D},
                      'mkclose': (lambda v: S.fmean(v) if v else None)([r['mkclose'] for r in G if r['mkclose'] is not None])}
    # each account's measured speed (all its test-window trades): how much of its move to the close is in by 5 and 30 min
    acc = defaultdict(list)
    for r in rows:
        if r['mkclose'] is not None:
            acc[r['w']].append(r)
    speed = {}
    for w, L in acc.items():
        if len(L) < 3:
            continue
        mc = S.fmean([r['mkclose'] for r in L])
        m5 = S.fmean([r['mk5'] for r in L if r['mk5'] is not None]) if any(r['mk5'] is not None for r in L) else None
        m30 = S.fmean([r['mk30'] for r in L if r['mk30'] is not None]) if any(r['mk30'] is not None for r in L) else None
        speed[w] = {'n': len(L), 'grp': lab.get(w, 'other'), 'close': round(mc, 4), 'm5': None if m5 is None else round(m5, 4), 'm30': None if m30 is None else round(m30, 4)}
    json.dump({'generated': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': PA.CREDIT, 'window': WINDOW, 'accounts': speed},
              open(os.path.join(ROOT, 'data', 'pm_account_speed.json'), 'w'), separators=(',', ':'))
    pc = lambda v, d=2: '' if v is None else f'{v * 100:+.{d}f}%'
    se_txt = lambda x: '' if x['se'] is None else f"{x['se'] * 100:.2f}"
    L = ['# Sharp Polymarket accounts: copy test results', '',
         'Rules: docs/pm-accounts-copy-test.md (committed before this ran). Quotes from the Pendulum Flow orderbook archive '
         '(archive.pendulumflow.com, CC BY 4.0).', '',
         f"Games: {len(games)} ({sum(1 for g in games if g['sport'] == 'nfl')} NFL weeks 1-3, {sum(1 for g in games if g['sport'] == 'cfb')} college). "
         f"First $1k+ trades per account, game and side: {len(rows)} (sharp {len(sharp)}, usually losing {curve['dull']['n']}, other {curve['other']['n']}). "
         f"Labels from the NFL scorecard with {n_removed} test games taken out.", '',
         '## 1. Copying a sharp account at the ask, d minutes later (vs the close)', '',
         '| Delay | Copies | Games | Average vs close | SE | NFL | College |', '|---|---|---|---|---|---|---|']
    for d in COPY_D:
        x = res[d]
        L.append(f"| {d} min{' (pre-registered)' if d == PRIMARY else ''} | {x['n']} | {x['games']} | {pc(x['mean'])} | {se_txt(x)} | {pc(x['nfl'])} | {pc(x['cfb'])} |")
    L += ['', f"Verdict: **{'GO' if go else 'NO-GO'}** (rule: average at 15 minutes above zero by 2+ standard errors).", '',
          '## 2. How the market moves after their trade (mid of the side bought vs the price paid)', '',
          '| Accounts | Trades | Spread paid | 1 min | 5 min | 15 min | 30 min | 60 min | 120 min | Kickoff |', '|---|---|---|---|---|---|---|---|---|---|']
    for grp, nm in (('sharp', 'Sharp'), ('dull', 'Usually losing'), ('other', 'Everyone else')):
        c = curve[grp]
        L.append(f"| {nm} | {c['n']} | {pc(c['spread_paid'])} | " + ' | '.join(pc(c[f'mk{d}']) for d in MARK_D) + f" | {pc(c['mkclose'])} |")
    L += ['', 'Spread paid = their price against the mid at the moment of the trade (a taker pays about half the spread).',
          f"Account speed profiles: data/pm_account_speed.json ({len(speed)} accounts with 3+ test-window trades).", '']
    open(os.path.join(ROOT, 'docs', f'pm-accounts-copy-results{sfx}.md'), 'w').write('\n'.join(L) + '\n')
    json.dump({'go': go, 'copy': res, 'curve': curve, 'games': len(games), 'rows': len(rows), 'removed': n_removed},
              open(os.path.join(ROOT, 'data', f'pm_accounts_copy{sfx}.json'), 'w'), indent=1, default=str)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
