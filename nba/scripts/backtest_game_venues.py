#!/usr/bin/env python3
"""
Which market is sharpest on NBA game lines, and does the game model add to it? The pre-registered test in
nba/docs/game-venues-test.md.

2025-26 season, one row per game (home team's chance), only games with all three closes:
  Polymarket  last minute of the home moneyline token at or before tip (clob.polymarket.com/prices-history), cached
  Kalshi      pre-tip VWAP / last from the Kalshi backfill (as backtest_game_vs_kalshi.py)
  Sportsbook  ESPN BET's closing moneyline, vig removed (raw/tables/game_lines.csv)
  Model       the game model's home win chance at 1 PM ET (walk-forward, as backtest_game_vs_kalshi.py)
A few Polymarket closes are cross-checked against the Pendulum Flow orderbook archive with --check.

Usage: python3 nba/scripts/backtest_game_venues.py [--check N]   -> nba/docs/game-venues-results.md, nba/data/game_venues.json
"""
import argparse, csv, datetime as dt, json, math, os, random, statistics as S, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nba_common as C
import build_game_model as GM
from backfill_kalshi import TEAM
from backtest_game_vs_kalshi import load, price, phi

ROOT = os.path.join(HERE, '..')
CACHE = os.path.join(ROOT, 'raw', 'polymarket')
SEASON = 2026
SPLIT = dt.date(2026, 2, 1)
B = 2000


def curl_json(url):
    p = subprocess.run(['curl', '-s', '--compressed', '--max-time', '60', url], capture_output=True, text=True)
    try:
        return json.loads(p.stdout, strict=False)
    except ValueError:
        return None


def nick_code(name):
    """Polymarket outcome name ("Knicks", "Trail Blazers") -> team code, from nba_common.TEAM_BY_NAME."""
    k = (name or '').replace(' ', '').lower()
    return next((c for full, c in C.TEAM_BY_NAME.items() if k and full.lower().endswith(k)), None)


def pm_games():
    """Polymarket NBA game moneylines for the season: (date, away, home) -> (tip, home token, away token)."""
    p = os.path.join(CACHE, 'games_2026.json')
    if os.path.exists(p):
        return {tuple(k.split('|')): v for k, v in json.load(open(p)).items()}
    out = {}
    for off in range(0, 6000, 100):
        E = curl_json(f'https://gamma-api.polymarket.com/events?series_id=10345&closed=true&limit=100&offset={off}'
                      f'&end_date_min=2025-10-15T00:00:00Z&end_date_max=2026-06-30T00:00:00Z') or []
        for e in E:
            parts = (e.get('slug') or '').split('-')            # nba-<away>-<home>-YYYY-MM-DD
            m = next((m for m in e.get('markets') or [] if m.get('sportsMarketType') == 'moneyline'), None)
            if len(parts) != 6 or not m:
                continue
            away, home = (TEAM.get(x.upper(), x.upper()) for x in parts[1:3])
            try:
                toks, outs = json.loads(m['clobTokenIds']), json.loads(m['outcomes'])
                tip = dt.datetime.fromisoformat((e.get('startTime') or e['endDate']).replace('Z', '+00:00')).timestamp()
            except (KeyError, ValueError):
                continue
            codes = [nick_code(o) for o in outs]                  # the home token by name, not by position
            if home not in codes or away not in codes:
                continue
            out[('-'.join(parts[3:]), away, home)] = [tip, toks[codes.index(home)], toks[codes.index(away)], outs]
        if len(E) < 100:
            break
    os.makedirs(CACHE, exist_ok=True)
    json.dump({'|'.join(k): v for k, v in out.items()}, open(p, 'w'))
    return out


def pm_close(tip, tok):
    p = os.path.join(CACHE, f'close_{tok[:16]}.json')
    if os.path.exists(p):
        return json.load(open(p))
    h = (curl_json(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={int(tip) - 3600}&endTs={int(tip)}&fidelity=1') or {}).get('history') or []
    pre = [x for x in h if x['t'] <= tip]
    v = pre[-1]['p'] if pre and tip - pre[-1]['t'] <= 1800 else None
    json.dump(v, open(p, 'w'))
    return v


def am_p(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if abs(a) < 100:
        return None
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


def ll(p, y):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def paired_se(rows, f):
    rnd, vals = random.Random(5), []
    for _ in range(B):
        smp = [rows[rnd.randrange(len(rows))] for _ in rows]
        vals.append(S.fmean(f(r) for r in smp))
    return S.pstdev(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', type=int, default=0)
    a = ap.parse_args()
    # model, as backtest_game_vs_kalshi.py
    P = dict(GM.DEFAULT, **json.load(open(GM.OUT_JSON))['params'])
    box = C.player_games(GM.WARM + GM.TUNE + GM.TEST)
    inj = C.InjuryAsOf(GM.TEST, C.player_index(box))
    _, recs = GM.run(P, GM.WARM + GM.TUNE + GM.TEST, box, C.closing_lines(), inj, record_from=GM.TEST[0])
    sigma = json.load(open(GM.OUT_JSON))['tune_mae'][0] * math.sqrt(math.pi / 2)
    by_gid = {r['g']['game_id']: r for r in recs if r['g']['season'] == SEASON}
    # Kalshi pre-tip, home team
    mk, am, pre = load('KXNBAGAME')
    kal = {}
    for t, m in mk.items():
        g = by_gid.get((am.get(t) or {}).get('game_id'))
        team = TEAM.get(t.rsplit('-', 1)[1], t.rsplit('-', 1)[1])
        if g and team == g['g']['home']:
            kal[g['g']['game_id']] = price(pre.get(t), 'pretip')
    # sportsbook close
    book = {}
    for r in csv.DictReader(open(os.path.join(C.RAW, 'tables', 'game_lines.csv'))):
        h, w = am_p(r['ml_home_close']), am_p(r['ml_away_close'])
        if r['season'] == str(SEASON) and h and w:
            book[int(r['game_id'])] = (h / (h + w), r['home'], r['away'], r['tip'], float(r['home_score']) > float(r['away_score']))
    # Polymarket close, matched by ET date and teams
    PG = pm_games()
    want = []
    for gid, (pb, home, away, tip, won) in book.items():
        if gid not in by_gid or gid not in kal or kal[gid] is None:
            continue
        t0 = dt.datetime.fromisoformat(tip.replace('Z', '+00:00'))
        hit = None
        for d in (t0 - dt.timedelta(hours=8), t0 - dt.timedelta(hours=3), t0):
            hit = PG.get((d.date().isoformat(), away, home))
            if hit:
                break
        if hit:
            want.append((gid, hit))
    with ThreadPoolExecutor(8) as ex:
        closes = list(ex.map(lambda w: pm_close(w[1][0], w[1][1]), want))
    rows = []
    for (gid, hit), pm in zip(want, closes):
        pb, home, away, tip, won = book[gid]
        if pm is None or not (0.01 < pm < 0.99):
            continue
        r = by_gid[gid]
        rows.append({'gid': gid, 'date': tip[:10], 'pm': pm, 'kal': kal[gid], 'book': pb, 'model': phi(r['am'][0] / sigma), 'y': 1 if won else 0,
                     'tip': hit[0], 'tok': hit[1], 'home': home, 'away': away})
    flips = [r for r in rows if abs(r['pm'] - r['book']) > 0.35]       # reported only: big disagreements
    V = ('pm', 'kal', 'book')
    NAME = {'pm': 'Polymarket', 'kal': 'Kalshi', 'book': 'Sportsbook (ESPN BET)'}
    lls = {v: S.fmean(ll(r[v], r['y']) for r in rows) for v in V}
    brier = {v: S.fmean((r[v] - r['y']) ** 2 for r in rows) for v in V}
    pairs = {}
    for x in V:
        for y in V:
            if x < y:
                d = S.fmean(ll(r[x], r['y']) - ll(r[y], r['y']) for r in rows)
                pairs[f'{x}-{y}'] = (d, paired_se(rows, lambda r: ll(r[x], r['y']) - ll(r[y], r['y'])))
    sharp = min(V, key=lambda v: lls[v])
    beats_book = {v: (lambda d, se: d <= -2 * se)(*pairs[f'{min(v, "book")}-{max(v, "book")}']) if v < 'book' else
                     (lambda d, se: -d <= -2 * se)(*pairs[f'book-{v}']) for v in ('pm', 'kal')}
    # model blend on the sharpest venue: fit w before Feb 1, score after
    fit = [r for r in rows if dt.date.fromisoformat(r['date']) < SPLIT]
    test = [r for r in rows if dt.date.fromisoformat(r['date']) >= SPLIT]
    best_w = min((w / 100 for w in range(0, 101)), key=lambda w: S.fmean(ll((1 - w) * r[sharp] + w * r['model'], r['y']) for r in fit))
    gain = S.fmean(ll((1 - best_w) * r[sharp] + best_w * r['model'], r['y']) - ll(r[sharp], r['y']) for r in test) if test else None
    gain_se = paired_se(test, lambda r: ll((1 - best_w) * r[sharp] + best_w * r['model'], r['y']) - ll(r[sharp], r['y'])) if test else None
    model_go = gain is not None and best_w > 0 and gain <= -2 * gain_se
    chk = []
    if a.check:
        sys.path.insert(0, os.path.join(ROOT, '..', 'scripts'))
        import duckdb
        c = duckdb.connect(); c.execute('INSTALL httpfs; LOAD httpfs;')
        for r in [r for r in rows if r['date'] >= '2026-04-14'][:a.check]:
            hr = dt.datetime.fromtimestamp(r['tip'] - 60, dt.timezone.utc)
            u = f"https://archive.pendulumflow.com/pmxt/v2/polymarket_orderbook_{hr.strftime('%Y-%m-%dT%H')}.parquet"
            q = c.execute(f"SELECT best_bid, best_ask FROM read_parquet('{u}') WHERE asset_id = '{r['tok']}' AND event_type = 'price_change' "
                          f"AND epoch_ms(timestamp) < {int(r['tip'] * 1000)} AND best_bid IS NOT NULL ORDER BY timestamp DESC LIMIT 1").fetchone()
            chk.append((r['gid'], r['date'], r['away'] + '@' + r['home'], r['pm'], None if not q else round((float(q[0]) + float(q[1])) / 2, 4)))
    pc = lambda v: f'{v:.4f}'
    L = ['# Which market is sharpest on NBA game lines: results', '',
         'Rules: nba/docs/game-venues-test.md (committed before this ran). 2025-26 season, every game with a Polymarket, Kalshi and '
         'ESPN BET closing moneyline; home team\'s chance; lower is better.', '',
         f'Games: {len(rows)}. Home token matched by team name. Games where Polymarket and the sportsbook closed 35+ points apart: {len(flips)} (kept).', '',
         '## 1. Sharpness at the close', '', '| Venue | Log loss | Brier |', '|---|---|---|']
    for v in sorted(V, key=lambda v: lls[v]):
        L.append(f'| {NAME[v]} | {pc(lls[v])} | {pc(brier[v])} |')
    L += ['', '| Comparison | Log-loss difference | SE |', '|---|---|---|']
    for k, (d, se) in pairs.items():
        x, y = k.split('-')
        L.append(f'| {NAME[x]} minus {NAME[y]} | {d:+.4f} | {se:.4f} |')
    L += ['', f"Decision rule: a venue moves ahead of the sportsbook in the Slate's fallback order only if its log loss is lower by 2+ SE. "
          f"Polymarket: **{'yes' if beats_book['pm'] else 'no'}**. Kalshi: **{'yes' if beats_book['kal'] else 'no'}**.", '',
          f'## 2. Does the game model add to {NAME[sharp]}?', '',
          f"Blend weight fit on {len(fit)} games before Feb 1: w = {best_w:.2f}. On the {len(test)} games after: log-loss change {gain:+.4f} (SE {gain_se:.4f}). "
          f"Verdict: **{'GO' if model_go else 'NO-GO'}** (rule: lower by 2+ SE).", '']
    if chk:
        L += ['## Cross-check against the orderbook archive', '', 'Polymarket price-history close vs the archive\'s mid one minute before tip (2026 playoff games):', '',
              '| Game | Date | Price history | Archive mid |', '|---|---|---|---|'] + [f'| {g} | {d} | {p:.3f} | {"" if m is None else f"{m:.3f}"} |' for _, d, g, p, m in chk] + ['']
    open(os.path.join(ROOT, 'docs', 'game-venues-results.md'), 'w').write('\n'.join(L) + '\n')
    json.dump({'n': len(rows), 'logloss': lls, 'brier': brier, 'pairs': pairs, 'sharpest': sharp, 'beats_book': beats_book,
               'model': {'w': best_w, 'gain': gain, 'se': gain_se, 'go': model_go, 'fit': len(fit), 'test': len(test)}, 'check': chk},
              open(os.path.join(ROOT, 'data', 'game_venues.json'), 'w'), indent=1)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
