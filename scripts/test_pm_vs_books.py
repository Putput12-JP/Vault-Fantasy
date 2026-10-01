#!/usr/bin/env python3
"""
Polymarket vs the sportsbooks on NFL moneylines: the pre-registered test in docs/pm-vs-books-test.md.

Inputs
  sportsbooks   every committed data/lineup-feed.json from the "refresh Lineup projections feed" job (the only job that
                fetches book lines), read from git; a snapshot whose moneylines did not change is dropped (the earliest
                copy is the observation). Observation time = the file's `generated` stamp.
  Polymarket    moneyline trade tapes from the Pendulum Flow archive (scripts/pm_archive.py tape), cached per hour.
                Price at t = size-weighted average of trades in the 15 minutes before t, home token, with away-token
                trades read as 1 - price.
  results       ESPN scoreboard finals (reported, not used for the verdict).

Measures (fixed in the doc before running)
  1. gap = Polymarket home chance - retail consensus (median no-vig of the US retail books). Slope of the consensus
     move to its close on the gap (beta_books) vs slope of Polymarket's move to its close on minus the gap (beta_pm).
     Polymarket leads if beta_books > beta_pm and beta_books >= 2 SE above zero (bootstrap over games).
  2. Bet the side Polymarket favors at any retail book 3+ points away, first trigger per game, book and side.
     CLV vs Pinnacle's no-vig close; GO if the mean is >= 2 SE above zero (bootstrap over games).

Usage: python3 scripts/test_pm_vs_books.py --cache <tape cache> [--out docs/pm-vs-books-results.md]
"""
import argparse, datetime as dt, glob, gzip, json, os, random, statistics as S, subprocess, sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RETAIL = ['DraftKings', 'FanDuel', 'BetMGM', 'Caesars', 'bet365', 'Fanatics', 'BetRivers', 'Hard Rock Bet']
NICK = {'Cardinals': 'ARI', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Bills': 'BUF', 'Panthers': 'CAR', 'Bears': 'CHI', 'Bengals': 'CIN',
        'Browns': 'CLE', 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB', 'Texans': 'HOU', 'Colts': 'IND',
        'Jaguars': 'JAX', 'Chiefs': 'KC', 'Chargers': 'LAC', 'Rams': 'LAR', 'Raiders': 'LV', 'Dolphins': 'MIA', 'Vikings': 'MIN',
        'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG', 'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA',
        '49ers': 'SF', 'Buccaneers': 'TB', 'Titans': 'TEN', 'Commanders': 'WAS'}
WIN = 15 * 60
THR, ALT_THR = 0.03, (0.02, 0.04, 0.05)
B = 2000


def am_p(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if abs(a) < 100:
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def book_snapshots(since='2026-09-01', until='2026-10-01'):
    log = subprocess.run(['git', '-C', ROOT, 'log', f'--since={since}', f'--until={until}', '--reverse', '--format=%H %s', '--', 'data/lineup-feed.json'],
                         capture_output=True, text=True).stdout.split('\n')
    out, last = [], None
    for line in filter(None, log):
        h, msg = line.split(' ', 1)
        if not msg.startswith('data: refresh Lineup'):
            continue
        try:
            d = json.loads(subprocess.run(['git', '-C', ROOT, 'show', f'{h}:data/lineup-feed.json'], capture_output=True, text=True).stdout)
        except ValueError:
            continue
        if not (d.get('vegas_meta') or {}).get('live_source') or not d.get('vegas_games'):
            continue
        gs = []
        for g in d['vegas_games']:
            ml = {q['book']: (q.get('away'), q.get('home')) for q in (g.get('ml') or {}).get('quotes', [])}
            if g.get('commence'):
                gs.append((g['away'], g['home'], ts(g['commence']), ml))
        key = json.dumps([[a, h_, m] for a, h_, _, m in gs], sort_keys=True)
        if key == last:
            continue
        last = key
        out.append((ts(d['generated']), gs))
    return out


def novig(ml):
    pa, ph = am_p(ml[0]), am_p(ml[1])
    return ph / (pa + ph) if pa and ph else None


def pm_series(cache):
    """(away, home, kickoff) -> sorted [(t, home price, size)] from the cached moneyline tapes."""
    G = json.load(open(os.path.join(cache, 'nfl_games.json')))
    tok = {}
    for g in G:
        m = next(m for m in g['markets'] if m['type'] == 'moneyline')
        teams = [NICK.get(o) for o in m['outcomes']]
        if None in teams:
            continue
        tok[m['cid']] = (g['kickoff'], teams, m['tokens'])
    rows = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(cache, 'nfl_*.json.gz'))):
        for cid, aid, tm, price, size in json.load(gzip.open(p, 'rt')):
            if cid in tok:
                rows[cid].append((tm / 1000, aid, price, size))
    out = {}
    for cid, R in rows.items():
        ko, teams, toks = tok[cid]
        out[(ko, frozenset(teams))] = (teams, toks, sorted(R))
    return out


def pm_at(series, home, t):
    teams, toks, R = series
    hi = toks[teams.index(home)]
    w = [(p if a == hi else 1 - p, s) for (tm, a, p, s) in R if t - WIN <= tm < t]
    tot = sum(s for _, s in w)
    return sum(p * s for p, s in w) / tot if tot > 0 else None


def finals(dates):
    F = {}
    for d in sorted(dates):
        js = json.loads(subprocess.run(['curl', '-s', f'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={d}'], capture_output=True, text=True).stdout or '{}')
        for e in js.get('events', []):
            c = e['competitions'][0]
            if not c['status']['type'].get('completed'):
                continue
            sc = {x['homeAway']: (x['team']['abbreviation'], float(x.get('score') or 0)) for x in c['competitors']}
            ab = lambda x: {'WSH': 'WAS', 'LA': 'LAR', 'JAC': 'JAX'}.get(x, x)
            F[(ab(sc['away'][0]), ab(sc['home'][0]))] = sc['home'][1] > sc['away'][1]
    return F


def boot(by_game, stat, n=B, seed=7):
    keys = list(by_game)
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        smp = [x for _ in keys for x in by_game[rnd.choice(keys)]]
        v = stat(smp)
        if v is not None:
            vals.append(v)
    return S.pstdev(vals) if len(vals) > 10 else float('nan')


def slope(pairs):
    if len(pairs) < 5:
        return None
    xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = S.fmean(xs), S.fmean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx if vx else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs', 'pm-vs-books-results.md'))
    a = ap.parse_args()
    snaps = book_snapshots()
    PM = pm_series(a.cache)
    # every game: its book snapshots before kickoff, Polymarket's series, and the closes
    # one game = one Polymarket moneyline; a snapshot joins it by teams and a kickoff within 3 hours (the feed's
    # kickoff can shift between snapshots, which must not split a game in two)
    games = defaultdict(list)
    for t, gs in snaps:
        for away, home, ko, ml in gs:
            key = next(((k, tm) for (k, tm) in PM if tm == frozenset([away, home]) and abs(k - ko) < 3 * 3600), None)
            if key and t < key[0]:
                games[(away, home, key)].append((t, ml))
    obs, bets, matched, no_pin = [], [], 0, 0
    for (away, home, key), L in games.items():
        ser, ko = PM[key], key[0]
        pm_close = pm_at(ser, home, ko)
        last = L[-1][1]
        pin_close = novig(last['Pinnacle']) if 'Pinnacle' in last else None
        cons = lambda ml: (lambda v: S.median(v) if len(v) >= 3 else None)([x for x in (novig(ml[b]) for b in RETAIL if b in ml) if x is not None])
        cons_close = cons(last)
        if pm_close is None or cons_close is None:
            continue
        matched += 1
        no_pin += pin_close is None
        gk = f'{away}@{home}'
        seen, prev = set(), {}
        for t, ml in L:
            pm, c = pm_at(ser, home, t), cons(ml)
            if pm is not None and c is not None:
                obs.append({'g': gk, 'gap': pm - c, 'd_books': cons_close - c, 'd_pm': pm_close - pm})
            if pm is None:
                prev = ml; continue
            for b in RETAIL:
                if b not in ml:
                    continue
                nv = novig(ml[b])
                if nv is None:
                    continue
                side = 'home' if pm > nv else 'away'
                gap = abs(pm - nv)
                cost = am_p(ml[b][1] if side == 'home' else ml[b][0])
                moved = b in prev and prev[b] != ml[b]
                for th in (THR,) + ALT_THR:
                    k = (th, b, side)
                    if gap >= th and k not in seen and cost:
                        seen.add(k)
                        ps = lambda p: None if p is None else (p if side == 'home' else 1 - p)
                        bets.append({'g': gk, 'th': th, 'book': b, 'side': side, 'gap': gap, 'cost': cost, 'moved': moved, 'home': home, 'away': away, 'ko': ko,
                                     'clv_pin': ps(pin_close) / cost - 1 if pin_close is not None else None, 'clv_pm': ps(pm_close) / cost - 1})
            prev = ml
    # measure 1
    byg = defaultdict(list)
    for o in obs:
        byg[o['g']].append(o)
    b_books = slope([(o['gap'], o['d_books']) for o in obs])
    b_pm = slope([(-o['gap'], o['d_pm']) for o in obs])
    se_books = boot(byg, lambda s: slope([(o['gap'], o['d_books']) for o in s]))
    se_pm = boot(byg, lambda s: slope([(-o['gap'], o['d_pm']) for o in s]))
    lead = b_books is not None and b_pm is not None and b_books > b_pm and b_books >= 2 * se_books
    # measure 2
    F = finals({dt.datetime.fromtimestamp(b['ko'] - 6 * 3600, dt.timezone.utc).strftime('%Y%m%d') for b in bets})
    res = {}
    for th in (THR,) + ALT_THR:
        X = [b for b in bets if b['th'] == th and b['clv_pin'] is not None]
        by = defaultdict(list)
        for x in X:
            by[x['g']].append(x)
        mean = lambda s, k='clv_pin': S.fmean([x[k] for x in s]) if s else None
        won = [(F.get((x['away'], x['home'])) == (x['side'] == 'home')) for x in X if (x['away'], x['home']) in F]
        pnl = [((1 - x['cost']) / x['cost'] if (F[(x['away'], x['home'])] == (x['side'] == 'home')) else -1) for x in X if (x['away'], x['home']) in F]
        res[th] = {'n': len(X), 'games': len(by), 'clv': mean(X), 'se': boot(by, lambda s: mean(s)), 'clv_pm': mean(X, 'clv_pm'),
                   'moved': S.fmean([x['moved'] for x in X]) if X else None, 'w': sum(won), 'l': len(won) - sum(won), 'roi': S.fmean(pnl) if pnl else None,
                   'books': {bk: len([x for x in X if x['book'] == bk]) for bk in RETAIL}}
    r = res[THR]
    go = r['clv'] is not None and r['se'] == r['se'] and r['clv'] >= 2 * r['se'] and r['clv'] > 0
    pc = lambda v, d=1: '' if v is None else f'{v * 100:+.{d}f}%'
    L = ['# Polymarket vs the sportsbooks: results', '', 'Rules: docs/pm-vs-books-test.md (committed before this ran). NFL 2026, every game played through Sept 29 (weeks 1-3), moneylines. '
         'Polymarket from the Pendulum Flow orderbook archive (archive.pendulumflow.com, CC BY 4.0).', '',
         f"Games matched: {matched} ({no_pin} without a Pinnacle close). Sportsbook snapshots: {len(snaps)} fetched, changed snapshots. Game-moments with both prices: {len(obs)}.", '',
         '## 1. Who closes the gap', '',
         f"- Books move toward Polymarket: beta_books = **{b_books:.2f}** (SE {se_books:.2f})",
         f"- Polymarket moves toward the books: beta_pm = **{b_pm:.2f}** (SE {se_pm:.2f})",
         f"- Verdict: **{'Polymarket leads' if lead else 'Polymarket does not lead'}** (rule: beta_books > beta_pm and beta_books >= 2 SE above zero)", '',
         '## 2. Betting the book side Polymarket favors (3+ points apart)', '',
         '| Threshold | Bets | Games | CLV vs Pinnacle close | SE | CLV vs Polymarket close | Book had just moved | Record | Return |', '|---|---|---|---|---|---|---|---|---|']
    for th in (THR,) + ALT_THR:
        x = res[th]
        L.append(f"| {th * 100:.0f} pts{' (pre-registered)' if th == THR else ''} | {x['n']} | {x['games']} | {pc(x['clv'], 2)} | {x['se'] * 100:.2f} | {pc(x['clv_pm'], 2)} | {pc(x['moved'], 0).lstrip('+')} | {x['w']}-{x['l']} | {pc(x['roi'])} |")
    L += ['', f"Verdict: **{'GO' if go else 'NO-GO'}** (rule: mean CLV vs Pinnacle's close >= 2 SE above zero at 3 points).", '',
          'By book (3 points): ' + ', '.join(f'{k} {v}' for k, v in r['books'].items() if v), '']
    open(a.out, 'w').write('\n'.join(L) + '\n')
    json.dump({'lead': lead, 'beta_books': b_books, 'beta_pm': b_pm, 'se_books': se_books, 'se_pm': se_pm, 'bets': res, 'go': go, 'matched': matched, 'obs': len(obs)},
              open(os.path.join(ROOT, 'data', 'pm_vs_books.json'), 'w'), indent=1, default=str)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
