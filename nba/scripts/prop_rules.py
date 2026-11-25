#!/usr/bin/env python3
"""
Sharp Money V2 Plays rules for NBA props (Jacob's request, 2026-11-25). The NBA prop board's own track record picked two groups that the V2
gates (rule C: fairs within 1 point, Kalshi quoting, 3%+ over the exchange) mostly pass over. This file says, for every prop on tonight's
board, which of those groups it is in, so sharp-money/v2/gates.js (applyRules) can make it a Play at the US book price the board shows.

  nba-sig5   all five counted Signals checks (market no-vig, matchup, minutes, shot volume, form last 10) point the same way as the Vault model
             (build_prop_signals.py, bucket 5|0). Record when the rule was set (prop_signals.json, nights through Nov 24 2026): 20-3 on 23,
             +28.3% ROI; 12-1 (+40.8%) on the nights after the Nov 8 freeze, so only that part is out of sample.
  nba-aplus  an A+ grade (build_prop_grades.py, |points| 7+) on Pts + Reb + Ast, Reb + Ast or Pts + Ast, on the side the grade favours.
             Record when the rule was set (prop_grades.json 'stat', through Nov 24 2026): PRA 21-11 on 32 (+20.3%), RA 16-5 on 21 (+42.3%),
             PA 21-9 on 30 (+21.4%). The stat split was chosen on those same rows: in-sample.
  nba-reb-a  Rebounds graded A+, A or A- on the Vault model's side (grade side = model side). Record when the rule was set (lean files, the same
             rebuild, Oct 22 - Nov 24 2026): 199-133 on 332, +38.78u, +12.4% ROI on 313 priced (A+ +9.1%, A +14.0%, A- +12.6%). In-sample:
             rebounds were picked because they were positive at every A grade.

Nothing is fitted here: every cut comes from build_prop_signals.py and build_prop_grades.py, which were frozen before the records above were read.
The inputs are the lean recorder's rows for this poll (lean_record.log: line, model chance, no-vig market chance, projected minutes) and the
game logs before tonight (build_prop_signals.Logs, the same point-in-time view the records were rebuilt with).

TEAMMATE OUT (grade part 4) reads the board's injury and lineup tags (Out, Doubtful, Inactive) and each teammate's minutes from
player_projections.json (min0, else last season's), the same as the Props page's live grade column. The rebuilt record counted a teammate as
out when he had no game that night, which knows late scratches, so the live grade can be a notch lower than the rebuild's on a late scratch.

Writes board['rules'] = {'v': 1, 't': poll time, 'rows': {'<game>|<pid>|<stat>': [line, model side, agree, against, grade, grade side, model edge]}}
  model side and grade side are 'O' or 'U'; grade is 'A+'..'D'; model edge = model chance of its side minus the no-vig market chance of that side
  (gates.js ranks the nightly nba-reb-a cap by it). Only rows in at least one rule group are written, to keep the board small.
"""
import datetime as dt, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_prop_signals as S      # noqa: E402
import build_prop_grades as GR      # noqa: E402

RULES_V = 1
APLUS_STATS = ('pra', 'ra', 'pa')
REB_GRADES = ('A+', 'A', 'A-')
ET = dt.timezone(dt.timedelta(hours=-5))      # the lean files name a night by its ET date; only the date matters, so a fixed offset is enough a few hours either side
OUT_RE = re.compile(r'out|doubt|inactive', re.I)

_LOGS = {'mt': None, 'logs': None}


def logs():
    """build_prop_signals.Logs, rebuilt only when gamelogs.json or player_projections.json changes (it reads the whole season)."""
    mt = tuple(os.path.getmtime(os.path.join(S.DATA, f)) for f in ('gamelogs.json', 'player_projections.json'))
    if _LOGS['mt'] != mt:
        _LOGS['logs'], _LOGS['mt'] = S.Logs(), mt
    return _LOGS['logs']


def night(tip):
    return (dt.datetime.fromtimestamp(tip, ET).date() - S.EPOCH).days


def roster_mins(proj):
    """team -> [(pid, minutes a game)] from player_projections.json, as the Props page reads it (min0, else last season's mpg)."""
    out = {}
    for t, v in (proj.get('teams') or {}).items():
        out[t] = [(int(pl['id']), pl.get('min0') or pl.get('last_mpg') or 0) for pl in v.get('players') or []]
    return out


def evaluate(lrows, lmeta, status, roster, L):
    """{lean key: [line, model side, agree, against, grade, grade side, model edge]} for the leans in a rule group.
    lrows / lmeta: lean_record.log output. status: pid -> injury / lineup tag. roster: roster_mins(). L: Logs."""
    out = {}
    for k, v in lrows.items():
        m = lmeta.get(k) or {}
        if not m or m.get('stat') is None:
            continue
        line, p, p_mkt, mins = v[0], v[3], v[6], v[7]
        if p is None or p_mkt is None:                      # the records only count rows with a model chance and a no-vig market chance
            continue
        mt, team, pid, s_ = m.get('matchup') or '', m.get('team'), int(m['pid']), m['stat']
        a, h = (mt.split(' @ ') + [None])[:2] if ' @ ' in mt else (None, None)
        opp = h if team == a else a if team == h else None
        day = night(m['tip'])
        row = {'pid': pid, 'stat': s_, 'line': line, 'p': p, 'p_mkt': p_mkt, 'min': mins, '_day': day}
        sg = S.signals(row, None, L, opp, None)
        ms = sg['model']
        kf = sum(sg[c] == ms for c in S.COUNTED)
        ka = sum(sg[c] is not None and sg[c] != ms for c in S.COUNTED)
        prev = L.before(pid, day)
        if len(prev) < 8:                                   # build_prop_grades.py grades a player only with 8+ earlier games
            gr, gs = None, None
        else:
            g = L.grp.get(pid)
            rank = L.rank(opp, g, s_, day) if g and s_ in S.RANK_STATS and opp else None
            l5 = prev[:5]
            md = (mins - sum(x[S.GI['min']] for x in l5) / 5) if mins is not None and len(l5) == 5 else None
            mo = [mp for q, mp in roster.get(team, []) if q != pid and mp >= GR.MATE_MPG and OUT_RE.search(status.get(q) or '')]
            *_, total = GR.points(rank, p, md, mo)
            gr, gs = (GR.grade_of(total), 'O' if total > 0 else 'U') if total else ('D', ms)
        if kf == 5 or (gr == 'A+' and s_ in APLUS_STATS) or (s_ == 'reb' and gr in REB_GRADES and gs == ms):
            edge = round((p - p_mkt) if ms == 'O' else (p_mkt - p), 4)   # model edge: the model's chance of its side minus the no-vig market's
            out[k] = [line, ms, kf, ka, gr, gs, edge]
    return out


def attach(board, lrows, lmeta, now):
    """Add board['rules'] for this poll. Never raises into the recorder: a failure leaves the board without rules (no rule plays this poll)."""
    import pricing as PX
    proj = json.load(open(os.path.join(S.DATA, 'player_projections.json')))
    board['rules'] = {'v': RULES_V, 't': now, 'rows': evaluate(lrows, lmeta, PX.status_from_board(board), roster_mins(proj), logs())}
    return board['rules']
