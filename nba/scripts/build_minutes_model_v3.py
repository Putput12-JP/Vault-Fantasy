#!/usr/bin/env python3
"""
Minutes model v3, workstream B of docs/v3-plan.md. Minutes are 28.5% of the points error and 25.5% of rebounds.

Keeps v2's minutes model (EWMA + vacated teammate minutes + blowout + back-to-back, team rescaled) and adds:
  role       separate EWMAs of minutes as a starter and off the bench, keyed on whether he started his last game
             (DARKO: starting role and minutes have a 1 to 3 game memory, so a switch should move minutes now)
  return     first games back after missing 3+ team games (restrictions): game 1, games 2-3, games 4-6
  trade      a faster learning rate for the first NEW_N games with a new team
  spread     blowout risk from the market spread (2024-25 on), our game model's margin before that
Also a hindsight variant that knows who actually started, to size what confirmed lineups (posted about 30 min
before tip) are worth before we build a feed for them.

Protocol: fit on 2022-23 to 2024-25 (who actually sat before 2024-25, the injury report after), test 2025-26
with the report 30 min before tip. Scored on players who played, same rows for every variant.

  python3 nba/scripts/build_minutes_model_v3.py
Writes data/minutes_model_v3.json and docs/minutes-model-v3.md.
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C
import build_minutes_model as MM

SEASONS = [2022, 2023, 2024, 2025, 2026]
FIT, TEST = [2023, 2024, 2025], 2026
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'minutes_model_v3.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'minutes-model-v3.md')
RETURN_MISSED = 3            # team games missed that make the next appearance a "return"
FEATURES = ['vac_same', 'vac_other', 'vac_same_x_share', 'vac_other_x_share', 'blowout_starter', 'blowout_bench',
            'b2b', 'b2b_x_share', 'role', 'back1', 'back2_3', 'back4_6', 'const']
V2_FEATURES = MM.FEATURES


class Cached(MM.State):
    """v2's state with the team rotation cached per game (it is rebuilt from every player otherwise)."""

    def rotation(self, team, when):
        key = (team, when)
        if getattr(self, '_rk', None) != key:
            self._rk, self._rv = key, super().rotation(team, when)
        return self._rv


class State(Cached):
    """v2's minutes state plus role-split minutes, return-from-absence tracking and a new-team learning rate."""

    def __init__(self, alpha, a_new=None, new_n=8):
        MM.State.__init__(self, alpha)
        self.a_new, self.new_n = a_new, new_n
        self.tg = defaultdict(int)          # team -> team games played so far

    def pre(self, aid, team):
        """Pre-game facts for a player: (games missed since his last appearance for this team, games since return)."""
        p = self.pl[aid]
        missed = self.tg[team] - p.get('idx', self.tg[team]) - 1 if p.get('team') == team else 0
        k = 0 if missed >= RETURN_MISSED else (p['since'] + 1 if p.get('since') is not None else None)
        return missed, k

    def update(self, g, rows):
        for r in rows:
            if not r['played']:
                continue
            aid, team, st = r['athlete_id'], r['team'], 1.0 if r['starter'] else 0.0
            p = self.pl.get(aid)
            if p is None:
                self.pl[aid] = {'m': r['minutes'], 'n': 1, 'team': team, 'last': g['tip'], 'pos': MM.group(r['pos']), 'st': st,
                                'ms': r['minutes'] if st else None, 'mb': None if st else r['minutes'], 'st_last': st,
                                'idx': self.tg[team], 'since': None, 'with': 1}
                continue
            moved = p['team'] != team
            missed, k = (0, None) if moved else self.pre(aid, team)
            p['with'] = 1 if moved else p.get('with', 0) + 1
            a = max(self.alpha, 1 / (p['n'] + 1))
            if self.a_new and p['with'] <= self.new_n:
                a = max(a, self.a_new)
            p['m'] += a * (r['minutes'] - p['m'])
            p['st'] += a * (st - p['st'])
            key = 'ms' if st else 'mb'
            p[key] = r['minutes'] if p[key] is None else p[key] + a * (r['minutes'] - p[key])
            p['st_last'] = st
            p['since'] = k if k is not None and k <= 6 else None
            p['n'] += 1
            p['team'], p['last'], p['idx'] = team, g['tip'], self.tg[team]
        for t in {g['home'], g['away']}:
            self.tg[t] += 1
        self.team_last[g['home']] = self.team_last[g['away']] = g['tip']


def role_term(p, started):
    ref = p['ms'] if started else p['mb']
    return (ref - p['m']) if ref is not None else 0.0


def features(st, g, team, aid, out, spread):
    """v2's features plus role (keyed on his last game's role, what is known live) and return from absence."""
    x = MM.features(st, g, team, aid, out, spread)             # v2's 9, const last
    p = st.pl[aid]
    _, k = st.pre(aid, team)
    return x[:-1] + [role_term(p, p['st_last']), p['m'] * (k == 0), p['m'] * (k in (1, 2)), p['m'] * (k in (3, 4, 5)), 1.0]


def walk(box, inj, spreads, alpha, a_new, record_from=2023):
    """Every player-game from record_from, v2 and v3 features side by side (v2 from its own state)."""
    s2, s3 = Cached(alpha_v2()), State(alpha, a_new)
    recs = []
    for g in C.games(SEASONS):
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if g['season'] >= record_from:
            played = {r['athlete_id'] for r in rows if r['played']}
            day = g['tip_et'].strftime('%Y-%m-%d')
            clk = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
            sp = spreads.get(g['game_id'])
            for team in (g['home'], g['away']):
                if g['season'] < 2025:
                    rot = s2.rotation(team, g['tip'])
                    out = {a: 1.0 for a in rot if a not in played}
                else:
                    out = {a: 1.0 for a, s in inj.status(day, team, clk).items() if s in ('Out', 'Doubtful')}
                for r in rows:
                    aid = r['athlete_id']
                    if r['team'] != team or not r['played'] or aid in out:
                        continue
                    if aid not in s2.pl or s2.pl[aid]['team'] != team or aid not in s3.pl or s3.pl[aid]['team'] != team:
                        continue
                    x3 = features(s3, g, team, aid, out, sp['best'])
                    x3o = list(x3)
                    x3o[8] = role_term(s3.pl[aid], r['starter'])          # hindsight: who actually started
                    recs.append({'g': g['game_id'], 'season': g['season'], 'team': team, 'aid': aid, 'y': r['minutes'],
                                 'b2': s2.pl[aid]['m'], 'x2': MM.features(s2, g, team, aid, out, sp['model']),
                                 'b3': s3.pl[aid]['m'], 'x3': x3, 'x3o': x3o})
        s2.update(g, rows)
        s3.update(g, rows)
    return recs


def alpha_v2():
    return json.load(open(MM.OUT_JSON))['alpha']


def predict(recs, beta, base, xkey, team_min):
    """Per-player prediction, then the team's candidates rescaled to team_min (v2's step), as the prop model does."""
    pred = {id(r): max(0.0, min(48.0, r[base] + sum(b * v for b, v in zip(beta, r[xkey])))) for r in recs}
    by = defaultdict(list)
    for r in recs:
        by[(r['g'], r['team'])].append(r)
    for grp in by.values():
        tot = sum(pred[id(r)] for r in grp)
        if tot > 0 and len(grp) >= 7:
            f = team_min / tot
            for r in grp:
                pred[id(r)] = min(48.0, pred[id(r)] * f)
    return pred


def score(recs, pred):
    e = [pred[id(r)] - r['y'] for r in recs]
    return {'mae': round(statistics.mean(abs(x) for x in e), 3), 'bias': round(statistics.mean(e), 3),
            'miss8': round(sum(abs(x) >= 8 for x in e) / len(e), 4), 'rmse': round(math.sqrt(statistics.mean(x * x for x in e)), 3)}


def main():
    box = C.player_games(SEASONS)
    inj = C.InjuryAsOf([2025, 2026], C.player_index(box))
    margins = MM.expected_margins(box)
    lines = C.closing_lines()
    spreads = {gid: {'model': m, 'best': (lines[gid]['spread_close'] if gid in lines and lines[gid]['spread_close'] is not None else m)}
               for gid, m in margins.items()}
    team_min = json.load(open(os.path.join(C.HERE, '..', 'data', 'prop_model.json')))['team_min']
    mm2 = json.load(open(MM.OUT_JSON))
    beta2 = [mm2['beta'][f] for f in V2_FEATURES]

    # tune the two learning rates: fit on 2022-23 + 2023-24, score 2024-25; then refit on all fit seasons
    best, grid = None, []
    for alpha in (0.2, 0.25, 0.3, 0.4):
        for a_new in (None, 0.35, 0.5):
            recs = walk(box, inj, spreads, alpha, a_new)
            tr = [r for r in recs if r['season'] in (2023, 2024)]
            va = [r for r in recs if r['season'] == 2025]
            beta = MM.ols([r['x3'] for r in tr], [r['y'] - r['b3'] for r in tr])
            s = score(va, predict(va, beta, 'b3', 'x3', team_min))
            grid.append({'alpha': alpha, 'a_new': a_new, **s})
            print(f'alpha {alpha} new-team {a_new}: 2024-25 MAE {s["mae"]:.3f}  8+ misses {s["miss8"]:.3f}', flush=True)
            if best is None or s['mae'] < best[0]:
                best = (s['mae'], alpha, a_new, recs)
    _, alpha, a_new, recs = best
    fit = [r for r in recs if r['season'] in FIT]
    test = [r for r in recs if r['season'] == TEST]
    beta = MM.ols([r['x3'] for r in fit], [r['y'] - r['b3'] for r in fit])
    beta_o = MM.ols([r['x3o'] for r in fit], [r['y'] - r['b3'] for r in fit])
    res = {'generated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'alpha': alpha, 'a_new': a_new,
           'new_n': 8, 'return_missed': RETURN_MISSED, 'team_min': team_min, 'features': FEATURES,
           'beta': dict(zip(FEATURES, [round(b, 4) for b in beta])), 'beta_hindsight_starters': dict(zip(FEATURES, [round(b, 4) for b in beta_o])),
           'grid': grid, 'n_test': len(test)}
    res['test'] = {'v2': score(test, predict(test, beta2, 'b2', 'x2', team_min)),
                   'v3': score(test, predict(test, beta, 'b3', 'x3', team_min)),
                   'v3_hindsight_starters': score(test, predict(test, beta_o, 'b3', 'x3o', team_min))}
    # where the new pieces act
    sub = {'first game back': lambda r: r['x3'][9] > 0, 'games 2-3 back': lambda r: r['x3'][10] > 0,
           'role switch (last game role differs from usual)': lambda r: abs(r['x3'][8]) >= 4,
           'market spread 12+': lambda r: r['x3'][4] + r['x3'][5] >= 6}
    res['slices'] = {}
    for name, f in sub.items():
        rs = [r for r in test if f(r)]
        if len(rs) >= 50:
            res['slices'][name] = {'n': len(rs), 'v2': score(rs, predict(rs, beta2, 'b2', 'x2', team_min)),
                                   'v3': score(rs, predict(rs, beta, 'b3', 'x3', team_min))}
    for k, v in res['test'].items():
        print(f'{k:24s} MAE {v["mae"]:.3f}  RMSE {v["rmse"]:.3f}  bias {v["bias"]:+.3f}  8+ misses {v["miss8"]:.3f}', flush=True)
    json.dump(res, open(OUT_JSON, 'w'), indent=1)
    write_md(res)
    print(open(OUT_MD).read())


def write_md(res):
    t = res['test']
    L = ['# Minutes model v3: backtest', '',
         f"Generated {res['generated']} by `nba/scripts/build_minutes_model_v3.py`. Fit on 2022-23 to 2024-25, tested on",
         f"2025-26 with the injury report 30 min before tip; {res['n_test']:,} player-games, identical for every row below.", '',
         '| Model | MAE (min) | RMSE | Bias | Misses of 8+ min |', '|---|---|---|---|---|']
    names = {'v2': 'v2 (shipped)', 'v3': 'v3 (role, returns, new team, market spread)', 'v3_hindsight_starters': 'v3 knowing who started (sizes a lineups feed)'}
    for k, v in t.items():
        L.append(f"| {names[k]} | {v['mae']:.3f} | {v['rmse']:.3f} | {v['bias']:+.3f} | {v['miss8']:.1%} |")
    L += ['', '## Where the new pieces act (2025-26)', '', '| Slice | Games | MAE v2 | MAE v3 | 8+ misses v2 | 8+ misses v3 |', '|---|---|---|---|---|---|']
    for k, v in res['slices'].items():
        L.append(f"| {k} | {v['n']:,} | {v['v2']['mae']:.2f} | {v['v3']['mae']:.2f} | {v['v2']['miss8']:.1%} | {v['v3']['miss8']:.1%} |")
    b = res['beta']
    L += ['', '## Fitted weights', '',
          f"- EWMA learning rate {res['alpha']}; new team: {res['a_new'] or 'no boost'} for the first {res['new_n']} games.",
          f"- Role: {b['role']:+.3f} x (his minutes in last game's role - his overall average).",
          f"- Returns (x his usual minutes): first game back {b['back1']:+.3f}, games 2-3 {b['back2_3']:+.3f}, games 4-6 {b['back4_6']:+.3f}.",
          f"- Blowout per point of spread beyond 6: starters {b['blowout_starter']:+.3f}, bench {b['blowout_bench']:+.3f}.",
          f"- Vacated minutes: same position {b['vac_same']:+.3f}, other {b['vac_other']:+.3f}. Back-to-back {b['b2b']:+.3f}.", '',
          'Learning-rate grid (fit 2022-24, scored on 2024-25):', '',
          '| EWMA | New-team rate | MAE | 8+ misses |', '|---|---|---|---|']
    for gg in res['grid']:
        L.append(f"| {gg['alpha']} | {gg['a_new'] or 'none'} | {gg['mae']:.3f} | {gg['miss8']:.1%} |")
    open(OUT_MD, 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
