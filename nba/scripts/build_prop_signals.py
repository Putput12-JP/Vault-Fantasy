#!/usr/bin/env python3
"""
Prop signals: a fixed set of yes/no checks for one NBA player prop, each pointing Over, Under or nowhere, and this season's record
for every check, rebuilt from the lean recorder (leans/<day>.json on the nba-data branch: every prop at its last look before tip).

The checks are defined here once and never tuned on the results. Each is scored against what the no-vig market already expected for
the side it points to, so a check "works" only if its side won more often than the market's own chance said it would.

  model     Vault's side (model chance of the over, 'p').                          Level 1-4 by |p - .5| (Props Sim cuts).
  market    no-vig market side ('p_mkt'), when it leans 2+ points.
  matchup   opponent's rank allowing this stat to his position group this season, as of that morning (5+ games each):
            21st-30th (gives up the most) -> Over, 1st-10th -> Under.
  minutes   projected minutes ('min') vs his last 5 games: +2 or more -> Over, -2 or more -> Under.
  opp       opportunity: shot attempts last 5 games vs the 15 before (FGA for points and points combos, 3PA for threes):
            +10% -> Over, -10% -> Under. Not scored for rebounds, assists, steals, blocks (no potential REB / AST source).
  form      hit rate at that night's line over his last 10 games: 70%+ -> Over, 30% or less -> Under.
  move      DraftKings line from first look to last look: up -> Over, down -> Under. CONTEXT ONLY: shown with its record,
            never counted in the agree total (market moves are context, the same rule as sharp money).

Agree total = how many of the counted checks (market, matchup, minutes, opp, form) point the same way as the model.

Writes data/prop_signals.json:
  {"t", "through", "first", "n", "defs": {...cuts}, "sig": {name: {"all": rec, "o": rec, "u": rec, "h1": rec, "h2": rec}},
   "level": {"1".."4": rec}, "agree": {"<k>|<against>": rec}, "days": {day: {"agree": {...}}}}
  rec = [n, wins, market-expected wins, clustered standard error of (win - expected) per prop]
Pushes and voids are left out. h1 / h2 split the season's nights in half by date (is it stable?).

  python3 nba/scripts/build_prop_signals.py           # also run by build_data_health.py
"""
import datetime as dt, json, math, os, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
DATA = os.path.join(HERE, '..', 'data')
OUT = os.path.join(DATA, 'prop_signals.json')
BRANCH = 'origin/nba-data'
EPOCH = dt.date(1970, 1, 1)

# frozen cuts (never fitted on results)
LEVEL_CUTS = (0.0345, 0.0683, 0.1223)
MKT_MIN = 0.02
RANK_SOFT, RANK_TOUGH, RANK_MIN_GAMES = 21, 10, 5
MIN_DELTA = 2.0
OPP_DELTA = 0.10
FORM_HI, FORM_LO = 0.7, 0.3
COUNTED = ('market', 'matchup', 'minutes', 'opp', 'form')
CONTEXT = ('move',)

GI = {'min': 5, 'pts': 6, 'reb': 7, 'ast': 8, '3pm': 9, 'stl': 10, 'blk': 11, 'tov': 12, 'fgm': 13, 'fga': 14, 'ftm': 15,
      'fta': 16, 'tpa': 17, 'oreb': 18, 'dreb': 19, 'pf': 20}
COMBO = {'pra': ['pts', 'reb', 'ast'], 'pr': ['pts', 'reb'], 'pa': ['pts', 'ast'], 'ra': ['reb', 'ast'], 'sb': ['stl', 'blk']}
OPP_STAT = {'pts': 'fga', 'pra': 'fga', 'pr': 'fga', 'pa': 'fga', 'fgm': 'fga', '3pm': 'tpa'}
RANK_STATS = ('pts', 'reb', 'ast', '3pm', 'stl', 'blk', 'tov', 'pra', 'pr', 'pa', 'ra', 'sb')


def gval(g, s):
    return sum(g[GI[k]] for k in COMBO[s]) if s in COMBO else g[GI[s]] if s in GI else None


def level(p):
    d = abs(p - 0.5)
    return 1 + sum(d >= c for c in LEVEL_CUTS)


class Logs:
    """Point-in-time views of gamelogs.json: only games before the prop's day."""
    def __init__(self):
        gl = json.load(open(os.path.join(DATA, 'gamelogs.json')))
        self.teams, self.cur = gl['teams'], gl['current_season']
        self.p = {int(k): [r for r in v if not r[4]] for k, v in gl['players'].items()}      # newest first, no playoffs
        pp = json.load(open(os.path.join(DATA, 'player_projections.json')))
        self.grp = {pl['id']: pl.get('grp') or pl.get('pos') for t in pp['teams'].values() for pl in t['players']}
        self._rank = {}
        # season games per (opponent team, day): who played against whom, for allowed-per-game ranks
        self.allow = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # (team) -> day -> key -> total
        for pid, rows in self.p.items():
            g = self.grp.get(pid)
            if not g:
                continue
            for r in rows:
                if r[1] != self.cur:
                    continue
                t = self.teams[r[2]]
                for s in RANK_STATS:
                    self.allow[t][r[0]][f'{g}|{s}'] += gval(r, s)
                self.allow[t][r[0]]['_'] = 1

    def before(self, pid, day):
        return [r for r in self.p.get(pid, []) if r[0] < day]

    def rank(self, team, grp, stat, day):
        """1 = allows the fewest of `stat` to `grp` per game this season before `day`; None with too few games."""
        key = (day, grp, stat)
        if key not in self._rank:
            per = {}
            for t, days in self.allow.items():
                ds = [d for d in days if d < day]
                if len(ds) >= RANK_MIN_GAMES:
                    per[t] = sum(days[d].get(f'{grp}|{stat}', 0.0) for d in ds) / len(ds)
            self._rank[key] = {t: i + 1 for i, (t, _) in enumerate(sorted(per.items(), key=lambda z: z[1]))} if len(per) >= 20 else {}
        return self._rank[key].get(team)


def signals(row, C, logs, opp_team, first_line):
    """{name: 'O' | 'U' | None} for one lean row (dict by column)."""
    pid, s, line, day = row['pid'], row['stat'], row['line'], row['_day']
    prev = logs.before(pid, day)
    out = {'model': 'O' if row['p'] > 0.5 else 'U'}
    pm = row.get('p_mkt')
    out['market'] = None if pm is None or abs(pm - 0.5) < MKT_MIN else 'O' if pm > 0.5 else 'U'
    g = logs.grp.get(pid)
    rk = logs.rank(opp_team, g, s, day) if g and s in RANK_STATS and opp_team else None
    out['matchup'] = None if rk is None else 'O' if rk >= RANK_SOFT else 'U' if rk <= RANK_TOUGH else None
    l5 = prev[:5]
    if row.get('min') is not None and len(l5) == 5:
        d = row['min'] - sum(r[GI['min']] for r in l5) / 5
        out['minutes'] = 'O' if d >= MIN_DELTA else 'U' if d <= -MIN_DELTA else None
    else:
        out['minutes'] = None
    os_ = OPP_STAT.get(s)
    if os_ and len(prev) >= 20:
        a, b = sum(r[GI[os_]] for r in prev[:5]) / 5, sum(r[GI[os_]] for r in prev[5:20]) / 15
        out['opp'] = None if b <= 0 else 'O' if a >= b * (1 + OPP_DELTA) else 'U' if a <= b * (1 - OPP_DELTA) else None
    else:
        out['opp'] = None
    l10 = [gval(r, s) for r in prev[:10]] if s in GI or s in COMBO else []
    if len(l10) == 10 and all(v is not None for v in l10):
        hr = sum(v > line for v in l10) / 10
        out['form'] = 'O' if hr >= FORM_HI else 'U' if hr <= FORM_LO else None
    else:
        out['form'] = None
    out['move'] = None if first_line is None or first_line == line else 'O' if line > first_line else 'U'
    return out


def git(*a):
    return subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout


def load_days():
    out = {}
    for name in sorted(git('ls-tree', '--name-only', f'{BRANCH}:leans').split()):
        if name.endswith('.json'):
            try:
                out[name[:-5]] = json.loads(git('show', f'{BRANCH}:leans/{name}'))
            except ValueError:
                pass
    return out


class Rec:
    """n, wins, market-expected wins; standard error of the mean (win - expected) clustered by player-night."""
    def __init__(self):
        self.n = self.w = 0; self.e = 0.0; self.cl = defaultdict(lambda: [0.0, 0]); self.pn = 0; self.u = 0.0

    def add(self, win, exp, night, units=None):
        self.n += 1; self.w += int(win); self.e += exp
        c = self.cl[night]; c[0] += int(win) - exp; c[1] += 1
        if units is not None:
            self.pn += 1; self.u += units

    def out(self):
        if not self.n:
            return [0, 0, 0.0, None, 0, 0.0]
        m, G = (self.w - self.e) / self.n, len(self.cl)
        se = math.sqrt(G / (G - 1) * sum((D - m * k) ** 2 for D, k in self.cl.values())) / self.n if G > 1 else None
        return [self.n, self.w, round(self.e, 2), round(se, 4) if se is not None else None, self.pn, round(self.u, 2)]


def units(price, win):
    """1-unit result at an American price string, or None when no price is stored."""
    try:
        a = float(str(price).replace('+', ''))
    except (TypeError, ValueError):
        return None
    if not a or abs(a) < 100:
        return None
    return (a / 100 if a > 0 else 100 / -a) if win else -1.0


def tier_of(lv, k_for, k_against):
    """Fixed verdict tiers, defined before any results were read (not fitted):
       strong  model level 3-4, 3+ counted checks agree, none against
       lean    2+ agree and more agree than disagree
       split   anything else with at least one check on each side, or nothing beyond the model
       against more checks disagree than agree"""
    if k_against > k_for:
        return 'against'
    if lv >= 3 and k_for >= 3 and k_against == 0:
        return 'strong'
    if k_for >= 2 and k_for > k_against:
        return 'lean'
    return 'split'


def build():
    days = load_days()
    logs = Logs()
    T = lambda: defaultdict(Rec)
    sig, lev, agree, by_day = defaultdict(T), defaultdict(Rec), defaultdict(Rec), defaultdict(lambda: defaultdict(Rec))
    tier, tier_day = defaultdict(Rec), defaultdict(lambda: defaultdict(Rec))
    nights = sorted(days)
    half = nights[len(nights) // 2] if nights else None
    n_rows = 0
    for day_s in nights:
        d = days[day_s]
        C = d['cols']; ix = {c: i for i, c in enumerate(C)}
        day = (dt.date.fromisoformat(day_s) - EPOCH).days
        first = {}
        for r in d['rows']:
            if r[ix['clock']] == 'f':
                first[(r[ix['game']], r[ix['pid']], r[ix['stat']])] = r[ix['line']]
        games = d.get('games', {})
        for r in d['rows']:
            if r[ix['clock']] != 'c' or r[ix['y']] is None or r[ix['p']] is None or r[ix['p_mkt']] is None:
                continue
            row = {c: r[i] for c, i in ix.items()}; row['_day'] = day
            y, line = row['y'], row['line']
            if y == line:
                continue                                                   # push
            over = y > line
            mt = games.get(row['game'], [''])[0]
            a, h = (mt.split(' @ ') + [None])[:2] if ' @ ' in mt else (None, None)
            opp = h if row['team'] == a else a if row['team'] == h else None
            sg = signals(row, C, logs, opp, first.get((row['game'], row['pid'], row['stat'])))
            night = (row['game'], row['pid'])
            pm = row['p_mkt']
            half_k = 'h1' if day_s < half else 'h2'
            for name, side in sg.items():
                if side is None:
                    continue
                win = over if side == 'O' else not over
                exp = pm if side == 'O' else 1 - pm
                for k in ('all', side.lower(), half_k):
                    sig[name][k].add(win, exp, night)
            ms = sg['model']
            mwin = over if ms == 'O' else not over
            mexp = pm if ms == 'O' else 1 - pm
            mu_ = units(row.get('price'), mwin)                        # the stored best price on the model's side at that look
            lev[str(level(row['p']))].add(mwin, mexp, night, mu_)
            k_for = sum(sg[c] == ms for c in COUNTED); k_against = sum(sg[c] is not None and sg[c] != ms for c in COUNTED)
            agree[f'{k_for}|{k_against}'].add(mwin, mexp, night, mu_)
            tier[tier_of(level(row['p']), k_for, k_against)].add(mwin, mexp, night, mu_)
            tier_day[day_s][tier_of(level(row['p']), k_for, k_against)].add(mwin, mexp, night, mu_)
            by_day[day_s][f'{k_for}|{k_against}'].add(mwin, mexp, night, mu_)
            n_rows += 1
    return {'t': int(time.time()), 'first': nights[0] if nights else None, 'through': nights[-1] if nights else None, 'n': n_rows,
            'half': half, 'counted': list(COUNTED), 'context': list(CONTEXT),
            'defs': {'level': LEVEL_CUTS, 'mkt': MKT_MIN, 'rank': [RANK_TOUGH, RANK_SOFT, RANK_MIN_GAMES], 'min': MIN_DELTA,
                     'opp': OPP_DELTA, 'form': [FORM_LO, FORM_HI]},
            'sig': {n: {k: v.out() for k, v in d.items()} for n, d in sig.items()},
            'level': {k: v.out() for k, v in sorted(lev.items())},
            'agree': {k: v.out() for k, v in sorted(agree.items())},
            'tier': {k: v.out() for k, v in sorted(tier.items())},
            'tier_days': {dd: {k: v.out() for k, v in a.items()} for dd, a in sorted(tier_day.items())},
            'days': {dd: {k: v.out() for k, v in a.items()} for dd, a in sorted(by_day.items())}}


def write():
    rep = build()
    tmp = OUT + '.tmp'
    json.dump(rep, open(tmp, 'w'), separators=(',', ':'))
    os.replace(tmp, OUT)
    return rep


if __name__ == '__main__':
    r = write()
    print('props', r['n'], r['first'], '->', r['through'])
