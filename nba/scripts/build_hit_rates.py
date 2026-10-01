#!/usr/bin/env python3
"""
Do players who "keep hitting this line" keep hitting it? The hit-rate test.

Betting apps lead with "8 of his last 10 over 24.5". This asks whether that is an edge, two ways, on every priced
line we have, using only games before the one being bet:

  1. Streaks. For each line, the player's hit rate against THAT line over his previous 5 / 10 / 20 games played and
     season to date. Does a hot or cold record beat the price?
  2. Consistent players. Does a player who beat his lines (hit more often than the price said) in the first half of a
     season keep doing it in the second half? If yes, the market is slow to learn him and that IS an edge.

Data: ESPN sportsbook main lines (ESPN BET / DraftKings) 2024-25 opening prices = the exploration set; untouched test
sets = ESPN 2025-26 (open, and the pre-tip close where we have it) and Kalshi 2025-26 at its 30-minute pre-tip VWAP.
Book prices are de-vigged (power) for "what the market said"; ROI is at the real price you would have paid.

Rule, fixed before running (same bar as every other signal):
  streak bet = OVER when the player hit today's line in 8+ of his last 10, UNDER when in 2 or fewer; GO = test-set ROI
  above zero with z >= 2 (per-game clustered) over 50+ games, on a test set it was not chosen on. The 8-of-10 cut is
  the apps' own headline, not tuned. Persistence: GO if the second-half residual of the top first-half quintile is
  above zero with z >= 2.

  python3 nba/scripts/build_hit_rates.py     -> data/hit_rates.json, docs/hit-rates.md
"""
import bisect, csv, datetime as dt, json, math, os, statistics, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw')
OUT_JSON = os.path.join(HERE, '..', 'data', 'hit_rates.json')
OUT_MD = os.path.join(HERE, '..', 'docs', 'hit-rates.md')
COLS = {'pts': ('points',), 'reb': ('rebounds',), 'ast': ('assists',), '3pm': ('three_point_field_goals_made',),
        'pra': ('points', 'rebounds', 'assists'), 'pr': ('points', 'rebounds'), 'pa': ('points', 'assists'), 'ra': ('rebounds', 'assists')}
WINDOWS = (5, 10, 20)


def imp(a):
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if abs(a) < 100:
        return None
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def devig(a, b):
    x, y = imp(a), imp(b)
    if not x or not y:
        return None
    lo, hi = 0.5, 3.0
    for _ in range(40):
        k = (lo + hi) / 2
        lo, hi = (k, hi) if x ** k + y ** k > 1 else (lo, k)
    return x ** ((lo + hi) / 2)


def payout(a):
    a = float(a)
    return 100 / -a if a < 0 else a / 100


def kal_fee(p):
    return math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100


def ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def load_box():
    """athlete -> sorted [(tip ts, season, {stat: value})] for games he played."""
    P = defaultdict(list)
    for s in (2024, 2025, 2026):
        for r in csv.DictReader(open(os.path.join(RAW, 'hoopr', f'player_box_{s}.csv'))):
            try:
                if r['did_not_play'] in ('TRUE', 'True', 'true') or not r['minutes'] or float(r['minutes']) <= 0:
                    continue
                v = {k: sum(float(r[c] or 0) for c in cs) for k, cs in COLS.items()}
                P[r['athlete_id']].append((ts(r['game_date_time']), s, v))
            except (ValueError, KeyError):
                continue
    for a in P:
        P[a].sort(key=lambda x: x[0])
    return P


def history(P, aid, tip, season, stat, line):
    """Hit counts against `line` over the previous games (strictly before tip)."""
    g = P.get(aid)
    if not g:
        return None
    i = bisect.bisect_left([x[0] for x in g], tip - 3600)
    prev = g[:i]
    out = {}
    for n in WINDOWS:
        if len(prev) >= n:
            out[n] = sum(x[2][stat] > line for x in prev[-n:])
    szn = [x for x in prev if x[1] == season]
    out['szn'] = (sum(x[2][stat] > line for x in szn), len(szn))
    return out


def real_main(po, pu):
    """A real main line: both sides between -200 and +200 and a normal hold (2-10%). ESPN's feed does not label the
    over, and some "main" rows are ladder rungs or swapped sides (over +275 / under -3000 on a player averaging 8
    assists). Those make any recent-form signal look like a huge edge, because the form simply detects the broken row:
    the first run without this filter showed +50-90% "edges"."""
    try:
        a, b = float(po), float(pu)
    except (TypeError, ValueError):
        return False
    if not (-200 <= a <= 200 and -200 <= b <= 200):
        return False
    return 1.02 <= imp(a) + imp(b) <= 1.10


def rows_espn(P):
    out = []
    for r in csv.DictReader(open(os.path.join(RAW, 'tables', 'props_espn.csv'))):
        if r['kind'] != 'main' or r['market'] not in COLS or r['played'] != '1' or r['actual'] == '':
            continue
        tip, season, actual = ts(r['tip']), int(r['season']), float(r['actual'])
        sets = [('open', float(r['line_open']), r['over_px_open'], r['under_px_open'])] if r['line_open'] else []
        if r['cur_is_pretip'] == '1' and r['line_cur']:
            sets.append(('close', float(r['line_cur']), r['over_px_cur'], r['under_px_cur']))
        for when, line, po, pu in sets:
            p = devig(po, pu)
            if p is None or line != line or not real_main(po, pu):
                continue
            h = history(P, r['athlete_id'], tip, season, r['market'], line)
            if not h:
                continue
            out.append({'src': f"espn{season}_{when}", 'gid': r['game_id'], 'aid': r['athlete_id'], 'player': r['player'], 'stat': r['market'],
                        'tip': tip, 'season': season, 'line': line, 'p': p, 'over': actual > line, 'push': actual == line,
                        'po': po, 'pu': pu, 'h': h})
    return out


def rows_kalshi(P):
    out = []
    for r in csv.DictReader(open(os.path.join(RAW, 'tables', 'props_kalshi.csv'))):
        if r['market'] not in COLS or r['played'] != '1' or r['result'] not in ('yes', 'no'):
            continue
        px = r['yes_vwap30_pretip'] or r['yes_last_pretip']
        try:
            p = float(px)
        except ValueError:
            continue
        if not 0.03 <= p <= 0.97:
            continue
        line, tip = float(r['strike']), float(r['tip_ts'])
        h = history(P, r['athlete_id'], tip, 2026, r['market'], line)
        if not h:
            continue
        out.append({'src': 'kalshi2026', 'gid': r['game_id'], 'aid': r['athlete_id'], 'player': r['player'], 'stat': r['market'],
                    'tip': tip, 'season': 2026, 'line': line, 'p': p, 'over': r['result'] == 'yes', 'push': False, 'h': h})
    return out


def bet_result(r, side):
    """Profit per 1 staked on `side` ('over' / 'under') at the price actually offered."""
    won = r['over'] if side == 'over' else not r['over']
    if r['push']:
        return 0.0
    if r['src'].startswith('kalshi'):
        c = (r['p'] if side == 'over' else 1 - r['p'])
        c += kal_fee(c)
        return (1 - c) / c if won else -1.0
    a = r['po'] if side == 'over' else r['pu']
    return payout(a) if won else -1.0


def summarize(bets):
    """bets [(gid, profit)] -> n, games, roi, per-game clustered z."""
    if not bets:
        return {'n': 0, 'games': 0, 'roi': None, 'z': None}
    by = defaultdict(float)
    for g, x in bets:
        by[g] += x
    n, G = len(bets), len(by)
    roi = sum(x for _, x in bets) / n
    v = list(by.values())
    sd = statistics.pstdev(v) if G > 1 else 0
    z = (sum(v) / G) / (sd / math.sqrt(G)) if sd else 0
    return {'n': n, 'games': G, 'roi': round(roi, 4), 'z': round(z, 2)}


def analyse(rows):
    res = {}
    # 1. what an L10 record says vs what happened vs what the market said
    buckets = [(0, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
    cal = []
    for lo, hi in buckets:
        rr = [r for r in rows if 10 in r['h'] and lo <= r['h'][10] <= hi and not r['push']]
        if rr:
            cal.append({'l10': f'{lo}-{hi} of 10', 'n': len(rr), 'streak_rate': round(statistics.mean(r['h'][10] / 10 for r in rr), 3),
                        'market': round(statistics.mean(r['p'] for r in rr), 3), 'actual': round(statistics.mean(r['over'] for r in rr), 3)})
    res['calibration'] = cal
    # 2. does the streak add anything to the price? residual (outcome - price) on (L10 rate - price)
    rr = [r for r in rows if 10 in r['h'] and not r['push']]
    if len(rr) > 100:
        xs = [r['h'][10] / 10 - r['p'] for r in rr]
        ys = [r['over'] - r['p'] for r in rr]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        resid = [y - my - b * (x - mx) for x, y in zip(xs, ys)]
        se = math.sqrt(sum(e * e for e in resid) / (len(rr) - 2) / sxx)
        res['slope'] = {'n': len(rr), 'b': round(b, 4), 't': round(b / se, 2), 'bias': round(my, 4)}
    # 3. the apps' bet: 8+ of 10 -> over, 2 or fewer -> under; plus each window's version
    rules = {}
    for n in WINDOWS:
        hot, cold = math.ceil(0.8 * n), math.floor(0.2 * n)
        rules[f'L{n} over (hit {hot}+ of {n})'] = summarize([(r['gid'], bet_result(r, 'over')) for r in rows if n in r['h'] and r['h'][n] >= hot])
        rules[f'L{n} under (hit {cold} or fewer of {n})'] = summarize([(r['gid'], bet_result(r, 'under')) for r in rows if n in r['h'] and r['h'][n] <= cold])
    rules['Season over (80%+, 10+ games)'] = summarize([(r['gid'], bet_result(r, 'over')) for r in rows if r['h']['szn'][1] >= 10 and r['h']['szn'][0] >= 0.8 * r['h']['szn'][1]])
    rules['Season under (20% or less, 10+ games)'] = summarize([(r['gid'], bet_result(r, 'under')) for r in rows if r['h']['szn'][1] >= 10 and r['h']['szn'][0] <= 0.2 * r['h']['szn'][1]])
    # the streak AND the price disagree by 15+ points: the strongest form of the claim
    rules['L10 over, 15+ pts above price'] = summarize([(r['gid'], bet_result(r, 'over')) for r in rows if 10 in r['h'] and r['h'][10] / 10 - r['p'] >= 0.15])
    rules['L10 under, 15+ pts below price'] = summarize([(r['gid'], bet_result(r, 'under')) for r in rows if 10 in r['h'] and r['p'] - r['h'][10] / 10 >= 0.15])
    rules['Baseline: every over'] = summarize([(r['gid'], bet_result(r, 'over')) for r in rows])
    rules['Baseline: every under'] = summarize([(r['gid'], bet_result(r, 'under')) for r in rows])
    res['rules'] = rules
    # same price, streak or not: does the record add anything once the price is held fixed? (venue biases cancel)
    B = [(0, .15), (.15, .3), (.3, .5), (.5, .7), (.7, .85), (.85, 1.01)]
    def matched(side, pick):
        d, n = 0.0, 0
        for lo, hi in B:
            rr = [r for r in rows if 10 in r['h'] and lo <= r['p'] < hi]
            a = [bet_result(r, side) for r in rr if pick(r)]
            b = [bet_result(r, side) for r in rr if not pick(r)]
            if len(a) >= 30 and len(b) >= 30:              # thin buckets (a few long shots) would swamp the average
                d += len(a) * (statistics.mean(a) - statistics.mean(b))
                n += len(a)
        return {'diff': round(d / n, 4) if n else None, 'n': n}
    res['same_price'] = {'cold_under': matched('under', lambda r: r['h'][10] <= 2), 'hot_over': matched('over', lambda r: r['h'][10] >= 8)}
    return res


def persistence(rows):
    """Per player x stat: average (outcome - price) in the first half of the season by tip, vs the second half."""
    rows = [r for r in rows if not r['push']]
    if not rows:
        return None
    cut = statistics.median(r['tip'] for r in rows)
    acc = defaultdict(lambda: [[], []])
    for r in rows:
        acc[(r['aid'], r['stat'])][r['tip'] >= cut].append(r)
    pairs = [(statistics.mean(x['over'] - x['p'] for x in a), b, k) for k, (a, b) in acc.items() if len(a) >= 15 and len(b) >= 15]
    if len(pairs) < 20:
        return None
    pairs.sort(key=lambda x: x[0])
    q = len(pairs) // 5
    top, bot = pairs[-q:], pairs[:q]
    second = lambda grp, side: summarize([(x['gid'], bet_result(x, side)) for _, b, _ in grp for x in b])
    x1 = [a for a, _, _ in pairs]
    x2 = [statistics.mean(x['over'] - x['p'] for x in b) for _, b, _ in pairs]
    m1, m2 = statistics.mean(x1), statistics.mean(x2)
    corr = sum((a - m1) * (b - m2) for a, b in zip(x1, x2)) / math.sqrt(sum((a - m1) ** 2 for a in x1) * sum((b - m2) ** 2 for b in x2))
    return {'players': len(pairs), 'corr': round(corr, 3),
            'top_first': round(statistics.mean(a for a, _, _ in top), 3), 'top_second': round(statistics.mean(statistics.mean(x['over'] - x['p'] for x in b) for _, b, _ in top), 3),
            'bot_first': round(statistics.mean(a for a, _, _ in bot), 3), 'bot_second': round(statistics.mean(statistics.mean(x['over'] - x['p'] for x in b) for _, b, _ in bot), 3),
            'bet_top_over': second(top, 'over'), 'bet_bot_under': second(bot, 'under')}


def main():
    P = load_box()
    print(f'box: {len(P):,} players', flush=True)
    rows = rows_espn(P) + rows_kalshi(P)
    sets = defaultdict(list)
    for r in rows:
        sets[r['src']].append(r)
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'sets': {}}
    for name in sorted(sets):
        rs = sets[name]
        a = analyse(rs)
        a['n'] = len(rs)
        a['persistence'] = persistence(rs)
        res['sets'][name] = a
        print(f"{name}: {len(rs):,} lines, slope t {a.get('slope', {}).get('t')}", flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


NAMES = {'espn2025_open': 'Sportsbook 2024-25, opening line (exploration set)', 'espn2026_open': 'Sportsbook 2025-26, opening line (test)',
         'espn2026_close': 'Sportsbook 2025-26, pre-tip close (test)', 'kalshi2026': 'Kalshi 2025-26, 30-min pre-tip VWAP (test)'}


def write_md(res):
    L = ['# Do players who keep hitting a line keep hitting it?', '',
         f"Generated {res['generated']} by `nba/scripts/build_hit_rates.py`. Every line priced before tip; the player's record",
         'against that same line from games before it only. Rule fixed first: bet OVER at 8+ of last 10, UNDER at 2 or fewer;',
         'GO = test-set ROI > 0 with z >= 2 over 50+ games.', '']
    for name, a in res['sets'].items():
        L += [f"## {NAMES.get(name, name)}", '', f"{a['n']:,} lines.", '',
              '| Last 10 vs this line | Lines | Streak said | Market said | Actually hit |', '|---|---|---|---|---|']
        for c in a['calibration']:
            L.append(f"| {c['l10']} | {c['n']:,} | {c['streak_rate']:.0%} | {c['market']:.1%} | {c['actual']:.1%} |")
        s = a.get('slope')
        if s:
            L += ['', f"Does the streak add to the price? outcome - price = a + b x (L10 rate - price): b = {s['b']} (t = {s['t']}), n = {s['n']:,}. "
                  f"Average outcome - price {s['bias']:+.3f}.", '']
        L += ['| Bet | Bets | Games | ROI | z |', '|---|---|---|---|---|']
        for k, v in a['rules'].items():
            L.append(f"| {k} | {v['n']:,} | {v['games']} | {'' if v['roi'] is None else format(v['roi'], '+.1%')} | {v['z']} |")
        sp = a.get('same_price')
        if sp and sp['cold_under']['diff'] is not None:
            L += ['', f"At the same price: 2-or-fewer unders return {sp['cold_under']['diff']:+.1%} more than other unders ({sp['cold_under']['n']:,} bets); "
                  f"8+ of 10 overs {sp['hot_over']['diff']:+.1%} vs other overs ({sp['hot_over']['n']:,} bets)."]
        p = a.get('persistence')
        if p:
            L += ['', f"Consistent players ({p['players']} player-stats with 15+ lines in each half): first-half vs second-half beat-the-price "
                  f"correlation {p['corr']}. Top fifth: {p['top_first']:+.3f} then {p['top_second']:+.3f}; bottom fifth: {p['bot_first']:+.3f} then "
                  f"{p['bot_second']:+.3f}. Betting the top fifth's overs in the second half: ROI {p['bet_top_over']['roi']:+.1%} (z {p['bet_top_over']['z']}); "
                  f"the bottom fifth's unders: {p['bet_bot_under']['roi']:+.1%} (z {p['bet_bot_under']['z']})."]
        L.append('')
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
