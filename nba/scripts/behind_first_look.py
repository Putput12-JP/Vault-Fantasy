#!/usr/bin/env python3
"""
Game behind first look: the pre-registered rule in nba/docs/behind-pinnacle.md, applied to the alert files on nba-data.

  python3 nba/scripts/behind_first_look.py [nba-data checkout]               # regular season: counts only until 100 games
  python3 nba/scripts/behind_first_look.py [nba-data checkout] --preseason   # exploratory; preseason never counts toward the test

A bet is (game, market, side, line): its earliest alert, best EV among ties (sharp.behind_firsts). Against Pinnacle's closing ladder
each bet is graded with its EV at the close (the ladder has its number), or classified toward / against / unclassified
(sharp.behind_close). A game's score is the mean EV at the close of its graded bets. The first look takes the first 100 regular-season
games by tip time that have a graded bet. Rules: mean score at least 2.0% with t >= 2; positive in both halves of 50; line moves not
adverse (one-sided binomial p > 0.05 on against vs toward) and at least 50% of the bets graded; at least 15 game days, at most 15
games on one.
"""
import glob, json, math, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sharp

FIRST_LOOK_GAMES, MIN_MEAN, MIN_DAYS, MAX_PER_DAY, MIN_GRADED, ALPHA = 100, 0.02, 15, 15, 0.50, 0.05


def load(root):
    """-> (first alert per behind bet, closes {tday: pinclose.json}, final game ids, preseason game ids)."""
    pre = set()
    try:
        pre = {g for g, t in json.load(open(os.path.join(root, 'season_types.json'))).items() if t == 1}
    except (OSError, ValueError):
        pass
    alerts = {}
    for p in sorted(glob.glob(os.path.join(root, 'snapshots', '20*', 'signals.json'))):
        try:
            alerts.update({k: a for k, a in json.load(open(p)).items() if a['type'] == 'behind'})
        except ValueError:
            pass
    firsts = sharp.behind_firsts(alerts.values())
    bets = [a for a in alerts.values() if a['id'] in firsts]
    closes = {}
    for a in bets:
        if a['tday'] not in closes:
            q = os.path.join(root, 'snapshots', a['tday'], 'pinclose.json')
            closes[a['tday']] = json.load(open(q)) if os.path.exists(q) else {}
    finals = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(root, 'results', '*.json')) if not f.endswith('.meta.json')}
    return bets, closes, finals, pre


def per_game(bets, closes, finals, keep):
    """-> {gid: {'tip', 'tday', 'ev': [EV at close], 'kinds': Counter of every bet's class}} for final games `keep` allows,
    with at least one graded bet."""
    out = {}
    for a in bets:
        g = str(a['g'])
        if g not in finals or not keep(g):
            continue
        G = out.setdefault(g, {'tip': a['tip'], 'tday': a['tday'], 'ev': [], 'kinds': Counter(), 'rows': []})
        c = closes.get(a['tday'], {}).get(g)
        kind, ev = sharp.behind_close(a, sharp._lad(c['lad'])) if c and c.get('lad') else ('unclassified', None)
        G['kinds'][kind] += 1
        G['rows'].append((a['m'], a['venue'], kind, ev))
        if ev is not None:
            G['ev'].append(ev)
    return {g: G for g, G in out.items() if G['ev']}


def stats(xs):
    n = len(xs)
    m = sum(xs) / n if n else None
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    return n, m, se, (m / se if se else None)


def binom_tail(k, n):
    """P(X >= k) for X ~ Binomial(n, 0.5)."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def evaluate(games, first=FIRST_LOOK_GAMES):
    """The pre-registered rule on the first `first` games by tip. -> dict with each rule's result and the verdict."""
    G = sorted(games.items(), key=lambda kv: (kv[1]['tip'], kv[0]))[:first]
    score = [sum(g['ev']) / len(g['ev']) for _, g in G]
    n, m, se, t = stats(score)
    h = first // 2
    halves = [stats(score[:h])[1], stats(score[h:])[1]]
    days = Counter(g['tday'] for _, g in G)
    kinds = Counter()
    for _, g in G:
        kinds.update(g['kinds'])
    total = sum(kinds.values())
    r = {'games': n, 'mean': m, 'se': se, 't': t, 'halves': halves, 'days': len(days), 'max_day': max(days.values()) if days else None,
         'kinds': dict(kinds), 'graded_share': kinds['ev'] / total if total else None,
         'against_p': binom_tail(kinds['against'], kinds['against'] + kinds['toward'])}
    r['rule1'] = bool(m is not None and m >= MIN_MEAN and t is not None and t >= 2)
    r['rule2'] = all(x is not None and x > 0 for x in halves)
    r['rule3'] = r['against_p'] > ALPHA and r['graded_share'] is not None and r['graded_share'] >= MIN_GRADED
    r['rule4'] = len(days) >= MIN_DAYS and max(days.values()) <= MAX_PER_DAY
    r['pass'] = r['rule1'] and r['rule2'] and r['rule3'] and r['rule4']
    return r


def report(r, label):
    f = lambda x, k=3: 'n/a' if x is None else f'{x:+.{k}f}'
    print(f"{label}: {r['games']} games  mean EV at the close {f(r['mean'])}  SE {f(r['se'])}  t {f(r['t'], 2)}")
    if not r['games']:
        print('  no games')
        return
    print(f"  halves {f(r['halves'][0])} / {f(r['halves'][1])}   game days {r['days']} (max {r['max_day']} on one day)")
    print(f"  bets: {r['kinds']}   graded share {r['graded_share']:.0%}   against-vs-toward one-sided p {r['against_p']:.3f}")
    for k, nm in (('rule1', '1 edge survives, mean >= 2.0% and t >= 2'), ('rule2', '2 both halves positive'),
                  ('rule3', '3 line moves not adverse and >= 50% graded'), ('rule4', '4 at least 15 days, at most 15 games on one')):
        print(f"  rule {nm}: {'ok' if r[k] else 'NOT MET'}")
    print(f"  verdict: {'PASS' if r['pass'] else 'NO-GO'}")


def main(argv):
    pre = '--preseason' in argv
    args = [a for a in argv if not a.startswith('--')]
    root = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw', 'nba-data')
    bets, closes, finals, PRE = load(root)
    keep = (lambda g: g in PRE) if pre else (lambda g: g not in PRE)
    mine = [a for a in bets if keep(str(a['g']))]
    games = per_game(bets, closes, finals, keep)
    print(f"{'preseason (exploratory, never counts)' if pre else 'regular season'}: {len(mine)} behind bets on {len({a['g'] for a in mine})} games, "
          f"{len(games)} final games with a graded bet (first look at {FIRST_LOOK_GAMES})")
    if pre:
        n = len(games) - len(games) % 2 or 2
        report(evaluate(games, first=n), 'exploratory, all preseason games')
        return
    if len(games) < FIRST_LOOK_GAMES:
        print(f"  not at the first look: {FIRST_LOOK_GAMES - len(games)} more games needed. No statistic is computed before it (docs/behind-pinnacle.md).")
        return
    report(evaluate(games), 'FIRST LOOK, first 100 regular-season games by tip')


if __name__ == '__main__':
    main(sys.argv[1:])
