#!/usr/bin/env python3
"""
Steam first look: the pre-registered rule in nba/docs/steam-continuation.md, applied to the alert files on nba-data.

  python3 nba/scripts/steam_first_look.py [nba-data checkout]        # regular season: counts only until 100 games
  python3 nba/scripts/steam_first_look.py [nba-data checkout] --preseason   # exploratory; preseason never counts toward the test

For every steam alert on a final game with a closing ladder, the move is (close level - alert level), signed + when Pinnacle
kept going the way the alert pointed (sharp.steam_move). A game's score is the mean of the sign of that move over its alerts.
The first look takes the first 100 regular-season games by tip time that have a graded alert, so later games cannot change
the verdict. Rules: mean score above zero with t >= 2; positive in both halves of 50; at least 15 game days with at most 15
games on one; at least 80% of the alerts on those games have a closing ladder.
"""
import glob, json, math, os, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sharp

FIRST_LOOK_GAMES, HALF, MIN_DAYS, MAX_PER_DAY, MIN_LADDER = 100, 50, 15, 15, 0.80


def sign(x):
    return (x > 0) - (x < 0)


def load(root):
    """-> (alerts, closes, finals, preseason ids). Steam alerts only; closes {tday: pinclose.json}; finals = game ids with a saved box."""
    pre = set()
    try:
        pre = {g for g, t in json.load(open(os.path.join(root, 'season_types.json'))).items() if t == 1}
    except (OSError, ValueError):
        pass
    alerts = {}
    for p in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'signals.json'))):
        try:
            alerts.update({k: a for k, a in json.load(open(p)).items() if a['type'] == 'steam'})
        except ValueError:
            pass
    closes = {}
    for a in alerts.values():
        if a['tday'] not in closes:
            q = os.path.join(root, 'snapshots', a['tday'], 'pinclose.json')
            closes[a['tday']] = json.load(open(q)) if os.path.exists(q) else {}
    finals = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(root, 'results', '*.json')) if not f.endswith('.meta.json')}
    return alerts, closes, finals, pre


def per_game(alerts, closes, finals, keep):
    """-> {gid: {'tip', 'tday', 'd': [signs], 'moves': [..], 'fired': n, 'ladder': n, 'markets': [...]}} for final games `keep(gid)` allows."""
    out = {}
    for a in alerts.values():
        g = str(a['g'])
        if g not in finals or not keep(g):
            continue
        G = out.setdefault(g, {'tip': a['tip'], 'tday': a['tday'], 'd': [], 'moves': [], 'fired': 0, 'ladder': 0, 'm': []})
        G['fired'] += 1
        c = closes.get(a['tday'], {}).get(g)
        mv = sharp.steam_move(a, sharp._lad(c['lad'])) if c and c.get('lad') else None
        if mv is None:
            continue
        G['ladder'] += 1
        G['d'].append(sign(mv))
        G['moves'].append(mv)
        G['m'].append((a['m'], sign(mv)))
    return {g: G for g, G in out.items() if G['d']}


def stats(xs):
    n = len(xs)
    m = sum(xs) / n if n else None
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    return n, m, se, (m / se if se else None)


def evaluate(games, first=FIRST_LOOK_GAMES):
    """The pre-registered rule on the first `first` games by tip. -> dict with each rule's result and the overall verdict."""
    G = sorted(games.items(), key=lambda kv: (kv[1]['tip'], kv[0]))[:first]
    score = [sum(g['d']) / len(g['d']) for _, g in G]
    n, m, se, t = stats(score)
    h = first // 2
    halves = [stats(score[:h])[1], stats(score[h:])[1]]
    days = Counter(g['tday'] for _, g in G)
    fired, ladder = sum(g['fired'] for _, g in G), sum(g['ladder'] for _, g in G)
    r = {'games': n, 'mean': m, 'se': se, 't': t, 'halves': halves, 'days': len(days), 'max_day': max(days.values()) if days else None,
         'ladder_share': ladder / fired if fired else None}
    r['rule1'] = bool(m and m > 0 and t is not None and t >= 2)
    r['rule2'] = all(x is not None and x > 0 for x in halves)
    r['rule3'] = len(days) >= MIN_DAYS and max(days.values()) <= MAX_PER_DAY
    r['rule4'] = r['ladder_share'] is not None and r['ladder_share'] >= MIN_LADDER
    r['pass'] = r['rule1'] and r['rule2'] and r['rule3'] and r['rule4']
    return r


def report(r, label):
    f = lambda x, k=3: 'n/a' if x is None else f'{x:+.{k}f}'
    print(f"{label}: {r['games']} games  mean score {f(r['mean'])}  SE {f(r['se'])}  t {f(r['t'], 2)}")
    print(f"  halves {f(r['halves'][0])} / {f(r['halves'][1])}   game days {r['days']} (max {r['max_day']} on one day)   alerts with a closing ladder {r['ladder_share']:.0%}" if r['games'] else '  no games')
    for k, nm in (('rule1', '1 continuation, mean > 0 and t >= 2'), ('rule2', '2 both halves positive'), ('rule3', '3 at least 15 days, at most 15 games on one'), ('rule4', '4 at least 80% of alerts have a closing ladder')):
        print(f"  rule {nm}: {'ok' if r[k] else 'NOT MET'}")
    print(f"  verdict: {'PASS' if r['pass'] else 'NO-GO'}")


def main(argv):
    pre = '--preseason' in argv
    args = [a for a in argv if not a.startswith('--')]
    root = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'nba-data')
    alerts, closes, finals, PRE = load(root)
    keep = (lambda g: g in PRE) if pre else (lambda g: g not in PRE)
    games = per_game(alerts, closes, finals, keep)
    fired = sum(1 for a in alerts.values() if keep(str(a['g'])))
    print(f"{'preseason (exploratory, never counts)' if pre else 'regular season'}: {fired} steam alerts fired, {len(games)} final games with a graded alert (first look at {FIRST_LOOK_GAMES})")
    if pre:
        report(evaluate(games, first=len(games) - len(games) % 2 or 2), 'exploratory, all preseason games')
        mv = [x for g in games.values() for x in g['moves']]
        print(f"  alerts {len(mv)}: continued {sum(x > 0 for x in mv)}, reversed {sum(x < 0 for x in mv)}, flat {sum(x == 0 for x in mv)}")
        for mk in ('sp', 'tot', 'ml'):
            ds = [d for g in games.values() for m, d in g['m'] if m == mk]
            print(f"  {mk}: {len(ds)} alerts, continued {sum(d > 0 for d in ds)}, reversed {sum(d < 0 for d in ds)}")
        return
    if len(games) < FIRST_LOOK_GAMES:
        print(f"  not at the first look: {FIRST_LOOK_GAMES - len(games)} more games needed. No statistic is computed before it (docs/steam-continuation.md).")
        return
    report(evaluate(games), 'FIRST LOOK, first 100 regular-season games by tip')


if __name__ == '__main__':
    main(sys.argv[1:])
