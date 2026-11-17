#!/usr/bin/env python3
"""Round 3: inputs the box score can't see. Does the closing line fully price (a) a team's starters being listed Out / Doubtful on the injury report, and
(b) a QB change (the game's starter differs from the team's previous starter, 11.7% of team-games)? Tested as: (actual margin - close) regressed on those features,
ridge, refit each season on earlier seasons only, judged on the 2020+ holdout. The target is the CLOSE, so anything that works is information the close missed.

Starter weight = the player's snap share in his previous game (>= 0.4), so a listed backup counts for ~0. Injury data: nflverse injuries (2011+). Snaps: 2013+, so features start 2014.

  python3 scripts/explore_nfl_rebuild3.py --games games.csv --dir DIR      # DIR holds inj{season}.csv and sn{season}.csv from the nflverse-data releases
"""
import argparse, csv, math, os, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_nfl_rebuild as B

GROUPS = {'OL': {'T', 'G', 'C', 'OL', 'OT', 'OG'}, 'DL': {'DE', 'DT', 'NT', 'DL'}, 'LB': {'LB', 'ILB', 'OLB', 'MLB'}, 'DB': {'CB', 'S', 'SS', 'FS', 'DB'}, 'SK': {'WR', 'TE', 'RB', 'FB'}}
GROUP_OF = {p: g for g, ps in GROUPS.items() for p in ps}
STATUS_W = {'out': 1.0, 'doubtful': 0.9, 'questionable': 0.2}
NAMES = list(GROUPS)


def norm(n): return re.sub(r'(jr|sr|ii|iii|iv|v)$', '', re.sub(r'[^a-z]', '', (n or '').lower()))


def load_snaps(d):
    """(team) -> list of (season, week, name, share) in time order."""
    rows = []
    for y in range(2013, 2027):
        p = os.path.join(d, f'sn{y}.csv')
        if not os.path.exists(p) or os.path.getsize(p) < 100: continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if r['game_type'] != 'REG': continue
            share = max(B.fnum(r['offense_pct']) or 0, B.fnum(r['defense_pct']) or 0)
            rows.append((int(r['season']), int(r['week']), B.team(r['team']), norm(r['player']), share))
    rows.sort(); return rows


def load_inj(d):
    out = defaultdict(list)           # (season, week, team) -> [(name, group, weight)]
    for y in range(2013, 2027):
        p = os.path.join(d, f'inj{y}.csv')
        if not os.path.exists(p): continue
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if r['game_type'] != 'REG': continue
            w, g = STATUS_W.get((r['report_status'] or '').strip().lower()), GROUP_OF.get(r['position'])
            if w and g: out[(int(r['season']), int(r['week']), B.team(r['team']))].append((norm(r['full_name']), g, w))
    return out


def build(games, snaps, inj):
    """Attach inj feature vector (home minus away, per group) and QB-change flags to each game."""
    last = {}                          # (team, name) -> share in his most recent game
    by_week = defaultdict(list)
    for s, w, t, n, sh in snaps: by_week[(s, w)].append((t, n, sh))
    qb_hist = defaultdict(list)        # team -> recent starters
    weeks = sorted({(g['season'], g['week']) for g in games})
    gi = defaultdict(list)
    for g in games: gi[(g['season'], g['week'])].append(g)
    allw = sorted(set(by_week) | set(weeks))
    for sw in allw:
        for g in gi.get(sw, []):
            feat = {}
            for side, tm in (('h', g['h']), ('a', g['a'])):
                v = dict.fromkeys(NAMES, 0.0)
                for n, grp, w in inj.get((g['season'], g['week'], tm), []):
                    sh = last.get((tm, n), 0.0)
                    if sh >= 0.4: v[grp] += w * sh
                feat[side] = v
            g['inj'] = [feat['h'][k] - feat['a'][k] for k in NAMES]
            for side, tm, q in (('h', g['h'], g['hq']), ('a', g['a'], g['aq'])):
                hist = qb_hist[tm]
                g['qbchg_' + side] = float(q is not None and bool(hist) and q != hist[-1])      # starter differs from the team's previous game
        for g in gi.get(sw, []):                 # starters become known only after the game
            for tm, q in ((g['h'], g['hq']), (g['a'], g['aq'])):
                if q: qb_hist[tm].append(q)
        for t, n, sh in by_week.get(sw, []): last[(t, n)] = sh
    return games


def row(g): return g['inj'] + [g['qbchg_h'] - g['qbchg_a']] + g['x']


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--games'); ap.add_argument('--dir', required=True)
    a = ap.parse_args(); games = [g for g in B.load_games(a.games) if g['season'] >= 2014]
    allg = B.load_games(a.games)
    for g in allg: g.setdefault('inj', [0.0] * len(NAMES))
    games = build(allg, load_snaps(a.dir), load_inj(a.dir)); games = [g for g in games if g['season'] >= 2014]
    print(len(games), 'games 2014+;', sum(1 for g in games if any(g['inj'])), 'with a nonzero injury feature;', sum(1 for g in games if g['qbchg_h'] or g['qbchg_a']), 'with a QB change')
    names = [f'{k}_out' for k in NAMES] + ['qb_change'] + B.FEATS
    # in-sample read on the train window: which features does the close mis-price?
    tr = [g for g in games if g['season'] <= 2019]
    X, y = [row(g) for g in tr], [g['res'] - g['sp'] for g in tr]
    w = B.ols(X, y, ridge=len(tr) * 0.05)
    resid_sd = math.sqrt(sum((yy - sum(c * x for c, x in zip(w, r))) ** 2 for r, yy in zip(X, y)) / (len(y) - len(w)))
    print('\nrefit target = actual margin minus close; coefficients on 2014-2019 (points per unit; + = home covers more):')
    for n_, c, i in zip(names, w, range(len(names))):
        sd = math.sqrt(sum(r[i] ** 2 for r in X) / len(X)); se = resid_sd / (sd * math.sqrt(len(X)))
        print(f'  {n_:<10} {c:+.3f}  (t~{c / se:+.1f})' if n_ in names[:6] else '', end='\n' if n_ in names[:6] else '')
    # walk-forward holdout
    preds = {}
    for s in sorted({g['season'] for g in games if g['season'] >= 2020}):
        tr = [g for g in games if g['season'] < s]
        w = B.ols([row(g) for g in tr], [g['res'] - g['sp'] for g in tr], ridge=len(tr) * 0.05)
        for g in games:
            if g['season'] == s: preds[g['gid']] = sum(c * x for c, x in zip(w, row(g)))
    hold = [g for g in games if g['season'] >= 2020]
    n = len(hold)
    mae_close = sum(abs(g['res'] - g['sp']) for g in hold) / n
    mae_adj = sum(abs(g['res'] - g['sp'] - preds[g['gid']]) for g in hold) / n
    print(f'\nHOLDOUT 2020+ (n={n}): close MAE {mae_close:.3f}; close + learned injury/QB-change correction MAE {mae_adj:.3f} (live model 10.005)')
    for thr in (0.5, 1.0, 1.5, 2.0):
        wn = l = 0
        for g in hold:
            p = preds[g['gid']]; c = g['res'] - g['sp']
            if abs(p) < thr or c == 0: continue
            if (c > 0) == (p > 0): wn += 1
            else: l += 1
        k = wn + l
        print(f'  correction >= {thr}: {wn}-{l}  {100 * wn / k:.1f}%  n={k}  CI95 {B.wilson(wn, k)}') if k else print(f'  correction >= {thr}: no picks')
    xs = [preds[g['gid']] for g in hold]; ys = [g['res'] - g['sp'] for g in hold]
    mx, my = sum(xs) / n, sum(ys) / n; sxx = sum((x - mx) ** 2 for x in xs)
    c = sum((x - mx) * (yy - my) for x, yy in zip(xs, ys)) / sxx
    se = math.sqrt(sum(((yy - my) - c * (x - mx)) ** 2 for x, yy in zip(xs, ys)) / (n - 2) / sxx)
    print(f'  slope of actual-minus-close on the correction: {c:+.2f} (se {se:.2f}, t={c / se:+.1f}); 1.0 would mean the correction is exactly right')


if __name__ == '__main__':
    main()
