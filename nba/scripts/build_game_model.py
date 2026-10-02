#!/usr/bin/env python3
"""
NBA game model: availability-adjusted team ratings -> spread, total, win%.
Pure stdlib. Walk-forward: every prediction uses only games before it.

Shape (docs/PLAN.md §4A), borrowed from the NFL build_game_model.py and
extended for what matters far more in the NBA, who is actually playing:

  team rating      R[t]  full-strength net margin, online update, mean-reverted each season
  scoring          O[t] / D[t] points above/below league base, same update
  player value     v = ewma(game score) - REP * ewma(minutes)   (production above replacement)
  availability     team missing value = sum over its rotation of P(out) * max(v, 0)
  rest             back-to-back penalty

  margin = R[h] - R[a] + HFA - C * (miss_h - miss_a) + B2B * (b2b_a - b2b_h)
  total  = 2*BASE + O[h] + O[a] - D[h] - D[a] - CT * (miss_h + miss_a)

P(out) comes from the official injury report AS OF the bet time (Out 1.0,
Doubtful / Questionable / Probable at their running measured play rates). The
ratings learn from what actually happened (who really sat), which is not a
leak: an update only ever happens after its game.

Tuning (2021-22 warm-up, 2022-23 + 2023-24 fit) uses who actually sat, since
there are no archived injury reports for those seasons. Test seasons 2024-25
and 2025-26 are then scored with the injury report as of the bet time, against
the real ESPN open and close lines.

  python3 nba/scripts/build_game_model.py            # tune + test + write
  python3 nba/scripts/build_game_model.py --no-tune  # reuse params in data/game_model.json
Writes nba/data/game_model.json and nba/docs/game-model.md
"""
import datetime as dt, json, math, os, statistics, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import nba_common as C

WARM, TUNE, TEST = [2022], [2023, 2024], [2025, 2026]
OUT_JSON = os.path.join(C.HERE, '..', 'data', 'game_model.json')
OUT_MD = os.path.join(C.HERE, '..', 'docs', 'game-model.md')

DEFAULT = {'K': 0.06, 'KP': 0.05, 'CARRY': 0.6, 'C': 1.0, 'CT': 0.8, 'REP': 0.30, 'B2B': 1.5,
           'ALPHA': 0.12, 'ROT_MIN': 12.0, 'ROT_DAYS': 21}


class Model:
    def __init__(self, P):
        self.P = P
        self.R = defaultdict(float)
        self.O = defaultdict(float)
        self.D = defaultdict(float)
        self.base = 112.0
        self.hfa = 2.5
        self.hfa_n = 0
        self.pl = {}                      # athlete_id -> {mpg, gs, n, team, last}
        self.team_last = {}               # team -> datetime of last game
        self.season = None
        self.status_counts = defaultdict(lambda: [1, 1])  # status -> [sat, played], Laplace prior
        self.pts = [0.0, 0]                 # this regular season's points scored, team-games (season-start option T)
        self.moves = {}                     # team -> {'in': [(aid, value)], 'out': [...]} at the last season start

    # ── state helpers ──
    def new_season(self, s, roster=None):
        """Season start: shrink ratings by CARRY. Options (docs/season-start-test.md), off unless set in P:
          ROSTER_K  roster: aid -> team for the new season; each team's rating moves by
                    ROSTER_K x C x (value of players who joined - value of players who left), and players take the team
          TOT_RESET league base = last regular season's points per team; offense / defense re-centered to zero"""
        if self.season is not None and s != self.season:
            c = self.P['CARRY']
            for d in (self.R, self.O, self.D):
                for t in d:
                    d[t] *= c
            if self.P.get('TOT_RESET') and self.pts[1]:
                self.base = self.pts[0] / self.pts[1]
                for d in (self.O, self.D):
                    mu = statistics.mean(d.values()) if d else 0.0
                    for t in d:
                        d[t] -= mu
            self.pts = [0.0, 0]
            if roster is not None:
                self.apply_roster(roster)
        self.season = s

    def apply_roster(self, roster):
        """roster: aid -> team now. Records who joined / left each team; with ROSTER_K, moves team ratings by it."""
        k, moves = self.P.get('ROSTER_K') or 0.0, defaultdict(lambda: {'in': [], 'out': []})
        for a, p in self.pl.items():
            if p.get('s') != self.season:          # only last season's players can join or leave a team
                continue
            new = roster.get(a)
            if new is None or new == p['team']:
                if new is None and p['team'] and self.value(p) > 0:
                    moves[p['team']]['out'].append((a, self.value(p)))     # not on any roster now
                continue
            v = self.value(p)
            moves[new]['in'].append((a, v))
            if p['team']:
                moves[p['team']]['out'].append((a, v))
            p['team'] = new
        if k:
            for t, mv in moves.items():
                self.R[t] += k * self.P['C'] * (sum(v for _, v in mv['in']) - sum(v for _, v in mv['out']))
        self.moves = dict(moves)

    def value(self, p):
        return max(0.0, p['gs'] - self.P['REP'] * p['mpg'])

    def rotation(self, team, when):
        lim = when - dt.timedelta(days=self.P['ROT_DAYS'])
        return {a: p for a, p in self.pl.items()
                if p['team'] == team and p['mpg'] >= self.P['ROT_MIN'] and p['last'] >= lim}

    def p_out(self, status):
        if status == 'Out':
            return 1.0
        if status in ('Doubtful', 'Questionable', 'Probable'):
            sat, played = self.status_counts[status]
            return sat / (sat + played)
        return 0.0

    def missing(self, team, when, out_prob):
        """out_prob: athlete_id -> P(out). Returns summed value of expected absences."""
        return sum(self.value(p) * out_prob.get(a, 0.0) for a, p in self.rotation(team, when).items())

    def b2b(self, team, when):
        last = self.team_last.get(team)
        return 1.0 if last and (when - last) < dt.timedelta(hours=30) else 0.0

    # ── predict / update ──
    def predict(self, g, miss_h, miss_a):
        P = self.P
        hfa = 0.0 if g['neutral'] else self.hfa
        bh, ba = self.b2b(g['home'], g['tip']), self.b2b(g['away'], g['tip'])
        margin = self.R[g['home']] - self.R[g['away']] + hfa - P['C'] * (miss_h - miss_a) + P['B2B'] * (ba - bh)
        ph = self.base + self.O[g['home']] - self.D[g['away']] + hfa / 2 - P['CT'] * miss_h - P['B2B'] / 2 * bh
        pa = self.base + self.O[g['away']] - self.D[g['home']] - hfa / 2 - P['CT'] * miss_a - P['B2B'] / 2 * ba
        return margin, ph + pa, ph, pa

    def update(self, g, rows):
        P = self.P
        played = {r['athlete_id'] for r in rows if r['played']}
        oracle = {}
        for t in (g['home'], g['away']):
            for a in self.rotation(t, g['tip']):
                if a not in played:
                    oracle[a] = 1.0
        mh, ma = self.missing(g['home'], g['tip'], oracle), self.missing(g['away'], g['tip'], oracle)
        margin, total, ph, pa = self.predict(g, mh, ma)
        err = (g['hs'] - g['as']) - margin
        self.R[g['home']] += P['K'] * err
        self.R[g['away']] -= P['K'] * err
        eh, ea = g['hs'] - ph, g['as'] - pa
        if not (P.get('TOT_RESET') and g['playoff']):       # option T: playoff games do not move scoring
            self.O[g['home']] += P['KP'] * eh
            self.D[g['away']] -= P['KP'] * eh
            self.O[g['away']] += P['KP'] * ea
            self.D[g['home']] -= P['KP'] * ea
            self.base += 0.002 * (eh + ea) / 2
        if not g['playoff']:
            self.pts[0] += g['hs'] + g['as']
            self.pts[1] += 2
        if not g['neutral'] and not g['playoff']:
            self.hfa_n += 1
            self.hfa += (g['hs'] - g['as'] - (margin - self.hfa) - self.hfa) / min(self.hfa_n, 1500)
        al = P['ALPHA']
        for r in rows:
            if not r['played']:
                continue
            p = self.pl.get(r['athlete_id'])
            gs, m = C.game_score(r), r['minutes']
            if p is None:
                self.pl[r['athlete_id']] = {'mpg': m, 'gs': gs, 'n': 1, 'team': r['team'], 'last': g['tip'], 's': self.season}
            else:
                a = max(al, 1 / (p['n'] + 1))
                p['mpg'] += a * (m - p['mpg'])
                p['gs'] += a * (gs - p['gs'])
                p['n'] += 1
                p['team'], p['last'], p['s'] = r['team'], g['tip'], self.season
        self.team_last[g['home']] = self.team_last[g['away']] = g['tip']
        return oracle

    def learn_status(self, statuses, played):
        for a, st in statuses.items():
            if st in self.status_counts or st in ('Doubtful', 'Questionable', 'Probable'):
                self.status_counts[st][0 if a not in played else 1] += 1


def run(P, seasons, box, lines=None, inj=None, record_from=None):
    """Walk forward over seasons. Returns per-game records for seasons >= record_from."""
    m = Model(P)
    recs = []
    first = season_rosters(seasons, box) if P.get('ROSTER_K') else {}
    for g in C.games(seasons):
        m.new_season(g['season'], first.get(g['season']) if P.get('ROSTER_K') else None)
        rows = box.get(g['game_id'], [])
        if not rows:
            continue
        if record_from and g['season'] >= record_from:
            day = g['tip_et'].strftime('%Y-%m-%d')
            rec = {'g': g, 'actual_margin': g['hs'] - g['as'], 'actual_total': g['hs'] + g['as']}
            played = {r['athlete_id'] for r in rows if r['played']}
            modes = {'none': ({}, {})}
            modes['oracle'] = tuple({a: 1.0 for a in m.rotation(t, g['tip']) if a not in played} for t in (g['home'], g['away']))
            if inj:
                for label, cutoff in (('tip', g['tip_et'] - dt.timedelta(minutes=30)),
                                      ('am', g['tip_et'].replace(hour=13, minute=0))):
                    c = min(cutoff, g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
                    modes[label] = tuple({a: m.p_out(s) for a, s in inj.status(day, t, c).items()}
                                         for t in (g['home'], g['away']))
            for label, (oh, oa) in modes.items():
                mh, ma = m.missing(g['home'], g['tip'], oh), m.missing(g['away'], g['tip'], oa)
                rec[label] = m.predict(g, mh, ma)[:2]
            if lines:
                rec['line'] = lines.get(g['game_id'])
            recs.append(rec)
            if inj:
                c = (g['tip_et'] - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
                for t in (g['home'], g['away']):
                    m.learn_status(inj.status(day, t, c), played)
        m.update(g, rows)
    return m, recs


def season_rosters(seasons, box):
    """season -> {aid: team he first plays for that season}: the opening roster as the backtest can know it."""
    out = defaultdict(dict)
    for g in C.games(seasons):
        for r in box.get(g['game_id'], []):
            if r['played']:
                out[g['season']].setdefault(r['athlete_id'], r['team'])
    return out


def mae(xs):
    return statistics.mean(abs(x) for x in xs) if xs else float('nan')


def tune(box):
    """Coordinate descent on margin + total MAE over the tune seasons (oracle availability)."""
    P = dict(DEFAULT)
    if os.path.exists(OUT_JSON):
        P.update(json.load(open(OUT_JSON)).get('params', {}))

    def score(P):
        _, recs = run(P, WARM + TUNE, box, record_from=TUNE[0])
        return (mae([r['oracle'][0] - r['actual_margin'] for r in recs]),
                mae([r['oracle'][1] - r['actual_total'] for r in recs]))

    grid = {'K': [0.04, 0.05, 0.06, 0.07, 0.08], 'CARRY': [0.4, 0.5, 0.6, 0.7, 0.8],
            'C': [0.0, 0.5, 0.75, 1.0, 1.25, 1.5], 'REP': [0.2, 0.25, 0.3, 0.35, 0.4],
            'B2B': [0.0, 1.0, 1.5, 2.0, 2.5, 3.0], 'KP': [0.03, 0.04, 0.05, 0.06, 0.07],
            'CT': [0.0, 0.4, 0.8, 1.2, 1.6], 'ALPHA': [0.06, 0.09, 0.12, 0.16]}
    target = {'K': 0, 'CARRY': 0, 'C': 0, 'REP': 0, 'B2B': 0, 'ALPHA': 0, 'KP': 1, 'CT': 1}
    best = score(P)
    print('start', P, [round(x, 3) for x in best], flush=True)
    for sweep in range(2):
        for k, vals in grid.items():
            i = target[k]
            for v in vals:
                if v == P[k]:
                    continue
                Q = dict(P, **{k: v})
                s = score(Q)
                if s[i] < best[i] - 1e-4:
                    P, best = Q, s
            print(f'  sweep {sweep} {k}={P[k]}  margin MAE {best[0]:.3f}  total MAE {best[1]:.3f}', flush=True)
    return P, best


# ── evaluation vs real lines ───────────────────────────────────────────────
def ats(recs, mode, line_key, thresholds=(0, 1, 2, 3, 4, 5)):
    """Bet the side the model prefers when |model - market| >= t. Graded on the actual result."""
    out = {}
    for t in thresholds:
        w = l = 0
        for r in recs:
            L = r.get('line') or {}
            spr = L.get(line_key)
            if spr is None or mode not in r:
                continue
            mkt = -spr
            edge = r[mode][0] - mkt
            if abs(edge) < t or edge == 0:
                continue
            res = r['actual_margin'] - mkt
            if res == 0:
                continue
            w += (res > 0) == (edge > 0)
            l += (res > 0) != (edge > 0)
        n = w + l
        out[t] = {'n': n, 'win': round(w / n, 4) if n else None,
                  'se': round(math.sqrt(0.25 / n), 4) if n else None,
                  'roi_110': round((w * 100 / 110 - l) / n, 4) if n else None}
    return out


def ou(recs, mode, line_key, thresholds=(0, 2, 4, 6, 8)):
    out = {}
    for t in thresholds:
        w = l = 0
        for r in recs:
            L = r.get('line') or {}
            tot = L.get(line_key)
            if tot is None or mode not in r:
                continue
            edge = r[mode][1] - tot
            if abs(edge) < t or edge == 0:
                continue
            res = r['actual_total'] - tot
            if res == 0:
                continue
            w += (res > 0) == (edge > 0)
            l += (res > 0) != (edge > 0)
        n = w + l
        out[t] = {'n': n, 'win': round(w / n, 4) if n else None, 'se': round(math.sqrt(0.25 / n), 4) if n else None}
    return out


def info_test(recs, mode, key, idx):
    """OLS actual ~ a + b*market + g*(model - market). g > 0 at 2 SE = the model knows something the line does not."""
    xs, ys = [], []
    for r in recs:
        L = r.get('line') or {}
        v = L.get(key)
        if v is None or mode not in r:
            continue
        mkt = -v if idx == 0 else v
        xs.append((mkt, r[mode][idx] - mkt))
        ys.append(r['actual_margin'] if idx == 0 else r['actual_total'])
    n = len(ys)
    if n < 50:
        return None
    # 3-param OLS via normal equations
    X = [(1.0, a, b) for a, b in xs]
    XtX = [[sum(x[i] * x[j] for x in X) for j in range(3)] for i in range(3)]
    Xty = [sum(x[i] * y for x, y in zip(X, ys)) for i in range(3)]
    inv = inverse3(XtX)
    beta = [sum(inv[i][j] * Xty[j] for j in range(3)) for i in range(3)]
    res = [y - sum(b * xi for b, xi in zip(beta, x)) for x, y in zip(X, ys)]
    s2 = sum(e * e for e in res) / (n - 3)
    se = [math.sqrt(s2 * inv[i][i]) for i in range(3)]
    return {'n': n, 'b_market': round(beta[1], 3), 'g_model_gap': round(beta[2], 3), 'g_se': round(se[2], 3),
            't': round(beta[2] / se[2], 2)}


def inverse3(m):
    a, b, c = m[0]; d, e, f = m[1]; g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def main(argv):
    box = C.player_games(WARM + TUNE + TEST)
    if '--no-tune' in argv and os.path.exists(OUT_JSON):
        prev = json.load(open(OUT_JSON))
        P, tuned = dict(DEFAULT, **prev['params']), prev.get('tune_mae')
    else:
        P, tuned = tune(box)
    lines = C.closing_lines()
    inj = C.InjuryAsOf(TEST, C.player_index(box))
    model, recs = run(P, WARM + TUNE + TEST, box, lines, inj, record_from=TEST[0])

    rep = {'params': P, 'tune_mae': tuned, 'hfa': round(model.hfa, 2), 'base': round(model.base, 1), 'seasons': {}}
    for s in TEST + ['all']:
        R = [r for r in recs if s == 'all' or r['g']['season'] == s]
        withl = [r for r in R if r.get('line') and r['line'].get('spread_close') is not None]
        blk = {'games': len(R), 'with_lines': len(withl), 'mae': {}}
        for mode in ('none', 'oracle', 'tip', 'am'):
            blk['mae'][mode] = {'margin': round(mae([r[mode][0] - r['actual_margin'] for r in withl]), 3),
                                'total': round(mae([r[mode][1] - r['actual_total'] for r in withl if r['line'].get('total_close')]), 3)}
        blk['mae']['market_open'] = {'margin': round(mae([-r['line']['spread_open'] - r['actual_margin'] for r in withl if r['line']['spread_open'] is not None]), 3),
                                     'total': round(mae([r['line']['total_open'] - r['actual_total'] for r in withl if r['line'].get('total_open')]), 3)}
        blk['mae']['market_close'] = {'margin': round(mae([-r['line']['spread_close'] - r['actual_margin'] for r in withl]), 3),
                                      'total': round(mae([r['line']['total_close'] - r['actual_total'] for r in withl if r['line'].get('total_close')]), 3)}
        blk['ats_close_tip'] = ats(withl, 'tip', 'spread_close')
        blk['ats_open_am'] = ats(withl, 'am', 'spread_open')
        blk['ou_close_tip'] = ou(withl, 'tip', 'total_close')
        blk['ou_open_am'] = ou(withl, 'am', 'total_open')
        blk['info_spread_close'] = info_test(withl, 'tip', 'spread_close', 0)
        blk['info_spread_open'] = info_test(withl, 'am', 'spread_open', 0)
        blk['info_total_close'] = info_test(withl, 'tip', 'total_close', 1)
        rep['seasons'][str(s)] = blk
        print(s, json.dumps(blk['mae']), flush=True)
        print('   ATS close@tip', {t: (v['n'], v['win']) for t, v in blk['ats_close_tip'].items()})
        print('   ATS open@1pm ', {t: (v['n'], v['win']) for t, v in blk['ats_open_am'].items()})
        print('   O/U close@tip', {t: (v['n'], v['win']) for t, v in blk['ou_close_tip'].items()})
        print('   info', blk['info_spread_close'], blk['info_spread_open'], blk['info_total_close'])

    rep['ratings'] = {t: {'net': round(model.R[t], 2), 'off': round(model.O[t], 2), 'def': round(model.D[t], 2)}
                      for t in sorted(model.R)}
    rep['status_play_rates'] = {k: round(v[1] / sum(v), 3) for k, v in model.status_counts.items()}
    rep['generated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    json.dump(rep, open(OUT_JSON, 'w'), indent=1)
    write_md(rep)


def write_md(rep):
    a = rep['seasons']['all']
    P = rep['params']
    L = ['# NBA game model: backtest', '',
         f"Generated {rep['generated']} by `nba/scripts/build_game_model.py`. Walk-forward, out of sample.", '',
         'Tuned on 2022-23 and 2023-24 (2021-22 warm-up) using who actually sat. Tested on 2024-25 and',
         '2025-26 with the **official injury report as of the bet time** (no hindsight), against real ESPN lines',
         '(DraftKings where available, else ESPN BET).', '',
         '## Verdict', '',
         (f"**Context, not an edge.** Against the closing spread the model adds nothing the line has not priced "
          f"(t = {a['info_spread_close']['t']}). It does beat ESPN's OPENING line, but that open has no timestamp and "
          "is often posted before the injury news the model uses. The honest bet-time test (Kalshi prices actually "
          "tradeable at 1pm, bottom of this page) is the one that decides. Same outcome as the NFL game model.")
         if a['info_spread_close'] and a['info_spread_close']['t'] < 2 else
         '**Possible edge vs the close. Verify against the Kalshi bet-time test below before trusting it.**', '',
         '## Accuracy (mean absolute error, points; lower is better)', '',
         '| Season | Games | Model, no injuries | Model, report 30 min pre-tip | Model, report 1pm | Model, hindsight lineups | Open line | Close line |',
         '|---|---|---|---|---|---|---|---|']
    for s in ['2025', '2026', 'all']:
        b = rep['seasons'][s]
        mm = b['mae']
        L.append(f"| {s} spread | {b['with_lines']} | {mm['none']['margin']} | {mm['tip']['margin']} | {mm['am']['margin']} | {mm['oracle']['margin']} | {mm['market_open']['margin']} | {mm['market_close']['margin']} |")
    for s in ['2025', '2026', 'all']:
        b = rep['seasons'][s]
        mm = b['mae']
        L.append(f"| {s} total | {b['with_lines']} | {mm['none']['total']} | {mm['tip']['total']} | {mm['am']['total']} | {mm['oracle']['total']} | {mm['market_open']['total']} | {mm['market_close']['total']} |")
    L += ['', '## Against the spread (both test seasons)', '',
          'Bet the side the model prefers when it disagrees with the line by at least the threshold.',
          'Break-even at -110 is 52.4%.', '',
          '| Gap (pts) | vs close, report@tip: bets | win% | ROI | vs open, report@1pm: bets | win% | ROI |', '|---|---|---|---|---|---|---|']
    for t in a['ats_close_tip']:
        c, o = a['ats_close_tip'][t], a['ats_open_am'][t]
        L.append(f"| {t}+ | {c['n']} | {pct(c['win'])} | {pct(c['roi_110'])} | {o['n']} | {pct(o['win'])} | {pct(o['roi_110'])} |")
    L += ['', '## Totals (both test seasons)', '', '| Gap (pts) | vs close: bets | win% | vs open: bets | win% |', '|---|---|---|---|---|']
    for t in a['ou_close_tip']:
        c, o = a['ou_close_tip'][t], a['ou_open_am'][t]
        L.append(f"| {t}+ | {c['n']} | {pct(c['win'])} | {o['n']} | {pct(o['win'])} |")
    L += ['', '## Does the model know anything the line does not?', '',
          'Regression: result = a + b x line + g x (model - line). If g is not clearly above 0 (t < 2), the model adds',
          'nothing the market has not already priced.', '']
    for k, lab in (('info_spread_close', 'spread vs close'), ('info_spread_open', 'spread vs open (1pm report)'), ('info_total_close', 'total vs close')):
        v = a[k]
        if v:
            L.append(f"- {lab}: g = {v['g_model_gap']} (SE {v['g_se']}, t = {v['t']}), n = {v['n']}")
    L += ['', '## Fitted parameters', '',
          f"K {P['K']} (rating step), CARRY {P['CARRY']} (season carryover), C {P['C']} (spread pts per unit of missing value),",
          f"CT {P['CT']} (total pts per unit), REP {P['REP']} (replacement game score per minute), B2B {P['B2B']} pts,",
          f"ALPHA {P['ALPHA']} (player form smoothing), KP {P['KP']} (scoring step). Home court {rep['hfa']} pts.", '',
          f"Injury status play rates (measured): {rep['status_play_rates']}", '']
    open(OUT_MD, 'w').write('\n'.join(L))


def pct(x):
    return '' if x is None else f'{x * 100:.1f}%'


if __name__ == '__main__':
    main(sys.argv[1:])
