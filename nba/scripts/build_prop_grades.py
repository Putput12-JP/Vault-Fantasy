#!/usr/bin/env python3
"""
Prop grades: one A+ to D grade per NBA prop from three fixed parts (matchup, projection, situation), and this season's record
for every grade, rebuilt from the lean recorder (leans/<day>.json on the nba-data branch: every prop at its last look before tip).

Points are signed: positive favours the Over, negative the Under. The grade is the size of the total, on the side it favours.

  matchup     opponent's rank allowing this stat to his position group this season (same ranks as the Signals matchup check):
              26th-30th +2, 21st-25th +1, 6th-10th -1, 1st-5th -2. Not ranked (under 5 games, or a stat that is not ranked) = 0.
  projection  Vault's side by Props Sim level (same cuts as Signals): level 1 or 2 = 1 point, level 3 = 2, level 4 = 3.
  minutes     projected minutes vs his last 5 games: +5 or more +2, +2 or more +1, -2 or less -1, -5 or less -2.
  teammate    Over only: a teammate who averages 20+ minutes is out. Two or more out, or one who averages 28+ = +2, one = +1.

  |total| 7+ A+   6 A   5 A-   4 B+   3 B   2 C   0 or 1 D

The cuts were fixed by how often each grade should appear (A+ about 1 prop in 100), not by results. They were never tuned on the record.
Each grade is scored against what the no-vig market already expected for the side it points to, so a grade "works" only if that side won
more often than the market's own chance said it would.

TEAMMATE OUT, IN THE REBUILD: the recorder keeps no injury status, so a teammate counts as out when he has no game that night. That
knows a late scratch and an in-game exit, so the rebuild is slightly generous to this part. The live column reads the board's OUT / doubtful / inactive tags.

Writes data/prop_grades.json:
  {"t", "first", "through", "n", "half", "cuts", "grade": {G: rec}, "side": {"G|o": rec, "G|u": rec}, "h1": {G: rec}, "h2": {G: rec},
   "grade_days": {day: {G: rec}}}
  rec = [n, wins, market-expected wins, clustered standard error of (win - expected) per prop, priced n, units]
  units are only counted when the graded side is also the model's side (the stored price is the model's side). Pushes and voids are left out.

  python3 nba/scripts/build_prop_grades.py           # also run by build_data_health.py
"""
import datetime as dt, json, os, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_prop_signals as S

OUT = os.path.join(S.DATA, 'prop_grades.json')
GRADES = ('A+', 'A', 'A-', 'B+', 'B', 'C', 'D')
LEVEL_PTS = {1: 1, 2: 1, 3: 2, 4: 3}
MATE_MPG, MATE_BIG = 20.0, 28.0


def grade_of(total):
    a = abs(total)
    return 'A+' if a >= 7 else 'A' if a == 6 else 'A-' if a == 5 else 'B+' if a == 4 else 'B' if a == 3 else 'C' if a == 2 else 'D'


def points(rank, p, mins_delta, mates_out):
    """(matchup, projection, minutes, teammate, total): signed, positive = Over. mates_out = list of those teammates' minutes per game."""
    m = 0 if rank is None else 2 if rank >= 26 else 1 if rank >= 21 else -2 if rank <= 5 else -1 if rank <= 10 else 0
    pr = LEVEL_PTS[S.level(p)] * (1 if p > 0.5 else -1)
    mi = 0 if mins_delta is None else 2 if mins_delta >= 5 else 1 if mins_delta >= 2 else -2 if mins_delta <= -5 else -1 if mins_delta <= -2 else 0
    mo = 2 if len(mates_out) >= 2 or any(x >= MATE_BIG for x in mates_out) else 1 if mates_out else 0
    return m, pr, mi, mo, m + pr + mi + mo


def build():
    days = S.load_days()
    logs = S.Logs()
    pp = json.load(open(os.path.join(S.DATA, 'player_projections.json')))
    roster = defaultdict(list)
    for t, v in pp['teams'].items():
        for pl in v['players']:
            roster[t].append(pl['id'])
    played = {pid: {g[0] for g in rows} for pid, rows in logs.p.items()}
    T = lambda: defaultdict(S.Rec)
    allr, side, h1, h2, by_day = T(), defaultdict(S.Rec), T(), T(), defaultdict(T)
    nights = sorted(days)
    half = nights[len(nights) // 2] if nights else None
    n_rows = 0
    for day_s in nights:
        d = days[day_s]
        ix = {c: i for i, c in enumerate(d['cols'])}
        day = (dt.date.fromisoformat(day_s) - S.EPOCH).days
        games = d.get('games', {})
        for r in d['rows']:
            if r[ix['clock']] != 'c' or r[ix['y']] is None or r[ix['p']] is None or r[ix['p_mkt']] is None:
                continue
            row = {c: r[i] for c, i in ix.items()}
            if row['y'] == row['line']:
                continue
            pid, s_, team = row['pid'], row['stat'], row['team']
            prev = logs.before(pid, day)
            if len(prev) < 8:
                continue
            mt = games.get(row['game'], [''])[0]
            a, h = (mt.split(' @ ') + [None])[:2] if ' @ ' in mt else (None, None)
            opp = h if team == a else a if team == h else None
            g = logs.grp.get(pid)
            rank = logs.rank(opp, g, s_, day) if g and s_ in S.RANK_STATS and opp else None
            l5 = prev[:5]
            md = (row['min'] - sum(x[S.GI['min']] for x in l5) / 5) if row.get('min') is not None and len(l5) == 5 else None
            mo = []
            for m in roster.get(team, []):
                if m == pid or day in played.get(m, ()):
                    continue
                pm = [x for x in logs.p.get(m, []) if x[0] < day and x[1] == logs.cur]
                if len(pm) < 5:
                    continue
                mpg = sum(x[S.GI['min']] for x in pm[:10]) / len(pm[:10])
                if mpg >= MATE_MPG:
                    mo.append(mpg)
            *_, total = points(rank, row['p'], md, mo)
            if total == 0:
                gr, over_side = 'D', row['p'] > 0.5
            else:
                gr, over_side = grade_of(total), total > 0
            over = row['y'] > row['line']
            win = over if over_side else not over
            pm_ = row['p_mkt']
            exp = pm_ if over_side else 1 - pm_
            night = (row['game'], pid)
            u = S.units(row.get('price'), win) if over_side == (row['p'] > 0.5) else None
            for rec in (allr[gr], side[f'{gr}|{"o" if over_side else "u"}'], (h1 if day_s < half else h2)[gr], by_day[day_s][gr]):
                rec.add(win, exp, night, u)
            n_rows += 1
    out = lambda dd: {k: v.out() for k, v in sorted(dd.items())}
    return {'t': int(time.time()), 'first': nights[0] if nights else None, 'through': nights[-1] if nights else None, 'n': n_rows, 'half': half,
            'cuts': {'matchup': [5, 10, 21, 26], 'level': LEVEL_PTS, 'minutes': [2, 5], 'mate': [MATE_MPG, MATE_BIG], 'grades': list(GRADES)},
            'grade': out(allr), 'side': out(side), 'h1': out(h1), 'h2': out(h2),
            'grade_days': {dd: out(a) for dd, a in sorted(by_day.items())}}


def write():
    rep = build()
    tmp = OUT + '.tmp'
    json.dump(rep, open(tmp, 'w'), separators=(',', ':'))
    os.replace(tmp, OUT)
    return rep


if __name__ == '__main__':
    r = write()
    print('props', r['n'], r['first'], '->', r['through'])
    for g in GRADES:
        rc = r['grade'].get(g)
        if rc and rc[0]:
            print(f'{g:2s} n={rc[0]:5d} hit={rc[1] / rc[0] * 100:4.1f} mkt={rc[2] / rc[0] * 100:4.1f} roi={rc[5] / rc[4] * 100 if rc[4] else float("nan"):+5.1f}% on {rc[4]}')
